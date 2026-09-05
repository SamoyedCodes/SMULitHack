import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, downloadEvaluation, fetchScorecard, type EvaluationScorecard } from './api'

export const METRIC_LABELS: Record<string,string> = {
  field_accuracy:'Field accuracy', answerable_coverage:'Answerable coverage', prediction_correctness:'Prediction correctness',
  citation_validity:'Citation validity', deadline_accuracy:'Deadline accuracy', deadline_recall:'Deadline recall',
  candidate_recall:'Candidate recall', retained_for_review_recall:'Retained for review recall',
  conflict_precision:'Conflict precision', conflict_recall:'Conflict recall', high_confidence_error_rate:'High-confidence error rate',
}
export function metricText(m: {correct:number; total:number; rate:number|null}) {
  return m.rate === null ? 'Not measurable (0 denominator)' : `${m.correct}/${m.total} (${(m.rate*100).toFixed(1)}%)`
}
export function ScorecardBody({card, split}: {card:EvaluationScorecard; split:'holdout'|'development'|'all'}) {
  const group = card.groups[split]
  const examples = card.examples.filter(e => split === 'all' || e.split === split).slice(0,5)
  const failures = card.failures.filter(e => split === 'all' || e.split === split)
  return <div className="evaluation-print-root">
    <h2>Saved benchmark campaign · {split}</h2>
    <p>These results describe a saved evaluation, not the current live portfolio.</p>
    <p className="evaluation-meta">Campaign {card.campaign_id} · Model {card.model}<br />Generated {card.generated_at}<br />Evaluated dates: {card.as_of_dates.join(', ')}<br />Review status: {card.review_status.replaceAll('_',' ')}</p>
    <details><summary>Frozen snapshot identifiers</summary><p className="evaluation-meta">Run: {card.run_sha256}<br />Answer key: {card.answer_key_sha256}</p></details>
    {card.stopped && <p className="evaluation-warning"><strong>Campaign stopped:</strong> {card.stopped}</p>}
    <p>Confirmed charges: US${card.budget.charged_usd} · Unreconciled reservation: US${card.budget.unreconciled_reserved_usd} · Ceiling: US${card.budget.ceiling_usd} · {card.budget.requests} requests.</p>
    {Number(card.budget.unreconciled_reserved_usd) > 0 && <p className="evaluation-warning">Actual total spend is unknown. Confirmed charges do not establish zero actual spend.</p>}
    <p><strong>{group.completed_documents}/{group.documents} documents completed analysis.</strong> {group.fields_unreviewed} fields and {group.predictions_unreviewed} predictions remain unreviewed; {group.pairs_unassessed} keyed pairs are unassessed.</p>
    {group.completed_documents < group.documents && <p className="evaluation-warning">Incomplete run: coverage and recall include missing outputs. They are not measured accuracy on completed answers.</p>}
    <div className="table-scroll"><table><thead><tr><th>Metric</th><th>Result (numerator / denominator)</th></tr></thead><tbody>{Object.entries(METRIC_LABELS).map(([key,label]) => <tr key={key}><th scope="row">{label}</th><td>{metricText(group.metrics[key])}{key === 'high_confidence_error_rate' && ` · ${group.metrics[key].unreviewed} unreviewed high-confidence predictions`}</td></tr>)}</tbody></table></div>
    <h3>Correctness by confidence band</h3><ul>{(['high','medium','low'] as const).map(band => <li key={band}>{band}: {metricText(group.confidence[band])} reviewed correct · {group.confidence[band].unreviewed} unreviewed.</li>)}</ul>
    <h3>Reviewed semantic mistakes (up to five)</h3>
    {!examples.length && <p>No reviewed semantic mistakes available. This is not proof of accuracy.</p>}
    {examples.map(e => <article className="finding" key={`${e.sample}-${e.finding_id}`}><h4>{e.sample} · {e.confidence} confidence</h4><p><strong>Expected:</strong> {e.expected}</p><p><strong>Observed:</strong> {e.observed}</p><p><strong>Reviewer:</strong> {e.explanation}</p></article>)}
    <h3>Operational failures and incomplete work</h3>
    {!failures.length ? <p>No operational failures recorded for this group.</p> : <ul>{failures.map(f => <li key={f.sample}>{f.sample} · {f.status.replaceAll('_',' ')} — {f.message}</li>)}</ul>}
    <h3>Limits of these results</h3><ul>{card.limitations.map((line,i) => <li key={i}>{line}</li>)}</ul>
  </div>
}
export function Evaluation() {
  const [card,setCard] = useState<EvaluationScorecard|null>(null)
  const [split,setSplit] = useState<'holdout'|'development'|'all'>('holdout')
  const [busy,setBusy] = useState(false), [error,setError] = useState(''), [exportError,setExportError] = useState('')
  const [unavailable,setUnavailable] = useState(false), [downloading,setDownloading] = useState(false)
  const active = useRef<AbortController|null>(null), download = useRef<AbortController|null>(null)
  const refresh = useCallback(async () => {
    if (active.current) return
    const controller = new AbortController(); active.current = controller; setBusy(true)
    try { const result = await fetchScorecard(controller.signal); if (!controller.signal.aborted) {setCard(result); setError(''); setUnavailable(false)} }
    catch (cause) { if (!controller.signal.aborted) {setError(cause instanceof Error ? cause.message : 'Evaluation unavailable.'); setUnavailable(cause instanceof ApiError && cause.status === 404)} }
    finally {if (active.current === controller) {active.current=null; if (!controller.signal.aborted) setBusy(false)}}
  }, [])
  useEffect(() => {void refresh(); const timer=setInterval(() => void refresh(),10000); return () => {clearInterval(timer); active.current?.abort(); active.current=null; download.current?.abort()}}, [refresh])
  async function save() {
    if (!card || busy || error) return
    const controller = new AbortController(); download.current=controller; setDownloading(true); setExportError('')
    try {
      const blob = await downloadEvaluation(card, controller.signal)
      if (controller.signal.aborted) return
      const url=URL.createObjectURL(blob), link=document.createElement('a'); link.href=url; link.download=`aithena-evaluation-${card.campaign_id}.html`; link.click(); setTimeout(() => URL.revokeObjectURL(url),1000)
    } catch (cause) {if (!controller.signal.aborted) setExportError(cause instanceof Error ? cause.message : 'Report download failed.')}
    finally {if (!controller.signal.aborted) setDownloading(false)}
  }
  return <section className="card evaluation-card"><div className="filter-controls evaluation-controls">
    <label>Evaluation group<select value={split} onChange={e => setSplit(e.target.value as typeof split)}><option value="holdout">Holdout</option><option value="development">Development</option><option value="all">All</option></select></label>
    <button className="secondary" disabled={busy} onClick={() => void refresh()}>Refresh saved results</button>
    <button className="secondary" disabled={!card || busy || Boolean(error) || downloading} onClick={() => void save()}>{downloading ? 'Downloading…' : 'Download report (all groups)'}</button>
    <button className="secondary" disabled={!card || busy || Boolean(error)} onClick={() => window.print()}>Print selected group / Save as PDF</button>
    </div>
    {busy && <p role="status">Refreshing saved evaluation…</p>}
    {error && <p role="alert" className="evaluation-warning">{unavailable ? 'No saved scorecard is available. Generate it with the local evaluator’s score command; this view never starts inference.' : error}{card && ' Previous scorecard is stale; refresh before exporting.'}</p>}
    {exportError && <p role="alert" className="evaluation-warning">{exportError}</p>}
    {card && <ScorecardBody card={card} split={split} />}
  </section>
}
