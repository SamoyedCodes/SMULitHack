import { useCallback, useEffect, useRef, useState } from 'react'
import { CalendarDays, ChevronRight, CircleAlert, FolderOpen, LayoutDashboard, Plus, Quote, RefreshCw, Scale, ShieldCheck } from 'lucide-react'
import { fetchHealth, fetchLivePortfolio, setSme, type Finding, type Health, type Portfolio } from './api'

const FIELD_LABELS: Record<Finding['field'], string> = {
  parties: 'Parties', term: 'Term', renewal: 'Renewal mechanics', notice: 'Notice requirements',
  termination: 'Termination rights', payments: 'Payment obligations',
  liability: 'Liability caps and exceptions', restrictions: 'Exclusivity and restrictive covenants',
}
const FIELD_ORDER = Object.keys(FIELD_LABELS) as Finding['field'][]

const navigation = [
  { name: 'Overview', icon: LayoutDashboard },
  { name: 'Contracts', icon: FolderOpen },
  { name: 'Calendar', icon: CalendarDays },
  { name: 'Conflicts', icon: Scale },
  { name: 'Needs review', icon: CircleAlert },
] as const
type View = typeof navigation[number]['name']

export function Readiness({ health, stale }: { health: Health | null; stale: boolean }) {
  const rows = [
    ['Local API', health ? (health.status === 'ready' ? 'Ready' : 'Degraded') : 'Checking', 'Local service readiness does not mean contracts have been analyzed.'],
    ['SQLite database', health?.database.status ?? 'Checking', 'Saved metadata and queued work persist locally.'],
    ['Gemini', health ? (health.key_configured ? 'Configured, not verified' : 'Not configured') : 'Checking', 'Optional in Phase 1. Configure GEMINI_API_KEY in the repository .env for the extraction phase.'],
    ['Tesseract OCR', health ? (health.ocr_available ? 'Executable detected' : 'Not detected') : 'Checking', 'Optional now. Install Tesseract or set TESSERACT_CMD before processing scans.'],
    ['DOCX conversion', health ? (health.docx_available ? 'Executable detected' : 'Not detected') : 'Checking', 'Optional now. Install LibreOffice or set LIBREOFFICE_CMD before converting DOCX files.'],
    ['Processing worker', health ? (health.worker.running ? 'Running' : health.worker.enabled ? 'Enabled, stopped' : 'Disabled') : 'Checking', 'Phase 1 does not start processing, OCR or model requests.'],
  ]
  return <section className="card readiness"><div className="section-heading"><h2>Workspace readiness</h2><span className="badge">{stale ? 'Last response · stale' : 'Local checks'}</span></div><div className="readiness-grid">{rows.map(([title, value, note]) => <article key={title}><h3>{title}</h3><strong>{stale ? `${value} · stale` : value}</strong><p>{note}</p></article>)}</div></section>
}

function Evidence({ items }: { items: Finding['evidence'] }) {
  if (!items.length) return null
  return <ul className="evidence">{items.map((e, i) => <li key={i}><Quote size={13} /><blockquote>{e.quote}</blockquote><cite>Page {e.page}{e.clause ? ` · ${e.clause}` : ''}{e.source === 'ocr' ? ' · OCR' : ''}</cite></li>)}</ul>
}

function FindingRow({ finding, stale }: { finding: Finding; stale: boolean }) {
  const resolved = finding.provenance !== 'unresolved' && finding.value != null
  return <article className={`finding provenance-${finding.provenance}`}>
    <div className="finding-head"><h4>{FIELD_LABELS[finding.field]}{finding.party ? <span className="finding-party"> · {finding.party}</span> : null}</h4>
      <div className="finding-badges"><span className={`badge provenance ${finding.provenance}`}>{finding.provenance}</span><span className={`badge confidence ${finding.confidence}`}>{finding.confidence} confidence</span></div></div>
    <p className="finding-value">{resolved ? finding.value : 'Not established in this document. This does not mean no obligation exists.'}</p>
    {finding.conditions.length ? <ul className="finding-conditions">{finding.conditions.map((c, i) => <li key={i}>{c}</li>)}</ul> : null}
    <p className="finding-reason">{finding.confidence_reason}{stale ? ' · stale' : ''}</p>
    <Evidence items={finding.evidence} />
  </article>
}

