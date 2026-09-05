"""One durable worker: local ingestion and explicitly requested extraction only."""
import json
import fcntl
import logging
import threading

from .documents import load_pages, normalize_pdf, parse_pdf, save_pages
from .models import ReviewIssue

logger = logging.getLogger(__name__)


class Interrupted(Exception):
    pass


class Worker:
    def __init__(self, config, store, llm=None):
        self.config, self.store = config, store
        self.llm = llm  # Construct a provider only inside an extraction job.
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
        from .foundation import CAPABILITIES
        if CAPABILITIES.extraction:
            self.store.recover('extract')
        if CAPABILITIES.conflicts:
            from .conflicts import JOB_KIND, CONFLICT_VERSION
            from .conflict_service import reconcile
            self.store.recover(JOB_KIND, CONFLICT_VERSION)
            for mode in ('live','sample'):
                reconcile(self.config, self.store, mode)
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
        from .foundation import CAPABILITIES
        if not job and CAPABILITIES.extraction:
            job = self.store.claim('extract')
        if not job and CAPABILITIES.conflicts:
            from .conflicts import JOB_KIND, CONFLICT_VERSION
            job = self.store.claim(JOB_KIND, CONFLICT_VERSION)
        if not job:
            return False
        try:
            if job['kind'] == 'conflict-v1':
                return self.run_conflict_job(job)
            if job['kind'] == 'extract':
                return self.run_extraction_job(job)
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
            doc.status, doc.stage, doc.error = state, message, message if state in {'failed', 'awaiting_key', 'waiting'} else None
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
            doc.stage = f'Reading page {len(pages)} of {total} locally; obligations not yet analyzed'
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
            kind='source_reading', reason_codes=['source_unreadable'], mode=doc.mode,
        ) for p in pages if p.warnings]
        doc.status = 'needs_source_review' if doc.warnings else 'text_ready'
        doc.stage = 'Local reading finished with source issues; review before extraction' if doc.warnings else 'Text ready; obligations have not been extracted'
        doc.error = None
        self.store.put_document(doc)

    def run_extraction_job(self, job):
        from .llm import ProviderUnavailable, ProviderFailure, QuotaWait
        try:
            self.extract_document(job['payload']['document_id'], visual_review=job['payload'].get('visual_review', False),
                                  visual_attempt=job['id'])
            self.store.job_state(job['id'], 'complete')
            from .conflict_service import reconcile
            try:
                reconcile(self.config, self.store, job['payload']['mode'])
            except Exception:
                logger.exception('Conflict screening failed after extraction; extraction remains complete.')
        except ProviderUnavailable as exc:
            self.store.job_state(job['id'], 'blocked', str(exc))
            self.mark_doc(job, 'awaiting_key', str(exc))
        except QuotaWait as exc:
            self.store.job_state(job['id'], 'waiting', str(exc), exc.delay)
            self.mark_doc(job, 'waiting', 'Waiting for model availability or the configured request interval.')
        except Interrupted:
            self.store.job_state(job['id'], 'queued', 'Interrupted; extraction will resume using cached responses.')
            self.mark_doc(job, 'extraction_queued', 'Interrupted; extraction will resume using cached responses.')
        except Exception as exc:
            logger.exception('Extraction job %s failed', job['id'])
            message = str(exc) if isinstance(exc, (ValueError, ProviderFailure)) else 'Extraction failed; inspect the local service logs and retry.'
            self.store.job_state(job['id'], 'failed', message)
            self.mark_doc(job, 'failed', message)
        return True

    def extract_document(self, document_id, visual_review=False, visual_attempt=None):
        """Phase 3 stage: grounded extraction and support review over already-read pages."""
        from .config import VERSION
        from .evidence import apply_extraction, stable_id
        from .llm import ModelClient, text_chunks, text_context
        from .models import Extraction, SupportReview, Verdict
        doc = self.store.document(document_id)
        if not doc:
            raise ValueError("Document no longer exists.")
        pages_path = self.config.directory(doc.id, create=False) / "pages.json"
        if pages_path.is_symlink() or not pages_path.exists():
            raise ValueError("Document pages are not available; read the document before extraction.")
        pages = load_pages(pages_path)
        if not any(p.spans for p in pages):
            raise ValueError("No legible text could be extracted. The document has not been analyzed.")
        if self.llm is None:
            self.llm = ModelClient(self.config, self.store)
        doc.model, doc.version = self.config.routing_identity, VERSION
        doc.model_usage = []
        doc.pages_analyzed = 0
        doc.status, doc.error = "extracting", None
        self.store.put_document(doc)
        if visual_review:
            from .ingestion import source_path
            from .visual_review import VisionClient, review_pages
            vision = VisionClient(self.config, self.store)
            old_source_warnings = {f'Page {p.number}: {w}' for p in pages for w in p.warnings}

            def visual_checkpoint(number):
                if self.stop_event.is_set():
                    raise Interrupted()
                doc.stage = f"Reviewing low-confidence OCR regions visually · page {number}"
                self.store.put_document(doc)

            attempt_key = 'visual-triage:' + visual_attempt if visual_attempt else None
            completed = self.store.setting(attempt_key, None) if attempt_key else None
            if completed is None:
                review_pages(source_path(self.config, doc.id, 'canonical.pdf'), pages_path, pages, vision, visual_checkpoint)
                completed = {'use': vision.last_use.model_dump() if vision.last_use else None}
                if attempt_key:
                    self.store.set_setting(attempt_key, completed)
            if completed['use']:
                from .models import ModelUse
                doc.model_usage.append(ModelUse.model_validate(completed['use']))
            # Replace only source-page warnings and issues; retain all other diagnostics.
            from .documents import LOW_OCR_WARNING
            old_source_warnings.update(f'Page {p.number}: {LOW_OCR_WARNING}' for p in pages)
            doc.warnings = [w for w in doc.warnings if w not in old_source_warnings]
            doc.warnings.extend(f'Page {p.number}: {w}' for p in pages for w in p.warnings)
            doc.issues = [i for i in doc.issues if i.kind != 'source_reading'] + [ReviewIssue(
                id=f'{doc.id}:source:{p.number}', document_ids=[doc.id], title=f'Page {p.number} needs source review',
                missing_facts=p.warnings, lawyer_question='Is there a legible complete copy of this page?',
                kind='source_reading', reason_codes=['source_unreadable'], mode=doc.mode,
            ) for p in pages if p.warnings]
            self.store.put_document(doc)
        def record_model_use():
            use = getattr(self.llm, 'last_use', None)
            if use and use not in doc.model_usage:
                doc.model_usage.append(use)
                doc.model = ', '.join(sorted({f'{u.provider}:{u.model}' for u in doc.model_usage}))
                self.store.put_document(doc)

        chunks = text_chunks(pages)
        extraction = Extraction(title=doc.filename)
        fingerprints = set()
        for n, chunk in enumerate(chunks):
            if self.stop_event.is_set():
                raise Interrupted()
            doc.stage = f"Extracting obligations · section {n+1} of {len(chunks)}"
            self.store.put_document(doc)
            part = self.llm.extract(doc.id, chunk)
            record_model_use()
            extraction.parties.extend(part.parties)
            extraction.missing_context.extend(part.missing_context)
            for category in ("findings", "deadlines", "provisions"):
                for item in getattr(part, category):
                    fingerprint = stable_id(category, json.dumps(item.model_dump(exclude={"id"}), sort_keys=True))
                    if fingerprint in fingerprints:
                        continue
                    fingerprints.add(fingerprint)
                    item.id = stable_id(doc.id, category, fingerprint)
                    getattr(extraction, category).append(item)
        extraction.parties = sorted(set(extraction.parties))
        extraction.missing_context = list(dict.fromkeys(extraction.missing_context))
        doc.stage = "Checking source support and exceptions"
        self.store.put_document(doc)
        context = text_context(pages)
        items = [*extraction.findings, *extraction.deadlines, *extraction.provisions]
        verdicts = []
        if len(context) > 240000:
            # All extraction chunks were read, but full-context support cannot be claimed.
            verdicts = [Verdict(item_id=item.id, status="uncertain",
                                reason="Full-context support review exceeds the local request budget; specialist review is needed.")
                        for item in items]
            doc.warnings.append("Full-context support review could not be completed within the request budget.")
        else:
            for start in range(0, len(items), 20):
                if self.stop_event.is_set():
                    raise Interrupted()
                review = self.llm.review(context, [{"item_id": x.id, "item": x.model_dump()} for x in items[start:start+20]])
                record_model_use()
                verdicts.extend(review.verdicts)
        doc = apply_extraction(doc, extraction, SupportReview(verdicts=verdicts), pages)
        doc.pages_analyzed = doc.pages_read if len(context) <= 240000 else 0
        doc.status = "needs_review" if doc.issues or doc.warnings else "complete"
        doc.stage = "Analysis complete; review unresolved items" if doc.status == "needs_review" else "Analysis complete"
        doc.error = None
        self.store.put_document(doc)

    def run_conflict_job(self, job):
        from .llm import ModelClient, ProviderUnavailable, ProviderFailure, QuotaWait
        from .conflict_service import process_comparison
        try:
            if self.llm is None:
                self.llm = ModelClient(self.config, self.store)
            process_comparison(self.config, self.store, job, self.llm)
        except ProviderUnavailable as exc:
            self.store.job_state(job['id'], 'blocked', str(exc))
        except QuotaWait as exc:
            self.store.job_state(job['id'], 'waiting', str(exc), exc.delay)
        except Exception as exc:
            logger.exception('Conflict comparison %s failed', job['id'])
            message = str(exc) if isinstance(exc, ProviderFailure) else 'Conflict comparison failed; retry or inspect the local service logs.'
            self.store.job_state(job['id'], 'failed', message)
        return True
