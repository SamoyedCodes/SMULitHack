import { fetchBrief } from './api'
import { expect, it, vi, afterEach } from 'vitest'
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

it('retains confidence explanations and disables exports for stale context', () => {
  const html = renderToStaticMarkup(<BriefView brief={brief} enabled={false} onBack={() => {}} />)
  expect(html).toContain('This brief is stale or refreshing')
  expect(html.match(/disabled=""/g)).toHaveLength(2)
  expect(html).toContain(brief.confidence_reason!)
  expect(briefHtml(brief)).toContain(brief.confidence_reason!)
  const hostile = briefHtml({...brief, kind: '<script>alert(1)</script>', lawyer_question: '<img src=x onerror=alert(1)>'})
  expect(hostile).not.toContain('<script>')
  expect(hostile).not.toContain('<img')
  expect(hostile).toContain('&lt;script&gt;')
})

afterEach(() => vi.unstubAllGlobals())
it('requests a brief in the selected workspace/date and honors cancellation', async () => {
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(brief)))
  vi.stubGlobal('fetch', fetch)
  const controller = new AbortController()
  expect(await fetchBrief('issue:1', controller.signal, {mode: 'sample', as_of: '2026-12-01'})).toEqual(brief)
  expect(fetch.mock.calls[0][0]).toBe('/api/review/issue%3A1/brief?mode=sample&as_of=2026-12-01')
  controller.abort()
  await expect(fetchBrief('issue:1', controller.signal, {mode: 'sample', as_of: '2026-12-01'})).rejects.toBeDefined()
})

it('keeps same-title agreements distinguishable in screen and printed/exported source labels', () => {
  const sameTitle = {...brief, documents: brief.documents.map(d => ({...d, title: 'Distribution agreement'}))}
  for (const html of [briefHtml(sameTitle), renderToStaticMarkup(<BriefView brief={sameTitle} onBack={() => {}} />)]) {
    expect(html).toContain('Distribution agreement (a.pdf)')
    expect(html).toContain('Distribution agreement (b.pdf)')
    expect(html).toContain('Clause 4.1')
  }
})
