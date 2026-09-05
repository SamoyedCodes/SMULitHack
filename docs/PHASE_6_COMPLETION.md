# Phase 6 completion — review queue and printable/downloadable lawyer briefs

> Integration update: this implementation is now included in the Phase 4–6 merge. See [combined verification](PHASE_4_6_INTEGRATION.md) for the current state and completed integration checks. The original branch-delivery notes below are historical.

Implemented against the `SMULitHack` repository on 5 September 2026, on branch `codex/phase-6-handoff`.
The existing frontend stack/design and canonical domain records were retained. No new dependency was
added (briefs print via the browser and download as self-contained HTML). The uncommitted
OpenRouter/Gemini provider work and unrelated `.claude/` files were preserved.

A lawyer brief is a **read-only projection of already-persisted, already-validated grounded data**
(`ReviewIssue` and `ConflictAssessment`, each carrying `Evidence`). **No model call is made** to
assemble the queue or a brief — the same discipline as the Phase 4 calendar.

## Delivered

- **Brief endpoint.** The reserved `GET /api/review/{issue_id}/brief` route is implemented
  ([backend/api.py](../backend/api.py)), returning a typed, schema-validated `Brief`. It accepts
  `mode` and `as_of` (like `/api/portfolio`), stays read-only (no jobs enqueued, no inference), and
  remains gated by the `handoff` capability in existing middleware (501 when disabled).
- **Aggregation + assembly module** [backend/review.py](../backend/review.py): `review_items`
  builds the canonical id space over extraction issues, deadline issues (only when the `deadlines`
  capability is enabled), and every conflict assessment; `build_brief` normalizes any record into a
  self-contained `Brief` (denormalized document titles, generation metadata, disclaimer). A
  competence gate re-checks that each cited source document exists and its page checkpoint is still
  readable, surfacing `coverage_warnings` instead of presenting stale certainty.
- **`Brief` / `BriefDocument` response models** ([backend/models.py](../backend/models.py)), added
  additively with defaulted fields; OpenAPI/fixtures regenerated from Python.
- **Unified review queue UI** ([frontend/src/Review.tsx](../frontend/src/Review.tsx)): counts
  (potential conflicts, insufficient evidence, extraction & deadline items, total open); rows sorted
  conflicts-first with document names, a lawyer-question preview and status badges; empty states
  that distinguish an analyzed-and-clear queue from unprocessed/incomplete documents ("not an
  all-clear"). "No conflict identified for this rule" is excluded from the actionable queue but
  still reachable by id.
- **Printable brief view** ([frontend/src/Brief.tsx](../frontend/src/Brief.tsx)): established facts,
  missing facts, scope comparison, exceptions, explanation, the specific lawyer question, urgency,
  provenance/confidence, verbatim source excerpts with document · page · clause labels, and coverage
  warnings shown prominently. **Print / Save as PDF** uses `window.print()`; **Download brief**
  writes a self-contained HTML file (no external assets). **View source** reuses the existing
  `SourceViewer` to open the cited document at its page with cited spans highlighted — closing the
  cross-document evidence-navigation gap within the brief view.
- **Shell wiring** ([frontend/src/App.tsx](../frontend/src/App.tsx)): the "Needs review" view renders
  the queue when connected and `handoff` is enabled, plus a sidebar open-item count. A new
  `fetchBrief` client validates the response against the generated `Brief` schema
  ([frontend/src/api.ts](../frontend/src/api.ts)). Review/brief styles and a `@media print` block
  were appended to `styles.css`.
- **`handoff` capability enabled** ([backend/foundation.py](../backend/foundation.py)) after the
  route and backend tests passed. No other capability was changed.

## Verification

| Check | Result |
|---|---|
| Backend tests — full suite | **97 passed** (`.venv/bin/python -m pytest -q`) |
| Backend tests — Phase 6 (`tests/test_review.py`) | **7 passed** |
| OpenAPI drift (`scripts/export_openapi.py --check`) | Passed |
| Fixture drift (`scripts/export_fixtures.py --check`) | Passed |
| `Brief`/`BriefDocument` present in `shared/openapi.json` | Confirmed |
| Pre-existing capability tests updated for enabled `handoff` | `test_foundation.py`, `test_ingestion.py` updated and passing |

Backend acceptance covered: handoff-disabled → 501; extraction-issue brief; conflict brief (scope
comparison, exceptions, explanation, status, provenance/confidence); unknown id → 404; live/sample
separation; unreadable cited source → `coverage_warnings` populated without fabricating certainty;
repeated reads deterministic with no jobs enqueued.

## Limits and remaining checks

- **Frontend checks were not run in this environment.** No Node.js runtime is installed on this
  machine (`node`, `pnpm`, and the `frontend/node_modules/.bin` tools cannot execute), so the
  TypeScript type generation, frontend unit tests and production build were **not** run here, and
  `shared/api.generated.ts` was **not** regenerated (it must never be hand-edited). The frontend
  source and two test files are complete and ready. Run, in an environment with Node 22.13+ and the
  pinned pnpm:

  ```sh
  pnpm --dir frontend api:generate   # adds Brief/BriefDocument to shared/api.generated.ts
  pnpm --dir frontend api:check
  pnpm --dir frontend test           # includes review.test.tsx and brief.test.tsx
  pnpm --dir frontend build
  ```

  Until `api:generate` runs, the frontend will not typecheck because `components['schemas']['Brief']`
  does not yet exist in the generated types (`ReviewIssue` and `ConflictAssessment` already do).
- **Browser walkthrough not performed** (no dev server without Node). Still to do: open "Needs
  review", open a conflict brief, follow **View source** to a highlighted page in each of the two
  documents, **Print / Save as PDF**, **Download brief** and open it standalone, and confirm an
  insufficient-evidence brief reads as unresolved/low-confidence and asserts no breach.
- Deadline issues appear in the queue only once Phase 4 is merged and `CAPABILITIES.deadlines` is
  enabled; conflicts appear once Phase 5 produces `comparisons`. On this branch those modules exist
  but are not yet wired into the portfolio, so the queue degrades to extraction issues plus any
  persisted conflicts — as designed (forward-compatible, non-blocking).
- No live model access, extraction/conflict accuracy, or hosted deployment is claimed; those remain
  earlier-phase and Phase 7 concerns.

## Next

Phase 7 (evaluation & demo). Do not start it until requested. Before considering Phase 6 fully
closed, complete the frontend command block and browser walkthrough above in a Node environment and
record the frontend/build results here.
