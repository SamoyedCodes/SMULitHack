import { useEffect, useRef, useState } from 'react'
import { continueConflicts, fetchConflictScreens, retryConflict, type ConflictAssessment, type ConflictScreen, type Evidence, type Portfolio } from './api'
import './conflicts.css'

const labels = {potential_conflict:'Potential conflict',no_conflict_identified_for_this_rule:'No conflict identified for this rule',insufficient_evidence:'Insufficient evidence'}

export function EvidenceLinks({ items, onEvidence }: {items:Evidence[]; onEvidence:(e:Evidence)=>void}) {
  return <ul className="conflict-evidence">{items.map((e,i)=><li key={i}><blockquote>{e.quote}</blockquote><button className="contract-link" onClick={()=>onEvidence(e)}>Page {e.page}{e.clause ? ` · Clause ${e.clause}` : ''}{e.source==='ocr' ? ' · OCR' : ''}</button></li>)}</ul>
}

export function ConflictCard({ result, names, onEvidence, focused }: {result:ConflictAssessment; names:Map<string,string>; onEvidence:(e:Evidence)=>void; focused:boolean}) {
  const card=useRef<HTMLElement>(null)
  useEffect(()=>{if(focused)card.current?.scrollIntoView({block:'start',behavior:'smooth'})},[focused])
  return <article ref={card} id={`conflict-${result.id}`} className={`card conflict-card ${focused?'conflict-focused':''}`}>
    <div className="section-heading"><h2>{labels[result.status]}</h2><span className={`badge ${result.status==='potential_conflict'?'amber':''}`}>{result.provenance} · {result.confidence} confidence</span></div>
    <p className="conflict-documents">{result.documents.map(id=>names.get(id)??id).join(' ↔ ')}</p>
    {!result.current && <p className="error">Stale assessment: source analysis or SME selection has changed. Do not rely on this result.</p>}
    <p>{result.explanation}</p><p className="finding-reason">{result.confidence_reason}</p>
    {result.status==='no_conflict_identified_for_this_rule' && <p>Limited to these agreements and distribution exclusivity. This is not portfolio-wide clearance.</p>}
    {Object.entries(result.scope_comparison).map(([dimension,value])=><details key={dimension}><summary>{dimension}: {value}</summary><EvidenceLinks items={result.dimension_evidence[dimension]??[]} onEvidence={onEvidence}/></details>)}
    {!!result.exceptions.length&&<><h3>Exceptions and consent conditions</h3><ul>{result.exceptions.map((x,i)=><li key={i}>{x}<EvidenceLinks items={result.exception_evidence[i]??[]} onEvidence={onEvidence}/></li>)}</ul></>}
    {!!result.missing_facts.length&&<><h3>Still needed</h3><ul>{result.missing_facts.map((x,i)=><li key={i}>{x}</li>)}</ul></>}
    <h3>Question for a lawyer</h3><p>{result.lawyer_question}</p>
    <details><summary>Both agreements’ source passages</summary>{result.documents.map(id=><section key={id}><h3>{names.get(id)??id}</h3><EvidenceLinks items={result.evidence.filter(e=>e.document_id===id)} onEvidence={onEvidence}/>{!result.evidence.some(e=>e.document_id===id)&&<p>Supporting passages have not been established in this agreement.</p>}</section>)}</details>
    {!!result.model_usage.length&&<p className="finding-reason">{result.model_usage.map(u=>`${u.provider} · ${u.model}${u.cached?' · cached':''}${u.fallback_reason?` · Secondary used: ${u.fallback_reason}`:''}`).join('; ')}</p>}
  </article>
}

export function unseenConflicts(results:ConflictAssessment[], seen:Set<string>) {
  return results.filter(r=>r.current&&r.status==='potential_conflict'&&!seen.has(r.input_revision||r.id))
}

