export type Brief = components['schemas']['Brief']
export type ReviewIssue = components['schemas']['ReviewIssue']
export type CalendarEvent = components['schemas']['Event']
import Ajv2020 from 'ajv/dist/2020'
import spec from '../../shared/openapi.json'
import type { components } from '../../shared/api.generated'

export type Health = components['schemas']['HealthResponse']
export type Portfolio = components['schemas']['Portfolio']
export type Finding = components['schemas']['Finding']
export type Evidence = components['schemas']['Evidence']
export type ApiDocument = components['schemas']['Document']

// Use the exact backend schemas for runtime validation as well as generated types.
const ajv = new Ajv2020({ strict: false, validateFormats: false })
ajv.addSchema({ $id: 'aithena', components: spec.components })
const validateHealth = ajv.compile<Health>({ $ref: 'aithena#/components/schemas/HealthResponse' })
const validatePortfolio = ajv.compile<Portfolio>({ $ref: 'aithena#/components/schemas/Portfolio' })
export class ApiError extends Error {
  constructor(public kind: 'transport' | 'api' | 'validation', message: string, public status?: number) { super(message) }
}

export async function apiRequest(path: string, options: RequestInit = {}, allowDegraded = false, timeout = 5000): Promise<unknown> {
  let response: Response
  try {
    response = await fetch(`/api${path}`, { ...options, signal: AbortSignal.any([AbortSignal.timeout(timeout), ...(options.signal ? [options.signal] : [])]) })
  } catch {
    throw new ApiError('transport', 'Cannot reach the local backend. Start it and check the configured ports.')
  }
  let body: unknown
  try { body = await response.json() } catch {
    throw new ApiError('api', `The local service returned an unreadable response (HTTP ${response.status}).`, response.status)
  }
  if (!response.ok && !(allowDegraded && response.status === 503)) {
    // Do not render arbitrary server text or proxy stack traces.
    throw new ApiError('api', `The local service could not complete this request (HTTP ${response.status}).`, response.status)
  }
  return body
}

export async function fetchHealth(signal?: AbortSignal): Promise<Health> {
  const body = await apiRequest('/health', { signal }, true)
  if (!validateHealth(body)) throw new ApiError('validation', 'The backend health response does not match this build. Restart matching frontend and backend versions.')
  return body
}
export async function fetchLivePortfolio(signal?: AbortSignal, asOf?: string): Promise<Portfolio> {
  const body = await apiRequest(`/portfolio${asOf ? `?as_of=${encodeURIComponent(asOf)}` : ''}`, { signal })
  if (!validatePortfolio(body) || body.mode !== 'live') throw new ApiError('validation', 'The portfolio response does not match the live workspace contract.')
  return body
}

export type Batch = components['schemas']['BatchResponse']
export type SourcePage = components['schemas']['Page']
const validateBatch = ajv.compile<Batch>({ $ref: 'aithena#/components/schemas/BatchResponse' })
const validatePages = ajv.compile<SourcePage[]>({ type: 'array', items: { $ref: 'aithena#/components/schemas/Page' } })
const validateRetry = ajv.compile<components['schemas']['RetryResponse']>({ $ref: 'aithena#/components/schemas/RetryResponse' })
export async function uploadBatch(files: File[], key: string): Promise<Batch> {
  const body = new FormData()
  files.forEach(file => body.append('files', file, file.webkitRelativePath || file.name))
  const result = await apiRequest('/batches', { method: 'POST', headers: { 'Idempotency-Key': key }, body }, false, 120000)
  if (!validateBatch(result)) throw new ApiError('validation', 'The upload acknowledgement does not match this build. Retry the same selection to recover its batch receipt.')
  return result
}
export async function fetchBatch(id: string): Promise<Batch> {
  const body = await apiRequest(`/batches/${encodeURIComponent(id)}`)
  if (!validateBatch(body)) throw new ApiError('validation', 'Invalid batch response.')
  return body
}
export async function fetchPages(id: string, signal?: AbortSignal): Promise<SourcePage[]> {
  const body = await apiRequest(`/documents/${encodeURIComponent(id)}/pages`, { signal })
  if (!validatePages(body)) throw new ApiError('validation', 'The source page response does not match this build.')
  return body
}
export async function retryReading(id: string) {
  const body = await apiRequest(`/retry?document_id=${encodeURIComponent(id)}`, { method: 'POST' })
  if (!validateRetry(body)) throw new ApiError('validation', 'Invalid retry response.')
  return body
}

