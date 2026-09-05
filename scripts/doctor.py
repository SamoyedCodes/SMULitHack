import importlib.util
import shutil
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.config import Config, libreoffice_path, tesseract_path

if __name__ == "__main__":
    try:
        config = Config()
    except ValueError as exc:
        raise SystemExit(str(exc))
    print(f"Python: {sys.version.split()[0]}")
    print(f"API: http://127.0.0.1:{config.api_port} | UI: http://127.0.0.1:{config.web_port}")
    for name in ("node", "pnpm"):
        print(f"{name}: {'detected' if shutil.which(name) else 'missing; install before launching'}")
    for name, found in (("Tesseract", tesseract_path()), ("LibreOffice", libreoffice_path())):
        print(f"{name}: {'executable detected (not tested)' if found else 'not detected (required for its document format)'}")
    print(f"OpenRouter primary ({config.openrouter_model}): {'key configured, access unverified' if config.openrouter_api_key else 'key not configured'}")
    print(f"Gemini secondary ({config.model}): {'key configured, access unverified' if config.api_key else 'key not configured'}")
    print("Ingestion worker starts with the API. This diagnostic performs no conversion, OCR or provider requests.")
