"""Self-service AgentVault service. Production requires external PostgreSQL.

Billing and customer writes stay closed until an operator has completed the
recovery drill and deliberately enabled sales. SQLite is for tests only.
"""
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit
from cryptography.fernet import Fernet, InvalidToken
from flask import Flask, jsonify, request, send_from_directory
from agentvault_paypal import PayPalOrders, PaymentError

MIB = 1024 * 1024
PLAN = {'id': 'starter30', 'name': 'AgentVault Starter', 'amount': '5.00',
        'currency': 'USD', 'days': 30, 'quota_bytes': 10*MIB,
        'max_checkpoint_bytes': MIB, 'max_versions': 5}
TERMS_VERSION = '2026-10-24'
SCHEMA = '''
CREATE TABLE IF NOT EXISTS av_vaults (
 id TEXT PRIMARY KEY, token_hash TEXT NOT NULL, created_at BIGINT NOT NULL,
 expires_at BIGINT NOT NULL DEFAULT 0, version BIGINT NOT NULL DEFAULT 0,
 quota_bytes BIGINT NOT NULL, terms_version TEXT NOT NULL, deleted_at BIGINT NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS av_checkpoints (
 vault_id TEXT NOT NULL REFERENCES av_vaults(id), version BIGINT NOT NULL,
 created_at BIGINT NOT NULL, byte_count BIGINT NOT NULL, digest TEXT NOT NULL,
 encrypted BYTEA NOT NULL, PRIMARY KEY(vault_id,version));
CREATE TABLE IF NOT EXISTS av_orders (
 reference TEXT PRIMARY KEY, vault_id TEXT NOT NULL REFERENCES av_vaults(id),
 provider_id TEXT UNIQUE, amount TEXT NOT NULL, state TEXT NOT NULL,
 created_at BIGINT NOT NULL, granted_at BIGINT NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS av_limits (bucket TEXT PRIMARY KEY, count BIGINT NOT NULL);
CREATE TABLE IF NOT EXISTS av_audit (
 id TEXT PRIMARY KEY, vault_id TEXT NOT NULL, event TEXT NOT NULL, created_at BIGINT NOT NULL);
CREATE INDEX IF NOT EXISTS av_orders_vault ON av_orders(vault_id);
CREATE INDEX IF NOT EXISTS av_audit_created ON av_audit(created_at);
'''

class Rejected(Exception):
    def __init__(self, message, code=400): self.message, self.code = message, code

class Store:
    def __init__(self, database_url, testing=False):
        self.url, self.testing = database_url, testing
        if not database_url: raise RuntimeError('database_unconfigured')
        self.pg = database_url.startswith(('postgres://', 'postgresql://'))
        if not self.pg and not testing: raise RuntimeError('external_postgres_required')
    @contextmanager
    def transaction(self):
        if self.pg:
            import psycopg
            from psycopg.rows import dict_row
            options = {} if self.testing else {'sslmode': 'require'}
            conn = psycopg.connect(self.url, connect_timeout=10, row_factory=dict_row,
                                  options='-c search_path=agentvault,pg_catalog', **options)
        else:
            conn = sqlite3.connect(self.url, timeout=10)
            conn.row_factory = sqlite3.Row
            conn.execute('PRAGMA foreign_keys=ON')
            conn.execute('BEGIN IMMEDIATE')
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback(); raise
        finally: conn.close()
    def sql(self, conn, query, args=()):
        return conn.execute(query.replace('?', '%s') if self.pg else query, args)
    def migrate(self):
        with self.transaction() as conn:
            if self.pg:
                self.sql(conn, 'CREATE SCHEMA IF NOT EXISTS agentvault')
                self.sql(conn, 'REVOKE ALL ON SCHEMA agentvault FROM PUBLIC')
            for statement in SCHEMA.split(';'):
                if statement.strip(): self.sql(conn, statement)
            if self.pg:
                for table in ('av_vaults','av_checkpoints','av_orders','av_limits','av_audit'):
                    self.sql(conn, 'ALTER TABLE '+table+' ENABLE ROW LEVEL SECURITY')
                    self.sql(conn, 'REVOKE ALL ON '+table+' FROM PUBLIC')
    def lock_vault(self, conn, vault_id):
        return self.sql(conn, 'SELECT * FROM av_vaults WHERE id=?' +
                        (' FOR UPDATE' if self.pg else ''), (vault_id,)).fetchone()
    def limit(self, conn, bucket, maximum):
        row = self.sql(conn, '''INSERT INTO av_limits VALUES (?,1)
          ON CONFLICT(bucket) DO UPDATE SET count=av_limits.count+1 RETURNING count''', (bucket,)).fetchone()
        if row['count'] > maximum: raise Rejected('rate_limit', 429)
    def audit(self, conn, vault_id, event, now):
        self.sql(conn, 'INSERT INTO av_audit VALUES (?,?,?,?)', (str(uuid.uuid4()),vault_id,event,now))

