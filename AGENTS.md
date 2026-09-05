# AITHENA — repository guidance for builders and coding agents

## Read this first

This is AITHENA, the SMU legal-tech hackathon contract-obligation project. Work in this repository, preserve Builder B's frontend, and implement the solution one phase at a time. Phases 1–3 are integrated; verification limits are recorded in `docs/PHASE_3_INTEGRATION.md`. Builder 2 is assigned Phase 4 via `docs/PHASE_4_HANDOFF.md`; the user owns Phase 5 on a separate branch. Finish the assigned checkpoint only.

This file records both the inspected implementation and the agreed destination. A planned feature, a sample screen, or a draft in another workspace is not a completed feature. Recheck the source and update this file when changes land. User instructions take precedence over this guidance.

**Snapshot date:** 5 September 2026, Asia/Singapore.
**Integrated baseline:** main combines Phase 2 checkpoint `f467ea8` and Phase 3 branch `460049c`, with integration fixes. Existing `.env.example` deletion and unrelated `.claude/` work are preserved. The user authorized this local merge; no push was requested.
**Repository:** `SMULitHack` (the saved Codex project may be named “SMU Hack”). An older folder also named “SMU Hack” contains a separate scaffold and planning material; do not confuse it with this Git repository or overwrite this frontend with that scaffold.

## Product scope

An SME with roughly 40–80 signed agreements needs a trustworthy answer to “what are we on the hook for, and what is coming up?” Users are not lawyers and are unlikely to verify output. Unsupported certainty is a product defect.

The intended local MVP must:

1. Batch-ingest PDF, DOCX, PNG and JPEG documents, including at least one actual scanned document. Preserve originals, hashes and page provenance.
2. Extract parties, term, renewal mechanics, notice requirements, termination rights, payment obligations, liability caps and exceptions, and exclusivity/restrictive covenants. Preserve whose obligation or protection a finding concerns.
3. Show contract events **or action deadlines** within the next 90 days of an adjustable Singapore as-of date, including relevant overdue notice deadlines for upcoming events.
4. Detect at least one class of **potential** cross-contract conflict: incompatible distribution rights involving exclusivity, including exclusive versus non-exclusive grants.
5. Link every substantive finding to the exact document, physical page, clause, quotation and source coordinates. Distinguish provenance from confidence.
6. Escalate unanswerable, missing-context and high-stakes interpretation issues into structured lawyer handoffs.

Use English-language synthetic/public documents only. No real client material is required. Initial delivery assumes two builders and an approximately 36-hour hackathon; phase acceptance matters more than the original time estimates.

### Excluded from the MVP

General legal chat, Singapore-law retrieval, authentication, drive integrations, cloud deployment, automated notices, automatically sending lawyer briefs, and definitive decisions about breach or enforceability. No Redis, separate queue service or vector database is needed for v1. Do not add these merely because a tool or skill is available.

## What is actually in this repository

The repository now contains the **Phase 3 ingestion, grounded extraction and source viewer**, preserving Builder B's design. Extraction is explicitly requested per document. Calendar, conflict and handoff modules remain disabled drafts. Live model accuracy is unverified.

