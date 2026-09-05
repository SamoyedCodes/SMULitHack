import { afterEach, expect, it, vi } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { ExtractionAction, Findings } from './Findings'
import { extractDocument, setSme, type ApiDocument, type Finding } from './api'

const finding: Finding = { id:'pay1', field:'payments', value:'Annual licence fee: S$40,000', party:'Acme', conditions:['Invoice required'], provenance:'found', confidence:'medium', confidence_reason:'Matched OCR; check the source.', evidence:[{document_id:'a',span_ids:['a:p2:s0'],quote:'S$40,000',page:2,clause:'4.1',boxes:[[1,2,3,4]],source:'ocr',ocr_confidence:90}] }
const doc: ApiDocument = { id:'a', filename:'a.pdf', title:'a', sha256:'h', mode:'live', status:'needs_review', stage:'Review required', error:null, page_count:2, pages_read:2, pages_analyzed:2, has_ocr:true, pagination:'original', parties:['Acme'], model_usage:[], findings:[finding,{...finding,id:'pay2',value:'Late fee: S$20'}], rules:[], provisions:[], reviews:[], issues:[], warnings:[], created_at:'2026-09-05', model:'fake', version:'test' }
afterEach(() => vi.unstubAllGlobals())
it('retains multiple payment obligations and explains missing fields beside evidence links', () => {
  const html = renderToStaticMarkup(<Findings document={doc} stale={false} onEvidence={() => {}} />)
  expect(html).toContain('Annual licence fee: S$40,000')
  expect(html).toContain('Late fee: S$20')
  expect(html).toContain('Page 2 · 4.1 · OCR')
  expect(html).toContain('Unresolved · Not established')
  expect(html).toContain('Invoice required')
  expect(html).toContain('Matched OCR')
})
it('shows data transfer and blocks another extraction while quota is waiting', () => {
  const html = renderToStaticMarkup(<ExtractionAction document={{...doc,status:'waiting',stage:'Waiting for model'}} enabled onRefresh={() => {}} />)
  expect(html).toContain('page text to OpenRouter')
  expect(html).toContain('disabled=""')
  expect(html).toContain('Waiting for model')
})
it('queues extraction explicitly and validates SME output', async () => {
  const fetch = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({resumed_jobs:1}))).mockResolvedValueOnce(new Response(JSON.stringify({name:'Acme',mode:'live'}))).mockResolvedValueOnce(new Response('{}'))
  vi.stubGlobal('fetch',fetch)
  await extractDocument('a')
  expect(fetch.mock.calls[0][0]).toBe('/api/extract?document_id=a')
  expect(fetch.mock.calls[0][1].method).toBe('POST')
  await setSme('Acme')
  await expect(setSme('Acme')).rejects.toMatchObject({kind:'validation'})
})
it('shows secondary provider use without confusing it with legal confidence', () => {
  const html = renderToStaticMarkup(<ExtractionAction document={{...doc,model_usage:[{provider:'gemini',requested_model:'configured-gemini',model:'actual-gemini',purpose:'Extraction',cached:true,fallback_reason:'OpenRouter API key is not configured.'}]}} enabled onRefresh={() => {}} />)
  expect(html).toContain('actual-gemini')
  expect(html).toContain('cached')
  expect(html).toContain('Secondary used: OpenRouter API key is not configured.')
})

it('makes visual review an explicit opt-in and explains image transfer', async () => {
  const html = renderToStaticMarkup(<ExtractionAction document={{...doc,has_ocr:true}} enabled onRefresh={() => {}} />)
  expect(html).toContain('Review low-confidence scans with AI (optional)')
  expect(html).toContain('page images and close-up crops')
  expect(html).not.toContain('checked=""')
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({resumed_jobs:1})))
  vi.stubGlobal('fetch', fetch)
  await extractDocument('a', true)
  expect(fetch.mock.calls[0][0]).toBe('/api/extract?document_id=a&visual_review=true')
})
