"""Visual triage boundaries, real PDF crops and fake HTTP; no paid inference."""
import base64
import io
import json

import httpx
import pymupdf
import pytest
from PIL import Image

from backend import config as settings
from backend.config import Config
from backend.documents import LOW_OCR_WARNING, load_pages, save_pages
from backend.evidence import evidence_confidence, resolve_citations
from backend.models import Citation, Page, Span
from backend.store import Store
from backend.visual_review import VisionClient, image_data, region_crop, review_pages


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'ROOT', tmp_path)
    monkeypatch.setenv('OPENROUTER_API_KEY', 'fake-key')
    monkeypatch.setenv('OPENROUTER_VISION_MODEL', 'google/gemini-2.5-flash-lite')
    monkeypatch.setenv('AITHENA_LLM_INTERVAL', '0')
    cfg, store = Config(tmp_path), Store(tmp_path)
    directory = cfg.directory('doc')
    with pymupdf.open() as pdf:
        p = pdf.new_page(width=300, height=400)
        p.draw_rect((40, 40, 80, 80), color=(1, 0, 0), fill=(1, 0, 0))
        p.insert_text((40, 150), 'Acme Ltd - fee $100')
        pdf.save(directory / 'canonical.pdf')
    spans = [Span(id=f'doc:p1:s{i}', document_id='doc', page=1, text=t,
                  bbox=box, source='ocr', ocr_confidence=20) for i, (t, box) in enumerate([
                      ('garbled artwork', [40, 40, 80, 80]), ('Acme Ltd - fee $100', [40, 130, 200, 160])])]
    pages = [Page(number=1, width=300, height=400, spans=spans, warnings=[LOW_OCR_WARNING])]
    save_pages(directory / 'pages.json', pages)
    return cfg, store, directory, pages


def stub(monkeypatch, kind='decoration', meaningful=False, invalid=False, status=200):
    calls = []
    original_post = httpx.Client.post
    def post(self, url, **kwargs):
        if str(url).startswith('/api/'):
            return original_post(self, url, **kwargs)
        body = kwargs['json']
        calls.append(body)
        text = body['messages'][1]['content'][0]['text']
        metadata = json.loads(text.split('UNTRUSTED DOCUMENT DATA:\n', 1)[1])
        rows = [dict(span_id=r['span_id'], kind=kind, contains_meaningful_content=meaningful,
                     reason='Synthetic visual decision') for r in metadata['regions']]
        if invalid:
            rows[-1]['span_id'] = 'invented'
        return httpx.Response(status, json={'model': body['model'], 'choices': [
            {'finish_reason': 'stop', 'message': {'content': json.dumps({'regions': rows})}}]})
    monkeypatch.setattr(httpx.Client, 'post', post)
    return calls


def run(setup):
    cfg, store, directory, pages = setup
    review_pages(directory / 'canonical.pdf', directory / 'pages.json', pages,
                 VisionClient(cfg, store), lambda n: None)


def test_images_cache_and_original_evidence_are_preserved(setup, monkeypatch):
    calls = stub(monkeypatch)
    cfg, store, directory, pages = setup
    original = [s.model_dump() for s in pages[0].spans]
    run(setup)
    assert not pages[0].warnings
    assert len(pages[0].visual_reviews) == 2
    assert [s.model_dump() for s in pages[0].spans] == original
    body = calls[0]
    content = body['messages'][1]['content']
    assert len(content) == 4  # Text, full page, and two crops.
    for part in content[1:]:
        raw = base64.b64decode(part['image_url']['url'].split(',', 1)[1])
        assert Image.open(io.BytesIO(raw)).format == 'PNG'
    assert body['model'] == cfg.vision_model
    assert body['provider']['max_price'] == {'prompt': .10, 'completion': .40}
    assert not body['provider']['allow_fallbacks'] and body['max_tokens'] == 1600
    assert 'UNTRUSTED DATA' in body['messages'][0]['content']
    run(setup)
    assert len(calls) == 1  # Resume/restart uses the persistent image/prompt cache.
    evidence, errors = resolve_citations([Citation(document_id='doc', span_ids=['doc:p1:s1'], quote='fee $100')], pages, {'doc'})
    assert not errors and evidence_confidence(evidence)[0] == 'low'
    assert load_pages(directory / 'pages.json')[0].visual_reviews == pages[0].visual_reviews


@pytest.mark.parametrize('kind,meaningful', [('text', True), ('diagram', True), ('uncertain', True), ('decoration', True)])
def test_only_pure_decoration_can_reduce_warning(setup, monkeypatch, kind, meaningful):
    stub(monkeypatch, kind, meaningful)
    run(setup)
    assert LOW_OCR_WARNING in setup[3][0].warnings


