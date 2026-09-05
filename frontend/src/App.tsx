import { useCallback, useEffect, useRef, useState } from 'react'
import { CalendarDays, ChevronRight, CircleAlert, FolderOpen, LayoutDashboard, Plus, RefreshCw, Scale, ShieldCheck } from 'lucide-react'
import { Calendar, UpcomingActions } from './Calendar'
import { Review, reviewItems } from './Review'
import Conflicts, { ConflictNotifications } from './Conflicts'
import { DocumentLibrary, RecentBatch, SourceViewer, UploadPanel } from './Ingestion'
import { ExtractionAction, Findings, SmeSelector } from './Findings'
import { fetchHealth, fetchLivePortfolio, setSme, type Evidence, type Health, type Portfolio } from './api'

const singaporeToday = () => new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Singapore' })

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
    ...(health?.providers ?? []).map(provider => [`${provider.name === 'openrouter' ? 'OpenRouter' : 'Gemini'} · ${provider.role}`, provider.key_configured ? 'Configured, not verified' : 'Not configured', `${provider.model} · Credentials stay in the backend. Availability has not been verified.`]),
    ['Tesseract OCR', health ? (health.ocr_available ? 'Executable detected' : 'Not detected') : 'Checking', 'Needed for scans. Install Tesseract or set TESSERACT_CMD before processing scans.'],
    ['DOCX conversion', health ? (health.docx_available ? 'Executable detected' : 'Not detected') : 'Checking', 'Needed for DOCX. Install LibreOffice or set LIBREOFFICE_CMD before converting DOCX files.'],
    ['Processing worker', health ? (health.worker.running ? 'Running' : health.worker.enabled ? 'Enabled, stopped' : 'Disabled') : 'Checking', 'The worker reads files locally and processes explicitly requested extraction jobs through OpenRouter, with Gemini as secondary.'],
  ]
  return <section className="card readiness"><div className="section-heading"><h2>Workspace readiness</h2><span className="badge">{stale ? 'Last response · stale' : 'Local checks'}</span></div><div className="readiness-grid">{rows.map(([title, value, note]) => <article key={title}><h3>{title}</h3><strong>{stale ? `${value} · stale` : value}</strong><p>{note}</p></article>)}</div></section>
}

