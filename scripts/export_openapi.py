"""Export without application startup, storage access or optional processing imports."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.api import create_app

body = json.dumps(create_app().openapi(), indent=2, sort_keys=True) + "\n"
target = ROOT / "shared/openapi.json"
if "--check" in sys.argv:
    if not target.exists() or target.read_text() != body:
        raise SystemExit("OpenAPI changed. Run scripts/export_openapi.py, then pnpm --dir frontend api:generate.")
else:
    target.write_text(body)
