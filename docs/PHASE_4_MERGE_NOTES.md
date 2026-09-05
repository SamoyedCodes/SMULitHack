# Phase 4 merge notes — for Builder 1

> Integration update: this implementation is now included in the Phase 4–6 merge. See [combined verification](PHASE_4_6_INTEGRATION.md) for the current state and completed integration checks. The original branch-delivery notes below are historical.

Phase 4 (grounded deadline calendar) is delivered on branch **`codex/phase-4-deadlines`**, commit
**`51f6dfb`**, branched from `main` at `011376d`. It is **not merged and not pushed**. Nothing on
`main` was changed.

This file is the coordination surface between Phase 4 and Phase 5. What the calendar does, and its
honest limits, are in [PHASE_4_COMPLETION.md](PHASE_4_COMPLETION.md); the original brief is
[PHASE_4_HANDOFF.md](PHASE_4_HANDOFF.md).

## 1. Regenerate `shared/*` on Python 3.12, never 3.13

Python 3.13 renamed two HTTP reason phrases (413 `Request Entity Too Large` → `Content Too Large`,
422 `Unprocessable Entity` → `Unprocessable Content`). Regenerating on 3.13 rewrites **30 lines of
`shared/openapi.json` that have nothing to do with anyone's phase**, and the churn propagates into
`shared/api.generated.ts`.

This was hit on the Phase 4 machine: `scripts/export_openapi.py --check` failed against a
completely untouched baseline. The fix is the interpreter, not the artifact.

```sh
python3.12 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt
.venv/bin/python --version   # expect 3.12.x before regenerating anything
```

If you see 413/422 wording move in a diff, stop: that is the wrong interpreter, not a real change.

## 2. `Event` changed shape — a stale schema fails loudly and misleadingly

`backend/models.py:159`. All additions are optional/defaulted, and `Event` is never persisted
(`Document` has no `events` field), so **no stored data migrates**.

| Change | Why |
|---|---|
| `confidence_reason: str = ""` | Section 5D requires a confidence explanation; `evidence_confidence` already returned a reason the draft discarded |
| `overdue: bool = False` | The frontend must not re-derive a date judgement |
| `occurrence: int = 0` | Makes the recurring UI and the stable-ID contract inspectable |
| `provenance: Literal["calculated", "found"]` | An explicit source date performed no arithmetic. `found` is the existing AGENTS.md vocabulary, not a new concept |

**The failure mode to know about:** `Event` is `additionalProperties: false`, and the browser
validates every portfolio response against `shared/openapi.json` with Ajv
(`frontend/src/api.ts`). If the schema is stale relative to the Python, the client rejects the
**entire** portfolio with "The portfolio response does not match the live workspace contract" — the
workspace looks blank or disconnected rather than reporting a schema problem. Regenerate whenever
either phase touches a response model.

`Portfolio.coverage` is `additionalProperties: {type: integer}`, so the three new keys
(`dated`, `dates_unavailable`, `undated`) need no schema change — but they are in
`scripts/export_fixtures.py`, so `shared/portfolio.fixture.json` regenerates.

## 3. Merge order

Per handoff section 7: **merge source first, then regenerate.** Do not hand-merge `shared/*` and do
not resolve a shared file by taking one branch wholesale.

```sh
# 1. resolve Python and TypeScript sources by hand
# 2. then, on the merged tree, with Python 3.12:
.venv/bin/python scripts/export_openapi.py
.venv/bin/python scripts/export_fixtures.py
pnpm --dir frontend api:generate
# 3. run both phase suites
.venv/bin/python -m pytest -q
.venv/bin/python scripts/export_openapi.py --check
.venv/bin/python scripts/export_fixtures.py --check
pnpm --dir frontend api:check
pnpm --dir frontend test
pnpm --dir frontend build
```

Expected after a correct merge: both capability flags independently set, both UI views present,
and the calendar projection **and** conflict counts both surviving in `/api/portfolio`.

## 4. Expected conflict points

Phase 4's footprint on files Phase 5 also edits is **76 insertions, 21 deletions across 7 files**.

