"""Evaluation invariants: entirely mocked HTTP, no live credentials or charges."""
import json
import time
from decimal import Decimal

import httpx
import pytest

from backend import config as settings
from backend.config import Config
from backend.evaluation_budget import BudgetStop, EvaluationBudget, MODEL, select_endpoint
from backend.llm import OpenRouter, InvalidModelOutput, Gemini
from backend.models import SupportReview
from backend.store import Store
from scripts.evaluate import SOURCES, verify


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'ROOT', tmp_path)
    monkeypatch.setenv('OPENROUTER_API_KEY', 'fake-evaluation-key')
    monkeypatch.setenv('OPENROUTER_MODEL', MODEL)
    monkeypatch.setenv('AITHENA_LLM_INTERVAL', '0')
    endpoint = {'tag': 'mock', 'context_length': 1000000, 'prompt': '.000001',
                'completion': '.000002', 'checked_at': time.time()}
    store = Store(tmp_path)
    budget = EvaluationBudget(store, [f'd{i}' for i in range(10)], endpoint)
    return Config(tmp_path), store, budget


def envelope(content='{"verdicts":[]}', cost=.02):
    return {'model': MODEL, 'usage': {'cost': cost},
            'choices': [{'finish_reason': 'stop', 'message': {'content': content}}]}


class HTTP:
    def __init__(self, result=None, failure=None):
        self.result, self.failure, self.calls = result or envelope(), failure, []
    def post(self, url, **kwargs):
        self.calls.append(kwargs)
        if self.failure:
            raise self.failure
        return httpx.Response(200, json=self.result)


def body(id='d0'):
    return {'model': MODEL, 'messages': [{'content': 'x\nUNTRUSTED DOCUMENT DATA:\n[document_id=' + id + ' page=1] source'}],
            'provider': {'require_parameters': True}}


def test_reserve_before_dispatch_and_replay_without_second_charge(setup):
    cfg, store, budget = setup
    class Inspect(HTTP):
        def post(self, *args, **kwargs):
            with store.connection() as db:
                assert db.execute("SELECT state FROM evaluation_requests").fetchone()['state'] == 'reserved'
            return super().post(*args, **kwargs)
    http = Inspect()
    budget.send(http, body(), cfg.openrouter_api_key)
    restarted = EvaluationBudget(store, budget.ids, budget.endpoint)
    restarted.send(http, body(), cfg.openrouter_api_key)
    assert len(http.calls) == 1 and restarted.summary()['requests'] == 1
    assert Decimal(restarted.summary()['charged_usd']) == Decimal('.02')
    sent = http.calls[0]['json']
    assert sent['provider']['allow_fallbacks'] is False and sent['max_tokens'] == 16384
    with store.connection() as db:
        assert 'fake-evaluation-key' not in str([dict(r) for r in db.execute('SELECT * FROM evaluation_requests')])


@pytest.mark.parametrize('result,failure', [({'choices': []}, None), (None, httpx.ReadTimeout('sensitive')),
    (envelope(cost='NaN'), None), (envelope(cost=-1), None), (envelope(cost=10), None)])
def test_uncertain_or_excess_charge_stops_restart(setup, result, failure):
    cfg, store, budget = setup
    http = HTTP(result, failure)
    with pytest.raises(BudgetStop):
        budget.send(http, body(), 'key')
    with pytest.raises(BudgetStop):
        EvaluationBudget(store, budget.ids, budget.endpoint).send(http, body('d1'), 'key')
    assert len(http.calls) == 1


def test_budget_never_dispatches_over_cap_or_eleventh_document(setup):
    cfg, store, budget = setup
    with store.connection() as db:
        db.execute("INSERT INTO evaluation_requests VALUES('previous','13.9','13.9','settled','{}',0)")
    http = HTTP()
    with pytest.raises(BudgetStop, match='ceiling'):
        budget.send(http, body(), 'key')
    with pytest.raises(BudgetStop, match='non-manifest'):
        budget.send(http, body('d10'), 'key')
    with pytest.raises(BudgetStop):
        EvaluationBudget(store, [str(i) for i in range(11)], budget.endpoint)
    assert not http.calls


def test_invalid_model_output_still_accounts_and_never_falls_back(setup, monkeypatch):
    cfg, store, budget = setup
    calls = []
    class Client:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, *args, **kwargs):
            calls.append(True)
            return httpx.Response(200, json=envelope('not json', .04))
    monkeypatch.setattr('backend.llm.httpx.Client', Client)
    monkeypatch.setattr(Gemini, 'request', lambda *args: pytest.fail('No Gemini fallback'))
    provider = OpenRouter(cfg, store, budget)
    for _ in range(2):
        with pytest.raises(InvalidModelOutput):
            provider.ask('review', {'text': '[document_id=d0 page=1] source'}, SupportReview)
    assert len(calls) == 1 and Decimal(budget.summary()['charged_usd']) == Decimal('.04')


