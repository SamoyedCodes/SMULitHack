from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_serialization_defaults_required=True)


class FieldName(StrEnum):
    PARTIES = "parties"
    TERM = "term"
    RENEWAL = "renewal"
    NOTICE = "notice"
    TERMINATION = "termination"
    PAYMENTS = "payments"
    LIABILITY = "liability"
    RESTRICTIONS = "restrictions"


FIELD_LABELS = {
    "parties": "Parties", "term": "Term", "renewal": "Renewal mechanics",
    "notice": "Notice requirements", "termination": "Termination rights",
    "payments": "Payment obligations", "liability": "Liability caps and exceptions",
    "restrictions": "Exclusivity and restrictive covenants",
}


class Span(Record):
    id: str
    document_id: str
    page: int
    text: str
    bbox: list[float]
    source: Literal["native", "ocr"]
    ocr_confidence: float | None = None
    clause: str | None = None


class VisualRegionReview(Record):
    span_id: str
    kind: Literal["decoration", "text", "diagram", "uncertain"]
    contains_meaningful_content: bool
    reason: str = Field(min_length=1, max_length=800)
    model: str


class Page(Record):
    number: int
    width: float
    height: float
    spans: list[Span] = Field(default_factory=list)
    status: Literal["read", "unreadable", "error"] = "read"
    warnings: list[str] = Field(default_factory=list)
    visual_reviews: list[VisualRegionReview] = Field(default_factory=list)
    visual_review_note: str | None = None


class Citation(Record):
    document_id: str
    span_ids: list[str]
    quote: str


class Evidence(Record):
    document_id: str
    span_ids: list[str]
    quote: str
    page: int
    clause: str | None = None
    boxes: list[list[float]]
    source: Literal["native", "ocr"]
    ocr_confidence: float | None = None


class Assertion(Record):
    id: str
    citations: list[Citation] = Field(default_factory=list)


class FindingDraft(Assertion):
    field: FieldName
    value: str | None
    party: str | None = None
    conditions: list[str] = Field(default_factory=list)
    inferred: bool = False


class DeadlineRule(Assertion):
    label: str
    event_type: Literal["expiry", "renewal", "payment", "termination", "other"]
    event_date: str | None = None
    trigger: str
    action: Literal["notice_received", "notice_sent", "payment_due", "review", "expiry"]
    offset: int | None = Field(default=None, ge=0, le=36500)
    earliest_offset: int | None = Field(default=None, ge=0, le=36500)
    unit: Literal["calendar_days", "calendar_months", "business_days", "unknown"] = "calendar_days"
    direction: Literal["before", "after"] = "before"
    recurrence_months: int | None = Field(default=None, ge=1, le=1200)
    month_end_rule: Literal["last_day", "unspecified"] = "unspecified"
    conditions: list[str] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)


class CommercialProvision(Assertion):
    grantor: str | None = None
    beneficiary: str | None = None
    activity: str
    kind: Literal["distribution", "other", "unknown"]
    exclusive: bool | None = None
    product: str | None = None
    territory: str | None = None
    channel: str | None = None
    customers: str | None = None
    starts_on: str | None = None
    ends_on: str | None = None
    exceptions: list[str] = Field(default_factory=list)
    missing_context: list[str] = Field(default_factory=list)


class Extraction(Record):
    title: str
    parties: list[str] = Field(default_factory=list)
    findings: list[FindingDraft] = Field(default_factory=list)
    deadlines: list[DeadlineRule] = Field(default_factory=list)
    provisions: list[CommercialProvision] = Field(default_factory=list)
    missing_context: list[str] = Field(default_factory=list)


ReviewReason = Literal["source_unreadable", "missing_context", "ambiguous_terms", "unsupported_evidence", "incomplete_analysis", "not_established"]


class Verdict(Record):
    item_id: str
    status: Literal["supported", "uncertain", "rejected"]
    reason: str
    reason_codes: list[ReviewReason] = Field(default_factory=list)
    missing_context: list[str] = Field(default_factory=list)


class SupportReview(Record):
    verdicts: list[Verdict]


class Finding(Record):
    id: str
    field: FieldName
    value: str | None
    party: str | None = None
    conditions: list[str] = Field(default_factory=list)
    provenance: Literal["found", "calculated", "inferred", "unresolved"]
    confidence: Literal["high", "medium", "low"]
    confidence_reason: str
    evidence: list[Evidence] = Field(default_factory=list)


class ReviewIssue(Record):
    reason_codes: list[ReviewReason] = Field(default_factory=list)
    id: str
    document_ids: list[str]
    title: str
    established: list[str] = Field(default_factory=list)
    missing_facts: list[str] = Field(default_factory=list)
    lawyer_question: str
    urgency: str = "Review before relying on this provision."
    evidence: list[Evidence] = Field(default_factory=list)
    kind: str = "uncertainty"
    mode: Literal["live", "sample"] = "live"


class Event(Record):
    id: str
    document_id: str
    label: str
    event_type: str
    event_date: str
    action_date: str | None
    window_start: str | None = None
    action: str
    formula: str
    assumptions: list[str]
    confidence: Literal["high", "medium", "low"]
    confidence_reason: str = ""
    evidence: list[Evidence]
    # Overdue is a calendar comparison against the selected date, never a finding of non-performance.
    overdue: bool = False
    occurrence: int = 0
    # "found" is an explicit source date; "calculated" means arithmetic ran on cited inputs.
    provenance: Literal["calculated", "found"] = "calculated"


