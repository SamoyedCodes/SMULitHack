# Optional visual review of OCR noise

The extraction screen offers **Review low-confidence scans with AI** for documents containing OCR. Select it before **Extract obligations**. The option also permits re-extraction of an already analyzed document. Uploading, local reading, ordinary extraction with the option unchecked, and the Phase 7 evaluator do not invoke the vision model. The stopped evaluation reservation is unchanged.

Keep the extraction model and add a separate vision model in the root `.env` file:

```dotenv
OPENROUTER_MODEL=z-ai/glm-5.3-flash
OPENROUTER_VISION_MODEL=google/gemini-2.5-flash-lite
```

The existing `OPENROUTER_API_KEY` is reused; no Google key is needed for this OpenRouter route. The vision model shown above is also the default if the new variable is omitted. Restart the backend after configuration changes. No credentials or `.env` changes are included in this implementation.

On 6 September 2026, [OpenRouter listed Gemini 2.5 Flash Lite](https://openrouter.ai/google/gemini-2.5-flash-lite/pricing) at US$0.10/million input tokens (including image input) and US$0.40/million output tokens. The visual request enforces those prompt/completion price ceilings, caps output at 1,600 tokens, and disables provider fallback and reasoning. A different configured model must fit these ceilings. Actual charges depend on image tokenization and response length; these limits are not a prepaid or aggregate dollar budget.

## Processing and evidence

- PyMuPDF renders the stored canonical PDF directly. Each request includes a full-page overview and up to four padded close-up crops, identified by existing span IDs and physical-page coordinates. Crop rendering follows page rotation and validates coordinates. No browser screenshots or new dependencies are required.
- A document reviews at most 24 flagged regions in physical-page order. A page may require several requests; a document with one flagged region on each of 24 pages can require 24 requests. Unreviewed regions keep their warning and a limit note. Purely unreadable pages with no OCR spans remain unresolved.
- Images are constructed in memory. The original PDF, spans, coordinates, OCR confidence, visual classifications and model names remain local. Successful model responses use the existing persistent cache, keyed by images, OCR context, model, prompt/version and schema. The images themselves are sent to OpenRouter and its provider when the user selects visual review.
- Only a `decoration` classification with `contains_meaningful_content=false` can downgrade its OCR warning. All low-confidence regions on that page must qualify before the page-wide low-OCR warning is removed. The source viewer retains an **AI inference** label, reason and model next to each original OCR block.
- A company name inside a logo is meaningful text. Labels, signatures, stamps, plans, maps, charts, mixed graphics/text, and uncertain regions retain source review. Other page warnings are never removed. Missing, duplicate or invented span IDs invalidate the whole response group.
- No source text is corrected or dropped, and no evidence-confidence score is raised. Classification is an uncalibrated model judgment, not proof that a region is irrelevant. Existing citation and conflict checks continue to inspect the original OCR.
- The existing durable extraction job saves the opt-in. Local request pacing can resume using cached results. Provider errors, refusals, truncation, transport timeouts and invalid output stop that visual attempt and retain source warnings, without switching models. A persisted completion marker prevents later text-extraction quota waits from repeating the visual attempt. New explicit attempts may retry failures.

## Verification

`tests/test_visual_review.py` exercises real rendered PDF crops at all four right-angle rotations, classification gating, original evidence/confidence preservation, persistent cache reuse, malformed output and provider failures, the region limit, API opt-in persistence and the default text-only worker path. HTTP responses are synthetic; there are no paid requests in these tests.

Recorded checks on 6 September 2026: 18 visual-review cases passed within a final 66-test run covering visual review, providers, extraction-worker and evaluation regressions. The full backend run before the final two quota-resume regressions had 204 passes and one sandbox-blocked LibreOffice conversion; that native test passed with host permissions. All 58 frontend tests, the TypeScript/Vite build, generated API/schema/fixture checks and diff whitespace checks passed. Other concurrent workspace changes were preserved. No interactive browser verification is claimed for the new checkbox or annotations.

The subsequent [CUAD smoke test](VISUAL_OCR_CUAD_SMOKE.md) verified live access: five requests classified eight simulated-scan text regions, with a provider-reported total of US$0.0007286. Cache replay made no additional requests. Actual decorative-logo and diagram accuracy remain unverified because those categories were absent from the tested regions. The frozen Phase 7 data and campaign were not modified or rerun.