def create_app(config=None):
    app = Flask(__name__, static_folder=None)
    app.config.update(MAX_CONTENT_LENGTH=MIB, TESTING=False,
        DATABASE_URL=os.getenv('AGENTVAULT_DATABASE_URL',''),
        ENCRYPTION_KEY=os.getenv('AGENTVAULT_KEY',''),
        SALES_ENABLED=os.getenv('AGENTVAULT_SALES_ENABLED') == 'true',
        RECOVERY_VERIFIED=os.getenv('AGENTVAULT_RECOVERY_VERIFIED') == 'true',
        PUBLIC_ORIGIN=os.getenv('AGENTVAULT_PUBLIC_ORIGIN',''),
        PAYPAL_ENVIRONMENT=os.getenv('PAYPAL_ENVIRONMENT','sandbox'),
        PAYPAL_CLIENT_ID=os.getenv('PAYPAL_CLIENT_ID',''),
        PAYPAL_CLIENT_SECRET=os.getenv('PAYPAL_CLIENT_SECRET',''),
        PAYPAL_MERCHANT_ID=os.getenv('PAYPAL_MERCHANT_ID',''))
    if config: app.config.update(config)
    store = Store(app.config['DATABASE_URL'],app.testing) if app.config['DATABASE_URL'] else None
    cipher = Fernet(app.config['ENCRYPTION_KEY'].encode()) if app.config['ENCRYPTION_KEY'] else None
    app.extensions['vault_store'] = store
    def payment():
        return PayPalOrders(app.config['PAYPAL_CLIENT_ID'],app.config['PAYPAL_CLIENT_SECRET'],app.config['PAYPAL_ENVIRONMENT'])
    def origin():
        value = app.config['PUBLIC_ORIGIN'].rstrip('/')
        parts = urlsplit(value)
        if parts.scheme != 'https' or not parts.netloc or parts.path or parts.query or parts.fragment:
            raise Rejected('public_origin_unconfigured',503)
        return value
    def available():
        if not store or not cipher: raise Rejected('service_not_configured',503)
    def sales_open():
        available(); origin()
        if not app.config['SALES_ENABLED'] or not app.config['RECOVERY_VERIFIED']:
            raise Rejected('sales_not_enabled',503)
        if not app.testing and (app.config['PAYPAL_ENVIRONMENT'] != 'live' or not app.config['PAYPAL_MERCHANT_ID']):
            raise Rejected('live_payment_not_configured',503)
        if not app.config['PAYPAL_CLIENT_ID'] or not app.config['PAYPAL_CLIENT_SECRET']:
            raise Rejected('payment_not_configured',503)
    def credentials():
        available()
        vid, auth = request.headers.get('X-Vault-Id',''), request.headers.get('Authorization','')
        if not re.fullmatch(r'[a-f0-9]{32}',vid) or not auth.startswith('Bearer ') or not 32<=len(auth[7:])<=160:
            raise Rejected('unauthorized',401)
        return vid,hashlib.sha256(auth[7:].encode()).hexdigest()
    def authorized(conn, vid, digest, active=False):
        row = store.lock_vault(conn,vid)
        if not row or row['deleted_at'] or not hmac.compare_digest(row['token_hash'],digest):
            raise Rejected('unauthorized',401)
        if active and store.sql(conn,"SELECT 1 FROM av_orders WHERE vault_id=? AND state='payment_hold' LIMIT 1",(vid,)).fetchone():
            raise Rejected('payment_review_contact_support',403)
        if active and row['expires_at'] <= int(time.time()): raise Rejected('plan_expired',402)
        return row
    def bounded(conn, vid, cap=120):
        store.limit(conn, f'api:{vid}:{int(time.time())//60}',cap)
    @app.errorhandler(Rejected)
    def rejected(error): return jsonify(error=error.message),error.code
    @app.errorhandler(413)
    def oversized(_): return jsonify(error='checkpoint_too_large'),413
    @app.errorhandler(PaymentError)
    def payment_error(_): return jsonify(error='payment_unconfirmed_contact_support'),502
    @app.errorhandler(Exception)
    def unknown(error):
        from werkzeug.exceptions import HTTPException
        if isinstance(error,HTTPException): return jsonify(error=error.name),error.code
        app.logger.error('AgentVault failure class=%s',type(error).__name__)
        return jsonify(error='temporarily_unavailable'),503
    @app.after_request
    def headers(response):
        response.headers.update({'Cache-Control':'no-store','X-Content-Type-Options':'nosniff',
            'Referrer-Policy':'no-referrer','X-Frame-Options':'DENY',
            'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"})
        return response
    @app.get('/healthz')
    def health():
        available()
        with store.transaction() as conn: store.sql(conn,'SELECT 1 FROM av_vaults LIMIT 1')
        return jsonify(status='ok',service='agentvault',durable_database=store.pg,
                       recovery_verified=app.config['RECOVERY_VERIFIED'])
    @app.get('/v1/plans')
    def plans():
        try: sales_open(); enabled=True
        except Rejected: enabled=False
        return jsonify(plans=[PLAN],sales_enabled=enabled,terms_version=TERMS_VERSION)
    @app.post('/v1/vaults')
    def provision():
        sales_open()
        data=request.get_json(silent=True) or {}
        if data.get('accept_terms') != TERMS_VERSION: raise Rejected('accept_current_terms')
        vid,token = uuid.uuid4().hex,secrets.token_urlsafe(32)
        now=int(time.time())
        with store.transaction() as conn:
            # Global cap bounds abandoned registrations without trusting forwarded IPs.
            store.limit(conn,f'signup:{now//3600}',50)
            store.sql(conn,'''INSERT INTO av_vaults
              (id,token_hash,created_at,quota_bytes,terms_version) VALUES (?,?,?,?,?)''',
              (vid,hashlib.sha256(token.encode()).hexdigest(),now,PLAN['quota_bytes'],TERMS_VERSION))
        return jsonify(vault_id=vid,secret=token,warning='Save this key now. It is shown once.'),201
    @app.get('/v1/vault')
    def status():
        vid,digest=credentials()
        with store.transaction() as conn:
            row=authorized(conn,vid,digest); bounded(conn,vid)
            items=store.sql(conn,'''SELECT version,created_at,byte_count,digest FROM av_checkpoints
              WHERE vault_id=? ORDER BY version DESC''',(vid,)).fetchall()
            held=bool(store.sql(conn,"SELECT 1 FROM av_orders WHERE vault_id=? AND state='payment_hold' LIMIT 1",(vid,)).fetchone())
            return jsonify(vault_id=vid,expires_at=row['expires_at'],active=row['expires_at']>int(time.time()) and not held,
                payment_review_required=held,plan=PLAN,used_bytes=sum(x['byte_count'] for x in items),versions=[dict(x) for x in items])
    @app.put('/v1/checkpoint')
    def save():
        vid,digest=credentials(); payload=request.get_data()
        if not payload: raise Rejected('empty_checkpoint')
        if len(payload)>PLAN['max_checkpoint_bytes']: raise Rejected('checkpoint_too_large',413)
        now=int(time.time()); hashed=hashlib.sha256(payload).hexdigest()
        # Include tenant identity in authenticated ciphertext to prevent cross-tenant substitution.
        encrypted=cipher.encrypt(vid.encode()+b'\0'+payload)
        with store.transaction() as conn:
            row=authorized(conn,vid,digest,active=True); bounded(conn,vid)
            version=row['version']+1
            store.sql(conn,'DELETE FROM av_checkpoints WHERE vault_id=? AND version<=?',(vid,version-PLAN['max_versions']))
            used=store.sql(conn,'SELECT COALESCE(SUM(byte_count),0) AS used FROM av_checkpoints WHERE vault_id=?',(vid,)).fetchone()['used']
            if used+len(payload)>row['quota_bytes']: raise Rejected('storage_quota_exceeded',409)
            store.sql(conn,'INSERT INTO av_checkpoints VALUES (?,?,?,?,?,?)',(vid,version,now,len(payload),hashed,encrypted))
            store.sql(conn,'UPDATE av_vaults SET version=? WHERE id=?',(version,vid)); store.audit(conn,vid,'checkpoint_saved',now)
        return jsonify(version=version,sha256=hashed,byte_count=len(payload)),201
    @app.get('/v1/checkpoint')
    def restore():
        vid,digest=credentials(); selected=request.args.get('version')
        if selected is not None and (not selected.isdigit() or len(selected)>18): raise Rejected('invalid_version')
        with store.transaction() as conn:
            authorized(conn,vid,digest); bounded(conn,vid)
            # Read/export remains available for 7 days after plan expiry; data is then purgeable.
            row=store.lock_vault(conn,vid)
            if row['expires_at']+7*86400<int(time.time()): raise Rejected('retention_expired',410)
            query='SELECT * FROM av_checkpoints WHERE vault_id=?'
            args=(vid,)
            if selected: query+=' AND version=?'; args+=(int(selected),)
            item=store.sql(conn,query+' ORDER BY version DESC LIMIT 1',args).fetchone()
            if not item: raise Rejected('not_found',404)
        try: plaintext=cipher.decrypt(bytes(item['encrypted']))
        except InvalidToken: raise Rejected('integrity_check_failed',503)
        prefix=vid.encode()+b'\0'
        if not plaintext.startswith(prefix): raise Rejected('integrity_check_failed',503)
        payload=plaintext[len(prefix):]
        if not hmac.compare_digest(hashlib.sha256(payload).hexdigest(),item['digest']): raise Rejected('integrity_check_failed',503)
        return payload,200,{'Content-Type':'application/octet-stream','X-Checkpoint-Version':str(item['version']),
                           'X-Content-SHA256':item['digest'],'Content-Disposition':'attachment; filename="checkpoint.bin"'}
    @app.delete('/v1/checkpoints')
    def delete_checkpoints():
        vid,digest=credentials()
        if request.headers.get('X-Confirm-Delete')!='all-checkpoints': raise Rejected('confirmation_required')
        with store.transaction() as conn:
            authorized(conn,vid,digest); bounded(conn,vid)
            store.sql(conn,'DELETE FROM av_checkpoints WHERE vault_id=?',(vid,));store.audit(conn,vid,'checkpoints_deleted',int(time.time()))
        return jsonify(deleted=True)
    @app.post('/v1/orders')
    def order():
        sales_open(); vid,digest=credentials(); data=request.get_json(silent=True) or {}
        if data.get('plan_id')!=PLAN['id']: raise Rejected('invalid_plan')
        ref=uuid.uuid4().hex; now=int(time.time())
        with store.transaction() as conn:
            authorized(conn,vid,digest); bounded(conn,vid,10)
            if store.sql(conn,"SELECT 1 FROM av_orders WHERE vault_id=? AND state='payment_hold' LIMIT 1",(vid,)).fetchone():
                raise Rejected('payment_review_contact_support',403)
            old=store.sql(conn,"SELECT reference FROM av_orders WHERE vault_id=? AND state IN ('creating','pending','capturing') LIMIT 1",(vid,)).fetchone()
            if old: raise Rejected('order_already_pending_contact_support',409)
            store.sql(conn,'INSERT INTO av_orders VALUES (?,?,NULL,?,?,?,0)',(ref,vid,PLAN['amount'],'creating',now))
        result=payment().create_order(ref,PLAN['amount'],origin()+'/console?payment=return',origin()+'/console?payment=cancel')
        provider_id=result.get('id','')
        links=[x.get('href','') for x in result.get('links',[]) if x.get('rel') in ('payer-action','approve')]
        host='www.paypal.com' if app.config['PAYPAL_ENVIRONMENT']=='live' else 'www.sandbox.paypal.com'
        if not re.fullmatch(r'[A-Za-z0-9]{1,64}',provider_id) or len(links)!=1 or urlsplit(links[0]).hostname!=host or urlsplit(links[0]).scheme!='https':
            raise PaymentError('Invalid approval response')
        with store.transaction() as conn:
            store.sql(conn,"UPDATE av_orders SET provider_id=?,state='pending' WHERE reference=?",(provider_id,ref))
        return jsonify(order_id=provider_id,approval_url=links[0])
    @app.get('/v1/orders/pending')
    def pending_order():
        """Resume the same checkout after cancellation/tab loss; never charge here."""
        sales_open();vid,digest=credentials()
        with store.transaction() as conn:
            authorized(conn,vid,digest);bounded(conn,vid,10)
            item=store.sql(conn,"SELECT * FROM av_orders WHERE vault_id=? AND state IN ('creating','pending','capturing') ORDER BY created_at DESC LIMIT 1",(vid,)).fetchone()
            if not item: raise Rejected('no_pending_order',404)
            item=dict(item)
        if not item['provider_id']: raise Rejected('payment_needs_reconciliation_contact_support',409)
        result=payment().get_order(item['provider_id'])
        units=result.get('purchase_units',[])
        if (result.get('id')!=item['provider_id'] or len(units)!=1
                or units[0].get('reference_id')!=item['reference']
                or units[0].get('amount',{}).get('currency_code')!='USD'
                or units[0].get('amount',{}).get('value')!=item['amount']
                or (app.config['PAYPAL_MERCHANT_ID'] and units[0].get('payee',{}).get('merchant_id')!=app.config['PAYPAL_MERCHANT_ID'])):
            raise PaymentError('Existing order could not be verified')
        status=result.get('status')
        if status in ('APPROVED','COMPLETED'):
            return jsonify(order_id=item['provider_id'],capture_ready=True)
        host='www.paypal.com' if app.config['PAYPAL_ENVIRONMENT']=='live' else 'www.sandbox.paypal.com'
        links=[x.get('href','') for x in result.get('links',[]) if x.get('rel') in ('payer-action','approve')]
        if (status not in ('CREATED','PAYER_ACTION_REQUIRED') or len(links)!=1
                or urlsplit(links[0]).scheme!='https' or urlsplit(links[0]).hostname!=host):
            raise Rejected('payment_needs_reconciliation_contact_support',409)
        return jsonify(order_id=item['provider_id'],approval_url=links[0],resumed=True)
    @app.post('/v1/orders/<provider_id>/capture')
    def capture(provider_id):
        sales_open();vid,digest=credentials();now=int(time.time())
        with store.transaction() as conn:
            authorized(conn,vid,digest);bounded(conn,vid,10)
            if store.sql(conn,"SELECT 1 FROM av_orders WHERE vault_id=? AND state='payment_hold' LIMIT 1",(vid,)).fetchone():
                raise Rejected('payment_review_contact_support',403)
            item=store.sql(conn,'SELECT * FROM av_orders WHERE vault_id=? AND provider_id=?',(vid,provider_id)).fetchone()
            if not item: raise Rejected('order_not_found',404)
            if item['state']=='payment_hold': raise Rejected('payment_review_contact_support',403)
            if item['granted_at']: return jsonify(activated=True,already_completed=True)
            if item['state'] not in ('pending','capturing'): raise Rejected('payment_needs_reconciliation_contact_support',409)
            reconcile=item['state']=='capturing'
            if not reconcile:
                store.sql(conn,"UPDATE av_orders SET state='capturing' WHERE reference=?",(item['reference'],))
        result=payment().get_order(provider_id) if reconcile else payment().capture_order(provider_id)
        merchant=app.config['PAYPAL_MERCHANT_ID']
        units=result.get('purchase_units',[])
        if not PayPalOrders.verify_capture(result,item['reference'],item['amount']) or (merchant and units[0].get('payee',{}).get('merchant_id')!=merchant):
            raise PaymentError('Capture could not be verified')
        with store.transaction() as conn:
            row=authorized(conn,vid,digest)
            done=store.sql(conn,'SELECT granted_at FROM av_orders WHERE reference=?',(item['reference'],)).fetchone()
            if not done['granted_at']:
                expiry=max(row['expires_at'],now)+PLAN['days']*86400
                store.sql(conn,'UPDATE av_vaults SET expires_at=? WHERE id=?',(expiry,vid))
                store.sql(conn,"UPDATE av_orders SET state='paid',granted_at=? WHERE reference=?",(now,item['reference']))
                store.audit(conn,vid,'payment_activated',now)
        return jsonify(activated=True)
    @app.get('/')
    def home(): return send_from_directory('agentvault_site','index.html')
    @app.get('/console')
    def console(): return send_from_directory('agentvault_site','console.html')
    @app.get('/<path:name>')
    def assets(name):
        if name not in ('styles.css','console.js','docs.html','terms.html','privacy.html'): raise Rejected('not_found',404)
        return send_from_directory('agentvault_site',name)
    return app

app=create_app()
if __name__=='__main__':
    import sys
    if '--migrate' in sys.argv:
        if not app.extensions['vault_store']: raise RuntimeError('database_unconfigured')
        app.extensions['vault_store'].migrate()
        print('AgentVault schema ready')
    else: app.run(host='127.0.0.1',port=8080)
