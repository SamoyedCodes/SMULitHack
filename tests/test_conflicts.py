import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import config as settings
from backend.api import create_app
from backend.config import Config
from backend.conflicts import screen,pair_id,time_comparison,validate_assessment,JOB_KIND,CONFLICT_VERSION
from backend.conflict_service import reconcile,snapshot,read_sources,retry_comparison
from backend.foundation import CAPABILITIES
from backend.llm import QuotaWait,ProviderUnavailable
from backend.store import Store
from backend.worker import Worker
from conflict_fixtures import seed,draft_for,FakeComparison,SME

@pytest.fixture(autouse=True)
def isolated(monkeypatch,tmp_path):
    monkeypatch.setattr(settings,'ROOT',tmp_path)
    monkeypatch.setattr(CAPABILITIES,'conflicts',True)
    for key in ['OPENROUTER_API_KEY','GEMINI_API_KEY','GOOGLE_API_KEY','OPENROUTER_MODEL','GEMINI_MODEL','AITHENA_DATA_DIR','AITHENA_WEB_PORT','AITHENA_API_PORT']:
        monkeypatch.delenv(key,raising=False)


def pair(tmp_path,**kwargs):
    config,store=Config(tmp_path),Store(tmp_path)
    a,_=seed(config,store,'a')
    b,_=seed(config,store,'b',exclusive=False,**kwargs)
    pages,hashes=read_sources(config,[a,b])
    return config,store,a,b,pages,hashes


def record(config,a,b,pages,hashes):return screen(a,b,pages,hashes,SME,config.routing_identity)


def test_answer_key_screening_and_constrained_outcomes(tmp_path):
    answers=json.loads((Path(__file__).parent/'fixtures/conflict_answer_key.json').read_text())
    observed={};expected_candidates=[];retained=[];predicted=[];actual=[]
    for name,expected in answers.items():
        root=tmp_path/name;root.mkdir()
        kwargs={'product':'coffee brewing equipment'} if name=='wording' else {'start':'2027-01-01','end':'2027-12-31'} if name=='disjoint' else {'channel':'online sales'} if name=='online_exception' else {'exceptions':['The competing grant is subject to prior written consent.']} if name=='unknown_consent' else {}
        config,store,a,b,pages,hashes=pair(root,**kwargs)
        if name=='missing_schedule':
            a.provisions[0].missing_context=['Schedule 1 is absent.']
            pages['a'][0].spans[0].text+=' Products means the items in Schedule 1.'
        if name=='missing_provisions':b.provisions=[]
        if name=='renewal_uncertain':a.provisions[0].exceptions=['Rights may renew with written agreement.']
        exception='Exclusive retail rights exclude online sales.' if name=='online_exception' else None
        if exception:
            from backend.documents import save_pages
            a.provisions[0].exceptions=[exception]
            pages['a'][0].spans[0].text+=' '+exception
            a.provisions[0].citations[0].quote=pages['a'][0].spans[0].text
        item=record(config,a,b,pages,hashes)
        assert item.outcome==expected['screen'],name
        observed[name]={'screen':item.outcome}
        if expected['screen']=='candidate':
            expected_candidates.append(name)
            if item.outcome=='candidate':retained.append(name)
            status='no_conflict_identified_for_this_rule' if exception else 'insufficient_evidence' if name in {'unknown_consent','renewal_uncertain'} else 'potential_conflict'
            draft=draft_for(a,b,pages,status=status,time='unknown' if name=='renewal_uncertain' else 'yes',
                            missing=['Written consent is not supplied.'] if name=='unknown_consent' else None,exception=exception)
            result=validate_assessment(draft,a,b,pages,item,time_comparison(a,b,pages))
            assert result.status==expected['status'],name
            observed[name]['status']=result.status
            predicted.append(result.status=='potential_conflict');actual.append(expected['status']=='potential_conflict')
    assert len(retained)==len(expected_candidates)==5
    tp=sum(p and a for p,a in zip(predicted,actual))
    assert tp/sum(predicted)==tp/sum(actual)==1
    # This measures fixtures and validator behavior, NOT actual model semantics.


@pytest.mark.parametrize('mutation',['quote','dimension','time','documents','exception'])
def test_invalid_assessments_suppress_unsupported_conclusions(tmp_path,mutation):
    cfg,store,a,b,pages,hashes=pair(tmp_path)
    item=record(cfg,a,b,pages,hashes);draft=draft_for(a,b,pages)
    if mutation=='quote':draft.citations[0].quote='Fabricated clause'
    if mutation=='dimension':draft.dimension_citations.pop('customers')
    if mutation=='time':draft.time_overlap='no'
    if mutation=='documents':draft.documents=['a','a','b']
    if mutation=='exception':draft.exceptions=['Consent was obtained']
    result=validate_assessment(draft,a,b,pages,item,time_comparison(a,b,pages))
    assert result.status=='insufficient_evidence' and not result.scope_comparison
    assert 'may be incompatible' not in result.explanation and result.missing_facts


