# AITHENA — local contract workspace

Phase 1 connects Builder 2's React interface to a local FastAPI/SQLite foundation. It shows real service readiness, optional tool detection, an honest empty workspace, and disabled later-phase capabilities. No Gemini key is needed; Phase 1 makes no provider requests.

The navy/blue dashboard styling and navigation are retained. The earlier synthetic dashboard is preserved in `frontend/src/PrototypeDashboard.tsx` for component reuse and fixture tests; it is not loaded by the application. Its legacy sample schema is **not** the backend integration contract. Live types are generated from Python into `shared/api.generated.ts`.

## Install

Use Python 3.12, Node 22 (at least 22.13), and pnpm 11.19.0. macOS/Linux are supported; use WSL2 on Windows. From this repository's root:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
pnpm --dir frontend install --frozen-lockfile
```

For first setup only, copy `.env.example` to `.env`. **Do not overwrite an existing `.env`.** Defaults also work without that file.

```sh
.venv/bin/python scripts/doctor.py
.venv/bin/python scripts/dev.py
```

Open `http://127.0.0.1:3000`. The API is at `http://127.0.0.1:8000`; API documentation is at `/docs`. Ctrl+C stops both child processes. The launcher checks ports and never stops unrelated processes or silently chooses a new port.

Tesseract and LibreOffice are optional for Phase 1. macOS users can install them with `brew install tesseract` and `brew install --cask libreoffice`. On Debian/Ubuntu, install `tesseract-ocr` and `libreoffice` using the system package manager. Detection means an executable was found, not that OCR/conversion has been tested.

## Configuration

Nonempty process environment values override repository-root `.env`, then defaults. Paths relative to `AITHENA_DATA_DIR` resolve against the repository root, regardless of the calling directory.

| Variable | Default | Purpose |
|---|---|---|
| `AITHENA_API_PORT` | `8000` | API loopback port |
| `AITHENA_WEB_PORT` | `3000` | UI loopback port; must differ from API port |
| `AITHENA_DATA_DIR` | `data` | Local SQLite and future originals/results |
| `GEMINI_API_KEY` | absent | Optional backend credential; `GOOGLE_API_KEY` is the fallback |
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
- **Disconnected / stale** means the current check failed; previous results cannot be treated as current. Checks repeat every ten seconds; Check connection retries immediately when no check is active.
- A fresh workspace has no analyzed contracts. No SME is assumed, and no zero-obligation or all-clear conclusion is shown.
- Uploads, source viewing, extraction, deadlines, conflict detection, lawyer briefs and sample loading are disabled. Their API routes return structured 501 errors without processing input.
- Existing saved metadata, settings and queued/running jobs are preserved. Phase 1 does not claim, recover, retry or execute jobs.

Draft later-phase Python modules are included from the original scaffold for the next builders; they are not imported by the Phase 1 API or validated as completed features. Enabling capability flags alone does not implement routes.

See [integration contract](docs/INTEGRATION.md), [phased implementation plan](IMPLEMENTATION_PLAN.md), [verification record](PHASE_1_COMPLETION.md) and [Phase 2 handoff](docs/PHASE_2_HANDOFF.md).
