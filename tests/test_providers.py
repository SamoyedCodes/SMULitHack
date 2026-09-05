"""HTTP/SDK are stubbed: exercise provider routing without credentials or paid requests."""
import json
from datetime import datetime, timezone
from email.utils import format_datetime

import httpx
import pytest
from fastapi.testclient import TestClient

from backend import config as settings
from backend.api import create_app
from backend.config import Config
from backend.llm import Gemini, ModelClient, OpenRouter, ProviderFailure, ProviderUnavailable, QuotaWait, retry_after
from backend.models import SupportReview
from backend.store import Store


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, 'ROOT', tmp_path)
    for name in ['OPENROUTER_API_KEY','OPENROUTER_MODEL','GEMINI_API_KEY','GOOGLE_API_KEY','GEMINI_MODEL','AITHENA_DATA_DIR','AITHENA_API_PORT','AITHENA_WEB_PORT']:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('AITHENA_LLM_INTERVAL','0')


def response(content='{"verdicts": []}', **overrides):
    return {'model':'selected/free-model', 'choices':[{'finish_reason':'stop','message':{'content':content}}], **overrides}


def stub_http(monkeypatch, body=None, code=200, headers=None, failure=None):
    calls = []
    class Client:
        def __init__(self, **kwargs):
            assert kwargs['follow_redirects'] is False
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def post(self, url, **kwargs):
            calls.append((url, kwargs))
            if failure: raise failure
            return httpx.Response(code,json=body if body is not None else response(),headers=headers)
    monkeypatch.setattr('backend.llm.httpx.Client', Client)
    return calls