| Area | Current implementation | Important limit |
| --- | --- | --- |
| Frontend | React 19, TypeScript, Vite 6, Tailwind CSS 4, Lucide icons; Zod for prototype data and Ajv for live response validation | Preserve the existing stack and blue/ink visual design. This checkout is not the older Vinext/Sites scaffold. |
| Live screens | Overview/readiness, Contracts, Calendar, Conflicts, Needs review | Add contracts uploads files/folders; Contracts shows reading progress, source pages and highlights. Extracted findings retain all obligations per field and link to source highlights. SME selection uses established parties; later views remain disabled. |
| Backend | FastAPI/Pydantic, root configuration, SQLite persistence, typed health/errors, read-only saved metadata | One locked worker handles `ingestion` and explicit `extract` jobs. Both capabilities are enabled; other job types remain idle. |
| API contract | Relative `/api`, Vite proxy, OpenAPI snapshot and generated TypeScript types | Legacy sample types are isolated and must not become the live contract. |
| Samples | Four synthetic agreements; original dashboard retained in `PrototypeDashboard.tsx` | Not loaded by the live application. Fixed as-of date `2026-09-05`; sample confidence is illustrative, not calibrated. |
| Evidence | Prototype text-page dialogs; canonical page/span and coordinate models in Python | Live source pages and coordinate highlights are implemented. New generated fixtures include actual scanned PDFs; prototype OCR remains illustrative. |
| Uploads | Prototype picker/drag-drop retained; live ingestion routes guarded | Live batch/folder ingestion, duplicate/rejection receipts, checkpoints and explicit retries are implemented. |
| Dates and conflicts | Sample presentation preserved; Python processing modules carried forward as drafts | No deadline or semantic conflict engine is enabled or certified. |
| Briefs | Prototype conflict JSON export retained | No live review/handoff export is enabled. |
| Validation/tests | Backend foundation tests; prototype checks; canonical API/readiness tests; build/schema drift checks | Foundation validation does not prove extraction correctness or confidence calibration. |
| WebMCP | Original prototype's optional read-only tool retained | Not part of the live readiness app; supporting-browser registration remains unverified. |

### File map

- `frontend/src/App.tsx`: live readiness shell, navigation and phase-specific empty states.
- `frontend/src/api.ts`: canonical relative API client, timeouts and OpenAPI-derived runtime validation.
- `frontend/src/api.test.tsx`, `ingestion.test.tsx`: API/readiness and ingestion checks.
- `frontend/src/Ingestion.tsx`: batch upload/receipt, document library and physical-page source viewer.
- `frontend/src/PrototypeDashboard.tsx`: isolated original dashboard for later visual/component reuse.
- `frontend/src/data.ts`, `data.test.tsx`: prototype fixtures/validation tests; legacy network functions are disabled.
- `frontend/src/styles.css`, `main.tsx`: shared appearance and live React entry point.
- `frontend/vite.config.ts`: configured loopback ports and relative `/api` development/preview proxy.
- `frontend/package.json`, `frontend/pnpm-lock.yaml`, `frontend/pnpm-workspace.yaml`: dependencies, scripts, pinned pnpm and build-script policy.
- `backend/api.py`, `config.py`, `foundation.py`: application lifespan, configuration, health, capabilities and route guards.
- `backend/models.py`, `store.py`: canonical Pydantic records and persistent SQLite layout.
- `backend/ingestion.py`, `documents.py`, `worker.py`: active local upload/reading pipeline and explicitly queued extraction. Provider imports are lazy; local reading needs no key.
- `backend/llm.py`, `evidence.py`: active extraction/support review and evidence checks; no live model accuracy claim.
- `frontend/src/Findings.tsx`: extraction request, full findings/evidence and SME selector.
- `backend/analysis_worker.py`, `deadlines.py`, `conflicts.py`: inactive drafts; never start the old coupled worker.
- `shared/openapi.json`, `shared/api.generated.ts`: canonical API snapshot and generated types.
- `shared/health.fixture.json`, `shared/portfolio.fixture.json`: backend-derived non-legal API fixtures.
- `shared/types.ts`, `shared/sample-portfolio.json`: **legacy prototype v1.0**, not the live API payload.
- `sample-contracts/*.txt`: synthetic transcriptions, not mixed-format ingestion fixtures.
- `scripts/dev.py`, `doctor.py`, `export_openapi.py`, `export_fixtures.py`: launch, diagnostics and contract generation.
- `tests/test_foundation.py`, `test_ingestion.py`: isolated foundation, local ingestion, 80-file load, restart, source, OCR/DOCX and boundary checks.
- `scripts/make_ingestion_fixtures.py`: seven synthetic mixed-format ingestion files; no extraction answer key implied.
- `README.md`, `docs/INTEGRATION.md`: current startup and integration guidance.
- `IMPLEMENTATION_PLAN.md`, `PHASE_1_COMPLETION.md`, `docs/PHASE_2_HANDOFF.md`: phase boundaries, recorded verification and next-builder extension points.

