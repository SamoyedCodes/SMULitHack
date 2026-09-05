# CUAD visual OCR smoke test — 6 September 2026

Live access to `google/gemini-2.5-flash-lite` through the configured OpenRouter account succeeded. Five image requests classified eight low-confidence OCR regions as meaningful text. Visual inspection of their source pages agreed with those classifications. No warning was incorrectly cleared in this small sample.

**Provider-reported total cost: US$0.0007286.** All five HTTP responses were 200, identified the requested model and included usage cost. There are no unresolved charges in this separate smoke-test ledger. These are response-reported charges, not an independent billing-statement reconciliation.

## Sample and method

- Enumerated 199 PDFs in `sample-contracts/CUAD_v1`. Selected five documents using Python random seed `20260906` from sorted paths (47 physical pages). Ordinary local parsing produced no OCR warnings.
- A read-only sparse-text inventory found five candidate documents. Three randomly selected candidates added 37 physical pages; ordinary local parsing again produced no OCR warnings. Those extra documents were not sent to a model.
- To exercise OCR, rendered and OCRed two randomly selected pages per original sampled document, using page-selection seed `9122026`. This was a scan simulation over native PDFs, not evidence that the original PDFs were scanned. Ten pages produced 16 low-confidence regions.
- For each of the five original documents, tested the first sampled page with low-confidence regions, taking at most four regions on that page. This yielded eight regions in five requests. Other regions were not visually classified.
- Used the real `VisionClient`, crop rendering, schema validation, warning logic and persistent provider cache. Each request sent the full page plus its flagged crops. Source spans, coordinates and OCR confidence were checked unchanged.
- Used an isolated directory, a five-request limit, conservative per-request reservations and a US$1 reservation ceiling. No contract-extraction or comparison requests were made. No normal application data or stopped Phase 7 campaign state was changed.
- Replayed the same five inputs successfully from the persistent cache with network access sandboxed; the ledger stayed at five requests and the same cost.

## Observed results

| Source | Physical page | Regions | Classification | OCR warning |
| --- | ---: | ---: | --- | --- |
| Rare Element Resources — IP agreement | 7 | 1 | Meaningful text | Retained |
| Prudential Bancorp — endorsement agreement | 1 | 1 | Meaningful text | Retained |
| Midwest Energy Emissions — content licence | 4 | 4 | Meaningful text | Retained |
| Todos Medical — marketing/reseller agreement | 8 | 1 | Meaningful text | Retained |
| PC Quote — co-branding amendment | 1 | 1 | Meaningful text | Retained |

The inspected content included section headings, trademark/termination wording and a `[***]` redaction marker. The model treated the redaction marker as meaningful rather than decorative.

## Limits and saved evidence

This sample contained no actual decorative-logo or diagram regions among the tested crops. It establishes live multimodal access and preservation of meaningful text on these examples; it does not establish logo-detection accuracy, diagram handling, confidence calibration, or full contract-extraction accuracy. All tested warnings remained because the regions were meaningful text.

The isolated local evidence is under `data/vision-cuad-smoke/`: `selection.json`, `sparse-selection.json`, `prepared.json`, `ocr-simulation.json`, `model-endpoints.json`, `requests.json`, five saved response envelopes, `results.json`, the bounded runner and per-document rendered pages/crops. Credentials are not included. This directory is ignored by Git.

The exact original paths, source hashes, selected page numbers and region IDs are retained in those records. The rendered page/crop PNGs can be used to inspect each classification without sending another request.