export function ConflictNotifications({portfolio,enabled,onOpen}:{portfolio:Portfolio|null;enabled:boolean;onOpen:(id:string)=>void}) {
  const [notice,setNotice]=useState<ConflictAssessment|null>(null)
  const seen=useRef(new Set<string>())
  const loaded=useRef('')
  useEffect(()=>{
    if(!portfolio||!enabled)return
    const key=`aithena:conflict-notices:${portfolio.mode}`
    if(loaded.current!==key){
      loaded.current=key
      try{const value=JSON.parse(localStorage.getItem(key)??'[]');seen.current=new Set(Array.isArray(value)?value.filter(x=>typeof x==='string'):[])}catch{seen.current=new Set()}
    }
    if(notice&&!portfolio.conflicts.some(r=>r.current&&r.id===notice.id)){setNotice(null);return}
    if(notice)return
    const next=unseenConflicts(portfolio.conflicts,seen.current)[0]
    if(next){
      seen.current.add(next.input_revision||next.id)
      try{localStorage.setItem(key,JSON.stringify([...seen.current]))}catch{/* Session ref still deduplicates if storage is unavailable. */}
      setNotice(next)
    }
  },[portfolio,enabled,notice])
  if(!notice||!enabled)return null
  return <aside role="status" aria-live="polite" className="conflict-toast"><strong>New potential distribution conflict</strong><p>Two agreements need review. This is not a finding of breach.</p><button className="primary" onClick={()=>{onOpen(notice.id);setNotice(null)}}>Review conflict</button><button className="secondary" onClick={()=>setNotice(null)}>Dismiss</button></aside>
}

