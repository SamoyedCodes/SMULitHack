"""SQLite-backed conflict scheduling. Reads never spend allowance or enqueue work."""
import hashlib
import json
import time
import uuid
from itertools import combinations

from .conflicts import (CONFLICT_VERSION, JOB_KIND, complete, insufficient, pair_id, screen,
                        time_comparison, validate_assessment)
from .documents import load_pages
from .models import ConflictAssessment, ConflictScan, ConflictScreen, Document, ReviewIssue
from .store import now

ACTIVE = {'queued','running','waiting'}


def read_sources(config, documents):
    pages,hashes={},{}
    for doc in documents:
        try:
            path=config.directory(doc.id,create=False)/'pages.json'
            if path.is_symlink(): raise ValueError('Invalid checkpoint')
            data=path.read_bytes()
            hashes[doc.id]=hashlib.sha256(data).hexdigest()
            pages[doc.id]=load_pages(path)
        except (OSError,ValueError):
            pages[doc.id]=[]
            hashes[doc.id]='unavailable'
    return pages,hashes


def setting(db,key,default=None):
    row=db.execute('SELECT value FROM settings WHERE key=?',(key,)).fetchone()
    return json.loads(row['value']) if row else default


def save_setting(db,key,value):
    db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',(key,json.dumps(value)))


def documents_in(db,mode):
    return [Document.model_validate_json(r['body']) for r in db.execute('SELECT body FROM documents WHERE mode=?',(mode,))]


def screen_rows(db,mode):
    return [ConflictScreen.model_validate_json(r['body']) for r in db.execute('SELECT body FROM conflict_screens WHERE mode=?',(mode,))]


def jobs_in(db,mode):
    return [dict(r) for r in db.execute("SELECT * FROM jobs WHERE kind=? AND json_extract(payload,'$.mode')=? AND json_extract(payload,'$.version')=?",(JOB_KIND,mode,CONFLICT_VERSION))]


def save_screen(db,record):
    # Job status is a read-time projection, not a second queue state machine.
    db.execute('INSERT OR REPLACE INTO conflict_screens VALUES(?,?,?)',(record.id,record.mode,record.model_dump_json()))


def text_size(pages):
    return sum(len(f'[document_id={s.document_id} page={s.page} span_id={s.id} source={s.source}]\n{s.text}')+1 for p in pages for s in p.spans)


def reconcile(config,store,mode,grant_key=None):
    """Serialize budget allocation, idempotency and source snapshots in one transaction."""
    from .foundation import CAPABILITIES
    if not CAPABILITIES.conflicts: return
    routing=config.routing_identity
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        sme=setting(db,'sme:'+mode)
        docs=documents_in(db,mode)
        pages,hashes=read_sources(config,docs)
        budget=setting(db,'conflict-budget:'+mode,{'allowance':10,'assigned':0})
        records=[]
        if sme:
            for a,b in combinations(sorted(docs,key=lambda d:d.id),2):
                record=screen(a,b,pages,hashes,sme,routing)
                if record.outcome=='candidate' and text_size(pages[a.id])+text_size(pages[b.id])>240000:
                    record.outcome='needs_evidence'
                    record.reason='The complete pair exceeds the 240,000-character context budget; no text was truncated.'
                records.append(record)
        current={r.id:r for r in records}
        jobs=jobs_in(db,mode)
        for job in jobs:
            if job['cache_key'] not in current or current[job['cache_key']].outcome!='candidate':
                if job['state'] in ACTIVE:
                    db.execute("UPDATE jobs SET state='superseded',error='Inputs changed; this comparison is stale.' WHERE id=?",(job['id'],))
        existing={r['id']:ConflictAssessment.model_validate_json(r['body']) for r in db.execute('SELECT * FROM comparisons WHERE mode=?',(mode,))}
        for result in existing.values():
            result.current=result.id in current and result.input_revision==result.id
            db.execute('UPDATE comparisons SET body=? WHERE id=?',(result.model_dump_json(),result.id))
        for old in screen_rows(db,mode):
            if old.id not in current:
                old.current=False
                save_screen(db,old)
        for record in records:
            save_screen(db,record)
            if record.outcome=='needs_evidence' and record.id not in existing:
                result=insufficient(record,record.reason)
                result.current=True;result.created_at=now()
                db.execute('INSERT INTO comparisons VALUES(?,?,?)',(result.id,mode,result.model_dump_json()))
                existing[result.id]=result
        # Returning to identical inputs reuses the already assigned slot.
        for record in records:
            if record.outcome=='candidate' and record.id not in existing:
                db.execute("UPDATE jobs SET state='queued',error=NULL WHERE cache_key=? AND kind=? AND state='superseded' AND json_extract(payload,'$.version')=?",
                           (record.id,JOB_KIND,CONFLICT_VERSION))
        jobs=jobs_in(db,mode)
        by_key={j['cache_key']:j for j in jobs}
        backlog=[r for r in records if r.outcome=='candidate' and r.id not in existing and r.id not in by_key]
        active=any(j['state'] in ACTIVE and j['cache_key'] in current for j in jobs)
        if grant_key:
            receipt_key='conflict-continue:'+mode+':'+grant_key
            if not setting(db,receipt_key):
                if not sme or active or not backlog or budget['assigned']<budget['allowance']:
                    raise ValueError('Continue is available only when comparisons are paused with unchecked pairs.')
                budget['allowance']+=10
                save_setting(db,receipt_key,True)
        for record in sorted(backlog,key=lambda r:(r.priority,r.documents)):
            if budget['assigned']>=budget['allowance']:break
            payload={'mode':mode,'documents':record.documents,'revision':record.id,'sme':sme,'version':CONFLICT_VERSION}
            db.execute('INSERT INTO jobs(id,cache_key,kind,payload,created_at) VALUES(?,?,?,?,?)',
                       (str(uuid.uuid4()),record.id,JOB_KIND,json.dumps(payload),now()))
            budget['assigned']+=1
        save_setting(db,'conflict-budget:'+mode,budget)


