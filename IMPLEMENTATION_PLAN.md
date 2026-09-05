# AITHENA implementation phases

Each phase has a separate acceptance boundary. This branch contains Phases 1–3 and Phase 5, with ingestion, extraction and distribution conflicts enabled. Phase 4 remains Builder 2’s independent work; Phase 6 and 7 remain outside this checkpoint. See `docs/PHASE_5_COMPLETION.md` for evidence and limits and `docs/PHASE_4_5_MERGE.md` before manually combining branches.

```mermaid
flowchart LR
    UI[React + TypeScript / Vite] -->|relative /api| API[FastAPI + Pydantic]
    API --> DB[(SQLite + local files)]
    API --> HEALTH[Configuration / readiness / capabilities]
    API -. Phase 2 .-> WORKER[Durable single worker]
    WORKER -.-> PARSE[PyMuPDF / Tesseract / LibreOffice]
    PARSE -. Phase 3 .-> LLM[OpenRouter primary / Gemini secondary]
    LLM -.-> VERIFY[Python evidence validation]
    VERIFY -. Phase 4 .-> DATES[Python deadline engine]
    VERIFY -. Phase 5 .-> PAIRS[Python pair selection]
    PAIRS -.-> COMPARE[LLM semantic comparison]
    COMPARE -.-> CHECK[Python validation / review]
    CHECK -. Phase 6 .-> BRIEF[Lawyer handoff]
```

| Phase | Deliverable | Acceptance boundary |
|---|---|---|
| 1. Runnable foundation | Builder 2's UI shell, local FastAPI, persistent SQLite, truthful health, generated contracts, launcher, tests | No key needed; no processing; disabled routes cannot mutate; schema/build/tests and local proxy work |
| 2. Ingestion and sources — implemented | Batch files/folders, originals/hashes, durable reading jobs, PDF/OCR/DOCX, every page with coordinates | Real clean/degraded scans and DOCX; duplicate/interrupted/error handling; local reading works without API key |
| 3. Grounded extraction — integrated | LLM typed extraction/support review, eight required fields, citation validation, provenance/confidence, SME selection | Every assertion supported; unknowns explicit; quota/key failures visible; no silent truncation |
| 4. Deadline calendar | Python offsets/windows/recurrence and 90-day event-or-action selection | Exact deadline fixtures pass; unknown triggers, business days and month-end ambiguity escalate |
| 5. Distribution conflicts — implemented on separate branch | Python candidates plus LLM scope/exception comparison, validated assessments | Exclusive/non-exclusive overlaps, exclusions, non-overlapping dates and missing schedules evaluated; no breach claims |
| 6. Review and lawyer briefs | Review queue, cited issue summaries, missing facts and specific questions, printable/downloadable handoff | Lawyer can locate clauses and act on the issue; no automatic sending |
| 7. Evaluation and demo | Real synthetic mixed-format corpus, reviewed answer key/holdout, measured accuracy/calibration, 80-file load test | Report actual field/citation/date/conflict metrics; planted unanswerable cases escalate; no hidden failures |

Use the existing React/Vite frontend and its lockfile. This pulled repository supersedes the older Sites/Vinext frontend described in the initial handoff; there is no need to replace the frontend framework or deploy it. The Python API and generated records remain the compatibility boundary for all later phases.