def test_uncertain_negative_inputs_never_exclude(tmp_path):
    cfg,store,a,b,pages,hashes=pair(tmp_path,start='2027-01-01',end='2027-12-31')
    assert record(cfg,a,b,pages,hashes).outcome=='excluded'
    a.reviews=[]
    assert record(cfg,a,b,pages,hashes).outcome=='needs_evidence'
    a,_=seed(cfg,store,'c')
    pages,hashes=read_sources(cfg,[a,b]);a.provisions[0].ends_on=None
    assert record(cfg,a,b,pages,hashes).outcome=='candidate'
    a.provisions[0].grantor='An unknown alias'
    assert record(cfg,a,b,pages,hashes).outcome=='needs_evidence'


def test_pair_key_symmetric_and_sensitive_to_sources_and_sme(tmp_path):
    cfg,store,a,b,pages,hashes=pair(tmp_path)
    assert pair_id(a,b,hashes,SME,'route')==pair_id(b,a,hashes,SME,'route')
    assert pair_id(a,b,hashes,SME,'route')!=pair_id(a,b,{**hashes,'a':'changed'},SME,'route')
    assert pair_id(a,b,hashes,SME,'route')!=pair_id(a,b,hashes,'other','route')


def test_budget_continue_idempotency_and_restart(tmp_path):
    cfg,store=Config(tmp_path),Store(tmp_path)
    for n in range(6):seed(cfg,store,str(n))
    reconcile(cfg,store,'live');assert not store.jobs('live')
    store.set_setting('sme:live',SME)
    for _ in range(3):reconcile(cfg,store,'live')
    scan,_,_,_=snapshot(cfg,store,'live')
    assert scan.assigned==scan.queued==10 and scan.unchecked==5
    with pytest.raises(ValueError):reconcile(cfg,store,'live','too-early')
    fake=FakeComparison();worker=Worker(cfg,store,llm=fake)
    while worker.run_once():pass
    assert fake.calls==10
    scan,_,results,issues=snapshot(cfg,store,'live')
    assert scan.can_continue and len(issues)==10 and all(r.current for r in results)
    reconcile(cfg,Store(tmp_path),'live')
    reconcile(cfg,store,'live','next-group');reconcile(cfg,store,'live','next-group')
    scan,*_=snapshot(cfg,store,'live')
    assert scan.allowance==20 and scan.assigned==15 and scan.queued==5
    while worker.run_once():pass
    seed(cfg,store,'6');reconcile(cfg,store,'live')
    scan,*_=snapshot(cfg,store,'live')
    assert scan.assigned==20 and scan.unchecked==1  # uploads do not replenish allowance


def test_failed_pair_retry_does_not_touch_documents_or_budget(tmp_path):
    cfg,store,a,b,pages,hashes=pair(tmp_path);store.set_setting('sme:live',SME);reconcile(cfg,store,'live')
    class Missing:
        def compare(self,payload):raise ProviderUnavailable('Configure provider')
    Worker(cfg,store,llm=Missing()).run_once()
    job=store.jobs('live')[0]
    assert job['state']=='blocked' and store.document(a.id)==a
    assert retry_comparison(cfg,store,'live',job['cache_key'])==1
    assert snapshot(cfg,store,'live')[0].assigned==1
    class Waiting:
        def compare(self,payload):raise QuotaWait(180)
    Worker(cfg,store,llm=Waiting()).run_once()
    before=store.jobs('live')[0]
    assert retry_comparison(cfg,store,'live',job['cache_key'])==0
    assert store.jobs('live')[0]['next_run']==before['next_run']


def test_stale_result_never_becomes_current_and_legacy_jobs_idle(tmp_path):
    cfg,store,a,b,pages,hashes=pair(tmp_path);store.set_setting('sme:live',SME)
    store.enqueue('old','conflict',{'mode':'live'})
    store.enqueue('unknown',JOB_KIND,{'mode':'live','version':'unknown'})
    reconcile(cfg,store,'live')
    worker=Worker(cfg,store,llm=FakeComparison(callback=lambda:store.set_setting('sme:live',None)))
    worker.run_once()
    scan,_,results,issues=snapshot(cfg,store,'live')
    assert scan.state=='awaiting_sme' and results and not results[0].current and not issues
    assert not worker.run_once()
    assert [j['state'] for j in store.jobs('live') if j['cache_key'] in {'old','unknown'}]==['queued','queued']


