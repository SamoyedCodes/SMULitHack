"""Phase 3 worker extraction stage and provider adapter, exercised with a fake model.
No live Gemini call: key/quota failures must surface on the document; no silent truncation."""
import pytest

from backend import config as settings
from backend.config import Config
from backend.documents import save_pages
from backend.llm import Gemini, ProviderUnavailable, QuotaWait
from backend.models import (
    Citation, Extraction, FieldName, FindingDraft, Page, Span, SupportReview, Verdict,
)
from backend.store import Store
from backend.worker import Worker

DOC = "docA"


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "ROOT", tmp_path)
    for name in ("OPENROUTER_API_KEY", "OPENROUTER_MODEL", "GEMINI_MODEL", "GEMINI_API_KEY", "GOOGLE_API_KEY", "AITHENA_DATA_DIR",
                 "AITHENA_API_PORT", "AITHENA_WEB_PORT", "AITHENA_LLM_INTERVAL"):
        monkeypatch.delenv(name, raising=False)


def _span(page, n, text):
    return Span(id=f"{DOC}:p{page}:s{n}", document_id=DOC, page=page, text=text,
                bbox=[0.0, 0.0, 1.0, 1.0], source="native")


def _pages(text="This Agreement is between Acme Pte Ltd and Beta LLC."):
    return [Page(number=1, width=600, height=800, spans=[_span(1, 0, text)])]


def _extraction():
    return Extraction(title="Acme", parties=["Acme Pte Ltd"], findings=[
        FindingDraft(id="local", field=FieldName.PARTIES, value="Acme Pte Ltd and Beta LLC",
                     citations=[Citation(document_id=DOC, span_ids=[f"{DOC}:p1:s0"],
                                         quote="Acme Pte Ltd and Beta LLC")]),
    ])


class FakeLLM:
    """Stands in for Gemini. review() echoes 'supported' for whatever item ids the worker sends,
    since the worker rewrites extraction item ids before the review pass."""
    def __init__(self, extraction=None, extract_error=None, status="supported"):
        self.extraction = extraction or _extraction()
        self.extract_error = extract_error
        self.status = status
        self.extract_calls = self.review_calls = 0

    def extract(self, document_id, context):
        self.extract_calls += 1
        if self.extract_error:
            raise self.extract_error
        return self.extraction.model_copy(deep=True)

    def review(self, context, items):
        self.review_calls += 1
        return SupportReview(verdicts=[Verdict(item_id=i["item_id"], status=self.status, reason="ok") for i in items])


def _seed(store, config, pages=None):
    from backend.models import Document
    doc = Document(id=DOC, filename="acme.pdf", title="Acme", sha256="h", mode="live",
                   status="read", created_at="2026-09-05T00:00:00Z", model="fake", version="1",
                   page_count=1, pages_read=1)
    store.put_document(doc, "cache-" + DOC)
    save_pages(config.directory(DOC) / "pages.json", pages or _pages())
    return doc


def _run_extract_job(store, worker):
    store.enqueue("extract:" + DOC, "extract", {"document_id": DOC, "mode": "live"})
    worker.run_once()


def test_extraction_produces_grounded_findings(tmp_path):
    config, store = Config(tmp_path), Store(tmp_path)
    _seed(store, config)
    llm = FakeLLM()
    _run_extract_job(store, Worker(config, store, llm=llm))
    doc = store.document(DOC)
    parties = next(f for f in doc.findings if f.field == FieldName.PARTIES)
    assert parties.provenance == "found" and parties.value and parties.evidence
    assert {f.field for f in doc.findings} == set(FieldName)  # all eight always represented
    assert doc.status == "needs_review"  # unestablished fields raise review issues
    assert doc.parties == ["Acme Pte Ltd"] and llm.review_calls == 1


def test_legacy_and_conflict_jobs_are_never_claimed(tmp_path):
    config, store = Config(tmp_path), Store(tmp_path)
    _seed(store, config)
    for kind in ['document', 'conflict']:
        store.enqueue(kind, kind, {'document_id': DOC, 'mode':'live'})
    llm = FakeLLM()
    assert not Worker(config, store, llm=llm).run_once()
    assert all(j['state'] == 'queued' for j in store.jobs('live'))
    assert llm.extract_calls == 0


def test_missing_key_surfaces_awaiting_key(tmp_path):
    config, store = Config(tmp_path), Store(tmp_path)
    _seed(store, config)
    _run_extract_job(store, Worker(config, store, llm=FakeLLM(extract_error=ProviderUnavailable("add key"))))
    doc = store.document(DOC)
    assert doc.status == "awaiting_key" and doc.error
    assert store.jobs("live")[0]["state"] == "blocked"


def test_quota_surfaces_waiting(tmp_path):
    config, store = Config(tmp_path), Store(tmp_path)
    _seed(store, config)
    _run_extract_job(store, Worker(config, store, llm=FakeLLM(extract_error=QuotaWait(30))))
    doc = store.document(DOC)
    assert doc.status == "waiting"
    assert store.jobs("live")[0]["state"] == "waiting"


