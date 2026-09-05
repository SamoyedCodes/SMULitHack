"""Non-legal API fixtures generated from the public Pydantic response types."""
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.foundation import HealthResponse, DatabaseStatus
from backend.models import Portfolio
from backend.config import VERSION

fixtures = {
    'health': HealthResponse(status='ready', version=VERSION, model='gemini-3.8-flash', key_configured=False,
                             model_status='not_configured', ocr_available=False, docx_available=False,
                             database=DatabaseStatus(status='ready')),
    'portfolio': Portfolio(mode='live', as_of='2026-09-05', horizon_end='2026-12-04', sme=None, parties=[], documents=[], events=[], issues=[], conflicts=[],
                           coverage={'total':0, 'analyzed':0, 'pages':0, 'pages_read':0, 'pages_analyzed':0,
                                     'dated':0, 'dates_unavailable':0, 'undated':0},
                           comparisons={'pending':0, 'assessed':0, 'failed':0}),
}
for name, record in fixtures.items():
    path = ROOT / 'shared' / f'{name}.fixture.json'
    body = json.dumps(record.model_dump(), indent=2) + '\n'
    if '--check' in sys.argv:
        if not path.exists() or path.read_text() != body:
            raise SystemExit(f'{name} fixture is stale. Run scripts/export_fixtures.py.')
    else:
        path.write_text(body)
