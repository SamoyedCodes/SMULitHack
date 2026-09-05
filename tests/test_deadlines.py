"""Phase 4 deadline engine: occurrence enumeration, competence gates and confidence inheritance.

Pure Python over synthetic pages and rules. No model call, no store, no filesystem. Expected dates
were written from the agreement wording in docs/PHASE_4_HANDOFF.md before the engine was repaired.
"""
from datetime import date

import pytest

from backend.deadlines import HORIZON_DAYS, calendar_for
from backend.models import Citation, DeadlineRule, Document, Page, Span, Verdict

DOC = "doc1"
AS_OF = date(2026, 9, 5)          # horizon ends 2026-12-04
EXPIRY_QUOTE = "Written notice must be received sixty calendar days before expiry."


def span(page, n, text, *, doc=DOC, source="native", ocr=None, clause=None):
    return Span(id=f"{doc}:p{page}:s{n}", document_id=doc, page=page, text=text,
                bbox=[0.0, 0.0, 1.0, 1.0], source=source, ocr_confidence=ocr, clause=clause)


def page(number, spans, *, status="read", warnings=None):
    return Page(number=number, width=600, height=800, spans=spans, status=status, warnings=warnings or [])


def sample_pages(**over):
    return [
        page(1, [span(1, 0, "The term expires on 31 December 2026.", clause="2.1")]),
        page(2, [span(2, 1, EXPIRY_QUOTE, clause="8.3", **over)]),
    ]


def cite(span_ids=None, quote=EXPIRY_QUOTE, doc=DOC):
    return Citation(document_id=doc, span_ids=span_ids or [f"{DOC}:p2:s1"], quote=quote)


def rule(**over):
    base = dict(id="r1", label="Renewal notice", event_type="expiry", event_date="2026-12-31",
                trigger="expiry of the term", action="notice_received", offset=60,
                unit="calendar_days", direction="before", citations=[cite()])
    return DeadlineRule(**{**base, **over})


def document(rules, reviews=None, **over):
    base = dict(id=DOC, filename="acme.pdf", title="Acme", sha256="abc", mode="live", status="complete",
                created_at="2026-09-05T00:00:00Z", model="fake", version="1", page_count=2, pages_read=2)
    reviews = [Verdict(item_id=r.id, status="supported", reason="ok") for r in rules] if reviews is None else reviews
    return Document(**{**base, **over}, rules=rules, reviews=reviews)


def run(rules, as_of=AS_OF, pages=None, reviews=None, **over):
    return calendar_for(document(rules, reviews, **over), pages or sample_pages(), as_of, days=HORIZON_DAYS)


# --- arithmetic and windows ------------------------------------------------------


def test_sixty_day_notice_before_expiry_is_subtracted():
    events, issues = run([rule()])
    assert not issues and len(events) == 1
    event = events[0]
    assert event.event_date == "2026-12-31" and event.action_date == "2026-11-01"
    assert event.action == "Notice must be received"          # receipt is never relabelled dispatch
    assert "− 60 calendar days" in event.formula and "2026-11-01" in event.formula
    assert event.evidence and event.provenance == "calculated"


def test_notice_window_keeps_both_boundaries():
    events, _ = run([rule(earliest_offset=90)])
    assert events[0].window_start == "2026-10-02" and events[0].action_date == "2026-11-01"


def test_action_inside_horizon_included_when_event_is_beyond_it():
    events, _ = run([rule()])
    # The 31 December expiry is 27 days past the 2026-12-04 horizon; its November action is not.
    assert events[0].event_date > "2026-12-04" and events[0].action_date < "2026-12-04"


def test_explicit_month_offset_with_valid_target_day_needs_no_month_end_rule():
    events, issues = run([rule(event_date="2026-09-15", offset=1, unit="calendar_months",
                               direction="after", action="payment_due")])
    assert not issues and events[0].action_date == "2026-10-15"


@pytest.mark.parametrize("event_date,included", [
    ("2026-09-05", True), ("2026-12-04", True), ("2026-12-05", False), ("2026-09-04", False)])
def test_horizon_boundaries_are_inclusive(event_date, included):
    events, _ = run([rule(event_date=event_date, offset=None, action="expiry")])
    assert bool(events) is included


# --- recurrence ------------------------------------------------------------------


