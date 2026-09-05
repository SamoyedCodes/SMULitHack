import io
import os
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pymupdf
import pytest
from fastapi.testclient import TestClient

from backend.api import create_app
from backend.config import Config, tesseract_path, libreoffice_path
from backend.documents import load_pages, parse_pdf, save_pages
from backend.models import Document
from backend.store import Store
from backend.worker import Worker, Interrupted
from scripts.make_ingestion_fixtures import fixtures, native_pdf


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.delenv('GEMINI_API_KEY', raising=False); monkeypatch.delenv('GOOGLE_API_KEY', raising=False)
    app = create_app(Config(tmp_path), start_worker=False)
    with TestClient(app) as client:
        yield client


def upload(client, data=None, name='native.pdf', key=None):
    return client.post('/api/batches', files=[('files',(name, data if data is not None else native_pdf(),'application/octet-stream'))],
                       headers={'Idempotency-Key':key or str(uuid.uuid4())})


def worker(client):
    return Worker(client.app.state.config, client.app.state.store)


def test_batch_dedup_rejections_and_idempotent_receipt(client):
    data = native_pdf()
    files = [('files', ('native.pdf', data)), ('files', ('same.PDF', data)), ('files', ('empty.pdf',b'')), ('files',('bad.exe',b'not a document'))]
    key = str(uuid.uuid4())
    response = client.post('/api/batches', files=files, headers={'Idempotency-Key':key})
    assert response.status_code == 202
    body = response.json()
    assert body['documents'][0]['id'] == body['documents'][1]['id']
    assert body['documents'][1]['cached']
    assert all(item['error'] for item in body['documents'][2:])
    assert len(client.get('/api/jobs').json()) == 1
    again = client.post('/api/batches', files=files, headers={'Idempotency-Key':key})
    assert again.json()['id'] == body['id']
    assert upload(client, data=native_pdf('Different synthetic document'), key=key).status_code == 409
    assert client.get('/api/batches/'+body['id']).json()['documents'] == body['documents']
    assert client.get('/api/portfolio').json()['coverage']['total'] == 1


def test_upload_limits_and_atomic_count_rejection(client):
    before = client.get('/api/jobs').json()
    assert client.post('/api/batches', files=[('files',(f'{i}.pdf', b'a')) for i in range(81)]).status_code == 422
    assert client.get('/api/jobs').json() == before
    body = upload(client, b'X' * (25*1024*1024+1)).json()
    assert body['documents'][0]['id'] is None and '25 MiB' in body['documents'][0]['error']
    assert client.get('/api/jobs').json() == before


def test_native_sources_coordinates_original_and_no_llm(client):
    original = native_pdf()
    body = upload(client, original).json(); id = body['documents'][0]['id']
    assert client.get(f'/api/documents/{id}/pages').json() == []
    assert worker(client).run_once()
    doc = client.get('/api/documents/'+id).json()
    assert doc['status'] == 'text_ready' and doc['pages_analyzed'] == 0 and doc['findings'] == []
    pages = client.get(f'/api/documents/{id}/pages').json()
    assert len(pages) == doc['page_count'] == doc['pages_read'] == 1
    for span in pages[0]['spans']:
        assert span['document_id'] == id and span['page'] == 1 and span['source'] == 'native'
        x0,y0,x1,y1 = span['bbox']; assert 0 <= x0 < x1 <= pages[0]['width'] and 0 <= y0 < y1 <= pages[0]['height']
    image = client.get(f'/api/documents/{id}/pages/1/image')
    assert image.status_code == 200 and image.headers['content-type'] == 'image/png'
    assert client.get(f'/api/documents/{id}/pages/2/image').status_code == 404
    assert client.get(f'/api/documents/{id}/original').content == original
    # Phase 3 tests import Gemini during collection; isolate the ingestion-only import check.
    import subprocess
    subprocess.run([sys.executable, '-c', "from backend.worker import Worker; import sys; assert 'backend.llm' not in sys.modules and 'google.genai' not in sys.modules"], check=True)
    assert not any(client.get('/api/health').json()['capabilities'][k] for k in ['conflicts','handoff','sample_workspace'])


