import { useEffect } from 'react'
import { actionGroups } from './presentation'
import { AlertTriangle, CalendarClock } from 'lucide-react'
import { Evidence as EvidenceLinks } from './Findings'
import type { CalendarEvent, Evidence, Portfolio, ReviewIssue } from './api'

const MONTHS = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']

/** The date a reader must act on: the window opening, else the deadline, else the event itself. */
export function actionableDate(event: CalendarEvent): string {
  return event.window_start ?? event.action_date ?? event.event_date
}

export function groupByDate(events: CalendarEvent[]): [string, CalendarEvent[]][] {
  const groups = new Map<string, CalendarEvent[]>()
  for (const event of events) groups.set(actionableDate(event), [...(groups.get(actionableDate(event)) ?? []), event])
  return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b))
}

function DateTile({ day }: { day: string }) {
  const [, month, date] = day.split('-')
  return <div className="date-tile"><small>{MONTHS[Number(month) - 1]}</small><strong>{Number(date)}</strong></div>
}

function EventRow({ event, stale, onEvidence }: { event: CalendarEvent; stale: boolean; onEvidence: (e: Evidence) => void }) {
  return <article id={`event-${event.id}`} tabIndex={-1} className="calendar-row">
    <DateTile day={actionableDate(event)} />
    <div className="row-copy">
      <h3>{event.label}</h3>
      <p className="due-label">{event.action}{event.action_date ? ` by ${event.action_date}` : ''} · {event.event_type} on {event.event_date}</p>
      {event.window_start && event.action_date && <p className="due-label">Window open {event.window_start} to {event.action_date}</p>}
      <p className="calendar-formula">{event.formula}</p>
      {event.assumptions.map((note, i) => <p key={i} className="subtle">{note}</p>)}
    </div>
    <div className="calendar-badges">
      {event.overdue && <span className="badge amber">Overdue · performance not established</span>}
      <span className={`badge provenance ${event.provenance}`}>{event.provenance}</span>
      <span className={`badge confidence ${event.confidence}`}>{event.confidence}{stale ? ' · stale' : ''}</span>
      <p className="finding-reason">{event.confidence_reason}</p>
      <EvidenceLinks items={event.evidence} onEvidence={onEvidence} />
    </div>
  </article>
}