def test_api_sme_auto_start_read_only_get_and_continue_guard(tmp_path):
    cfg=Config(tmp_path)
    with TestClient(create_app(cfg,start_worker=False)) as client:
        store=client.app.state.store
        seed(cfg,store,'a');seed(cfg,store,'b',exclusive=False)
        assert client.post('/api/settings/sme',json={'name':SME}).status_code==200
        before=store.jobs('live')
        for _ in range(2):
            body=client.get('/api/portfolio?as_of=2026-09-05').json()
            assert body['conflict_scan']['queued']==1 and body['as_of']=='2026-09-05' and body['events']==[]
            assert client.get('/api/conflicts/screening').status_code==200
        assert store.jobs('live')==before
        assert client.post('/api/conflicts/continue').status_code==422
        assert client.post('/api/conflicts/continue',headers={'Idempotency-Key':'00000000-0000-0000-0000-000000000001'}).status_code==409
        assert client.post('/api/conflicts/continue',headers={'Origin':'https://evil.example'}).status_code==403
        assert client.get('/api/portfolio?mode=sample').json()['conflict_scan']['total_pairs']==0


def test_multiple_periods_preserve_candidate_and_low_ocr_blocks(tmp_path):
    cfg,store,a,b,pages,hashes=pair(tmp_path,start='2027-01-01',end='2027-12-31')
    provision=a.provisions[0].model_copy(deep=True,update={'id':'extra','starts_on':'2027-01-01','ends_on':'2027-12-31'})
    # Give the additional period actual source support, not just invented structured dates.
    pages[a.id][0].spans[0].text+=' A separate grant also applies from 2027-01-01 to 2027-12-31.'
    provision.citations[0].quote=pages[a.id][0].spans[0].text
    a.provisions.append(provision)
    a.reviews.append(a.reviews[0].model_copy(update={'item_id':'extra'}))
    assert record(cfg,a,b,pages,hashes).outcome=='candidate'
    pages[a.id][0].spans[0].source='ocr';pages[a.id][0].spans[0].ocr_confidence=40
    assert record(cfg,a,b,pages,hashes).outcome=='needs_evidence'


def test_source_change_invalidates_without_get_mutations(tmp_path):
    cfg,store,a,b,pages,hashes=pair(tmp_path);store.set_setting('sme:live',SME);reconcile(cfg,store,'live')
    Worker(cfg,store,llm=FakeComparison()).run_once()
    assert snapshot(cfg,store,'live')[2][0].current
    (cfg.directory(a.id)/'pages.json').write_text('broken')
    before=store.jobs('live')
    scan,_,results,issues=snapshot(cfg,store,'live')
    assert not results[0].current and scan.unscreened==1 and not issues
    assert store.jobs('live')==before
    reconcile(cfg,store,'live')
    scan,_,results,issues=snapshot(cfg,store,'live')
    assert scan.needs_evidence==1 and issues


def test_startup_recovers_only_current_job_version(tmp_path):
    cfg,store,a,b,pages,hashes=pair(tmp_path);store.set_setting('sme:live',SME);reconcile(cfg,store,'live')
    job=store.claim(JOB_KIND,CONFLICT_VERSION)
    store.enqueue('foreign',JOB_KIND,{'version':'foreign','mode':'live'})
    foreign=store.claim(JOB_KIND,'foreign')
    worker=Worker(cfg,store,llm=FakeComparison());worker.stop_event.set()
    worker.start();worker.stop()
    jobs={j['id']:j for j in store.jobs('live')}
    assert jobs[job['id']]['state']=='queued' and jobs[foreign['id']]['state']=='running'


def test_oversize_pair_gets_local_issue_without_allowance(tmp_path):
    from backend.documents import save_pages
    cfg,store,a,b,pages,hashes=pair(tmp_path)
    pages['a'][0].spans[0].text+=' '+'x'*240001
    save_pages(cfg.directory('a')/'pages.json',pages['a'])
    store.set_setting('sme:live',SME);reconcile(cfg,store,'live')
    scan,_,results,_=snapshot(cfg,store,'live')
    assert scan.assigned==0 and results[0].status=='insufficient_evidence'
    assert 'context budget' in results[0].explanation


def test_return_to_identical_inputs_reuses_superseded_slot(tmp_path):
    cfg,store,a,b,pages,hashes=pair(tmp_path)
    store.set_setting('sme:live',SME);reconcile(cfg,store,'live')
    first=store.jobs('live')[0]
    store.set_setting('sme:live',None);reconcile(cfg,store,'live')
    assert store.jobs('live')[0]['state']=='superseded'
    store.set_setting('sme:live',SME);reconcile(cfg,store,'live')
    jobs=store.jobs('live')
    assert len(jobs)==1 and jobs[0]['id']==first['id'] and jobs[0]['state']=='queued'
    assert snapshot(cfg,store,'live')[0].assigned==1
    Worker(cfg,store,llm=FakeComparison()).run_once()
    assert snapshot(cfg,store,'live')[2][0].current