export async function fetchLatestBatch(): Promise<Batch | null> {
  const body = await apiRequest('/batches?limit=1')
  if (!Array.isArray(body) || body.some(item => !validateBatch(item))) throw new ApiError('validation', 'Invalid batch history response.')
  return (body[0] as Batch | undefined) ?? null
}

const validateSme = ajv.compile<components['schemas']['SmeSelection-Output']>({ $ref: 'aithena#/components/schemas/SmeSelection-Output' })
export async function setSme(name: string | null): Promise<void> {
  const body = await apiRequest('/settings/sme', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({name, mode:'live'}) })
  if (!validateSme(body)) throw new ApiError('validation', 'The party selection response does not match this build.')
}
export async function extractDocument(id: string, visualReview = false): Promise<void> {
  const body = await apiRequest(`/extract?document_id=${encodeURIComponent(id)}${visualReview ? '&visual_review=true' : ''}`, { method: 'POST' })
  if (!validateRetry(body)) throw new ApiError('validation', 'The extraction response does not match this build.')
}

export type ConflictAssessment = components['schemas']['ConflictAssessment']
export type ConflictScreen = components['schemas']['ConflictScreen']
const validateScreens = ajv.compile<ConflictScreen[]>({type:'array',items:{$ref:'aithena#/components/schemas/ConflictScreen'}})
const validateScan = ajv.compile<components['schemas']['ConflictScan']>({$ref:'aithena#/components/schemas/ConflictScan'})
export async function fetchConflictScreens(signal?:AbortSignal):Promise<ConflictScreen[]> {
  const data=await apiRequest('/conflicts/screening',{signal})
  if(!validateScreens(data))throw new ApiError('validation','Conflict screening does not match this build.')
  return data
}
export async function continueConflicts(key:string) {
  const data=await apiRequest('/conflicts/continue',{method:'POST',headers:{'Idempotency-Key':key}},false,120000)
  if(!validateScan(data))throw new ApiError('validation','The conflict allowance response does not match this build.')
  return data
}
export async function retryConflict(id:string) {
  const data=await apiRequest(`/conflicts/${encodeURIComponent(id)}/retry`,{method:'POST'})
  if(!validateRetry(data))throw new ApiError('validation','The comparison retry response does not match this build.')
  return data
}

const validateBrief = ajv.compile<Brief>({ $ref: 'aithena#/components/schemas/Brief' })
export async function fetchBrief(id: string, signal?: AbortSignal, context?: Pick<Portfolio, 'mode' | 'as_of'>): Promise<Brief> {
  const query = context ? `?${new URLSearchParams({mode: context.mode, as_of: context.as_of})}` : ''
  const body = await apiRequest(`/review/${encodeURIComponent(id)}/brief${query}`, { signal })
  if (!validateBrief(body)) throw new ApiError('validation', 'The lawyer brief response does not match this build.')
  return body
}

export type EvaluationScorecard = components['schemas']['EvaluationScorecard']
const validateScorecard = ajv.compile<EvaluationScorecard>({$ref:'aithena#/components/schemas/EvaluationScorecard'})
export async function fetchScorecard(signal?: AbortSignal): Promise<EvaluationScorecard> {
  const result = await apiRequest('/evaluation/scorecard', {signal})
  if (!validateScorecard(result)) throw new ApiError('validation', 'The saved evaluation does not match this build.')
  return result
}
export async function downloadEvaluation(card: EvaluationScorecard, signal?: AbortSignal) {
  const query = new URLSearchParams({run_sha256:card.run_sha256, generated_at:card.generated_at})
  const response = await fetch(`/api/evaluation/report?${query}`, {signal:AbortSignal.any([AbortSignal.timeout(5000), ...(signal ? [signal] : [])])})
  if (!response.ok) throw new Error('The evaluation report could not be downloaded. Refresh the saved scorecard and retry.')
  return response.blob()
}