export function Contracts({ portfolio, stale }: { portfolio: Portfolio | null; stale: boolean }) {
  const docs = portfolio?.documents ?? []
  if (!docs.length) return <section className="card foundation-empty"><FolderOpen size={30} /><h2>No contracts have been analyzed yet</h2><p>Once documents are ingested and extracted, every field below is shown with its source, provenance and confidence. An empty workspace tells us nothing about obligations in documents that have not been processed.</p></section>
  return <>{docs.map(doc => {
    const byField = new Map(doc.findings.map(f => [f.field, f]))
    return <section className="card contract-card" key={doc.id}>
      <div className="section-heading"><h2>{doc.filename}</h2><span className="badge">{doc.status.replaceAll('_', ' ')}{stale ? ' · stale' : ''}</span></div>
      <p className="contract-stage">{doc.stage}{doc.error ? ` — ${doc.error}` : ''} · {doc.pages_analyzed}/{doc.page_count} pages analyzed</p>
      <div className="findings">{FIELD_ORDER.map(field => { const f = byField.get(field); return f ? <FindingRow key={field} finding={f} stale={stale} /> : null })}</div>
    </section>
  })}</>
}

function SmeSelector({ portfolio, disabled, onChoose }: { portfolio: Portfolio | null; disabled: boolean; onChoose: (name: string | null) => void }) {
  const parties = portfolio?.parties ?? []
  return <label className="sme-selector">Established party (your organisation)
    <select value={portfolio?.sme ?? ''} disabled={disabled || !parties.length} onChange={e => onChoose(e.target.value || null)}>
      <option value="">{parties.length ? 'Not selected' : 'No parties extracted yet'}</option>
      {parties.map(p => <option key={p} value={p}>{p}</option>)}
    </select>
  </label>
}