def test_conflict_routes_are_guarded_when_capability_disabled(tmp_path,monkeypatch):
    monkeypatch.setattr(CAPABILITIES,'conflicts',False)
    with TestClient(create_app(Config(tmp_path),start_worker=False)) as client:
        for method,path in [('get','/api/conflicts/screening'),('post','/api/conflicts/continue'),('post','/api/conflicts/unknown/retry')]:
            assert getattr(client,method)(path).status_code==501


def test_model_cannot_suppress_consent_or_add_uncited_dimensions(tmp_path):
    cfg,store,a,b,pages,hashes=pair(tmp_path)
    item=record(cfg,a,b,pages,hashes)
    draft=draft_for(a,b,pages)
    draft.scope_comparison['enforceability']='This is an enforceable breach.'
    clean=validate_assessment(draft,a,b,pages,item,time_comparison(a,b,pages))
    assert 'enforceability' not in clean.scope_comparison
    a.provisions[0].exceptions=['Subject to prior written consent.']
    blocked=validate_assessment(draft,a,b,pages,item,time_comparison(a,b,pages))
    assert blocked.status=='insufficient_evidence'
    assert any('consent' in fact for fact in blocked.missing_facts)


def test_extraction_completion_automatically_schedules_pair(tmp_path):
    from backend.models import Extraction,FindingDraft,SupportReview,Verdict,ModelUse
    cfg,store,a,b,pages,hashes=pair(tmp_path)
    store.set_setting('sme:live',SME)
    b.status='text_ready';b.pages_analyzed=0;store.put_document(b)
    class ExtractAndCompare(FakeComparison):
        last_use=ModelUse(provider='openrouter',requested_model='fake',model='fake-fixture',purpose='compare')
        def extract(self,document_id,chunk):
            return Extraction(title='Synthetic',parties=b.parties,provisions=b.provisions,
                findings=[FindingDraft(id='party',field='parties',value=' and '.join(b.parties),citations=b.provisions[0].citations)])
        def review(self,context,items):
            return SupportReview(verdicts=[Verdict(item_id=item['item_id'],status='supported',reason='Fixture') for item in items])
    store.enqueue('extract-b','extract',{'mode':'live','document_id':'b'})
    model=ExtractAndCompare();worker=Worker(cfg,store,llm=model)
    worker.run_once()
    scan=snapshot(cfg,store,'live')[0]
    assert scan.queued==1 and scan.assigned==1
    worker.run_once()
    result=snapshot(cfg,store,'live')[2][0]
    assert result.current and result.model_usage[0].model=='fake-fixture'


def test_eighty_document_screening_is_bounded_and_mode_isolated(tmp_path):
    cfg,store=Config(tmp_path),Store(tmp_path)
    for n in range(80):seed(cfg,store,f'd{n:02d}')
    seed(cfg,store,'sample',mode='sample')
    store.set_setting('sme:live',SME)
    reconcile(cfg,store,'live')
    scan,records,_,_=snapshot(cfg,store,'live')
    assert scan.total_pairs==3160 and len(records)==3160
    assert scan.assigned==10 and scan.queued==10 and scan.unchecked==3150
    assert len(store.jobs('live'))==10 and not store.jobs('sample')


def test_unextracted_renewal_and_uncited_low_ocr_prevent_clearance(tmp_path):
    from backend.models import Span
    cfg,store,a,b,pages,hashes=pair(tmp_path,start='2027-01-01',end='2027-12-31')
    pages['a'][0].spans.append(Span(id='a:p1:s1',document_id='a',page=1,text='The rights automatically renew annually.',bbox=[40,150,550,180],source='native'))
    assert record(cfg,a,b,pages,hashes).outcome=='candidate'
    assert all(x['overlap']=='unknown' for x in time_comparison(a,b,pages))
    pages['a'][0].spans[-1].source='ocr';pages['a'][0].spans[-1].ocr_confidence=20
    assert record(cfg,a,b,pages,hashes).outcome=='needs_evidence'


def test_malformed_model_answer_becomes_neutral_insufficient_evidence(tmp_path):
    from backend.llm import InvalidModelOutput
    cfg,store,a,b,pages,hashes=pair(tmp_path)
    store.set_setting('sme:live',SME);reconcile(cfg,store,'live')
    class Malformed:
        def compare(self,payload):raise InvalidModelOutput('invalid JSON')
    Worker(cfg,store,llm=Malformed()).run_once()
    scan,_,results,issues=snapshot(cfg,store,'live')
    assert scan.completed==1 and scan.failed==0
    assert results[0].status=='insufficient_evidence' and results[0].current and issues
    assert not results[0].model_usage and not results[0].scope_comparison
