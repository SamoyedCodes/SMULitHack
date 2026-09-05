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


class Page(Record):
    number: int
    width: float
    height: float
    spans: list[Span] = Field(default_factory=list)
    status: Literal["read", "unreadable", "error"] = "read"
    warnings: list[str] = Field(default_factory=list)


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


class Verdict(Record):
    item_id: str
    status: Literal["supported", "uncertain", "rejected"]
    reason: str
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
    evidence: list[Evidence]
    provenance: Literal["calculated"] = "calculated"


class ConflictDraft(Record):
    status: Literal["potential_conflict", "no_conflict_identified_for_this_rule", "insufficient_evidence"]
    documents: list[str]
    scope_comparison: dict[str, str]
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
    rules: list[DeadlineRule] = Field(default_factory=list)
    provisions: list[CommercialProvision] = Field(default_factory=list)
    reviews: list[Verdict] = Field(default_factory=list)
    issues: list[ReviewIssue] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    created_at: str
    model: str
    version: str


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
    coverage: dict[str, int]


class SmeSelection(Record):
    name: str | None
    mode: Literal["live", "sample"] = "live"
