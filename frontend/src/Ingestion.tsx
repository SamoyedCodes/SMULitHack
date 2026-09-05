import { useEffect, useRef, useState } from 'react'
import { ArrowDownToLine, FileText, FolderOpen, RefreshCw, UploadCloud, X } from 'lucide-react'
import { fetchLatestBatch, fetchPages, retryReading, uploadBatch, type ApiDocument, type Batch, type Health, type SourcePage } from './api'

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
  return <section className="card ingestion-upload" aria-label="Upload contracts"><div className="section-heading"><h2>Add contracts</h2><button className="icon-button" disabled={busy} onClick={onClose} aria-label="Close upload"><X /></button></div><p>PDF, DOCX, PNG or JPEG · up to {health.limits.files_per_batch} files · {health.limits.megabytes_per_file} MiB each · {health.limits.pages_per_file} pages each.</p><div className="dropzone" onDragOver={event => event.preventDefault()} onDrop={event => { event.preventDefault(); choose(Array.from(event.dataTransfer.files)) }}><UploadCloud size={32} /><h3>Drop files here or choose a folder</h3><p>Local reading only. No contract text is sent to a model in Phase 2.</p><div className="upload-choices"><button className="secondary" disabled={busy} onClick={() => fileInput.current?.click()}>Choose files</button><button className="secondary" disabled={busy} onClick={() => folderInput.current?.click()}>Choose folder</button></div><input ref={fileInput} type="file" multiple accept=".pdf,.docx,.png,.jpg,.jpeg" className="sr-only" aria-label="Contract files" disabled={busy} onChange={event => { choose(Array.from(event.target.files ?? [])); event.target.value = '' }} /><input ref={node => { folderInput.current = node; node?.setAttribute('webkitdirectory', '') }} type="file" multiple className="sr-only" aria-label="Contract folder" disabled={busy} onChange={event => { choose(Array.from(event.target.files ?? [])); event.target.value = '' }} /></div>{error && <p className="error" role="alert">{error}</p>}<ul className="selected-files">{files.map((file, index) => <li key={index}><FileText size={16} /><span>{file.webkitRelativePath || file.name}<small>{warnings[index] ?? `${Math.ceil(file.size / 1024)} KiB`}</small></span></li>)}</ul><div className="dialog-actions"><button className="primary" disabled={!enabled || busy || !files.length || Boolean(batch)} onClick={() => void submit()}>{busy ? 'Uploading batch…' : 'Upload for local reading'}</button></div>{batch && <BatchReceipt batch={batch} />}</section>
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

export function DocumentLibrary({ documents, enabled, stale, onOpen, onRefresh }: { documents: ApiDocument[]; enabled: boolean; stale: boolean; onOpen: (id: string) => void; onRefresh: () => void }) {
  const [error, setError] = useState('')
  const [retrying, setRetrying] = useState<string | null>(null)
  async function retry(id: string) {
    setRetrying(id); setError('')
    try { await retryReading(id); onRefresh() } catch (cause) { setError((cause as Error).message) } finally { setRetrying(null) }
  }
  return <section className="card ingestion-library"><div className="section-heading"><h2>Document library{stale ? ' · stale' : ''}</h2><span>{documents.length} documents</span></div><p className="library-note">Text readiness is not obligation extraction. All documents remain legally unassessed in Phase 2.</p>{error && <p className="error" role="alert">{error}</p>}{!documents.length && <div className="empty"><FolderOpen /><p>No documents uploaded. Add contracts to start local reading.</p></div>}<ul className="document-rows">{documents.map(doc => <li key={doc.id}><FileText size={24} /><div className="row-copy"><button className="contract-link" disabled={!enabled} onClick={() => onOpen(doc.id)}>{doc.filename}</button><p>{doc.stage}</p><small>{doc.pages_read}/{doc.page_count || '?'} pages read · {doc.has_ocr ? 'Contains OCR' : 'OCR not recorded'} · {doc.pages_analyzed} pages analyzed</small>{doc.error && <p className="error">{doc.error}</p>}{doc.warnings.length > 0 && <p>{doc.warnings.length} source warning(s)</p>}</div><span className={`badge ${doc.status === 'text_ready' ? 'blue' : 'amber'}`}>{doc.status.replaceAll('_', ' ')}</span><div className="document-actions"><button className="secondary" disabled={!enabled} onClick={() => onOpen(doc.id)}>View source</button>{['failed', 'needs_source_review'].includes(doc.status) && <button className="secondary" disabled={!enabled || retrying !== null} onClick={() => void retry(doc.id)}><RefreshCw size={16} />{retrying === doc.id ? 'Queuing…' : 'Retry reading'}</button>}</div></li>)}</ul></section>
}

