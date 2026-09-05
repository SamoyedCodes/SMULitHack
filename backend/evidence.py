import hashlib
import re
import unicodedata

from .models import (
    Citation, Document, Evidence, Extraction, FIELD_LABELS, FieldName, Finding,
    Page, ReviewIssue, SupportReview, Verdict,
)


def normalized(text: str) -> str:
    # Deliberately do not remove punctuation, negation, numbers, or change case.
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).strip()


def stable_id(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:20]


def resolve_citations(citations: list[Citation], pages: list[Page], allowed: set[str]) -> tuple[list[Evidence], list[str]]:
    spans = {s.id: s for p in pages for s in p.spans}
    evidence, errors = [], []
    for citation in citations:
        if citation.document_id not in allowed:
            errors.append("Citation refers to a different document.")
            continue
        selected = [spans.get(s) for s in citation.span_ids]
        if not selected or any(s is None or s.document_id != citation.document_id for s in selected):
            errors.append("Citation contains an unknown text-span identifier.")
            continue
        # Model order cannot move text to a different page or manufacture contiguous support.
        if len({s.page for s in selected}) != 1:
            errors.append("Cross-page evidence must be supplied as separate citations.")
            continue
        selected.sort(key=lambda s: int(s.id.rsplit(":s", 1)[1]))
        ids = [int(s.id.rsplit(":s", 1)[1]) for s in selected]
        if ids != list(range(ids[0], ids[-1] + 1)):
            errors.append("Citation combines non-adjacent text spans.")
            continue
        source_text = normalized(" ".join(s.text for s in selected))
        quote = normalized(citation.quote)
        if not quote or quote not in source_text:
            errors.append("Quoted text does not match the cited source passage.")
            continue
        # Keep the source string as the authority; the model never chooses page/box/label.
        ocr = [s.ocr_confidence for s in selected if s.ocr_confidence is not None]
        evidence.append(Evidence(
            document_id=citation.document_id, span_ids=[s.id for s in selected], quote=quote,
            page=selected[0].page, clause=next((s.clause for s in selected if s.clause), None),
            boxes=[s.bbox for s in selected], source="ocr" if ocr else "native",
            ocr_confidence=min(ocr) if ocr else None,
        ))
    unique = {stable_id(e.document_id, str(e.page), e.quote): e for e in evidence}
    return list(unique.values()), errors


def evidence_confidence(evidence: list[Evidence], inferred: bool = False) -> tuple[str, str]:
    if not evidence:
        return "low", "No matching source evidence."
    if any(e.ocr_confidence is not None and e.ocr_confidence < 70 for e in evidence):
        return "low", "The source contains low-confidence scanned words; verify the page."
    if any(e.source == "ocr" for e in evidence):
        return "medium", "Matched to OCR text. Scanned characters may have been misread."
    if inferred:
        return "medium", "The cited wording supports an interpretation that still depends on assumptions."
    return "high", "Source text matched and the support-review pass accepted this finding. This is not legal verification."


def unresolved_finding(field: FieldName, document_id: str, reason: str) -> Finding:
    return Finding(id=stable_id(document_id, field.value), field=field, value=None,
                   provenance="unresolved", confidence="low", confidence_reason=reason)


def apply_extraction(doc: Document, extraction: Extraction, review: SupportReview, pages: list[Page]) -> Document:
    verdicts = {v.item_id: v for v in review.verdicts}
    findings, issues = [], []
    complete = bool(pages) and all(p.status == "read" for p in pages)
    for draft in extraction.findings:
        evidence, errors = resolve_citations(draft.citations, pages, {doc.id})
        verdict = verdicts.get(draft.id)
        reason = "; ".join(errors) or (verdict.reason if verdict else "Support review did not assess this field.")
        supported = draft.value is not None and bool(evidence) and not errors and verdict and verdict.status == "supported"
        if supported:
            confidence, confidence_reason = evidence_confidence(evidence, draft.inferred)
            if not complete:
                confidence, confidence_reason = "low", "Some pages could not be read; additional conditions may be missing."
            findings.append(Finding(
                id=draft.id, field=draft.field, value=draft.value, party=draft.party,
                conditions=draft.conditions, provenance="inferred" if draft.inferred else "found",
                confidence=confidence, confidence_reason=confidence_reason, evidence=evidence,
            ))
        else:
            finding = unresolved_finding(draft.field, doc.id, reason)
            finding.id = draft.id
            finding.evidence = evidence
            findings.append(finding)
        if not supported or (verdict and verdict.missing_context):
            issues.append(ReviewIssue(
                id=stable_id(doc.id, draft.id, "issue"), document_ids=[doc.id],
                title=FIELD_LABELS[draft.field] + " needs review",
                missing_facts=[reason] + (verdict.missing_context if verdict else []),
                lawyer_question="What does the complete agreement establish about " + FIELD_LABELS[draft.field].lower() + "?",
                evidence=evidence, mode=doc.mode,
            ))
    for field in FieldName:
        if not any(f.field == field for f in findings):
            finding = unresolved_finding(field, doc.id, "Not established in the supplied document. This does not mean no obligation exists.")
            findings.append(finding)
            issues.append(ReviewIssue(
                id=stable_id(doc.id, field, "missing"), document_ids=[doc.id],
                title=FIELD_LABELS[field] + " not established",
                missing_facts=[finding.confidence_reason],
                lawyer_question="Is there another clause or document establishing " + FIELD_LABELS[field].lower() + "?",
                mode=doc.mode,
            ))
    for missing in extraction.missing_context:
        issues.append(ReviewIssue(
            id=stable_id(doc.id, missing), document_ids=[doc.id], title="Referenced context needs review",
            missing_facts=[missing], lawyer_question="Which additional documents or facts are needed to complete the assessment?",
            mode=doc.mode,
        ))
    # Carry forward processing issues and require evidence/support for all machine-readable rules.
    checked_reviews = list(review.verdicts)
    for item in [*extraction.deadlines, *extraction.provisions]:
        evidence, errors = resolve_citations(item.citations, pages, {doc.id})
        verdict = verdicts.get(item.id)
        if errors or not evidence or not complete:
            why = "; ".join(errors) or ("Some pages could not be read." if not complete else "No valid source evidence.")
            checked_reviews = [v for v in checked_reviews if v.item_id != item.id]
            checked_reviews.append(Verdict(item_id=item.id, status="uncertain", reason=why))
        elif not verdict:
            checked_reviews.append(Verdict(item_id=item.id, status="uncertain", reason="Not assessed by the support-review pass."))
    doc.findings = findings
    doc.rules = extraction.deadlines
    doc.provisions = extraction.provisions
    doc.reviews = checked_reviews
    doc.issues = [i for i in doc.issues if i.kind == "processing"] + issues
    # Party picker entries must occur verbatim in accepted party findings' sources.
    party_sources = normalized(" ".join(e.quote for f in findings if f.field == "parties" and f.value for e in f.evidence))
    doc.parties = [p for p in extraction.parties if normalized(p) in party_sources]
    # Model-generated titles are not used as an uncited summary.
    return doc
