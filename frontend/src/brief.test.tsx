import { expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { BriefView, briefHtml } from './Brief'
import type { Brief, Evidence } from './api'

const evidence: Evidence = { document_id: 'doc-a', span_ids: ['doc-a:s0'], quote: 'exclusive distribution rights in Singapore', page: 2, clause: '4.1', boxes: [[1, 2, 3, 4]], source: 'native', ocr_confidence: null }

const brief: Brief = {
  id: 'conflict-1', source: 'conflict', kind: 'potential_conflict', mode: 'live',
  generated_at: '2026-09-05T10:00:00+08:00', as_of: '2026-09-05', title: 'Potential distribution-rights conflict',
  documents: [{ id: 'doc-a', title: 'Alpha Agreement', filename: 'a.pdf' }, { id: 'doc-b', title: 'Beta Agreement', filename: 'b.pdf' }],
  established: [], missing_facts: ['The effective date of the second grant is unconfirmed.'],
  lawyer_question: 'Can both exclusive grants coexist, or does one override the other?',
  urgency: 'Confirm before signing the next distribution agreement.',
  explanation: 'Two agreements appear to grant overlapping exclusive distribution rights.',
  scope_comparison: { territory: 'Both grant Singapore rights.', product: 'Both cover Model X.' },
  exceptions: ['Online sales are carved out in the second agreement.'],
  provenance: 'inferred', confidence: 'medium', confidence_reason: 'Cited wording overlaps.',
  evidence: [{ ...evidence }, { ...evidence, document_id: 'doc-b' }], coverage_warnings: [],
  disclaimer: 'This brief summarizes grounded source evidence for human legal review. It is not legal advice.',
}

it('renders every brief section, excerpts and the print/download controls', () => {
  const html = renderToStaticMarkup(<BriefView brief={brief} onBack={() => {}} />)
  expect(html).toContain('Potential distribution-rights conflict')
  expect(html).toContain('Both grant Singapore rights.')
  expect(html).toContain('The effective date of the second grant is unconfirmed.')
  expect(html).toContain('Can both exclusive grants coexist')
  expect(html).toContain('Confirm before signing the next distribution agreement.')
  expect(html).toContain('exclusive distribution rights in Singapore')
  expect(html).toContain('Online sales are carved out')
  expect(html).toContain('inferred')
  expect(html).toContain('medium confidence')
  expect(html).toContain('Print / Save as PDF')
  expect(html).toContain('Download brief')
  expect(html).toContain('It is not legal advice.')
})

it('surfaces source coverage warnings instead of hiding them', () => {
  const html = renderToStaticMarkup(<BriefView brief={{ ...brief, coverage_warnings: ['The source pages for a cited document could not be reopened.'] }} onBack={() => {}} />)
  expect(html).toContain('Source coverage warning')
  expect(html).toContain('could not be reopened')
})

it('serializes a self-contained HTML brief with verbatim excerpts', () => {
  const doc = briefHtml(brief)
  expect(doc.startsWith('<!doctype html>')).toBe(true)
  expect(doc).toContain('exclusive distribution rights in Singapore')
  expect(doc).toContain('Can both exclusive grants coexist')
  expect(doc).toContain('Both cover Model X.')
  // No external asset references — fully self-contained for offline reading.
  expect(doc).not.toContain('src=')
  expect(doc).not.toContain('http://')
})
