import { useState } from 'react'
import { Quote } from 'lucide-react'
import { extractDocument, type ApiDocument, type Evidence as SourceEvidence, type Finding, type Portfolio } from './api'
const FIELD_LABELS: Record<Finding['field'], string> = {
  parties: 'Parties', term: 'Term', renewal: 'Renewal mechanics', notice: 'Notice requirements',
  termination: 'Termination rights', payments: 'Payment obligations',
  liability: 'Liability caps and exceptions', restrictions: 'Exclusivity and restrictive covenants',
}
const FIELD_ORDER = Object.keys(FIELD_LABELS) as Finding['field'][]

function Evidence({ items, onEvidence }: { items: Finding['evidence']; onEvidence: (e: SourceEvidence) => void }) {
  if (!items.length) return null
  return <ul className="evidence">{items.map((e, i) => <li key={i}><Quote size={13} /><blockquote>{e.quote}</blockquote><button className="contract-link" onClick={() => onEvidence(e)}>Page {e.page}{e.clause ? ` · ${e.clause}` : ''}{e.source === 'ocr' ? ' · OCR' : ''}</button></li>)}</ul>
}

function FindingRow({ finding, stale, onEvidence }: { finding: Finding; stale: boolean; onEvidence: (e: SourceEvidence) => void }) {
  const resolved = finding.provenance !== 'unresolved' && finding.value != null
  return <article className={`finding provenance-${finding.provenance}`}>
    <div className="finding-head"><h4>{FIELD_LABELS[finding.field]}{finding.party ? <span className="finding-party"> · {finding.party}</span> : null}</h4>
      <div className="finding-badges"><span className={`badge provenance ${finding.provenance}`}>{finding.provenance}</span><span className={`badge confidence ${finding.confidence}`}>{finding.confidence} confidence</span></div></div>
    <p className="finding-value">{resolved ? finding.value : 'Not established in this document. This does not mean no obligation exists.'}</p>
    {finding.conditions.length ? <ul className="finding-conditions">{finding.conditions.map((c, i) => <li key={i}>{c}</li>)}</ul> : null}
    <p className="finding-reason">{finding.confidence_reason}{stale ? ' · stale' : ''}</p>
    <Evidence items={finding.evidence} onEvidence={onEvidence} />
  </article>
}

export function Findings({ document: doc, stale, onEvidence }: { document: ApiDocument; stale: boolean; onEvidence: (e: SourceEvidence) => void }) {
  return <section className="card contract-card"><h2>Obligations and source evidence</h2><p>{doc.pages_analyzed}/{doc.page_count} pages analyzed. Findings describe the named parties; select your organisation before treating an obligation as yours.</p>
    {FIELD_ORDER.map(field => <section key={field} className="finding-group"><h3>{FIELD_LABELS[field]}</h3>{doc.findings.filter(f => f.field === field).length ? doc.findings.filter(f => f.field === field).map(f => <FindingRow key={f.id} finding={f} stale={stale} onEvidence={onEvidence} />) : <p>Unresolved · {doc.pages_analyzed ? 'Not established in this document.' : 'Extraction has not established this field.'} This does not mean no obligation exists.</p>}</section>)}
    {doc.issues.length > 0 && <section><h3>Needs review</h3>{doc.issues.map(issue => <article className="finding" key={issue.id}><h4>{issue.title}</h4><p>{issue.missing_facts.join(' ')}</p><p>{issue.lawyer_question}</p><Evidence items={issue.evidence} onEvidence={onEvidence} /></article>)}</section>}
  </section>
}

export function SmeSelector({ portfolio, disabled, onChoose }: { portfolio: Portfolio | null; disabled: boolean; onChoose: (name: string | null) => void }) {
  const parties = portfolio?.parties ?? []
  return <label className="sme-selector">Established party (your organisation)
    <select value={portfolio?.sme ?? ''} disabled={disabled || !parties.length} onChange={e => onChoose(e.target.value || null)}>
      <option value="">{parties.length ? 'Not selected' : 'No parties extracted yet'}</option>
      {parties.map(p => <option key={p} value={p}>{p}</option>)}
    </select>
  </label>
}


export function ExtractionAction({ document: doc, enabled, onRefresh }: { document: ApiDocument; enabled: boolean; onRefresh: () => void }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const ready = ['text_ready','needs_source_review','read','failed','awaiting_key'].includes(doc.status) && doc.pages_read > 0
  async function extract() {
    setBusy(true); setError('')
    try { await extractDocument(doc.id); onRefresh() } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  return <section className="card extraction-action"><div><h2>Grounded extraction</h2><p>{doc.stage} · {doc.pages_analyzed}/{doc.page_count} pages analyzed</p><p>Extract obligations sends this document’s page text to Gemini for extraction and support review. Originals stay local. A matching completed result is reused; quota waits resume automatically.</p>{doc.error && <p className="error">{doc.error}</p>}{error && <p className="error" role="alert">{error}</p>}</div><button className="primary" disabled={!enabled || !ready || busy} onClick={() => void extract()}>{busy ? 'Queuing…' : ['failed','awaiting_key'].includes(doc.status) ? 'Retry extraction' : 'Extract obligations'}</button></section>
}
