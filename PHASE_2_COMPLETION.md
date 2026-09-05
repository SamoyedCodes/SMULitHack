# Phase 2 completion — local ingestion and source viewing

Implemented against the corrected `SMULitHack` repository on 5 September 2026. Existing frontend stack/design and canonical domain records were retained. No new dependency was added. User changes to `.env.example` and unrelated `.claude/` files were preserved.

## Delivered

- Multiple-file upload, native folder selection and file drag/drop; limits of 80 files, 25 MiB/file and 200 pages/document.
- Original bytes and SHA-256 hashes retained; versioned ingestion deduplication independent of Gemini configuration; typed, persisted batch receipts with individual rejection/duplicate details and idempotent acknowledgement recovery.
- One ingestion-only worker per data directory with an exclusive process lock. Only ingestion jobs are recovered/claimed; old document/conflict jobs remain idle. No inference adapter is imported.
- Native PDF extraction, actual Tesseract OCR, PNG/JPEG processing and LibreOffice DOCX conversion. Every physical page is represented, including blank/error pages; low-quality OCR is flagged.
- Atomic page checkpoints and explicit source-reading retries. Good saved pages are reused; uncertain/error pages are reread.
- Live document library/progress, physical page image/transcription viewer, selected source-coordinate highlights, original download and rendered-pagination labels for DOCX.
- Canonical typed batch/job/source responses, regenerated OpenAPI/TypeScript, runtime response validation, updated guidance and a Phase 3 handoff.

Only ingestion is enabled. New files retain `pages_analyzed=0` and no extracted findings. `text_ready` means text is available, not that legal obligations have been determined.

## Verification

| Check | Result |
|---|---|
| Backend tests | **37 passed** |
| Frontend tests | **25 passed** |
| TypeScript, production build, OpenAPI/fixture/type drift checks | Passed |
| Native PDFs and rotated-page coordinates | Passed |
| Real clean/degraded scanned PDFs, PNG, JPEG, DOCX, mixed and blank pages | Passed using installed Tesseract/LibreOffice |
| 80-file ingestion load | 80 distinct documents uploaded and locally read; zero extraction |
| Duplicate/concurrent uploads, stable upload-key retry and rejected receipt persistence | Passed |
| Malformed, password-protected, oversized, unsupported and empty files | Visible failure/rejection checks passed |
| Missing converter/OCR, source retry and interrupted page checkpoint recovery | Passed |
| Source path confinement, missing-resource reads and original-byte preservation | Passed |
| Browser file upload | Native PDF, actual scanned PDF and DOCX accepted and read |
| Browser folder upload | Seven files selected; three previously uploaded files reused as duplicates |
| Browser source viewer | OCR selection visibly highlighted the matching notice text; DOCX rendered-pagination label shown |
| Browser mixed-page viewing | Page 3 stayed visibly unreadable/blank; not omitted |
| Mobile source layout | Checked at 390 × 844 |

Tests run with provider keys unset; the test process asserts that neither the Gemini adapter nor `google.genai` was imported. Native conversion required execution outside the tooling sandbox; the unrestricted local test passed. Dependency deprecation warnings remain from Starlette/httpx and PyMuPDF; no test failed or was skipped in the final native suite.

Environment: macOS, Python 3.12.14, Node 24.19.0, pnpm 11.19.0. Browser integration used loopback ports 3002/8002. Linux, Node 22 and exact 200% zoom were not separately verified. The automatic interruption test exercises saved-page recovery rather than a timed operating-system power-loss test. Upload file drag/drop uses the same handler as selection but was not separately exercised in the browser.

A crash before the upload database transaction commits can leave an unreferenced original file. No receipt/job is acknowledged without its original; automatic deletion of orphan files is not implemented. Blank or low-confidence pages intentionally require source review. Current OCR/limits target the agreed English local corpus, not arbitrary-language or unlimited-size documents.

No extraction accuracy, legal confidence calibration, deadline accuracy, semantic conflict result, live Gemini access/quota, lawyer brief or hosted deployment is claimed. Those remain later checkpoints.

Next: `docs/PHASE_3_HANDOFF.md`. Start Phase 3 only when requested.
