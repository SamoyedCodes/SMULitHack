import { z } from 'zod'
import sample from '../../shared/sample-portfolio.json'
import { fieldNames, type Portfolio, type OcrDocument, type Action } from '../../shared/types'

const date = z.string().regex(/^\d{4}-\d{2}-\d{2}$/).refine(value => {
  const parsed = new Date(`${value}T00:00:00Z`)
  return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value
}, 'Invalid calendar date')
const confidence = z.enum(['high', 'medium', 'low'])
const basis = z.enum(['found', 'inferred', 'unresolved'])
const evidence = z.object({ document_id: z.string(), page: z.number().int().positive(), clause: z.string(), quote: z.string() })
const field = z.object({ value: z.string().nullable(), basis, confidence, reason: z.string(), evidence: z.array(evidence) })
export const documentSchema = z.object({
  id: z.string(), filename: z.string(), status: z.enum(['queued', 'processing', 'ready', 'failed']),
  pages: z.array(z.object({ number: z.number().int().positive(), text: z.string(), method: z.enum(['native', 'ocr']), quality: z.enum(['good', 'poor', 'unknown']) })),
  error: z.string().nullable(),
})
const portfolioSchema = z.object({
  schema_version: z.literal('1.0'), as_of: date, documents: z.array(documentSchema),
  contracts: z.array(z.object({ id: z.string(), document_id: z.string(), name: z.string(), category: z.string(), fields: z.object(Object.fromEntries(fieldNames.map(name => [name, field])) as Record<typeof fieldNames[number], typeof field>) })),
  actions: z.array(z.object({ id: z.string(), contract_id: z.string(), title: z.string(), due_date: date, event_date: date.nullable(), basis, confidence, reason: z.string(), evidence: z.array(evidence) })),
  conflicts: z.array(z.object({ id: z.string(), title: z.string(), contract_ids: z.array(z.string()).min(2), summary: z.string(), question: z.string(), confidence, evidence: z.array(evidence) })),
})

export function parsePortfolio(input: unknown): Portfolio {
  const portfolio = portfolioSchema.parse(input)
  for (const collection of [portfolio.documents, portfolio.contracts, portfolio.actions, portfolio.conflicts]) {
    if (new Set(collection.map(item => item.id)).size !== collection.length) throw new Error('Duplicate record IDs in response.')
  }
  for (const doc of portfolio.documents) {
    if (new Set(doc.pages.map(page => page.number)).size !== doc.pages.length) throw new Error('Duplicate page numbers in response.')
  }
  const documentIds = new Set(portfolio.documents.map(doc => doc.id))
  const contractIds = new Set(portfolio.contracts.map(contract => contract.id))
  const citations = [...portfolio.contracts.flatMap(contract => Object.values(contract.fields).flatMap(value => value.evidence)), ...portfolio.actions.flatMap(action => action.evidence), ...portfolio.conflicts.flatMap(conflict => conflict.evidence)]
  if (portfolio.contracts.some(contract => !documentIds.has(contract.document_id)) || portfolio.actions.some(action => !contractIds.has(action.contract_id)) || portfolio.conflicts.some(conflict => conflict.contract_ids.some(id => !contractIds.has(id)))) throw new Error('Response contains missing document or contract references.')
  for (const citation of citations) {
    const page = portfolio.documents.find(doc => doc.id === citation.document_id)?.pages.find(page => page.number === citation.page)
    if (!page || !citation.quote.trim() || !page.text.includes(citation.quote)) throw new Error('A source quote could not be matched to its cited page.')
  }
  for (const contract of portfolio.contracts) {
    for (const value of Object.values(contract.fields)) {
      if (value.evidence.some(source => source.document_id !== contract.document_id)) throw new Error('Contract fields must cite their own document.')
      if (value.basis !== 'unresolved' && (!value.value || !value.evidence.length)) throw new Error('Resolved fields must contain a value and supporting evidence.')
      if (value.basis === 'unresolved' && value.value !== null) throw new Error('Unresolved fields must have a null value.')
    }
  }
  if (portfolio.actions.some(action => !action.evidence.length) || portfolio.conflicts.some(conflict => !conflict.evidence.length)) throw new Error('Actions and potential conflicts must cite source evidence.')
  if (portfolio.actions.some(action => action.basis === 'unresolved')) throw new Error('Unresolved dates cannot be published as calendar actions.')
  for (const conflict of portfolio.conflicts) {
    if (new Set(conflict.contract_ids).size !== conflict.contract_ids.length) throw new Error('Conflicts must reference distinct contracts.')
    const documents = conflict.contract_ids.map(id => portfolio.contracts.find(contract => contract.id === id)!.document_id)
    if (documents.some(id => !conflict.evidence.some(source => source.document_id === id))) throw new Error('Conflicts must cite every compared contract.')
  }
  return portfolio
}

export const demoPortfolio = parsePortfolio(sample)
export const apiBase = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')
export function daysBetween(from: string, to: string) {
  return Math.round((Date.parse(`${to}T00:00:00Z`) - Date.parse(`${from}T00:00:00Z`)) / 86400000)
}
export function upcomingActions(actions: Action[], asOf: string) {
  return actions.filter(action => { const days = daysBetween(asOf, action.due_date); return days >= 0 && days <= 90 }).sort((first, second) => first.due_date.localeCompare(second.due_date))
}
export function formatDate(value: string) {
  return new Intl.DateTimeFormat('en-SG', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }).format(new Date(`${value}T00:00:00Z`))
}
export function validateFiles(files: File[]) {
  if (!files.length) throw new Error('Choose at least one document.')
  if (files.length > 80) throw new Error('Choose no more than 80 documents per batch.')
  for (const file of files) {
    if (!/\.(pdf|docx|png|jpe?g)$/i.test(file.name)) throw new Error(`${file.name}: use PDF, DOCX, PNG, or JPG.`)
    if (file.size === 0 || file.size > 20 * 1024 * 1024) throw new Error(`${file.name}: files must be nonempty and at most 20 MB.`)
  }
}
async function request(path: string, options?: RequestInit) {
  const response = await fetch(`${apiBase}${path}`, { ...options, signal: AbortSignal.timeout(60000) })
  if (!response.ok) throw new Error(`Server returned ${response.status}. Please try again.`)
  return response.json()
}
export async function fetchPortfolio() { return parsePortfolio(await request('/portfolio')) }
export async function uploadDocument(file: File): Promise<OcrDocument> {
  const body = new FormData()
  body.append('file', file)
  return documentSchema.parse(await request('/documents', { method: 'POST', body }))
}
