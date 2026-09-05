"""Phase 6 review queue and printable lawyer-brief endpoint."""
import pytest
from fastapi.testclient import TestClient

from backend import config as settings
from backend import foundation
from backend.api import create_app
from backend.config import Config
from backend.documents import save_pages
from backend.models import ConflictAssessment, Document, Evidence, Page, Span, ReviewIssue

LOCAL = {"Origin": "http://127.0.0.1:3000"}


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "ROOT", tmp_path)
    for name in ("OPENROUTER_API_KEY", "OPENROUTER_MODEL", "GEMINI_MODEL", "GEMINI_API_KEY", "GOOGLE_API_KEY",
                 "AITHENA_DATA_DIR", "AITHENA_API_PORT", "AITHENA_WEB_PORT", "AITHENA_LLM_INTERVAL"):
        monkeypatch.delenv(name, raising=False)


def evidence(document_id="doc-alpha", page=2):
    return Evidence(document_id=document_id, span_ids=[f"{document_id}:s0"], quote="exclusive distribution rights",
                    page=page, clause="4.1", boxes=[[10.0, 20.0, 30.0, 40.0]], source="native")


def seed_document(cfg, store, document_id="doc-alpha", mode="live", issues=None, readable=True):
    doc = Document(id=document_id, filename=f"{document_id}.pdf", title=f"{document_id.title()} Agreement",
                   sha256=document_id, mode=mode, created_at="2026-09-05T00:00:00Z", model="fake", version="1",
                   issues=issues or [], status="complete", page_count=2, pages_read=2, pages_analyzed=2)
    store.put_document(doc, document_id)
    if readable:
        save_pages(cfg.directory(document_id) / "pages.json", [
            Page(number=1, width=600, height=800, spans=[Span(id=f"{document_id}:cover:s0", document_id=document_id, page=1, text="Synthetic agreement cover", bbox=[10, 10, 200, 30], source="native")]),
            Page(number=2, width=600, height=800, spans=[Span(id=f"{document_id}:s0", document_id=document_id, page=2, text="exclusive distribution rights", bbox=[10, 20, 30, 40], source="native", clause="4.1")]),
        ])
    return doc


def review_issue(document_id="doc-alpha", mode="live"):
    return ReviewIssue(id="issue-1", document_ids=[document_id], title="Termination rights need review",
                       established=["A 30-day notice period is stated in clause 8."],
                       missing_facts=["The renewal schedule referenced in clause 8.2 was not supplied."],
                       lawyer_question="Does the missing schedule change the termination notice window?",
                       urgency="Confirm before the next renewal date.", evidence=[evidence(document_id)],
                       kind="uncertainty", mode=mode)


def conflict(mode="live"):
    return ConflictAssessment(id="conflict-1", status="potential_conflict", documents=["doc-alpha", "doc-beta"],
                              scope_comparison={"territory": "Both grant Singapore rights.", "product": "Both cover Model X."},
                              evidence=[evidence("doc-alpha"), evidence("doc-beta")], exceptions=["Online sales are carved out in the second agreement."],
                              missing_facts=["The effective date of the second grant is unconfirmed."],
                              explanation="Two agreements appear to grant overlapping exclusive distribution rights.",
                              lawyer_question="Can both exclusive grants coexist, or does one override the other?",
                              confidence="medium", confidence_reason="Cited wording overlaps but depends on the effective date.",
                              provenance="inferred", mode=mode)


def app_and_config(tmp_path):
    cfg = Config(tmp_path)
    return TestClient(create_app(cfg, start_worker=False)), cfg


def test_brief_disabled_when_handoff_off(tmp_path, monkeypatch):
    monkeypatch.setattr(foundation.CAPABILITIES, "handoff", False)
    c, cfg = app_and_config(tmp_path)
    with c:
        seed_document(cfg, c.app.state.store, issues=[review_issue()])
        response = c.get("/api/review/issue-1/brief")
        assert response.status_code == 501 and response.json()["error"]["code"] == "feature_not_enabled"


