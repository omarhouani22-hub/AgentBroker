"""Read an offsite ZIP; restore only to disposable SQLite, never production.

No network access, payment operations, production queries or credential output.
The owner key is supplied via getpass locally, or explicitly from the existing
Render environment. Only aggregate evidence is printed. No key is archived.
"""
import base64
import hashlib
import hmac
import io
import json
import os
import secrets
import tempfile
import time
import zipfile
from pathlib import Path


def drill(zip_bytes, expected_zip_sha256, key, probe=None):
    from cryptography.fernet import Fernet
    from agentvault_backup import TABLES, open_snapshot, restore_local, encode_snapshot
    from agentvault_service import Store, create_app

    if len(zip_bytes) > 20*1024*1024:
        raise ValueError('zip_too_large')
    if not hmac.compare_digest(hashlib.sha256(zip_bytes).hexdigest(), expected_zip_sha256):
        raise ValueError('zip_digest_mismatch')
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        if sorted(archive.namelist()) != ['agentvault-backup.fernet', 'agentvault-backup.sha256']:
            raise ValueError('unexpected_zip_contents')
        if any(item.file_size > 16*1024*1024 for item in archive.infolist()):
            raise ValueError('archive_too_large')
        encrypted = archive.read('agentvault-backup.fernet')
        checksum = archive.read('agentvault-backup.sha256').decode('ascii').split()
    if checksum != [hashlib.sha256(encrypted).hexdigest(), 'agentvault-backup.fernet']:
        raise ValueError('archive_digest_mismatch')
    snapshot = open_snapshot(encrypted, key)
    if snapshot.get('encryption_key') is not None:
        raise ValueError('offsite_archive_must_not_contain_key')
    cipher = Fernet(key)

    def verify(row):
        raw = cipher.decrypt(base64.b64decode(row['encrypted'], validate=True))
        prefix = row['vault_id'].encode()+b'\0'
        if not raw.startswith(prefix):
            raise ValueError('tenant_integrity_failed')
        payload = raw[len(prefix):]
        if len(payload) != row['byte_count'] or not hmac.compare_digest(hashlib.sha256(payload).hexdigest(), row['digest']):
            raise ValueError('checkpoint_integrity_failed')
        return payload

    for row in snapshot['tables']['av_checkpoints']:
        verify(row)
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='agentvault-offsite-drill-') as temporary:
        path = Path(temporary)/'restored.sqlite'
        restored = restore_local(encrypted, key, path)
        store = Store(str(path), testing=True)
        with store.transaction() as conn:
            if conn.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('sqlite_integrity_failed')
            if conn.execute('PRAGMA foreign_key_check').fetchall():
                raise ValueError('foreign_key_integrity_failed')
            rows = {name:[dict(row) for row in store.sql(conn, 'SELECT * FROM '+name).fetchall()] for name in TABLES}
        readback = encode_snapshot(rows)
        canonical = lambda rows: sorted(json.dumps(row, sort_keys=True) for row in rows)
        for name in TABLES:
            if canonical(readback['tables'][name]) != canonical(snapshot['tables'][name]):
                raise ValueError('restored_rows_differ')
        config = dict(TESTING=True, DATABASE_URL=str(path), ENCRYPTION_KEY=key.decode() if isinstance(key,bytes) else key,
                      SALES_ENABLED=False, RECOVERY_VERIFIED=False, PAYPAL_ENVIRONMENT='sandbox',
                      PAYPAL_CLIENT_ID='', PAYPAL_CLIENT_SECRET='', PAYPAL_MERCHANT_ID='', OPERATIONS_TOKEN='')
        client = create_app(config).test_client()
        for vault in snapshot['tables']['av_vaults']:
            rejected = client.get('/v1/vault', headers={'X-Vault-Id':vault['id'], 'Authorization':'Bearer '+secrets.token_urlsafe(32)})
            if rejected.status_code != 401:
                raise ValueError('wrong_secret_not_rejected')
        probe_ok = False
        if probe is not None:
            # Separate, previously exported operator-only fixture. Insert only
            # AFTER complete snapshot equality; never pretend it was in this ZIP.
            expected = verify(probe)
            token = secrets.token_urlsafe(32)
            with store.transaction() as conn:
                store.sql(conn, 'INSERT INTO av_vaults VALUES (?,?,?,?,?,?,?,?)',
                          (probe['vault_id'], hashlib.sha256(token.encode()).hexdigest(), int(time.time()),
                           int(time.time())+3600, probe['version'], 10485760, 'isolated-probe', 0))
                store.sql(conn, 'INSERT INTO av_checkpoints VALUES (?,?,?,?,?,?)',
                          tuple(base64.b64decode(probe[name]) if name=='encrypted' else probe[name] for name in TABLES['av_checkpoints']))
            response = create_app(config).test_client().get('/v1/checkpoint',
                headers={'X-Vault-Id':probe['vault_id'], 'Authorization':'Bearer '+token})
            if response.status_code != 200 or response.data != expected:
                raise ValueError('separate_probe_api_restore_failed')
            probe_ok = True
        result = dict(completed=True, destination_type='isolated_sqlite', counts=restored['counts'],
                      all_rows_identical=True, foreign_keys_valid=True,
                      archive_authenticated=True, archived_checkpoints_verified=len(snapshot['tables']['av_checkpoints']),
                      separate_synthetic_probe_verified=probe_ok, production_database_accessed=False,
                      elapsed_seconds=round(time.monotonic()-started,3))
    result['temporary_database_removed'] = not path.exists()
    return result


def main():
    import argparse
    import getpass
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--zip')
    source.add_argument('--zip-base64')
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--key-from-environment', action='store_true')
    parser.add_argument('--probe-from-verifier', action='store_true')
    args = parser.parse_args()
    key = os.environ.get('AGENTVAULT_KEY','') if args.key_from_environment else getpass.getpass('Saved AgentVault key: ')
    # Imports cannot accidentally inherit production DB/payment credentials.
    for name in list(os.environ):
        if name.startswith(('AGENTVAULT_', 'PAYPAL_')):
            os.environ.pop(name)
    probe = None
    if args.probe_from_verifier:
        import re
        text = Path(__file__).with_name('AgentVault-verify-saved-key.html').read_text()
        probe = json.loads(re.search(r'const checkpoint=(\{[^\n]+\});',text).group(1))
    data = Path(args.zip).read_bytes() if args.zip else base64.b64decode(args.zip_base64,validate=True)
    try:
        result = drill(data,args.sha256,key,probe)
    except Exception as error:
        # Never log exception details, input rows, plaintext or the key.
        raise SystemExit('Offsite drill failed: '+type(error).__name__) from None
    print('AGENTVAULT_OFFSITE_DRILL '+json.dumps(result,sort_keys=True))


if __name__ == '__main__':
    main()