def test_bad_pdf_and_page_limit_are_visible_failures(client):
    for content in [b'not actually PDF', native_pdf(pages=201)]:
        id = upload(client, content).json()['documents'][0]['id']
        worker(client).run_once()
        doc = client.get('/api/documents/'+id).json()
        assert doc['status'] == 'failed' and doc['error']
        assert doc['pages_analyzed'] == 0


def test_80_file_ingestion_without_extraction(client):
    files = [('files',(f'contract-{i}.pdf',native_pdf(f'Synthetic contract number {i}. Local reading only; no legal extraction or real client data.'))) for i in range(80)]
    response = client.post('/api/batches', files=files)
    assert response.status_code == 202 and len(response.json()['documents']) == 80
    runner = worker(client)
    count = 0
    while runner.run_once(): count += 1
    assert count == 80
    docs = client.get('/api/portfolio').json()['documents']
    assert len(docs) == 80 and all(doc['status'] == 'text_ready' and doc['pages_analyzed'] == 0 for doc in docs)


def test_concurrent_duplicate_uploads(client):
    data = native_pdf()
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: upload(client, data), range(2)))
    assert all(r.status_code == 202 for r in responses)
    assert len({r.json()['documents'][0]['id'] for r in responses}) == 1
    assert len(client.get('/api/jobs').json()) == 1


def test_worker_recovers_only_ingestion_and_enforces_single_owner(client):
    upload(client)
    store = client.app.state.store
    store.claim('ingestion')
    store.enqueue('old-conflict', 'conflict', {'mode':'live','documents':['a','b']})
    old = store.claim('conflict')
    runner = worker(client); runner.start()
    try:
        with pytest.raises(RuntimeError, match='already using'):
            worker(client).start()
        deadline = time.time() + 10
        while time.time() < deadline and store.jobs('live')[0]['state'] != 'complete': time.sleep(.05)
        jobs = store.jobs('live')
        assert jobs[0]['state'] == 'complete'
        assert next(j for j in jobs if j['id'] == old['id'])['state'] == 'running'
    finally:
        runner.stop()


def test_interrupted_page_checkpoint_resumes_without_rereading_good_page(client, monkeypatch):
    id = upload(client, native_pdf(pages=3)).json()['documents'][0]['id']
    import backend.worker as module
    real_save = module.save_pages
    def interrupted(path, pages):
        real_save(path, pages)
        if len(pages) == 1:
            raise Interrupted()
    monkeypatch.setattr(module, 'save_pages', interrupted)
    runner = worker(client); runner.run_once()
    assert client.get('/api/jobs').json()[0]['state'] == 'queued'
    checkpoint = client.app.state.config.directory(id, create=False)/'pages.json'
    assert len(load_pages(checkpoint)) == 1
    monkeypatch.setattr(module, 'save_pages', real_save)
    runner.run_once()
    assert len(load_pages(checkpoint)) == 3
    assert client.get('/api/documents/'+id).json()['status'] == 'text_ready'


def test_missing_sources_do_not_create_paths_and_symlinks_are_rejected(client, tmp_path):
    for suffix in ['pages','pages/1/image','original']:
        assert client.get('/api/documents/missing/'+suffix).status_code == 404
    assert not (tmp_path/'documents').exists()
    id = upload(client).json()['documents'][0]['id']
    directory = client.app.state.config.directory(id, create=False)
    secret = tmp_path/'unrelated'; secret.write_text('private')
    original = next(directory.glob('original.*')); original.unlink(); original.symlink_to(secret)
    assert client.get(f'/api/documents/{id}/original').status_code == 404