def test_extraction_issue_brief(tmp_path, monkeypatch):
    monkeypatch.setattr(foundation.CAPABILITIES, "handoff", True)
    c, cfg = app_and_config(tmp_path)
    with c:
        seed_document(cfg, c.app.state.store, issues=[review_issue()])
        body = c.get("/api/review/issue-1/brief").json()
        assert body["source"] == "issue" and body["title"] == "Termination rights need review"
        assert body["established"] and body["missing_facts"] and body["lawyer_question"]
        assert body["urgency"] == "Confirm before the next renewal date."
        assert body["evidence"][0]["quote"] == "exclusive distribution rights"
        assert body["documents"][0]["title"] == "Doc-Alpha Agreement"
        assert body["provenance"] == "unresolved" and body["disclaimer"]
        assert body["coverage_warnings"] == []


def test_conflict_brief(tmp_path, monkeypatch):
    monkeypatch.setattr(foundation.CAPABILITIES, "handoff", True)
    c, cfg = app_and_config(tmp_path)
    with c:
        store = c.app.state.store
        seed_document(cfg, store, "doc-alpha")
        seed_document(cfg, store, "doc-beta")
        store.put_comparison(conflict())
        body = c.get("/api/review/conflict-1/brief").json()
        assert body["source"] == "conflict" and body["kind"] == "potential_conflict"
        assert body["scope_comparison"]["territory"] and body["exceptions"]
        assert body["explanation"] and body["confidence"] == "medium"
        assert body["provenance"] == "inferred"
        assert {d["id"] for d in body["documents"]} == {"doc-alpha", "doc-beta"}
        assert len(body["evidence"]) == 2
        assert len(body["coverage_warnings"]) == 1 and "Historical comparison" in body["coverage_warnings"][0]


def test_unknown_id_is_404(tmp_path, monkeypatch):
    monkeypatch.setattr(foundation.CAPABILITIES, "handoff", True)
    c, cfg = app_and_config(tmp_path)
    with c:
        seed_document(cfg, c.app.state.store, issues=[review_issue()])
        assert c.get("/api/review/does-not-exist/brief").status_code == 404


def test_live_sample_separation(tmp_path, monkeypatch):
    monkeypatch.setattr(foundation.CAPABILITIES, "handoff", True)
    c, cfg = app_and_config(tmp_path)
    with c:
        seed_document(cfg, c.app.state.store, issues=[review_issue()])
        assert c.get("/api/review/issue-1/brief?mode=live").status_code == 200
        assert c.get("/api/review/issue-1/brief?mode=sample").status_code == 404


def test_unreadable_source_warns_without_fabricating(tmp_path, monkeypatch):
    monkeypatch.setattr(foundation.CAPABILITIES, "handoff", True)
    c, cfg = app_and_config(tmp_path)
    with c:
        # Document exists but its page checkpoint was never written (or was lost).
        seed_document(cfg, c.app.state.store, issues=[review_issue()], readable=False)
        body = c.get("/api/review/issue-1/brief").json()
        assert body["coverage_warnings"], "an unreadable cited source must surface a warning"
        # The excerpt is still shown as-is; certainty is not fabricated, but the record is preserved.
        assert body["evidence"][0]["quote"] == "exclusive distribution rights"


def test_repeated_reads_are_deterministic(tmp_path, monkeypatch):
    monkeypatch.setattr(foundation.CAPABILITIES, "handoff", True)
    c, cfg = app_and_config(tmp_path)
    with c:
        seed_document(cfg, c.app.state.store, issues=[review_issue()])
        first = c.get("/api/review/issue-1/brief").json()
        second = c.get("/api/review/issue-1/brief").json()
        first.pop("generated_at"); second.pop("generated_at")
        assert first == second
        assert c.get("/api/jobs").json() == []  # no jobs enqueued by a read
