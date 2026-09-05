import { useEffect, useRef, useState } from 'react'
import { AlertTriangle, ArrowLeft, Download, Printer, Quote } from 'lucide-react'
import { SourceViewer } from './Ingestion'
import { fetchBrief, type ApiDocument, type Brief as BriefData, type Evidence, type Portfolio } from './api'

const KIND_LABELS: Record<string, string> = {
  potential_conflict: 'Potential conflict',
  insufficient_evidence: 'Insufficient evidence',
  no_conflict_identified_for_this_rule: 'No conflict identified for this rule',
}

function label(brief: BriefData) {
  return KIND_LABELS[brief.kind] ?? brief.kind.replaceAll('_', ' ')
}

function escapeHtml(value: string) {
  return value.replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch] as string))
}

function documentLabel(doc: BriefData['documents'][number]) {
  return doc.title === doc.filename ? doc.filename : `${doc.title} (${doc.filename})`
}

// A self-contained, printable HTML document with verbatim excerpts and page/clause references.
export function briefHtml(brief: BriefData) {
  const li = (items: string[]) => items.map(item => `<li>${escapeHtml(item)}</li>`).join('')
  const docs = brief.documents.map(d => escapeHtml(documentLabel(d))).join(', ')
  const scope = Object.entries(brief.scope_comparison).map(([k, v]) => `<tr><th>${escapeHtml(k)}</th><td>${escapeHtml(v)}</td></tr>`).join('')
  const sources = brief.evidence.map(e =>
    `<div class="source"><div class="label">${escapeHtml(brief.documents.find(d => d.id === e.document_id) ? documentLabel(brief.documents.find(d => d.id === e.document_id)!) : e.document_id)} · Page ${e.page}${e.clause ? ` · Clause ${escapeHtml(e.clause)}` : ''}${e.source === 'ocr' ? ' · OCR' : ''}</div><blockquote>${escapeHtml(e.quote)}</blockquote></div>`).join('')
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>${escapeHtml(brief.title)}</title>
<style>body{font:15px/1.6 -apple-system,Segoe UI,Inter,sans-serif;color:#1a2a3f;max-width:820px;margin:40px auto;padding:0 20px}
h1{font-size:1.5rem}h2{font-size:1rem;margin-top:26px}.meta{color:#5b6b80;font-size:.85rem}blockquote{border-left:3px solid #98b2d4;margin:10px 0;padding-left:12px;color:#33465f}
.source{border:1px solid #e2e7ee;border-radius:6px;padding:14px;margin:12px 0}.label{color:#4b6384;font-size:.8rem;margin-bottom:6px}
.question{border-left:3px solid #ba924c;background:#fcf8ef;padding:14px;margin:18px 0}.warn{border:1px solid #eac7c4;background:#fff0ee;color:#923e35;padding:12px;border-radius:6px}
table{border-collapse:collapse;margin:10px 0}th,td{border:1px solid #e2e7ee;padding:6px 10px;text-align:left;vertical-align:top}.disclaimer{color:#5b6b80;font-size:.8rem;margin-top:30px;border-top:1px solid #e2e7ee;padding-top:14px}</style></head>
<body><h1>${escapeHtml(brief.title)}</h1>
<p class="meta">${docs} · ${escapeHtml(label(brief))} · Provenance: ${escapeHtml(brief.provenance)}${brief.confidence ? ` · Confidence: ${escapeHtml(brief.confidence)}` : ''}<br>Generated ${escapeHtml(brief.generated_at)} · As of ${escapeHtml(brief.as_of)} · ${escapeHtml(brief.mode)} workspace</p>
${brief.confidence_reason ? `<p class="meta">${escapeHtml(brief.confidence_reason)}</p>` : ''}
${brief.coverage_warnings.length ? `<div class="warn"><ul>${li(brief.coverage_warnings)}</ul></div>` : ''}
${brief.established.length ? `<h2>Established facts</h2><ul>${li(brief.established)}</ul>` : ''}
${scope ? `<h2>Scope comparison</h2><table>${scope}</table>` : ''}
${brief.explanation ? `<h2>Assessment</h2><p>${escapeHtml(brief.explanation)}</p>` : ''}
${brief.exceptions.length ? `<h2>Exceptions</h2><ul>${li(brief.exceptions)}</ul>` : ''}
${brief.missing_facts.length ? `<h2>Missing facts</h2><ul>${li(brief.missing_facts)}</ul>` : ''}
<div class="question"><strong>Question requiring human judgment</strong><p>${escapeHtml(brief.lawyer_question)}</p><p class="meta">${escapeHtml(brief.urgency)}</p></div>
<h2>Source excerpts</h2>${sources || '<p class="meta">No source excerpts are attached to this item.</p>'}
<p class="disclaimer">${escapeHtml(brief.disclaimer)}</p></body></html>`
}

function download(brief: BriefData) {
  const blob = new Blob([briefHtml(brief)], { type: 'text/html' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `aithena-brief-${brief.id}.html`
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

export function BriefView({ brief, onBack, onViewSource, viewable, enabled = true }:
  { brief: BriefData; onBack: () => void; onViewSource?: (e: Evidence) => void; viewable?: (documentId: string) => boolean; enabled?: boolean }) {
  return <article className="card conflict-card brief-print-root">
    {!enabled && <div className="error" role="alert">This brief is stale or refreshing. Reconnect and wait for the current context before relying on it, printing or downloading.</div>}
    <div className="brief-actions">
      <button className="secondary review-back" onClick={onBack}><ArrowLeft size={16} />Back to review queue</button>
      <div className="brief-buttons">
        <button className="secondary" disabled={!enabled} onClick={() => window.print()}><Printer size={16} />Print / Save as PDF</button>
        <button className="primary" disabled={!enabled} onClick={() => download(brief)}><Download size={16} />Download brief</button>
      </div>
    </div>
    <div className="section-heading"><h2>{brief.title}</h2><span className="badge">{label(brief)}</span></div>
    <p className="brief-meta">{brief.documents.map(documentLabel).join(', ')} · Generated {brief.generated_at} · As of {brief.as_of} · {brief.mode} workspace</p>
    <div className="finding-badges"><span className={`badge provenance ${brief.provenance}`}>{brief.provenance}</span>{brief.confidence ? <span className={`badge confidence ${brief.confidence}`}>{brief.confidence} confidence</span> : null}</div>
    {brief.confidence_reason && <p className="brief-meta">{brief.confidence_reason}</p>}
    {brief.coverage_warnings.length > 0 && <div className="error" role="alert"><strong>Source coverage warning.</strong><ul>{brief.coverage_warnings.map((w, i) => <li key={i}>{w}</li>)}</ul></div>}
    {brief.established.length > 0 && <section className="brief-section"><h3>Established facts</h3><ul>{brief.established.map((f, i) => <li key={i}>{f}</li>)}</ul></section>}
    {Object.keys(brief.scope_comparison).length > 0 && <section className="brief-section"><h3>Scope comparison</h3><div className="table-scroll"><table><tbody>{Object.entries(brief.scope_comparison).map(([k, v]) => <tr key={k}><th>{k}</th><td>{v}</td></tr>)}</tbody></table></div></section>}
    {brief.explanation && <section className="brief-section"><h3>Assessment</h3><p>{brief.explanation}</p></section>}
    {brief.exceptions.length > 0 && <section className="brief-section"><h3>Exceptions</h3><ul>{brief.exceptions.map((x, i) => <li key={i}>{x}</li>)}</ul></section>}
    {brief.missing_facts.length > 0 && <section className="brief-section"><h3>Missing facts</h3><ul>{brief.missing_facts.map((m, i) => <li key={i}>{m}</li>)}</ul></section>}
    <div className="review-question"><strong>Question requiring human judgment</strong><p>{brief.lawyer_question}</p><small>{brief.urgency}</small></div>
    <section className="brief-section"><h3>Source excerpts</h3>{brief.evidence.length ? <div className="sources">{brief.evidence.map((e, i) => <div className="source" key={i}><div className="source-label"><Quote size={14} />{brief.documents.find(d => d.id === e.document_id) ? documentLabel(brief.documents.find(d => d.id === e.document_id)!) : e.document_id} · Page {e.page}{e.clause ? ` · Clause ${e.clause}` : ''}{e.source === 'ocr' ? ' · OCR' : ''}</div><blockquote>{e.quote}</blockquote>{onViewSource && <button className="contract-link" disabled={!enabled || (viewable ? !viewable(e.document_id) : false)} onClick={() => onViewSource(e)}>View source</button>}</div>)}</div> : <p className="brief-meta">No source excerpts are attached to this item.</p>}</section>
    <p className="brief-disclaimer"><AlertTriangle size={14} /> {brief.disclaimer}</p>
  </article>
}

export function Brief({ id, portfolio, enabled, onBack }: { id: string; portfolio: Portfolio; enabled: boolean; onBack: () => void }) {
  const [brief, setBrief] = useState<BriefData | null>(null)
  const [error, setError] = useState('')
  const [loadedContext, setLoadedContext] = useState('')
  const context = JSON.stringify([id, portfolio.mode, portfolio.as_of, portfolio.issues.find(i => i.id === id), portfolio.conflicts.find(c => c.id === id || `conflict:${c.id}` === id), portfolio.documents.map(d => [d.id, d.status, d.sha256, d.version, d.pages_read, d.pages_analyzed])])
  const [evidence, setEvidence] = useState<Evidence | null>(null)
  const sourceRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!enabled) return
    const controller = new AbortController()
    setBrief(null); setError(''); setEvidence(null)
    void fetchBrief(id, controller.signal, {mode: portfolio.mode, as_of: portfolio.as_of})
      .then(result => { if (!controller.signal.aborted) { setBrief(result); setLoadedContext(context) } })
      .catch(cause => { if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : 'The brief could not be loaded.') })
    return () => controller.abort()
  }, [id, portfolio.mode, portfolio.as_of, context, enabled])
  const docLookup = new Map<string, ApiDocument>(portfolio.documents.map(doc => [doc.id, doc]))
  function viewSource(e: Evidence) { setEvidence(e); requestAnimationFrame(() => sourceRef.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })) }
  const sourceDoc = evidence ? docLookup.get(evidence.document_id) : undefined
  if (error) return <section className="card foundation-empty"><h2>The brief could not be loaded</h2><p>{error}</p><button className="secondary" onClick={onBack}><ArrowLeft size={16} />Back to review queue</button></section>
  if (!brief && !enabled) return <section className="card foundation-empty" role="alert"><p>The brief is unavailable while the workspace is stale or refreshing.</p><button className="secondary" onClick={onBack}>Back to review queue</button></section>
  if (!brief) return <section className="card foundation-empty" role="status"><h2>Preparing brief…</h2><p>Assembling grounded source evidence for this item.</p></section>
  return <>
    <BriefView brief={brief} enabled={enabled && loadedContext === context} onBack={onBack} onViewSource={viewSource} viewable={documentId => docLookup.has(documentId)} />
    {evidence && sourceDoc && <div ref={sourceRef}><SourceViewer key={sourceDoc.id} document={sourceDoc} evidence={evidence} enabled={enabled} onClose={() => setEvidence(null)} /></div>}
  </>
}