@pytest.mark.parametrize('invalid,status', [(True, 200), (False, 401), (False, 400), (False, 429), (False, 503)])
def test_bad_responses_retain_source_warning_without_fallback(setup, monkeypatch, invalid, status):
    calls = stub(monkeypatch, invalid=invalid, status=status)
    run(setup)
    page = setup[3][0]
    assert LOW_OCR_WARNING in page.warnings and not page.visual_reviews
    assert 'could not be completed' in page.visual_review_note
    assert len(calls) == 1


def test_region_limit_and_other_page_warnings_are_retained(setup, monkeypatch):
    calls = stub(monkeypatch)
    page = setup[3][0]
    page.spans = [page.spans[0].model_copy(update={'id': f'doc:p1:s{i}'}) for i in range(25)]
    page.warnings.append('Referenced schedule is unreadable.')
    run(setup)
    assert len(calls) == 6 and len(page.visual_reviews) == 24
    assert len(page.warnings) == 2 and '24 flagged regions' in page.visual_review_note


@pytest.mark.parametrize('rotation', [0, 90, 180, 270])
def test_crops_follow_physical_rotated_geometry(setup, rotation):
    directory, span = setup[2], setup[3][0].spans[0]
    with pymupdf.open(directory / 'canonical.pdf') as pdf:
        page = pdf[0]
        page.set_rotation(rotation)
        span = span.model_copy(update={'bbox': list(pymupdf.Rect(span.bbox) * page.rotation_matrix)})
        data = image_data(page, region_crop(page, span))
        image = Image.open(io.BytesIO(base64.b64decode(data.split(',', 1)[1])))
        r, g, b = image.getpixel((image.width // 2, image.height // 2))
        assert r > 240 and g < 10 and b < 10


def test_api_opt_in_survives_queue_and_default_worker_never_uses_vision(setup, monkeypatch):
    from fastapi.testclient import TestClient
    from backend.api import create_app
    from backend.models import Document, Extraction, ReviewIssue
    from backend.worker import Worker
    cfg, store, directory, pages = setup
    doc = Document(id='doc', filename='source.pdf', title='source', sha256='h', mode='live',
                   status='needs_source_review', created_at='2026-09-06', model='fake', version='test',
                   page_count=1, pages_read=1, has_ocr=True, warnings=['Page 1: ' + LOW_OCR_WARNING],
                   issues=[ReviewIssue(id='doc:source:1', document_ids=['doc'], title='Page 1 needs source review',
                                       missing_facts=[LOW_OCR_WARNING], lawyer_question='Legible copy?', kind='source_reading')])
    store.put_document(doc, 'visual-test-doc')
    calls = stub(monkeypatch)
    class TextModel:
        def extract(self, *args): return Extraction(title='source')
    # Direct calls, including the evaluation runner, remain text-only by default.
    Worker(cfg, store, llm=TextModel()).extract_document('doc')
    assert not calls and store.document('doc').warnings
    with TestClient(create_app(cfg, start_worker=False)) as client:
        result = client.post('/api/extract?document_id=doc&visual_review=true')
        assert result.status_code == 202
        job = store.jobs('live')[0]
        assert job['payload']['visual_review'] is True
        assert Worker(cfg, store, llm=TextModel()).run_once()
        saved = store.document('doc')
        assert not saved.warnings and not any(i.kind == 'source_reading' for i in saved.issues)
        assert calls and saved.model_usage[0].purpose == 'VisualClassification'


@pytest.mark.parametrize('status', [200, 503])
def test_text_quota_resume_does_not_repeat_completed_visual_attempt(setup, monkeypatch, status):
    from backend.llm import QuotaWait
    from backend.models import Document, Extraction
    from backend.worker import Worker
    cfg, store, directory, pages = setup
    doc = Document(id='doc', filename='source.pdf', title='source', sha256='h', mode='live',
                   status='needs_source_review', created_at='2026-09-06', model='fake', version='test',
                   page_count=1, pages_read=1, has_ocr=True, warnings=['Page 1: ' + LOW_OCR_WARNING])
    store.put_document(doc, 'resume-test')
    store.queue_extraction('doc', 'resume-test', visual_review=True)
    calls = stub(monkeypatch, status=status)
    class TextModel:
        waiting = True
        def extract(self, *args):
            if self.waiting:
                self.waiting = False
                raise QuotaWait(10)
            return Extraction(title='source')
    text = TextModel()
    Worker(cfg, store, llm=text).run_once()
    assert store.jobs('live')[0]['state'] == 'waiting' and len(calls) == 1
    store.job_state(store.jobs('live')[0]['id'], 'queued')
    Worker(cfg, store, llm=text).run_once()
    assert store.jobs('live')[0]['state'] == 'complete' and len(calls) == 1
    if status == 503:
        assert store.document('doc').warnings
    else:
        assert store.document('doc').model_usage[0].purpose == 'VisualClassification'
