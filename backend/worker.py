"""One ingestion-only worker per data directory. Never imports Gemini or extraction."""
import fcntl
import logging
import threading

from .documents import load_pages, normalize_pdf, parse_pdf, save_pages
from .models import ReviewIssue

logger = logging.getLogger(__name__)


class Interrupted(Exception):
    pass


class Worker:
    def __init__(self, config, store):
        self.config, self.store = config, store
        self.stop_event = threading.Event()
        self.thread = None
        self.lock = None

    @property
    def running(self):
        return bool(self.thread and self.thread.is_alive())

    def start(self):
        self.lock = (self.config.data_dir / 'ingestion-worker.lock').open('a')
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.lock.close()
            raise RuntimeError('Another ingestion worker is already using this data directory.') from None
        self.store.recover('ingestion')
        self.thread = threading.Thread(target=self.run, name='aithena-ingestion', daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=3)
        if not self.running and self.lock:
            self.lock.close()

    def run(self):
        try:
            while not self.stop_event.is_set():
                try:
                    if not self.run_once():
                        self.stop_event.wait(.5)
                except Exception:
                    logger.exception('Ingestion queue unavailable')
                    self.stop_event.wait(2)
        finally:
            if self.lock:
                self.lock.close()

    def run_once(self):
        job = self.store.claim('ingestion')
        if not job:
            return False
        try:
            self.process_document(job['payload']['document_id'])
            self.store.job_state(job['id'], 'complete')
        except Interrupted:
            self.store.job_state(job['id'], 'queued', 'Interrupted; local reading will resume.')
            self.mark_doc(job, 'queued', 'Interrupted; local reading will resume.')
        except Exception as exc:
            logger.exception('Ingestion job %s failed', job['id'])
            message = str(exc) if isinstance(exc, ValueError) else 'Local reading failed. The file may be damaged; inspect it and retry.'
            self.store.job_state(job['id'], 'failed', message)
            self.mark_doc(job, 'failed', message)
        return True

    def mark_doc(self, job, state, message):
        doc = self.store.document(job['payload']['document_id'])
        if doc:
            doc.status, doc.stage, doc.error = state, message, message if state == 'failed' else None
            self.store.put_document(doc)

    def process_document(self, document_id):
        doc = self.store.document(document_id)
        if not doc:
            raise ValueError('Document no longer exists.')
        directory = self.config.directory(doc.id, create=False)
        original = next(directory.glob('original.*'), None)
        if not original or not original.resolve().is_relative_to(directory):
            raise ValueError('Original file is unavailable.')
        pdf_path, pages_path = directory / 'canonical.pdf', directory / 'pages.json'
        if any(path.is_symlink() for path in (pdf_path, pages_path, pages_path.with_suffix('.json.tmp'))):
            raise ValueError('Invalid source cache path.')
        doc.status, doc.error, doc.stage = 'processing', None, 'Preparing pages locally'
        self.store.put_document(doc)
        doc.pagination = normalize_pdf(original, pdf_path)
        existing = []
        if pages_path.exists():
            try:
                existing = load_pages(pages_path)
            except (ValueError, OSError):
                pass  # An invalid checkpoint is reread, never treated as complete.

        def progress(pages, total):
            save_pages(pages_path, pages)
            doc.page_count, doc.pages_read = total, sum(p.status == 'read' and bool(p.spans) for p in pages)
            doc.has_ocr = any(s.source == 'ocr' for p in pages for s in p.spans)
            doc.stage = f'Reading page {len(pages)} of {total} locally; extraction is disabled'
            self.store.put_document(doc)
            if self.stop_event.is_set():
                raise Interrupted()

        if self.stop_event.is_set():
            raise Interrupted()
        pages = parse_pdf(pdf_path, doc.id, progress=progress, existing=existing)
        doc.page_count = len(pages)
        doc.pages_read = sum(p.status == 'read' and bool(p.spans) for p in pages)
        doc.has_ocr = any(s.source == 'ocr' for p in pages for s in p.spans)
        doc.warnings = [f'Page {p.number}: {w}' for p in pages for w in p.warnings]
        doc.issues = [i for i in doc.issues if i.kind != 'source_reading'] + [ReviewIssue(
            id=f'{doc.id}:source:{p.number}', document_ids=[doc.id], title=f'Page {p.number} needs source review',
            missing_facts=p.warnings, lawyer_question='Is there a legible complete copy of this page?',
            kind='source_reading', mode=doc.mode,
        ) for p in pages if p.warnings]
        doc.status = 'needs_source_review' if doc.warnings else 'text_ready'
        doc.stage = 'Local reading finished with source issues; extraction is disabled' if doc.warnings else 'Text ready; obligations have not been extracted'
        doc.error = None
        self.store.put_document(doc)
