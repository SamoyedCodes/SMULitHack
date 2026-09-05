"""Combined Phase 4–6 projections use the same context and never schedule inference."""
import json

import pytest
from fastapi.testclient import TestClient

from backend import config as settings
from backend.api import create_app
from backend.config import Config
from backend.conflict_service import reconcile
from backend.documents import save_pages
from backend.models import Citation, DeadlineRule, Verdict
from backend.store import Store
from backend.worker import Worker
from conflict_fixtures import FakeComparison, SME, seed
from test_portfolio_deadlines import contract, workspace
from test_review import app_and_config, review_issue, seed_document


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, 'ROOT', tmp_path)
    for key in ('OPENROUTER_API_KEY', 'GEMINI_API_KEY', 'GOOGLE_API_KEY', 'AITHENA_DATA_DIR', 'AITHENA_API_PORT', 'AITHENA_WEB_PORT'):
        monkeypatch.delenv(key, raising=False)


def combined_workspace(root):
    cfg, store = Config(root), Store(root)
    a, pages = seed(cfg, store, 'a')
    seed(cfg, store, 'b', exclusive=False)
    quote = 'The agreement expires on 2026-12-31. Notice must be received 60 calendar days before expiry. Payment is due 30 calendar days after invoice receipt.'
    pages[0].spans[0].text += ' ' + quote
    citation = Citation(document_id=a.id, span_ids=[pages[0].spans[0].id], quote=quote)
    a.rules = [
        DeadlineRule(id='notice', label='Notice before expiry', event_type='expiry', event_date='2026-12-31', trigger='expiry', action='notice_received', offset=60, citations=[citation]),
        DeadlineRule(id='invoice', label='Invoice payment', event_type='payment', trigger='invoice receipt', action='payment_due', offset=30, direction='after', citations=[citation]),
    ]
    a.reviews += [Verdict(item_id=r.id, status='supported', reason='Synthetic fixture support') for r in a.rules]
    store.put_document(a)
    save_pages(cfg.directory(a.id) / 'pages.json', pages)
    store.set_setting('sme:live', SME)
    reconcile(cfg, store, 'live')
    fake = FakeComparison()
    worker = Worker(cfg, store, llm=fake)
    while worker.run_once():
        pass
    assert fake.calls == 1
    return cfg, store


def test_combined_portfolio_briefs_aliases_history_and_read_only_budget(tmp_path):
    cfg, store = combined_workspace(tmp_path)
    with TestClient(create_app(cfg, start_worker=False)) as client:
        before_jobs = store.jobs('live')
        before_budget = store.setting('conflict-budget:live')
        body = client.get('/api/portfolio?as_of=2026-12-01').json()
        assert body['events'][0]['action_date'] == '2026-11-01' and body['events'][0]['overdue']
        assert body['events'][0]['action'] == 'Notice must be received'
        assert body['conflict_scan']['completed'] == 1
        current = [c for c in body['conflicts'] if c['current']]
        assert len(current) == 1 and current[0]['status'] == 'potential_conflict'
        assessment = current[0]
        issue = next(i for i in body['issues'] if i['kind'] == 'deadline')
        for id in (issue['id'], assessment['id'], 'conflict:' + assessment['id']):
            response = client.get(f'/api/review/{id}/brief?as_of=2026-12-01')
            assert response.status_code == 200
            brief = response.json()
            assert brief['as_of'] == body['as_of'] and not brief['coverage_warnings']
            if id != issue['id']:
                assert brief['id'] == assessment['id'] and brief['scope_comparison']
                assert {e['document_id'] for e in brief['evidence']} == {'a', 'b'}
        assert client.get('/api/portfolio?as_of=2026-12-01').json() == body
        assert store.jobs('live') == before_jobs and store.setting('conflict-budget:live') == before_budget
        assert client.get(f"/api/review/{assessment['id']}/brief?mode=sample").status_code == 404
        # External source changes must stale the assessment even without a reconcile/write.
        path = cfg.directory('a') / 'pages.json'
        saved = json.loads(path.read_text())
        saved[0]['spans'][0]['text'] += ' Additional supplied text.'
        path.write_text(json.dumps(saved))
        stale = client.get('/api/portfolio?as_of=2026-12-01').json()
        assert not any(c['current'] for c in stale['conflicts'])
        assert not any(i['kind'] == 'conflict' for i in stale['issues'])
        historical = client.get(f"/api/review/{assessment['id']}/brief").json()
        assert 'Historical comparison' in historical['coverage_warnings'][0]
        assert store.jobs('live') == before_jobs and store.setting('conflict-budget:live') == before_budget


@pytest.mark.parametrize('state', ['missing', 'corrupt', 'extracting'])
def test_every_projected_deadline_issue_resolves_to_a_brief(tmp_path, state):
    with workspace(tmp_path, contract(status='extracting' if state == 'extracting' else 'complete'), write_pages=state != 'missing') as client:
        cfg = client.app.state.config
        if state == 'corrupt':
            (cfg.directory('doc1') / 'pages.json').write_text('{ broken')
        body = client.get('/api/portfolio?as_of=2026-12-01').json()
        issues = [i for i in body['issues'] if i['kind'] == 'deadline']
        assert len(issues) == 1
        response = client.get(f"/api/review/{issues[0]['id']}/brief?as_of=2026-12-01")
        assert response.status_code == 200 and response.json()['missing_facts'] == issues[0]['missing_facts']
        assert not client.app.state.store.jobs('live')


@pytest.mark.parametrize('damage', ['corrupt', 'span', 'page', 'quote', 'boxes'])
def test_brief_revalidates_page_checkpoint_and_exact_evidence(tmp_path, damage):
    client, cfg = app_and_config(tmp_path)
    with client:
        issue = review_issue()
        if damage == 'span': issue.evidence[0].span_ids = ['absent:s0']
        if damage == 'page': issue.evidence[0].page = 1
        if damage == 'quote': issue.evidence[0].quote = 'fabricated clause'
        if damage == 'boxes': issue.evidence[0].boxes = [[0, 0, 1, 1]]
        seed_document(cfg, client.app.state.store, issues=[issue])
        if damage == 'corrupt':
            (cfg.directory('doc-alpha') / 'pages.json').write_text('{ corrupt')
        response = client.get('/api/review/issue-1/brief')
        assert response.status_code == 200 and response.json()['coverage_warnings']
        assert response.json()['provenance'] == 'unresolved'
