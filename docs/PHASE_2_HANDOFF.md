# Phase 2 implemented: ingestion and sources

Phase 2 was continued in this repository. See `PHASE_2_COMPLETION.md` for results and limits. The next checkpoint is described in `PHASE_3_HANDOFF.md`.

Current implementation:

- Multiple files, folder selection and file drag/drop share `POST /api/batches` (`files`, max 80, 25 MiB per file).
- Originals/hashes are preserved, byte-identical documents are reused, and each batch has a durable receipt with per-file rejection/duplicate details. A UUID `Idempotency-Key` recovers the same receipt after a lost response. Latest receipts survive browser session loss via `GET /api/batches`.
- One local worker claims only ingestion jobs; it never imports an LLM adapter. Tesseract handles scans, LibreOffice handles DOCX, and PyMuPDF produces page text/images. A process lock prevents two ingestion workers using the same data directory.
- Atomic page checkpoints resume interrupted reading. Retry source issues explicitly with `POST /api/retry?document_id=...`. Existing analysis/comparison jobs are not recovered or claimed.
- The source viewer renders actual physical pages, selectable text blocks and coordinate highlights. Source warnings and OCR reading confidence remain visible; DOCX pagination is labelled rendered.
- Only `CAPABILITIES.ingestion` is enabled. Source readiness does not mean legal extraction has occurred. `pages_analyzed` remains zero for new ingestion documents.

The original coupled worker is retained as `backend/analysis_worker.py` for review in Phase 3; it is not imported or started. Do not start that draft or use the legacy sample dashboard as a live data adapter.
