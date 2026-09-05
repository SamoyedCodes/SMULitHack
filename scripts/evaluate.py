"""Phase 7: prepare, freeze, run, score and replay one ten-document campaign.

Live inference is opt-in, sequential, separately stored and budgeted. No background worker.
"""
import argparse
import asyncio
import fcntl
import hashlib
import io
import json
import os
import re
import shutil
import sys
import time
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.config import Config, VERSION
from backend.documents import load_pages
from backend.evaluation_budget import BudgetStop, EvaluationBudget, MODEL, select_endpoint
from backend.llm import OpenRouter, ProviderFailure, ProviderUnavailable, QuotaWait
from backend.store import Store
from backend.worker import Worker

SOURCES = [
    'northstar.txt', 'cloud.txt', 'harbour.txt', 'studio.txt',
    'sample contact 1.pdf', 'Singapore lease agreement.pdf', 'Exhibit 10.21 - Singapore Lease.pdf',
    'Exclusive_Distribution_Rights_Agreement.pdf', 'seychelle and confident.pdf', 'seychelle and pacific.pdf',
]
DEFAULT = ROOT / 'data' / 'phase7'
AS_OF = ['2026-09-05', '2026-12-01', '2027-01-01']


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('w') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


@contextmanager
def campaign_lock(root):
    root.mkdir(parents=True, exist_ok=True)
    with (root / 'campaign.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Another evaluation or replay is using this workspace.') from None
        yield


def workspace(root):
    data = root / 'workspace'
    data.mkdir(exist_ok=True)
    return Config(data), Store(data)


def source_pages(text):
    pieces = re.split(r'--- PAGE \d+ ---', text)
    return [pieces[0].strip() + '\n\n' + pieces[1].strip(), *[x.strip() for x in pieces[2:]]]


def convert(source, output):
    """Render existing text verbatim; no additional legal content is invented."""
    import pymupdf
    from docx import Document
    from docx.shared import Pt
    pages = source_pages(source.read_text())
    if output.suffix == '.docx':
        doc = Document()
        doc.styles['Normal'].font.size = Pt(11)
        for n, text in enumerate(pages):
            if n:
                doc.add_page_break()
            for paragraph in text.split('\n\n'):
                doc.add_paragraph(paragraph)
        doc.save(output)
        return [[n + 1] for n in range(len(pages))]
    pdf = pymupdf.open()
    rendered = ['\n\n'.join(pages)] if output.suffix == '.png' else pages
    for text in rendered:
        page = pdf.new_page()
        # HTML insertion uses a Unicode font, preserving typographic source punctuation.
        from html import escape
        remaining, scale = page.insert_htmlbox(pymupdf.Rect(40, 40, 555, 800),
            '<div style="font-family:sans-serif;font-size:12pt;white-space:pre-wrap">' + escape(text) + '</div>')
        if remaining < 0 or scale < .95:
            raise ValueError('Fixture text does not fit its declared page.')
    if output.suffix == '.png':
        pdf[0].get_pixmap(matrix=pymupdf.Matrix(2, 2)).save(output)
        return [[1] for _ in pages]
    if source.stem == 'cloud':
        scan = pymupdf.open()
        for page in pdf:
            scanned = scan.new_page(width=page.rect.width, height=page.rect.height)
            scanned.insert_image(scanned.rect, stream=page.get_pixmap(matrix=pymupdf.Matrix(2, 2)).tobytes('png'))
        scan.save(output)
    else:
        pdf.save(output)
    return [[n + 1] for n in range(len(pages))]


