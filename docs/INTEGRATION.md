# Team integration contract · version 1.0

The UI is a local prototype, not an extraction service. Its four sample agreements and all analysis are synthetic. Source previews show page text, not original PDF images. There is no login or durable upload storage in the frontend.

## Ownership and sequence

1. Frontend: `frontend/`. Render validated records, upload files to the API, present evidence and uncertainty.
2. OCR owner (you): accept documents, preserve original files, return page text and scan quality.
3. Extraction owner (agree together): consume OCR pages and identify the seven fields, resolve parties and terms, derive action dates, and attach source quotes. OCR does not do this automatically.
4. Conflict owner (your friend): consume extracted contracts and relevant source pages; return potential conflicts supported by at least two agreements. For the first class, compare exclusivity and competing sales commitments, considering party roles, product, territory, dates, exceptions, and amendments. Do not declare a proven breach from overlapping keywords alone.
5. FastAPI assembly: return a combined portfolio. One of the backend owners must own these HTTP routes and join the module outputs.

Keep work on separate branches when ready. This setup does not create branches, commits, or pushes.

## Shared files

- `shared/types.ts`: language-independent field meanings expressed as TypeScript types.
- `shared/sample-portfolio.json`: complete valid API response, including OCR pages, extracted fields, actions, and a potential conflict. Both Python owners can load this with `json.load`.
- `sample-contracts/*.txt`: synthetic source text matching the sample pages, for inspecting the intended extraction results. These are not PDF or scan test fixtures; create native PDFs and degraded scans separately when implementing OCR.
- `frontend/src/data.ts`: runtime response validation and API calls.

Do not rename fields independently. Change the shared examples/types, frontend validator, and backend implementation together, or bump the schema version.

## HTTP routes

### `POST /documents`

Request: multipart form data containing one `file` field. The frontend sends each selected document separately, keeps per-file results, and retries only failed requests. Supported UI selection: PDF, DOCX, PNG, JPG; nonempty files up to 20 MiB, up to 80 in a batch. The server must enforce its own type, count, and size limits and inspect content, not trust extensions.

Return HTTP 202 (queued) or 200 (ready) and an `OcrDocument`:

```json
{
  "id": "doc-123",
  "filename": "agreement.pdf",
  "status": "queued",
  "pages": [],
  "error": null
}
```

Valid statuses: `queued`, `processing`, `ready`, `failed`. `ready` means text is available, not that obligations have been extracted. On failure, populate `error`. Preserve uploaded bytes server-side. Use a stable ID and consider file hashing for deduplication: an upload that times out may still have succeeded server-side.

Example internal OCR result:

```json
{
  "id": "doc-123",
  "filename": "agreement.pdf",
  "status": "ready",
  "pages": [
    { "number": 1, "text": "Exact page text...", "method": "ocr", "quality": "poor" }
  ],
  "error": null
}
```

Page numbers are one-based, unique within each document, and match original PDF page positions. `method` is `native` or `ocr`; `quality` is `good`, `poor`, or `unknown`. Do not silently merge pages. For DOCX, define a stable rendered page representation before issuing page citations. Native extraction is not proof of good text quality.

### `GET /portfolio`

Return HTTP 200 and exactly the structure illustrated in `shared/sample-portfolio.json`:

```json
{
  "schema_version": "1.0",
  "as_of": "2026-09-05",
  "documents": [],
  "contracts": [],
  "actions": [],
  "conflicts": []
}
```

Keep queued/processing documents in `documents`; add contracts after extraction succeeds. Do not manufacture placeholder analysis for queued documents. The contract library shows documents awaiting extraction. The user refreshes to see processing updates; automatic polling is not implemented.

Use current Singapore calendar date for `as_of` in connected mode. Sample mode intentionally fixes it to 5 September 2026 so dates are reproducible. Use ISO `YYYY-MM-DD` date-only strings. The UI includes today through day 90 inclusive and surfaces overdue actions separately.

### Extraction fields

Each contract has `id`, `document_id`, `name`, `category`, and all seven `fields`: `parties`, `term`, `renewal`, `termination`, `payment`, `liability`, `restrictions`.

Each field contains:

```json
{
  "value": "The extracted obligation in plain language.",
  "basis": "found",
  "confidence": "high",
  "reason": "Why this interpretation is supported, or what remains uncertain.",
  "evidence": [
    { "document_id": "doc-123", "page": 1, "clause": "4.2", "quote": "Exact substring of the source page." }
  ]
}
```

`basis` is independent of confidence: `found` means explicit wording, `inferred` means interpretation or calculation, `unresolved` means not established. Unresolved fields must have `value: null`. Do not treat an absent liability clause as unlimited liability. `confidence` is `high`, `medium`, or `low`; sample labels are illustrative, not calibrated model probabilities. The backend must evaluate confidence against held-out ground truth.

Every found/inferred field needs a nonempty value and at least one citation. Quote strings must match the referenced page exactly, including whitespace. Store a consistent canonical page transcription first. The UI rejects malformed responses and missing/mismatched citations. Matching text proves source presence, not that the interpretation follows from it.

### Action output

Each action contains `id`, `contract_id`, `title`, `due_date`, `event_date` (nullable), `basis`, `confidence`, `reason`, and `evidence`. `due_date` is when action is required, not necessarily the expiry/renewal date. Calculate dates in tested backend code from established terms, checking calendar vs business days and notice delivery provisions. If an action date cannot be established, do not guess it; keep that issue unresolved in the contract field.

### Conflict output

Each potential conflict contains `id`, `title`, `contract_ids` (at least two), `summary`, `question` for a lawyer, `confidence`, and `evidence`. IDs must reference existing contracts. Cite each side of the comparison and relevant qualifications. Use sample `northstar` and `harbour` as the positive example; `cloud` and `studio` are unrelated negative examples. This tiny fixture is an integration test, not an accuracy benchmark.

The initial shared contract holds human-readable field values. The conflict module can use structured internal facts (roles, territory, product and date intervals) but must derive them from these fields and their sources. If you expose those normalized facts between services, agree on a versioned extension rather than inventing frontend-only fields.

The UI exports a JSON review brief from each conflict containing the issue, established facts, document names, source clauses, uncertainty, and the question for a lawyer. It does not decide legal liability.

## Connecting FastAPI

Create `frontend/.env.local` containing `VITE_API_BASE_URL=http://127.0.0.1:8000`, then restart Vite. Blank or unset means sample mode. A configured backend failure displays an error; it never silently substitutes sample results. Never put API secrets in `VITE_*` variables, which are public browser configuration.

Allow the actual Vite origin in FastAPI CORS configuration (normally `http://127.0.0.1:5173`, and `http://localhost:5173` if used). Allow GET/POST and necessary request headers. The current prototype has no credentialed requests or authentication.

Manual integration check:

1. Serve the shared sample JSON at GET `/portfolio`; verify four contract rows, four upcoming actions, one review-needed contract, and one potential conflict.
2. Upload a file; return the queued document record and include it in GET `/portfolio`.
3. Add OCR page text and set the document to ready; the library should show awaiting extraction.
4. Add an extracted contract with valid evidence, refresh, and open its details.
5. Add a conflict with evidence from both contracts, refresh, and download its review brief.
6. Try missing pages, invented quotes, and unreadable clauses; confirm the UI rejects unsupported records or displays unresolved fields rather than claiming certainty.