export default function App() {
  const [focusedConflict, setFocusedConflict] = useState<string | null>(null)
  const [evidence, setEvidence] = useState<Evidence | null>(null)
  const [smeBusy, setSmeBusy] = useState(false)
  const [uploadOpen, setUploadOpen] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [view, setView] = useState<View>('Overview')
  const [health, setHealth] = useState<Health | null>(null)
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null)
  const [checking, setChecking] = useState(true)
  const [error, setError] = useState('')
  const [stale, setStale] = useState(false)
  const [checkedAt, setCheckedAt] = useState<string | null>(null)
  const [asOf, setAsOf] = useState(singaporeToday)
  const asOfRef = useRef(asOf)
  const active = useRef<AbortController | null>(null)
  const refresh = useCallback(async (force = false) => {
    // A new as-of date must supersede an in-flight read; the ordinary poll still never overlaps.
    if (active.current) { if (!force) return; active.current.abort() }
    const controller = new AbortController()
    active.current = controller
    setChecking(true)
    try {
      const latest = await fetchHealth(controller.signal)
      if (controller.signal.aborted) return
      setHealth(latest)
      setCheckedAt(new Date().toLocaleTimeString('en-SG', { timeZone: 'Asia/Singapore' }))
      if (latest.status !== 'ready') throw new Error('The backend is reachable, but its database is unavailable.')
      const data = await fetchLivePortfolio(controller.signal, asOfRef.current)
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
    const timer = setInterval(() => void refresh(), 3000)
    return () => { clearInterval(timer); active.current?.abort(); active.current = null }
  }, [refresh])

  async function chooseSme(name: string | null) {
    setSmeBusy(true)
    try { await setSme(name); await refresh() } catch (cause) { setError((cause as Error).message) } finally { setSmeBusy(false) }
  }
  function openDocument(id: string) { setEvidence(null); setSelectedId(id) }
  function openEvidence(e: Evidence) { setEvidence(e); setSelectedId(e.document_id) }
  function openConflict(id: string) { setFocusedConflict(id); setSelectedId(null); setView('Conflicts') }
  const conflictCount = portfolio?.conflicts.filter(c => c.current && c.status === 'potential_conflict').length ?? 0
  function chooseAsOf(value: string) { if (!value) return; setAsOf(value); asOfRef.current = value; void refresh(true) }
  const contextChanged = Boolean(portfolio && portfolio.as_of !== asOf)
  const reviewCount = portfolio && health?.capabilities.handoff ? reviewItems(portfolio).length : 0
  const connected = Boolean(health?.status === 'ready' && !stale && !contextChanged && portfolio)
  const ingestionEnabled = Boolean(connected && health?.capabilities.ingestion)
  const deadlinesEnabled = Boolean(connected && health?.capabilities.deadlines)
  const selectedDocument = portfolio?.documents.find(doc => doc.id === selectedId)
  const status = error ? (health?.status === 'degraded' ? 'Degraded' : 'Disconnected') : connected ? 'Local service ready' : 'Checking connection'
  const explanation: Record<Exclude<View, 'Overview' | 'Calendar'>, string> = {
    Contracts: 'Document ingestion and source viewing arrive in Phase 2. No new documents can be processed in this build.',
    Conflicts: 'Distribution conflict assessment arrives in Phase 5. Agreements have not been checked for compatibility in this build.',
    'Needs review': 'Evidence review and lawyer briefs arrive in later phases. An empty queue does not mean there are no unresolved obligations.',
  }
  return <div className="app-shell foundation-shell">
    <aside className="sidebar"><a className="brand" href="#" onClick={event => { event.preventDefault(); setView('Overview') }}><span className="brand-mark"><Scale size={24} /></span>aithena<span className="brand-dot">.</span></a><div className="workspace-label">LOCAL WORKSPACE</div><nav aria-label="Main navigation">{navigation.map(({ name, icon: Icon }) => <button key={name} className={`nav-item ${view === name ? 'active' : ''}`} aria-current={view === name ? 'page' : undefined} onClick={() => { setView(name); setSelectedId(null) }}><Icon size={19} />{name}{name === 'Needs review' && reviewCount > 0 && <span className="nav-count">{reviewCount}</span>}{name === 'Conflicts' && conflictCount > 0 && <span className="nav-count">{conflictCount}</span>}</button>)}</nav><div className="sidebar-bottom"><ShieldCheck /><strong>Evidence comes first.</strong><p>Know what is established.<br />See what needs review.</p><div className="profile">{portfolio?.sme ?? 'SME not selected'}<small>Choose your organisation in Contracts.</small></div></div></aside>
    <div className="main-shell"><header className="topbar"><div>Workspace <ChevronRight size={14} /><strong>{view}</strong></div><span role="status" className={`badge ${connected ? 'green' : 'amber'}`}>{status}</span></header><main>
      <div className="page-heading"><div><h1>{view === 'Overview' ? 'Workspace overview' : view}</h1><p>A connected foundation for evidence-backed contract review.</p></div><div className="heading-actions"><button className="secondary" disabled={checking} onClick={() => void refresh()}><RefreshCw size={18} className={checking ? 'spin' : ''} />Check connection</button><button className="primary" disabled={!ingestionEnabled} aria-describedby="ingestion-note" onClick={() => setUploadOpen(true)}><Plus size={18} />Add contracts</button></div></div>
      <p id="ingestion-note" className="phase-notice">{ingestionEnabled ? "Local reading is available. Open a document to request extraction (OpenRouter primary, Gemini secondary). Distribution comparisons start automatically after SME selection and extraction; dates are calculated locally, and review items open printable lawyer briefs." : "Connect to the backend to upload and read documents locally."}</p>
      {error && <div className="error" role="alert">{error} {health && 'Previous information below must not be treated as current.'}</div>}
      {checkedAt && <p className="check-time">Last response: {checkedAt} SGT{stale ? ' · stale' : ''}. Checks repeat every 3 seconds.</p>}
      {uploadOpen && health && <UploadPanel health={health} enabled={ingestionEnabled} onClose={() => setUploadOpen(false)} onUploaded={() => { setUploadOpen(false); setSelectedId(null); setView('Contracts'); void refresh() }} />}
      {selectedDocument ? <><ExtractionAction document={selectedDocument} enabled={Boolean(connected && health?.capabilities.extraction)} onRefresh={() => void refresh()} /><div className="contract-detail"><Findings document={selectedDocument} stale={stale || !['complete','needs_review'].includes(selectedDocument.status)} onEvidence={setEvidence} /><SourceViewer backLabel={view === 'Conflicts' ? '← Conflicts' : view === 'Calendar' ? '← Calendar' : undefined} key={selectedDocument.id} document={selectedDocument} evidence={evidence} enabled={ingestionEnabled} onClose={() => setSelectedId(null)} /></div></> : <>
      {view === 'Overview' ? <><Readiness health={health} stale={stale} /><section className="card foundation-empty"><FolderOpen size={30} /><h2>{portfolio?.documents.length ? `${portfolio.documents.length} saved document records${stale ? ' · stale' : ''}` : 'No contracts have been analyzed in this build'}</h2><p>{portfolio?.documents.length ? 'Original files stay local. Requested extraction sends page text to OpenRouter or Gemini; text readiness alone is not analysis.' : 'Add contracts to read their pages locally. An empty workspace tells us nothing about obligations in unprocessed documents.'}</p></section>{deadlinesEnabled && <UpcomingActions portfolio={portfolio} onOpen={() => setView('Calendar')} />}{health && <section className="card capability-card"><h2>Available capabilities{stale ? ' · stale' : ''}</h2><ul>{Object.entries(health.capabilities).map(([name, enabled]) => <li key={name}><span>{name.replaceAll('_', ' ')}</span><span>{enabled ? 'Backend enabled' : 'Not enabled'}</span></li>)}</ul><p>{health.inference_notice}</p></section>}</> : view === 'Calendar' ? <Calendar portfolio={portfolio} asOf={asOf} enabled={deadlinesEnabled} stale={stale || contextChanged} onAsOf={chooseAsOf} onEvidence={openEvidence} /> : view === 'Contracts' ? <><SmeSelector portfolio={portfolio} disabled={!connected || !health?.capabilities.extraction || smeBusy} onChoose={name => void chooseSme(name)} /><DocumentLibrary documents={portfolio?.documents ?? []} enabled={ingestionEnabled} stale={stale} onOpen={openDocument} onRefresh={() => void refresh()} /><RecentBatch revision={checkedAt ?? ''} /></> : view === 'Conflicts' && portfolio && health?.capabilities.conflicts ? <Conflicts portfolio={portfolio} enabled={connected} stale={stale} focused={focusedConflict} onEvidence={openEvidence} onRefresh={() => void refresh()} onChooseSme={() => setView('Contracts')} /> : view === 'Needs review' && portfolio && health?.capabilities.handoff ? <Review portfolio={portfolio} enabled={connected} /> : <section className="card foundation-empty"><FolderOpen size={30} /><h2>{view} is awaiting its implementation phase</h2><p>{explanation[view]}</p></section>}
      </>}
      <ConflictNotifications portfolio={portfolio} enabled={Boolean(connected && health?.capabilities.conflicts)} onOpen={openConflict} />
      <footer><ShieldCheck size={16} /><span>Found · Calculated · Inferred · Unresolved — provenance stays separate from confidence.</span></footer>
    </main></div>
  </div>
}
