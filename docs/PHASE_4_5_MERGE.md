# Manually combine Phase 4 and Phase 5

Phase 5 lives on `codex/phase-5-conflicts`. It includes OpenRouter-primary/Gemini-secondary checkpoint `e69f758`, based on integrated main `011376d`. It has not been merged into main or pushed. Builder 2's Phase 4 branch name is intentionally not assumed.

The implementing task used an isolated worktree because another task had uncommitted Phase 6 work in the shared checkout. Do not switch or clean that dirty checkout merely to merge these branches. Use a separate integration worktree, or first let its owner finish.

## Suggested sequence

1. Start an integration branch/worktree from current main after reviewing its latest state.
2. Merge Builder 2's completed Phase 4 branch.
3. Merge `codex/phase-5-conflicts`. Merge both commits in its history; do not omit the OpenRouter prerequisite if main does not already contain it.
4. Resolve shared source files as described below. Regenerate API artifacts from the combined Python models.
5. Run both phases' tests and browser acceptance, inspect the diff, then manually merge the verified integration branch into main.

No merge, commit, push or deployment is performed by these notes.

## Shared-file decisions

| File | Preserve from Phase 4 | Preserve from Phase 5 |
|---|---|---|
| `backend/api.py` | Calendar event projection, adjustable as-of input, deadline review issues and Phase 4 routes | Read-only conflict snapshot, additive conflict issues, scan summary, guarded Continue/Retry/screening routes, SME-triggered reconciliation |
| `backend/models.py` | Event/DeadlineRule extensions and calendar-specific schemas | Defaulted ConflictScan, ConflictScreen, assessment revision/current/creation metadata, dimension/exception evidence and ModelUse |
| `backend/foundation.py` | Enable deadlines only after Phase 4 acceptance | Enable conflicts; retain ingestion/extraction and leave handoff/sample disabled unless independently accepted |
| `backend/worker.py` | Any justified Phase 4 hooks | Ingestion/extraction priority, post-extraction reconcile, one worker lock, versioned conflict recovery and pair-specific errors |
| `frontend/src/App.tsx` | Calendar view, as-of controls and deadline evidence links | Dedicated Conflicts view, navigation count, notifications, selected conflict and source navigation callback |
| `frontend/src/api.ts` | Calendar types and client methods | Conflict types, Ajv validation, screening/Continue/Retry methods; retain relative `/api` and existing request safety |
| `frontend/src/Ingestion.tsx` | Source-viewer behavior required by Calendar | Optional `backLabel` for return to Conflicts and existing page/span evidence selection |
| `backend/config.py` | Existing config and any independent safe additions | OpenRouter routing and version invalidation; choose one new combined processing version |
| Tests and docs | Phase 4 fixtures, assertions and results | Phase 5 conflict tests, answer key and completion record |

Do not resolve `backend/api.py` by taking Phase 5 wholesale: its baseline still has `events=[]` because Phase 4 was not present. The combined response must retain Phase 4's calculated events and append extraction + deadline + conflict issues. Keep portfolio GET read-only; reconciliation belongs in processing/SME/startup triggers.

Phase 5 does not modify `backend/deadlines.py` or supply a Calendar replacement. Keep Builder 2's implementation. Merge phase capability assertions to allow both deadlines and conflicts; do not disable one to satisfy the other branch's old test.

Conflict identity includes extracted rules and findings, source analysis and routing. Changing these inputs legitimately stales comparisons and may consume remaining allowance for new candidates; never reset the persistent budget to make a demo look complete. Legacy unversioned draft comparison jobs stay idle.

## Regenerate, then verify

Resolve Python source schemas first, then regenerate rather than selecting one side of generated-file conflicts:

```sh
.venv/bin/python scripts/export_openapi.py
.venv/bin/python scripts/export_fixtures.py
pnpm --dir frontend api:generate
.venv/bin/python -m pytest -q
pnpm --dir frontend test
pnpm --dir frontend build
.venv/bin/python scripts/export_openapi.py --check
.venv/bin/python scripts/export_fixtures.py --check
pnpm --dir frontend api:check
git diff --check
```

In an isolated synthetic workspace verify: a Phase 4 calculated notice deadline and its formula/evidence; current and overdue horizon behavior; automatic Phase 5 notification; both cited source pages; named missing-schedule issue; paused backlog/Continue; no duplicate slots on restart; deadline and conflict issues both survive portfolio polling. Preserve originals, local data, `.env`, keys and other builders' uncommitted files.
