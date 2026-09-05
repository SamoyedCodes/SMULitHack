"""Phase 3 grounded-extraction logic: citation validation, confidence bands, and
apply_extraction provenance/completeness. No model calls; pure Python over synthetic pages."""
import pytest

from backend.evidence import apply_extraction, evidence_confidence, resolve_citations
from backend.models import (
    Citation, CommercialProvision, DeadlineRule, Document, Evidence, Extraction,
    FieldName, FindingDraft, Page, Span, SupportReview, Verdict,
)

DOC = "doc1"


def span(page, n, text, *, doc=DOC, source="native", ocr=None, clause=None):
    return Span(id=f"{doc}:p{page}:s{n}", document_id=doc, page=page, text=text,
                bbox=[0.0, 0.0, 1.0, 1.0], source=source, ocr_confidence=ocr, clause=clause)


def page(number, spans, *, status="read", warnings=None):
    return Page(number=number, width=600, height=800, spans=spans, status=status, warnings=warnings or [])


def sample_pages():
    return [
        page(1, [
            span(1, 0, "This Agreement is between Acme Pte Ltd and Beta LLC."),
            span(1, 1, "The term is two years from the Effective Date."),
        ]),
        page(2, [span(2, 2, "Either party may terminate on 60 days written notice.")]),
    ]


def cite(span_ids, quote, doc=DOC):
    return Citation(document_id=doc, span_ids=span_ids, quote=quote)


def document(**over):
    base = dict(id=DOC, filename="acme.pdf", title="Acme", sha256="abc", mode="live",
                created_at="2026-09-05T00:00:00Z", model="fake", version="1")
    return Document(**{**base, **over})


# --- resolve_citations ---------------------------------------------------------

def test_valid_citation_resolves_to_evidence():
    pages = sample_pages()
    evidence, errors = resolve_citations([cite([f"{DOC}:p1:s0"], "Acme Pte Ltd and Beta LLC")], pages, {DOC})
    assert not errors and len(evidence) == 1
    e = evidence[0]
    assert e.page == 1 and e.source == "native" and e.quote == "Acme Pte Ltd and Beta LLC"


def test_unknown_span_id_is_rejected():
    evidence, errors = resolve_citations([cite([f"{DOC}:p9:s99"], "whatever")], sample_pages(), {DOC})
    assert not evidence and any("unknown text-span" in e for e in errors)


def test_cross_page_citation_is_rejected():
    evidence, errors = resolve_citations([cite([f"{DOC}:p1:s1", f"{DOC}:p2:s2"], "text")], sample_pages(), {DOC})
    assert not evidence and any("Cross-page" in e for e in errors)


def test_non_adjacent_spans_are_rejected():
    pages = [page(1, [span(1, 0, "Alpha clause."), span(1, 3, "Distant clause.")])]
    evidence, errors = resolve_citations([cite([f"{DOC}:p1:s0", f"{DOC}:p1:s3"], "Alpha clause. Distant clause.")], pages, {DOC})
    assert not evidence and any("non-adjacent" in e for e in errors)


def test_quote_not_in_source_is_rejected():
    evidence, errors = resolve_citations([cite([f"{DOC}:p1:s0"], "a quote that never appears")], sample_pages(), {DOC})
    assert not evidence and any("does not match" in e for e in errors)


def test_citation_to_other_document_is_rejected():
    evidence, errors = resolve_citations([cite([f"{DOC}:p1:s0"], "Acme", doc="other")], sample_pages(), {DOC})
    assert not evidence and any("different document" in e for e in errors)


# --- evidence_confidence -------------------------------------------------------

def _ev(source="native", ocr=None):
    return Evidence(document_id=DOC, span_ids=[f"{DOC}:p1:s0"], quote="q", page=1,
                    boxes=[[0, 0, 1, 1]], source=source, ocr_confidence=ocr)


def test_confidence_bands():
    assert evidence_confidence([])[0] == "low"
    assert evidence_confidence([_ev(source="ocr", ocr=40)])[0] == "low"
    assert evidence_confidence([_ev(source="ocr", ocr=90)])[0] == "medium"
    assert evidence_confidence([_ev()], inferred=True)[0] == "medium"
    assert evidence_confidence([_ev()])[0] == "high"


# --- apply_extraction ----------------------------------------------------------

def _parties_draft():
    return FindingDraft(id="f1", field=FieldName.PARTIES, value="Acme Pte Ltd and Beta LLC",
                        citations=[cite([f"{DOC}:p1:s0"], "Acme Pte Ltd and Beta LLC")])


def test_supported_finding_is_found_high_and_all_fields_present():
    pages = sample_pages()
    extraction = Extraction(title="Acme", parties=["Acme Pte Ltd", "Beta LLC", "Ghost Corp"], findings=[_parties_draft()])
    review = SupportReview(verdicts=[Verdict(item_id="f1", status="supported", reason="stated")])
    doc = apply_extraction(document(), extraction, review, pages)
    parties = next(f for f in doc.findings if f.field == FieldName.PARTIES)
    assert parties.provenance == "found" and parties.confidence == "high" and parties.evidence
    # Every one of the eight fields is represented, unresolved when not established.
    assert {f.field for f in doc.findings} == set(FieldName)
    # Party picker only keeps names that occur verbatim in the accepted source.
    assert doc.parties == ["Acme Pte Ltd", "Beta LLC"]


def test_null_value_becomes_unresolved_with_issue():
    draft = FindingDraft(id="f2", field=FieldName.LIABILITY, value=None)
    extraction = Extraction(title="Acme", findings=[draft])
    review = SupportReview(verdicts=[Verdict(item_id="f2", status="uncertain", reason="no cap stated")])
    doc = apply_extraction(document(), extraction, review, sample_pages())
    liability = next(f for f in doc.findings if f.field == FieldName.LIABILITY)
    assert liability.provenance == "unresolved" and liability.value is None
    assert any("Liability" in i.title for i in doc.issues)


def test_missing_field_produces_not_established_issue():
    doc = apply_extraction(document(), Extraction(title="Acme"), SupportReview(verdicts=[]), sample_pages())
    assert any(i.title.endswith("not established") for i in doc.issues)
    assert all(f.provenance == "unresolved" for f in doc.findings)


def test_incomplete_pages_downgrade_confidence():
    pages = sample_pages()
    pages[1].status = "unreadable"  # one page could not be read
    extraction = Extraction(title="Acme", parties=["Acme Pte Ltd"], findings=[_parties_draft()])
    review = SupportReview(verdicts=[Verdict(item_id="f1", status="supported", reason="stated")])
    doc = apply_extraction(document(), extraction, review, pages)
    parties = next(f for f in doc.findings if f.field == FieldName.PARTIES)
    assert parties.confidence == "low" and "could not be read" in parties.confidence_reason


def test_machine_rules_without_evidence_are_marked_uncertain():
    rule = DeadlineRule(id="r1", label="Renewal notice", event_type="renewal", trigger="expiry",
                        action="notice_received", citations=[cite([f"{DOC}:p9:s0"], "missing")])
    extraction = Extraction(title="Acme", deadlines=[rule])
    doc = apply_extraction(document(), extraction, SupportReview(verdicts=[]), sample_pages())
    verdict = next(v for v in doc.reviews if v.item_id == "r1")
    assert verdict.status == "uncertain"