### Prototype differences to preserve awareness of

The original dashboard's automatic sample selection, URL-based “Connected” badge, hard-coded Meridian SME and direct `/portfolio` / `/documents` HTTP behavior are not the live implementation. Do not reintroduce them when reusing its components.

- Prototype provenance has only `found | inferred | unresolved`; canonical findings also distinguish `calculated`.
- Prototype fields use singular `payment` and combine notice with renewal. Canonical fields use `payments` and separate `notice`.
- Prototype evidence lacks canonical span IDs and page-coordinate boxes.
- Prototype conflicts cannot represent all canonical insufficient-evidence and rule-specific no-conflict statuses.
- Prototype date filtering checks supplied action dates only; the future backend must select event **or** action dates within the horizon.
- Prototype upload validation still says 20 MiB; live backend health advertises the planned 25 MiB limit. Phase 2 reads server limits and implements batch multipart `files`.

## Phase status and checkpoints

**Current checkpoint: Phase 3 integrated with Phase 2.** Read `docs/PHASE_3_INTEGRATION.md` for verification and limits, and `docs/PHASE_4_HANDOFF.md` for Builder 2. Phases 4–7 are not complete. The sample dashboard previews later UI only. Do not import temporary work or overwrite another active builder's changes without checking the repository.

| Phase | Scope and completion gate | Status at this snapshot |
| --- | --- | --- |
| 1 — Runnable foundation | Preserve the frontend shell; add FastAPI/SQLite, validated configuration, real health/capability reporting, stable generated interfaces, portable startup and smoke tests. Runs without a Gemini key. | Implemented; remaining checks listed below. |
| 2 — Ingestion and pages | Up to 80 mixed-format files, originals/hashes, durable local queue, conversion/OCR, page coverage/errors, deduplication, restart recovery, source viewer. Local reading must work without a key. | Implemented and tested, including real OCR/DOCX and 80-file ingestion; no model calls. |
| 3 — Grounded extraction | Gemini structured extraction and support review, Python citation checks, all required fields, explained provenance/confidence, completeness and SME selection. | Integrated and tested with fake-provider fixtures; live model access and extraction accuracy remain unverified. |
| 4 — Deadlines | Tested Python rules, notice windows, ambiguity stops, adjustable as-of date, 90-day/overdue events with cited calculations. | Planned; sample date display and disabled drafts only. |
| 5 — Conflicts | Conservative Python candidate selection, LLM comparison of both agreements, evidence validation, cached/pending assessments and uncertainty. | Planned; sample conflict display and disabled drafts only. |
| 6 — Review and handoff | Dedicated review queue, missing facts, urgency, source excerpts and a specific lawyer question; printable/downloadable briefs. | Planned; sample conflict JSON export only exists. |
| 7 — Evaluation and demo | Mixed-quality corpus and reviewed answer key, grouped holdout, quality/calibration metrics, 80-file ingestion test and reproducible demonstration. | Planned; four synthetic examples are not an evaluation corpus. |

Complete the explicitly assigned phase, run appropriate acceptance checks, record actual results and remaining limits, and stop at the checkpoint. Do not silently enable the next phase.

## Agreed target architecture