def prepare(root):
    import pymupdf
    from fastapi import UploadFile
    from backend.ingestion import ingest
    if (root / 'manifest.json').exists():
        verify(root, frozen=False)
        print('Existing manifest verified; preparation did not overwrite it.', flush=True)
        return
    cfg, store = workspace(root)
    if store.documents('live') and not store.batch('phase7-ten-v1'):
        raise ValueError('Preparation requires an empty evaluation workspace or its own partial batch.')
    inputs = root / 'inputs'
    inputs.mkdir(exist_ok=True)
    entries = []
    for index, name in enumerate(SOURCES):
        source = ROOT / 'sample-contracts' / name
        suffix = {'northstar': '.docx', 'cloud': '.pdf', 'harbour': '.pdf', 'studio': '.png'}.get(source.stem, '.pdf')
        output = inputs / (source.stem + suffix)
        if output.exists() and source.suffix == '.txt':
            mapping = [[1], [1]] if output.suffix == '.png' else [[1], [2]]
        elif source.suffix == '.txt':
            mapping = convert(source, output)
        else:
            shutil.copyfile(source, output)
            with pymupdf.open(output) as pdf:
                mapping = [[n + 1] for n in range(len(pdf))]
        entries.append({'sample_id': f's{index + 1:02}', 'source': name, 'input': str(output.relative_to(root)),
                        'source_sha256': digest(source), 'input_sha256': digest(output),
                        'source_page_to_physical': mapping,
                        'split': 'holdout' if index >= 7 else 'development'})
    uploads = [UploadFile(filename=Path(e['input']).name, file=io.BytesIO((root / e['input']).read_bytes())) for e in entries]
    receipt = asyncio.run(ingest(uploads, cfg, store, 'phase7-ten-v1'))
    for entry, item in zip(entries, receipt.documents):
        if not item.id or item.error:
            raise ValueError('A corpus file was rejected during ingestion.')
        entry['document_id'] = item.id
    worker = Worker(cfg, store)
    for job in store.jobs('live'):
        if job['kind'] == 'ingestion' and job['state'] in {'failed', 'running'}:
            store.job_state(job['id'], 'queued')
    while job := store.claim('ingestion'):
        try:
            worker.process_document(job['payload']['document_id'])
            store.job_state(job['id'], 'complete')
        except Exception as exc:
            store.job_state(job['id'], 'failed', str(exc))
            raise
    sources = root / 'source-text'
    sources.mkdir(exist_ok=True)
    for entry in entries:
        directory = cfg.directory(entry['document_id'], create=False)
        entry['pages_sha256'] = digest(directory / 'pages.json')
        entry['canonical_sha256'] = digest(directory / 'canonical.pdf')
        pages = load_pages(directory / 'pages.json')
        (sources / (entry['sample_id'] + '.txt')).write_text('\n\n'.join(
            f'PHYSICAL PAGE {p.number}\n' + '\n'.join(s.text for s in p.spans) for p in pages))
        print(f"Read {entry['sample_id']}: {entry['source']} ({len(pages)} pages)", flush=True)
    write_json(root / 'manifest.json', {'version': 1, 'processing_version': VERSION, 'model': MODEL,
               'as_of': AS_OF, 'answer_key_sha256': None, 'documents': entries})


def verify(root, frozen=True):
    manifest = json.loads((root / 'manifest.json').read_text())
    entries = manifest['documents']
    if (len(entries) != 10 or [e['source'] for e in entries] != SOURCES or
            len({e['document_id'] for e in entries}) != 10 or manifest['model'] != MODEL):
        raise ValueError('Manifest must contain exactly the agreed ten unique source documents.')
    cfg, store = workspace(root)
    if {d.id for d in store.documents('live')} != {e['document_id'] for e in entries} or store.documents('sample'):
        raise ValueError('Workspace contains non-manifest documents.')
    for e in entries:
        source = ROOT / 'sample-contracts' / e['source']
        input_path = (root / e['input']).resolve()
        if not input_path.is_relative_to(root / 'inputs') or digest(input_path) != e['input_sha256']:
            raise ValueError('Prepared input changed or escaped the corpus directory.')
        directory = cfg.directory(e['document_id'], create=False)
        original = next(directory.glob('original.*'))
        if (digest(source) != e['source_sha256'] or digest(original) != e['input_sha256'] or
                digest(directory / 'pages.json') != e['pages_sha256'] or
                digest(directory / 'canonical.pdf') != e['canonical_sha256']):
            raise ValueError('Frozen source material changed; no inference is allowed.')
    if frozen and (not manifest.get('answer_key_sha256') or
                   digest(root / 'answer-key.json') != manifest['answer_key_sha256']):
        raise ValueError('Freeze a source-checked answer key before live inference.')
    if frozen and manifest['processing_version'] != VERSION:
        raise ValueError('Processing version changed since this campaign was prepared.')
    return manifest, cfg, store


