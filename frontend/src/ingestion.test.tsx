import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { BatchReceipt, DocumentLibrary, validateBatchFiles } from './Ingestion'
import { fetchLatestBatch, fetchPages, retryReading, uploadBatch, type Batch, type Health } from './api'
import healthFixture from '../../shared/health.fixture.json'

afterEach(() => vi.unstubAllGlobals())
const limits = healthFixture.limits as Health['limits']
const batch: Batch = { id:'test', created_at:'2026-09-05T00:00:00Z', documents:[
  {id:'one',filename:'native.pdf',cached:false,error:null},
  {id:'one',filename:'duplicate.pdf',cached:true,error:null},
  {id:null,filename:'bad.exe',cached:false,error:'Unsupported format.'},
], progress:[] }

describe('batch ingestion UI contract', () => {
  it('keeps supported siblings and surfaces individual invalid file warnings', () => {
    const warnings = validateBatchFiles([new File(['fixture'],'valid.pdf'), new File([],'empty.pdf'), new File(['x'],'bad.exe'), {name:'large.pdf',size:26*1024*1024} as File], limits)
    expect(warnings[0]).toBeNull()
    expect(warnings.slice(1).every(Boolean)).toBe(true)
    expect(() => validateBatchFiles(Array(81).fill(new File(['x'],'doc.pdf')), limits)).toThrow('80')
  })
  it('uses one multipart batch and a stable idempotency key', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(batch)))
    vi.stubGlobal('fetch', fetch)
    await uploadBatch([new File(['x'],'one.pdf'),new File(['x'],'two.pdf')], 'retry-key')
    const [url, request] = fetch.mock.calls[0]
    expect(url).toBe('/api/batches')
    expect(request.headers).toEqual({'Idempotency-Key':'retry-key'})
    expect(request.body.getAll('files')).toHaveLength(2)
  })
  it('retrieves the latest persisted receipt without browser session state', async () => {
    vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify([batch]))))
    expect(await fetchLatestBatch()).toEqual(batch)
  })
  it('renders rejection and duplicate receipts visibly', () => {
    const markup = renderToStaticMarkup(<BatchReceipt batch={batch} />)
    expect(markup).toContain('Unsupported format.')
    expect(markup).toContain('Duplicate: existing document retained.')
  })
  it('requires canonical source pages and retry responses', async () => {
    vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify([{page:1,text:'invented'}]))))
    await expect(fetchPages('one')).rejects.toMatchObject({kind:'validation'})
    vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify({resumed_jobs:1}))))
    expect(await retryReading('one')).toEqual({resumed_jobs:1})
  })
  it('does not equate text readiness with legal assessment', () => {
    const markup = renderToStaticMarkup(<DocumentLibrary documents={[]} enabled stale={false} onOpen={() => {}} onRefresh={() => {}} />)
    expect(markup).toContain('Text readiness is not obligation extraction')
  })
})
