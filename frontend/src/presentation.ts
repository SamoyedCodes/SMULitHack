import type { ApiDocument, CalendarEvent, Portfolio, ReviewIssue } from './api'

export const REASONS = {
  source_unreadable: 'Source problems', missing_context: 'Missing context', ambiguous_terms: 'Ambiguous terms',
  unsupported_evidence: 'Unsupported evidence', incomplete_analysis: 'Incomplete analysis',
  potential_conflict: 'Potential conflicts', other: 'Other / unclassified',
} as const
export type ReviewCategory = keyof typeof REASONS
export type QueueItem = { id: string; source: 'issue' | 'conflict'; title: string; documentIds: string[]; question: string; badge: string; rank: number; reasons: ReviewCategory[]; missing: string[]; urgency: string }
export function issueReasons(issue: ReviewIssue): ReviewCategory[] {
  const codes = (issue.reason_codes ?? []).map(code => code === 'not_established' ? 'other' : code) as ReviewCategory[]
  if (!codes.length && issue.kind === 'source_reading') codes.push('source_unreadable')
  if (!codes.length && issue.kind === 'processing') codes.push('incomplete_analysis')
  return [...new Set(codes.length ? codes : ['other' as const])]
}
export function reviewItems(portfolio: Portfolio): QueueItem[] {
  const conflicts: QueueItem[] = portfolio.conflicts.filter(c => c.current && c.status !== 'no_conflict_identified_for_this_rule').map(c => ({
    id: c.id, source: 'conflict', title: c.status === 'potential_conflict' ? 'Potential distribution-rights conflict' : 'Distribution conflict — insufficient evidence',
    documentIds: c.documents, question: c.lawyer_question, badge: c.status.replaceAll('_', ' '), rank: c.status === 'potential_conflict' ? 3 : 2,
    reasons: c.status === 'potential_conflict' ? ['potential_conflict', ...(c.missing_facts.length ? ['missing_context' as const] : [])] : c.missing_facts.length ? ['missing_context'] : ['other'],
    missing: c.missing_facts, urgency: 'Review before relying on these distribution rights.',
  }))
  const wrappers = new Set(portfolio.conflicts.map(c => `conflict:${c.id}`))
  const issues: QueueItem[] = portfolio.issues.filter(i => !wrappers.has(i.id)).map(i => ({
    id: i.id, source: 'issue', title: i.title, documentIds: i.document_ids, question: i.lawyer_question,
    badge: i.kind.replaceAll('_', ' '), rank: i.kind === 'deadline' ? 1 : 0, reasons: issueReasons(i), missing: i.missing_facts, urgency: i.urgency,
  }))
  return [...new Map([...conflicts, ...issues].map(i => [i.id, i])).values()].sort((a,b) => b.rank-a.rank || a.id.localeCompare(b.id))
}
export function documentName(doc: ApiDocument) { return doc.title || doc.filename }
export function documentSummary(id: string, events: CalendarEvent[], queue: QueueItem[], asOf: string) {
  const own = events.filter(e => e.document_id === id)
  return { next: own.filter(e => e.action_date && e.action_date >= asOf && !e.overdue).map(e => e.action_date!).sort()[0] ?? null,
    overdue: own.filter(e => e.action_date && e.overdue).length, reviews: queue.filter(i => i.documentIds.includes(id)).length }
}
export type LibraryFilters = { query: string; status: string; needsReview: boolean; sort: 'name' | 'deadline' | 'review' }
export const EMPTY_LIBRARY: LibraryFilters = {query:'', status:'', needsReview:false, sort:'name'}
export function filterDocuments(documents: ApiDocument[], filters: LibraryFilters, events: CalendarEvent[], queue: QueueItem[], asOf: string) {
  const summary = new Map(documents.map(d => [d.id, documentSummary(d.id, events, queue, asOf)]))
  const query = filters.query.trim().toLowerCase()
  return documents.filter(d => (!query || [d.filename, d.title, ...d.parties].join(' ').toLowerCase().includes(query)) &&
    (!filters.status || d.status === filters.status) && (!filters.needsReview || summary.get(d.id)!.reviews > 0)).sort((a,b) => {
      const aa = summary.get(a.id)!, bb = summary.get(b.id)!
      return (filters.sort === 'deadline' ? (aa.next ?? '9999').localeCompare(bb.next ?? '9999') : filters.sort === 'review' ? bb.reviews-aa.reviews : 0) || documentName(a).localeCompare(documentName(b)) || a.id.localeCompare(b.id)
    })
}
export type ReviewFilters = {query: string; category: '' | ReviewCategory; sort: 'priority' | 'document'}
export const EMPTY_REVIEW: ReviewFilters = {query:'', category:'', sort:'priority'}
export function filterReview(queue: QueueItem[], names: Map<string,string>, filters: ReviewFilters) {
  const query = filters.query.trim().toLowerCase()
  return queue.filter(i => (!filters.category || i.reasons.includes(filters.category)) && (!query || [i.title, i.question, ...i.missing, ...i.documentIds.map(id => names.get(id) ?? id)].join(' ').toLowerCase().includes(query)))
    .sort((a,b) => filters.sort === 'document' ? a.documentIds.map(id => names.get(id) ?? id).join(' ').localeCompare(b.documentIds.map(id => names.get(id) ?? id).join(' ')) || a.id.localeCompare(b.id) : b.rank-a.rank || a.id.localeCompare(b.id))
}
export function actionGroups(events: CalendarEvent[]) {
  const order = (a: CalendarEvent,b: CalendarEvent) => (a.action_date ?? a.event_date).localeCompare(b.action_date ?? b.event_date) || a.id.localeCompare(b.id)
  return {overdue: events.filter(e => e.action_date && e.overdue).sort(order), upcoming: events.filter(e => e.action_date && !e.overdue).sort(order), events: events.filter(e => !e.action_date).sort(order)}
}
