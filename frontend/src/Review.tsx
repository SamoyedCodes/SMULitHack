import { useState } from 'react'
import { CircleAlert, FileText, Scale } from 'lucide-react'
import { Brief } from './Brief'
import type { Portfolio } from './api'

import { reviewItems, filterReview, REASONS, EMPTY_REVIEW, type ReviewFilters, type ReviewCategory } from './presentation'
export { reviewItems } from './presentation'

function Stat({ label, value }: { label: string; value: number }) {
  return <article><span>{label}</span><strong>{value}</strong></article>
}

export function ReviewQueue({ portfolio, onOpen, enabled = true, filters = EMPTY_REVIEW, onFilters = () => {} }: { portfolio: Portfolio; onOpen: (id: string) => void; enabled?: boolean; filters?: ReviewFilters; onFilters?: (f: ReviewFilters) => void }) {
  const queue = reviewItems(portfolio)
  const names = new Map(portfolio.documents.map(doc => [doc.id, doc.title || doc.filename]))
  const shown = filterReview(queue, names, filters)
  const conflicts = portfolio.conflicts.filter(c => c.current)
  const potential = conflicts.filter(c => c.status === 'potential_conflict').length
  const insufficient = conflicts.filter(c => c.status === 'insufficient_evidence').length
  const analyzed = portfolio.documents.filter(d => ['complete', 'needs_review'].includes(d.status)).length
  return <>
    {!enabled && <p className="error" role="alert">Previous review information is stale or refreshing. Reconnect before relying on it or opening a brief.</p>}
    <section className="card review-summary">
      <div className="section-heading"><h2><Scale size={18} /> Needs review</h2><span className="badge">{queue.length} open</span></div>
      <div className="stats review-stats">
        <Stat label="Potential conflicts" value={potential} />
        <Stat label="Insufficient evidence" value={insufficient} />
        <Stat label="Extraction & deadline items" value={queue.filter(item => item.source === 'issue').length} />
        <Stat label="Total open items" value={queue.length} />
      </div>
      <p className="phase-notice">Each item collects the established facts, missing facts, source excerpts and the specific question a lawyer must answer. Opening one builds a printable brief. Nothing is ever sent automatically.</p>
    </section>
    <section className="card ingestion-library review-list">
      <div className="filter-controls">
        <label>Search review items<input type="search" value={filters.query} onChange={e => onFilters({...filters, query:e.target.value})} /></label>
        <label>Reason<select value={filters.category} onChange={e => onFilters({...filters, category:e.target.value as ReviewFilters['category']})}><option value="">All reasons</option>{Object.entries(REASONS).map(([key,label]) => <option key={key} value={key}>{label} ({queue.filter(i => i.reasons.includes(key as ReviewCategory)).length})</option>)}</select></label>
        <label>Sort review items<select value={filters.sort} onChange={e => onFilters({...filters, sort:e.target.value as ReviewFilters['sort']})}><option value="priority">Queue order</option><option value="document">Document name</option></select></label>
        <button className="secondary" onClick={() => onFilters({...EMPTY_REVIEW})}>Clear filters</button>
        <p role="status">Showing {shown.length} of {queue.length} review items. Reason categories may overlap.</p>
      </div>
      {queue.length > 0 && !shown.length && <p className="library-note">No review items match these filters.</p>}
      {!queue.length ? <div className="empty"><CircleAlert />
        <p>{!portfolio.documents.length
          ? 'No documents have been analyzed yet. An empty queue does not mean there are no unresolved obligations.'
          : analyzed === 0
            ? 'No documents have completed analysis. Unprocessed documents are not covered by this queue.'
            : 'No open review items in the analyzed set. Documents that are still unprocessed or incomplete are not covered here — this is not an all-clear.'}</p>
      </div>
      : <ul className="document-rows">{shown.map(item => <li key={`${item.source}-${item.id}`}>
        {item.source === 'conflict' ? <Scale size={22} /> : <FileText size={22} />}
        <div className="row-copy">
          <button id={`review-${item.id}`} className="contract-link" disabled={!enabled} onClick={() => onOpen(item.id)}>{item.title}</button>
          <p>{item.documentIds.map(id => names.get(id) ?? id).join(' · ')}</p>
          <p>{item.reasons.map(r => REASONS[r]).join(' · ')}</p>
          <p><strong>Missing:</strong> {item.missing[0] ?? 'No additional fact was specified; review the question below.'}</p>
          {item.missing.length > 1 && <details><summary>{item.missing.length-1} more missing fact(s)</summary><ul>{item.missing.slice(1).map((fact,i) => <li key={i}>{fact}</li>)}</ul></details>}
          <p>{item.urgency}</p><small>{item.question}</small>
        </div>
        <span className="badge amber">{item.badge}</span>
        <div className="document-actions"><button className="secondary" disabled={!enabled} onClick={() => onOpen(item.id)}>Open brief</button></div>
      </li>)}</ul>}
    </section>
  </>
}

export function Review({ portfolio, enabled, filters, onFilters }: { portfolio: Portfolio; enabled: boolean; filters?: ReviewFilters; onFilters?: (f:ReviewFilters) => void }) {
  const [briefId, setBriefId] = useState<string | null>(null)
  if (briefId && !reviewItems(portfolio).some(i => i.id === briefId)) return <section className="card"><p role="alert">This review item changed or is no longer current.</p><button className="secondary" onClick={() => setBriefId(null)}>Return to review queue</button></section>
  if (briefId) return <Brief id={briefId} portfolio={portfolio} enabled={enabled} onBack={() => { const id=briefId; setBriefId(null); requestAnimationFrame(() => document.getElementById(`review-${id}`)?.focus()) }} />
  return <ReviewQueue portfolio={portfolio} onOpen={setBriefId} enabled={enabled} filters={filters} onFilters={onFilters} />
}
