"""Local ingestion and explicitly queued, grounded extraction API."""
import sqlite3
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Request, Response, File, UploadFile, Header, Query
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import VERSION, Config, libreoffice_path, tesseract_path
from .foundation import CAPABILITIES, DatabaseStatus, ErrorResponse, HealthResponse, WorkerStatus, ProviderStatus
from .models import Document, Page, Portfolio, BatchResponse, Job, RetryResponse, SmeSelection
from .store import Store


def error(status: int, code: str, message: str):
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message, "details": []}})


def create_app(config: Config | None = None, start_worker: bool = True):
    @asynccontextmanager
    async def lifespan(app):
        resolved = config or Config()
        app.state.config = resolved
        resolved.data_dir.mkdir(parents=True, exist_ok=True)
        app.state.store = Store(resolved.data_dir)
        if start_worker and CAPABILITIES.ingestion:
            from .worker import Worker
            app.state.worker = Worker(resolved, app.state.store)
            app.state.worker.start()
        try:
            yield
        finally:
            if app.state.worker:
                app.state.worker.stop()

    app = FastAPI(title="AITHENA evidence API", version=VERSION, lifespan=lifespan,
                  responses={status: {"model": ErrorResponse} for status in (403, 404, 409, 413, 422, 500, 501)})
    app.state.worker = None
    app.add_middleware(CORSMiddleware, allow_origin_regex=r"http://(?:127\.0\.0\.1|localhost):\d+",
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type", "Idempotency-Key"])

    @app.middleware("http")
    async def local_origin(request: Request, call_next):
        import re
        origin = request.headers.get("origin")
        if request.method not in {"GET", "HEAD", "OPTIONS"} and origin:
            cfg = request.app.state.config
            allowed = {f"http://{host}:{port}" for host in ("127.0.0.1", "localhost") for port in (cfg.web_port, cfg.api_port)}
            if origin not in allowed:
                return error(403, "forbidden", "Only the configured local interface can modify this workspace.")
        # Gate before parsing bodies: disabled uploads must not spool files or validate input.
        path = request.url.path
        capability = None
        if request.method == "POST":
            capability = {"/api/batches": "ingestion", "/api/retry": "ingestion",
                          "/api/extract": "extraction", "/api/settings/sme": "extraction", "/api/demo": "sample_workspace"}.get(path.rstrip("/"))
        if request.method == "GET":
            if re.fullmatch(r"/api/documents/[^/]+/(?:pages(?:/[^/]+/image)?|original)/?", path):
                capability = "ingestion"
            elif re.fullmatch(r"/api/review/[^/]+/brief/?", path):
                capability = "handoff"
        if capability and not getattr(CAPABILITIES, capability):
            return error(501, "feature_not_enabled", f"{capability.replace('_', ' ').capitalize()} is not enabled in this build.")
        return await call_next(request)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request, exc):
        codes = {409: "conflict", 413: "payload_too_large", 404: "not_found", 422: "validation_error", 403: "forbidden", 501: "feature_not_enabled"}
        return error(exc.status_code, codes.get(exc.status_code, "http_error"), str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return error(422, "validation_error", "Request parameters are invalid.")

    @app.exception_handler(Exception)
    async def internal_error(request, exc):
        return error(500, "internal_error", "The local service could not complete this request.")

    @app.get("/api/health", response_model=HealthResponse, responses={503: {"model": HealthResponse}})
    def health(request: Request, response: Response):
        cfg = request.app.state.config
        ready = True
        try:
            with request.app.state.store.connection() as db:
                db.execute("SELECT count(*) FROM documents").fetchone()
        except (sqlite3.Error, OSError):
            ready = False
        if not ready:
            response.status_code = 503
        configured = bool(cfg.openrouter_api_key or cfg.api_key)
        return HealthResponse(status="ready" if ready else "degraded", version=VERSION, model=cfg.openrouter_model,
                              providers=[ProviderStatus(name="openrouter", role="primary", model=cfg.openrouter_model, key_configured=bool(cfg.openrouter_api_key)),
                                         ProviderStatus(name="gemini", role="secondary", model=cfg.model, key_configured=bool(cfg.api_key))],
                              key_configured=configured, model_status="configured_unverified" if configured else "not_configured",
                              ocr_available=bool(tesseract_path()), docx_available=bool(libreoffice_path()),
                              database=DatabaseStatus(status="ready" if ready else "unavailable"),
                              worker=WorkerStatus(enabled=bool(request.app.state.worker), running=bool(request.app.state.worker and request.app.state.worker.running)))

    @app.get("/api/portfolio", response_model=Portfolio)
    def portfolio(request: Request, mode: Literal["live", "sample"] = "live", as_of: date | None = None):
        store = request.app.state.store
        as_of = as_of or datetime.now(ZoneInfo("Asia/Singapore")).date()
        docs = store.documents(mode)
        comparisons = store.comparisons(mode)
        pairs = [j for j in store.jobs(mode) if j["kind"] == "conflict"]
        return Portfolio(mode=mode, as_of=as_of.isoformat(), horizon_end=(as_of + timedelta(days=90)).isoformat(),
                         sme=store.setting("sme:" + mode), parties=sorted({p for doc in docs for p in doc.parties}),
                         documents=docs, events=[], issues=[i for doc in docs for i in doc.issues], conflicts=comparisons,
                         comparisons={"pending": sum(j["state"] != "complete" for j in pairs), "assessed": len(comparisons),
                                      "failed": sum(j["state"] in {"failed", "blocked"} for j in pairs)},
                         coverage={"total": len(docs), "analyzed": sum(d.status in {"complete", "needs_review"} for d in docs),
                                   "pages": sum(d.page_count for d in docs), "pages_read": sum(d.pages_read for d in docs),
                                   "pages_analyzed": sum(d.pages_analyzed for d in docs)})

    @app.get("/api/documents/{document_id}", response_model=Document)
    def document(document_id: str, request: Request):
        doc = request.app.state.store.document(document_id)
        if doc is None:
            raise HTTPException(404, "Document not found.")
        return doc

    @app.get("/api/batches", response_model=list[BatchResponse])
    def recent_batches(request: Request, limit: int = Query(1, ge=1, le=20)):
        import json
        from .ingestion import batch_response
        store = request.app.state.store
        with store.connection() as db:
            rows = db.execute("SELECT body FROM batches ORDER BY json_extract(body, '$.created_at') DESC LIMIT ?", (limit,)).fetchall()
        return [batch_response(store, json.loads(row['body'])) for row in rows]

    @app.get("/api/batches/{batch_id}", response_model=BatchResponse)
    def batch(batch_id: str, request: Request):
        store = request.app.state.store
        batch = store.batch(batch_id)
        if batch is None:
            raise HTTPException(404, "Batch not found.")
        from .ingestion import batch_response
        return batch_response(store, batch)

    @app.get("/api/jobs", response_model=list[Job])
    def jobs(request: Request, mode: Literal["live", "sample"] = "live"):
        return request.app.state.store.jobs(mode)

    @app.post("/api/batches", response_model=BatchResponse, status_code=202)
    async def upload(request: Request, files: list[UploadFile] = File(...), idempotency_key: uuid.UUID | None = Header(None)):
        from .ingestion import ingest
        return await ingest(files, request.app.state.config, request.app.state.store, str(idempotency_key or uuid.uuid4()))

    @app.post("/api/retry", response_model=RetryResponse)
    def retry(request: Request, document_id: str, mode: Literal['live', 'sample'] = 'live'):
        doc = document(document_id, request)
        if doc.mode != mode:
            raise HTTPException(404, 'Document not found in this workspace.')
        return RetryResponse(resumed_jobs=request.app.state.store.retry_ingestion(document_id, mode))

    @app.get("/api/documents/{document_id}/pages", response_model=list[Page])
    def pages(document_id: str, request: Request):
        from .documents import load_pages
        from .ingestion import source_path
        document(document_id, request)
        try:
            path = source_path(request.app.state.config, document_id, 'pages.json')
        except HTTPException:
            return []
        return load_pages(path)

    @app.get("/api/documents/{document_id}/pages/{number}/image", responses={200: {'content': {'image/png': {}}}})
    def page_image(document_id: str, number: int, request: Request):
        from .documents import render_page
        from .ingestion import source_path
        document(document_id, request)
        path = source_path(request.app.state.config, document_id, 'canonical.pdf')
        try:
            content = render_page(path, number)
        except ValueError:
            raise HTTPException(404, 'Page does not exist.') from None
        return Response(content, media_type='image/png', headers={'Cache-Control': 'no-store'})

    @app.get("/api/documents/{document_id}/original")
    def original(document_id: str, request: Request):
        from .ingestion import source_path
        doc = document(document_id, request)
        directory = request.app.state.config.directory(document_id, create=False)
        original = next(directory.glob('original.*'), None)
        if not original:
            raise HTTPException(404, 'Original file unavailable.')
        path = source_path(request.app.state.config, document_id, original.name)
        return FileResponse(path, filename=doc.filename, media_type='application/octet-stream', headers={'X-Content-Type-Options':'nosniff'})

    @app.post("/api/extract", response_model=RetryResponse, status_code=202)
    def extract(document_id: str, request: Request):
        import hashlib
        from .ingestion import source_path
        doc = document(document_id, request)
        source = source_path(request.app.state.config, doc.id, 'pages.json')
        cfg = request.app.state.config
        key = 'extract:' + hashlib.sha256((doc.id + doc.sha256 + cfg.routing_identity + VERSION).encode() + source.read_bytes()).hexdigest()
        try:
            count = request.app.state.store.queue_extraction(doc.id, key)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from None
        return RetryResponse(resumed_jobs=count)

    @app.post("/api/settings/sme", response_model=SmeSelection)
    def set_sme(selection: SmeSelection, request: Request):
        store = request.app.state.store
        parties = {p for doc in store.documents(selection.mode) for p in doc.parties}
        if selection.name is not None and selection.name not in parties:
            raise HTTPException(422, 'Choose a party established in this workspace.')
        store.set_setting('sme:' + selection.mode, selection.name)
        return selection

    def disabled():
        raise HTTPException(501, "This feature is not implemented in Phase 3.")

    for path in ("/api/demo",):
        app.add_api_route(path, disabled, methods=["POST"], status_code=501)
    app.add_api_route("/api/review/{issue_id}/brief", disabled, methods=["GET"])
    return app


app = create_app()
