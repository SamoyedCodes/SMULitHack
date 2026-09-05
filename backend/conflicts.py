"""Conservative distribution screening and evidence-bound semantic validation."""
import hashlib
import json
from datetime import date

from .evidence import normalized, resolve_citations
from .models import ConflictAssessment, ConflictDraft, ConflictScreen, Document, Page

CONFLICT_VERSION = 'distribution-1'
JOB_KIND = 'conflict-v1'
DIMENSIONS = {'product', 'territory', 'activity', 'channel', 'customers', 'parties', 'time'}


def source_descriptor(doc, source_hash):
    return {**doc.model_dump(include={'id','sha256','version','model','status','page_count','pages_read',
            'pages_analyzed','parties','findings','rules','provisions','reviews','warnings','issues'}), 'source_hash':source_hash}


def pair_id(a: Document, b: Document, hashes=None, sme='', routing='') -> str:
    hashes = hashes or {}
    records = sorted([source_descriptor(d, hashes.get(d.id,'')) for d in (a,b)], key=lambda d:d['id'])
    return hashlib.sha256(json.dumps([CONFLICT_VERSION, sme, routing, records],sort_keys=True).encode()).hexdigest()


def complete(doc, pages):
    return (doc.status in {'complete','needs_review'} and doc.page_count > 0
            and doc.pages_analyzed == doc.pages_read == doc.page_count and len(pages) == doc.page_count
            and {p.number for p in pages} == set(range(1,doc.page_count+1))
            and all(p.status == 'read' and p.spans and not p.warnings for p in pages) and not doc.warnings
            and all(s.source!='ocr' or s.ocr_confidence is not None and s.ocr_confidence>=70 for p in pages for s in p.spans))


def relevant(doc):
    return [p for p in doc.provisions if p.kind in {'distribution','unknown'}]


def supported(doc, provision, pages):
    verdicts = [v for v in doc.reviews if v.item_id == provision.id]
    evidence, errors = resolve_citations(provision.citations, pages, {doc.id})
    valid = (len(verdicts)==1 and verdicts[0].status=='supported' and not verdicts[0].missing_context
             and not errors and bool(evidence) and not provision.missing_context)
    return bool(valid), evidence


def period(p):
    try:
        start,end=date.fromisoformat(p.starts_on),date.fromisoformat(p.ends_on)
        return (start,end) if start <= end else None
    except (TypeError,ValueError):
        return None


def temporal_uncertainty(doc, pages):
    # A stated initial end cannot exclude renewed or surviving rights.
    text = ' '.join([f.value or '' for f in doc.findings if f.field in {'renewal','term','restrictions'}]
                    + [x for p in relevant(doc) for x in p.exceptions] + [s.text for p in pages for s in p.spans]).lower()
    return bool(any(r.recurrence_months or r.conditions or r.missing_inputs for r in doc.rules)
                or any(word in text for word in ('renew','extend','extension','surviv','amend')))


def time_comparison(a, b, pages):
    result=[]
    for p in relevant(a):
        for q in relevant(b):
            item={'left':p.id,'right':q.id,'overlap':'unknown'}
            if (complete(a,pages[a.id]) and complete(b,pages[b.id]) and not temporal_uncertainty(a,pages[a.id])
                    and not temporal_uncertainty(b,pages[b.id]) and supported(a,p,pages[a.id])[0] and supported(b,q,pages[b.id])[0]):
                left,right=period(p),period(q)
                if left and right:
                    item['overlap']='yes' if max(left[0],right[0]) <= min(left[1],right[1]) else 'no'
            result.append(item)
    return result


def aggregate_time(comparison):
    values=[x['overlap'] for x in comparison]
    return 'yes' if 'yes' in values else 'no' if values and all(v=='no' for v in values) else 'unknown'


