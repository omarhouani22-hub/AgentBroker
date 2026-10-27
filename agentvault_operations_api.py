"""Disabled-by-default, narrowly scoped scheduler endpoints.

Scheduler receives only an encrypted data snapshot, never DB/PayPal/encryption
credentials. Provisioning OPERATIONS_TOKEN is a separate owner approval step.
"""
import hashlib
import hmac
import time
from flask import request,jsonify,Response


def register_operations(app):
    def authorize(kind):
        from agentvault_service import Rejected
        token=app.config.get('OPERATIONS_TOKEN','')
        if len(token)<32:raise Rejected('operations_not_configured',503)
        supplied=request.headers.get('X-AgentVault-Operations','')
        if not hmac.compare_digest(supplied.encode(),token.encode()):raise Rejected('unauthorized',401)
        store=app.extensions['vault_store']
        if not store or not app.config.get('ENCRYPTION_KEY'):raise Rejected('service_not_configured',503)
        with store.transaction() as conn:
            store.limit(conn,'ops-'+kind+':'+str(int(time.time())//3600),6)
        return store

    @app.post('/internal/operations/backup')
    def backup():
        from agentvault_backup import TABLES,encode_snapshot,seal_snapshot
        store=authorize('backup')
        with store.transaction() as conn:
            if store.pg:store.sql(conn,'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            rows={table:[dict(row) for row in store.sql(conn,'SELECT * FROM '+table).fetchall()] for table in TABLES}
        # Owner keeps the original key independently; it is never inside archive.
        archive=seal_snapshot(encode_snapshot(rows),app.config['ENCRYPTION_KEY'].encode())
        return Response(archive,headers={'Content-Type':'application/octet-stream',
            'Content-Disposition':'attachment; filename="agentvault-backup.fernet"',
            'Cache-Control':'no-store','X-Backup-SHA256':hashlib.sha256(archive).hexdigest()})

    @app.post('/internal/operations/review')
    def review():
        authorize('review')
        from agentvault_reconcile import reconcile_payments
        result=reconcile_payments(app,limit=1)
        return jsonify(result),502 if result['verification_failures'] else 200

    @app.post('/internal/operations/maintenance')
    def maintenance():
        authorize('maintenance')
        from agentvault_ops import maintenance as perform
        perform(app)
        return jsonify(completed=True)
