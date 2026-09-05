from datetime import date
from itertools import combinations

from .evidence import normalized, resolve_citations, stable_id
from .models import ConflictAssessment, ConflictDraft, Document, Page


def pair_id(a: Document, b: Document) -> str:
    return stable_id(*sorted([a.id, b.id]), a.version, b.version, a.model, b.model)


def candidate(a: Document, b: Document) -> tuple[bool, str]:
    """Conservative screening: uncertain scope never becomes a negative."""
    left = [p for p in a.provisions if p.kind in ("distribution", "unknown")]
    right = [p for p in b.provisions if p.kind in ("distribution", "unknown")]
    if not left or not right:
        return False, "No extracted distribution provisions to compare; this does not rule out missed clauses."
    if not any(p.exclusive is not False for p in [*left, *right]):
        # A failed support review cannot validate a negative exclusivity flag.
        verdicts = {v.item_id: v for v in [*a.reviews, *b.reviews]}
        if all(verdicts.get(p.id) and verdicts[p.id].status == "supported" for p in [*left, *right]):
            return False, "The extracted distribution provisions are explicitly non-exclusive; other restrictions are outside this rule."
    # Only discard for disjoint periods if EVERY possible provision pair is definitely disjoint.
    verdicts = {v.item_id: v for v in [*a.reviews, *b.reviews]}
    disjoint = []
    for p in left:
        for q in right:
            try:
                supported = all(verdicts.get(x.id) and verdicts[x.id].status == "supported" for x in (p, q))
                bounded = all([p.starts_on, p.ends_on, q.starts_on, q.ends_on])
                if not supported or not bounded or p.missing_context or q.missing_context:
                    disjoint.append(False)
                    continue
                ps, pe, qs, qe = map(date.fromisoformat, [p.starts_on, p.ends_on, q.starts_on, q.ends_on])
                disjoint.append(ps <= pe and qs <= qe and (pe < qs or qe < ps))
            except ValueError:
                disjoint.append(False)
    if disjoint and all(disjoint):
        return False, "Every supported, explicitly bounded distribution period is non-overlapping."
    return True, "Distribution provisions may overlap; semantic comparison is required."


def candidates(documents: list[Document]):
    for a, b in combinations(documents, 2):
        selected, reason = candidate(a, b)
        yield a, b, selected, reason


def time_comparison(a: Document, b: Document) -> list[dict]:
    result = []
    for p in a.provisions:
        for q in b.provisions:
            item = {"left": p.id, "right": q.id, "overlap": "unknown"}
            if all([p.starts_on, p.ends_on, q.starts_on, q.ends_on]):
                try:
                    starts = [date.fromisoformat(p.starts_on), date.fromisoformat(q.starts_on)]
                    ends = [date.fromisoformat(p.ends_on), date.fromisoformat(q.ends_on)]
                    if all(s <= e for s, e in zip(starts, ends)):
                        item["overlap"] = "yes" if max(starts) <= min(ends) else "no"
                except ValueError:
                    pass
            result.append(item)
    return result


def validate_assessment(draft: ConflictDraft, a: Document, b: Document, pages: list[Page]) -> ConflictAssessment:
    expected = {a.id, b.id}
    evidence, errors = resolve_citations(draft.citations, pages, expected)
    if set(draft.documents) != expected:
        errors.append("The comparison returned the wrong document identifiers.")
    if {e.document_id for e in evidence} != expected:
        errors.append("Evidence from both agreements is required.")
    required_dimensions = {"product", "territory", "activity", "channel", "parties", "time"}
    if not required_dimensions.issubset(draft.scope_comparison):
        errors.append("The comparison omitted a required scope dimension.")
    missing = list(draft.missing_facts)
    for doc in (a, b):
        missing.extend(doc.warnings)
        reviews = {v.item_id: v for v in doc.reviews}
        for p in doc.provisions:
            missing.extend(p.missing_context)
            if not reviews.get(p.id) or reviews[p.id].status != "supported":
                missing.append("A commercial provision has not passed support review.")
    status = draft.status
    if errors or missing:
        status = "insufficient_evidence"
    if any(e.ocr_confidence is not None and e.ocr_confidence < 70 for e in evidence):
        missing.append("Low-confidence OCR may change the commercial scope.")
        status = "insufficient_evidence"
    # The explanation itself is a semantic assessment, never deterministic proof.
    return ConflictAssessment(
        id=pair_id(a, b), status=status, documents=sorted(expected),
        scope_comparison=draft.scope_comparison if not errors else {},
        evidence=evidence, exceptions=draft.exceptions if not errors else [],
        missing_facts=list(dict.fromkeys(missing + errors)),
        explanation=draft.explanation if not errors else "The proposed comparison did not pass evidence validation.",
        lawyer_question=draft.lawyer_question if not errors else "Do the source provisions grant incompatible distribution rights?",
        confidence="low" if status == "insufficient_evidence" else "medium",
        confidence_reason="Semantic assessment of cited clauses; actual breach and enforceability require legal judgment.",
        provenance="unresolved" if status == "insufficient_evidence" else "inferred", mode=a.mode,
    )
