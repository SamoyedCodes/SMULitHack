# Usability and saved evaluation checkpoint

Implemented 6 September 2026. The existing React/Vite design, canonical API, one worker and evidence validation remain in place. Interaction ideas from the reference implementation were adapted independently; no dependencies were added.

## Delivered behavior

- Overview leads with the Singapore as-of date, document/page coverage and linked action, overdue, conflict and review summaries. Actions distinguish overdue notices, upcoming deadlines and events without action deadlines. Incomplete analysis and outstanding comparisons stay visible; healthy diagnostics are expandable.
- Contracts searches filenames, titles and established parties, filters current processing statuses and review needs, and sorts by name, next action or review count. All matching records remain accessible. Per-document counts use the same deduplicated review selector and backend-projected calendar window.
- Needs review searches questions and missing facts as well as names/titles. Typed reason filters explain uncertainty, with additional missing facts expandable. Existing queue order and historical exclusions are preserved.
- Overview actions focus the exact Calendar event by ID. Existing source controls retain physical-page citations and highlights. Session state preserves the selected date, filters and return focus; disappearing targets show an explanation.
- Evaluation displays a saved benchmark campaign, defaults to Holdout, and separates incomplete coverage, operational failures and explicitly reviewed semantic results. Metrics show denominators; empty denominators are not measurable. Confidence-band errors and up to five reviewed examples never substitute model confidence for human review. Download exports all groups as standalone HTML; app printing uses the selected group.

## Data and read-only interfaces

`ReviewIssue.reason_codes` and optional support-review verdict reasons default to empty lists for old records. Causes are assigned from structured backend decisions, not human-readable error matching. Legacy issues remain unclassified unless their structured kind supplies a category. No database reset, forced extraction or confidence-threshold change is required.

The existing offline score command now writes versioned `scorecard.json` and `SCORECARD.html` alongside `metrics.json` and `REPORT.md`. Frozen run/key identities are retained. Existing scoring definitions are unchanged.

```sh
.venv/bin/python scripts/evaluate.py score
```

`AITHENA_EVALUATION_DIR` selects the saved artifact directory, defaulting to repository-relative `data/phase7`. Evaluation replay selects its explicit campaign directory. `GET /api/evaluation/scorecard` validates saved JSON; `GET /api/evaluation/report` renders self-contained HTML from that same validated data. Optional run-hash and generation-time guards reject a changed report. These routes do not score, initialize storage/campaigns, enqueue jobs or contact providers. Missing artifacts return unavailable; corrupt or unsafe artifacts return sanitized errors.

The existing stopped campaign was scored offline: zero validated extractions, confirmed US$0 and an unresolved US$0.082739200 reservation. Saved run/budget values were checked against the scorecard. The reservation and stopped state were not changed and no inference was retried. Confirmed zero is not proof of zero actual spending.

## Actual verification

- Full combined backend suite: **208 passed**, seven existing warnings, including native OCR/DOCX checks. The four new focused tests also passed after making their fixtures self-contained.
- Frontend: **62 passed** across nine files. TypeScript/Vite production build, OpenAPI/fixture/generated-type drift checks and whitespace checks passed.
- Tests cover old reason defaults/persistence and evidence gates; 80-document search/filter/sort and duplicate titles; deduplication and category defaults; empty/incomplete/stale action presentation; missing targets; scorecard zero/partial/reviewed results; holdout separation; corrupt/missing/unsafe artifacts; snapshot guards; and read-only endpoint behavior.
- Browser checks used an isolated synthetic 80-document API without a worker. Verified exact event focus, physical-page source highlights and return focus, retained library/review filters, brief return, Holdout/All switching, and stale Evaluation export disabling/recovery. Keyboard focus was inspected through these flows. Desktop and 390-pixel mobile layouts had no horizontal overflow.
- Standalone report HTML was rendered and inspected. Download and print controls were exercised. Native file-save completion and a printed PDF were **not verified** because the browser environment did not expose those native surfaces.
- A temporary 200% CSS-zoom preview was visually checked without overflow. Native browser 200% zoom remains **unverified**; CSS zoom is not equivalent verification. This was not a complete accessibility audit.

Concurrent visual-review changes in the shared checkout were preserved and are included in the combined suite totals. These checks establish local behavior, not extraction accuracy, independent answer-key review or confidence calibration. No deployment, paid campaign, automated sending or legal-risk scoring was added.
