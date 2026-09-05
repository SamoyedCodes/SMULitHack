import { afterEach, expect, it, vi } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import Conflicts, { ConflictCard, unseenConflicts } from './Conflicts'
import { continueConflicts, fetchConflictScreens, type ConflictAssessment, type Portfolio } from './api'
import fixture from '../../shared/portfolio.fixture.json'

const evidence = {document_id:'a',span_ids:['a:p1:s0'],quote:'Exclusive distribution rights.',page:1,clause:'1',boxes:[[0,0,10,10]],source:'native' as const,ocr_confidence:null}
const result:ConflictAssessment={id:'pair',input_revision:'revision',created_at:'2026-09-05',current:true,status:'potential_conflict',documents:['a','b'],scope_comparison:{product:'Same product.'},exception_evidence:[],dimension_evidence:{product:[evidence]},evidence:[evidence,{...evidence,document_id:'b',page:2}],exceptions:[],missing_facts:[],explanation:'The grants may be incompatible.',lawyer_question:'Does the second grant need consent?',confidence:'medium',confidence_reason:'Semantic interpretation.',provenance:'inferred',mode:'live',model_usage:[]}
afterEach(()=>vi.unstubAllGlobals())
it('notifications include only unseen current potential conflicts',()=>{
  expect(unseenConflicts([result],new Set())).toHaveLength(1)
  expect(unseenConflicts([result],new Set(['revision']))).toHaveLength(0)
  expect(unseenConflicts([{...result,current:false}],new Set())).toHaveLength(0)
  expect(unseenConflicts([{...result,status:'insufficient_evidence'}],new Set())).toHaveLength(0)
})
it('renders both contracts, page links, bounded status and lawyer question',()=>{
  const html=renderToStaticMarkup(<ConflictCard result={result} names={new Map([['a','Alpha.pdf'],['b','Beta.pdf']])} onEvidence={()=>{}} focused={false}/> )
  expect(html).toContain('Alpha.pdf');expect(html).toContain('Beta.pdf')
  expect(html).toContain('Page 1');expect(html).toContain('Page 2')
  expect(html).toContain('Does the second grant need consent?')
  const stale=renderToStaticMarkup(<ConflictCard result={{...result,current:false}} names={new Map()} onEvidence={()=>{}} focused={false}/> )
  expect(stale).toContain('Stale assessment')
})
it('shows paused backlog and exposes remaining uncertainty without clearance',()=>{
  const portfolio={...fixture,mode:'live',sme:'Acme',conflicts:[result],conflict_scan:{...fixture.conflict_scan,state:'paused',allowance:10,assigned:10,unchecked:5,can_continue:true}} as Portfolio
  const html=renderToStaticMarkup(<Conflicts portfolio={portfolio} enabled stale={false} onEvidence={()=>{}} onRefresh={()=>{}} onChooseSme={()=>{}} focused={null}/> )
  expect(html).toContain('Continue — next 10');expect(html).toContain('Remaining candidate pairs have not been checked.')
  expect(html).toContain('unchecked candidate pairs')
})
it('uses an idempotency key and validates screening payloads',async()=>{
  const fetch=vi.fn().mockResolvedValueOnce(new Response(JSON.stringify(fixture.conflict_scan))).mockResolvedValueOnce(new Response('[{"outcome":"clear"}]'))
  vi.stubGlobal('fetch',fetch)
  await continueConflicts('same-click-key')
  expect(fetch.mock.calls[0][1].headers).toEqual({'Idempotency-Key':'same-click-key'})
  await expect(fetchConflictScreens()).rejects.toMatchObject({kind:'validation'})
})
