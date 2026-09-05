import { useEffect, useRef, useState } from 'react'
import { ArrowDownToLine, FileText, FolderOpen, RefreshCw, UploadCloud, X } from 'lucide-react'
import { filterDocuments, documentSummary, EMPTY_LIBRARY, type LibraryFilters, type QueueItem } from './presentation'
import type { CalendarEvent } from './api'
import { fetchLatestBatch, fetchPages, retryReading, uploadBatch, type Evidence, type ApiDocument, type Batch, type Health, type SourcePage } from './api'

export function validateBatchFiles(files: File[], limits: Health['limits']) {
  if (!files.length || files.length > limits.files_per_batch) throw new Error(`Choose 1–${limits.files_per_batch} files.`)
  // Keep unsupported/empty/large files visible: the server rejects them individually,
  // while accepting supported siblings. Show the same warning before transmission.
  return files.map(file => !/\.(pdf|docx|png|jpe?g)$/i.test(file.name) ? 'Unsupported format; this file will be rejected.' : !file.size ? 'Empty file; this file will be rejected.' : file.size > limits.megabytes_per_file * 1024 * 1024 ? `Exceeds ${limits.megabytes_per_file} MiB; this file will be rejected.` : null)
}

export function UploadPanel({ health, enabled, onClose, onUploaded }: { health: Health; enabled: boolean; onClose: () => void; onUploaded: () => void }) {
  const [files, setFiles] = useState<File[]>([])
  const [warnings, setWarnings] = useState<(string | null)[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [batch, setBatch] = useState<Batch | null>(null)
  const key = useRef('')
  const fileInput = useRef<HTMLInputElement>(null)
  const folderInput = useRef<HTMLInputElement>(null)
  function choose(incoming: File[]) {
    if (busy) return
    try { setWarnings(validateBatchFiles(incoming, health.limits)); setFiles(incoming); key.current = crypto.randomUUID(); setBatch(null); setError('') }
    catch (cause) { setFiles([]); setWarnings([]); setBatch(null); setError((cause as Error).message) }
  }
  async function submit() {
    if (!enabled || busy || !files.length) return
    setBusy(true); setError('')
    try { const receipt = await uploadBatch(files, key.current); setBatch(receipt); onUploaded() }
    catch (cause) { setError(`${(cause as Error).message} Retry this selection to recover the same batch acknowledgement.`) }
    finally { setBusy(false) }
  }
  return <section className="card ingestion-upload" aria-label="Upload contracts"><div className="section-heading"><h2>Add contracts</h2><button className="icon-button" disabled={busy} onClick={onClose} aria-label="Close upload"><X /></button></div><p>PDF, DOCX, PNG or JPEG · up to {health.limits.files_per_batch} files · {health.limits.megabytes_per_file} MiB each · {health.limits.pages_per_file} pages each.</p><div className="dropzone" onDragOver={event => event.preventDefault()} onDrop={event => { event.preventDefault(); choose(Array.from(event.dataTransfer.files)) }}><UploadCloud size={32} /><h3>Drop files here or choose a folder</h3><p>Local reading only. Extraction is requested separately after reading.</p><div className="upload-choices"><button className="secondary" disabled={busy} onClick={() => fileInput.current?.click()}>Choose files</button><button className="secondary" disabled={busy} onClick={() => folderInput.current?.click()}>Choose folder</button></div><input ref={fileInput} type="file" multiple accept=".pdf,.docx,.png,.jpg,.jpeg" className="sr-only" aria-label="Contract files" disabled={busy} onChange={event => { choose(Array.from(event.target.files ?? [])); event.target.value = '' }} /><input ref={node => { folderInput.current = node; node?.setAttribute('webkitdirectory', '') }} type="file" multiple className="sr-only" aria-label="Contract folder" disabled={busy} onChange={event => { choose(Array.from(event.target.files ?? [])); event.target.value = '' }} /></div>{error && <p className="error" role="alert">{error}</p>}<ul className="selected-files">{files.map((file, index) => <li key={index}><FileText size={16} /><span>{file.webkitRelativePath || file.name}<small>{warnings[index] ?? `${Math.ceil(file.size / 1024)} KiB`}</small></span></li>)}</ul><div className="dialog-actions"><button className="primary" disabled={!enabled || busy || !files.length || Boolean(batch)} onClick={() => void submit()}>{busy ? 'Uploading batch…' : 'Upload for local reading'}</button></div>{batch && <BatchReceipt batch={batch} />}</section>
}

export function BatchReceipt({ batch }: { batch: Batch }) {
  return <div className="batch-receipt" aria-live="polite"><h3>Batch receipt</h3><p>{batch.documents.filter(item => item.id).length} accepted entries · {batch.documents.filter(item => item.cached).length} duplicates · {batch.documents.filter(item => item.error).length} rejected.</p><ul>{batch.documents.map((item, index) => <li key={index}><strong>{item.filename}</strong><span>{item.error ?? (item.cached ? 'Duplicate: existing document retained. ' : 'Accepted. ') + (batch.progress.find(doc => doc.id === item.id)?.stage ?? 'Queued for local reading.')}</span></li>)}</ul></div>
}

export function RecentBatch({ revision }: { revision: string }) {
  const [batch, setBatch] = useState<Batch | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let current = true
    void fetchLatestBatch().then(result => { if (current) { setBatch(result); setError('') } }).catch(() => { if (current) setError('The last batch receipt could not be refreshed; previous receipt is stale.') })
    return () => { current = false }
  }, [revision])
  return batch || error ? <section className="card ingestion-upload">{error && <p role="alert" className="error">{error}</p>}{batch && <BatchReceipt batch={batch} />}</section> : null
}