def screen(a,b,pages,hashes,sme,routing):
    record=ConflictScreen(id=pair_id(a,b,hashes,sme,routing),documents=sorted([a.id,b.id]),mode=a.mode,
                         outcome='needs_evidence',reason='Source or extraction evidence is incomplete.')
    if a.mode != b.mode:
        raise ValueError('Cannot compare different workspaces.')
    if not all(complete(d,pages[d.id]) for d in (a,b)):
        return record
    left,right=relevant(a),relevant(b)
    if not left or not right:
        record.reason='Distribution provisions were not established in both documents. Missing extraction is not an exclusion.'
        return record
    checks=[supported(d,p,pages[d.id]) for d in (a,b) for p in relevant(d)]
    record.evidence=list({(e.document_id,e.page,e.quote):e for _,ev in checks for e in ev}.values())
    if not all(ok for ok,_ in checks):
        record.reason='A distribution provision has missing context, invalid evidence or unresolved support review.'
        record.missing_facts=list(dict.fromkeys([x for d in (a,b) for p in relevant(d) for x in p.missing_context]
            + [x for d in (a,b) for v in d.reviews if v.item_id in {p.id for p in relevant(d)}
               for x in ([v.reason] if v.status!='supported' else [])+v.missing_context]))
        return record
    if any(e.source=='ocr' and (e.ocr_confidence is None or e.ocr_confidence<70) for e in record.evidence):
        record.reason='OCR is too uncertain to establish the commercial scope.'
        return record
    # The extracted grantor may resolve a document-defined alias, but must be supported.
    # No fuzzy entity matching or inference from absence in a party list.
    if not sme or any(normalized(p.grantor or '') != normalized(sme) for p in [*left,*right]):
        record.reason='The selected SME is not established as the common grantor of these distribution rights. Identity or role needs review.'
        return record
    for d in (a,b):
        party_sources=[e for f in d.findings if f.field=='parties' and f.provenance=='found' and f.confidence!='low'
                       and any(v.item_id==f.id and v.status=='supported' and not v.missing_context for v in d.reviews)
                       for e in f.evidence if normalized(sme) in normalized(e.quote)]
        if not party_sources:
            record.reason='The SME identity needs cited party evidence in both agreements.'
            return record
        for e in party_sources:
            from .models import Citation
            resolved,errors=resolve_citations([Citation(document_id=e.document_id,span_ids=e.span_ids,quote=e.quote)],pages[d.id],{d.id})
            if errors or not resolved:
                record.reason='The party evidence no longer matches the source.'
                return record
            record.evidence.extend(resolved)
    if any(not p.beneficiary for p in [*left,*right]):
        record.reason='A beneficiary of the distribution rights is not established.'
        return record
    if all(p.exclusive is False for p in [*left,*right]):
        record.outcome,record.reason='excluded','Both sets of supported distribution grants are explicitly non-exclusive; this rule does not assess other restrictions.'
        return record
    if aggregate_time(time_comparison(a,b,pages))=='no':
        record.outcome,record.reason='excluded','Every relevant supported distribution period is explicitly bounded and disjoint.'
        return record
    if any(not p.product or not p.territory or not p.channel for p in [*left,*right]):
        record.reason='A required product, territory or channel scope is not established.'
        return record
    record.outcome,record.reason='candidate','Supported distribution rights may overlap; semantic comparison is needed.'
    record.priority=0 if any(p.exclusive is True for p in [*left,*right]) else 1
    return record


def insufficient(record,reason,missing=None):
    gaps=missing or record.missing_facts or [reason]
    return ConflictAssessment(id=record.id,input_revision=record.id,documents=record.documents,
        status='insufficient_evidence',scope_comparison={},evidence=record.evidence,exceptions=[],
        missing_facts=gaps,explanation=reason,
        lawyer_question='What additional source or judgement resolves this distribution-rights question: '+gaps[0],
        confidence='low',confidence_reason='Required evidence or support is missing.',provenance='unresolved',mode=record.mode)


