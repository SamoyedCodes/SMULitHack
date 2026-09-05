# Phase 3 integration checkpoint

The local main merge combines Phase 2 checkpoint `f467ea8` with extraction branch `worktree-phase-3-extraction` (`460049c`). The extraction branch was based on Phase 1; taking its worker/UI wholesale would have removed Phase 2 functionality.

## Integration changes

- Preserved local batch/folder ingestion, original hashes, source coordinates/OCR, checkpoint recovery, typed receipts and the single-worker lock.
- Integrated Phase 3 extraction/support review with lazy provider creation and explicit `extract` queue dispatch. Uploads continue local reading without a key. Legacy `document` and future `conflict` jobs remain idle.
- Added an explicit extraction API and UI action, source/model/version cache identity, idempotent queueing, visible key/quota/errors and separate extraction retry. Retrying does not bypass a provider delay. No fallback to another model or paid inference was introduced.
- Kept all eight categories and multiple findings within each category. Evidence links open the exact page and highlight all cited spans. Source-reading issues survive extraction; OCR without a numeric confidence value stays marked OCR.
- Missing pages, source warnings and missing context lower confidence or block machine-rule support. Unsupported rules/provisions generate review issues. SME names must be established in that workspace; no SME is assumed.
- Regenerated canonical API artifacts and added integration regressions. `ingestion` and `extraction` are enabled; deadline/conflict/brief/sample capabilities are false.

## Verification

Final integrated checks passed on macOS / Python 3.12 / Node 24:

- **65 backend tests** passed, including real Tesseract/LibreOffice mixed-format ingestion and the inherited 80-file ingestion test; extraction, citation, missing-context, key/quota, explicit retry and job-isolation checks use synthetic fixtures and a fake provider.
- **28 frontend tests** passed, including retaining multiple payment findings, unresolved categories, explicit extraction requests and runtime response validation.
- Production TypeScript/Vite build, OpenAPI/type drift checks and `git diff --check` passed.
- Browser check on isolated synthetic data confirmed persisted SME selection, multiple findings, unresolved fields, and a payment source link opening physical page 2 with a visible highlight. Browser fake-provider results were never inserted into the user's workspace and no Gemini request was sent.

Dependency deprecation warnings remain in the backend suite. Native tool tests required permission to run outside the filesystem sandbox. No dependency upgrade was included.

No live Gemini key/model availability, free-tier capacity, field accuracy, semantic correctness or confidence calibration is established by these tests. `gemini-3.8-flash` remains a configurable, unverified default. No claim of 85% extraction accuracy is made. The previous branch completion report is preserved as historical context.

## Next work

Builder 2 implements Phase 4 from [PHASE_4_HANDOFF.md](PHASE_4_HANDOFF.md). The user can implement Phase 5 concurrently from the same main baseline. Both must preserve the shared evidence/API contracts and use separate components and focused module ownership. No Phase 4 or Phase 5 implementation is included in this merge.

Source reading cannot currently be rerun beneath an existing extraction job/result; upload a corrected source as a new document when needed. Per-document extraction is explicit, not an automatic batch model run. Dedicated review/brief export remains Phase 6; document detail already exposes extraction issues.
