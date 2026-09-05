# Phase 4 — grounded deadline calendar (checkpoint notes)

> Integration update: this implementation is now included in the Phase 4–6 merge. See [combined verification](PHASE_4_6_INTEGRATION.md) for the current state and completed integration checks. The original branch-delivery notes below are historical.

Built on branch `codex/phase-4-deadlines` from merged `main` (`011376d`), which contains Phase 2
checkpoint `f467ea8` and Phase 3 extraction `460049c` in its ancestry (verified before starting).
Phase 5 conflict work is proceeding concurrently on a separate branch and was not touched.

## Implemented

- **Deterministic engine** (`backend/deadlines.py`, previously an inactive draft imported by
  nobody). The public entry point `calendar_for(doc, pages, as_of, days=90)` is unchanged. Repaired:
  - **All occurrences, not one.** The draft advanced `while event_date < as_of` and emitted a single
    occurrence per rule. Occurrences are now enumerated over a bounded scan window with asymmetric
    margins — `direction="before"` extends forward (a later event can still act inside the horizon),
    `direction="after"` extends backward (a past trigger's action can be ahead of us). Indices are
    solved arithmetically in month space rather than walked from the anchor, so a 1990 anchor costs
    the same as a 2026 one.
  - **Past triggers are no longer skipped.** A recurring `direction="after"` rule whose previous
    occurrence acts inside the horizon is retained (regression covered by a test).
  - **Occurrence-stable IDs.** `stable_id(doc.id, rule.id, rule.event_date, occurrence)` — a
    function of the contract alone, so IDs do not move when the as-of filter does.
  - **Reproducible ordering** by earliest relevant date, then event date, then ID.
  - Anchor-derived recurrence (already correct in the draft) preserved: Jan 31 → Feb 28 → **Mar 31**,
    with no compounding drift.
- **Competence gates before any date is emitted.** Citations revalidated against saved pages; the
  support verdict must be `supported` **with no unresolved `missing_context`** (the draft ignored
  `missing_context` — a spec violation against §5B); declared `missing_inputs` block; a counting
  unit of `business_days`/`unknown` is refused **before** enumeration, or an out-of-range occurrence
  would have hidden the gate entirely; ambiguous month-end raises. Every failure becomes
  `ReviewIssue(kind='deadline')` naming the missing fact and a question that identifies the
  convention, not "consult a lawyer". A rule that fails on any occurrence emits **no** events for
  that rule — a schedule with a hole is indistinguishable from a complete one.
- **`established` no longer repeats model prose.** The draft wrote
  `f"Source identifies a date rule for {rule.trigger}."`, asserting an unvalidated model label.
  It now carries only Python-verified facts: quotes matched to source spans, the parsed anchor, and
  the recorded verdict status.
- **Confidence inheritance.** Weakening is monotone. Calculated dates are capped at **medium**
  (see Limits), incomplete page coverage caps at low, and recurrence projection, unresolved
  conditions and overdue status each cap at medium. Every weakening cause is also appended to
  `Event.assumptions`, so a cause that loses the band race is still shown rather than hidden.
- **Portfolio wiring** (`backend/api.py`). `events` was hardcoded `[]`. It now runs a read-only
  projection per request: no model call, no queued work, no stored record changed, and no document
  directory created (`source_path` already resolves with `create=False`). Failures are isolated per
  document — an unreadable page checkpoint yields a document-specific issue and a coverage count
  while every other document still reports. `conflicts`, `comparisons`, `sme` and `parties` are
  passed through untouched for Phase 5. Issues are deduplicated by stable ID, persisted issues
  first. `HORIZON_DAYS` is a single constant feeding both `horizon_end` and the engine, so the
  advertised horizon cannot drift from the filter.
- **Additive model fields**, agreed with the user before implementing: `Event.confidence_reason`,
  `Event.overdue`, `Event.occurrence` (all defaulted) and `Event.provenance` widened to
  `Literal["calculated", "found"]`. `found` is the existing AGENTS.md vocabulary for an explicit
  source date, so an unshifted first occurrence no longer claims arithmetic it did not perform.
  Events are never persisted, so there is no stored-data migration.
- **Coverage keys** `dated`, `dates_unavailable`, `undated` added (`Portfolio.coverage` is
  `additionalProperties: integer`, so no schema break) to distinguish "checked and found nothing"
  from "not checked".
- **Frontend** (`frontend/src/Calendar.tsx`, `calendar.test.tsx`, one appended CSS block). Adjustable
  as-of date, visible Singapore horizon, events grouped by actionable date with event date, action
  deadline, window boundaries, overdue and conditional status, the formula, assumptions, the
  confidence explanation and source buttons. Overview gained a next-actions list. Unresolved date
  items appear in a calendar review section in this phase, since the dedicated queue is Phase 6.
  Existing `.calendar-row` / `.date-tile` / `.action-row` design language and the exported
  `SourceViewer` were reused; no second date engine exists in the browser.
- **Two shell fixes** required by §5D: `refresh()` early-returned while a request was in flight, so a
  rapid as-of change was silently dropped — it now aborts and replaces for as-of changes while the
  3-second health poll still never overlaps. Evidence selection now sets the document as well as the
  passage, so a calendar link opens the right document at the right page.
- **`CAPABILITIES.deadlines` enabled last**, after engine, API and UI passed. `conflicts`, `handoff`
  and `sample_workspace` remain false.

`backend/evidence.py` gained `pages_complete(doc, pages)`, extracted verbatim from `apply_extraction`
so Phase 4 reuses the completeness predicate instead of duplicating it. Behaviour is unchanged;
Builder 1 sees a no-op. No shared helper signature was altered.

## Checks actually run (this environment)

| Check | Result |
|---|---|
| `.venv/bin/python -m pytest -q` | **105 passed, 2 skipped** (baseline before this work: 63 passed, 2 skipped) |
| New `tests/test_deadlines.py` | 33 passed — engine, gates, confidence |
| New `tests/test_portfolio_deadlines.py` | 9 passed — API wiring, isolation, side-effect freedom |
| `scripts/export_openapi.py --check` | in sync |
| `scripts/export_fixtures.py --check` | in sync |
| `pnpm --dir frontend api:check` | in sync |
| `pnpm --dir frontend test` | **42 passed** (baseline: 28) |
| `pnpm --dir frontend build` (`tsc -b && vite build`) | passed |
| `git diff --check` | clean |
| Browser walkthrough (isolated synthetic data) | passed — see below |

The 2 skips are the native Tesseract/LibreOffice integration tests. **Neither tool is installed on
this machine, so those native checks were skipped, not passed.**

### Browser walkthrough

Run against an isolated synthetic workspace under a scratch `AITHENA_DATA_DIR`; the repository's real
`data/` workspace was never written to and no synthetic result entered it. Two invented agreements:
a grounded renewal notice and an invoice-payment rule whose receipt date is deliberately unrecorded.

- As-of `2026-09-05` (horizon `2026-12-04`): the notice event shows **2026-11-01**, labelled
  "Notice must be received", with `2026-12-31 − 60 calendar days = 2026-11-01` displayed — the
  31 December expiry is 27 days beyond the horizon and the action is still surfaced.
- Following its evidence link opened the northstar document and jumped the source viewer to
  **page 2 of 2** with the cited span and clause 8.3 shown. The page image was reported unavailable
  because the synthetic fixture has no rendered PDF; the UI states this rather than failing silently.
- Changing the as-of date to `2026-12-01` re-projected to the `2026-12-01 → 2027-03-01` horizon and
  marked the November notice **"Overdue · performance not established"**, stating that whether the
  action was performed, waived or varied is not established, and that whether late or alternative
  notice would still be effective is not established. No wording asserts the renewal can still be
  cancelled.
- The unanswerable invoice rule appears under "Dates that could not be established" with its
  established quote, the missing fact, and the question *"On what date was the invoice received, and
  how is receipt evidenced?"* beside its clause 5.2 citation.
- At a 375 × 812 viewport the page does not scroll horizontally, calendar rows wrap and the as-of
  control stays usable.

## Environment note

`AGENTS.md` specifies Python 3.12. This machine initially had only 3.13, and 3.13 renamed the HTTP
413/422 reason phrases, which made `scripts/export_openapi.py --check` fail on the **untouched**
baseline and would have injected 30 unrelated lines into `shared/openapi.json` — a generated file
Builder 1 also regenerates. Python 3.12.14 was installed and the virtualenv rebuilt on it, after
which the baseline check passed and the regenerated contract diff contains only Phase 4 changes.
Anyone regenerating these artifacts must use Python 3.12. `pnpm` is not installed system-wide here;
a local `.bin/pnpm` shim wrapping `npx pnpm@11.19.0` was used and is untracked scaffolding, not part
of the deliverable.

## Limits — do not overstate

- **Per-input grounding is not verified.** Phase 3 attaches citations to a `DeadlineRule` as a whole.
  Phase 4 confirms the rule is cited and support-reviewed, but **cannot confirm that `offset`,
  `unit`, `direction` and `month_end_rule` individually have source support** — an input-evidence map
  would change the extraction schema Builder 1 also consumes, which is out of scope. Because of this,
  every arithmetic-derived event is capped at **medium** confidence and carries an assumption saying
  so. This is the largest honesty gap in the phase.
- **No live model run and no measured accuracy.** The engine makes no model call by design, and every
  test uses synthetic fixtures. Deadline accuracy against a real corpus is Phase 7, not established
  here. Gemini access, model availability and quota remain unverified.
- **Overdue bound is a display window, not a legal position.** Overdue actions are shown when their
  event still falls inside the horizon, plus a bounded 90-day lookback for lapses whose event has
  passed (the value agreed with the user, symmetric with the forward horizon). Older lapses are not
  shown. An overdue label claims only that a scheduled date precedes the selected date; it never
  claims the action was missed, a payment is unpaid, a breach occurred, or delivery failed.
- **`earliest_offset` direction semantics are undocumented** in the model and the extraction prompt:
  with `direction="before"` it must be the larger number, with `"after"` the smaller. A reversed
  window is caught and raised as a review issue, but the prompt should state the convention. Flagged
  for Builder 1; the prompt was not changed unilaterally.
- **Duplicate review cards are possible.** `evidence.py` already persists a `"support"` issue when a
  deadline rule is unsupported, and Phase 4 adds a `"deadline"` issue for the same rule under a
  different ID, so both can appear. The deadline issue names the missing arithmetic input to keep
  them distinguishable, but the overlap is not resolved.
- **Per-request page reads are unoptimised.** The projection reads `pages.json` for every analyzed
  document on each portfolio GET. The handoff blesses this for an 80-document local MVP; it was not
  load-tested at 80 documents with large checkpoints in this phase.
- **Page-coverage gate is currently unreachable through the normal path**, because extraction already
  marks a rule `uncertain` when coverage is incomplete, so the verdict gate fires first. It is kept
  as defence in depth and tested by constructing the document directly.
- Unit and browser coverage do not establish extraction correctness, confidence calibration, or that
  any obligation shown is enforceable. Python cannot establish enforceability, breach, delivery
  success, continued operation, or that a payment remains unpaid.

## Merging with Phase 5

Coordination items, expected conflict points and the regeneration order are in
[PHASE_4_MERGE_NOTES.md](PHASE_4_MERGE_NOTES.md). Read it before merging — in particular the
Python 3.12 requirement for regenerating `shared/*`, and the fact that a stale `openapi.json`
makes the browser reject the entire portfolio response rather than reporting a schema error.

## Not done (deliberately out of scope)

Conflict assessment, lawyer-brief export, sample loading, legal chat and deployment are untouched.
`backend/conflicts.py`, `backend/worker.py`, provider prompts and the single-worker lock were not
modified. Nothing has been committed or pushed; the branch holds the working tree only.
