# AITHENA — local contract workspace

> Current checkpoint: Phases 1–6 are integrated. Local ingestion, explicit OpenRouter/Gemini extraction, grounded deadline calculations, automatic distribution comparisons, and review/printable lawyer briefs are enabled. Phase 7 evaluation and sample loading remain outside this checkpoint. See [combined integration verification](docs/PHASE_4_6_INTEGRATION.md).


Phase 2 adds batch ingestion and real source viewing to Builder 2's React interface and the local FastAPI/SQLite foundation. Upload PDFs, DOCX, PNGs or JPEGs (including scans), inspect every physical page, and select text blocks to highlight their source locations. Local reading needs no model key. Requested extraction and automatically allowed conflict comparisons send extracted text to a configured provider.

The navy/blue dashboard styling and navigation are retained. The earlier synthetic dashboard is preserved in `frontend/src/PrototypeDashboard.tsx` for component reuse and fixture tests; it is not loaded by the application. Its legacy sample schema is **not** the backend integration contract. Live types are generated from Python into `shared/api.generated.ts`.

## Install

Use Python 3.12, Node 22 (at least 22.13), and pnpm 11.19.0. macOS/Linux are supported; use WSL2 on Windows. From this repository's root:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
pnpm --dir frontend install --frozen-lockfile
```

Defaults work without an environment file. To override them, create a repository-root `.env` using the settings below. Do not overwrite an existing `.env` or store keys in frontend configuration.

```sh
.venv/bin/python scripts/doctor.py
.venv/bin/python scripts/dev.py
```

Open `http://127.0.0.1:3000`. The API is at `http://127.0.0.1:8000`; API documentation is at `/docs`. Ctrl+C stops both child processes. The launcher checks ports and never stops unrelated processes or silently chooses a new port.

Tesseract is required for scanned content; LibreOffice is required for DOCX. Missing tools do not prevent app startup: affected documents/pages show visible failures and can be retried after installation. macOS users can install them with `brew install tesseract` and `brew install --cask libreoffice`. On Debian/Ubuntu, install `tesseract-ocr` and `libreoffice` using the system package manager. The readiness panel reports executable detection. Per-document results report whether reading or conversion actually succeeded.

## Configuration

Nonempty process environment values override repository-root `.env`, then defaults. Paths relative to `AITHENA_DATA_DIR` resolve against the repository root, regardless of the calling directory.

| Variable | Default | Purpose |
|---|---|---|
| `AITHENA_API_PORT` | `8000` | API loopback port |
| `AITHENA_WEB_PORT` | `3000` | UI loopback port; must differ from API port |
| `AITHENA_DATA_DIR` | `data` | Local SQLite and future originals/results |
| `OPENROUTER_API_KEY` | absent | Primary backend provider credential |
| `OPENROUTER_MODEL` | `openrouter/free` | Primary model/route; set a supported model explicitly for reproducible evaluation |
| `GEMINI_API_KEY` | absent | Secondary backend credential; `GOOGLE_API_KEY` is its alias |
| `GEMINI_MODEL` | `gemini-3.8-flash` | Planned configurable model; access has not been verified |
| `AITHENA_LLM_INTERVAL` | `12` | Future request spacing; finite and nonnegative |
| `TESSERACT_CMD` | discovery | Optional executable override; an invalid override reports unavailable |
| `LIBREOFFICE_CMD` | discovery | Optional executable override |

API credentials must never be named `VITE_*` or placed in frontend configuration. `VITE_API_BASE_URL` from the prototype is no longer used. All live requests use relative `/api` routes through Vite's local proxy. The backend never infers feature availability from key presence.

For separate-terminal diagnosis, set any port overrides in root `.env` and use the matching port explicitly for uvicorn:

```sh
# Terminal 1, repository root (replace 8000 if configured differently)
.venv/bin/python -m uvicorn backend.api:app --host 127.0.0.1 --port 8000
# Terminal 2, repository root
pnpm --dir frontend dev
```

`pnpm --dir frontend build` checks and builds the frontend. `pnpm --dir frontend preview` previews that output with the same local API proxy; the Python API must be running separately. This is a local application, not a hosted deployment.

## Verify

```sh
.venv/bin/python -m pytest -q
.venv/bin/python scripts/export_openapi.py --check
.venv/bin/python scripts/export_fixtures.py --check
pnpm --dir frontend api:check
pnpm --dir frontend test
pnpm --dir frontend build
```

After changing a Pydantic response model:

