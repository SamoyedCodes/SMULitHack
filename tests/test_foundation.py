import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import config as settings
from backend.api import create_app
from backend.config import Config
from backend.foundation import HealthResponse
from backend.models import Document
from backend.store import Store


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, 'ROOT', tmp_path)
    for name in ('OPENROUTER_API_KEY', 'OPENROUTER_MODEL', 'GEMINI_MODEL', 'GEMINI_API_KEY', 'GOOGLE_API_KEY', 'AITHENA_DATA_DIR', 'AITHENA_API_PORT', 'AITHENA_WEB_PORT', 'AITHENA_LLM_INTERVAL'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('TESSERACT_CMD', '/missing/tesseract')
    monkeypatch.setenv('LIBREOFFICE_CMD', '/missing/soffice')


def test_import_schema_has_no_startup_side_effect(tmp_path):
    path = tmp_path / 'never-created'
    script = "from backend.api import app; import sys; app.openapi(); assert 'backend.worker' not in sys.modules; assert 'google.genai' not in sys.modules"
    subprocess.run([sys.executable, '-c', script], check=True, env={**os.environ, 'AITHENA_DATA_DIR': str(path)})
    assert not path.exists()


def test_health_no_key_tools_optional_and_empty_portfolio(tmp_path):
    cfg = Config(tmp_path / 'data')
    assert not cfg.data_dir.exists()
    app = create_app(cfg, start_worker=False)
    assert not cfg.data_dir.exists()
    with TestClient(app) as client:
        response = client.get('/api/health')
        health = HealthResponse.model_validate(response.json())
        assert response.status_code == 200
        assert health.status == 'ready' and health.database.status == 'ready'
        assert not health.ocr_available and not health.docx_available and not health.key_configured
        assert health.capabilities.ingestion and health.capabilities.extraction and health.capabilities.handoff
        assert not any(v for k, v in health.capabilities.model_dump().items() if k not in {"ingestion", "extraction", "handoff"})
        assert not health.worker.enabled and app.state.worker is None
        portfolio = client.get('/api/portfolio?as_of=2026-09-05').json()
        assert portfolio['as_of'] == '2026-09-05' and portfolio['horizon_end'] == '2026-12-04'
        assert portfolio['sme'] is None and portfolio['documents'] == [] and portfolio['events'] == []
        assert portfolio['coverage']['total'] == 0


def test_key_is_never_exposed_or_verified(tmp_path, monkeypatch):
    key = 'sentinel-secret-not-to-serialize'
    monkeypatch.setenv('GEMINI_API_KEY', key)
    with TestClient(create_app(Config(tmp_path / 'data'))) as client:
        health = client.get('/api/health')
        assert health.json()['model_status'] == 'configured_unverified'
        assert key not in health.text
        assert key not in client.get('/openapi.json').text
        assert key not in client.get('/api/portfolio?as_of=' + key).text


def test_config_precedence_relative_paths_and_binary_override(tmp_path, monkeypatch):
    (tmp_path / '.env').write_text('GEMINI_API_KEY=from-file\nAITHENA_API_PORT=8100\nAITHENA_DATA_DIR=with spaces/data\n')
    monkeypatch.chdir('/')
    cfg = Config()
    assert cfg.data_dir == tmp_path / 'with spaces/data'
    assert cfg.api_port == 8100 and cfg.api_key == 'from-file'
    monkeypatch.setenv('GEMINI_API_KEY', 'process')
    assert cfg.api_key == 'process'
    monkeypatch.setenv('GEMINI_API_KEY', '')
    assert cfg.api_key == 'from-file'
    assert settings.tesseract_path() is None
    executable = tmp_path / 'fake tool'
    executable.write_text('unused')
    monkeypatch.setenv('TESSERACT_CMD', str(executable))
    assert settings.tesseract_path() is None
    executable.chmod(0o755)
    assert settings.tesseract_path() == str(executable)


@pytest.mark.parametrize('name,value', [('AITHENA_API_PORT','0'),('AITHENA_WEB_PORT','65536'),('AITHENA_API_PORT','abc'),('AITHENA_API_PORT','1.2'),('AITHENA_WEB_PORT','8000'),('AITHENA_LLM_INTERVAL','nan'),('AITHENA_LLM_INTERVAL','inf'),('AITHENA_LLM_INTERVAL','-1')])
def test_config_invalid(name, value, monkeypatch):
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError):
        Config()


