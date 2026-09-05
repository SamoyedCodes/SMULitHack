import { describe, expect, it, vi, afterEach } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import PrototypeDashboard from './PrototypeDashboard'
import { demoPortfolio, parsePortfolio, daysBetween, upcomingActions, validateFiles, fetchPortfolio, uploadDocument } from './data'

afterEach(() => vi.unstubAllGlobals())
const clone = () => structuredClone(demoPortfolio)

describe('shared data contract', () => {
  it('loads the complete sample portfolio', () => {
    expect(demoPortfolio.contracts).toHaveLength(4)
    expect(demoPortfolio.conflicts).toHaveLength(1)
    expect(demoPortfolio.contracts[3].fields.liability.value).toBeNull()
  })
  it('rejects invented source quotations', () => {
    const data = clone(); data.contracts[0].fields.payment.evidence[0].quote = 'Invented legal claim'
    expect(() => parsePortfolio(data)).toThrow('source quote')
  })
  it('rejects missing source pages and contract references', () => {
    const data = clone(); data.actions[0].evidence[0].page = 500
    expect(() => parsePortfolio(data)).toThrow('source quote')
    const missing = clone(); missing.conflicts[0].contract_ids.push('missing')
    expect(() => parsePortfolio(missing)).toThrow('references')
  })
  it('rejects duplicate IDs and page numbers', () => {
    const data = clone(); data.documents.push(data.documents[0])
    expect(() => parsePortfolio(data)).toThrow('Duplicate record')
    const pages = clone(); pages.documents[0].pages.push(pages.documents[0].pages[0])
    expect(() => parsePortfolio(pages)).toThrow('Duplicate page')
  })
  it('requires evidence for established fields and actions', () => {
    const data = clone(); data.contracts[0].fields.term.evidence = []
    expect(() => parsePortfolio(data)).toThrow('supporting evidence')
    const action = clone(); action.actions[0].evidence = []
    expect(() => parsePortfolio(action)).toThrow('must cite')
  })
  it('rejects impossible dates and non-null unresolved fields', () => {
    const data = clone(); data.as_of = '2026-02-30'
    expect(() => parsePortfolio(data)).toThrow()
    const unresolved = clone(); unresolved.contracts[3].fields.liability.value = 'Unlimited'
    expect(() => parsePortfolio(unresolved)).toThrow('null value')
  })
  it('requires distinct conflict parties and evidence on both sides', () => {
    const data = clone(); data.conflicts[0].evidence.pop()
    expect(() => parsePortfolio(data)).toThrow('every compared contract')
    const duplicate = clone(); duplicate.conflicts[0].contract_ids = ['northstar', 'northstar']
    expect(() => parsePortfolio(duplicate)).toThrow('distinct contracts')
  })
  it('rejects unresolved calendar actions and evidence from a different contract', () => {
    const data = clone(); data.actions[0].basis = 'unresolved'
    expect(() => parsePortfolio(data)).toThrow('Unresolved dates')
    const wrong = clone(); wrong.contracts[0].fields.term.evidence = wrong.contracts[1].fields.term.evidence
    expect(() => parsePortfolio(wrong)).toThrow('own document')
  })
})

describe('date windows', () => {
  it('calculates the sample notice deadline using calendar days', () => {
    expect(daysBetween('2026-10-01', '2026-11-30')).toBe(60)
    expect(daysBetween('2028-02-28', '2028-03-01')).toBe(2)
  })
  it('includes today and day 90, excludes overdue and day 91, sorts chronologically', () => {
    const action = demoPortfolio.actions[0]
    const dates = ['2026-12-05', '2026-12-04', '2026-09-04', '2026-09-05']
    const result = upcomingActions(dates.map(due_date => ({ ...action, due_date })), '2026-09-05')
    expect(result.map(item => item.due_date)).toEqual(['2026-09-05', '2026-12-04'])
  })
})

describe('upload validation', () => {
  it('accepts supported documents and rejects empty, oversized, unsupported and too many files', () => {
    const valid = new File(['sample'], 'contract.PDF')
    expect(() => validateFiles([valid])).not.toThrow()
    expect(() => validateFiles([new File([], 'empty.pdf')])).toThrow('nonempty')
    expect(() => validateFiles([{ name: 'huge.pdf', size: 21 * 1024 * 1024 } as File])).toThrow('20 MB')
    expect(() => validateFiles([new File(['sample'], 'run.exe')])).toThrow('use PDF')
    expect(() => validateFiles(Array(81).fill(valid))).toThrow('80 documents')
  })
})

it('retains the isolated synthetic prototype for future component reuse', () => {
  const markup = renderToStaticMarkup(<PrototypeDashboard />)
  expect(markup).toContain('Sample workspace')
  expect(markup).toContain('Needs review')
})
