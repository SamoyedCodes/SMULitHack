from typing import Literal
from pydantic import Field
from .models import Record


class Capabilities(Record):
    ingestion: bool = False
    extraction: bool = False
    deadlines: bool = False
    conflicts: bool = False
    handoff: bool = False
    sample_workspace: bool = False


# Enable a capability only when its route implementation and phase acceptance tests land.
CAPABILITIES = Capabilities(ingestion=True, extraction=True)


class DatabaseStatus(Record):
    status: Literal["ready", "unavailable"]


class WorkerStatus(Record):
    enabled: bool = False
    running: bool = False


class Limits(Record):
    files_per_batch: int = 80
    megabytes_per_file: int = 25
    pages_per_file: int = 200


class HealthResponse(Record):
    api_version: Literal["1"] = "1"
    status: Literal["ready", "degraded"]
    version: str
    model: str
    key_configured: bool
    model_status: Literal["not_configured", "configured_unverified"]
    ocr_available: bool
    docx_available: bool
    database: DatabaseStatus
    worker: WorkerStatus = Field(default_factory=WorkerStatus)
    capabilities: Capabilities = Field(default_factory=lambda: CAPABILITIES.model_copy())
    limits: Limits = Field(default_factory=Limits)
    inference_notice: str = "When analysis is enabled, extracted contract text is sent to Gemini. Original files and saved results stay local."


class ErrorDetail(Record):
    code: str
    message: str
    details: list[str] = Field(default_factory=list)


class ErrorResponse(Record):
    error: ErrorDetail
