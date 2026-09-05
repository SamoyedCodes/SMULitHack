"""Phase 1 API. Draft processing modules are deliberately not imported here."""
import sqlite3
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import VERSION, Config, libreoffice_path, tesseract_path
from .foundation import CAPABILITIES, DatabaseStatus, ErrorResponse, HealthResponse
from .models import Document, Page, Portfolio, SmeSelection
from .store import Store


def error(status: int, code: str, message: str):
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message, "details": []}})


def create_app(config: Config | None = None, start_worker: bool = False):
    # Kept for caller compatibility. Phase 1 never constructs or starts a worker.
    @asynccontextmanager
    async def lifespan(app):
        resolved = config or Config()
        app.state.config = resolved
        resolved.data_dir.mkdir(parents=True, exist_ok=True)
        app.state.store = Store(resolved.data_dir)
        yield

    app = FastAPI(title="AITHENA evidence API", version=VERSION, lifespan=lifespan,
                  responses={status: {"model": ErrorResponse} for status in (403, 404, 422, 500, 501)})
    app.state.worker = None
    app.add_middleware(CORSMiddleware, allow_origin_regex=r"http://(?:127\.0\.0\.1|localhost):\d+",
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type"])

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
                          "/api/settings/sme": "extraction", "/api/demo": "sample_workspace"}.get(path.rstrip("/"))
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
        codes = {404: "not_found", 422: "validation_error", 403: "forbidden", 501: "feature_not_enabled"}
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
        configured = bool(cfg.api_key)
        return HealthResponse(status="ready" if ready else "degraded", version=VERSION, model=cfg.model,
                              key_configured=configured, model_status="configured_unverified" if configured else "not_configured",
                              ocr_available=bool(tesseract_path()), docx_available=bool(libreoffice_path()),
                              database=DatabaseStatus(status="ready" if ready else "unavailable"))

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

    @app.get("/api/batches/{batch_id}")
    def batch(batch_id: str, request: Request):
        store = request.app.state.store
        batch = store.batch(batch_id)
        if batch is None:
            raise HTTPException(404, "Batch not found.")
        return {**batch, "progress": [store.document(doc["id"]) for doc in batch["documents"]]}

    @app.get("/api/jobs")
    def jobs(request: Request, mode: Literal["live", "sample"] = "live"):
        return request.app.state.store.jobs(mode)

    @app.post("/api/settings/sme", response_model=SmeSelection)
    def set_sme(selection: SmeSelection, request: Request):
        # Established-party selection (Phase 3). The middleware already gates this on the
        # extraction capability; persistence reuses the existing settings store.
        request.app.state.store.set_setting("sme:" + selection.mode, selection.name)
        return selection

    def disabled():
        raise HTTPException(501, "This feature is not implemented in Phase 1.")

    for path in ("/api/batches", "/api/retry", "/api/demo"):
        app.add_api_route(path, disabled, methods=["POST"], status_code=501)
    app.add_api_route("/api/documents/{document_id}/pages", disabled, methods=["GET"], response_model=list[Page])
    for path in ("/api/documents/{document_id}/pages/{number}/image", "/api/documents/{document_id}/original", "/api/review/{issue_id}/brief"):
        app.add_api_route(path, disabled, methods=["GET"])
    return app


app = create_app()
