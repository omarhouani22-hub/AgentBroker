"""Portable encrypted logical backups. Restore ONLY to a new local test database.

The recovery key must be held separately from the encrypted archive. The archive
contains the application encryption key, so it must never be logged or published.
No command overwrites production or enables sales.
"""
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
from cryptography.fernet import Fernet
from agentvault_service import Store

TABLES = {
    'av_vaults': ('id','token_hash','created_at','expires_at','version','quota_bytes','terms_version','deleted_at'),
    'av_checkpoints': ('vault_id','version','created_at','byte_count','digest','encrypted'),
    'av_orders': ('reference','vault_id','provider_id','amount','state','created_at','granted_at'),
    'av_limits': ('bucket','count'),
    'av_audit': ('id','vault_id','event','created_at'),
}
MAX_BYTES = 64*1024*1024


def encode_snapshot(rows, encryption_key=None):
    """Canonical transport format; ciphertext is base64, never pickle or SQL."""
    if set(rows) != set(TABLES): raise ValueError('unexpected_tables')
    result = {}
    for table,columns in TABLES.items():
        result[table] = []
        for row in rows[table]:
            if set(row) != set(columns): raise ValueError('unexpected_columns')
            item = dict(row)
            if table == 'av_checkpoints':
                item['encrypted'] = base64.b64encode(bytes(item['encrypted'])).decode()
            result[table].append(item)
    return {'format':'agentvault-logical-v1','encryption_key':encryption_key,
            'tables':result}


def seal_snapshot(snapshot, recovery_key):
    payload=json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()
    if len(payload)>MAX_BYTES: raise ValueError('backup_too_large')
    return Fernet(recovery_key).encrypt(payload)


def open_snapshot(archive, recovery_key):
    if len(archive)>MAX_BYTES*2: raise ValueError('backup_too_large')
    payload=Fernet(recovery_key).decrypt(archive)
    if len(payload)>MAX_BYTES: raise ValueError('backup_too_large')
    result=json.loads(payload)
    if result.get('format')!='agentvault-logical-v1': raise ValueError('unsupported_backup')
    if set(result.get('tables',{}))!=set(TABLES): raise ValueError('unexpected_tables')
    cipher=Fernet(result['encryption_key'].encode()) if result.get('encryption_key') else None
    for table,columns in TABLES.items():
        if not isinstance(result['tables'][table],list): raise ValueError('invalid_rows')
        for row in result['tables'][table]:
            if set(row)!=set(columns): raise ValueError('unexpected_columns')
            if table=='av_checkpoints':
                encrypted=base64.b64decode(row['encrypted'],validate=True)
                if cipher is None: continue
                raw=cipher.decrypt(encrypted)
                prefix=row['vault_id'].encode()+b'\0'
                if not raw.startswith(prefix): raise ValueError('tenant_integrity_failed')
                data=raw[len(prefix):]
                if len(data)!=row['byte_count'] or not hmac.compare_digest(hashlib.sha256(data).hexdigest(),row['digest']):
                    raise ValueError('checkpoint_integrity_failed')
    return result


def restore_local(archive, recovery_key, destination):
    """Validate the archive and restore into a NEW SQLite database, never Postgres."""
    snapshot=open_snapshot(archive,recovery_key)
    path=Path(destination)
    # Exclusive creation prevents symlink traversal or accidental overwrite.
    fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    os.close(fd)
    store=Store(str(path),testing=True)
    try:
        store.migrate()
        with store.transaction() as conn:
            for table,columns in TABLES.items():
                for original in snapshot['tables'][table]:
                    row=dict(original)
                    if table=='av_checkpoints': row['encrypted']=base64.b64decode(row['encrypted'],validate=True)
                    values=tuple(row[name] for name in columns)
                    store.sql(conn,'INSERT INTO '+table+' ('+','.join(columns)+') VALUES ('+','.join('?' for _ in columns)+')',values)
        return {'counts':{name:len(rows) for name,rows in snapshot['tables'].items()},
                'checkpoint_integrity_verified':bool(snapshot.get('encryption_key')),'destination_type':'isolated_sqlite'}
    except Exception:
        path.unlink(missing_ok=True)
        raise