def validate_assessment(draft: ConflictDraft, a, b, pages, record, comparison):
    expected={a.id,b.id}
    errors=[]
    if len(draft.documents)!=2 or set(draft.documents)!=expected:
        errors.append('The comparison returned the wrong document identifiers.')
    evidence,invalid=resolve_citations(draft.citations,[*pages[a.id],*pages[b.id]],expected)
    errors.extend(invalid)
    if {e.document_id for e in evidence}!=expected:
        errors.append('Valid evidence from both agreements is required.')
    dimensions={}
    for dimension in sorted(DIMENSIONS):
        if not draft.scope_comparison.get(dimension,'').strip():
            errors.append(f'The {dimension} comparison is missing.')
        ev,bad=resolve_citations(draft.dimension_citations.get(dimension,[]),[*pages[a.id],*pages[b.id]],expected)
        if bad or {e.document_id for e in ev}!=expected:
            errors.append(f'The {dimension} comparison needs valid evidence from both agreements.')
        dimensions[dimension]=ev
        evidence.extend(ev)
    if len(draft.exceptions)!=len(draft.exception_citations):
        errors.append('Each claimed exception needs its own citations.')
    exception_evidence=[]
    for citations in draft.exception_citations:
        ev,bad=resolve_citations(citations,[*pages[a.id],*pages[b.id]],expected)
        if bad or not ev: errors.append('An exception has invalid or missing evidence.')
        exception_evidence.append(ev)
        evidence.extend(ev)
    expected_time=aggregate_time(comparison)
    if draft.time_overlap!=expected_time:
        errors.append('The time conclusion disagrees with supported Python date comparisons.')
    if draft.status=='potential_conflict' and expected_time!='yes':
        errors.append('Concurrent exercise of these rights has not been established.')
    if not draft.explanation.strip() or not draft.lawyer_question.strip():
        errors.append('An explanation and specific lawyer question are required.')
    if record.outcome!='candidate': errors.append(record.reason)
    # Consent is an external fact unless the source establishes it. Merely omitting
    # it from the model's missing_facts cannot turn a conditional grant into clearance.
    for doc in (a,b):
        for provision in relevant(doc):
            errors.extend(provision.missing_context)
            if any(word in ' '.join(provision.exceptions).lower() for word in ('consent','approval','permission')):
                errors.append('A consent or approval condition requires confirmation; permission to exercise these rights is not established.')
        for verdict in doc.reviews:
            if verdict.item_id in {p.id for p in relevant(doc)}:
                errors.extend(verdict.missing_context)
                if verdict.status!='supported': errors.append('A commercial provision has unresolved support.')
    if not all(complete(d,pages[d.id]) for d in (a,b)):
        errors.append('Complete reliable source coverage is required.')
    if any(e.source=='ocr' and (e.ocr_confidence is None or e.ocr_confidence<70) for e in evidence):
        errors.append('Low or unknown OCR confidence may change the scope.')
    missing=list(dict.fromkeys([*draft.missing_facts,*errors]))
    if missing or draft.status=='insufficient_evidence':
        result=insufficient(record,'The comparison could not establish compatibility from the available evidence.',
                            missing or ['The semantic comparison identified unresolved scope.'])
        result.evidence=list({(e.document_id,e.page,e.quote):e for e in evidence}.values())
        return result
    return ConflictAssessment(id=record.id,input_revision=record.id,status=draft.status,documents=record.documents,
        scope_comparison={**{key:draft.scope_comparison[key] for key in sorted(DIMENSIONS)}, 'time': {'yes':'Python establishes overlap in at least one supported distribution period.', 'no':'Python establishes that all supported distribution periods are disjoint.', 'unknown':'The applicable overlap is not established by supported dates.'}[expected_time]},dimension_evidence=dimensions,exception_evidence=exception_evidence,
        evidence=list({(e.document_id,e.page,e.quote):e for e in evidence}.values()),exceptions=draft.exceptions,
        missing_facts=[],explanation=draft.explanation,lawyer_question=draft.lawyer_question,
        confidence='medium',confidence_reason='Semantic interpretation of cited passages; this does not establish actual breach or enforceability.',
        provenance='inferred',mode=a.mode)
