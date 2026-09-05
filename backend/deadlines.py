import calendar
from datetime import date, timedelta

from .evidence import evidence_confidence, resolve_citations, stable_id
from .models import DeadlineRule, Document, Event, Page, ReviewIssue

ACTION_LABELS = {
    "notice_received": "Notice must be received", "notice_sent": "Notice must be sent",
    "payment_due": "Payment due", "review": "Review required", "expiry": "Term ends",
}


def parse_date(value: str | None) -> date:
    if not value:
        raise ValueError("The triggering date is not available.")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError("The triggering date is ambiguous or invalid.") from None


def offset_months(day: date, months: int, end_rule: str = "unspecified") -> date:
    year, month_index = divmod(day.year * 12 + day.month - 1 + months, 12)
    month = month_index + 1
    if year < 1 or year > 9999:
        raise ValueError("Calculated date is outside the supported range.")
    last = calendar.monthrange(year, month)[1]
    if day.day > last and end_rule != "last_day":
        raise ValueError("A month-end adjustment is required but the contract does not establish the rule.")
    return date(year, month, min(day.day, last))


def shift(day: date, amount: int, rule: DeadlineRule) -> date:
    sign = -1 if rule.direction == "before" else 1
    if rule.unit == "calendar_days":
        return day + timedelta(days=sign * amount)
    if rule.unit == "calendar_months":
        return offset_months(day, sign * amount, rule.month_end_rule)
    raise ValueError("Business-day or unknown counting rules require review; no calendar-day substitution was made.")


def calculate(rule: DeadlineRule, as_of: date) -> tuple[date, date | None, date | None, str, list[str]]:
    if rule.missing_inputs:
        raise ValueError("; ".join(rule.missing_inputs))
    event_date = parse_date(rule.event_date)
    assumptions = list(rule.conditions)
    if rule.recurrence_months:
        assumptions.append("Conditional on the agreement still being in force, with no effective notice or later amendment.")
        # Advance from the original anchor, never from a clamped intermediate date.
        anchor, n = event_date, 0
        while event_date < as_of:
            n += 1
            if n > 2400:
                raise ValueError("Renewal history is too long to establish the current occurrence.")
            event_date = offset_months(anchor, n * rule.recurrence_months, rule.month_end_rule)
    if rule.offset is None:
        if rule.action != "expiry":
            raise ValueError("The action offset is not established.")
        return event_date, None, None, "Explicit event date: " + event_date.isoformat(), assumptions
    action_date = shift(event_date, rule.offset, rule)
    window_start = None
    if rule.earliest_offset is not None:
        window_start = shift(event_date, rule.earliest_offset, rule)
        if window_start > action_date:
            raise ValueError("The extracted notice window is inconsistent.")
    unit = rule.unit.replace("_", " ")
    operator = "−" if rule.direction == "before" else "+"
    formula = f"{event_date.isoformat()} {operator} {rule.offset} {unit} = {action_date.isoformat()}"
    return event_date, action_date, window_start, formula, assumptions


def calendar_for(doc: Document, pages: list[Page], as_of: date, days: int = 90) -> tuple[list[Event], list[ReviewIssue]]:
    events, issues = [], []
    end = as_of + timedelta(days=days)
    reviews = {v.item_id: v for v in doc.reviews}
    for rule in doc.rules:
        evidence, errors = resolve_citations(rule.citations, pages, {doc.id})
        verdict = reviews.get(rule.id)
        try:
            if errors or not evidence:
                raise ValueError("; ".join(errors) or "The date rule has no validated evidence.")
            if not verdict or verdict.status != "supported":
                raise ValueError(verdict.reason if verdict else "The date rule has not passed support review.")
            event_date, action_date, window_start, formula, assumptions = calculate(rule, as_of)
            relevant = as_of <= event_date <= end or (action_date and as_of <= action_date <= end)
            relevant = relevant or (window_start and window_start <= end and action_date and action_date >= as_of)
            relevant = relevant or (action_date and action_date < as_of and event_date >= as_of)
            if not relevant:
                continue
            confidence, _ = evidence_confidence(evidence, bool(assumptions))
            events.append(Event(
                id=stable_id(doc.id, rule.id, event_date.isoformat()), document_id=doc.id,
                label=rule.label, event_type=rule.event_type, event_date=event_date.isoformat(),
                action_date=action_date.isoformat() if action_date else None,
                window_start=window_start.isoformat() if window_start else None,
                action=ACTION_LABELS[rule.action], formula=formula, assumptions=assumptions,
                confidence=confidence, evidence=evidence,
            ))
        except (ValueError, OverflowError) as error:
            issues.append(ReviewIssue(
                id=stable_id(doc.id, rule.id, "date"), document_ids=[doc.id],
                title="Deadline cannot be established",
                established=[f"Source identifies a date rule for {rule.trigger}."] if evidence else [],
                missing_facts=[str(error)],
                lawyer_question=f"What date and counting/delivery rule applies to {rule.trigger}?",
                evidence=evidence, kind="deadline", mode=doc.mode,
            ))
    return events, issues
