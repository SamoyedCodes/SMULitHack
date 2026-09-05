# Phase 3 — grounded extraction (checkpoint notes)

Built on branch `worktree-phase-3-extraction`, branched from `main` (`1f352ea`), **while Phase 2
(ingestion) is being built concurrently by another agent**. This branch does not contain that
agent's in-progress ingestion work; it must be reconciled at merge (see "Merge notes").

## Implemented

- **Two-stage worker** (`backend/worker.py`): `process_document` was split into `read_document`
  (Phase 2 stage — render/persist pages, then enqueue an `extract` job; constructs no model client
  and needs no key) and `extract_document` (Phase 3 stage — chunked extraction, batched support
  review, `apply_extraction`, over already-read `pages.json`). `run_once` dispatches
  `document` → read, `extract` → extract, else → pair. `mark_doc` now surfaces failure/blocking on
  both read and extract jobs. Cross-contract pair scheduling stays gated behind `CAPABILITIES.conflicts`
  (Phase 5), so extraction never fires premature comparison calls.
- **Capability**: `CAPABILITIES = Capabilities(extraction=True)` (`backend/foundation.py`).
  `ingestion` and later flags remain owned by their phases.
- **SME selection endpoint**: real `POST /api/settings/sme` (`backend/api.py`) persisting
  `sme:{mode}` via the existing settings store; the existing middleware gates it on the extraction
  capability. `GET /api/portfolio.sme` reads it back.
- **Frontend** (`frontend/src/App.tsx`, `api.ts`): the Contracts tab renders per-document findings
  for all eight fields with value, party, provenance badge, confidence badge + reason, and evidence
  (quote, page, clause, OCR marker); unresolved/missing fields shown honestly. An SME selector
  (dropdown of `portfolio.parties`) posts to `/api/settings/sme`; the sidebar shows the chosen SME.
  Both appear only when `health.capabilities.extraction` is true.
- **Generated contracts**: `shared/openapi.json` and `shared/api.generated.ts` regenerated; both
  drift checks pass and now include the SME route and the extraction records.

The extraction/citation/confidence *logic itself* was already drafted in `backend/llm.py` and
`backend/evidence.py`; Phase 3 decoupled, enabled, wired, and — the main new value — **certified** it.

## Checks actually run (this environment)

| Check | Result |
|---|---|
| `pytest` (backend + new Phase 3 suites) | 46 passed |
| `backend/foundation.py` no-startup-side-effect (no worker/genai import on schema export) | passed |
| `tsc -b` (frontend typecheck) | passed |
| `scripts/export_openapi.py --check` | in sync |
| `frontend api:generate` + `--check` (type drift) | in sync |

New tests: `tests/test_extraction.py` (citation validation edge cases, confidence bands,
`apply_extraction` provenance/completeness/party-filtering/incomplete-page downgrade),
`tests/test_worker_extraction.py` (read→extract enqueue, grounded findings, `awaiting_key`/`waiting`
visibility, >240k-context guard with no silent truncation, provider-adapter caching),
`tests/test_sme_api.py` (set/read-back/clear, 422 on invalid body, 501 when capability off).

## Limits and remaining checks (do not overstate)

- **No live model run.** All extraction tests use a fake LLM over synthetic `Page`/`Span` fixtures.
  Gemini model access, `gemini-3.8-flash` availability, and free-tier quota remain **unverified**;
  true extraction/citation accuracy is **not** measured (that is Phase 7 evaluation).
- **No end-to-end with real ingestion.** The `read` stage's PDF/OCR/DOCX path (PyMuPDF/Tesseract/
  LibreOffice) is Phase 2's and is not exercised here beyond the enqueue wiring; a full
  ingest → extract run needs the merged Phase 2 pipeline and real documents.
- **Frontend runtime not run here.** `vitest` and `vite build` could not execute in this sandbox
  (no compatible Node: only an embedded Node whose signature cannot load rollup's native binary).
  Typecheck and type/schema drift pass. Run `pnpm --dir frontend test` and `pnpm --dir frontend build`
  in a normal shell to confirm.

## Merge notes

`worker.py`, `api.py`, `foundation.py`, and `App.tsx` are also edited by the concurrent Phase 2
agent. The split-worker design keeps the extraction stage additive over their reading stage; the
merge work is aligning the reading half and the `document` → `extract` enqueue, and combining the
capability flags (`ingestion` from Phase 2 + `extraction` from Phase 3). Do not claim extraction is
verified end-to-end until Phase 2 ingestion is merged and a keyed live run has been done.