export default function App() {
  const [view, setView] = useState<View>('Overview')
  const [health, setHealth] = useState<Health | null>(null)
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null)
  const [checking, setChecking] = useState(true)
  const [error, setError] = useState('')
  const [stale, setStale] = useState(false)
  const [checkedAt, setCheckedAt] = useState<string | null>(null)
  const active = useRef<AbortController | null>(null)
  const refresh = useCallback(async () => {
    if (active.current) return
    const controller = new AbortController()
    active.current = controller
    setChecking(true)
    try {
      const latest = await fetchHealth(controller.signal)
      if (controller.signal.aborted) return
      setHealth(latest)
      setCheckedAt(new Date().toLocaleTimeString('en-SG', { timeZone: 'Asia/Singapore' }))
      if (latest.status !== 'ready') throw new Error('The backend is reachable, but its database is unavailable.')
      const data = await fetchLivePortfolio(controller.signal)
      if (controller.signal.aborted) return
      setPortfolio(data); setStale(false); setError('')
    } catch (cause) {
      if (!controller.signal.aborted) { setError(cause instanceof Error ? cause.message : 'Connection check failed.'); setStale(true) }
    } finally {
      if (active.current === controller) { active.current = null; if (!controller.signal.aborted) setChecking(false) }
    }
  }, [])
  useEffect(() => {
    void refresh()
    const timer = setInterval(() => void refresh(), 10000)
    return () => { clearInterval(timer); active.current?.abort(); active.current = null }
  }, [refresh])
  const [smeBusy, setSmeBusy] = useState(false)
  const chooseSme = useCallback(async (name: string | null) => {
    setSmeBusy(true)
    try { await setSme(name); await refresh() }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not update the established party.') }
    finally { setSmeBusy(false) }
  }, [refresh])

  const extraction = Boolean(health?.capabilities.extraction)
  const connected = Boolean(health?.status === 'ready' && !stale && portfolio)
  const status = error ? (health?.status === 'degraded' ? 'Degraded' : 'Disconnected') : connected ? 'Local service ready' : 'Checking connection'
  const explanation: Record<Exclude<View, 'Overview'>, string> = {
    Contracts: 'Document ingestion and source viewing arrive in Phase 2. No new documents can be processed in this build.',
    Calendar: 'Deadline calculations arrive in Phase 4. No deadlines have been calculated in this build.',
    Conflicts: 'Distribution conflict assessment arrives in Phase 5. Agreements have not been checked for compatibility in this build.',
    'Needs review': 'Evidence review and lawyer briefs arrive in later phases. An empty queue does not mean there are no unresolved obligations.',
  }
  return <div className="app-shell foundation-shell">
    <aside className="sidebar"><a className="brand" href="#" onClick={event => { event.preventDefault(); setView('Overview') }}><span className="brand-mark"><Scale size={24} /></span>aithena<span className="brand-dot">.</span></a><div className="workspace-label">LOCAL WORKSPACE</div><nav aria-label="Main navigation">{navigation.map(({ name, icon: Icon }) => <button key={name} className={`nav-item ${view === name ? 'active' : ''}`} aria-current={view === name ? 'page' : undefined} onClick={() => setView(name)}><Icon size={19} />{name}</button>)}</nav><div className="sidebar-bottom"><ShieldCheck /><strong>Evidence comes first.</strong><p>Know what is established.<br />See what needs review.</p><div className="profile">{portfolio?.sme ?? 'SME not selected'}<small>{portfolio?.sme ? 'Established party for this workspace.' : extraction ? 'Choose your organisation in Contracts.' : 'Party selection arrives with extraction.'}</small></div></div></aside>
    <div className="main-shell"><header className="topbar"><div>Workspace <ChevronRight size={14} /><strong>{view}</strong></div><span role="status" className={`badge ${connected ? 'green' : 'amber'}`}>{status}</span></header><main>
      <div className="page-heading"><div><div className="eyebrow">AITHENA · {extraction ? 'GROUNDED EXTRACTION' : 'PHASE 1'}</div><h1>{view === 'Overview' ? 'Workspace overview' : view}</h1><p>A connected foundation for evidence-backed contract review.</p></div><div className="heading-actions"><button className="secondary" disabled={checking} onClick={() => void refresh()}><RefreshCw size={18} className={checking ? 'spin' : ''} />Check connection</button><button className="primary" disabled aria-describedby="ingestion-note"><Plus size={18} />Add contracts</button></div></div>
      <p id="ingestion-note" className="phase-notice">Contract ingestion is not enabled. Uploads become available in Phase 2.</p>
      {error && <div className="error" role="alert">{error} {health && 'Previous information below must not be treated as current.'}</div>}
      {checkedAt && <p className="check-time">Last response: {checkedAt} SGT{stale ? ' · stale' : ''}. Checks repeat every 10 seconds.</p>}
      {view === 'Overview' ? <><Readiness health={health} stale={stale} /><section className="card foundation-empty"><FolderOpen size={30} /><h2>{portfolio?.documents.length ? `${portfolio.documents.length} saved document records${stale ? ' · stale' : ''}` : 'No contracts have been analyzed in this build'}</h2><p>{portfolio?.documents.length ? 'Existing records are preserved. Processing and analysis remain disabled; saved results are not recomputed.' : 'The workspace is ready for future ingestion. An empty workspace tells us nothing about obligations in documents that have not been processed.'}</p></section>{health && <section className="card capability-card"><h2>Available capabilities{stale ? ' · stale' : ''}</h2><ul>{Object.entries(health.capabilities).map(([name, enabled]) => <li key={name}><span>{name.replaceAll('_', ' ')}</span><span>{enabled ? 'Backend enabled' : 'Not enabled'}</span></li>)}</ul><p>{health.inference_notice}</p></section>}</> : view === 'Contracts' && extraction ? <><SmeSelector portfolio={portfolio} disabled={smeBusy || checking} onChoose={name => void chooseSme(name)} /><Contracts portfolio={portfolio} stale={stale} /></> : <section className="card foundation-empty"><FolderOpen size={30} /><h2>{view} is awaiting its implementation phase</h2><p>{explanation[view]}</p>{view === 'Contracts' && Boolean(portfolio?.documents.length) && <ul className="saved-documents">{portfolio?.documents.map(doc => <li key={doc.id}><strong>{doc.filename}</strong><span>{doc.status} · {doc.stage}{stale ? ' · stale' : ''}</span></li>)}</ul>}</section>}
      <footer><ShieldCheck size={16} /><span>Found · Calculated · Inferred · Unresolved — provenance stays separate from confidence.</span></footer>
    </main></div>
  </div>
}
