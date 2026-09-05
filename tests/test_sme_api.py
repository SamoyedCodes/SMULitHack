"""Phase 3 SME (established-party) selection endpoint."""
import pytest
from fastapi.testclient import TestClient

from backend import config as settings
from backend import foundation
from backend.api import create_app
from backend.config import Config

LOCAL = {"Origin": "http://127.0.0.1:3000"}


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "ROOT", tmp_path)
    for name in ("OPENROUTER_API_KEY", "OPENROUTER_MODEL", "GEMINI_MODEL", "GEMINI_API_KEY", "GOOGLE_API_KEY", "AITHENA_DATA_DIR",
                 "AITHENA_API_PORT", "AITHENA_WEB_PORT", "AITHENA_LLM_INTERVAL"):
        monkeypatch.delenv(name, raising=False)


def client(tmp_path):
    return TestClient(create_app(Config(tmp_path), start_worker=False))


def test_set_and_read_back_sme(tmp_path):
    with client(tmp_path) as c:
        from backend.models import Document
        c.app.state.store.put_document(Document(id='party-doc', filename='a.pdf', title='a', sha256='a', mode='live', created_at='2026-09-05T00:00:00Z', model='fake', version='1', parties=['Acme Pte Ltd']), 'a')
        response = c.post("/api/settings/sme", json={"name": "Acme Pte Ltd", "mode": "live"}, headers=LOCAL)
        assert response.status_code == 200 and response.json()["name"] == "Acme Pte Ltd"
        assert c.get("/api/portfolio").json()["sme"] == "Acme Pte Ltd"


def test_sme_can_be_cleared(tmp_path):
    with client(tmp_path) as c:
        c.post("/api/settings/sme", json={"name": "Acme Pte Ltd"}, headers=LOCAL)
        c.post("/api/settings/sme", json={"name": None}, headers=LOCAL)
        assert c.get("/api/portfolio").json()["sme"] is None


@pytest.mark.parametrize("body", [{}, {"name": "X", "unexpected": 1}, {"name": "X", "mode": "invalid"}])
def test_invalid_body_is_422(tmp_path, body):
    with client(tmp_path) as c:
        assert c.post("/api/settings/sme", json=body, headers=LOCAL).status_code == 422


def test_disabled_when_extraction_capability_off(tmp_path, monkeypatch):
    monkeypatch.setattr(foundation.CAPABILITIES, "extraction", False)
    with client(tmp_path) as c:
        from backend.models import Document
        c.app.state.store.put_document(Document(id='party-doc', filename='a.pdf', title='a', sha256='a', mode='live', created_at='2026-09-05T00:00:00Z', model='fake', version='1', parties=['Acme Pte Ltd']), 'a')
        response = c.post("/api/settings/sme", json={"name": "Acme Pte Ltd"}, headers=LOCAL)
        assert response.status_code == 501 and response.json()["error"]["code"] == "feature_not_enabled"
