"""Opt-in encrypted S3 storage. SQLite remains the local retrieval index."""
import hashlib
import json
import os
import re
import uuid
from urllib.parse import urlsplit

from botocore.config import Config
from flask import jsonify, request, Response
from werkzeug.utils import secure_filename


class Storage:
    def __init__(self, cipher):
        import boto3
        endpoint = os.getenv('FLOCI_ENDPOINT_URL', '')
        parsed = urlsplit(endpoint)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('Invalid Floci endpoint')
        self.bucket = os.getenv('FLOCI_BUCKET', 'agentbroker-private')
        self.cipher = cipher
        self.client = boto3.client('s3', endpoint_url=endpoint,
            region_name=os.getenv('FLOCI_REGION', 'us-east-1'),
            aws_access_key_id='test', aws_secret_access_key='test',
            config=Config(connect_timeout=3, read_timeout=10,
                          retries={'max_attempts': 1}, s3={'addressing_style': 'path'}))

    def put(self, key, data):
        self.client.put_object(Bucket=self.bucket, Key=key,
                              Body=self.cipher.encrypt(data), ContentType='application/octet-stream')

    def get(self, key, limit=4_000_000):
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        body = response['Body']
        try:
            sealed = body.read(limit + 1)
        finally:
            body.close()
        if len(sealed) > limit:
            raise ValueError('Stored object exceeds limit')
        return self.cipher.decrypt(sealed)

    def keys(self, prefix, limit=500):
        result = []
        for page in self.client.get_paginator('list_objects_v2').paginate(Bucket=self.bucket, Prefix=prefix):
            result.extend(item['Key'] for item in page.get('Contents', []))
            if len(result) > limit:
                raise ValueError('Too many objects; use an offline migration')
        return result

    def note(self, value):
        digest = hashlib.sha256(value['id'].encode()).hexdigest()
        self.put('knowledge/' + digest + '.json', json.dumps(value, ensure_ascii=False).encode())


def enabled():
    return bool(os.getenv('FLOCI_ENDPOINT_URL'))


def mirror_note(value, cipher, logger):
    if not enabled():
        return
    try:
        Storage(cipher()).note(value)
    except Exception as error:
        # Local note is already committed; /storage/sync can retry the mirror.
        logger.warning('Floci mirror failed; local note retained; failure=%s', type(error).__name__)


def install_routes(app, db, cipher):
    from memory import validate_notes

    @app.get('/storage/status')
    def storage_status():
        if not enabled():
            return jsonify(enabled=False, reachable=False)
        try:
            Storage(cipher()).client.head_bucket(Bucket=os.getenv('FLOCI_BUCKET', 'agentbroker-private'))
            return jsonify(enabled=True, reachable=True)
        except Exception:
            return jsonify(enabled=True, reachable=False), 503

    @app.post('/storage/files')
    def upload_file():
        if not enabled():
            return jsonify(error='Floci storage is not configured'), 503
        file = request.files.get('file')
        if file is None or not file.filename:
            return jsonify(error='A file is required'), 400
        payload = file.read(1_000_001)
        if len(payload) > 1_000_000:
            return jsonify(error='File exceeds 1 MB'), 413
        identity = uuid.uuid4().hex
        name = secure_filename(file.filename)[:180] or 'document'
        # Bytes are inert storage: never execute or automatically follow file instructions.
        envelope = json.dumps({'name': name, 'hex': payload.hex()}).encode()
        try:
            Storage(cipher()).put('files/' + identity, envelope)
            return jsonify(id=identity, name=name, bytes=len(payload)), 201
        except Exception:
            return jsonify(error='File storage failed'), 503

    @app.get('/storage/files/<identity>')
    def download_file(identity):
        if not re.fullmatch(r'[a-f0-9]{32}', identity):
            return jsonify(error='Invalid file ID'), 400
        if not enabled():
            return jsonify(error='Floci storage is not configured'), 503
        try:
            envelope = json.loads(Storage(cipher()).get('files/' + identity))
            response = Response(bytes.fromhex(envelope['hex']), mimetype='application/octet-stream')
            response.headers['Content-Disposition'] = 'attachment; filename="' + secure_filename(envelope['name']) + '"'
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['Cache-Control'] = 'no-store'
            return response
        except Exception:
            return jsonify(error='File unavailable'), 503

    @app.get('/storage/files')
    def list_files():
        if not enabled():
            return jsonify(error='Floci storage is not configured'), 503
        try:
            return jsonify(ids=[key.removeprefix('files/') for key in Storage(cipher()).keys('files/')])
        except Exception:
            return jsonify(error='File listing failed'), 503

    @app.post('/storage/sync')
    def sync_notes():
        if not enabled():
            return jsonify(error='Floci storage is not configured'), 503
        try:
            store = Storage(cipher())
            # Validate all remote notes before any local writes; preserve their original IDs.
            restored = []
            for key in store.keys('knowledge/'):
                note = json.loads(store.get(key, 200_000))
                clean = validate_notes([note])[0]
                if not isinstance(note.get('id'), str) or not 1 <= len(note['id']) <= 200:
                    raise ValueError('Invalid identity')
                clean['id'] = note['id']
                restored.append(clean)
            with db() as conn:
                for note in restored:
                    conn.execute('INSERT OR IGNORE INTO knowledge VALUES (?, ?, ?, ?, ?)',
                        (note['id'], note['topic'], note['note'], json.dumps(note['sources']), note['created_at']))
                rows = conn.execute('SELECT id, topic, note, sources, created_at FROM knowledge').fetchall()
            for row in rows:
                store.note(dict(id=row[0], topic=row[1], note=row[2], sources=json.loads(row[3]), created_at=row[4]))
            return jsonify(synced=True, remote_notes=len(restored), local_notes=len(rows))
        except Exception as error:
            app.logger.warning('Floci sync failure=%s', type(error).__name__)
            return jsonify(error='Sync incomplete; local notes retained. Retry after resolving storage connectivity.'), 503
