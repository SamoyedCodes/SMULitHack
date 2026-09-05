import Ajv2020 from 'ajv/dist/2020'
import spec from '../../shared/openapi.json'
import type { components } from '../../shared/api.generated'

export type Health = components['schemas']['HealthResponse']
export type Portfolio = components['schemas']['Portfolio']
export type ApiDocument = components['schemas']['Document']
export type Finding = components['schemas']['Finding']
export type Evidence = components['schemas']['Evidence']
export type ContractMode = 'live' | 'sample'

// Use the exact backend schemas for runtime validation as well as generated types.
const ajv = new Ajv2020({ strict: false, validateFormats: false })
ajv.addSchema({ $id: 'aithena', components: spec.components })
const validateHealth = ajv.compile<Health>({ $ref: 'aithena#/components/schemas/HealthResponse' })
const validatePortfolio = ajv.compile<Portfolio>({ $ref: 'aithena#/components/schemas/Portfolio' })
export class ApiError extends Error {
  constructor(public kind: 'transport' | 'api' | 'validation', message: string, public status?: number) { super(message) }
}

export async function apiRequest(path: string, options: RequestInit = {}, allowDegraded = false): Promise<unknown> {
  let response: Response
  try {
    response = await fetch(`/api${path}`, { ...options, signal: AbortSignal.any([AbortSignal.timeout(5000), ...(options.signal ? [options.signal] : [])]) })
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
export async function fetchLivePortfolio(signal?: AbortSignal): Promise<Portfolio> {
  const body = await apiRequest('/portfolio', { signal })
  if (!validatePortfolio(body) || body.mode !== 'live') throw new ApiError('validation', 'The portfolio response does not match the live workspace contract.')
  return body
}

// Established-party (SME) selection. Sends null to clear the current selection.
export async function setSme(name: string | null, mode: ContractMode = 'live', signal?: AbortSignal): Promise<void> {
  await apiRequest('/settings/sme', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, mode }),
    signal,
  })
}
