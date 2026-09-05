# Phases 4–6 integration checkpoint

The authorized integration combines main `011376d`, Phase 4 `4bc742c`, Phase 5 `dd50bbf` and Phase 6 `9e887f0`. The shared provider prerequisite `e69f758` is retained. Original phase commits remain in history. The integration is intended for local main and GitHub main, as explicitly authorized by the user.

## Combined behavior and compatibility fixes

- Ingestion, extraction, deadlines, conflicts and handoff capabilities are enabled together; sample/demo remains disabled. Builder B's React/Vite design, canonical Pydantic/OpenAPI boundary, relative API proxy and three-second polling remain intact.
- Portfolio reads retain deadline events/coverage, conflict counts/snapshot and all distinct extraction/deadline/conflict issues. A shared read-only deadline projection supplies the same issue IDs to portfolio and brief lookup, including unreadable sources and incomplete analysis.
- Needs review counts each current assessment once. Conflict issue wrappers resolve to the complete assessment brief and are not duplicated in the queue. Historical comparisons remain accessible by ID with a prominent stale warning and are excluded from open counts. Separate support-review and arithmetic-input issues are retained when their questions differ.
- Brief requests retain the selected Singapore as-of date and workspace mode. Changed context cancels outdated requests. Disconnected or refreshing briefs are labeled stale and cannot be printed/downloaded as current. Reconnection reloads the brief.
- Brief source checks reopen parsed checkpoints and revalidate document membership, physical page, spans, quotation and coordinates. Source failures are visible rather than treating an existing empty/corrupt file as valid evidence. Confidence explanations appear on screen and in downloaded HTML. Filenames distinguish documents with identical titles.
- Print output excludes application notifications and source-navigation buttons, preserves warnings, and uses page margins. HTML downloads are self-contained and escaped. Briefs are never automatically sent.
- Processing version is `2026-09-05.6`. Existing records, comparison version/allowance, assigned retry slots and provider cooldowns are preserved. One worker prioritizes ingestion, extraction and then versioned comparisons; old unversioned jobs remain idle. GET requests do not allocate allowance, queue jobs or call a model.
- The accidental Phase 6 `.claude/worktrees/phase-3-extraction` gitlink is excluded from the integrated tree. The actual existing worktree, other builders' branches, unrelated local `.claude/` files, credentials, originals and user data are preserved.

## Verification — 5 September 2026

Environment: macOS, Python 3.12.14, Node 24.19.0, pnpm 11.19.0. Existing dependencies were reused in the isolated integration worktree; no dependency change was required. The worktree's untracked node_modules link is not part of the deliverable.

- **171 backend tests passed across the full run and native retry:** 170 passed in the full sandbox run; its sole failure was LibreOffice conversion permissions. The real mixed-format OCR/DOCX test then passed outside the sandbox. The suite includes the inherited 80-file ingestion test, deadline cases, provider mocks, comparison budgeting/recovery and nine new cross-phase integration regressions.
- **57 frontend tests passed**, including current-only deduplicated counts, selected-date/mode brief requests, cancellation, stale export controls, confidence explanations, HTML escaping and same-title document citations.
- TypeScript and production Vite build passed. OpenAPI, fixture and generated TypeScript drift checks passed using Python 3.12; artifacts were regenerated from combined source rather than hand-merged. Diff whitespace checks passed.
- Browser verification used localhost `3026 → 8026`, seven isolated synthetic agreements, actual rendered PDF pages and a fake provider. It confirmed the November notice action for December expiry under the September horizon, cited arithmetic/highlights, December overdue status, and the unknown invoice trigger.
- Automatic conflict notifications appeared. An intentionally failed comparison succeeded through Retry; Continue processed the remaining candidate backlog without resetting allowance. The completed fixture had 15 current potential comparisons and six local insufficient-evidence assessments. Needs review displayed 71 distinct items, including the fixture's 50 extraction/deadline issues.
- Both brief source buttons opened the appropriate rendered document and highlighted its cited page. Selected `2026-12-01` context reached the brief. Downloaded HTML opened standalone; Print invoked the browser print action and PDF output was rendered/inspected. Notifications and source-action controls were absent from final print output.
- A 390 × 844 viewport and 200% CSS zoom stayed within the viewport. Offline simulation retained visible stale warnings and disabled both export controls; reconnection restored a current brief. Missing-schedule briefs stayed unresolved/low confidence. No browser JavaScript errors were observed.

Reproduce repository checks with the documented runtimes:

```sh
.venv/bin/python -m pytest -q
.venv/bin/python scripts/export_openapi.py --check
.venv/bin/python scripts/export_fixtures.py --check
pnpm --dir frontend api:check
pnpm --dir frontend test
pnpm --dir frontend build
git diff --check
```

Native converters require host permissions. For an integration worktree reusing an existing node_modules directory, pnpm's `--config.verify-deps-before-run=false` avoids reinstalling those dependencies; a normal checkout should use its pinned frozen-lockfile installation.

## Remaining limits

No live OpenRouter/Gemini request, billing/quota verification, semantic accuracy, confidence calibration or independently reviewed holdout is claimed. Calculated deadlines remain capped at medium confidence because the extraction schema does not map each arithmetic input to separate evidence. The extraction convention for earliest notice offsets remains a documented Phase 4 limitation. Quotation matching and source coordinates establish provenance, not legal correctness.

Browser results use constructed source/extraction data and mocked comparisons. They do not establish extraction accuracy on a real ingested corpus. The mobile check and CSS zoom do not substitute for every browser's native zoom or printer settings. Linux and Node 22 were not exercised. Inherited deprecation warnings remain. Phase 7 evaluation/demo, deployment and automatic sending are outside this checkpoint.