```mermaid
flowchart TB
    UI[React / TypeScript interface] -->|relative /api HTTP| API[FastAPI / Pydantic]
    API <--> DB[(SQLite metadata, queue and results)]
    API <--> FILES[Local originals and rendered pages]
    DB --> WORKER[One backend-managed Python worker]
    WORKER --> PARSE[PyMuPDF / Tesseract / LibreOffice]
    PARSE --> EXTRACT[LLM extraction and support review]
    EXTRACT --> VERIFY[Python evidence and completeness checks]
    VERIFY --> DATES[Python deadline arithmetic]
    VERIFY --> PAIRS[Python candidate selection]
    PAIRS --> COMPARE[LLM semantic comparison]
    COMPARE --> VALIDATE[Python assessment validation]
    DATES --> DB
    VALIDATE --> DB
    EXTRACT <--> GEMINI[Gemini API]
    COMPARE <--> GEMINI
```

Phases 2–3 add local upload, OCR/conversion, source viewing and explicit provider extraction/support review. Deadline, conflict and handoff nodes remain disabled. OpenRouter is primary via existing httpx with `OPENROUTER_API_KEY`/`OPENROUTER_MODEL` (default `openrouter/free`), with the Google Gemini SDK as secondary and configurable `GEMINI_MODEL`; the agreed provisional default is `gemini-3.8-flash`. Model availability, key validity and free-tier capacity must be verified in the extraction phase; naming a default does not verify access. Never silently switch to paid inference.

Conversion/OCR run locally. When model analysis is enabled, extracted text is sent to OpenRouter and its model provider, or Gemini as secondary. Keys stay in the backend. The browser communicates only with FastAPI; no credentials belong in `VITE_*` variables.

### Historical Phase 1 contract and continuing invariants

- Backend Pydantic records are the source of truth: `Document`, `Finding`, `Evidence`, `Page`/`Span`, `Event`, `ReviewIssue`, `ConflictAssessment`, `Portfolio`.
- Preserve IDs, hashes, original files, JSON meanings and existing SQLite records when introducing the backend. Do not reset data to solve interface mismatches.
- Export OpenAPI without starting storage, a worker or inference; generate TypeScript API types and add schema/type drift checks. Keep synthetic prototype types explicitly separate if retained during migration.
- Use relative `/api` requests and a Vite proxy. Planned ports: API `8000`, frontend `3000`, configurable through root `AITHENA_API_PORT` and `AITHENA_WEB_PORT`. The live Vite config and launcher use these same validated ports.
- Resolve relative `AITHENA_DATA_DIR` against the repository root. Nonempty process environment overrides root `.env`, which overrides defaults. Validate distinct ports and finite non-negative inference intervals.
- Importing the API or exporting its schema must not create directories, initialize SQLite, instantiate a worker, or contact Gemini. Initialize storage in application lifespan. Existing queued/running jobs stay idle in Phase 1.
- Add backend-owned capabilities: `ingestion`, `extraction`, `deadlines`, `conflicts`, `handoff`, `sample_workspace`. All are false in Phase 1; both API and UI honor them. Installing a tool or configuring a key does not enable a feature.
- Health reports API/database status, model name, key presence as **configured but unverified**, optional OCR/DOCX executable detection, worker state, capability flags, limits and the inference data-flow notice. A missing key/native tool is nonfatal in Phase 1. A runtime database failure produces degraded health/503.
- Distinguish executable detection from successful processing. Never expose credentials, raw exception details or sensitive input in API errors.
- Use a consistent error envelope: `{"error":{"code":"feature_not_enabled","message":"…","details":[]}}`. Disabled features return 501; missing reads 404; invalid input 422; forbidden origins 403; internal failures a sanitized 500.
- The live UI defaults to checking/empty, never invented sample obligations. Preserve Builder B's sample components/fixtures for later reuse, but do not load them automatically when the live service is absent.
- Show readiness, disabled ingestion with a Phase 2 explanation, unknown SME, and accurate empty states. Poll health every 10 seconds without overlapping requests, use bounded timeouts and cleanup, allow manual retry, and label retained results stale after failure.
- Keep main text readable, controls keyboard-operable, status updates accessible, and layouts usable on mobile and at 200% zoom.

### Current routes and later extension points

