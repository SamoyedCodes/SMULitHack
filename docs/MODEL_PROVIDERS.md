# Model providers — OpenRouter primary, Gemini secondary

This provider change follows the Phase 3 merge. It does not enable deadline/conflict processing or change grounding requirements. Configure credentials in the repository-root `.env` on the backend only; never put them in `VITE_*` variables, browser storage, fixtures or committed files.

```dotenv
OPENROUTER_API_KEY=your-openrouter-key
OPENROUTER_MODEL=openrouter/free
GEMINI_API_KEY=your-existing-gemini-key
GEMINI_MODEL=your-supported-gemini-model
```

`OPENROUTER_MODEL` defaults to `openrouter/free`. `GEMINI_API_KEY` retains the existing `GOOGLE_API_KEY` alias. `GEMINI_MODEL` retains the previous configurable default, `gemini-3.8-flash`, whose availability has not been verified; set a model available to your account. Restart the local service after changing configuration. Keep a provider's key absent if you do not want that provider used.

The [OpenRouter free router](https://openrouter.ai/docs/guides/routing/routers/free-router) chooses an available free model compatible with requested features. Selection can vary between calls. Pin a supported `:free` model for a repeatable model choice during evaluation. Changing `OPENROUTER_MODEL` to a paid model is an explicit configuration choice; the application never automatically upgrades a model or buys credits. Gemini uses only your configured secondary account/model; this application cannot verify that account's billing or remaining free quota.

## Routing behavior

| Condition | Behavior |
|---|---|
| OpenRouter returns a complete schema-valid answer | Use OpenRouter; do not call Gemini |
| OpenRouter key missing, HTTP 401/402/404 | Try configured Gemini; show a secondary-use reason on the saved result |
| OpenRouter network/timeout, 429 or 500/502/503/504 | Persist its cooldown, try Gemini, and do not retry OpenRouter before the delay expires |
| Local `AITHENA_LLM_INTERVAL` pacing | Wait for that provider; do not switch merely to bypass pacing |
| Both unavailable without a retryable condition | Job is blocked/awaiting configuration with a visible message |
| One/both waiting and no usable fallback | Job waits until a provider can be retried; provider cooldowns persist across restart |
| Malformed JSON/schema, incomplete answer, refusal, 400/403 | Fail visibly; do not ask a second provider to bypass an invalid or refused answer |
| Matching validated cached result | Reuse it and mark it cached; no inference call |

A successful extraction or support-review response still passes the existing Python citation checks, completeness gates and uncertainty handling. Schema validation and a second model pass do not establish legal truth or calibrated accuracy.

OpenRouter requests use `https://openrouter.ai/api/v1/chat/completions`, an authorization header, no redirects, a 120-second HTTP timeout, JSON Schema structured output and `provider.require_parameters=true`. See the [structured-output requirements](https://openrouter.ai/docs/guides/features/structured-outputs). Both HTTP failures and errors within a 200 response are checked; retry delays honor numeric or HTTP-date `Retry-After` headers as described in [OpenRouter error handling](https://openrouter.ai/docs/api/reference/errors-and-debugging). There are no new dependencies: the adapter uses existing `httpx`; Gemini retains the Google SDK.

Original files and source processing stay local. Explicit extraction sends page text to OpenRouter and its selected model provider, or to Gemini as secondary. The UI explains this before the extraction action. Neither readiness checks nor local uploads call a provider. The launcher strips all three provider-key variables from its frontend child environment.

## Shared interfaces for Builders 1 and 2

- `backend.llm.ModelClient(config, store)` is the active entry point. Its `extract`, `review`, `compare` signatures are unchanged. `Gemini` remains the direct secondary adapter; do not instantiate it for new analysis orchestration.
- The single durable worker creates ModelClient lazily. No extra worker or server is introduced. Future Phase 5 comparison jobs should use that same entry point and retain capability gating.
- `Document.model_usage` is an additive default-empty list of `ModelUse`: `provider`, `requested_model`, returned `model`, `purpose`, `cached`, nullable `fallback_reason`. The worker persists it after each successful extraction/review call. `Document.model` summarizes actual providers/models once calls succeed. Old records remain readable and are not rewritten merely by a health check.
- `ModelClient.last_use` carries the latest response metadata. Phase 5 should save it with its own assessment provenance when that phase adds comparison execution. Provider metadata is separate from finding confidence and source evidence.
- `HealthResponse.providers` reports the two roles, requested models and key presence as configured but unverified. Legacy `key_configured` means at least one key is configured; legacy `model` reports the primary requested model. No key material is serialized.
- Response cache identities contain processing version, provider, requested model, purpose, input and schema. Cache envelopes also preserve the returned actual model, including a free-router selection. Extraction job identities include both configured model identities. Primary and secondary caches cannot collide.
- Calendar calculations remain entirely local and must not import/call ModelClient. These additions preserve the Phase 4/5 handoff's existing date/source interfaces.

## Verification boundary

Tests stub HTTP/SDK calls. They cover primary preference, configured/missing secondary access, fallback provenance, provider-specific caches, cooldown persistence, local pacing, retry headers, errors in HTTP 200 responses, refusal/truncation/malformed-answer handling, secret-free health and saved worker metadata. The existing ingestion, extraction, UI and schema/build suites are also required.

No live OpenRouter/Gemini model access, quota, billing, extraction quality or semantic accuracy is claimed. A free-router selection can differ across calls; pin and evaluate a model before reporting quality scores.

Verified locally: **90 backend tests and 29 frontend tests passed**, including native mixed-format/80-file ingestion regression checks. TypeScript/Vite production build, OpenAPI and fixture drift checks, generated API type check and `git diff --check` passed. Provider tests used mocked responses; no live inference requests were made.
