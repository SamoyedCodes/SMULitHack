import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .models import ConflictAssessment, Document


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, root: Path):
        self.path = root / "aithena.sqlite3"
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY, cache_key TEXT UNIQUE NOT NULL,
                    mode TEXT NOT NULL, created_at TEXT NOT NULL, body TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_documents_mode ON documents(mode, created_at);
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, cache_key TEXT UNIQUE NOT NULL,
                    kind TEXT NOT NULL, payload TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'queued',
                    attempts INTEGER NOT NULL DEFAULT 0, next_run REAL NOT NULL DEFAULT 0,
                    error TEXT, created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_jobs_pending ON jobs(state, next_run);
                CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS llm_cache (key TEXT PRIMARY KEY, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS comparisons (
                    id TEXT PRIMARY KEY, mode TEXT NOT NULL, body TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS batches (id TEXT PRIMARY KEY, body TEXT NOT NULL);
            """)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def put_document(self, doc: Document, cache_key: str | None = None):
        with self.connection() as db:
            if cache_key:
                db.execute("INSERT INTO documents VALUES (?, ?, ?, ?, ?)",
                           (doc.id, cache_key, doc.mode, doc.created_at, doc.model_dump_json()))
            else:
                db.execute("UPDATE documents SET body=? WHERE id=?", (doc.model_dump_json(), doc.id))

    def document(self, document_id: str) -> Document | None:
        with self.connection() as db:
            row = db.execute("SELECT body FROM documents WHERE id=?", (document_id,)).fetchone()
        return Document.model_validate_json(row["body"]) if row else None

    def cached_document(self, key: str) -> Document | None:
        with self.connection() as db:
            row = db.execute("SELECT body FROM documents WHERE cache_key=?", (key,)).fetchone()
        return Document.model_validate_json(row["body"]) if row else None

    def documents(self, mode: str) -> list[Document]:
        with self.connection() as db:
            rows = db.execute("SELECT body FROM documents WHERE mode=? ORDER BY created_at DESC", (mode,)).fetchall()
        return [Document.model_validate_json(r["body"]) for r in rows]

    def enqueue(self, key: str, kind: str, payload: dict):
        with self.connection() as db:
            db.execute("INSERT OR IGNORE INTO jobs(id,cache_key,kind,payload,created_at) VALUES(?,?,?,?,?)",
                       (str(uuid.uuid4()), key, kind, json.dumps(payload), now()))

    def recover(self, kind: str | None = None):
        with self.connection() as db:
            db.execute("UPDATE jobs SET state='queued', error='Resumed after interruption' WHERE state='running' AND (? IS NULL OR kind=?)", (kind, kind))

    def claim(self, kind: str | None = None) -> dict | None:
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM jobs WHERE state IN ('queued','waiting') AND next_run<=? AND (? IS NULL OR kind=?) ORDER BY created_at LIMIT 1",
                (time.time(), kind, kind)).fetchone()
            if row:
                db.execute("UPDATE jobs SET state='running', attempts=attempts+1 WHERE id=?", (row["id"],))
                job = dict(row)
                job["payload"] = json.loads(job["payload"])
                return job
        return None

    def job_state(self, job_id: str, state: str, error: str | None = None, delay: float = 0):
        with self.connection() as db:
            db.execute("UPDATE jobs SET state=?,error=?,next_run=? WHERE id=?",
                       (state, error, time.time() + delay, job_id))

    def retry(self, mode: str) -> int:
        with self.connection() as db:
            return db.execute(
                "UPDATE jobs SET state='queued',next_run=0,error=NULL WHERE state IN ('waiting','failed','blocked') "
                "AND json_extract(payload,'$.mode')=?", (mode,)).rowcount

    def jobs(self, mode: str) -> list[dict]:
        with self.connection() as db:
            rows = db.execute("SELECT * FROM jobs WHERE json_extract(payload,'$.mode')=? ORDER BY created_at", (mode,)).fetchall()
        return [{**dict(r), "payload": json.loads(r["payload"])} for r in rows]

    def set_setting(self, key: str, value):
        with self.connection() as db:
            db.execute("INSERT OR REPLACE INTO settings VALUES(?,?)", (key, json.dumps(value)))

    def setting(self, key: str, default=None):
        with self.connection() as db:
            row = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return json.loads(row["value"]) if row else default

    def cache_get(self, key: str):
        with self.connection() as db:
            row = db.execute("SELECT body FROM llm_cache WHERE key=?", (key,)).fetchone()
        return json.loads(row["body"]) if row else None

    def cache_put(self, key: str, value):
        with self.connection() as db:
            db.execute("INSERT OR REPLACE INTO llm_cache VALUES (?,?)", (key, json.dumps(value)))

    def put_comparison(self, result: ConflictAssessment):
        with self.connection() as db:
            db.execute("INSERT OR REPLACE INTO comparisons VALUES(?,?,?)",
                       (result.id, result.mode, result.model_dump_json()))

    def comparisons(self, mode: str) -> list[ConflictAssessment]:
        with self.connection() as db:
            rows = db.execute("SELECT body FROM comparisons WHERE mode=?", (mode,)).fetchall()
        return [ConflictAssessment.model_validate_json(r["body"]) for r in rows]

    def put_batch(self, batch_id: str, data: dict):
        with self.connection() as db:
            db.execute("INSERT INTO batches VALUES(?,?)", (batch_id, json.dumps(data)))

    def batch(self, batch_id: str):
        with self.connection() as db:
            row = db.execute("SELECT body FROM batches WHERE id=?", (batch_id,)).fetchone()
        return json.loads(row["body"]) if row else None

    def retry_ingestion(self, document_id: str, mode: str = "live") -> int:
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT body FROM documents WHERE id=? AND mode=?", (document_id, mode)).fetchone()
            if not row:
                return 0
            doc = Document.model_validate_json(row['body'])
            if doc.status not in {'failed', 'needs_source_review'}:
                return 0
            count = db.execute("UPDATE jobs SET state='queued',next_run=0,error=NULL WHERE kind='ingestion' AND state IN ('failed','complete') AND json_extract(payload,'$.document_id')=? AND json_extract(payload,'$.mode')=?", (document_id, mode)).rowcount
            if count:
                doc.status, doc.stage, doc.error = 'queued', 'Queued for local reading retry', None
                db.execute("UPDATE documents SET body=? WHERE id=?", (doc.model_dump_json(), document_id))
            return count