@pytest.mark.skipif(not tesseract_path() or not libreoffice_path(), reason='Native integration requires Tesseract and LibreOffice')
def test_real_mixed_format_corpus_without_key(client):
    corpus = fixtures()
    response = client.post('/api/batches', files=[('files',(name,data)) for name,data in corpus.items()])
    assert response.status_code == 202
    runner = worker(client)
    while runner.run_once(): pass
    docs = {doc['filename']:doc for doc in client.get('/api/portfolio').json()['documents']}
    assert set(docs) == set(corpus)
    for name, doc in docs.items():
        assert doc['status'] in {'text_ready','needs_source_review'}, (name, doc['error'])
        assert doc['pages_analyzed'] == 0 and doc['findings'] == []
        pages = client.get('/api/documents/'+doc['id']+'/pages').json()
        assert len(pages) == doc['page_count']
        assert any('Synthetic' in span['text'] or 'synthetic' in span['text'] for p in pages for span in p['spans'])
        if name in ['clean-scan.pdf','degraded-scan.pdf','scan.png','scan.jpeg']:
            assert doc['has_ocr']
    assert docs['agreement.docx']['pagination'] == 'rendered'
    assert docs['mixed-pages.pdf']['page_count'] == 3 and docs['mixed-pages.pdf']['status'] == 'needs_source_review'


@pytest.mark.skipif(not tesseract_path(), reason='Requires Tesseract for retry recovery')
def test_missing_ocr_is_visible_and_retry_recovers(client, monkeypatch):
    import backend.documents as module
    real = module.tesseract_path
    id = upload(client, fixtures()['clean-scan.pdf'], 'scan.pdf').json()['documents'][0]['id']
    monkeypatch.setattr(module, 'tesseract_path', lambda:None)
    worker(client).run_once()
    doc = client.get('/api/documents/'+id).json()
    assert doc['status'] == 'needs_source_review' and doc['pages_read'] == 0
    assert any('Tesseract is missing' in warning for warning in doc['warnings'])
    monkeypatch.setattr(module, 'tesseract_path', real)
    response = client.post('/api/retry?document_id='+id)
    assert response.json()['resumed_jobs'] == 1
    assert client.post('/api/retry?document_id='+id).json()['resumed_jobs'] == 0
    worker(client).run_once()
    doc = client.get('/api/documents/'+id).json()
    assert doc['pages_read'] == 1 and doc['has_ocr']


def test_rejected_batch_history_survives_restart(client):
    response = upload(client, b'unsupported', 'bad.exe')
    id = response.json()['id']
    with TestClient(create_app(client.app.state.config, start_worker=False)) as reopened:
        latest = reopened.get('/api/batches?limit=1').json()[0]
        assert latest['id'] == id and latest['documents'][0]['error']
        assert latest['documents'][0]['id'] is None


def test_password_pdf_and_missing_converter(client, monkeypatch):
    pdf = pymupdf.open(stream=native_pdf(), filetype='pdf')
    protected = pdf.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw='owner', user_pw='password');pdf.close()
    id = upload(client, protected).json()['documents'][0]['id']; worker(client).run_once()
    assert 'Password-protected' in client.get('/api/documents/'+id).json()['error']
    import backend.documents as module
    monkeypatch.setattr(module, 'libreoffice_path', lambda:None)
    id = upload(client, fixtures()['agreement.docx'], 'agreement.docx').json()['documents'][0]['id']; worker(client).run_once()
    assert 'LibreOffice is missing' in client.get('/api/documents/'+id).json()['error']


def test_rotated_native_page_coordinates_follow_rendered_page(client):
    pdf = pymupdf.open(stream=native_pdf(), filetype='pdf');pdf[0].set_rotation(90)
    data = pdf.tobytes();pdf.close()
    id = upload(client,data).json()['documents'][0]['id'];worker(client).run_once()
    page = client.get('/api/documents/'+id+'/pages').json()[0]
    assert (page['width'],page['height']) == (792,612)
    for span in page['spans']:
        x0,y0,x1,y1 = span['bbox']
        assert 0 <= x0 < x1 <= 792 and 0 <= y0 < y1 <= 612
