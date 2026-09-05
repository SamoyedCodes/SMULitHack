"""Phase 6 handoff: aggregate grounded review items and assemble printable lawyer briefs.

A brief is a read-only projection of data already extracted, validated and persisted by earlier
phases. No model call is made here — this module only normalizes existing ``ReviewIssue`` and
``ConflictAssessment`` records into a self-contained ``Brief`` and re-checks that each cited source
is still readable before presenting it.
"""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from .config import Config
from .foundation import CAPABILITIES
from .models import Brief, BriefDocument, ConflictAssessment, ReviewIssue
from .store import Store

CONFLICT_TITLES = {
    "potential_conflict": "Potential distribution-rights conflict",
    "insufficient_evidence": "Distribution conflict — insufficient evidence",
    "no_conflict_identified_for_this_rule": "No distribution conflict identified for this rule",
}
# Higher rank sorts first in the queue. Potential conflicts demand attention before uncertainties.
CONFLICT_RANK = {"potential_conflict": 3, "insufficient_evidence": 2, "no_conflict_identified_for_this_rule": 0}


def review_items(store: Store, config: Config, mode: str, as_of: date) -> list[tuple[str, str, object]]:
    """The canonical id space of review items as ``(id, source, record)``.

    Includes extraction issues, deadline issues (only when that capability is enabled), and every
    conflict assessment (all statuses, so any id resolves to a brief). The frontend queue decides
    which of these are actionable; here we only need stable, complete id resolution.
    """
    items: list[tuple[str, str, object]] = []
    docs = store.documents(mode)
    for doc in docs:
        for issue in doc.issues:
            items.append((issue.id, "issue", issue))
    if CAPABILITIES.deadlines:
        # Deadline issues are computed, not persisted; rebuild them the way the portfolio does so
        # their stable ids match. Lazy import keeps this optional while Phase 4 is separate work.
        from .deadlines import calendar_for
        from .documents import load_pages
        from .ingestion import source_path
        for doc in docs:
            try:
                pages = load_pages(source_path(config, doc.id, "pages.json"))
            except HTTPException:
                pages = []
            _, issues = calendar_for(doc, pages, as_of)
            for issue in issues:
                items.append((issue.id, "issue", issue))
    for assessment in store.comparisons(mode):
        items.append((assessment.id, "conflict", assessment))
    return items


def _document_descriptors(store: Store, document_ids: list[str], mode: str) -> tuple[list[BriefDocument], list[str]]:
    descriptors, warnings = [], []
    for document_id in document_ids:
        doc = store.document(document_id)
        if doc is None or doc.mode != mode:
            warnings.append(f"A cited document ({document_id}) is no longer in this workspace; verify the source before relying on this brief.")
            descriptors.append(BriefDocument(id=document_id, title="Unavailable document", filename=document_id))
            continue
        descriptors.append(BriefDocument(id=doc.id, title=doc.title or doc.filename, filename=doc.filename))
    return descriptors, warnings


def _source_warnings(config: Config, evidence, seen: set[str]) -> list[str]:
    """Competence gate: confirm each cited source page checkpoint is still readable."""
    from .ingestion import source_path
    warnings = []
    for item in evidence:
        if item.document_id in seen:
            continue
        seen.add(item.document_id)
        try:
            source_path(config, item.document_id, "pages.json")
        except HTTPException:
            warnings.append(f"The source pages for a cited document ({item.document_id}) could not be reopened; re-read the document before relying on these excerpts.")
    return warnings


def build_brief(record: object, source: str, store: Store, config: Config, mode: str, as_of: date) -> Brief:
    generated_at = datetime.now(ZoneInfo("Asia/Singapore")).isoformat()
    if source == "conflict":
        assert isinstance(record, ConflictAssessment)
        descriptors, doc_warnings = _document_descriptors(store, record.documents, mode)
        coverage = doc_warnings + _source_warnings(config, record.evidence, set())
        return Brief(
            id=record.id, source="conflict", kind=record.status, mode=record.mode,
            generated_at=generated_at, as_of=as_of.isoformat(),
            title=CONFLICT_TITLES.get(record.status, "Distribution-rights review"),
            documents=descriptors, missing_facts=record.missing_facts,
            lawyer_question=record.lawyer_question, explanation=record.explanation,
            scope_comparison=record.scope_comparison, exceptions=record.exceptions,
            provenance=record.provenance, confidence=record.confidence,
            confidence_reason=record.confidence_reason, evidence=record.evidence,
            coverage_warnings=coverage,
        )
    assert isinstance(record, ReviewIssue)
    descriptors, doc_warnings = _document_descriptors(store, record.document_ids, mode)
    coverage = doc_warnings + _source_warnings(config, record.evidence, set())
    return Brief(
        id=record.id, source="issue", kind=record.kind, mode=record.mode,
        generated_at=generated_at, as_of=as_of.isoformat(), title=record.title,
        documents=descriptors, established=record.established, missing_facts=record.missing_facts,
        lawyer_question=record.lawyer_question, urgency=record.urgency,
        provenance="unresolved", evidence=record.evidence, coverage_warnings=coverage,
    )


def brief_for(store: Store, config: Config, issue_id: str, mode: str, as_of: date) -> Brief:
    for rid, source, record in review_items(store, config, mode, as_of):
        if rid == issue_id:
            return build_brief(record, source, store, config, mode, as_of)
    raise HTTPException(404, "Review item not found.")