export function DocumentLibrary({ documents, enabled, stale, onOpen, onRefresh, events = [], queue = [], asOf = '', filters = EMPTY_LIBRARY, onFilters = () => {} }: { documents: ApiDocument[]; enabled: boolean; stale: boolean; onOpen: (id: string) => void; onRefresh: () => void; events?: CalendarEvent[]; queue?: QueueItem[]; asOf?: string; filters?: LibraryFilters; onFilters?: (f: LibraryFilters) => void }) {
  const shown = filterDocuments(documents, filters, events, queue, asOf)
  const summary = new Map(documents.map(d => [d.id, documentSummary(d.id, events, queue, asOf)]))
  const [error, setError] = useState('')
  const [retrying, setRetrying] = useState<string | null>(null)
  async function retry(id: string) {
    setRetrying(id); setError('')
    try { await retryReading(id); onRefresh() } catch (cause) { setError((cause as Error).message) } finally { setRetrying(null) }
  }
  return <section className="card ingestion-library"><div className="section-heading"><h2>Document library{stale ? ' · stale' : ''}</h2><span>{documents.length} documents</span></div><p className="library-note">Text readiness is not obligation extraction. Open a document to extract obligations and inspect their evidence.</p>{error && <p className="error" role="alert">{error}</p>}{!documents.length && <div className="empty"><FolderOpen /><p>No documents uploaded. Add contracts to start local reading.</p></div>}<div className="filter-controls">
    <label>Search contracts<input type="search" placeholder="Name, filename or established party" value={filters.query} onChange={e => onFilters({...filters, query:e.target.value})} /></label>
    <label>Processing status<select value={filters.status} onChange={e => onFilters({...filters, status:e.target.value})}><option value="">All statuses</option>{[...new Set([...documents.map(d => d.status), ...(filters.status ? [filters.status] : [])])].sort().map(status => <option key={status} value={status}>{status.replaceAll('_',' ')}</option>)}</select></label>
    <label className="checkbox-label"><input type="checkbox" checked={filters.needsReview} onChange={e => onFilters({...filters, needsReview:e.target.checked})} />Needs review</label>
    <label>Sort contracts<select value={filters.sort} onChange={e => onFilters({...filters, sort:e.target.value as LibraryFilters['sort']})}><option value="name">Name</option><option value="deadline">Next action deadline</option><option value="review">Review item count</option></select></label>
    <button className="secondary" onClick={() => onFilters({...EMPTY_LIBRARY})}>Clear filters</button>
    <p role="status">Showing {shown.length} of {documents.length} documents. Dates belong to the selected 90-day window from {asOf || 'the portfolio date'}, including relevant overdue actions.</p>
    </div>{documents.length > 0 && !shown.length && <p className="library-note">No contracts match these filters.</p>}<ul className="document-rows">{shown.map(doc => <li id={`library-row-${doc.id}`} tabIndex={-1} key={doc.id}><FileText size={24} /><div className="row-copy"><button id={`document-${doc.id}`} className="contract-link" disabled={!enabled} onClick={() => onOpen(doc.id)}>{doc.title || doc.filename}</button>{doc.title !== doc.filename && <small>{doc.filename}</small>}<p>{doc.stage}</p><p>Next action: {summary.get(doc.id)!.next ?? 'Not established in this window'} · {summary.get(doc.id)!.overdue} overdue · {summary.get(doc.id)!.reviews} review items</p><small>{doc.pages_read}/{doc.page_count || '?'} pages read · {doc.has_ocr ? 'Contains OCR' : 'OCR not recorded'} · {doc.pages_analyzed} pages analyzed</small>{doc.error && <p className="error">{doc.error}</p>}{doc.warnings.length > 0 && <p>{doc.warnings.length} source warning(s)</p>}</div><span className={`badge ${doc.status === 'text_ready' ? 'blue' : 'amber'}`}>{doc.status.replaceAll('_', ' ')}</span><div className="document-actions"><button className="secondary" disabled={!enabled} onClick={() => onOpen(doc.id)}>View source</button>{(doc.status === 'needs_source_review' || (doc.status === 'failed' && !doc.pages_read)) && <button className="secondary" disabled={!enabled || retrying !== null} onClick={() => void retry(doc.id)}><RefreshCw size={16} />{retrying === doc.id ? 'Queuing…' : 'Retry reading'}</button>}</div></li>)}</ul></section>
}

