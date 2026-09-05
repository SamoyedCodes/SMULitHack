import { expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { ReviewQueue } from './Review'
import type { ApiDocument, ConflictAssessment, Evidence, Portfolio, ReviewIssue } from './api'

const evidence: Evidence = { document_id: 'doc-a', span_ids: ['doc-a:s0'], quote: 'exclusive distribution rights', page: 2, clause: '4.1', boxes: [[1, 2, 3, 4]], source: 'native', ocr_confidence: null }

const issue: ReviewIssue = { id: 'issue-1', document_ids: ['doc-a'], title: 'Termination rights need review', established: ['A 30-day notice period is stated.'], missing_facts: ['Schedule 2 was not supplied.'], lawyer_question: 'Does the missing schedule change the notice window?', urgency: 'Confirm before renewal.', evidence: [evidence], kind: 'uncertainty', mode: 'live' }

const conflict: ConflictAssessment = { id: 'conflict-1', status: 'potential_conflict', documents: ['doc-a', 'doc-b'], scope_comparison: { territory: 'Both grant Singapore.' }, evidence: [evidence], exceptions: [], missing_facts: ['Effective date unconfirmed.'], explanation: 'Overlapping exclusive grants.', lawyer_question: 'Can both exclusive grants coexist?', confidence: 'medium', confidence_reason: 'Wording overlaps.', provenance: 'inferred', mode: 'live' }

const cleared: ConflictAssessment = { ...conflict, id: 'conflict-2', status: 'no_conflict_identified_for_this_rule', lawyer_question: 'n/a' }

function doc(id: string, status = 'complete'): ApiDocument {
  return { id, filename: `${id}.pdf`, title: `${id} Agreement`, sha256: id, mode: 'live', status, stage: 'Analyzed', error: null, page_count: 3, pages_read: 3, pages_analyzed: 3, has_ocr: false, pagination: 'original', parties: [], findings: [], model_usage: [], rules: [], provisions: [], reviews: [], issues: [], warnings: [], created_at: '2026-09-05', model: 'fake', version: 'test' }
}

function portfolio(over: Partial<Portfolio> = {}): Portfolio {
  return { mode: 'live', as_of: '2026-09-05', horizon_end: '2026-12-04', sme: null, parties: [], documents: [doc('doc-a'), doc('doc-b')], events: [], issues: [issue], conflicts: [conflict, cleared], comparisons: {}, coverage: {}, ...over }
}

it('lists conflicts and issues with counts, names and lawyer questions', () => {
  const html = renderToStaticMarkup(<ReviewQueue portfolio={portfolio()} onOpen={() => {}} />)
  expect(html).toContain('Potential distribution-rights conflict')
  expect(html).toContain('Termination rights need review')
  expect(html).toContain('Can both exclusive grants coexist?')
  expect(html).toContain('doc-a Agreement · doc-b Agreement')
  // Potential + insufficient + total open counts (issue + one actionable conflict = 2 open).
  expect(html).toContain('2 open')
  expect(html).toContain('Open brief')
})

it('excludes no-conflict results from the actionable queue', () => {
  const html = renderToStaticMarkup(<ReviewQueue portfolio={portfolio()} onOpen={() => {}} />)
  expect(html).not.toContain('No distribution conflict identified for this rule')
})

it('distinguishes an analyzed-and-clear queue from unprocessed documents', () => {
  const clear = renderToStaticMarkup(<ReviewQueue portfolio={portfolio({ issues: [], conflicts: [] })} onOpen={() => {}} />)
  expect(clear).toContain('not an all-clear')
  const none = renderToStaticMarkup(<ReviewQueue portfolio={portfolio({ documents: [], issues: [], conflicts: [] })} onOpen={() => {}} />)
  expect(none).toContain('An empty queue does not mean')
})