export function Calendar({ portfolio, asOf, enabled, stale, onAsOf, onEvidence, focused = null, category = 'all', onCategory = () => {} }: {
  portfolio: Portfolio | null; asOf: string; enabled: boolean; stale: boolean
  onAsOf: (value: string) => void; onEvidence: (e: Evidence) => void
  focused?: string | null; category?: 'all' | 'upcoming' | 'overdue' | 'events'; onCategory?: (value: 'all' | 'upcoming' | 'overdue' | 'events') => void
}) {
  const allEvents = portfolio?.events ?? []
  const events = category === 'all' ? allEvents : actionGroups(allEvents)[category]
  const targetExists = Boolean(focused && allEvents.some(e => e.id === focused))
  useEffect(() => {
    if (focused && targetExists) {
      const element = document.getElementById(`event-${focused}`)
      element?.focus({preventScroll:true}); element?.scrollIntoView({block:'center'})
    }
  }, [focused, targetExists, category])
  const issues = (portfolio?.issues ?? []).filter((issue: ReviewIssue) => issue.kind === 'deadline')
  const coverage = portfolio?.coverage ?? {}
  const undated = (coverage.undated ?? 0) + (coverage.dates_unavailable ?? 0)
  return <>
    <section className="card calendar-controls">
      <div className="section-heading"><h2>Upcoming dates{stale ? ' · stale' : ''}</h2><span className="badge">{events.length} relevant dates · includes overdue</span></div>
      <label>Show<select value={category} onChange={e => onCategory(e.target.value as typeof category)}><option value="all">All dates</option><option value="upcoming">Upcoming action deadlines</option><option value="overdue">Overdue actions</option><option value="events">Events without action deadlines</option></select></label>
      {focused && !targetExists && <p role="alert">The selected event changed or is no longer in this date window.</p>}
      <label className="calendar-asof">As-of date (Singapore)
        <input type="date" value={asOf} disabled={!enabled} onChange={event => onAsOf(event.target.value)} />
      </label>
      <p className="due-label">Showing events and action deadlines from {portfolio?.as_of ?? asOf} to {portfolio?.horizon_end ?? '—'}, inclusive.</p>
      <p className="subtle">Dates are calculated locally from cited contract wording. No model request is made to build this calendar. A date shown here is not advice that an action is still effective.</p>
    </section>

    {!enabled && <section className="card foundation-empty"><CalendarClock size={30} /><h2>Calendar is unavailable</h2><p>The backend is not reporting the deadline capability, so no dates can be relied on here.</p></section>}

    {enabled && !events.length && <section className="card foundation-empty"><CalendarClock size={30} /><h2>{allEvents.length ? 'No dates match this filter' : 'No dates found in the documents that were checked'}</h2>
      <p>{allEvents.length ? 'Other dates exist in this window; choose All dates to see them.' : coverage.dated ? `${coverage.dated} document(s) were checked and produced no event or deadline in this window.` : 'No document has completed analysis, so nothing has been checked for dates.'}
        {undated ? ` ${undated} document(s) could not be checked and may contain deadlines.` : ''} An empty window is not a finding that no obligations exist.</p></section>}

    {enabled && groupByDate(events).map(([day, group]) => <section className="card calendar-day" key={day}>
      <div className="section-heading"><h2>{day}</h2><span className="badge">{group.length} item(s)</span></div>
      {group.map(event => <EventRow key={event.id} event={event} stale={stale} onEvidence={onEvidence} />)}
    </section>)}

    {enabled && undated > 0 && <section className="card attention-card"><h2>{undated} document(s) were not checked for dates</h2>
      <p className="subtle">{coverage.undated ?? 0} are still being processed or have not completed analysis, and {coverage.dates_unavailable ?? 0} have source pages that could not be read. Their deadlines are unknown, not absent.</p></section>}

    {enabled && issues.length > 0 && <section className="card calendar-review">
      <div className="section-heading"><h2>Dates that could not be established</h2><span className="badge amber">{issues.length}</span></div>
      {issues.map(issue => <article className="finding" key={issue.id}>
        <h3><AlertTriangle size={15} /> {issue.title}</h3>
        {issue.established.length > 0 && <><h4>Established</h4><ul className="calendar-facts">{issue.established.map((fact, i) => <li key={i}>{fact}</li>)}</ul></>}
        <h4>Missing</h4>
        {issue.missing_facts.map((fact, i) => <p key={i}>{fact}</p>)}
        <p className="review-question">{issue.lawyer_question}</p>
        <EvidenceLinks items={issue.evidence} onEvidence={onEvidence} />
      </article>)}
    </section>}
  </>
}

export function UpcomingActions({ portfolio, onOpen, onEvent, stale = false }: { portfolio: Portfolio | null; onOpen: () => void; onEvent?: (id:string) => void; stale?: boolean }) {
  const groups = actionGroups(portfolio?.events ?? [])
  const coverage = portfolio?.coverage ?? {}
  const undated = (coverage.undated ?? 0) + (coverage.dates_unavailable ?? 0)
  return <section className="card overview-actions"><div className="section-heading"><h2>Next actions{stale ? ' · stale' : ''}</h2><button className="text-button" onClick={onOpen}>Open calendar</button></div>
    {([['overdue','Overdue actions'], ['upcoming','Upcoming action deadlines'], ['events','Events without action deadlines']] as const).map(([key,label]) => <section key={key}><h3>{label} ({groups[key].length})</h3>
      {groups[key].length === 0 ? <p>No established items in this group.</p> : groups[key].slice(0,4).map(event => <button id={`action-${event.id}`} disabled={stale} className="action-row" key={event.id} onClick={() => onEvent ? onEvent(event.id) : onOpen()}>
        <DateTile day={event.action_date ?? event.event_date} />
        <span className="row-copy"><strong>{event.label}</strong><span className="due-label">{event.action}{event.action_date ? ` by ${event.action_date}` : ''} · {event.event_type} on {event.event_date}</span>
        {event.window_start && <span>Window opens {event.window_start}</span>}</span>
        {event.overdue && <span className="badge amber">Overdue · performance not established</span>}
      </button>)}{groups[key].length > 4 && <p>Showing 4 of {groups[key].length}. Open calendar for every item.</p>}</section>)}
    <p>{undated} document(s) have no established dates yet. This list covers only checked documents; an empty list is not an all-clear.</p>
  </section>
}