| Route | Current behavior | Later implementation |
| --- | --- | --- |
| `GET /api/health` | Typed readiness/capabilities | Shared foundation |
| `GET /api/portfolio` | Canonical live shape; empty on fresh storage; read stored results without recomputation | Portfolio aggregation |
| `GET /api/jobs`, `GET /api/batches/{id}`, `GET /api/documents/{id}` | Read existing metadata only | Progress and inspection |
| `POST /api/batches` | Enabled; typed 202 receipt, optional UUID `Idempotency-Key` | Batch multipart `files`, max 80; backend enforces limits |
| `GET /api/batches?limit=1` | Latest persisted receipts (limit 1–20) | Receipt history |
| `POST /api/retry?document_id=...` | Enabled for failed/source-review ingestion only | Resume eligible local jobs |
| `GET /api/documents/{id}/pages`, `GET /api/documents/{id}/pages/{number}/image`, `GET /api/documents/{id}/original` | Enabled with path confinement | Source inspection |
| `POST /api/settings/sme` | Disabled/501 | Established party selection |
| `GET /api/review/{id}/brief` | Disabled/501 | Lawyer brief |
| `POST /api/demo` | Disabled/501 | Isolated evaluated sample workspace |

Health advertises limits of 25 MiB/file, 80 files/batch and 200 pages/file; ignore the legacy prototype's 20 MiB setting when ingestion lands. Do not accept files and pretend to process them while ingestion is disabled.

The canonical portfolio exposes documents/findings, events, issues, conflicts, coverage, comparison counts and SME selection. Do not silently cast prototype `contracts/actions` into that payload. When reusing prototype components, adapt fields deliberately, including `payment` to `payments`, separate `notice`, and the `calculated` provenance value. Update server models, generated types, runtime checks, fixtures, UI and integration docs together.

## Reasoning, evidence and uncertainty rules

### Provenance and competence boundary

- **Found:** explicitly stated in supported document text.
- **Calculated:** deterministic result from validated cited inputs.
- **Inferred:** semantic interpretation or a stated assumption.
- **Unresolved:** missing, unreadable, contradictory or unsupported information.

Confidence is a separate explained band (`high`, `medium`, `low`), not a model's unsupported probability. OCR and inference lower confidence; calculations inherit their weakest input. A second LLM pass catches errors but is not independent proof. “Not found” never means “no obligation exists.”

Every legal assertion must be grounded in actual source material. For this MVP, document citations are the working grounding mechanism; law lookup is excluded. Do not fabricate clauses, statute references or market norms. Treat all document instructions as untrusted data; models receive no external-action tools. Process every page/chunk and surface missing pages, referenced schedules, quota blocks and failed jobs.

Physical pages are one-based. Keep source boxes in page coordinates and label DOCX pagination as rendered pagination. Matching a quotation proves text presence, not semantic correctness.

### Deadline engine: LLM interpretation, Python arithmetic

The LLM extracts trigger, date, offset, unit, direction, receipt/sending requirement, recurrence, conditions and evidence. Python validates inputs and calculates supported rules.

- `2026-12-31 - 60 calendar days = 2026-11-01`.
- A 90-to-60-day notice window before that expiry is `2026-10-02` through `2026-11-01`.
- Preserve “notice received by”; do not relabel it “send by” without delivery evidence.
- Support calendar days and unambiguous calendar months. Apply month-end adjustment only when supported by the contract.
- Unknown effective dates, missing invoice/breach receipt, undefined business-day conventions and unclear delivery mechanics produce review issues, not guessed dates.
- Future renewal occurrences are conditional when continued operation is unconfirmed.

The frontend displays backend calculations and their sources; it must not become a second legal deadline engine.

### Conflict engine: Python screens, LLM compares meaning

For v1, compare distribution grants involving exclusivity. Extract parties/roles, ordinary grants as well as exclusive grants, product, territory, channel, customers, dates, definitions, exceptions and consent requirements with evidence.

