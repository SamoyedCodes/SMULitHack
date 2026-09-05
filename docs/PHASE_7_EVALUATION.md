# Phase 7: bounded evaluation and local replay

## Delivered checkpoint — 6 September 2026, Singapore

Evaluation tooling, the ten-document mixed-format corpus, a frozen provisional answer key, offline regression checks and a read-only walkthrough are implemented. **The live evaluation is incomplete:** its first OpenRouter response had no trustworthy usage cost. The campaign stopped before any validated extraction was published. The other nine documents were not sent. This is not an extraction-accuracy or confidence-calibration result.

The user selected ten documents rather than ten requests, `z-ai/glm-5.3-flash` only, a US$14 execution ceiling within US$15 available spending, provisional rather than independent key review, and demo instructions rather than a sample-mode UI. `/api/demo` and `sample_workspace` remain disabled. Builder B's frontend and the pre-existing `DemoResponse` record are preserved. No new public API schema is needed.

## Corpus and frozen reference

`evaluation/answer-key.json` contains 144 explicit expectations across the eight canonical fields: 128 answerable and 16 unresolved/missing-context expectations. Numeric amounts, parties, independent obligations, exceptions, overwritten special conditions and source quotations are recorded. It also contains four keyed date events and four distribution-pair expectations. This is a provisional reference, not a claim of exhaustive independent legal review of every obligation in the long lease.

| ID | Original in sample-contracts | Prepared input | Split |
| --- | --- | --- | --- |
| s01 | northstar.txt | northstar.docx, two rendered pages | Development |
| s02 | cloud.txt | cloud.pdf, two actual image-only scanned pages | Development |
| s03 | harbour.txt | harbour.pdf, two native pages | Development |
| s04 | studio.txt | studio.png, both transcription pages on one image | Development |
| s05 | sample contact 1.pdf | Unchanged eight-page PDF | Development |
| s06 | Singapore lease agreement.pdf | Unchanged ten-page PDF | Development |
| s07 | Exhibit 10.21 - Singapore Lease.pdf | Unchanged 52-page PDF | Development |
| s08 | Exclusive_Distribution_Rights_Agreement.pdf | Unchanged five-page PDF | Holdout |
| s09 | seychelle and confident.pdf | Unchanged three-page PDF | Holdout |
| s10 | seychelle and pacific.pdf | Unchanged three-page PDF | Holdout |

The 75-page `Lease Agreement.pdf` is excluded. Related Meridian fixtures remain together; all three Seychelle-related texts remain together, without treating different corporate names as established aliases. No additional live sample, adversarial rewrite or paid grading call was used.

The manifest records source/input/canonical/page-checkpoint hashes, physical-page mappings and the frozen answer-key hash. All 88 physical pages were processed locally. Eleven page-level source warnings remain in the two public leases. Source warnings are retained. OCR reads the `S$` currency prefix as `$$` in the two synthetic images; visual inspection confirmed the original image wording, and the key explicitly flags the reading discrepancy.

## Reproduce safely

Run from the repository root with the existing Python environment, Node and pinned pnpm. The default isolated directory is `data/phase7`; it is ignored by Git. Do not point the evaluator at the normal application data directory, launch its normal worker, or create a new campaign merely to retry a stopped paid request.

```sh
.venv/bin/python scripts/evaluate.py prepare
.venv/bin/python scripts/evaluate.py freeze --key evaluation/answer-key.json
# Explicit paid step; run only for the authorized campaign:
.venv/bin/python scripts/evaluate.py run
.venv/bin/python scripts/evaluate.py score
```

Preparation and scoring do not call a model. Preparation reuses the real ingestion pipeline, OCR, conversion and original-file storage. Freeze checks all answerable quotations against their physical parsed page before inference. A custom `--root` must be supplied consistently to every command. Failed native preparation can resume its own persisted ingestion batch.

The paid runner reads the existing backend OpenRouter key without copying or printing it. It validates model endpoint metadata, selects and pins an available structured-output endpoint, sets `max_tokens=16384`, disables reasoning and provider fallback, and uses only the OpenRouter class, never the Gemini router. Each request reserves full advertised input context cost plus maximum completion cost at enforced provider price ceilings. The first preflight selected `deepinfra/fp4`, with US$0.075/million input and US$0.25/million output tokens. Pricing is rechecked before starting/resuming, not assumed permanent.

The SQLite `evaluation_requests` ledger commits each reservation before dispatch, accounts for usage before response validation, and reuses saved response envelopes across a crash/cache-write gap. Missing/invalid cost, ambiguous transport results, unexpected model identity or exceeded reservations stop inference. Unknown reservations remain held across restarts. The normal application's provider behavior is unchanged unless the optional budget guard is supplied.

All extraction precedes comparisons. The runner records separate snapshots for established grantor/SME contexts, without inventing aliases. It preserves the existing persistent ten-slot comparison allowance rather than automatically granting more. Unchecked/failed pairs remain visible in `run.json`. There is no automatic retry of a failed provider request or paid rerun to improve scores. Local pacing waits do not send a request. Closed/stopped campaigns make no further network request when `run` is invoked again.

### Saved reports and judgments