def primary(tmp_path, monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY','openrouter-sentinel')
    return OpenRouter(Config(tmp_path),Store(tmp_path))


def test_primary_request_schema_cache_and_actual_model(tmp_path, monkeypatch):
    client=primary(tmp_path,monkeypatch)
    calls=stub_http(monkeypatch)
    client.ask('review', {'text':'UNTRUSTED'}, SupportReview)
    request=calls[0][1]['json']
    assert calls[0][0] == 'https://openrouter.ai/api/v1/chat/completions'
    assert request['model'] == 'openrouter/free'
    assert request['provider']['require_parameters']
    assert request['response_format']['json_schema']['strict']
    assert request['response_format']['json_schema']['schema'] == SupportReview.model_json_schema(mode='serialization')
    assert request['messages'][0]['role'] == 'system'
    assert client.last_use.model == 'selected/free-model' and not client.last_use.cached
    client.ask('review', {'text':'UNTRUSTED'}, SupportReview)
    assert len(calls)==1 and client.last_use.cached
    monkeypatch.setenv('OPENROUTER_MODEL','another/model:free')
    client.ask('review', {'text':'UNTRUSTED'}, SupportReview)
    assert len(calls)==2


def test_gemini_cache_is_not_reused_for_openrouter(tmp_path, monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY','primary')
    monkeypatch.setenv('GEMINI_API_KEY','secondary')
    config, store=Config(tmp_path), Store(tmp_path)
    monkeypatch.setattr(Gemini,'request',lambda *args: ('{"verdicts": []}','gemini-actual'))
    Gemini(config,store).ask('p',{},SupportReview)
    calls=stub_http(monkeypatch)
    ModelClient(config,store).ask('p',{},SupportReview)
    assert len(calls)==1


@pytest.mark.parametrize('status',[401,402,404,408,429,500,502,503,504])
def test_availability_failure_falls_back_and_records_reason(tmp_path, monkeypatch, status):
    monkeypatch.setenv('OPENROUTER_API_KEY','primary')
    monkeypatch.setenv('GEMINI_API_KEY','secondary')
    calls=stub_http(monkeypatch,code=status,headers={'Retry-After':'180'})
    gemini_calls=[]
    def gemini(*args):
        gemini_calls.append(True)
        return '{"verdicts": []}','gemini-actual'
    monkeypatch.setattr(Gemini,'request',gemini)
    model=ModelClient(Config(tmp_path),Store(tmp_path))
    assert model.ask('p',{},SupportReview).verdicts==[]
    assert len(calls)==len(gemini_calls)==1
    assert model.last_use.provider=='gemini' and model.last_use.fallback_reason
    if status in [408,429,500,502,503,504]:
        # Another instance/restart also honors the primary cooldown.
        ModelClient(model.primary.config,model.primary.store).ask('another',{},SupportReview)
        assert len(calls)==1


@pytest.mark.parametrize('body,status',[
    (response('not-json'),200),
    (response('{"invented": 1}'),200),
    (response(choices=[{'finish_reason':'length','message':{'content':'{"verdicts":[]}'}}]),200),
    (response(choices=[{'finish_reason':'stop','message':{'refusal':'declined','content':'{"verdicts":[]}'}}]),200),
    (response(model=None),200),
    ({'error':{'code':403,'message':'sensitive provider details'}},200),
    ({'error':{'code':400,'message':'sensitive provider details'}},400),
])
def test_bad_answers_and_policy_errors_never_fall_back(tmp_path,monkeypatch,body,status):
    monkeypatch.setenv('OPENROUTER_API_KEY','primary')
    monkeypatch.setenv('GEMINI_API_KEY','secondary')
    stub_http(monkeypatch,body=body,code=status)
    def forbidden(*args): raise AssertionError('Must not bypass a refusal or invalid output')
    monkeypatch.setattr(Gemini,'request',forbidden)
    with pytest.raises(ProviderFailure) as error:
        ModelClient(Config(tmp_path),Store(tmp_path)).ask('p',{},SupportReview)
    assert 'sensitive provider details' not in str(error.value)


def test_success_envelope_error_and_network_timeout_are_retriable(tmp_path,monkeypatch):
    client=primary(tmp_path,monkeypatch)
    stub_http(monkeypatch,body={'error':{'code':429,'message':'private'}},headers={'Retry-After':'123'})
    with pytest.raises(QuotaWait) as error: client.ask('p',{},SupportReview)
    assert error.value.delay==123
    client.store.set_setting('provider-cooldown:openrouter:openrouter/free',0)
    stub_http(monkeypatch,failure=httpx.ReadTimeout('private-key'))
    with pytest.raises(QuotaWait) as error: client.ask('p',{},SupportReview)
    assert error.value.delay==60 and 'private-key' not in str(error.value)


def test_local_pacing_waits_instead_of_switching(tmp_path,monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY','primary')
    monkeypatch.setenv('GEMINI_API_KEY','secondary')
    monkeypatch.setenv('AITHENA_LLM_INTERVAL','100')
    stub_http(monkeypatch)
    model=ModelClient(Config(tmp_path),Store(tmp_path))
    model.ask('first',{},SupportReview)
    def forbidden(*args): raise AssertionError('Local pacing must not route elsewhere')
    monkeypatch.setattr(Gemini,'request',forbidden)
    with pytest.raises(QuotaWait) as error: model.ask('second',{},SupportReview)
    assert not error.value.fallback_allowed


def test_missing_primary_key_uses_secondary_and_both_missing_block(tmp_path,monkeypatch):
    model=ModelClient(Config(tmp_path),Store(tmp_path))
    with pytest.raises(ProviderUnavailable): model.ask('p',{},SupportReview)
    monkeypatch.setenv('GEMINI_API_KEY','secondary')
    monkeypatch.setattr(Gemini,'request',lambda *args: ('{"verdicts": []}','actual'))
    model.ask('p',{},SupportReview)
    assert model.last_use.provider=='gemini'
    assert 'not configured' in model.last_use.fallback_reason


def test_primary_cooldown_without_secondary_stays_waiting(tmp_path,monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY','primary')
    stub_http(monkeypatch,code=429,headers={'Retry-After':'125'})
    with pytest.raises(QuotaWait) as error:
        ModelClient(Config(tmp_path),Store(tmp_path)).ask('p',{},SupportReview)
    assert error.value.delay==125


def test_retry_after_date_and_invalid_values(monkeypatch):
    monkeypatch.setattr('backend.llm.time.time',lambda:1000)
    stamp=format_datetime(datetime.fromtimestamp(1180,timezone.utc),usegmt=True)
    assert retry_after(stamp)==180
    assert retry_after('120')==120
    for invalid in [None,'garbage','nan','inf']: assert retry_after(invalid)==60


def test_health_reports_both_providers_without_secrets(tmp_path,monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY','openrouter-secret')
    monkeypatch.setenv('GEMINI_API_KEY','gemini-secret')
    with TestClient(create_app(Config(tmp_path),start_worker=False)) as client:
        health=client.get('/api/health')
        assert health.json()['key_configured']
        assert health.json()['model']=='openrouter/free'
        assert [p['role'] for p in health.json()['providers']]==['primary','secondary']
        assert all(p['status']=='configured_unverified' for p in health.json()['providers'])
        for route in ['/api/health','/openapi.json','/api/portfolio']:
            body=client.get(route).text
            assert 'openrouter-secret' not in body and 'gemini-secret' not in body
