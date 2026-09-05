"""Phase 4 portfolio wiring: calendar projection, per-document isolation and Phase 5 preservation.

The projection is read-only. These checks assert it starts no work, writes nothing and creates no
document directories, and that one unreadable document never becomes a portfolio-wide all-clear.
"""
import json

import pytest
from fastapi.testclient import TestClient

from backend import config as settings
from backend import foundation
from backend.api import create_app
from backend.config import Config
from backend.documents import save_pages
from backend.models import Citation, DeadlineRule, Document, Page, Span, Verdict
from backend.store import Store

AS_OF = "2026-09-05"
QUOTE = "Written notice must be received sixty calendar days before expiry."


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "ROOT", tmp_path)
    monkeypatch.setattr(foundation.CAPABILITIES, "deadlines", True)
    for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "AITHENA_DATA_DIR"):
        monkeypatch.delenv(name, raising=False)


def pages(doc_id):
    return [Page(number=1, width=600, height=800, spans=[
        Span(id=f"{doc_id}:p1:s0", document_id=doc_id, page=1, text=QUOTE, bbox=[0.0, 0.0, 1.0, 1.0],
             source="native", clause="8.3")])]


def contract(doc_id="doc1", *, status="complete", rules=True):
    rule = DeadlineRule(id=f"{doc_id}-r1", label="Renewal notice", event_type="expiry", event_date="2026-12-31",
                        trigger="expiry", action="notice_received", offset=60, unit="calendar_days",
                        direction="before", citations=[Citation(document_id=doc_id, span_ids=[f"{doc_id}:p1:s0"],
                                                                quote=QUOTE)])
    return Document(id=doc_id, filename=f"{doc_id}.pdf", title=doc_id, sha256="h" + doc_id, mode="live",
                    status=status, created_at="2026-09-05T00:00:00Z", model="fake", version="1",
                    page_count=1, pages_read=1, parties=["Acme Pte Ltd"],
                    rules=[rule] if rules else [],
                    reviews=[Verdict(item_id=rule.id, status="supported", reason="ok")] if rules else [])


def workspace(tmp_path, *docs, write_pages=True):
    config, store = Config(tmp_path), Store(tmp_path)
    for doc in docs:
        store.put_document(doc, "cache-" + doc.id)
        if write_pages:
            save_pages(config.directory(doc.id) / "pages.json", pages(doc.id))
    return TestClient(create_app(config, start_worker=False))


def portfolio(client, as_of=AS_OF):
    response = client.get(f"/api/portfolio?as_of={as_of}")
    assert response.status_code == 200
    return response.json()


def test_supported_rules_become_events_within_the_horizon(tmp_path):
    with workspace(tmp_path, contract()) as client:
        body = portfolio(client)
        assert body["horizon_end"] == "2026-12-04" and len(body["events"]) == 1
        event = body["events"][0]
        assert event["action_date"] == "2026-11-01" and event["action"] == "Notice must be received"
        assert event["confidence"] == "medium" and event["evidence"][0]["page"] == 1
        assert body["coverage"]["dated"] == 1 and body["coverage"]["dates_unavailable"] == 0


def test_unreadable_pages_isolate_one_document_without_an_all_clear(tmp_path):
    config, store = Config(tmp_path), Store(tmp_path)
    good, bad = contract("good"), contract("bad")
    for doc in (good, bad):
        store.put_document(doc, "cache-" + doc.id)
    save_pages(config.directory(good.id) / "pages.json", pages(good.id))
    (config.directory(bad.id) / "pages.json").write_text("{ not json")
    with TestClient(create_app(config, start_worker=False)) as client:
        body = portfolio(client)
        assert [e["document_id"] for e in body["events"]] == ["good"]      # the healthy one still reports
        assert body["coverage"]["dates_unavailable"] == 1
        failed = [i for i in body["issues"] if i["kind"] == "deadline" and i["document_ids"] == ["bad"]]
        assert failed and "could not be read" in failed[0]["missing_facts"][0]


def test_unanalyzed_document_does_not_read_as_having_no_deadlines(tmp_path):
    with workspace(tmp_path, contract(status="extracting")) as client:
        body = portfolio(client)
        assert body["events"] == [] and body["coverage"]["undated"] == 1
        stale = [i for i in body["issues"] if i["kind"] == "deadline"]
        assert stale and "not used while the current run is incomplete" in stale[0]["missing_facts"][0]


def test_queued_document_without_rules_raises_no_issue(tmp_path):
    # A fresh 80-file workspace must not produce one review card per unprocessed document.
    with workspace(tmp_path, contract(status="queued", rules=False)) as client:
        body = portfolio(client)
        assert body["events"] == [] and not [i for i in body["issues"] if i["kind"] == "deadline"]
        assert body["coverage"]["undated"] == 1


def test_reads_are_deterministic_and_free_of_side_effects(tmp_path):
    with workspace(tmp_path, contract()) as client:
        store = client.app.state.store
        before = json.dumps(store.document("doc1").model_dump(), sort_keys=True)
        first, second = portfolio(client), portfolio(client)
        assert first == second                                            # no as-of drift, no churn
        portfolio(client, as_of="2026-10-01")
        assert json.dumps(store.document("doc1").model_dump(), sort_keys=True) == before
        assert store.jobs("live") == []                                   # a GET queues no work


def test_projection_creates_no_document_directories(tmp_path):
    config, store = Config(tmp_path), Store(tmp_path)
    store.put_document(contract(), "cache-doc1")
    with TestClient(create_app(config, start_worker=False)) as client:
        portfolio(client)
    assert not (tmp_path / "documents" / "doc1").exists()


def test_deadline_issues_are_deduplicated_by_stable_id(tmp_path):
    with workspace(tmp_path, contract(status="extracting")) as client:
        ids = [i["id"] for i in portfolio(client)["issues"]]
        assert len(ids) == len(set(ids))


def test_calendar_preserves_phase_five_comparison_records(tmp_path):
    with workspace(tmp_path, contract()) as client:
        body = portfolio(client)
        assert body["conflicts"] == [] and body["comparisons"] == {"pending": 0, "assessed": 0, "failed": 0}
        assert body["sme"] is None and body["parties"] == ["Acme Pte Ltd"]


def test_disabled_capability_produces_no_events(tmp_path, monkeypatch):
    monkeypatch.setattr(foundation.CAPABILITIES, "deadlines", False)
    with workspace(tmp_path, contract()) as client:
        body = portfolio(client)
        assert body["events"] == [] and not [i for i in body["issues"] if i["kind"] == "deadline"]
