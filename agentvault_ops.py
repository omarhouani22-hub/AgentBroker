"""Operator maintenance; no credentials or customer content are printed."""
import sys
import time
import uuid
import hashlib
import secrets
from agentvault_service import app, PLAN

def payment_check():
    """Create an unapproved diagnostic order; never approve or capture money.

    Output contains only the merchant's public identifier, never credentials,
    access tokens, approval links, or payer information.
    """
    from agentvault_paypal import PayPalOrders, PaymentError
    from urllib.parse import urlsplit
    origin=app.config['PUBLIC_ORIGIN'].rstrip('/')
    parsed=urlsplit(origin)
    if parsed.scheme!='https' or not parsed.netloc or parsed.path or parsed.query or parsed.fragment:
        raise RuntimeError('public_origin_unconfigured')
    provider=PayPalOrders(app.config['PAYPAL_CLIENT_ID'],app.config['PAYPAL_CLIENT_SECRET'],app.config['PAYPAL_ENVIRONMENT'])
    result=provider.create_order('launch-check-'+uuid.uuid4().hex,PLAN['amount'],
                                origin+'/console?payment=return',origin+'/console?payment=cancel')
    units=result.get('purchase_units',[])
    if result.get('status') not in ('CREATED','PAYER_ACTION_REQUIRED') or len(units)!=1:
        raise PaymentError('diagnostic_order_not_created')
    merchant=units[0].get('payee',{}).get('merchant_id','')
    import re
    if not re.fullmatch(r'[A-Z0-9]{8,32}',merchant):
        raise PaymentError('merchant_identity_not_returned')
    expected=app.config['PAYPAL_MERCHANT_ID']
    if expected and expected!=merchant:
        raise PaymentError('merchant_identity_mismatch')
    print('PASS: PayPal '+provider.environment+' unapproved order created; no payment captured; merchant_id='+merchant)
    return merchant

def maintenance():
    store=app.extensions['vault_store']
    if not store:raise RuntimeError('database_unconfigured')
    now=int(time.time())
    with store.transaction() as conn:
        store.sql(conn,'''DELETE FROM av_checkpoints WHERE vault_id IN
          (SELECT id FROM av_vaults WHERE expires_at<?)''',(now-7*86400,))
        store.sql(conn,'DELETE FROM av_audit WHERE created_at<?',(now-90*86400,))
        # Rate bucket names include their fixed-window epoch; no personal identifiers.
        rows=store.sql(conn,'SELECT bucket FROM av_limits').fetchall()
        for row in rows:
            bucket=row['bucket'];window=int(bucket.rsplit(':',1)[-1]);unit=3600 if bucket.startswith('signup:') else 60
            if window*unit<now-2*86400:store.sql(conn,'DELETE FROM av_limits WHERE bucket=?',(bucket,))
    print('Maintenance completed')

def recovery_drill():
    """Synthetic record only. Reconstruct the app after commit and verify bytes.

    Does not enable sales, activate real customers, or call PayPal. A separate
    database backup restoration drill is still needed before launch.
    """
    from agentvault_service import create_app
    store=app.extensions['vault_store']
    if not store or not store.pg:raise RuntimeError('external_postgres_required')
    vid,token=uuid.uuid4().hex,secrets.token_urlsafe(32)
    now=int(time.time());payload=secrets.token_bytes(128)
    try:
        with store.transaction() as conn:
            store.sql(conn,'''INSERT INTO av_vaults
              (id,token_hash,created_at,expires_at,quota_bytes,terms_version)
              VALUES (?,?,?,?,?,?)''',(vid,hashlib.sha256(token.encode()).hexdigest(),now,now+3600,PLAN['quota_bytes'],'operator-drill'))
        headers={'X-Vault-Id':vid,'Authorization':'Bearer '+token}
        result=app.test_client().put('/v1/checkpoint',data=payload,headers=headers)
        if result.status_code!=201:raise RuntimeError('save_failed')
        restarted=create_app()
        recovered=restarted.test_client().get('/v1/checkpoint',headers=headers)
        if recovered.status_code!=200 or recovered.data!=payload:raise RuntimeError('restore_failed')
        print('PASS: committed encrypted synthetic checkpoint survived application reconstruction')
    finally:
        with store.transaction() as conn:
            store.sql(conn,'DELETE FROM av_checkpoints WHERE vault_id=?',(vid,))
            store.sql(conn,'DELETE FROM av_audit WHERE vault_id=?',(vid,))
            store.sql(conn,'DELETE FROM av_vaults WHERE id=?',(vid,))

if __name__=='__main__':
    if sys.argv[1:] == ['maintenance']:maintenance()
    elif sys.argv[1:] == ['recovery-drill']:recovery_drill()
    elif sys.argv[1:] == ['payment-check']:payment_check()
    else:raise SystemExit('Choose maintenance, recovery-drill or payment-check')
