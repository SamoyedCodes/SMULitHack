# Phase 5 — automatic distribution comparisons

> Integration update: this implementation is now included in the Phase 4–6 merge. See [combined verification](PHASE_4_6_INTEGRATION.md) for the current state and completed integration checks. The original branch-delivery notes below are historical.

Implemented on `codex/phase-5-conflicts`, based on main `011376d` plus provider checkpoint `e69f758`. This branch is deliberately unmerged and unpushed. Phase 4 belongs to Builder 2 and is not included here. See [manual integration notes](PHASE_4_5_MERGE.md).

## Delivered behavior

Selecting an established SME, completing an extraction, or recovering startup automatically screens same-workspace document pairs. Python retains candidates, evidence-backed exclusions, and explicit evidence gaps. Missing extraction, uncertain roles, missing definitions, weak OCR, uncertain renewal and incomplete source coverage never silently establish compatibility. Exclusive and non-exclusive competing grants are included; differently worded scopes remain candidates.

The existing single worker prioritizes ingestion and extraction, then processes only versioned `conflict-v1` jobs. A persistent per-workspace allowance assigns the first ten candidate pair revisions. Continue grants ten more with a UUID idempotency receipt. Uploads, selection changes and restarts do not replenish allowance; cached results and local gaps consume no new slot. Retries reuse their original slot and retain provider cooldowns. Returning to identical previously superseded inputs reuses the assigned job.

`ModelClient.compare()` uses OpenRouter primary and Gemini secondary. It receives complete page-labelled text from both documents, provisions, support reviews and supported Python period comparisons. Combined text above 240,000 characters becomes a local insufficient-evidence issue, without truncation. Actual provider/model/cache/fallback metadata accompanies completed model use.

Python validates both identifiers, exact quotations and contiguous spans, all seven comparison dimensions, each exception's citations, source reliability, missing context, consent conditions and agreement with supported period calculations. Unsupported output becomes a neutral unresolved/low-confidence assessment. Valid semantic findings remain inferred/medium. Neither outcome establishes breach or enforceability. Source quotation matching and a support-review verdict cannot prove semantic correctness.

SQLite initialization is additive. The fingerprint includes sorted complete document descriptors, hashes, checkpoint text, extracted findings/rules/provisions/support, SME, routing identity and conflict version. Old results remain stale history. Current results are rechecked against input revisions during read projection and immediately before publication; obsolete jobs cannot generate a current notification. Portfolio GET does not enqueue work.

The Conflicts screen exposes counts, pending/failure states, Continue/Retry, local screening evidence, historical results, scope and exception evidence, missing facts, specific lawyer questions, provider metadata and links to both source pages. Non-blocking notifications are deduplicated by revision in localStorage, with a persistent navigation count on wide and narrow screens. Conflict review issues are appended to extraction issues. Printable/downloadable briefs remain Phase 6 and disabled.

## Validation, 5 September 2026

- Full backend suite: **113 passed**, including native DOCX conversion, actual OCR/ingestion regression, automatic extraction-to-comparison scheduling, ten-slot persistence, idempotency, retries/cooldowns, stale-result suppression, versioned recovery, context limits and source reliability.
- Frontend suite: **33 passed**. TypeScript/production Vite build passed.
- OpenAPI, fixtures and generated TypeScript drift checks passed; no dependencies added.
- Separate 80-document screening fixture: all **3,160** unordered live pairs represented; **10** assigned and **3,150** unchecked. Sample data stayed isolated. The existing full suite separately runs the Phase 2 80-file ingestion test.
- Separate synthetic answer key: `tests/fixtures/conflict_answer_key.json`, eight cases. All **5/5 expected candidates** survive. Mocked final conflict precision **2/2 (100%)**, recall **2/2 (100%)**. These numbers test fixtures, scheduling and validation, not model reasoning. Responses are constructed mocks; no independent lawyer-reviewed holdout or live-model accuracy claim is made.
- Browser walkthrough used an isolated seven-document synthetic workspace, rendered PDF pages, and a mocked comparison provider. SME selection automatically produced ten current potential findings and notifications, six missing-schedule issues with no new slots, and a paused five-pair backlog. Both source links displayed the correct highlighted PDF clauses. Continue processed the remainder; after dismissing notices, reload produced no repeated notification while the count remained. Narrow-screen navigation retains the conflict count. Provider keys and the user's live documents were not used.

Reproduce automated checks from the repository root:

```sh
.venv/bin/python -m pytest -q
pnpm --dir frontend test
pnpm --dir frontend build
.venv/bin/python scripts/export_openapi.py --check
.venv/bin/python scripts/export_fixtures.py --check
pnpm --dir frontend api:check
```

The implementation machine used its existing dependencies through a worktree symlink and disabled pnpm's automatic dependency reinstallation for these runs (`--config.verify-deps-before-run=false`). A normal clone should install the pinned dependencies as documented in README.

## Remaining boundaries

Live OpenRouter/Gemini access, fallback availability, semantic precision/recall and confidence calibration remain unverified. Unit tests exercise provider routing and cooldowns with mocks. A separate public/synthetic held-out corpus and reviewed model responses are needed before claiming extraction/conflict accuracy.

Identity resolution is deliberately limited to the supported normalized grantor and verbatim SME party evidence. Unestablished aliases/roles are escalated. Temporal renewal/extension/survival/amendment wording is conservative: even a negative or unrelated mention may keep time overlap uncertain. Consent conditions require confirmation and can cause escalation even when a lawyer could resolve them from context. This trades answerable coverage for avoiding unsupported clearance.

Polling currently rechecks local pair fingerprints and sources; it is designed for the stated 80-document laptop corpus, not a hosted multi-user deployment. Browser notification persistence depends on localStorage availability; if storage is blocked, deduplication lasts for the page session. Model-use metadata is present for completed calls, while failed/waiting jobs expose sanitized queue errors rather than a complete per-request audit log.

Phase 4 calendar integration cannot be certified before Builder 2's branch is available. This branch preserves the existing Event schema, disabled Calendar view and portfolio event field. After the manual merge, run both phases' regression suites and explicitly check deadline events/issues plus source navigation. No Phase 6 implementation or lawyer export was included.
