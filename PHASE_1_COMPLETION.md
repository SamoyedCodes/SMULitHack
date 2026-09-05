# Phase 1 integration verification

Verified 5 September 2026 against the pulled Builder 2 frontend (baseline commit `b3607a7`). Existing React 19 / Vite 6 / Tailwind 4 dependency resolutions were preserved. Added Ajv runtime response validation, OpenAPI type generation and Node configuration types; no frontend framework replacement or deployment.

## Implemented

- Live React readiness shell preserving the dashboard design; all five navigation views have phase-specific states.
- Local FastAPI/SQLite lifecycle, validated root configuration, read-only saved metadata and idle persisted jobs.
- Backend capability manifest and structured API errors, including guards before disabled body parsing.
- Canonical Pydantic records preserved from the original backend scaffold; generated OpenAPI/TypeScript and backend-derived health/portfolio fixtures.
- Relative API client, five-second request timeout, ten-second non-overlapping refresh, explicit stale/error state, no automatic synthetic fallback or assumed SME.
- Portable launcher/doctor, environment example, startup/check instructions, and a Phase 2 integration handoff.
- Original sample dashboard preserved as an isolated prototype; not an enabled demo, uploaded corpus, legal evaluation or live interface.

## Actual checks

| Check | Result |
|---|---|
| Backend foundation suite | 23 passed; isolated storage; no model calls |
| Frontend tests | 19 passed, including retained sample validation tests and new canonical API/readiness checks |
| TypeScript | Passed |
| Production frontend build | Passed |
| OpenAPI, fixture and generated-type drift checks | Passed |
| Import / export without storage, worker or Gemini initialization | Passed |
| Saved documents/settings and queued/running jobs across restarts | Passed |
| Missing tools/key, configured-but-unverified key, 503 database failure | Passed controlled tests |
| Browser readiness through Vite proxy on 3001 → 8001 | Passed |
| Browser navigation and disabled Add contracts | Passed all five views |
| Keyboard focus | Tab reached Check connection with visible focus |
| Mobile viewport | Checked at 390 × 844; navigation wraps, controls and text fit |
| Stop / connection retry | Disconnected and stale information visible after stopping services |
| Launcher Ctrl+C | Both owned child processes exited |

Test environment: macOS, Python 3.12.14, Node 24.19.0, pnpm 11.19.0. Node 22 is the declared minimum but was not separately exercised. Two dependency deprecation warnings are emitted by the installed FastAPI/Starlette test-client stack; tests pass.

## Limits and remaining checks

The default UI port 3000 was already occupied by another local server. The configurable 3001/8001 path was exercised instead; that server was left untouched. Exact default-port proxy behavior, a full 200% browser-zoom check, and separate Linux/Node 22 runs remain unverified.

No live Gemini call, actual OCR/DOCX conversion, ingestion load test, extraction/deadline/conflict evaluation, page highlights or lawyer-brief export was performed. Those belong to later phases. Model identifier/access/quota remain unverified. Draft processing modules are carried forward but not enabled or certified. Phase 1 engineering checks above pass; the complete original acceptance checklist should not be represented as fully verified until the remaining environment/browser checks are done.

See README for startup and `docs/PHASE_2_HANDOFF.md` for the next builder's concrete extension points.
