"""Phase 4 deadline projection: Python arithmetic over already-extracted, support-reviewed rules.

No model call is made here. Every occurrence is recomputed from the validated anchor, and a rule
whose inputs or counting conventions are not established becomes a review issue rather than a
guessed date. Returning a date proves arithmetic, never that an obligation was performed, remains
effective, or that an agreement is still operating.
"""
import calendar
from datetime import date, timedelta

from .evidence import evidence_confidence, pages_complete, resolve_citations, stable_id
from .models import DeadlineRule, Document, Event, Evidence, Page, ReviewIssue, Verdict

ACTION_LABELS = {
    "notice_received": "Notice must be received", "notice_sent": "Notice must be sent",
    "payment_due": "Payment due", "review": "Review required", "expiry": "Term ends",
}
# Documents whose current analysis is finished. Any other status means retained rules are stale.
ANALYZED = frozenset({"complete", "needs_review"})
HORIZON_DAYS = 90
# A lapsed action stays visible for one horizon behind the as-of date; older lapses are not shown.
OVERDUE_LOOKBACK_DAYS = 90
# A planning date can differ from the strict date by a month-end clamp (day 31 becomes day 28).
HORIZON_SLACK_DAYS = 3
MAX_OCCURRENCES = 64
UNIT_DAY_BOUND = {"calendar_days": 1, "calendar_months": 31}
BAND_ORDER = {"low": 0, "medium": 1, "high": 2}
CONTINUATION = "Conditional on the agreement still being in force, with no effective notice or later amendment."
DISPATCH = ("The source establishes a date by which notice must be received. The required delivery method and any "
            "deemed-receipt period are not established, so a safe date to send notice has not been calculated.")
ARITHMETIC = ("The offset, unit and direction used for this calculation are cited for the rule as a whole rather "
              "than individually.")


class Unestablished(ValueError):
    """A rule input or convention the source does not settle. Carries the question a lawyer needs."""

    def __init__(self, missing: str, question: str, reason_code: str = "ambiguous_terms"):
        super().__init__(missing)
        self.question = question
        self.reason_code = reason_code


def parse_date(value: str | None) -> date:
    if not value:
        raise Unestablished("The date this period runs from is not established in the source.",
                            "What date does this period run from, and which clause records it?", "missing_context")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise Unestablished("The date this period runs from is not a valid calendar date.",
                            "What date does this period run from, and which clause records it?", "missing_context") from None


def offset_months(day: date, months: int, end_rule: str = "unspecified") -> date:
    year, month_index = divmod(day.year * 12 + day.month - 1 + months, 12)
    month = month_index + 1
    if year < 1 or year > 9999:
        raise ValueError("Calculated date is outside the supported range.")
    last = calendar.monthrange(year, month)[1]
    if day.day > last and end_rule != "last_day":
        raise Unestablished(
            "A month-end adjustment is required but the contract does not establish the rule.",
            "When a monthly period lands on a date that does not exist in the target month, what does the agreement "
            "provide that the date becomes?")
    return date(year, month, min(day.day, last))


def shift(day: date, amount: int, rule: DeadlineRule) -> date:
    sign = -1 if rule.direction == "before" else 1
    if rule.unit == "calendar_days":
        return day + timedelta(days=sign * amount)
    if rule.unit == "calendar_months":
        return offset_months(day, sign * amount, rule.month_end_rule)
    raise Unestablished(
        "Business-day or unknown counting rules require review; no calendar-day substitution was made.",
        "What does the agreement define as a business day, and which holiday calendar applies?")


def month_index(day: date) -> int:
    return day.year * 12 + day.month - 1


def occurrence_date(anchor: date, recurrence: int | None, index: int, end_rule: str) -> date:
    # Always recomputed from the original anchor so a February clamp never compounds into March.
    return anchor if not recurrence else offset_months(anchor, index * recurrence, end_rule)


def derived_span(rule: DeadlineRule) -> int:
    """Upper bound, in days, on how far an offset moves a date away from its event."""
    return max(rule.offset or 0, rule.earliest_offset or 0) * UNIT_DAY_BOUND.get(rule.unit, 0)