export function SourceViewer({ document: doc, enabled, onClose, evidence, backLabel = '← Document library' }: { document: ApiDocument; enabled: boolean; onClose: () => void; evidence?: Evidence | null; backLabel?: string }) {
  const sourceCard = useRef<HTMLElement>(null)
  const [pages, setPages] = useState<SourcePage[]>([])
  const [number, setNumber] = useState(1)
  const [selected, setSelected] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [imageError, setImageError] = useState(false)
  const [imageRevision, setImageRevision] = useState(0)
  const [loading, setLoading] = useState(true)
  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    void fetchPages(doc.id, controller.signal).then(data => { if (!controller.signal.aborted) { setPages(data); setError('') } }).catch(cause => { if (!controller.signal.aborted) setError(cause.message) }).finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [doc.id, doc.stage, doc.status])
  const page = pages.find(item => item.number === number)
  useEffect(() => {
    if (evidence?.document_id === doc.id) { setNumber(evidence.page); setSelected(null); setImageError(false); sourceCard.current?.scrollIntoView({block:'nearest', behavior:'smooth'}) }
  }, [evidence, doc.id])
  const highlighted = page?.spans.filter(item => selected ? item.id === selected : evidence?.document_id === doc.id && evidence.page === number && evidence.span_ids.includes(item.id)) ?? []
  const total = Math.max(doc.page_count, pages.length, 1)
  const imageUrl = `/api/documents/${encodeURIComponent(doc.id)}/pages/${number}/image?revision=${imageRevision}`
  function changePage(value: number) { setNumber(value); setSelected(null); setImageError(false) }
  return <section className="source-viewer"><div className="source-toolbar"><button className="secondary" onClick={onClose}>{backLabel}</button><h2>{doc.filename}</h2><a className="secondary" href={`/api/documents/${encodeURIComponent(doc.id)}/original`} download><ArrowDownToLine size={16} />Download original</a></div><p className="phase-notice">{doc.pagination === 'rendered' ? 'Rendered pagination (DOCX converted to PDF)' : 'Physical source pages'} · Original retained · Highlights show source locations, not legal verification.</p>{!enabled && <p role="alert" className="error">Connection unavailable. Displayed source data may be stale.</p>}{error && <p role="alert" className="error">{error}</p>}<div className="page-controls"><button className="secondary" disabled={number <= 1} onClick={() => changePage(number - 1)}>Previous</button><label>Page <select value={number} onChange={event => changePage(Number(event.target.value))}>{Array.from({length: total}, (_, index) => <option key={index + 1} value={index + 1}>{index + 1}</option>)}</select> of {doc.page_count || '?'}</label><button className="secondary" disabled={number >= total} onClick={() => changePage(number + 1)}>Next</button></div>{loading && <p role="status">Refreshing source text…</p>}<div className="source-layout"><section ref={sourceCard} className="card source-image-card"><h3>Source page {number}</h3>{doc.page_count > 0 ? <>{imageError && <p className="error">Source image unavailable. Reading may still be in progress; retry when the page is ready. <button className="secondary" onClick={() => setImageRevision(value => value + 1)}>Retry image</button></p>}<div className="page-image"><img key={imageUrl} src={imageUrl} alt={`${doc.filename}, physical page ${number}`} onLoad={() => setImageError(false)} onError={() => setImageError(true)} />{page && !imageError && <svg viewBox={`0 0 ${page.width} ${page.height}`} aria-hidden="true">{highlighted.map(span => <rect key={span.id} x={span.bbox[0]} y={span.bbox[1]} width={Math.max(0,span.bbox[2]-span.bbox[0])} height={Math.max(0,span.bbox[3]-span.bbox[1])} />)}</svg>}</div></> : <p>The source PDF is not ready yet. {doc.error ?? doc.stage}</p>}</section><section className="card transcription"><h3>Page text and source locations</h3><p>Choose a text block to highlight its location. OCR confidence measures reading quality, not legal accuracy.</p>{page?.warnings.map((warning,index) => <p className="error" key={index}>{warning}</p>)}{page?.visual_review_note && <p role="status">{page.visual_review_note}</p>}{!page?.spans.length && <p>{page ? `Page status: ${page.status}. No readable text was established.` : 'This page has not been read yet.'}</p>}{page?.spans.map(item => <button className={`transcript-block ${selected === item.id ? 'selected' : ''}`} aria-pressed={selected === item.id} key={item.id} onClick={() => { setSelected(item.id); sourceCard.current?.scrollIntoView({block:'nearest', behavior:'smooth'}) }}><span className="badge">{item.source === 'ocr' ? `OCR · ${item.ocr_confidence ?? 'unknown'} reading confidence` : 'Native text'}{item.clause ? ` · Detected clause label ${item.clause}` : ''}</span><span className="transcript-text">{item.text}</span>{page.visual_reviews?.filter(review => review.span_id === item.id).map(review => <span className="visual-review" key={review.span_id}><strong>{review.kind === 'decoration' && !review.contains_meaningful_content ? 'Likely decorative artwork' : `Source review: ${review.kind}`} · AI inference</strong><span>{review.reason}</span><small>{review.model} · Original OCR retained; reading confidence unchanged.</small></span>)}</button>)}</section></div></section>
}