- `manifest.json`, `answer-key.json`: frozen campaign identity and reference.
- `workspace/`: isolated SQLite, originals, canonical PDFs, physical pages and provider cache.
- `run.json`, `portfolios.json`: actual outcomes, costs/reservations and date/context snapshots.
- `metrics.json`, `REPORT.md`: group-specific counts, missing results and confidence bands.
- `judgments-template.json`: explicit per-fact and per-finding semantic review slots.

After reviewing real saved outputs, copy the judgment template to a separate local JSON and supply it to `score --judgments PATH`. Each judgment needs a boolean and source-based explanation; fact matches must reference actual non-null findings. Key/run hashes prevent accidentally scoring another run. Unreviewed decisions do not count as passes. Field accuracy requires all keyed facts and additional substantive predictions in that field to pass. Answerable coverage counts answered facts separately from their correctness. Citation validity revalidates quotations, physical pages and coordinates, not meaning. Empty denominators remain not measurable. Date and pair metrics explicitly concern the frozen keyed set; they are not an independently exhaustive corpus benchmark.

Tracked snapshots are available in [recorded metrics](../evaluation/recorded-metrics.json) and [recorded manifest](../evaluation/recorded-manifest.json). They describe this stopped run; a newly prepared corpus gets its own manifest.

## Actual live outcome

The frozen key was prepared before any inference. One HTTP generation request was attempted, for s01. No usable extraction, support-review or comparison result was published. Its response had no trustworthy usage cost, so the campaign halted.

- Confirmed charges recorded: US$0; **this does not establish zero actual spend**.
- Unreconciled maximum reservation: **US$0.082739200**.
- Requests: one; validated extracted documents: zero; further live documents sent: zero.
- Actual total charge remains unknown until the provider's billing record is reconciled.

The first guard version did not retain an error response envelope when usage was absent, so this attempt has no saved HTTP status or generation ID for diagnosis. The guard now saves the local receipt before reading cost, and tests cover missing-cost recovery behavior. The original reservation and stopped state were preserved; no diagnostic generation retry was made. Do not erase the reservation or silently start another campaign. Independent answer-key review, model quality and calibration, and a successful ten-document evaluation remain outstanding.

## Read-only demonstration

Start these two commands in separate terminals:

```sh
AITHENA_API_PORT=8027 AITHENA_WEB_PORT=3027 .venv/bin/python scripts/evaluate.py replay --port 8027
AITHENA_API_PORT=8027 AITHENA_WEB_PORT=3027 pnpm --dir frontend dev
```

Open `http://127.0.0.1:3027`. The replay uses the existing UI and API shapes, starts no worker and rejects every mutation route. Existing UI upload/extraction controls may remain visible, but the replay server refuses their requests. Ctrl+C stops each owned server.

1. Overview shows ten saved documents and a disabled worker. No established dates is an incomplete-analysis warning, not proof of no obligations.
2. Contracts → `cloud.pdf`: select the renewal sentence under Page text and source locations. Its actual scan coordinates highlight. Next shows physical page two.
3. `northstar.docx` shows the stopped extraction and rendered pagination. The other nine remain locally read, unextracted documents.
4. Calendar supports an adjustable Singapore as-of date; use `2026-09-05` for the frozen reference. No live dates were established by this campaign. Conflicts likewise has no evaluated conclusions.
5. Needs review → Page 10 needs source review opens the degraded-plan handoff. Inspect the missing facts and lawyer question, then Print / Save as PDF or Download brief. This source-reading brief correctly has no legal source excerpts attached.

Do not replace missing live findings with the answer key or prototype examples. For this stopped campaign, the walkthrough demonstrates sources, uncertainty and source-review handoff, not successful extraction or semantic conflicts.

## Verification

- 186 backend tests passed across the full suite, the native-conversion retry and the final focused evaluation regressions: the original full run had 180 passes plus one sandbox-blocked LibreOffice test; that native test passed with host permissions; the expanded evaluation suite has 15 passing tests, five added after the full run.
- All 57 frontend tests passed. TypeScript/Vite build and OpenAPI, fixture and generated-type drift checks passed.
- The existing 80-file ingestion test ran locally without inference. Existing offline fixtures exercise OCR/degraded pages, missing schedules, fabricated citations, ambiguous deadlines, conflict exceptions and provider quota/failure behavior.
- New checks cover reservation-before-dispatch, restart accounting, ambiguous/missing/invalid/excess costs, no Gemini fallback, invalid output with charged usage, no eleventh document, pricing prerequisites, stopped/closed campaign replay, mutation refusal, semantic versus citation correctness, ten extractions preceding bounded comparisons using a fake provider, and misleading document instructions remaining in tool-free request data with fabricated-citation rejection. This tests boundaries, not live model resistance to prompt injection.
- Browser verification on `3027 → 8027` confirmed the ten-document library, stopped extraction, real scan image and highlighted renewal sentence, source warnings and a source-review brief. The HTML export function was exercised with that real brief and its standalone output validated locally. Download was clicked in the in-app browser, but its automation download-completion event timed out; native download completion is not claimed.
- No further model requests were made during tests or replay. Linux, Node 22, new independent legal review and live semantic/calibration scores were not verified.

This checkpoint delivers Phase 7 tooling with an explicitly incomplete live evaluation, not the original unrestricted Phase 7 accuracy acceptance gate.