def occurrence_indices(rule: DeadlineRule, anchor: date, as_of: date, end: date) -> list[int]:
    """Every occurrence index whose event, action or window could touch the horizon."""
    span = derived_span(rule)
    # "before" pulls the action earlier, so a later event can still act inside the horizon; "after"
    # pushes it later, so an earlier event can. Extend only the side that can actually reach in.
    back = HORIZON_SLACK_DAYS + OVERDUE_LOOKBACK_DAYS + (span if rule.direction == "after" else 0)
    forward = HORIZON_SLACK_DAYS + (span if rule.direction == "before" else 0)
    low, high = as_of - timedelta(days=back), end + timedelta(days=forward)
    if not rule.recurrence_months:
        return [0] if low <= anchor <= high else []
    step = rule.recurrence_months
    first = max(0, (month_index(low) - month_index(anchor)) // step - 1)
    last = (month_index(high) - month_index(anchor)) // step + 1
    if last < first:
        return []
    if last - first + 1 > MAX_OCCURRENCES + 2:
        raise Unestablished(
            f"This recurring schedule produces about {last - first + 1} occurrences in the period being checked, "
            "which is more than can be presented reliably. No occurrences are shown for it.",
            "What is the correct recurrence interval and period for this schedule?")
    found = []
    for index in range(first, last + 1):
        try:
            # Range selection only. Clamping here keeps an ambiguous month-end occurrence in the
            # candidate set so it fails visibly during emission instead of silently disappearing.
            nominal = occurrence_date(anchor, step, index, "last_day")
        except ValueError:
            break
        if nominal > high:
            break
        if nominal >= low:
            found.append(index)
    if len(found) > MAX_OCCURRENCES:
        raise Unestablished(
            f"This recurring schedule produces {len(found)} occurrences in the period being checked, which is more "
            "than can be presented reliably. No occurrences are shown for it.",
            "What is the correct recurrence interval and period for this schedule?")
    return found


def project(rule: DeadlineRule, anchor: date, index: int) -> tuple[date, date | None, date | None, str, list[str]]:
    """One occurrence's event date, action deadline, window opening, formula and assumptions."""
    event_date = occurrence_date(anchor, rule.recurrence_months, index, rule.month_end_rule)
    assumptions = list(rule.conditions)
    if rule.recurrence_months:
        assumptions.append(CONTINUATION)
    if rule.month_end_rule == "last_day" and event_date.day != anchor.day:
        assumptions.append(f"The month-end rule stated in the source moved this occurrence from day {anchor.day} "
                           f"to {event_date.isoformat()}.")
    if rule.action == "notice_received":
        assumptions.append(DISPATCH)
    if rule.offset is None:
        return event_date, None, None, "Explicit event date: " + event_date.isoformat(), assumptions
    action_date = shift(event_date, rule.offset, rule)
    window_start = None
    if rule.earliest_offset is not None:
        window_start = shift(event_date, rule.earliest_offset, rule)
        if window_start > action_date:
            raise Unestablished(
                "The extracted notice window is inconsistent: its earliest and latest dates are reversed.",
                "Which clause fixes the earliest and latest dates of the notice window?")
    unit = rule.unit.replace("_", " ")
    operator = "−" if rule.direction == "before" else "+"
    formula = f"{event_date.isoformat()} {operator} {rule.offset} {unit} = {action_date.isoformat()}"
    return event_date, action_date, window_start, formula, assumptions


def relevance(event_date: date, action_date: date | None, window_start: date | None,
              as_of: date, end: date) -> tuple[bool, bool]:
    """(include, overdue) under the event-or-action horizon rule."""
    def inside(day):
        return day is not None and as_of <= day <= end

    if inside(event_date) or inside(action_date):
        return True, action_date is not None and action_date < as_of
    # A notice window straddling the horizon with neither boundary inside it still matters.
    if window_start is not None and action_date is not None and window_start <= end and action_date >= as_of:
        return True, False
    # Bounded recent lapse: an overdue action whose event already fell outside the horizon.
    if action_date is not None and as_of - timedelta(days=OVERDUE_LOOKBACK_DAYS) <= action_date < as_of:
        return True, True
    return False, False


def weaken(band: str, reason: str, cap: str, why: str) -> tuple[str, str]:
    """Confidence only ever falls; a cap that is not stricter leaves the band and its reason alone."""
    return (cap, why) if BAND_ORDER[cap] < BAND_ORDER[band] else (band, reason)


def established_facts(evidence: list[Evidence], verdict: Verdict | None, anchor: date | None) -> list[str]:
    """Only what Python verified: quotes matched to source spans, a parsed anchor, a saved verdict."""
    facts = [f"Page {e.page}" + (f", clause {e.clause}" if e.clause else "") + f" contains: “{e.quote}”"
             for e in evidence]
    if anchor is not None:
        facts.append(f"The saved rule records an anchor date of {anchor.isoformat()}.")
    if verdict is not None:
        facts.append(f"The support-review pass recorded this rule as {verdict.status}.")
    return facts


def check_support(rule: DeadlineRule, evidence: list[Evidence], errors: list[str], verdict: Verdict | None):
    """Grounding gates. A partial citation failure still blocks the whole rule."""
    if errors or not evidence:
        raise Unestablished("; ".join(errors) or "This date rule has no validated source citation.",
                            "Which clause and page establish this date and the period that runs from it?", "unsupported_evidence")
    if not verdict or verdict.status != "supported" or verdict.missing_context:
        missing = "; ".join([verdict.reason, *verdict.missing_context]) if verdict \
            else "This date rule has not passed the support-review pass."
        raise Unestablished(missing, "What does the complete agreement establish about this date rule?",
                            "incomplete_analysis" if not verdict else "missing_context" if verdict.missing_context else
                            verdict.reason_codes[0] if verdict.reason_codes else "not_established")
    if rule.missing_inputs:
        raise Unestablished("; ".join(rule.missing_inputs),
                            "On what date was the invoice received, and how is receipt evidenced?"
                            if rule.action == "payment_due" else
                            "What are the missing facts this period depends on, and where are they recorded?", "missing_context")
    if rule.offset is None and rule.action != "expiry":
        raise Unestablished("The notice or payment period is not established.",
                            "What notice or payment period does the agreement require, and from what date?", "not_established")
    # Refuse the counting rule before enumeration, or an out-of-range occurrence would hide the gate.
    if rule.offset is not None and rule.unit in {"business_days", "unknown"}:
        raise Unestablished(
            "Business days are not defined in the source; no calendar-day substitution was made."
            if rule.unit == "business_days" else
            "The counting unit for this period is not established; no calendar-day substitution was made.",
            "What does the agreement define as a business day, and which holiday calendar applies?")


def event_order(event: Event) -> tuple[str, str, str]:
    """Earliest relevant date, then event date, then stable ID. ISO strings sort chronologically."""
    first = min(day for day in (event.window_start, event.action_date, event.event_date) if day)
    return first, event.event_date, event.id


def calendar_for(doc: Document, pages: list[Page], as_of: date,
                 days: int = HORIZON_DAYS) -> tuple[list[Event], list[ReviewIssue]]:
    events, issues = [], []
    end = as_of + timedelta(days=days)
    reviews = {v.item_id: v for v in doc.reviews}
    complete = pages_complete(doc, pages)
    for rule in doc.rules:
        evidence, errors = resolve_citations(rule.citations, pages, {doc.id})
        verdict = reviews.get(rule.id)
        anchor = None
        try:
            check_support(rule, evidence, errors, verdict)
            anchor = parse_date(rule.event_date)
            produced = []
            for index in occurrence_indices(rule, anchor, as_of, end):
                event_date, action_date, window_start, formula, assumptions = project(rule, anchor, index)
                include, overdue = relevance(event_date, action_date, window_start, as_of, end)
                if not include:
                    continue
                if overdue:
                    assumptions = assumptions + [
                        f"This scheduled date passed on {action_date.isoformat()}, before the selected date of "
                        f"{as_of.isoformat()}. Whether the action was performed, waived or varied is not established.",
                    ]
                    if rule.action in {"notice_received", "notice_sent"}:
                        assumptions.append("Whether notice was given, and whether late or alternative notice would "
                                           "still be effective, is not established here.")
                if action_date is not None:
                    # Stated even when another cause wins the band, so the limit is never hidden.
                    assumptions = assumptions + [ARITHMETIC]
                band, reason = evidence_confidence(evidence, bool(assumptions))
                if not complete:
                    band, reason = weaken(band, reason, "low", "Some pages of this document could not be read; "
                                          "other dates or conditions may not have been seen.")
                if action_date is not None:
                    band, reason = weaken(band, reason, "medium", ARITHMETIC)
                if rule.recurrence_months or index:
                    band, reason = weaken(band, reason, "medium", "Future occurrences depend on the agreement "
                                          "continuing to operate, which is not established here.")
                if rule.conditions:
                    band, reason = weaken(band, reason, "medium", "This clause applies subject to conditions the "
                                          "source does not resolve.")
                if overdue:
                    band, reason = weaken(band, reason, "medium", "This date has passed as at the selected date; "
                                          "whether the action was performed is not established.")
                produced.append(Event(
                    id=stable_id(doc.id, rule.id, rule.event_date or "", str(index)), document_id=doc.id,
                    label=rule.label, event_type=rule.event_type, event_date=event_date.isoformat(),
                    action_date=action_date.isoformat() if action_date else None,
                    window_start=window_start.isoformat() if window_start else None,
                    action=ACTION_LABELS[rule.action], formula=formula, assumptions=assumptions,
                    confidence=band, confidence_reason=reason, evidence=evidence, overdue=overdue, occurrence=index,
                    # Only an unshifted first occurrence is read straight from the source.
                    provenance="found" if rule.offset is None and not index else "calculated",
                ))
            # A schedule with a hole reads exactly like a complete one, so all or nothing per rule.
            events.extend(produced)
        except (ValueError, OverflowError) as error:
            issues.append(ReviewIssue(
                id=stable_id(doc.id, rule.id, "deadline"), document_ids=[doc.id],
                title="Deadline cannot be established",
                established=established_facts(evidence, verdict, anchor),
                missing_facts=[str(error)],
                lawyer_question=getattr(error, "question", "What date and counting rule applies to this period?"),
                evidence=evidence, kind="deadline", mode=doc.mode,
                reason_codes=[getattr(error, "reason_code", "unsupported_evidence")],
            ))
    events.sort(key=event_order)
    return events, issues


def unreadable_pages_issue(doc: Document) -> ReviewIssue:
    return ReviewIssue(
        id=stable_id(doc.id, "deadline", "pages"), document_ids=[doc.id],
        title="Source pages could not be read for date checking", reason_codes=["source_unreadable"],
        missing_facts=["The saved page checkpoint for this document could not be read, so its date citations could "
                       "not be revalidated. No deadlines have been calculated from it."],
        lawyer_question="Re-read this document's source pages, then confirm which dates and notice periods it "
                        "establishes.",
        kind="deadline", mode=doc.mode,
    )


def stale_analysis_issue(doc: Document) -> ReviewIssue:
    return ReviewIssue(
        id=stable_id(doc.id, "deadline", "stale"), document_ids=[doc.id],
        title="Saved date rules are not current", reason_codes=["incomplete_analysis"],
        missing_facts=[f"This document is currently {doc.status}. Date rules saved by an earlier run are not used "
                       "while the current run is incomplete."],
        lawyer_question="Once analysis finishes, confirm which dates and notice periods this document establishes.",
        kind="deadline", mode=doc.mode,
    )


def document_pages(config, document_id: str):
    """None denotes an unreadable checkpoint; an empty readable checkpoint remains []."""
    from fastapi import HTTPException
    from .documents import load_pages
    from .ingestion import source_path
    try:
        return load_pages(source_path(config, document_id, 'pages.json'))
    except (HTTPException, OSError, ValueError):
        return None


def project_deadlines(docs: list[Document], config, as_of: date):
    """Shared read-only projection for portfolio events and review/brief issue identities."""
    from .foundation import CAPABILITIES
    events, projected, evaluated, unavailable = [], [], 0, 0
    # A read-only projection: no model call, no queued work and no stored record is changed.
    for doc in docs if CAPABILITIES.deadlines else []:
        if doc.status not in ANALYZED:
            # Rules retained from an earlier run cannot supply dates while this run is incomplete.
            projected += [stale_analysis_issue(doc)] if doc.rules else []
            continue
        if not doc.rules:
            continue
        pages = document_pages(config, doc.id)
        if pages is None:
            unavailable += 1
            projected.append(unreadable_pages_issue(doc))
            continue
        found, raised = calendar_for(doc, pages, as_of, days=HORIZON_DAYS)
        events += found
        projected += raised
        evaluated += 1
    events.sort(key=event_order)
    return events, projected, evaluated, unavailable
