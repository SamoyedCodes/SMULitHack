import { useEffect, useRef, useState, type ReactNode } from 'react'
import { ArrowDownToLine, ArrowRight, CalendarDays, Check, ChevronRight, CircleAlert, FileText, FolderOpen, LayoutDashboard, Plus, RefreshCw, Scale, Search, ShieldCheck, UploadCloud, X } from 'lucide-react'
import { fieldNames, type Contract, type Evidence, type Portfolio, type Field } from '../../shared/types'
import { apiBase, daysBetween, demoPortfolio, fetchPortfolio, formatDate, upcomingActions, uploadDocument, validateFiles } from './data'

type View = 'Overview' | 'Contracts' | 'Calendar' | 'Conflicts'
type Panel = { title: string; content: ReactNode }
const labels = { parties: 'Parties', term: 'Contract term', renewal: 'Renewal & notice', termination: 'Termination rights', payment: 'Payment obligations', liability: 'Liability cap', restrictions: 'Restrictions & exclusivity' }
const navigation = [{ name: 'Overview', icon: LayoutDashboard }, { name: 'Contracts', icon: FolderOpen }, { name: 'Calendar', icon: CalendarDays }, { name: 'Conflicts', icon: Scale }] as const

function Badge({ children, tone = 'neutral' }: { children: ReactNode; tone?: string }) { return <span className={`badge ${tone}`}>{children}</span> }
function Empty({ children }: { children: ReactNode }) { return <div className="empty"><FolderOpen size={28} /><p>{children}</p></div> }
function Modal({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null)
  useEffect(() => { ref.current?.showModal(); const dialog = ref.current; return () => dialog?.close() }, [])
  return <dialog ref={ref} onCancel={onClose} onClick={event => { if (event.target === event.currentTarget) onClose() }}><div className="dialog-header"><h2>{title}</h2><button className="icon-button" aria-label="Close dialog" onClick={onClose}><X /></button></div>{children}</dialog>
}
function Sources({ evidence, portfolio }: { evidence: Evidence[]; portfolio: Portfolio }) {
  return <div className="sources">{evidence.length === 0 ? <p>No source has been established. Human review is needed.</p> : evidence.map((source, index) => {
    const doc = portfolio.documents.find(doc => doc.id === source.document_id)
    const page = doc?.pages.find(page => page.number === source.page)
    return <article className="source" key={`${source.document_id}-${source.page}-${index}`}><div className="source-label"><FileText size={16} />{doc?.filename} · Page {source.page} · Clause {source.clause}</div><blockquote>{source.quote}</blockquote><details><summary>Read surrounding page text</summary><pre>{page?.text ?? 'Source page unavailable.'}</pre></details><small>{page?.method === 'ocr' ? `OCR transcription · ${page.quality} scan quality` : 'Extracted document text'} · A matching quote does not prove the interpretation is correct.</small></article>
  })}</div>
}
function FieldValue({ field, onClick }: { field: Field; onClick: () => void }) {
  return <><div className="field-flags"><Badge tone={field.basis === 'unresolved' ? 'amber' : field.basis === 'inferred' ? 'blue' : 'green'}>{field.basis === 'unresolved' ? 'Needs review' : field.basis === 'inferred' ? 'Inferred' : 'Found'}</Badge><small>{field.confidence} confidence</small></div><p>{field.value ?? 'Unable to establish from this document.'}</p><button className="text-button" onClick={onClick}>View evidence <ArrowRight size={15} /></button></>
}
function downloadBrief(data: unknown) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }))
  const link = document.createElement('a'); link.href = url; link.download = 'aithena-review-brief.json'; link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export default function App() {
  const [portfolio, setPortfolio] = useState<Portfolio | null>(apiBase ? null : demoPortfolio)
  const [view, setView] = useState<View>('Overview')
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('all')
  const [selected, setSelected] = useState<Contract | null>(null)
  const [panel, setPanel] = useState<Panel | null>(null)
  const [uploadOpen, setUploadOpen] = useState(false)
  const [files, setFiles] = useState<File[]>([])
  const [uploadResults, setUploadResults] = useState<Record<string, string>>({})
  const [error, setError] = useState('')
  const [uploadError, setUploadError] = useState('')
  const [loading, setLoading] = useState(Boolean(apiBase))
  const [uploading, setUploading] = useState(false)
  const [dragging, setDragging] = useState(false)
  const input = useRef<HTMLInputElement>(null)

  async function refresh() {
    setLoading(true); setError('')
    try { setPortfolio(await fetchPortfolio()); setSelected(null); setPanel(null) } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to load contracts.') } finally { setLoading(false) }
  }
  useEffect(() => { if (apiBase) void refresh() }, [])
  useEffect(() => {
    const context = (document as Document & { modelContext?: { registerTool: (tool: unknown, options: { signal: AbortSignal }) => void | Promise<void> } }).modelContext
    if (!context || !portfolio) return
    const controller = new AbortController()
    try {
      void Promise.resolve(context.registerTool({ name: 'read_contract_portfolio', description: 'Read the currently displayed contract portfolio and its evidence. Sample data is identified explicitly.', inputSchema: { type: 'object', properties: {}, additionalProperties: false }, annotations: { readOnlyHint: true, untrustedContentHint: true }, execute: (args: unknown) => {
        if (!args || typeof args !== 'object' || Array.isArray(args) || Object.keys(args).length) throw new Error('Expected an empty object.')
        return { mode: apiBase ? 'api' : 'sample', portfolio }
      } }, { signal: controller.signal })).catch(() => {})
    } catch { controller.abort() }
    return () => controller.abort()
  }, [portfolio])

  function chooseFiles(incoming: File[]) {
    try { validateFiles(incoming); setFiles(incoming); setUploadResults({}); setUploadError('') } catch (cause) { setUploadError((cause as Error).message) }
  }
  async function upload() {
    if (!apiBase) return
    setUploading(true); setUploadError('')
    for (const [index, file] of files.entries()) {
      if (uploadResults[String(index)]?.startsWith('Accepted')) continue
      setUploadResults(previous => ({ ...previous, [index]: 'Uploading…' }))
      try {
        const result = await uploadDocument(file)
        setUploadResults(previous => ({ ...previous, [index]: result.status === 'failed' ? `Failed: ${result.error ?? 'OCR processing failed.'}` : `Accepted · ${result.status}` }))
      } catch (cause) { setUploadResults(previous => ({ ...previous, [index]: `Failed: ${(cause as Error).message}` })) }
    }
    setUploading(false); await refresh()
  }

  const actions = portfolio ? upcomingActions(portfolio.actions, portfolio.as_of) : []
  const reviews = portfolio?.contracts.filter(contract => Object.values(contract.fields).some(field => field.basis === 'unresolved' || field.confidence === 'low')) ?? []
  const overdue = portfolio?.actions.filter(action => daysBetween(portfolio.as_of, action.due_date) < 0) ?? []
  const contracts = portfolio?.contracts.filter(contract => `${contract.name} ${contract.category} ${contract.fields.parties.value ?? ''}`.toLowerCase().includes(search.toLowerCase()) && (filter === 'all' || reviews.some(review => review.id === contract.id))) ?? []
  const nameOf = (id: string) => portfolio?.contracts.find(contract => contract.id === id)?.name ?? id
  const openEvidence = (title: string, reason: string, evidence: Evidence[]) => { if (portfolio) setPanel({ title, content: <><p className="dialog-intro">{reason}</p><Sources evidence={evidence} portfolio={portfolio} /></> }) }
  const navigate = (next: View) => { setView(next); setSelected(null); setSearch(''); setFilter('all') }

  return <div className="app-shell">
    <aside className="sidebar"><a href="#" className="brand" onClick={event => { event.preventDefault(); navigate('Overview') }}><span className="brand-mark"><Scale size={24} /></span>aithena<span className="brand-dot">.</span></a><div className="workspace-label">MERIDIAN WORKSPACE <span>01</span></div><nav aria-label="Main navigation">{navigation.map(({ name, icon: Icon }) => <button key={name} className={view === name ? 'nav-item active' : 'nav-item'} onClick={() => navigate(name)} aria-current={view === name ? 'page' : undefined}><Icon size={19} />{name}{name === 'Conflicts' && Boolean(portfolio?.conflicts.length) && <span className="nav-count">{portfolio?.conflicts.length}</span>}</button>)}</nav><div className="sidebar-bottom"><ShieldCheck size={22} /><strong>Evidence comes first.</strong><p>Know what’s established.<br />See what needs a second look.</p><div className="profile"><span>MP</span><div>Meridian Pte Ltd<small>Contract workspace</small></div></div></div></aside>
    <div className="main-shell"><header className="topbar"><div>Workspace <ChevronRight size={14} /><strong>{view}</strong></div><Badge tone={apiBase ? 'green' : 'blue'}>{apiBase ? 'Connected workspace' : 'Sample workspace'}</Badge></header>
    <main><div className="page-heading"><div><div className="eyebrow">YOUR CONTRACTS, IN FOCUS</div><h1>{selected ? selected.name : view === 'Overview' ? 'Portfolio overview' : view === 'Calendar' ? 'Upcoming actions' : view === 'Conflicts' ? 'Potential conflicts' : 'Contract library'}</h1><p>{selected ? 'Every field keeps its source and uncertainty in view.' : view === 'Overview' ? 'What you’re committed to. What needs your attention.' : view === 'Calendar' ? 'Action dates and contract events in the next 90 days.' : view === 'Conflicts' ? 'Overlapping commitments that need human judgement.' : 'Your agreements, with the details that matter.'}</p></div><div className="heading-actions">{apiBase && <button className="secondary icon-button" onClick={() => void refresh()} disabled={loading || uploading} aria-label="Refresh portfolio"><RefreshCw size={18} className={loading ? 'spin' : ''} /></button>}<button className="primary" onClick={() => { setUploadOpen(true); setUploadError('') }}><Plus size={18} />Add contracts</button></div></div>
      {!apiBase && <div className="demo-notice"><span><span className="live-dot" /> Demo data · 4 synthetic agreements</span><span>Reference date: {formatDate(demoPortfolio.as_of)} · Uploads are staged locally</span></div>}
      {error && <div className="error" role="alert">{error} <button onClick={() => void refresh()}>Try again</button></div>}
      {loading && <p role="status">Loading portfolio…</p>}
      {!portfolio && !loading && <Empty>Your workspace could not be loaded. Check the backend connection and retry.</Empty>}
      {portfolio && selected ? <><button className="text-button back" onClick={() => setSelected(null)}>← Back to {view.toLowerCase()}</button><div className="detail-grid">{fieldNames.map(key => <article className="card field-card" key={key}><h3>{labels[key]}</h3><FieldValue field={selected.fields[key]} onClick={() => openEvidence(labels[key], selected.fields[key].reason, selected.fields[key].evidence)} /></article>)}</div></> : portfolio && <>
      {view === 'Overview' && <><div className="stats"><article><span>Contracts in portfolio</span><strong>{portfolio.contracts.length.toString().padStart(2, '0')}</strong><small><FileText size={14} />Across your business</small></article><article><span>Actions in 90 days</span><strong>{actions.length.toString().padStart(2, '0')}<span className="stat-dot blue-dot" /></strong><small>Next: {actions[0] ? formatDate(actions[0].due_date) : 'Nothing scheduled'}</small></article><article><span>Need a closer look</span><strong>{reviews.length.toString().padStart(2, '0')}<span className="stat-dot amber-dot" /></strong><small>Incomplete or uncertain fields</small></article><article><span>Potential conflicts</span><strong>{portfolio.conflicts.length.toString().padStart(2, '0')}</strong><small>For legal review</small></article></div><div className="overview-grid"><section className="card"><div className="section-heading"><h2>On the horizon <span className="subtle">/ 90 days</span></h2><button className="text-button" onClick={() => navigate('Calendar')}>View all <ArrowRight size={16} /></button></div>{actions.length ? actions.slice(0, 3).map(action => <button className="action-row" key={action.id} onClick={() => openEvidence(action.title, action.reason, action.evidence)}><span className="date-tile"><small>{new Date(action.due_date + 'T00:00:00Z').toLocaleString('en', { month: 'short', timeZone: 'UTC' })}</small><strong>{Number(action.due_date.slice(-2))}</strong></span><span className="row-copy"><strong>{action.title}</strong><small>{nameOf(action.contract_id)}</small></span><span className="due-label">In {daysBetween(portfolio.as_of, action.due_date)} days</span><ChevronRight size={17} /></button>) : <Empty>No actions fall in this 90-day window.</Empty>}</section><section className="attention-card"><div className="section-heading"><h2><CircleAlert size={19} />Worth a closer look</h2></div>{portfolio.conflicts[0] ? <><Badge tone="amber">Potential conflict</Badge><h3>{portfolio.conflicts[0].title}</h3><p>{portfolio.conflicts[0].summary}</p><button className="text-button" onClick={() => navigate('Conflicts')}>Review both agreements <ArrowRight size={16} /></button></> : <p>No potential conflicts have been reported. This is not confirmation that all agreements are compatible.</p>}</section></div></>}
      {overdue.length > 0 && (view === 'Calendar' || view === 'Overview') && <div className="error">{overdue.length} overdue action(s): {overdue.map(action => <button key={action.id} onClick={() => openEvidence(action.title, action.reason, action.evidence)}>{action.title} · {formatDate(action.due_date)}</button>)}</div>}
      {(view === 'Contracts' || view === 'Overview') && <section className="card library"><div className="section-heading"><h2>{view === 'Overview' ? 'Your contracts' : 'All contracts'} <span className="count">{portfolio.contracts.length}</span></h2><div className="table-controls"><label className="search"><Search size={17} /><input placeholder="Search contracts…" aria-label="Search contracts" value={search} onChange={event => setSearch(event.target.value)} /></label><select aria-label="Filter contracts" value={filter} onChange={event => setFilter(event.target.value)}><option value="all">All statuses</option><option value="review">Needs review</option></select></div></div><div className="table-scroll"><table><thead><tr><th>Agreement</th><th>Category</th><th>Evidence status</th><th>Next action</th><th><span className="sr-only">Open</span></th></tr></thead><tbody>{contracts.map(contract => { const review = reviews.some(item => item.id === contract.id); const action = actions.find(item => item.contract_id === contract.id); return <tr key={contract.id}><td><button className="contract-link" onClick={() => setSelected(contract)}><span className="file-icon"><FileText size={19} /></span><span>{contract.name}<small>{portfolio.documents.find(doc => doc.id === contract.document_id)?.filename}</small></span></button></td><td>{contract.category}</td><td><Badge tone={review ? 'amber' : 'green'}>{review ? <CircleAlert size={12} /> : <Check size={12} />}{review ? 'Needs review' : 'Sources linked'}</Badge></td><td>{action ? formatDate(action.due_date) : 'None in 90 days'}</td><td><button className="icon-button" onClick={() => setSelected(contract)} aria-label={`Open ${contract.name}`}><ChevronRight size={17} /></button></td></tr> })}</tbody></table></div>{!contracts.length && <Empty>{portfolio.contracts.length ? 'No contracts match your search.' : 'No extracted contracts yet. Add documents to begin.'}</Empty>}</section>}
      {view === 'Contracts' && portfolio.documents.some(doc => doc.status !== 'ready' || !portfolio.contracts.some(contract => contract.document_id === doc.id)) && <section className="card processing"><h2>Document processing</h2>{portfolio.documents.filter(doc => doc.status !== 'ready' || !portfolio.contracts.some(contract => contract.document_id === doc.id)).map(doc => <div className="processing-row" key={doc.id}><span>{doc.filename}</span><Badge tone={doc.status === 'failed' ? 'amber' : 'blue'}>{doc.status === 'ready' ? 'Text ready · awaiting extraction' : doc.status}</Badge>{doc.error && <p>{doc.error}</p>}</div>)}<p className="subtle">Refresh to check for completed extraction.</p></section>}
      {view === 'Calendar' && <section className="card"><div className="section-heading"><h2>90-day action calendar</h2><span className="subtle">From {formatDate(portfolio.as_of)}</span></div>{actions.map(action => <div className="calendar-row" key={action.id}><div><strong>{formatDate(action.due_date)}</strong><small>Action date</small></div><div className="row-copy"><h3>{action.title}</h3><p>{nameOf(action.contract_id)}</p><small>Contract event: {action.event_date ? formatDate(action.event_date) : 'Not established'}</small></div><Badge tone={action.basis === 'found' ? 'green' : action.basis === 'unresolved' ? 'amber' : 'blue'}>{action.basis}</Badge><button className="text-button" onClick={() => openEvidence(action.title, action.reason, action.evidence)}>View basis <ArrowRight size={16} /></button></div>)}{!actions.length && <Empty>No upcoming actions have been established.</Empty>}</section>}
      {view === 'Conflicts' && <div className="conflict-list">{portfolio.conflicts.map(conflict => <section className="card conflict-card" key={conflict.id}><div className="section-heading"><Badge tone="amber">Potential conflict · {conflict.confidence} confidence</Badge><Scale size={22} /></div><h2>{conflict.title}</h2><p>{conflict.summary}</p><div className="contract-chips">{conflict.contract_ids.map(id => <button key={id} onClick={() => setSelected(portfolio.contracts.find(contract => contract.id === id)!)}><FileText size={15} />{nameOf(id)}<ChevronRight size={14} /></button>)}</div><Sources evidence={conflict.evidence} portfolio={portfolio} /><div className="review-question"><strong>Question for legal review</strong><p>{conflict.question}</p></div><button className="secondary" onClick={() => downloadBrief({ schema_version: '1.0', sample_data: !apiBase, as_of: portfolio.as_of, issue: conflict.title, established: conflict.summary, question: conflict.question, confidence: conflict.confidence, documents: portfolio.documents.filter(doc => conflict.evidence.some(source => source.document_id === doc.id)).map(doc => ({ id: doc.id, filename: doc.filename })), evidence: conflict.evidence })}><ArrowDownToLine size={17} />Download review brief</button></section>)}{!portfolio.conflicts.length && <Empty>No potential conflicts reported. Detection coverage depends on the connected analysis service.</Empty>}</div>}
      </>}
      <footer><ShieldCheck size={15} /><span>Found = explicit wording. Inferred = derived interpretation. Needs review = unresolved.</span><span>Human judgement stays in the loop.</span></footer>
    </main></div>
    {panel && <Modal title={panel.title} onClose={() => setPanel(null)}>{panel.content}</Modal>}
    {uploadOpen && <Modal title="Add contracts" onClose={() => { if (!uploading) setUploadOpen(false) }}><p className="dialog-intro">Add signed agreements, including scans. PDF, DOCX, PNG or JPG · up to 20 MB each.</p><div className={`dropzone ${dragging ? 'dragging' : ''}`} onDragOver={event => { event.preventDefault(); if (!uploading) setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={event => { event.preventDefault(); setDragging(false); if (!uploading) chooseFiles(Array.from(event.dataTransfer.files)) }}><UploadCloud size={36} /><h3>Drop your contracts here</h3><p>or choose up to 80 files from your computer</p><button className="secondary" disabled={uploading} onClick={() => input.current?.click()}>Browse files</button><input ref={input} className="sr-only" type="file" multiple accept=".pdf,.docx,.png,.jpg,.jpeg" aria-label="Select contract files" disabled={uploading} onChange={event => { chooseFiles(Array.from(event.target.files ?? [])); event.target.value = '' }} /></div>{uploadError && <p className="error" role="alert">{uploadError}</p>}<div className="file-queue" aria-live="polite">{files.map((file, index) => <div key={`${file.name}-${index}`}><FileText size={17} /><span>{file.name}<small>{uploadResults[String(index)] ?? `${Math.ceil(file.size / 1024)} KB · selected`}</small></span><button className="icon-button" aria-label={`Remove ${file.name}`} disabled={uploading || Boolean(Object.keys(uploadResults).length)} onClick={() => setFiles(previous => previous.filter((_, position) => position !== index))}><X size={16} /></button></div>)}</div>{!apiBase ? <div className="sample-warning"><strong>Sample workspace</strong><p>Files stay in this browser session. OCR and extraction aren’t connected yet, so selecting a document will not create analysis.</p></div> : <p className="dialog-intro">Accepted documents are queued for OCR and extraction. Refresh the contract library to check their progress.</p>}<div className="dialog-actions"><button className="secondary" disabled={uploading} onClick={() => setUploadOpen(false)}>{apiBase ? 'Close' : 'Done'}</button>{apiBase && <button className="primary" disabled={!files.length || uploading} onClick={() => void upload()}>{uploading ? 'Uploading…' : 'Upload documents'}</button>}</div></Modal>}
  </div>
}