def test_oversized_context_skips_review_without_silent_truncation(tmp_path):
    config, store = Config(tmp_path), Store(tmp_path)
    _seed(store, config, pages=_pages("Acme Pte Ltd and Beta LLC " + "x" * 250000))
    llm = FakeLLM()
    _run_extract_job(store, Worker(config, store, llm=llm))
    doc = store.document(DOC)
    assert llm.review_calls == 0  # full-context review not attempted
    assert any("support review could not be completed" in w for w in doc.warnings)
    assert doc.status == "needs_review"


# --- provider adapter caching --------------------------------------------------

def test_ask_caches_and_avoids_second_model_call(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setenv("AITHENA_LLM_INTERVAL", "0")
    config, store = Config(tmp_path), Store(tmp_path)
    calls = {"n": 0}

    class FakeResp:
        text = '{"verdicts": []}'

    class FakeModels:
        def generate_content(self, **kw):
            calls["n"] += 1
            return FakeResp()

    class FakeClient:
        def __init__(self, **kw):
            self.models = FakeModels()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr("backend.llm.genai.Client", FakeClient)
    gemini = Gemini(config, store)
    first = gemini.ask("purpose", {"x": 1}, SupportReview)
    second = gemini.ask("purpose", {"x": 1}, SupportReview)
    assert calls["n"] == 1 and first == second


def test_explicit_api_extraction_is_idempotent_and_keeps_quota_delay(tmp_path):
    from fastapi.testclient import TestClient
    from backend.api import create_app
    config = Config(tmp_path)
    with TestClient(create_app(config, start_worker=False)) as client:
        store = client.app.state.store
        _seed(store, config)
        for expected in [1, 0]:
            response = client.post('/api/extract?document_id=' + DOC)
            assert response.status_code == 202 and response.json()['resumed_jobs'] == expected
        Worker(config, store, llm=FakeLLM(extract_error=QuotaWait(123))).run_once()
        before = store.jobs('live')[0]
        assert client.post('/api/extract?document_id=' + DOC).json()['resumed_jobs'] == 0
        assert store.jobs('live')[0]['next_run'] == before['next_run']
        store.job_state(before['id'], 'blocked')
        assert client.post('/api/extract?document_id=' + DOC).json()['resumed_jobs'] == 1
        Worker(config, store, llm=FakeLLM()).run_once()
        assert client.post('/api/extract?document_id=' + DOC).json()['resumed_jobs'] == 0
        assert len(store.jobs('live')) == 1
        assert client.post('/api/retry?document_id=' + DOC).json()['resumed_jobs'] == 0
        assert client.post('/api/settings/sme', json={'name':'Ghost'}).status_code == 422
        assert client.post('/api/settings/sme', json={'name':'Acme Pte Ltd'}).status_code == 200
        assert client.post('/api/settings/sme', json={'name':'Acme Pte Ltd','mode':'sample'}).status_code == 422


def test_extraction_recovery_is_explicit_and_capability_gated(tmp_path, monkeypatch):
    from backend.foundation import CAPABILITIES
    config, store = Config(tmp_path), Store(tmp_path)
    _seed(store, config)
    store.enqueue('ex', 'extract', {'document_id': DOC, 'mode':'live'})
    monkeypatch.setattr(CAPABILITIES, 'extraction', False)
    assert not Worker(config, store, llm=FakeLLM()).run_once()
    monkeypatch.setattr(CAPABILITIES, 'extraction', True)
    job = store.claim('extract')
    store.recover('extract')
    assert store.jobs('live')[0]['state'] == 'queued'
    assert Worker(config, store, llm=FakeLLM()).run_once()
    assert store.jobs('live')[0]['state'] == 'complete'


def test_worker_persists_secondary_provider_and_model_metadata(tmp_path, monkeypatch):
    from backend.llm import ModelClient, OpenRouter
    monkeypatch.setenv('OPENROUTER_API_KEY', 'primary')
    monkeypatch.setenv('GEMINI_API_KEY', 'secondary')
    monkeypatch.setenv('AITHENA_LLM_INTERVAL', '0')
    config, store = Config(tmp_path), Store(tmp_path)
    _seed(store, config)
    fake = FakeLLM()
    def unavailable(*args):
        raise ProviderUnavailable('OpenRouter access unavailable (HTTP 401).')
    def secondary(self, purpose, serialized, schema):
        data = __import__('json').loads(serialized)
        result = fake.extract(DOC, data['text']) if schema is Extraction else fake.review(data['complete_document_text'], data['items'])
        return result.model_dump_json(), 'gemini-actual-version'
    monkeypatch.setattr(OpenRouter, 'request', unavailable)
    monkeypatch.setattr(Gemini, 'request', secondary)
    _run_extract_job(store, Worker(config, store, llm=ModelClient(config, store)))
    doc = store.document(DOC)
    assert doc.status == 'needs_review'
    assert {use.purpose for use in doc.model_usage} == {'Extraction', 'SupportReview'}
    assert all(use.provider == 'gemini' and '401' in use.fallback_reason for use in doc.model_usage)
    assert doc.model == 'gemini:gemini-actual-version'
    assert all(f.evidence for f in doc.findings if f.provenance == 'found')