export function SourceViewer({ document: doc, enabled, onClose }: { document: ApiDocument; enabled: boolean; onClose: () => void }) {
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
  const span = page?.spans.find(item => item.id === selected)
  const total = Math.max(doc.page_count, pages.length, 1)
  const imageUrl = `/api/documents/${encodeURIComponent(doc.id)}/pages/${number}/image?revision=${imageRevision}`
  function changePage(value: number) { setNumber(value); setSelected(null); setImageError(false) }
  return <section className="source-viewer"><div className="source-toolbar"><button className="secondary" onClick={onClose}>← Document library</button><h2>{doc.filename}</h2><a className="secondary" href={`/api/documents/${encodeURIComponent(doc.id)}/original`} download><ArrowDownToLine size={16} />Download original</a></div><p className="phase-notice">{doc.pagination === 'rendered' ? 'Rendered pagination (DOCX converted to PDF)' : 'Physical source pages'} · Original retained · No obligations extracted.</p>{!enabled && <p role="alert" className="error">Connection unavailable. Displayed source data may be stale.</p>}{error && <p role="alert" className="error">{error}</p>}<div className="page-controls"><button className="secondary" disabled={number <= 1} onClick={() => changePage(number - 1)}>Previous</button><label>Page <select value={number} onChange={event => changePage(Number(event.target.value))}>{Array.from({length: total}, (_, index) => <option key={index + 1} value={index + 1}>{index + 1}</option>)}</select> of {doc.page_count || '?'}</label><button className="secondary" disabled={number >= total} onClick={() => changePage(number + 1)}>Next</button></div>{loading && <p role="status">Refreshing source text…</p>}<div className="source-layout"><section ref={sourceCard} className="card source-image-card"><h3>Source page {number}</h3>{doc.page_count > 0 ? <>{imageError && <p className="error">Source image unavailable. Reading may still be in progress; retry when the page is ready. <button className="secondary" onClick={() => setImageRevision(value => value + 1)}>Retry image</button></p>}<div className="page-image"><img key={imageUrl} src={imageUrl} alt={`${doc.filename}, physical page ${number}`} onLoad={() => setImageError(false)} onError={() => setImageError(true)} />{page && !imageError && <svg viewBox={`0 0 ${page.width} ${page.height}`} aria-hidden="true">{span && <rect x={span.bbox[0]} y={span.bbox[1]} width={Math.max(0,span.bbox[2]-span.bbox[0])} height={Math.max(0,span.bbox[3]-span.bbox[1])} />}</svg>}</div></> : <p>The source PDF is not ready yet. {doc.error ?? doc.stage}</p>}</section><section className="card transcription"><h3>Page text and source locations</h3><p>Choose a text block to highlight its location. OCR confidence measures reading quality, not legal accuracy.</p>{page?.warnings.map((warning,index) => <p className="error" key={index}>{warning}</p>)}{!page?.spans.length && <p>{page ? `Page status: ${page.status}. No readable text was established.` : 'This page has not been read yet.'}</p>}{page?.spans.map(item => <button className={`transcript-block ${selected === item.id ? 'selected' : ''}`} aria-pressed={selected === item.id} key={item.id} onClick={() => { setSelected(item.id); sourceCard.current?.scrollIntoView({block:'nearest', behavior:'smooth'}) }}><span className="badge">{item.source === 'ocr' ? `OCR · ${item.ocr_confidence ?? 'unknown'} reading confidence` : 'Native text'}{item.clause ? ` · Detected clause label ${item.clause}` : ''}</span><span className="transcript-text">{item.text}</span></button>)}</section></div></section>
}