def snapshot(config,store,mode):
    """Pure projection. Revalidate revisions so even externally changed sources appear stale."""
    from .foundation import CAPABILITIES
    with store.connection() as db:
        docs=documents_in(db,mode)
        sme=setting(db,'sme:'+mode)
        budget=setting(db,'conflict-budget:'+mode,{'allowance':10,'assigned':0})
        records=screen_rows(db,mode)
        jobs=jobs_in(db,mode)
        results=[ConflictAssessment.model_validate_json(r['body']) for r in db.execute('SELECT body FROM comparisons WHERE mode=?',(mode,))]
    pages,hashes=read_sources(config,docs)
    by_doc={d.id:d for d in docs}
    routing=config.routing_identity
    current_ids=set()
    for record in records:
        pair=[by_doc.get(id) for id in record.documents]
        record.current=bool(CAPABILITIES.conflicts and sme and len(pair)==2 and all(pair)
                            and pair_id(*pair,hashes,sme,routing)==record.id)
        if record.current:current_ids.add(record.id)
    jobs_by_key={j['cache_key']:j for j in jobs}
    for record in records:
        job=jobs_by_key.get(record.id)
        if job:record.job_state,record.error=job['state'],job['error']
    for result in results:
        result.current=result.id in current_ids and result.input_revision==result.id
    active_records=[r for r in records if r.current]
    present_results={r.id for r in results if r.current}
    summary=ConflictScan(**budget,total_pairs=len(docs)*(len(docs)-1)//2,
        unscreened=max(0,len(docs)*(len(docs)-1)//2-len(active_records)),
        candidates=sum(r.outcome=='candidate' for r in active_records),
        excluded=sum(r.outcome=='excluded' for r in active_records),
        needs_evidence=sum(r.outcome=='needs_evidence' for r in active_records),
        unprocessed_documents=sum(not complete(d,pages[d.id]) for d in docs),
        completed=sum(r.outcome=='candidate' and r.id in present_results for r in active_records),
        unchecked=sum(r.outcome=='candidate' and r.id not in present_results and r.id not in jobs_by_key for r in active_records))
    for state in ['queued','running','waiting','blocked','failed']:
        setattr(summary,state,sum(j['state']==state and j['cache_key'] in current_ids for j in jobs))
    active=summary.queued+summary.running+summary.waiting
    summary.can_continue=bool(CAPABILITIES.conflicts and sme and summary.unchecked and not active and summary.assigned>=summary.allowance)
    summary.state=('disabled' if not CAPABILITIES.conflicts else 'awaiting_sme' if not sme else 'running' if active
                   else 'paused' if summary.can_continue else 'needs_review' if summary.unscreened or summary.needs_evidence or summary.unprocessed_documents or summary.failed or summary.blocked else 'ready')
    issues=[]
    for result in results:
        if result.current and result.status!='no_conflict_identified_for_this_rule':
            issues.append(ReviewIssue(id='conflict:'+result.id,document_ids=result.documents,
                title='Potential distribution conflict' if result.status=='potential_conflict' else 'Distribution comparison needs evidence',
                established=[result.explanation] if result.status=='potential_conflict' else [],
                missing_facts=result.missing_facts,lawyer_question=result.lawyer_question,
                evidence=result.evidence,kind='conflict',mode=mode,
                urgency='Review before exercising or extending these distribution rights.'))
    return summary,records,results,issues


def retry_comparison(config,store,mode,comparison_id):
    reconcile(config,store,mode)
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT body FROM conflict_screens WHERE id=? AND mode=?',(comparison_id,mode)).fetchone()
        if not row or not ConflictScreen.model_validate_json(row['body']).current:
            raise ValueError('This comparison is stale or unavailable.')
        return db.execute("UPDATE jobs SET state='queued',error=NULL WHERE cache_key=? AND kind=? AND state IN ('failed','blocked') AND json_extract(payload,'$.mode')=? AND json_extract(payload,'$.version')=?",
                          (comparison_id,JOB_KIND,mode,CONFLICT_VERSION)).rowcount


def process_comparison(config,store,job,llm):
    payload=job['payload'];mode=payload['mode']
    if payload.get('version')!=CONFLICT_VERSION:
        store.job_state(job['id'],'superseded','Unrecognized comparison version.');return
    reconcile(config,store,mode)
    with store.connection() as db:
        row=db.execute('SELECT body FROM conflict_screens WHERE id=?',(job['cache_key'],)).fetchone()
    record=ConflictScreen.model_validate_json(row['body']) if row else None
    if not record or not record.current or record.outcome!='candidate':
        store.job_state(job['id'],'superseded','The comparison inputs changed.');return
    a,b=[store.document(id) for id in record.documents]
    pages,hashes=read_sources(config,[a,b])
    if pair_id(a,b,hashes,payload['sme'],config.routing_identity)!=record.id:
        store.job_state(job['id'],'superseded','The comparison inputs changed.');return
    from .llm import text_context
    comparison=time_comparison(a,b,pages)
    if text_size(pages[a.id])+text_size(pages[b.id])>240000:
        result=insufficient(record,'The complete pair exceeds the context budget; no text was truncated.')
    else:
        from .llm import InvalidModelOutput
        try:
            draft=llm.compare({'selected_sme':payload['sme'],'documents':[
                {'id':d.id,'provisions':[p.model_dump() for p in d.provisions],
                 'support_reviews':[v.model_dump() for v in d.reviews],'text':text_context(pages[d.id])} for d in (a,b)],
                 'python_time_comparison':comparison})
            result=validate_assessment(draft,a,b,pages,record,comparison)
            use=getattr(llm,'last_use',None)
            if use:result.model_usage=[use]
        except InvalidModelOutput:
            result=insufficient(record,'The returned model answer could not be validated; no substantive conclusion was published.')
    result.created_at=now()
    # Re-read source revisions inside the final transaction: never publish a late stale result.
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        docs={d.id:d for d in documents_in(db,mode)}
        pair=[docs.get(id) for id in record.documents]
        fresh_pages,fresh_hashes=read_sources(config,[d for d in pair if d])
        from .foundation import CAPABILITIES
        result.current=bool(CAPABILITIES.conflicts and setting(db,'sme:'+mode)==payload['sme'] and all(pair)
                            and pair_id(*pair,fresh_hashes,payload['sme'],config.routing_identity)==record.id)
        db.execute('INSERT OR REPLACE INTO comparisons VALUES(?,?,?)',(result.id,mode,result.model_dump_json()))
        db.execute('UPDATE jobs SET state=?,error=NULL WHERE id=?',('complete' if result.current else 'superseded',job['id']))