def freeze(root, key_path):
    from backend.evidence import normalized
    manifest, cfg, store = verify(root, frozen=False)
    if manifest.get('answer_key_sha256'):
        verify(root)
        if digest(key_path) != manifest['answer_key_sha256']:
            raise ValueError('This campaign already has a different frozen answer key.')
        return
    key = json.loads(key_path.read_text())
    from backend.models import FieldName
    fields = set(FieldName)
    if key.get('review_status') != 'provisional_pending_independent_review':
        raise ValueError('The answer key must explicitly identify its provisional review status.')
    if set(key['documents']) != {e['sample_id'] for e in manifest['documents']}:
        raise ValueError('Answer key does not cover all ten samples.')
    for e in manifest['documents']:
        facts = key['documents'][e['sample_id']]['facts']
        if {f['field'] for f in facts} != fields or len({f['id'] for f in facts}) != len(facts):
            raise ValueError('Each document needs all eight fields and unique fact identifiers.')
        pages = {p.number: p for p in load_pages(cfg.directory(e['document_id']) / 'pages.json')}
        for fact in facts:
            if not fact.get('expected') or not isinstance(fact.get('answerable'), bool):
                raise ValueError('Every fact requires an expectation and answerability decision.')
            if fact['answerable'] and not fact.get('evidence'):
                raise ValueError('Answerable facts require source quotations.')
            for evidence in fact.get('evidence', []):
                page = pages.get(evidence['page'])
                if not page or not normalized(evidence['quote']) or normalized(evidence['quote']) not in normalized(' '.join(s.text for s in page.spans)):
                    raise ValueError(f"Unmatched key quotation: {e['sample_id']}/{fact['id']}")
    shutil.copyfile(key_path, root / 'answer-key.json')
    manifest['answer_key_sha256'] = digest(root / 'answer-key.json')
    write_json(root / 'manifest.json', manifest)
    print('Answer key source quotations verified and frozen before inference.', flush=True)


class PacedOpenRouter(OpenRouter):
    def ask(self, *args):
        while True:
            try:
                return super().ask(*args)
            except QuotaWait as exc:
                if exc.fallback_allowed:
                    raise  # No retry of a provider failure, even if credits remain.
                time.sleep(min(exc.delay, 30))  # Existing local pacing, not another HTTP attempt.


def snapshot_portfolios(cfg, store, root):
    from fastapi.testclient import TestClient
    from backend.api import create_app
    with TestClient(create_app(cfg, start_worker=False)) as client:
        result = {day: client.get('/api/portfolio', params={'as_of': day}).json() for day in AS_OF}
    write_json(root / 'portfolios.json', result)


def finalize_stop(root, cfg, store):
    """Repair interrupted display state locally; never retry a request to get a report."""
    reason = store.setting('evaluation:stopped')
    if not reason:
        return
    for doc in store.documents('live'):
        if doc.status == 'extracting':
            doc.status, doc.error, doc.stage = 'failed', reason, 'Evaluation stopped; extraction is incomplete'
            store.put_document(doc)
    path = root / 'run.json'
    if path.exists():
        saved = json.loads(path.read_text())
        saved['documents'] = [d.model_dump() for d in store.documents('live')]
        write_json(path, saved)
        snapshot_portfolios(cfg, store, root)


