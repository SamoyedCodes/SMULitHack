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
from .models import Brief, BriefDocument, Citation, ConflictAssessment, ReviewIssue
from .store import Store

CONFLICT_TITLES = {
    "potential_conflict": "Potential distribution-rights conflict",
    "insufficient_evidence": "Distribution conflict — insufficient evidence",
    "no_conflict_identified_for_this_rule": "No distribution conflict identified for this rule",
}


def review_items(store: Store, config: Config, mode: str, as_of: date) -> list[tuple[str, str, object]]:
    """The canonical id space of review items as ``(id, source, record)``.

    Includes extraction issues, deadline issues (only when that capability is enabled), and every
    conflict assessment (all statuses, so any id resolves to a brief). The frontend queue decides
    which of these are actionable; here we only need stable, complete id resolution.
    """
    from .deadlines import project_deadlines
    from .conflict_service import snapshot
    docs = store.documents(mode)
    _, projected, _, _ = project_deadlines(docs, config, as_of)
    _, _, assessments, conflict_issues = snapshot(config, store, mode)
    issues = {i.id: i for i in [*(i for doc in docs for i in doc.issues), *projected, *conflict_issues]}
    wrappers = {"conflict:" + c.id for c in assessments}
    items = [(i.id, "issue", i) for i in issues.values() if i.id not in wrappers]
    for assessment in assessments:
        # Both the assessment ID and the portfolio's issue wrapper resolve to the full brief.
        items.extend([(assessment.id, "conflict", assessment), ("conflict:" + assessment.id, "conflict", assessment)])
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


def _source_warnings(config: Config, evidence, store: Store, mode: str) -> list[str]:
    """Reopen and validate cited pages/spans instead of equating file presence with support."""
    from .deadlines import document_pages
    from .evidence import resolve_citations
    warnings, checkpoints = [], {}
    for item in evidence:
        doc = store.document(item.document_id)
        if doc is None or doc.mode != mode:
            warnings.append(f"A cited document ({item.document_id}) is unavailable in this workspace.")
            continue
        if item.document_id not in checkpoints:
            checkpoints[item.document_id] = document_pages(config, item.document_id)
        pages = checkpoints[item.document_id]
        if pages is None:
            warnings.append(f"The source pages for a cited document ({item.document_id}) could not be reopened; verify the original before relying on these excerpts.")
            continue
        cited_page = next((page for page in pages if page.number == item.page), None)
        try:
            resolved, errors = resolve_citations([Citation(document_id=item.document_id, span_ids=item.span_ids, quote=item.quote)], pages, {doc.id})
        except (ValueError, IndexError):
            resolved, errors = [], ["Invalid source span identifier."]
        if (not cited_page or cited_page.status != "read" or cited_page.warnings or errors
                or not resolved or resolved[0].page != item.page or resolved[0].boxes != item.boxes):
            warnings.append(f"Source evidence for {item.document_id}, page {item.page}, could not be revalidated; verify the original before relying on this excerpt.")
        if doc.status not in {"complete", "needs_review"}:
            warnings.append(f"The analysis for {item.document_id} is not current ({doc.status}); these excerpts may belong to an earlier analysis.")
    return list(dict.fromkeys(warnings))


def build_brief(record: object, source: str, store: Store, config: Config, mode: str, as_of: date) -> Brief:
    generated_at = datetime.now(ZoneInfo("Asia/Singapore")).isoformat()
    if source == "conflict":
        assert isinstance(record, ConflictAssessment)
        descriptors, doc_warnings = _document_descriptors(store, record.documents, mode)
        coverage = doc_warnings + _source_warnings(config, record.evidence, store, mode)
        if not record.current:
            coverage.insert(0, "Historical comparison — stale: the current workspace inputs no longer establish this assessment as current. It is excluded from open review counts.")
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
    coverage = doc_warnings + _source_warnings(config, record.evidence, store, mode)
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
