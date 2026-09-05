import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import App, { Readiness } from './App'
import { apiRequest, fetchHealth, fetchLivePortfolio } from './api'
import health from '../../shared/health.fixture.json'
import portfolio from '../../shared/portfolio.fixture.json'

afterEach(() => vi.unstubAllGlobals())
const mock = (body: unknown, status = 200) => {
  const fn = vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status }))
  vi.stubGlobal('fetch', fn)
  return fn
}

describe('canonical backend contract', () => {
  it('uses relative API routes and validates the real backend fixtures', async () => {
    const fetch = mock(health)
    expect(await fetchHealth()).toEqual(health)
    expect(fetch.mock.calls[0][0]).toBe('/api/health')
    mock(portfolio)
    expect(await fetchLivePortfolio()).toEqual(portfolio)
  })
  it('rejects missing capabilities and legacy sample payloads', async () => {
    mock({ ...health, capabilities: undefined })
    await expect(fetchHealth()).rejects.toMatchObject({ kind: 'validation' })
    mock({ schema_version: '1.0', contracts: [] })
    await expect(fetchLivePortfolio()).rejects.toMatchObject({ kind: 'validation' })
  })
  it('handles structured degraded health without pretending readiness', async () => {
    mock({ ...health, status: 'degraded', database: { status: 'unavailable' } }, 503)
    expect((await fetchHealth()).status).toBe('degraded')
  })
  it('distinguishes transport, malformed and HTTP errors without falling back to samples', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('private details')))
    await expect(fetchHealth()).rejects.toMatchObject({ kind: 'transport' })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('<html>proxy error</html>', { status: 503 })))
    await expect(fetchHealth()).rejects.toMatchObject({ kind: 'api', status: 503 })
    mock({ error: { code: 'feature_not_enabled' } }, 501)
    await expect(apiRequest('/batches')).rejects.toMatchObject({ kind: 'api', status: 501 })
  })
  it('leaves multipart content type to the browser for future batch upload', async () => {
    const fetch = mock({})
    const body = new FormData(); body.append('files', new File(['fixture'], 'fixture.pdf'))
    await apiRequest('/batches', { method: 'POST', body })
    expect(fetch.mock.calls[0][1].body).toBe(body)
    expect(fetch.mock.calls[0][1].headers).toBeUndefined()
  })
})

it('starts with a live checking state, disabled ingestion and no invented SME or sample claims', () => {
  const markup = renderToStaticMarkup(<App />)
  expect(markup).toContain('Checking connection')
  expect(markup).toContain('SME not selected')
  expect(markup).toContain('Connect to the backend')
  expect(markup).not.toContain('Meridian')
  expect(markup).not.toContain('Sample workspace')
  expect(markup).toContain('disabled="" aria-describedby="ingestion-note"')
})

it('marks stale local checks and does not claim a configured key was verified', () => {
  // Fixture is generated directly from the typed backend response.
  const markup = renderToStaticMarkup(<Readiness health={{ ...health, api_version: '1', status: 'ready', model_status: 'configured_unverified', key_configured: true, providers: [{name:'openrouter',role:'primary',model:'openrouter/free',key_configured:true,status:'configured_unverified'}], database: {status:'ready'} }} stale />)
  expect(markup).toContain('Configured, not verified · stale')
  expect(markup).toContain('Last response · stale')
})
