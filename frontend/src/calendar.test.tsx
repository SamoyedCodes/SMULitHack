import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { Calendar, UpcomingActions, actionableDate, groupByDate } from './Calendar'
import type { CalendarEvent, Portfolio, ReviewIssue } from './api'

const evidence = [{ document_id: 'a', span_ids: ['a:p2:s0'], quote: 'sixty calendar days before expiry', page: 2, clause: '8.3', boxes: [[1, 2, 3, 4]], source: 'native' as const, ocr_confidence: null }]

const event = (over: Partial<CalendarEvent> = {}): CalendarEvent => ({
  id: 'e1', document_id: 'a', label: 'Renewal notice', event_type: 'expiry', event_date: '2026-12-31',
  action_date: '2026-11-01', window_start: null, action: 'Notice must be received',
  formula: '2026-12-31 − 60 calendar days = 2026-11-01', assumptions: [], confidence: 'medium',
  confidence_reason: 'Matched source text.', evidence, overdue: false, occurrence: 0, provenance: 'calculated', ...over,
})

const issue = (over: Partial<ReviewIssue> = {}): ReviewIssue => ({
  id: 'i1', document_ids: ['a'], title: 'Deadline cannot be established', established: [],
  missing_facts: ['Business days are not defined in the source.'],
  lawyer_question: 'What does the agreement define as a business day?', urgency: 'Review before relying on this provision.',
  evidence, kind: 'deadline', mode: 'live', ...over,
})

const portfolio = (over: Partial<Portfolio> = {}): Portfolio => ({
  mode: 'live', as_of: '2026-09-05', horizon_end: '2026-12-04', sme: null, parties: [], documents: [],
  events: [], issues: [], conflicts: [], comparisons: { pending: 0, assessed: 0, failed: 0 },
  coverage: { total: 0, analyzed: 0, pages: 0, pages_read: 0, pages_analyzed: 0, dated: 0, dates_unavailable: 0, undated: 0 }, ...over,
})

const render = (over: Partial<Portfolio> = {}, enabled = true) =>
  renderToStaticMarkup(<Calendar portfolio={portfolio(over)} asOf="2026-09-05" enabled={enabled} stale={false} onAsOf={() => {}} onEvidence={() => {}} />)

describe('grouping helpers', () => {
  it('acts on the window opening before the deadline it closes', () => {
    expect(actionableDate(event({ window_start: '2026-10-02' }))).toBe('2026-10-02')
    expect(actionableDate(event({ action_date: null, window_start: null }))).toBe('2026-12-31')
  })

  it('groups by actionable date in chronological order', () => {
    const groups = groupByDate([event({ id: 'b', action_date: '2026-12-01' }), event({ id: 'a' })])
    expect(groups.map(([day]) => day)).toEqual(['2026-11-01', '2026-12-01'])
  })
})

describe('calendar view', () => {
  it('shows the deadline, its arithmetic and its source without recomputing anything', () => {
    const html = render({ events: [event()] })
    expect(html).toContain('2026-12-31 − 60 calendar days = 2026-11-01')
    expect(html).toContain('Notice must be received by 2026-11-01')
    expect(html).toContain('Page 2 · 8.3')
    expect(html).toContain('No model request is made to build this calendar')
  })

  it('preserves both notice window boundaries', () => {
    expect(render({ events: [event({ window_start: '2026-10-02' })] })).toContain('Window open 2026-10-02 to 2026-11-01')
  })

  it('marks an overdue action without asserting it was missed', () => {
    const html = render({ events: [event({ overdue: true })] })
    expect(html).toContain('Overdue · performance not established')
    expect(html.toLowerCase()).not.toContain('unpaid')
    expect(html.toLowerCase()).not.toContain('you can still')
  })

  it('states the confidence explanation rather than a bare band', () => {
    expect(render({ events: [event({ confidence_reason: 'Matched to OCR text.' })] })).toContain('Matched to OCR text.')
  })

  it('distinguishes an empty checked window from unprocessed documents', () => {
    const checked = render({ coverage: { ...portfolio().coverage, dated: 3 } })
    expect(checked).toContain('3 document(s) were checked')
    expect(checked).toContain('not a finding that no obligations exist')
    expect(checked.toLowerCase()).not.toContain('nothing to worry')
    expect(render()).toContain('No document has completed analysis')
  })

  it('counts documents whose dates could not be established as unknown, not absent', () => {
    const html = render({ coverage: { ...portfolio().coverage, dated: 1, undated: 2, dates_unavailable: 1 } })
    expect(html).toContain('3 document(s) were not checked for dates')
    expect(html).toContain('Their deadlines are unknown, not absent.')
  })

  it('shows unresolved date questions with their evidence in this phase', () => {
    const html = render({ issues: [issue({ established: ['Page 2, clause 8.3 contains: “sixty calendar days”'] })] })
    expect(html).toContain('Dates that could not be established')
    expect(html).toContain('Business days are not defined in the source.')
    expect(html).toContain('What does the agreement define as a business day?')
    expect(html).toContain('Page 2, clause 8.3 contains')
  })

  it('hides conflict issues that belong to another phase', () => {
    expect(render({ issues: [issue({ id: 'c1', kind: 'conflict', title: 'Overlapping grants' })] })).not.toContain('Overlapping grants')
  })

  it('disables reliance when the backend does not report the capability', () => {
    const html = render({ events: [event()] }, false)
    expect(html).toContain('Calendar is unavailable')
    expect(html).not.toContain('2026-12-31 − 60 calendar days')
  })

  it('marks retained results stale rather than hiding them', () => {
    const html = renderToStaticMarkup(<Calendar portfolio={portfolio({ events: [event()] })} asOf="2026-09-05" enabled stale onAsOf={() => {}} onEvidence={() => {}} />)
    expect(html).toContain('Upcoming dates · stale')
  })
})

describe('overview upcoming actions', () => {
  it('lists next actions without combining unrelated amounts into a total', () => {
    const html = renderToStaticMarkup(<UpcomingActions portfolio={portfolio({ events: [event()] })} onOpen={() => {}} />)
    expect(html).toContain('Renewal notice')
    expect(html).toContain('Notice must be received by 2026-11-01')
    expect(html.toLowerCase()).not.toContain('total exposure')
  })

  it('says the list only covers documents that finished analysis', () => {
    const html = renderToStaticMarkup(<UpcomingActions portfolio={portfolio({ events: [event()], coverage: { ...portfolio().coverage, undated: 2 } })} onOpen={() => {}} />)
    expect(html).toContain('2 document(s) have no established dates yet')
  })
})
