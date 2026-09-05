"""Durable, idempotent local ingestion. No inference dependencies."""
import hashlib
import json
import os
import tempfile
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

from .config import VERSION
from .documents import ALLOWED_EXTENSIONS, MAX_FILE_BYTES
from .models import BatchItem, BatchResponse, Document
from .store import now

INGESTION_VERSION = "ingestion-2.1"


def batch_response(store, body: dict) -> BatchResponse:
    return BatchResponse(id=body['id'], created_at=body['created_at'],
                         documents=[BatchItem.model_validate(item) for item in body['documents']],
                         progress=[doc for item in body['documents'] if item.get('id') and (doc := store.document(item['id']))])


async def ingest(files: list[UploadFile], config, store, batch_id: str) -> BatchResponse:
    if not 1 <= len(files) <= 80:
        for file in files:
            await file.close()
        raise HTTPException(422, 'Choose between 1 and 80 files.')
    items = []
    # Uploaded files may spool to disk; processing uses bounded chunks, never an 80-file RAM buffer.
    with tempfile.TemporaryDirectory(prefix='upload-', dir=config.data_dir) as temporary:
        try:
            for index, file in enumerate(files):
                filename = Path((file.filename or 'untitled').replace('\\', '/')).name
                suffix = Path(filename).suffix.lower()
                digest, size = hashlib.sha256(), 0
                path = Path(temporary) / str(index)
                with path.open('wb') as stream:
                    while chunk := await file.read(256 * 1024):
                        size += len(chunk)
                        digest.update(chunk)
                        if size <= MAX_FILE_BYTES:
                            stream.write(chunk)
                        # File.size is measured by Starlette during multipart parsing.
                        if size > MAX_FILE_BYTES:
                            break
                failure = None
                if suffix not in ALLOWED_EXTENSIONS:
                    failure = 'Unsupported format. Use PDF, DOCX, PNG, or JPEG.'
                elif size > MAX_FILE_BYTES:
                    failure = 'File exceeds the 25 MiB limit. No processing was queued.'
                elif size == 0:
                    failure = 'The file is empty. No processing was queued.'
                items.append({'filename': filename, 'suffix': suffix, 'sha256': digest.hexdigest(),
                              'size': file.size or size, 'error': failure, 'path': path})
        finally:
            for file in files:
                await file.close()
        fingerprint = hashlib.sha256(json.dumps([{k:v for k,v in i.items() if k != 'path'} for i in items], sort_keys=True).encode()).hexdigest()
        result = {'id': batch_id, 'created_at': now(), 'documents': [], 'request_fingerprint': fingerprint}
        # Documents, queue entries and batch acknowledgement commit together. Files land first;
        # a crash can leave an unreferenced original, never an acknowledged job without its file.
        with store.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            existing = db.execute('SELECT body FROM batches WHERE id=?', (batch_id,)).fetchone()
            if existing:
                body = json.loads(existing['body'])
                if body.get('request_fingerprint') != fingerprint:
                    raise HTTPException(409, 'This upload key belongs to a different batch. Choose files again.')
                result = body
            else:
                for item in items:
                    receipt = BatchItem(id=None, filename=item['filename'], error=item['error'])
                    if not item['error']:
                        format_key = '.jpg' if item['suffix'] == '.jpeg' else item['suffix']
                        cache_key = hashlib.sha256(f"{item['sha256']}:{format_key}:live:{INGESTION_VERSION}".encode()).hexdigest()
                        previous = db.execute('SELECT id FROM documents WHERE cache_key=?', (cache_key,)).fetchone()
                        if previous:
                            receipt.id, receipt.cached = previous['id'], True
                        else:
                            document = Document(id=str(uuid.uuid4()), filename=item['filename'], title=item['filename'],
                                                sha256=item['sha256'], mode='live', created_at=now(), model='local-ingestion', version=VERSION,
                                                stage='Queued for local reading; extraction is disabled')
                            directory = config.directory(document.id)
                            os.replace(item['path'], directory / ('original' + item['suffix']))
                            db.execute('INSERT INTO documents VALUES(?,?,?,?,?)', (document.id, cache_key, 'live', document.created_at, document.model_dump_json()))
                            db.execute('INSERT INTO jobs(id,cache_key,kind,payload,created_at) VALUES(?,?,?,?,?)',
                                       (str(uuid.uuid4()), cache_key, 'ingestion', json.dumps({'document_id':document.id,'mode':'live'}), now()))
                            receipt.id = document.id
                    result['documents'].append(receipt.model_dump())
                db.execute('INSERT INTO batches VALUES(?,?)', (batch_id, json.dumps(result)))
    return batch_response(store, result)


def source_path(config, document_id: str, name: str) -> Path:
    directory = config.directory(document_id, create=False)
    path = (directory / name).resolve()
    if not path.is_relative_to(directory) or not path.is_file():
        raise HTTPException(404, 'Source file is not available yet.')
    return path