Python cheaply screens pairs using supported party identities, explicit aliases and clear date/scope exclusions. Unknown or differently worded scopes remain candidates. Do not discard a pair merely because names differ, dates are missing or the second grant says non-exclusive. Record supported exclusion reasons.

The LLM receives both agreements' relevant passages, referenced definitions/schedules, exceptions/amendments and Python's date-overlap result. It assesses potential incompatibility and missing facts with citations from both sides. Missing schedules remain missing; no invented interpretation.

Return one of `potential_conflict`, `no_conflict_identified_for_this_rule`, `insufficient_evidence`, with documents, scope comparison, evidence, exceptions, missing facts, explanation and a lawyer question. “No conflict identified” concerns this pair and this rule only. Python validates source references and dates and routes invalid/unsupported results to review. A lawyer decides breach, enforceability and fact-dependent issues.

Cache by both document hashes, model/processing version and relevant inputs. Show outstanding/failed comparison counts when quota prevents completion.

### Handoff and evaluation

A lawyer brief includes the issue, relevant documents/clauses, established facts, source excerpts, missing facts, urgency and the specific question requiring human judgment. It is downloadable/printable, never automatically sent.

Evaluation needs a separately reviewed answer key and roughly one-third grouped holdout, keeping related agreements together. Include actual scans, degraded/mixed pages, missing schedules, misleading document instructions, fabricated citations, ambiguous deadlines, exceptions/consent, non-overlapping terms, duplicate uploads, restart and quota cases.

Measure field accuracy, citation validity, answerable coverage, deadline accuracy, candidate recall, final conflict precision/recall and correctness by confidence band. Run the 80-file ingestion test separately. The 85% answerable-field accuracy is a target, not an achieved result. No measured extraction/calibration score is established by the current sample frontend.

## Builder workflow and verification

Builder B's UI is the design baseline. Reuse components and fixtures; avoid re-scaffolding, unrelated redesign or broad dependency upgrades. Suggested responsibility split: Builder A owns backend foundation/ingestion/extraction/deadlines; Builder B owns frontend integration/evidence/review views and may own conflict work by explicit team agreement. Ownership must be confirmed for overlapping backend modules. “Builder B” does not itself authorize spawning agents or sending messages to another person/task.

For the current frontend, from repository root:

```sh
pnpm --dir frontend install --frozen-lockfile
pnpm --dir frontend dev
pnpm --dir frontend test
pnpm --dir frontend build
```

Use Python 3.12, Node 22.13+ and the pinned pnpm 11.19.0. The recorded verification used Node 24; Node 22 has not been separately exercised. Preserve `frontend/pnpm-workspace.yaml`'s existing scoped build policy (`esbuild: false`); do not globally enable install scripts.

