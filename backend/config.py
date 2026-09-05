"""Configuration is read-only; only application lifespan may initialize storage."""
import math
import os
import shutil
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
VERSION = "2026-09-05.3-or1"


def setting(name: str, default: str = "") -> str:
    return os.getenv(name) or dotenv_values(ROOT / ".env").get(name) or default


def binary(name: str, override: str, extras: list[str]) -> str | None:
    def executable(value):
        path = shutil.which(value)
        return path if path and Path(path).is_file() and os.access(path, os.X_OK) else None
    value = setting(override)
    if value:
        return executable(value)
    return executable(name) or next((p for p in extras if executable(p)), None)


def tesseract_path() -> str | None:
    return binary("tesseract", "TESSERACT_CMD", ["/opt/homebrew/bin/tesseract", "/usr/local/bin/tesseract"])


def libreoffice_path() -> str | None:
    return binary("soffice", "LIBREOFFICE_CMD", [
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
        "/opt/homebrew/bin/soffice", "/usr/bin/libreoffice",
    ])


class Config:
    def __init__(self, data_dir: Path | str | None = None):
        path = Path(data_dir if data_dir is not None else setting("AITHENA_DATA_DIR", "data")).expanduser()
        self.data_dir = (path if path.is_absolute() else ROOT / path).resolve()
        self.api_port = self._port("AITHENA_API_PORT", "8000")
        self.web_port = self._port("AITHENA_WEB_PORT", "3000")
        if self.api_port == self.web_port:
            raise ValueError("AITHENA_API_PORT and AITHENA_WEB_PORT must be distinct.")
        try:
            self._interval = float(setting("AITHENA_LLM_INTERVAL", "12"))
        except ValueError:
            raise ValueError("AITHENA_LLM_INTERVAL must be a finite non-negative number.") from None
        if not math.isfinite(self._interval) or self._interval < 0:
            raise ValueError("AITHENA_LLM_INTERVAL must be a finite non-negative number.")

    @staticmethod
    def _port(name: str, default: str) -> int:
        value = setting(name, default)
        if not value.isascii() or not value.isdecimal() or not 1 <= int(value) <= 65535:
            raise ValueError(f"{name} must be an integer between 1 and 65535.")
        return int(value)

    @property
    def api_key(self) -> str:
        return setting("GEMINI_API_KEY") or setting("GOOGLE_API_KEY")

    @property
    def model(self) -> str:
        return setting("GEMINI_MODEL", "gemini-3.8-flash")

    @property
    def openrouter_api_key(self) -> str:
        return setting("OPENROUTER_API_KEY")

    @property
    def openrouter_model(self) -> str:
        return setting("OPENROUTER_MODEL", "openrouter/free")

    @property
    def routing_identity(self) -> str:
        # No credentials in job/cache identifiers; include both requested model identities.
        return f"openrouter:{self.openrouter_model}|gemini:{self.model}"

    @property
    def llm_interval(self) -> float:
        return self._interval

    def directory(self, document_id: str, create: bool = True) -> Path:
        if not document_id.replace("-", "").isalnum():
            raise ValueError("Invalid document identifier")
        root = (self.data_dir / "documents").resolve()
        if not root.is_relative_to(self.data_dir):
            raise ValueError("Invalid document storage path")
        path = (root / document_id).resolve()
        if not path.is_relative_to(root):
            raise ValueError("Invalid document storage path")
        if create:
            path.mkdir(parents=True, exist_ok=True)
        return path
