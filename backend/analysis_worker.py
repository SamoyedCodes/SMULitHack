import json
import logging
import threading
from pathlib import Path

from .conflicts import candidates, pair_id, time_comparison, validate_assessment
from .documents import load_pages, normalize_pdf, parse_pdf, save_pages
from .evidence import apply_extraction, stable_id
from .llm import ModelClient, ProviderFailure, ProviderUnavailable, QuotaWait, text_chunks, text_context
from .models import Extraction, ReviewIssue, SupportReview, Verdict

logger = logging.getLogger(__name__)


class Worker:
    def __init__(self, config, store, llm=None):
        self.config, self.store = config, store
        self.llm = llm or ModelClient(config, store)
        self.stop_event = threading.Event()
        self.thread = None

    def start(self):
        self.store.recover()
        self.thread = threading.Thread(target=self.run, name="aithena-worker", daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=3)

    def run(self):
        while not self.stop_event.is_set():
            if not self.run_once():
                self.stop_event.wait(1)

    def run_once(self):
        job = self.store.claim()
        if not job:
            return False
        try:
            if job["kind"] == "document":
                self.process_document(job["payload"]["document_id"])
            else:
                self.process_pair(job["payload"])
            self.store.job_state(job["id"], "complete")
        except ProviderUnavailable as error:
            self.store.job_state(job["id"], "blocked", str(error))
            self.mark_doc(job, "awaiting_key", str(error))
        except QuotaWait as error:
            self.store.job_state(job["id"], "waiting", str(error), error.delay)
            self.mark_doc(job, "waiting", "Waiting for model availability or the configured request interval.")
        except Exception as error:
            # Provider exceptions are already sanitized by the adapter.
            message = str(error) if isinstance(error, (ValueError, ProviderFailure)) else "Processing failed. Retry or inspect the local service logs."
            logger.exception("Job %s failed", job["id"])
            self.store.job_state(job["id"], "failed", message)
            self.mark_doc(job, "failed", message)
        return True

    def mark_doc(self, job, state, message):
        if job["kind"] == "document":
            doc = self.store.document(job["payload"]["document_id"])
            if doc:
                doc.status, doc.stage, doc.error = state, message, message
                self.store.put_document(doc)

    def process_document(self, document_id):
        doc = self.store.document(document_id)
        if not doc:
            raise ValueError("Document no longer exists.")
        directory = self.config.directory(doc.id)
        original = next(directory.glob("original.*"))
        pdf_path, pages_path = directory / "canonical.pdf", directory / "pages.json"
        doc.status, doc.error = "processing", None
        doc.stage = "Reading document pages"
        self.store.put_document(doc)
        if not pages_path.exists():
            doc.pagination = normalize_pdf(original, pdf_path)
            def progress(pages, total):
                doc.page_count = total
                doc.pages_read = sum(bool(p.spans) for p in pages)
                doc.stage = f"Reading page {len(pages)} of {total}"
                self.store.put_document(doc)
            pages = parse_pdf(pdf_path, doc.id, progress=progress)
            save_pages(pages_path, pages)
        else:
            pages = load_pages(pages_path)
        doc.page_count = len(pages)
        doc.pages_read = sum(bool(p.spans) for p in pages)
        doc.has_ocr = any(s.source == "ocr" for p in pages for s in p.spans)
        doc.warnings = [f"Page {p.number}: {w}" for p in pages for w in p.warnings]
        doc.issues = [ReviewIssue(
            id=stable_id(doc.id, "page", str(p.number)), document_ids=[doc.id],
            title=f"Page {p.number} needs source review", missing_facts=p.warnings,
            lawyer_question="Does this unreadable or uncertain page alter any obligation?",
            kind="processing", mode=doc.mode,
        ) for p in pages if p.warnings]
        self.store.put_document(doc)
        if not any(p.spans for p in pages):
            raise ValueError("No legible text could be extracted. The document has not been analyzed.")
        chunks = text_chunks(pages)
        extraction = Extraction(title=doc.filename)
        fingerprints = set()
        for n, chunk in enumerate(chunks):
            doc.stage = f"Extracting obligations · section {n+1} of {len(chunks)}"
            self.store.put_document(doc)
            part = self.llm.extract(doc.id, chunk)
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
        doc.pages_analyzed = doc.pages_read
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
                review = self.llm.review(context, [{"item_id": x.id, "item": x.model_dump()} for x in items[start:start+20]])
                verdicts.extend(review.verdicts)
        doc = apply_extraction(doc, extraction, SupportReview(verdicts=verdicts), pages)
        doc.status = "needs_review" if doc.issues or doc.warnings else "complete"
        doc.stage = "Analysis complete; review unresolved items" if doc.status == "needs_review" else "Analysis complete"
        doc.error = None
        self.store.put_document(doc)
        self.schedule_pairs(doc.mode)

    def schedule_pairs(self, mode):
        documents = [d for d in self.store.documents(mode) if d.status in ("complete", "needs_review")]
        for a, b, selected, reason in candidates(documents):
            key = pair_id(a, b)
            if selected:
                self.store.enqueue(key, "conflict", {"documents": [a.id, b.id], "mode": mode})
            else:
                self.store.set_setting("screen:" + key, {"documents": [a.id, b.id], "reason": reason, "mode": mode})

    def process_pair(self, payload):
        a, b = [self.store.document(i) for i in payload["documents"]]
        if not a or not b:
            raise ValueError("A comparison document no longer exists.")
        pages_a = load_pages(self.config.directory(a.id) / "pages.json")
        pages_b = load_pages(self.config.directory(b.id) / "pages.json")
        context_a, context_b = text_context(pages_a), text_context(pages_b)
        if len(context_a) + len(context_b) > 240000:
            from .models import ConflictDraft
            draft = ConflictDraft(
                status="insufficient_evidence", documents=[a.id, b.id], scope_comparison={},
                citations=[], exceptions=[], missing_facts=["The pair exceeds the full-context comparison budget."],
                explanation="A complete semantic comparison requires specialist review.",
                lawyer_question="Do the complete distribution agreements grant incompatible rights?",
            )
        else:
            draft = self.llm.compare({
                "documents": [
                    {"id": a.id, "provisions": [p.model_dump() for p in a.provisions], "text": context_a},
                    {"id": b.id, "provisions": [p.model_dump() for p in b.provisions], "text": context_b},
                ],
                "python_time_comparison": time_comparison(a, b),
                "scope": "Only distribution rights involving exclusivity; no assertion of actual breach.",
            })
        self.store.put_comparison(validate_assessment(draft, a, b, [*pages_a, *pages_b]))