def monthly():
    return rule(id="r2", label="Monthly fee", event_type="payment", action="payment_due",
                event_date="2026-09-10", recurrence_months=1, offset=7, direction="after")


def test_every_monthly_occurrence_in_horizon_appears_once():
    events, issues = run([monthly()])
    assert not issues
    # 10 Sep/Oct/Nov trigger actions on the 17th; the 10 December occurrence acts beyond the horizon.
    assert [e.event_date for e in events] == ["2026-09-10", "2026-10-10", "2026-11-10"]
    assert [e.occurrence for e in events] == [0, 1, 2]
    assert len({e.id for e in events}) == 3
    assert all("still being in force" in " ".join(e.assumptions) for e in events)


def test_ids_do_not_change_when_as_of_moves():
    early = {e.occurrence: e.id for e in run([monthly()])[0]}
    later = {e.occurrence: e.id for e in run([monthly()], as_of=date(2026, 10, 20))[0]}
    shared = early.keys() & later.keys()
    assert shared and all(early[k] == later[k] for k in shared)


def test_past_trigger_with_after_offset_action_is_not_skipped():
    # The draft advanced past any occurrence before as_of, losing an action still ahead of it.
    events, _ = run([rule(event_date="2026-08-20", recurrence_months=12, offset=30,
                          direction="after", action="review")])
    assert [e.event_date for e in events] == ["2026-08-20"] and events[0].action_date == "2026-09-19"


def test_supported_clamp_does_not_drift_after_february():
    events, issues = run([rule(event_date="2026-01-31", recurrence_months=1, month_end_rule="last_day",
                               offset=None, action="expiry")], as_of=date(2026, 1, 1))
    assert not issues
    # February clamps to the 28th, but March is recomputed from the anchor and returns to the 31st.
    assert [e.event_date for e in events] == ["2026-01-31", "2026-02-28", "2026-03-31"]


def test_supported_clamp_uses_the_leap_day_in_a_leap_year():
    events, _ = run([rule(event_date="2028-01-31", recurrence_months=1, month_end_rule="last_day",
                          offset=None, action="expiry")], as_of=date(2028, 1, 1))
    assert [e.event_date for e in events] == ["2028-01-31", "2028-02-29", "2028-03-31"]


def test_unbounded_recurrence_range_is_refused_visibly():
    events, issues = run([rule(recurrence_months=1, offset=36500, unit="calendar_days")])
    assert not events and len(issues) == 1 and "more than can be presented reliably" in issues[0].missing_facts[0]


# --- overdue ---------------------------------------------------------------------


def test_past_notice_is_overdue_while_its_expiry_is_still_upcoming():
    events, _ = run([rule()], as_of=date(2026, 12, 1))
    assert len(events) == 1 and events[0].overdue is True
    assert events[0].event_date == "2026-12-31" and events[0].action_date == "2026-11-01"
    text = " ".join(events[0].assumptions + [events[0].action, events[0].confidence_reason])
    assert "not established" in text
    for claim in ("still possible", "unpaid", "missed", "breach"):
        assert claim not in text.lower()


def test_recent_lapse_is_shown_but_older_ones_are_not():
    recent = rule(event_date="2026-08-01", offset=25, direction="after", action="payment_due", recurrence_months=None)
    events, _ = run([recent])
    assert len(events) == 1 and events[0].overdue is True and events[0].action_date == "2026-08-26"
    stale, _ = run([rule(event_date="2026-01-01", offset=25, direction="after", action="payment_due")])
    assert not stale


# --- competence gates ------------------------------------------------------------


def only_issue(rules, **kw):
    events, issues = run(rules, **kw)
    assert not events and len(issues) == 1 and issues[0].kind == "deadline"
    return issues[0]


def test_ambiguous_month_end_produces_an_issue_not_a_date():
    issue = only_issue([rule(event_date="2026-01-31", offset=1, unit="calendar_months",
                             direction="after", action="payment_due")], as_of=date(2026, 1, 15))
    assert "month-end" in issue.missing_facts[0]
    assert "does not exist in the target month" in issue.lawyer_question


def test_business_days_require_review_without_a_calendar_day_substitute():
    issue = only_issue([rule(unit="business_days")])
    assert "no calendar-day substitution" in issue.missing_facts[0]
    assert "business day" in issue.lawyer_question and "holiday calendar" in issue.lawyer_question