| File | What Phase 4 did | Merge note |
|---|---|---|
| `backend/api.py:103` | Added `document_pages()` helper | New function, additive |
| `backend/api.py:114` | `portfolio()` — replaced `events=[]` with a per-document projection loop | **Real conflict likely.** Phase 5 adds conflicts to the same handler. Keep both: the loop, and your `conflicts`/`comparisons` passthrough, which Phase 4 leaves byte-identical |
| `backend/models.py:159` | Four `Event` changes above | Additive |
| `backend/foundation.py:16` | `deadlines=True` | **Combine flags, do not overwrite.** Phase 4 leaves `conflicts`, `handoff`, `sample_workspace` false |
| `backend/evidence.py:74,84` | Added `pages_complete()`, `apply_extraction` now calls it | Behaviour-identical refactor; a pure no-op for Phase 5. No shared helper signature changed |
| `frontend/src/App.tsx:83,86,100` | Added `deadlinesEnabled`, removed `Calendar` from the placeholder map, added the Calendar branch | **Real conflict likely.** Phase 5 adds a Conflicts branch to the same ternary chain and the same `explanation` record |
| `frontend/src/api.ts` | Added `CalendarEvent`/`ReviewIssue` type exports and an optional `as_of` on `fetchLivePortfolio` | Additive; the parameter is optional so existing callers are unaffected |
| `frontend/src/Findings.tsx` | Exported the existing `Evidence` component for reuse | One-word change |

Untouched by Phase 4, as required: `backend/conflicts.py`, `backend/worker.py`, provider prompts,
store comparison methods and the single-worker lock.

## 5. Two behaviour changes in shared code

- **`App.tsx` `refresh()` now aborts and replaces** for as-of changes instead of early-returning
  while a request is in flight. The old behaviour silently dropped a rapid date change, which
  section 5D forbids. The ordinary 3-second health poll still never overlaps.
- **Evidence selection now sets the document as well as the passage.** Previously `Findings` only
  rendered inside an already-selected document, so following evidence never needed to change
  `selectedId`; a calendar link does. Note `openDocument()` clears evidence, so it is deliberately
  not reused for this.

## 6. Known overlap to decide together

**A single rule can produce two review cards.** `backend/evidence.py` already persists an issue with
id `stable_id(doc.id, item.id, "support")` when a deadline rule is unsupported. Phase 4 adds
`stable_id(doc.id, rule.id, "deadline")` for the same rule. Different IDs, so portfolio-level dedup
will not merge them, and both will appear in the review queue.

Phase 4's version deliberately names the missing *arithmetic input* to keep the two
distinguishable, but the overlap is unresolved. It is worth an editorial decision when Phase 6's
review queue lands, rather than a silent duplicate.

**`earliest_offset` direction semantics are undocumented.** With `direction="before"` it must be the
larger number (90 before 60); with `"after"` the smaller. Nothing in `models.py`, the extraction
prompt or the handoff states this. Phase 4 catches a reversed window and raises a review issue, but
**the extraction prompt should state the convention** — that is Builder 1's file, so Phase 4 did not
change it unilaterally.

## 7. Ownership question still open

`PHASE_4_HANDOFF.md` assigns Builder 1 **Phase 5 only** ("Builder 1 / the user owns Phase 5
distribution conflicts"). **Phase 6** — review queue and lawyer briefs — is not assigned to anyone
in that document, and `IMPLEMENTATION_PLAN.md` lists it as planned without an owner. Settle this
explicitly before planning around it.

Phase 4 deliberately stopped short of Phase 6: date-related unresolved items are shown inline in a
calendar review section, not in a dedicated queue, and no brief export exists.

## 8. What Phase 4 has not established

Do not let the merge imply more verification than exists. In full in
[PHASE_4_COMPLETION.md](PHASE_4_COMPLETION.md); the load-bearing ones:

- **The calendar has never run against a real ingested contract** — only synthetic fixtures. There
  was no live model run, and deadline accuracy against a real corpus is Phase 7.
- **Per-input grounding is not verified.** Phase 3 cites a rule as a whole, so Phase 4 cannot confirm
  that `offset`, `unit` and `direction` individually have source support. Every arithmetic-derived
  event is therefore capped at **medium** confidence. Fixing this properly needs an input-evidence
  map in the extraction schema — a shared change to agree before either phase attempts it.
- **Native OCR/DOCX checks were skipped, not passed** (Tesseract and LibreOffice absent on the
  Phase 4 machine).
- **The per-request `pages.json` read was not load-tested at 80 documents.** The handoff blesses a
  read-only projection per request for this scale; it is unmeasured.