def test_existing_documents_settings_jobs_preserved_across_restart(tmp_path):
    store = Store(tmp_path)
    doc = Document(id='saved', filename='saved.pdf', title='Saved', sha256='abc', mode='live', created_at='2026-09-05T00:00:00Z', model='draft', version='1')
    store.put_document(doc, 'cache')
    store.set_setting('sme:live', 'Saved SME')
    store.enqueue('queued', 'document', {'mode':'live', 'document_id':'saved'})
    store.enqueue('running', 'conflict', {'mode':'live', 'documents':['saved','other']})
    jobs = store.jobs('live')
    store.job_state(jobs[1]['id'], 'running')
    before = store.jobs('live')
    for _ in range(2):
        with TestClient(create_app(Config(tmp_path), start_worker=False)) as client:
            assert client.get('/api/health').status_code == 200
            portfolio = client.get('/api/portfolio').json()
            assert portfolio['documents'][0]['id'] == 'saved' and portfolio['sme'] == 'Saved SME'
            assert client.get('/api/jobs').json() == before
    assert Store(tmp_path).document('saved') == doc


@pytest.mark.parametrize('method,path', [('POST','/api/batches'),('POST','/api/batches/'),('POST','/api/retry'),('POST','/api/demo'),('POST','/api/settings/sme'),('GET','/api/documents/missing/pages'),('GET','/api/documents/missing/pages/1/image'),('GET','/api/documents/missing/original'),('GET','/api/review/missing/brief')])
def test_disabled_routes_do_not_mutate(tmp_path, method, path, monkeypatch):
    from backend.foundation import CAPABILITIES
    monkeypatch.setattr(CAPABILITIES, "ingestion", False)
    monkeypatch.setattr(CAPABILITIES, "extraction", False)
    monkeypatch.setattr(CAPABILITIES, "handoff", False)
    with TestClient(create_app(Config(tmp_path), start_worker=False)) as client:
        response = client.request(method, path, content=b'not-even-a-valid-upload')
        assert response.status_code == 501 and response.json()['error']['code'] == 'feature_not_enabled'
        assert client.get('/api/jobs').json() == []
        assert client.get('/api/portfolio').json()['documents'] == []
        assert not (tmp_path / 'documents').exists()


def test_missing_validation_origin_and_runtime_database_failure(tmp_path, monkeypatch):
    app = create_app(Config(tmp_path), start_worker=False)
    with TestClient(app, raise_server_exceptions=False) as client:
        for route in ('/api/documents/missing','/api/batches/missing','/api/unknown'):
            response = client.get(route)
            assert response.status_code == 404 and response.json()['error']['code'] == 'not_found'
        response = client.get('/api/portfolio?as_of=not-a-date')
        assert response.status_code == 422 and 'not-a-date' not in response.text
        assert client.post('/api/demo', headers={'Origin':'https://example.com'}).status_code == 403
        assert client.post('/api/demo', headers={'Origin':'http://127.0.0.1:3000'}).status_code == 501
        def broken():
            raise sqlite3.OperationalError('private-path/sentinel')
        monkeypatch.setattr(app.state.store, 'connection', broken)
        response = client.get('/api/health')
        assert response.status_code == 503 and response.json()['database']['status'] == 'unavailable'
        response = client.get('/api/portfolio')
        assert response.status_code == 500 and 'sentinel' not in response.text
