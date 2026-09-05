import type { Portfolio } from './api'
import { actionGroups, reviewItems } from './presentation'

export function OverviewSummary({ portfolio, asOf, stale, onAsOf, onCalendar, onConflicts, onReview }: {
  portfolio: Portfolio | null; asOf: string; stale: boolean; onAsOf: (v:string) => void;
  onCalendar: (category:'upcoming'|'overdue') => void; onConflicts: () => void; onReview: () => void
}) {
  const p = portfolio, coverage = p?.coverage ?? {}, groups = actionGroups(p?.events ?? [])
  const analyzed = coverage.analyzed ?? 0, total = p?.documents.length ?? 0
  const summaries = [
    {label:'Upcoming action deadlines', value:groups.upcoming.length, open:() => onCalendar('upcoming')},
    {label:'Overdue actions / notices', value:groups.overdue.length, open:() => onCalendar('overdue')},
    {label:'Potential conflicts', value:p?.conflicts.filter(c => c.current && c.status === 'potential_conflict').length ?? 0, open:onConflicts},
    {label:'Open review items', value:p ? reviewItems(p).length : 0, open:onReview},
  ]
  return <section className="card overview-summary"><div className="section-heading"><h2>Your contract portfolio{stale ? ' · stale or refreshing' : ''}</h2><label>As-of date (Singapore)<input type="date" value={asOf} onChange={e => onAsOf(e.target.value)} /></label></div>
    <p><strong>{analyzed}/{total} documents completed analysis</strong> · {coverage.pages_analyzed ?? 0}/{coverage.pages ?? 0} pages analyzed · {coverage.pages_read ?? 0}/{coverage.pages ?? 0} pages read.</p>
    <p>Completed analysis does not mean every finding is resolved. Dates cover {p?.as_of ?? asOf} to {p?.horizon_end ?? 'the end of the selected 90-day window'}, including relevant overdue actions.</p>
    <div className="overview-stats">{summaries.map(s => <button className="summary-stat" key={s.label} onClick={s.open} disabled={!p || stale}><span>{s.label}</span><strong>{p ? s.value : '—'}</strong></button>)}</div>
    <p>{Math.max(0,total-analyzed)} documents have incomplete analysis. {p?.comparisons.pending ?? 0} comparisons remain outstanding; {p?.comparisons.failed ?? 0} failed or blocked. {coverage.dates_unavailable ?? 0} documents have source pages unavailable for date checking.</p>
    {!total && <p>Add contracts to begin. An empty workspace tells us nothing about obligations.</p>}
  </section>
}