export default function Conflicts({portfolio,enabled,stale,onEvidence,onRefresh,onChooseSme,focused}:{portfolio:Portfolio;enabled:boolean;stale:boolean;onEvidence:(e:Evidence)=>void;onRefresh:()=>void;onChooseSme:()=>void;focused:string|null}) {
  const [screens,setScreens]=useState<ConflictScreen[]>([])
  const [error,setError]=useState('')
  const [busy,setBusy]=useState(false)
  const [show,setShow]=useState(20)
  const [filter,setFilter]=useState('attention')
  const [history,setHistory]=useState(false)
  const [revision,setRevision]=useState(0)
  const grantKey=useRef('')
  const scan=portfolio.conflict_scan
  const names=new Map(portfolio.documents.map(d=>[d.id,d.filename]))
  useEffect(()=>{
    if(!enabled)return
    const controller=new AbortController()
    void fetchConflictScreens(controller.signal).then(data=>{if(!controller.signal.aborted){setScreens(data);setError('')}}).catch(cause=>{if(!controller.signal.aborted)setError(cause.message)})
    return()=>controller.abort()
  },[portfolio,enabled,revision])
  useEffect(()=>{if(focused){setHistory(false);setFilter('all');setShow(Math.max(20,portfolio.conflicts.filter(r=>r.current).findIndex(r=>r.id===focused)+1))}},[focused])
  async function next(){
    setBusy(true);setError('');grantKey.current ||= crypto.randomUUID()
    try{await continueConflicts(grantKey.current);grantKey.current='';onRefresh();setRevision(v=>v+1)}catch(cause){setError((cause as Error).message)}finally{setBusy(false)}
  }
  async function retry(id:string){setBusy(true);setError('');try{await retryConflict(id);onRefresh();setRevision(v=>v+1)}catch(cause){setError((cause as Error).message)}finally{setBusy(false)}}
  const current=portfolio.conflicts.filter(r=>r.current)
  const visible=(history?portfolio.conflicts.filter(r=>!r.current):current).filter(r=>filter==='all'||filter==='attention'&&r.status!=='no_conflict_identified_for_this_rule'||r.status===filter)
  const progress=screens.filter(s=>s.job_state&&['queued','running','waiting','blocked','failed'].includes(s.job_state))
  return <div className="conflicts-view">
    <section className="card conflict-summary"><div className="section-heading"><h2>Distribution exclusivity checks</h2><span className="badge">{scan.state.replaceAll('_',' ')}{stale?' · stale':''}</span></div>
      <p>Checks start automatically after extraction and SME selection. The first 10 pairs are allowed automatically; Continue adds the next 10. A pair can require multiple provider requests.</p>
      {!portfolio.sme&&<p className="phase-notice">Select your SME before automatic comparisons begin. <button className="contract-link" onClick={onChooseSme}>Choose your organisation</button></p>}
      <div className="conflict-counts"><div><strong>{current.filter(r=>r.status==='potential_conflict').length}</strong>potential conflicts</div><div><strong>{current.filter(r=>r.status==='insufficient_evidence').length}</strong>insufficient evidence</div><div><strong>{scan.completed}</strong>completed comparisons</div><div><strong>{scan.unchecked}</strong>unchecked candidate pairs</div></div>
      <p>{scan.total_pairs} document pairs · {scan.unscreened} pairs awaiting current screening · {scan.excluded} evidenced exclusions · {scan.unprocessed_documents} documents with incomplete source/analysis coverage.</p>
      <p>Allowance used: {scan.assigned}/{scan.allowance} pairs. Pending: {scan.queued} queued, {scan.running} running, {scan.waiting} waiting. {scan.blocked} blocked; {scan.failed} failed.</p>
      {scan.state==='paused'&&<p className="phase-notice">Automatic allowance reached. Remaining candidate pairs have not been checked.</p>}
      <button className="primary" disabled={!enabled||busy||!scan.can_continue} onClick={()=>void next()}>{busy?'Updating…':'Continue — next 10'}</button>
      {stale&&<p className="error">Connection unavailable. Previous conflict information is stale.</p>}{error&&<p className="error" role="alert">{error} Previous screening details may be stale.</p>}
    </section>
    {!!progress.length&&<section className="card conflict-card"><h2>Comparison progress and failures</h2>{progress.map(s=><article key={s.id}><strong>{s.documents.map(id=>names.get(id)??id).join(' ↔ ')}</strong><p>{s.job_state}{s.error?` · ${s.error}`:''}</p>{['failed','blocked'].includes(s.job_state??'')&&<button className="secondary" disabled={!enabled||busy} onClick={()=>void retry(s.id)}>Retry comparison</button>}</article>)}</section>}
    <div className="conflict-filters"><label>Show <select value={filter} onChange={e=>{setFilter(e.target.value);setShow(20)}}><option value="attention">Needs attention</option><option value="all">All assessments</option><option value="potential_conflict">Potential conflicts</option><option value="insufficient_evidence">Insufficient evidence</option><option value="no_conflict_identified_for_this_rule">No conflict identified for this rule</option></select></label><label><input type="checkbox" checked={history} onChange={e=>{setHistory(e.target.checked);setShow(20)}}/> Stale assessment history</label></div>
    {!visible.length&&<section className="card conflict-card"><h2>No assessments in this view</h2><p>{scan.unchecked||scan.unprocessed_documents||scan.queued||scan.running||scan.waiting?'Some documents or pairs have not been fully checked. An empty view is not clearance.':'This rule covers distribution exclusivity only. An empty view does not establish that all agreements are compatible.'}</p></section>}
    {visible.slice(0,show).map(result=><ConflictCard key={result.id} result={result} names={names} onEvidence={onEvidence} focused={focused===result.id}/>)}
    {visible.length>show&&<button className="secondary" onClick={()=>setShow(v=>v+20)}>Show more assessments ({visible.length-show} remaining)</button>}
    <details className="card conflict-card"><summary>Local screening decisions ({screens.length})</summary>{screens.map(s=><details key={s.id}><summary>{s.documents.map(id=>names.get(id)??id).join(' ↔ ')} · {s.outcome.replaceAll('_',' ')}</summary><p>{s.reason}</p><EvidenceLinks items={s.evidence} onEvidence={onEvidence}/></details>)}</details>
  </div>
}
