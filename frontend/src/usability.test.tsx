import { expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import fixture from '../../shared/portfolio.fixture.json'
import type { ApiDocument, CalendarEvent, Portfolio, ReviewIssue } from './api'
import { EMPTY_LIBRARY, EMPTY_REVIEW, actionGroups, documentSummary, filterDocuments, filterReview, issueReasons, reviewItems } from './presentation'
import { OverviewSummary } from './Overview'
import { UpcomingActions, Calendar } from './Calendar'
import { DocumentLibrary } from './Ingestion'
import { ReviewQueue } from './Review'
import { metricText } from './Evaluation'

const doc = (id: string):ApiDocument => ({id,filename:`${id}.pdf`,title:'Same title',parties:['Acme Pte Ltd'],sha256:id,mode:'live',status:'text_ready',stage:'Text ready',error:null,page_count:2,pages_read:2,pages_analyzed:0,has_ocr:false,pagination:'original',findings:[],model_usage:[],rules:[],provisions:[],reviews:[],issues:[],warnings:[],created_at:'2026-09-05',model:'fake',version:'test'})
const issue:ReviewIssue = {id:'missing',document_ids:['00'],title:'Missing schedule',established:[],missing_facts:['Supply Schedule 2.','Confirm effective date.'],lawyer_question:'Does Schedule 2 change this?',urgency:'Review before renewal.',reason_codes:['missing_context','ambiguous_terms'],evidence:[],kind:'uncertainty',mode:'live'}
const event = (id:string, over:Partial<CalendarEvent> = {}):CalendarEvent => ({id,document_id:'00',label:'Renewal notice',event_type:'renewal',event_date:'2026-12-31',action_date:'2026-11-01',window_start:'2026-10-02',action:'Notice must be received',formula:'source calculation',assumptions:[],confidence:'medium',confidence_reason:'Source-based arithmetic',evidence:[],overdue:false,occurrence:0,provenance:'calculated',...over})
const portfolio = (over:Partial<Portfolio> = {}):Portfolio => ({...fixture,documents:[doc('00')],issues:[issue],events:[],...over} as Portfolio)

it('keeps all 80 contracts searchable, supports duplicate names and stable sorting without mutation', () => {
  const docs = Array.from({length:80},(_,i)=>doc(String(i).padStart(2,'0')))
  const queue = reviewItems(portfolio())
  const events = [event('next'), event('past',{overdue:true,action_date:'2026-08-30'})]
  expect(filterDocuments(docs,EMPTY_LIBRARY,events,queue,'2026-09-05')).toHaveLength(80)
  expect(filterDocuments(docs,{...EMPTY_LIBRARY,query:'ACME'},events,queue,'2026-09-05')).toHaveLength(80)
  expect(filterDocuments(docs,{...EMPTY_LIBRARY,query:'79.pdf'},events,queue,'2026-09-05').map(d=>d.id)).toEqual(['79'])
  expect(filterDocuments(docs,{...EMPTY_LIBRARY,needsReview:true},events,queue,'2026-09-05').map(d=>d.id)).toEqual(['00'])
  expect(filterDocuments(docs,{...EMPTY_LIBRARY,status:'failed'},events,queue,'2026-09-05')).toHaveLength(0)
  expect(documentSummary('00',events,queue,'2026-09-05')).toEqual({next:'2026-11-01',overdue:1,reviews:1})
  expect(filterDocuments([...docs].reverse(),{...EMPTY_LIBRARY,sort:'deadline'},events,queue,'2026-09-05')[0].id).toBe('00')
  expect(filterDocuments(docs,{...EMPTY_LIBRARY,sort:'review'},events,queue,'2026-09-05')[0].id).toBe('00')
  expect(docs[0].id).toBe('00')
  const html=renderToStaticMarkup(<DocumentLibrary documents={docs} enabled stale={false} onOpen={()=>{}} onRefresh={()=>{}} />)
  expect(html).toContain('Showing 80 of 80')
  expect(html).toContain('79.pdf')
})

it('deduplicates overlapping review reasons and keeps legacy uncertainty unclassified',()=>{
  const queue = reviewItems(portfolio({issues:[issue,issue]}))
  expect(queue).toHaveLength(1)
  expect(filterReview(queue,new Map([['00','Acme Agreement']]),{...EMPTY_REVIEW,category:'ambiguous_terms',query:'Schedule 2'})).toHaveLength(1)
  expect(filterReview(queue,new Map([['00','Acme Agreement']]),{...EMPTY_REVIEW,query:'acme'})).toHaveLength(1)
  expect(issueReasons({...issue,reason_codes:[]})).toEqual(['other'])
  expect(issueReasons({...issue,reason_codes:[],kind:'source_reading'})).toEqual(['source_unreadable'])
  const html=renderToStaticMarkup(<ReviewQueue portfolio={portfolio()} onOpen={()=>{}} />)
  expect(html).toContain('Supply Schedule 2.')
  expect(html).toContain('Review before renewal.')
  expect(html).toContain('more missing fact(s)')
})

it('separates overdue, windowed deadlines and event-only items with incomplete coverage',()=>{
  const events=[event('next'),event('past',{overdue:true,action_date:'2026-08-30'}),event('expiry',{action_date:null,window_start:null,action:'Term ends'})]
  const groups=actionGroups(events)
  expect(groups.overdue.map(e=>e.id)).toEqual(['past'])
  expect(groups.upcoming.map(e=>e.id)).toEqual(['next'])
  expect(groups.events.map(e=>e.id)).toEqual(['expiry'])
  const p=portfolio({events,coverage:{analyzed:0,pages:2,pages_analyzed:0,undated:1}})
  const overview=renderToStaticMarkup(<OverviewSummary portfolio={p} asOf="2026-09-05" stale onAsOf={()=>{}} onCalendar={()=>{}} onConflicts={()=>{}} onReview={()=>{}} />)
  expect(overview).toContain('0/1 documents completed analysis')
  expect(overview).toContain('stale or refreshing')
  expect(overview.match(/disabled=""/g)).toHaveLength(4)
  const actions=renderToStaticMarkup(<UpcomingActions portfolio={p} onOpen={()=>{}} />)
  expect(actions).toContain('Notice must be received by 2026-11-01')
  expect(actions).toContain('Window opens 2026-10-02')
  expect(actions).toContain('performance not established')
  const missing=renderToStaticMarkup(<Calendar portfolio={p} asOf="2026-09-05" enabled stale={false} focused="removed" onAsOf={()=>{}} onEvidence={()=>{}} />)
  expect(missing).toContain('selected event changed')
})

it('shows empty groups and zero denominators without claiming accuracy',()=>{
  expect(metricText({correct:0,total:0,rate:null})).toBe('Not measurable (0 denominator)')
  expect(metricText({correct:1,total:2,rate:.5})).toBe('1/2 (50.0%)')
  const html=renderToStaticMarkup(<UpcomingActions portfolio={portfolio({documents:[],issues:[]})} onOpen={()=>{}} />)
  expect(html).toContain('not an all-clear')
})