```sh
.venv/bin/python scripts/export_openapi.py
.venv/bin/python scripts/export_fixtures.py
pnpm --dir frontend api:generate
```

Neither schema export nor app import initializes storage or starts a worker. Tests use isolated temporary SQLite databases. Do not put actual client contracts or credentials in fixtures.

## Readiness and phase boundary

- **Ready** means the local API can query SQLite. It is not evidence of completed extraction.
- **Configured, not verified** means only that a backend API key exists. Model availability/quota are not tested.
- **Disconnected / stale** means the current check failed; previous results cannot be treated as current. Checks repeat every three seconds; Check connection retries immediately when no check is active.
- A fresh workspace has no analyzed contracts. No SME is assumed, and no zero-obligation or all-clear conclusion is shown.
- Ingestion/source viewing, extraction, deadlines, conflicts and lawyer briefs are enabled. Sample loading remains disabled with a structured 501 error.
- Existing metadata/settings, comparison allowances and provider cooldowns are preserved. One worker handles ingestion, extraction and versioned conflict jobs in that priority order. Legacy unversioned analysis/conflict jobs remain idle.

The original coupled worker in `backend/analysis_worker.py` remains inactive. Calendar projection and lawyer brief assembly are read-only and do not call a model or enqueue work.

See [integration contract](docs/INTEGRATION.md), [phased implementation plan](IMPLEMENTATION_PLAN.md), [Phase 2 verification](PHASE_2_COMPLETION.md) and [Phase 3 handoff](docs/PHASE_3_HANDOFF.md).

## Ingest and inspect

1. Start the app, open Add contracts, and choose files or a folder. The browser reports unsupported, empty and oversized selections before sending; the backend rejects those entries individually while accepting valid siblings.
2. Submit one batch (1–80 files, 25 MiB per file). Its persisted receipt lists accepted documents, duplicates and rejections. A retry of an uncertain upload uses the same idempotency key. A duplicate reuses its saved document and does not silently restart a failed read.
3. Open Contracts. Progress refreshes every three seconds. `text_ready` means local text is available; `needs_source_review` means pages are unreadable or have warnings; `failed` means preparation/reading failed. Neither state establishes legal obligations.
4. Open View source, choose a physical page, and select a text block to highlight it. OCR reading confidence is separate from future legal confidence. DOCX pages use rendered pagination. Download original returns the preserved bytes.
5. If a converter/OCR tool was missing, install it and use Retry reading on the affected document. Good page checkpoints are reused; error/uncertain pages are read again. Blank pages are visibly unresolved, not silently omitted.

To generate seven synthetic test files (native PDF, real scanned PDF, degraded scan, mixed/blank pages, PNG, JPEG and DOCX):

```sh
.venv/bin/python scripts/make_ingestion_fixtures.py --output /tmp/aithena-synthetic
```

These fixtures are for ingestion verification only. They are not reviewed extraction ground truth. The native integration tests require installed Tesseract/LibreOffice and otherwise report explicit skips; all other tests still run. The 80-file ingestion test is separate from any future extraction evaluation.

Maximum document size is 200 pages; oversized/password-protected/damaged PDFs fail visibly. DOCX conversion has a 90-second timeout and a 100 MiB expanded archive limit; images have a 40-megapixel limit. Multi-frame images are rejected rather than reading only the first frame. New ingestion jobs use a cache version independent of Gemini model/key configuration. A process lock ensures one worker per data directory.

## Provider configuration

See [MODEL_PROVIDERS.md](docs/MODEL_PROVIDERS.md) for OpenRouter primary/Gemini secondary setup, fallback conditions and provider provenance. Local reading still requires no key; provider access and quality are unverified until tested with your configured account/model.

## Calendar, conflicts and lawyer review

Choose a Singapore as-of date in Calendar. Events include action deadlines within the next 90 days even when the related expiry is outside that horizon; overdue labels do not establish non-performance. Follow evidence links to the highlighted physical source page.

After selecting an established SME and requesting extraction, Conflicts automatically allows the first ten candidate pair revisions. Continue adds ten more; Retry retains the original slot and provider cooldowns. Missing schedules and unresolved scope remain visible, and historical comparisons are marked stale.

Needs review counts each current assessment once alongside distinct extraction and deadline issues. Open a brief to inspect facts, missing context, confidence explanations and source excerpts. It uses the selected calendar date. Print / Save as PDF invokes browser printing; Download brief saves self-contained HTML. Disconnected or changing context disables export until the brief is current. Briefs are never sent automatically.