The Python foundation and scripts now exist. From repository root:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
# Defaults work without .env. Create root .env only for overrides; preserve existing secrets.
.venv/bin/python scripts/doctor.py
.venv/bin/python scripts/dev.py
```

The launcher starts API and UI together on loopback, validates ports, and stops both owned children on Ctrl+C. It does not stop unrelated servers. No Gemini key is required for Phase 1 or local ingestion. `VITE_API_BASE_URL` is no longer used.

```sh
.venv/bin/python -m pytest -q
.venv/bin/python scripts/export_openapi.py --check
.venv/bin/python scripts/export_fixtures.py --check
pnpm --dir frontend api:check
pnpm --dir frontend test
pnpm --dir frontend build
```

After response-model changes, run `scripts/export_openapi.py` and `scripts/export_fixtures.py` without `--check`, then `pnpm --dir frontend api:generate`. Do not edit generated types by hand.

Phase 1 acceptance must cover import/schema side effects, optional missing tools/key, sanitized health/errors, configuration precedence and invalid values, persistence across restart, idle queued work, disabled routes, missing resources, degraded database behavior, frontend build/schema checks, proxy on default and nondefault ports, and clean shutdown. Record actual test/browser results and untested limits; do not label the entire phase complete on file creation alone.

Preserve unrelated edits and coordinate shared-file changes. Do not copy `.env`, credentials, document data, dependency caches or virtual environments between builders. Do not commit, push, deploy, send notices or send briefs without the relevant user authorization. Keep setup documentation machine-independent.

## Recorded verification and immediate next work

`PHASE_1_COMPLETION.md` records **23 backend tests and 19 frontend tests passed**, TypeScript/build and schema/fixture/type checks passed, plus browser verification through the `3001 → 8001` proxy, all five views, disabled uploads, keyboard focus, a 390 × 844 viewport, stale/disconnected behavior and launcher shutdown. These are the implementing task's recorded results; this documentation task did not rerun the suites.

Still unverified: exact default `3000 → 8000` proxy path (3000 was occupied), full 200% browser zoom, Linux and Node 22 runs. Live Gemini access/quota, actual OCR/DOCX conversion, ingestion load, extraction/deadline/conflict accuracy, source highlights and lawyer export are outside Phase 1 verification.

Phase 2 verification: **37 backend tests and 25 frontend tests passed**, including real clean/degraded scans, mixed/blank pages, DOCX, images, duplicate/idempotent/concurrent uploads, errors/retries, process-lock/restart behavior, path confinement and an 80-file ingestion run. Source coordinates and rotated page geometry are checked. Browser verification exercised native PDF/scan/DOCX upload and visible source highlights. See `PHASE_2_COMPLETION.md` for final checks and limits; Phase 1's old out-of-scope list above is historical.

Phase 3 integration: read `docs/PHASE_3_INTEGRATION.md`. The active `worker.py` retains local ingestion and claims explicit `extract` jobs with a lazy provider; old `document` and `conflict` jobs remain idle. `analysis_worker.py` is an inactive reference. Keep source checkpoints, warnings, lock/recovery, generated contracts and three-second polling intact. Only ingestion/extraction capabilities are enabled. Builder 2's Phase 4 ownership and Phase 5 compatibility are specified in `docs/PHASE_4_HANDOFF.md`.

## Skills and local tooling

Use a skill only when its actual instructions and the task make it applicable. Read its `SKILL.md` first and tell the user when applying it. A machine-local skill path is not a portable repository dependency.

### Ponytail — smallest correct implementation

Ponytail **4.9.0** is installed on the current builder's machine and its skills have been inspected. Apply the core `ponytail` skill to AITHENA coding, bug fixes, design and dependency decisions. Respect the user's selected level or deactivation; the plugin's default is **full**, with **lite** and **ultra** alternatives. This guidance does not change plugin settings or hooks.

Locate the installed plugin through the current host's skill catalog; its core instructions are `skills/ponytail/SKILL.md` inside the plugin package. Companion instructions are `skills/ponytail-review/SKILL.md`, `skills/ponytail-audit/SKILL.md`, `skills/ponytail-debt/SKILL.md`, `skills/ponytail-gain/SKILL.md` and `skills/ponytail-help/SKILL.md`. Read the relevant installed file before use. The inspected package lives under `~/.codex/plugins/cache/ponytail/ponytail/4.9.0/`; this is a discovery hint, not a portable application dependency. Another builder may have a different version or no installation; retain these project principles without claiming to have loaded an unavailable skill.

**Working order:** understand the actual flow and affected callers first; check whether the requested change is needed for the assigned phase; reuse existing code/types; prefer the standard library, then native platform features, then already-installed dependencies; only then add the minimum readable code that satisfies the requirements. Fix the shared root cause rather than patching each symptom. Prefer fewer files and a small, reviewable diff over speculative wrappers, factories, configuration and new dependencies.

For this project:

- Preserve Builder B's React/Vite/Tailwind implementation and reuse the canonical Pydantic/OpenAPI contract and existing client. Do not create a second schema, deadline engine or upload path merely to reuse a prototype component.
- Keep SQLite, local files and one worker for the agreed scale. Do not add a queue service, vector database or generalized framework without a concrete requirement.
- Phase 1 capability guards and later-phase schema records have an explicit integration purpose; do not classify them as dead code merely because processing is currently disabled. Preserve carried-forward drafts unless the assigned task authorizes their removal.
- Never simplify away trust-boundary validation, evidence/citation checks, provenance/confidence distinctions, missing-input escalation, data-loss prevention, job durability, security or accessibility. These are core requirements. A shorter but confidently unsupported answer is a failure.
- Keep the smallest meaningful runnable check for changed nontrivial behavior, using the existing pytest/Vitest setup. Ponytail's generic preference for minimal tests does not remove the expressly required corpus evaluation, regression fixtures, schema checks or phase acceptance gates. Documentation-only edits need a focused diff/content check rather than an unrelated suite run.
- Mark a deliberate implementation shortcut with a `ponytail:` code comment only when it has a real known limit; name that limit and the concrete trigger/upgrade path. Do not label ordinary readable code as debt or use a shortcut to omit a must-have requirement.
- Keep unsolicited explanations brief. Provide requested plans, walkthroughs, evidence and handoffs in full; brevity must not conceal uncertainty, test failures or remaining work.

| Skill | When to use | Boundary |
| --- | --- | --- |
| `ponytail` | Implement/fix/design the assigned work with the smallest correct change | Does not override explicit requirements or advance the phase. |
| `ponytail-review` | Review a diff for unnecessary complexity | Report-only; not a correctness/security review and not permission to apply fixes. |
| `ponytail-audit` | Requested whole-repository complexity audit | One-shot ranked report; does not mutate the repo or replace phase verification. |
| `ponytail-debt` | Report deliberate `ponytail:` shortcuts and revisit triggers | Read-only ledger; persist a report only when requested. |
| `ponytail-gain` | Requested plugin benchmark summary | Published plugin benchmarks are not measured AITHENA savings. Never invent repo-specific cost, speed or line savings. |
| `ponytail-help` | Explain available levels/commands | Reference only; does not change settings or activate unrelated work. |

Ponytail's help identifies Codex mentions such as `@ponytail`, `@ponytail-review` and `@ponytail-help`; command availability depends on the host. Follow the installed skill for invocation. “Stop ponytail” or “normal mode” deactivates the mode; do not silently reactivate it during that session. Merely adding this guidance does not request an audit, deletion pass, benchmark run or additional project work.

### Other skills

- Preserve the installed React/Vite/Tailwind implementation. Apply other skills only for a concrete need within the assigned phase.
- A PDF skill may help later with creating and visually verifying actual PDF/scan evaluation fixtures. It does not replace the application's PyMuPDF/Tesseract ingestion pipeline.
- Sites skills are conditional on applicable project metadata or explicit Sites work. This inspected checkout has no `.openai/hosting.json`; do not migrate or publish the local app merely because Sites is available.
- Azure deployment, document/presentation/spreadsheet creation and image-generation skills are not required for Phase 1. Do not add infrastructure or artifacts outside the requested phase.

Keep this file current as implementation replaces the prototype: update the inspected baseline, phase status, live routes/schema, commands, verification evidence and remaining gaps. Clearly separate facts, plans and unverified assumptions.

## Provider routing update

Use `backend.llm.ModelClient` for extraction/review and future Phase 5 comparison work: OpenRouter primary, Gemini secondary. Read `docs/MODEL_PROVIDERS.md`; primary/secondary caches and cooldowns are separate, failed/refused answers do not trigger fallback, and per-document model usage stays separate from evidence/confidence. Health reports both providers without exposing keys; original data and inference capability boundaries are unchanged. Phase 4 makes no model calls. Preserve the additive schema fields when merging other builders’ branches. Live provider access/accuracy remain unverified.
