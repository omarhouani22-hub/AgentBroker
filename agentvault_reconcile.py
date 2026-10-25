"""Operator-only payment review: provider GET only, never refunds or charges.

A refund, reversal or other non-completed capture puts writes and new checkout on
hold; read/export remains available under the existing retention period. Holds
require operator resolution; a later API response never silently clears one.
"""
from agentvault_paypal import PayPalOrders, PaymentError


def reconcile_payments(app, limit=None):
    store = app.extensions['vault_store']
    expected_merchant = app.config['PAYPAL_MERCHANT_ID']
    if not store or not expected_merchant:
        raise RuntimeError('payment_review_not_configured')
    provider = PayPalOrders(app.config['PAYPAL_CLIENT_ID'], app.config['PAYPAL_CLIENT_SECRET'], app.config['PAYPAL_ENVIRONMENT'])
    if limit is not None and (type(limit) is not int or not 1<=limit<=100):
        raise ValueError('invalid_review_limit')
    with store.transaction() as conn:
        query="""SELECT o.* FROM av_orders o WHERE o.state='paid' AND o.granted_at>0
          ORDER BY COALESCE((SELECT MAX(a.created_at) FROM av_audit a
          WHERE a.vault_id=o.vault_id AND a.event='payment_checked:' || o.reference),0),o.reference"""
        if limit is not None:query+=' LIMIT ?'
        orders = [dict(row) for row in store.sql(conn,query,(limit,) if limit is not None else ()).fetchall()]
    checked = held = failed = 0
    for order in orders:
        try:
            result = provider.get_order(order['provider_id'])
            units = result.get('purchase_units',[])
            if (result.get('id')!=order['provider_id'] or len(units)!=1
                    or units[0].get('reference_id')!=order['reference']
                    or units[0].get('payee',{}).get('merchant_id')!=expected_merchant):
                raise PaymentError('payment_identity_unverified')
            captures = units[0].get('payments',{}).get('captures',[])
            if len(captures)!=1 or captures[0].get('amount',{}).get('currency_code')!='USD' or captures[0].get('amount',{}).get('value')!=order['amount']:
                raise PaymentError('payment_amount_unverified')
            status = captures[0].get('status')
            if status not in ('COMPLETED','REFUNDED','PARTIALLY_REFUNDED','PENDING','DECLINED','FAILED'):
                raise PaymentError('payment_status_unverified')
            checked += 1
            import time
            with store.transaction() as conn:
                store.audit(conn,order['vault_id'],'payment_checked:'+order['reference'],int(time.time()))
            if status!='COMPLETED' or result.get('status')!='COMPLETED':
                import time
                with store.transaction() as conn:
                    store.lock_vault(conn,order['vault_id'])
                    current = store.sql(conn,'SELECT state FROM av_orders WHERE reference=?',(order['reference'],)).fetchone()
                    if current and current['state']=='paid':
                        store.sql(conn,"UPDATE av_orders SET state='payment_hold' WHERE reference=?",(order['reference'],))
                        store.audit(conn,order['vault_id'],'payment_review_'+status.lower(),int(time.time()))
                        held += 1
        except PaymentError:
            failed += 1
    return {'checked':checked,'new_holds':held,'verification_failures':failed}


if __name__ == '__main__':
    import json
    from agentvault_service import app
    print(json.dumps(reconcile_payments(app)))