def test_endpoint_requires_pricing_and_structured_output():
    with pytest.raises(BudgetStop):
        select_endpoint({'id': MODEL, 'endpoints': []})
    endpoint = {'tag': 'test', 'status': 0, 'context_length': 100000, 'max_completion_tokens': 20000,
                'supported_parameters': ['structured_outputs', 'response_format', 'max_tokens', 'reasoning'],
                'pricing': {'prompt': '.000001', 'completion': '.000002'}}
    assert select_endpoint({'id': MODEL, 'endpoints': [endpoint]})['tag'] == 'test'
    endpoint['pricing']['request'] = '.1'
    with pytest.raises(BudgetStop):
        select_endpoint({'id': MODEL, 'endpoints': [endpoint]})


def test_eleventh_manifest_document_rejected_before_workspace_read(tmp_path):
    entries = [{'source': name, 'document_id': str(i)} for i, name in enumerate(SOURCES + ['extra.pdf'])]
    (tmp_path / 'manifest.json').write_text(json.dumps({'model': MODEL, 'documents': entries}))
    with pytest.raises(ValueError, match='exactly'):
        verify(tmp_path)


def test_stopped_campaign_cannot_make_preflight_or_inference_requests(tmp_path, monkeypatch):
    from scripts import evaluate
    store = Store(tmp_path)
    store.set_setting('evaluation:stopped', 'Unaccounted charge')
    monkeypatch.setattr(evaluate, 'verify', lambda root: ({}, Config(tmp_path), store))
    monkeypatch.setattr(httpx.Client, 'get', lambda *a, **k: pytest.fail('Stopped campaign must be offline'))
    evaluate.run(tmp_path)


def test_replay_blocks_mutation_and_leaves_worker_off(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from scripts import evaluate
    cfg, store = Config(tmp_path), Store(tmp_path)
    monkeypatch.setattr(evaluate, 'verify', lambda root: ({}, cfg, store))
    with TestClient(evaluate.replay_app(tmp_path)) as client:
        assert client.get('/api/health').json()['worker'] == {'enabled': False, 'running': False}
        for route in ('/api/batches', '/api/extract', '/api/settings/sme', '/api/conflicts/continue', '/api/demo'):
            response = client.post(route, json={})
            assert response.status_code == 403
        assert not store.jobs('live')


def test_scoring_distinguishes_unreviewed_incorrect_and_unsupported_citations(tmp_path, monkeypatch):
    from scripts import evaluate
    from evaluation.scoring import score
    from backend.models import Document, Finding, Page, Span
    from backend.documents import save_pages
    from backend.store import now
    from backend.evidence import resolve_citations
    from backend.models import Citation
    cfg, store = Config(tmp_path), Store(tmp_path)
    page = Page(number=1, width=600, height=800, spans=[Span(id='d0:p1:s0', document_id='d0', page=1,
                text='Rent is S$100 per month.', bbox=[0, 0, 100, 20], source='native')])
    evidence, errors = resolve_citations([Citation(document_id='d0', span_ids=['d0:p1:s0'], quote=page.spans[0].text)], [page], {'d0'})
    assert not errors
    finding = Finding(id='f', field='payments', value='Rent is S$200 per month.', provenance='found',
                      confidence='high', confidence_reason='Incorrect test assertion', evidence=evidence)
    doc = Document(id='d0', mode='live', filename='test.pdf', title='Test', sha256='hash', created_at=now(), model='fake',
                   version='test', status='complete', findings=[finding], page_count=1, pages_read=1, pages_analyzed=1)
    save_pages(cfg.directory('d0') / 'pages.json', [page])
    key = {'review_status': 'provisional_pending_independent_review', 'documents': {'s01': {'facts': [
        {'id': 'rent', 'field': 'payments', 'answerable': True, 'expected': 'S$100 monthly'}]}}}
    evaluate.write_json(tmp_path / 'answer-key.json', key)
    manifest = {'answer_key_sha256': evaluate.digest(tmp_path / 'answer-key.json'),
                'documents': [{'sample_id': 's01', 'document_id': 'd0', 'split': 'development'}]}
    monkeypatch.setattr(evaluate, 'verify', lambda root: (manifest, cfg, store))
    evaluate.write_json(tmp_path / 'run.json', {'model': 'fake', 'budget': {'charged_usd': '0', 'unreconciled_reserved_usd': '0', 'requests': 0},
                                             'stopped': None, 'documents': [doc.model_dump()], 'contexts': {}})
    evaluate.write_json(tmp_path / 'portfolios.json', {})
    unreviewed = score(tmp_path)['groups']['all']
    assert unreviewed['field_accuracy']['rate'] is None and unreviewed['fields_unreviewed'] == 1
    judgments = json.loads((tmp_path / 'judgments-template.json').read_text())
    judgments['facts']['s01']['rent'] = {'correct': False, 'matched_findings': ['f'], 'reason': 'Wrong rent amount.'}
    judgments['findings']['s01']['f'] = {'correct': False, 'reason': 'S$200 contradicts S$100 source.'}
    evaluate.write_json(tmp_path / 'judgments.json', judgments)
    reviewed = score(tmp_path, tmp_path / 'judgments.json')['groups']['all']
    assert reviewed['citation_validity']['rate'] == 1  # Presence is not entailment.
    assert reviewed['field_accuracy']['rate'] == 0 and reviewed['answerable_coverage']['rate'] == 1
    assert reviewed['correctness_by_confidence']['high']['rate'] == 0
    assert reviewed['conflict_precision']['rate'] is None