def test_unknown_receipt_produces_a_specific_question_beside_its_citation():
    issue = only_issue([rule(action="payment_due", offset=30, direction="after",
                             missing_inputs=["The invoice receipt date is not recorded."])])
    assert issue.missing_facts == ["The invoice receipt date is not recorded."]
    assert "invoice received" in issue.lawyer_question
    assert issue.evidence and issue.evidence[0].page == 2 and issue.evidence[0].clause == "8.3"


def test_unsupported_verdict_blocks_the_event():
    issue = only_issue([rule()], reviews=[Verdict(item_id="r1", status="uncertain", reason="Schedule 1 is missing.")])
    assert "Schedule 1 is missing." in issue.missing_facts[0]


def test_unresolved_required_context_blocks_the_event():
    # The draft accepted a "supported" verdict while its required context was still open.
    issue = only_issue([rule()], reviews=[Verdict(item_id="r1", status="supported", reason="ok",
                                                  missing_context=["Schedule 1 was not provided."])])
    assert "Schedule 1 was not provided." in issue.missing_facts[0]


def test_fabricated_quote_is_rejected():
    issue = only_issue([rule(citations=[cite(quote="Notice may be sent at any time.")])])
    assert "does not match" in issue.missing_facts[0]


def test_missing_offset_on_a_non_expiry_rule_is_refused():
    issue = only_issue([rule(offset=None, action="notice_sent")])
    assert "not established" in issue.missing_facts[0]


def test_reversed_notice_window_is_refused():
    issue = only_issue([rule(offset=90, earliest_offset=60)])
    assert "reversed" in issue.missing_facts[0]


def test_established_never_repeats_unvalidated_trigger_text():
    issue = only_issue([rule(unit="unknown", trigger="SENTINEL-MODEL-PROSE")])
    assert issue.established and not any("SENTINEL" in fact for fact in issue.established)
    # Only Python-verified material: a matched quote, the parsed anchor, the recorded verdict.
    assert any(EXPIRY_QUOTE in fact for fact in issue.established)


# --- confidence ------------------------------------------------------------------


def test_calculated_dates_are_never_high_confidence():
    events, _ = run([rule()])
    # The offset, unit and direction are cited for the rule as a whole, not individually.
    assert events[0].confidence == "medium"
    assert any("individually" in assumption for assumption in events[0].assumptions)


def test_explicit_source_date_is_found_rather_than_calculated():
    events, _ = run([rule(event_date="2026-10-01", offset=None, action="expiry")])
    assert events[0].provenance == "found" and events[0].formula.startswith("Explicit event date")


def test_ocr_evidence_never_reaches_high_confidence():
    events, _ = run([rule(event_date="2026-10-01", offset=None, action="expiry")],
                    pages=sample_pages(source="ocr", ocr=95))
    assert events[0].confidence == "medium"
    low, _ = run([rule(event_date="2026-10-01", offset=None, action="expiry")],
                 pages=sample_pages(source="ocr", ocr=40))
    assert low[0].confidence == "low"


def test_incomplete_page_coverage_lowers_confidence():
    events, _ = run([rule()], page_count=3)
    assert events[0].confidence == "low" and "could not be read" in events[0].confidence_reason


def test_no_event_carrying_assumptions_is_high_confidence():
    for rules in ([rule()], [monthly()], [rule(conditions=["Subject to board approval."])]):
        for event in run(rules)[0]:
            assert not (event.assumptions and event.confidence == "high")


# --- ordering and isolation ------------------------------------------------------


def test_events_sort_by_earliest_relevant_date():
    events, _ = run([rule(), monthly()])
    keys = [min(d for d in (e.window_start, e.action_date, e.event_date) if d) for e in events]
    assert keys == sorted(keys)


def test_one_broken_rule_does_not_suppress_a_valid_one():
    events, issues = run([rule(), rule(id="r9", unit="business_days")])
    assert len(events) == 1 and len(issues) == 1


def test_notice_received_always_states_that_dispatch_timing_is_unestablished():
    events, _ = run([rule()])
    assert any("safe date to send notice has not been calculated" in a for a in events[0].assumptions)