class ConflictDraft(Record):
    status: Literal["potential_conflict", "no_conflict_identified_for_this_rule", "insufficient_evidence"]
    documents: list[str]
    scope_comparison: dict[str, str]
    dimension_citations: dict[str, list[Citation]] = Field(default_factory=dict)
    exception_citations: list[list[Citation]] = Field(default_factory=list)
    time_overlap: Literal["yes", "no", "unknown"] = "unknown"
    citations: list[Citation]
    exceptions: list[str]
    missing_facts: list[str]
    explanation: str
    lawyer_question: str


class ConflictAssessment(Record):
    id: str
    status: Literal["potential_conflict", "no_conflict_identified_for_this_rule", "insufficient_evidence"]
    documents: list[str]
    scope_comparison: dict[str, str]
    evidence: list[Evidence]
    exceptions: list[str]
    missing_facts: list[str]
    explanation: str
    lawyer_question: str
    confidence: Literal["medium", "low"]
    confidence_reason: str
    provenance: Literal["inferred", "unresolved"]
    mode: Literal["live", "sample"] = "live"
    input_revision: str = ""
    created_at: str = ""
    current: bool = False
    dimension_evidence: dict[str, list[Evidence]] = Field(default_factory=dict)
    exception_evidence: list[list[Evidence]] = Field(default_factory=list)
    model_usage: list[ModelUse] = Field(default_factory=list)


class BriefDocument(Record):
    id: str
    title: str
    filename: str


class Brief(Record):
    id: str
    source: Literal["issue", "conflict"]
    kind: str
    mode: Literal["live", "sample"] = "live"
    generated_at: str
    as_of: str
    title: str
    documents: list[BriefDocument] = Field(default_factory=list)
    established: list[str] = Field(default_factory=list)
    missing_facts: list[str] = Field(default_factory=list)
    lawyer_question: str
    urgency: str = "Review before relying on this provision."
    explanation: str | None = None
    scope_comparison: dict[str, str] = Field(default_factory=dict)
    exceptions: list[str] = Field(default_factory=list)
    provenance: str
    confidence: str | None = None
    confidence_reason: str | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    coverage_warnings: list[str] = Field(default_factory=list)
    disclaimer: str = ("This brief summarizes grounded source evidence for human legal review. "
                       "It is not legal advice, does not assert breach or enforceability, and was not sent anywhere automatically.")


class ModelUse(Record):
    provider: Literal["openrouter", "gemini"]
    requested_model: str
    model: str
    purpose: str
    cached: bool = False
    fallback_reason: str | None = None


class Document(Record):
    id: str
    filename: str
    title: str
    sha256: str
    mode: Literal["live", "sample"]
    status: str = "queued"
    stage: str = "Waiting to process"
    error: str | None = None
    page_count: int = 0
    pages_read: int = 0
    pages_analyzed: int = 0
    has_ocr: bool = False
    pagination: str = "original"
    parties: list[str] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    model_usage: list[ModelUse] = Field(default_factory=list)
    rules: list[DeadlineRule] = Field(default_factory=list)
    provisions: list[CommercialProvision] = Field(default_factory=list)
    reviews: list[Verdict] = Field(default_factory=list)
    issues: list[ReviewIssue] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    created_at: str
    model: str
    version: str


class ConflictScreen(Record):
    id: str
    documents: list[str]
    mode: Literal["live", "sample"]
    outcome: Literal["candidate", "excluded", "needs_evidence"]
    reason: str
    evidence: list[Evidence] = Field(default_factory=list)
    missing_facts: list[str] = Field(default_factory=list)
    priority: int = 1
    current: bool = True
    job_state: str | None = None
    error: str | None = None


class ConflictScan(Record):
    state: Literal["disabled", "awaiting_sme", "ready", "running", "paused", "needs_review"] = "disabled"
    allowance: int = 10
    assigned: int = 0
    total_pairs: int = 0
    unscreened: int = 0
    candidates: int = 0
    excluded: int = 0
    needs_evidence: int = 0
    unprocessed_documents: int = 0
    completed: int = 0
    unchecked: int = 0
    queued: int = 0
    running: int = 0
    waiting: int = 0
    blocked: int = 0
    failed: int = 0
    can_continue: bool = False


class Portfolio(Record):
    mode: str
    as_of: str
    horizon_end: str
    sme: str | None
    parties: list[str]
    documents: list[Document]
    events: list[Event]
    issues: list[ReviewIssue]
    conflicts: list[ConflictAssessment]
    comparisons: dict[str, int]
    conflict_scan: ConflictScan = Field(default_factory=ConflictScan)
    coverage: dict[str, int]


class SmeSelection(Record):
    name: str | None
    mode: Literal["live", "sample"] = "live"


class BatchItem(Record):
    id: str | None
    filename: str
    cached: bool = False
    error: str | None = None


class BatchResponse(Record):
    id: str
    created_at: str
    documents: list[BatchItem]
    progress: list[Document] = Field(default_factory=list)


class Job(Record):
    id: str
    cache_key: str
    kind: str
    payload: dict
    state: str
    attempts: int
    next_run: float
    error: str | None
    created_at: str


class RetryResponse(Record):
    resumed_jobs: int


class DemoResponse(Record):
    loaded: int
    mode: Literal["sample"] = "sample"
    message: str = "Demo workspace loaded. Switch to sample mode to view."
