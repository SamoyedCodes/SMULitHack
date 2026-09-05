import { useState } from 'react'
import { CircleAlert, FileText, Scale } from 'lucide-react'
import { Brief } from './Brief'
import type { ConflictAssessment, Portfolio, ReviewIssue } from './api'

const CONFLICT_TITLES: Record<string, string> = {
  potential_conflict: 'Potential distribution-rights conflict',
  insufficient_evidence: 'Distribution conflict — insufficient evidence',
  no_conflict_identified_for_this_rule: 'No distribution conflict identified for this rule',
}
const CONFLICT_RANK: Record<string, number> = { potential_conflict: 3, insufficient_evidence: 2 }

type QueueItem = { id: string; source: 'issue' | 'conflict'; title: string; documentIds: string[]; question: string; badge: string; rank: number }

function items(portfolio: Portfolio): QueueItem[] {
  const conflicts = (portfolio.conflicts as ConflictAssessment[])
    .filter(c => c.status !== 'no_conflict_identified_for_this_rule')
    .map(c => ({ id: c.id, source: 'conflict' as const, title: CONFLICT_TITLES[c.status] ?? 'Distribution-rights review', documentIds: c.documents, question: c.lawyer_question, badge: c.status.replaceAll('_', ' '), rank: CONFLICT_RANK[c.status] ?? 1 }))
  const issues = (portfolio.issues as ReviewIssue[])
    .map(i => ({ id: i.id, source: 'issue' as const, title: i.title, documentIds: i.document_ids, question: i.lawyer_question, badge: i.kind.replaceAll('_', ' '), rank: i.kind === 'deadline' ? 1 : 0 }))
  return [...conflicts, ...issues].sort((a, b) => b.rank - a.rank || a.id.localeCompare(b.id))
}

function Stat({ label, value }: { label: string; value: number }) {
  return <article><span>{label}</span><strong>{value}</strong></article>
}

export function ReviewQueue({ portfolio, onOpen }: { portfolio: Portfolio; onOpen: (id: string) => void }) {
  const queue = items(portfolio)
  const names = new Map(portfolio.documents.map(doc => [doc.id, doc.title || doc.filename]))
  const conflicts = portfolio.conflicts as ConflictAssessment[]
  const potential = conflicts.filter(c => c.status === 'potential_conflict').length
  const insufficient = conflicts.filter(c => c.status === 'insufficient_evidence').length
  const analyzed = portfolio.documents.filter(d => ['complete', 'needs_review'].includes(d.status)).length
  return <>
    <section className="card review-summary">
      <div className="section-heading"><h2><Scale size={18} /> Needs review</h2><span className="badge">{queue.length} open</span></div>
      <div className="stats review-stats">
        <Stat label="Potential conflicts" value={potential} />
        <Stat label="Insufficient evidence" value={insufficient} />
        <Stat label="Extraction & deadline items" value={portfolio.issues.length} />
        <Stat label="Total open items" value={queue.length} />
      </div>
      <p className="phase-notice">Each item collects the established facts, missing facts, source excerpts and the specific question a lawyer must answer. Opening one builds a printable brief. Nothing is ever sent automatically.</p>
    </section>
    <section className="card ingestion-library review-list">
      {!queue.length ? <div className="empty"><CircleAlert />
        <p>{!portfolio.documents.length
          ? 'No documents have been analyzed yet. An empty queue does not mean there are no unresolved obligations.'
          : analyzed === 0
            ? 'No documents have completed analysis. Unprocessed documents are not covered by this queue.'
            : 'No open review items in the analyzed set. Documents that are still unprocessed or incomplete are not covered here — this is not an all-clear.'}</p>
      </div>
      : <ul className="document-rows">{queue.map(item => <li key={`${item.source}-${item.id}`}>
        {item.source === 'conflict' ? <Scale size={22} /> : <FileText size={22} />}
        <div className="row-copy">
          <button className="contract-link" onClick={() => onOpen(item.id)}>{item.title}</button>
          <p>{item.documentIds.map(id => names.get(id) ?? id).join(' · ')}</p>
          <small>{item.question}</small>
        </div>
        <span className="badge amber">{item.badge}</span>
        <div className="document-actions"><button className="secondary" onClick={() => onOpen(item.id)}>Open brief</button></div>
      </li>)}</ul>}
    </section>
  </>
}

export function Review({ portfolio, enabled }: { portfolio: Portfolio; enabled: boolean }) {
  const [briefId, setBriefId] = useState<string | null>(null)
  if (briefId) return <Brief id={briefId} portfolio={portfolio} enabled={enabled} onBack={() => setBriefId(null)} />
  return <ReviewQueue portfolio={portfolio} onOpen={setBriefId} />
}