def run(root):
    import httpx
    from backend.conflict_service import reconcile, snapshot, process_comparison
    from backend.conflicts import JOB_KIND, CONFLICT_VERSION
    manifest, cfg, store = verify(root)
    if store.setting('evaluation:stopped'):
        finalize_stop(root, cfg, store)
        print('Campaign stopped with an unresolved provider/billing outcome. No network request was made.')
        raise SystemExit(2)
    if cfg.openrouter_model != MODEL or not cfg.openrouter_api_key:
        raise ValueError('Configure the agreed OPENROUTER_MODEL and OPENROUTER_API_KEY first.')
    if store.setting('evaluation:closed'):
        print('Campaign is closed; saved outputs can be scored or replayed without inference.')
        return
    with httpx.Client(timeout=30, follow_redirects=False) as http:
        response = http.get(f'https://openrouter.ai/api/v1/models/{MODEL}/endpoints')
        response.raise_for_status()
        endpoint = select_endpoint(response.json()['data'])
    old = store.setting('evaluation:endpoint')
    if old and any(old[k] != endpoint[k] for k in ('tag', 'prompt', 'completion', 'context_length')):
        raise ValueError('Endpoint or pricing changed since the first run; campaign cannot switch silently.')
    store.set_setting('evaluation:endpoint', endpoint)
    budget = EvaluationBudget(store, [e['document_id'] for e in manifest['documents']], endpoint)
    provider = PacedOpenRouter(cfg, store, budget=budget)
    worker = Worker(cfg, store, llm=provider)
    fatal = None
    try:
        for e in manifest['documents']:
            doc = store.document(e['document_id'])
            outcome = store.setting('evaluation:document:' + doc.id)
            if outcome:
                continue
            print(f"Extracting {e['sample_id']}: {doc.filename}", flush=True)
            try:
                worker.extract_document(doc.id)
                store.set_setting('evaluation:document:' + doc.id, 'complete')
            except BudgetStop:
                raise
            except (ProviderFailure, ProviderUnavailable, QuotaWait, ValueError) as exc:
                doc = store.document(doc.id)
                doc.status, doc.error, doc.stage = 'failed', str(exc), 'Evaluation extraction failed; not retried'
                store.put_document(doc)
                store.set_setting('evaluation:document:' + doc.id, 'failed')
                print(f"Incomplete {e['sample_id']}: {exc}", flush=True)
            print(json.dumps(budget.summary()), flush=True)
        # Score all relevant SME contexts, but never treat similarly named entities as aliases.
        contexts = sorted({p.grantor for d in store.documents('live') for p in d.provisions if p.grantor})
        established = {party for d in store.documents('live') for party in d.parties}
        contexts = [s for s in contexts if s in established]
        saved = store.setting('evaluation:contexts', {})
        for sme in contexts:
            if sme in saved:
                continue
            store.set_setting('sme:live', sme)
            reconcile(cfg, store, 'live')
            while job := store.claim(JOB_KIND, CONFLICT_VERSION):
                try:
                    print('Comparing for ' + sme, flush=True)
                    process_comparison(cfg, store, job, provider)
                except BudgetStop:
                    store.job_state(job['id'], 'blocked', 'Evaluation budget stopped the campaign.')
                    raise
                except (ProviderFailure, ProviderUnavailable, QuotaWait, ValueError) as exc:
                    store.job_state(job['id'], 'failed', str(exc))
            scan, screens, assessments, _ = snapshot(cfg, store, 'live')
            saved[sme] = {'scan': scan.model_dump(), 'screens': [x.model_dump() for x in screens],
                          'assessments': [x.model_dump() for x in assessments]}
            store.set_setting('evaluation:contexts', saved)
        # Leave the 2026/2027 fictional pair selected for the walkthrough when established.
        demo_sme = next((s for s in contexts if s == 'SEYCHELLE ENVIRONMENTAL PRODUCTS PTE. LTD.'),
                        contexts[0] if contexts else None)
        store.set_setting('sme:live', demo_sme)
        if demo_sme:
            reconcile(cfg, store, 'live')
        store.set_setting('evaluation:closed', True)
    except (BudgetStop, ProviderUnavailable, QuotaWait) as exc:
        fatal = str(exc)
        store.set_setting('evaluation:stopped', fatal)
        finalize_stop(root, cfg, store)
        print('CAMPAIGN STOPPED: ' + fatal, flush=True)
    finally:
        snapshot_portfolios(cfg, store, root)
        write_json(root / 'run.json', {'model': MODEL, 'endpoint': endpoint, 'budget': budget.summary(),
                   'stopped': fatal, 'documents': [d.model_dump() for d in store.documents('live')],
                   'contexts': store.setting('evaluation:contexts', {})})
    if fatal:
        raise SystemExit(2)


def replay_app(root):
    from backend.api import create_app, error
    _, cfg, store = verify(root)
    finalize_stop(root, cfg, store)
    cfg.evaluation_dir = root.resolve()
    app = create_app(cfg, start_worker=False)
    @app.middleware('http')
    async def read_only(request, call_next):
        if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
            return error(403, 'evaluation_read_only', 'Saved evaluation replay is read-only. No inference can run.')
        return await call_next(request)
    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'freeze', 'run', 'score', 'replay'])
    parser.add_argument('--root', type=Path, default=DEFAULT)
    parser.add_argument('--key', type=Path, default=ROOT / 'evaluation' / 'answer-key.json')
    parser.add_argument('--judgments', type=Path)
    parser.add_argument('--port', type=int, default=8027)
    args = parser.parse_args()
    root = args.root.expanduser().resolve()
    if root == Config().data_dir or root == ROOT:
        parser.error('Use a dedicated evaluation subdirectory, never the normal data directory.')
    with campaign_lock(root):
        if args.command == 'prepare':
            prepare(root)
        elif args.command == 'freeze':
            freeze(root, args.key.resolve())
        elif args.command == 'run':
            run(root)
        elif args.command == 'score':
            from evaluation.scoring import score
            _, cfg, store = verify(root)
            finalize_stop(root, cfg, store)
            score(root, args.judgments)
        else:
            import uvicorn
            uvicorn.run(replay_app(root), host='127.0.0.1', port=args.port)


if __name__ == '__main__':
    main()
