import time
import tempfile
import unittest
from unittest.mock import patch
from cryptography.fernet import Fernet
from agentvault_service import create_app,PLAN,TERMS_VERSION
from agentvault_reconcile import reconcile_payments

class PaymentReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.app=create_app(dict(TESTING=True,DATABASE_URL=self.temp.name+'/db',ENCRYPTION_KEY=Fernet.generate_key().decode(),SALES_ENABLED=True,RECOVERY_VERIFIED=True,PUBLIC_ORIGIN='https://vault.example',PAYPAL_ENVIRONMENT='sandbox',PAYPAL_CLIENT_ID='mock',PAYPAL_CLIENT_SECRET='mock',PAYPAL_MERCHANT_ID='MERCHANT'))
        self.store=self.app.extensions['vault_store'];self.store.migrate();self.client=self.app.test_client()
        v=self.client.post('/v1/vaults',json={'accept_terms':TERMS_VERSION}).get_json();self.vid=v['vault_id']
        self.headers={'X-Vault-Id':self.vid,'Authorization':'Bearer '+v['secret']}
        with self.store.transaction() as conn:
            self.store.sql(conn,'UPDATE av_vaults SET expires_at=? WHERE id=?',(int(time.time())+86400,self.vid))
            self.store.sql(conn,"INSERT INTO av_orders VALUES (?,?,?,'5.00','paid',?,?)",('REF',self.vid,'ORDER',int(time.time()),int(time.time())))
        self.assertEqual(self.client.put('/v1/checkpoint',data=b'recoverable',headers=self.headers).status_code,201)
    def tearDown(self):self.temp.cleanup()
    def result(self,status):
        return {'id':'ORDER','status':'COMPLETED','purchase_units':[{'reference_id':'REF','payee':{'merchant_id':'MERCHANT'},'payments':{'captures':[{'status':status,'amount':{'currency_code':'USD','value':'5.00'}}]}}]}
    def test_refund_and_other_capture_failures_hold_writes_keep_export_and_never_reactivate(self):
        for status in ('REFUNDED','PARTIALLY_REFUNDED','PENDING','DECLINED','FAILED'):
            with self.subTest(status=status):
                with self.store.transaction() as conn:
                    self.store.sql(conn,"UPDATE av_orders SET state='paid'")
                    self.store.sql(conn,"DELETE FROM av_limits")
                with patch('agentvault_reconcile.PayPalOrders.get_order',return_value=self.result(status)),patch('agentvault_reconcile.PayPalOrders.capture_order') as capture,patch('agentvault_reconcile.PayPalOrders.create_order') as create:
                    self.assertEqual(reconcile_payments(self.app)['new_holds'],1)
                    self.assertEqual(reconcile_payments(self.app)['new_holds'],0)
                    capture.assert_not_called();create.assert_not_called()
                self.assertEqual(self.client.put('/v1/checkpoint',data=b'blocked',headers=self.headers).status_code,403)
                self.assertEqual(self.client.get('/v1/checkpoint',headers=self.headers).data,b'recoverable')
                state=self.client.get('/v1/vault',headers=self.headers).get_json()
                self.assertFalse(state['active']);self.assertTrue(state['payment_review_required'])
                self.assertEqual(self.client.post('/v1/orders',json={'plan_id':PLAN['id']},headers=self.headers).status_code,403)
                self.assertEqual(self.client.post('/v1/orders/ORDER/capture',headers=self.headers).status_code,403)
    def test_existing_pending_renewal_cannot_charge_while_an_earlier_payment_is_on_hold(self):
        with self.store.transaction() as conn:
            self.store.sql(conn,"UPDATE av_orders SET state='payment_hold'")
            self.store.sql(conn,"INSERT INTO av_orders VALUES (?,?,?,'5.00','pending',?,0)",('RENEWAL',self.vid,'PENDINGORDER',int(time.time())))
        with patch('agentvault_service.PayPalOrders.capture_order') as capture:
            self.assertEqual(self.client.post('/v1/orders/PENDINGORDER/capture',headers=self.headers).status_code,403)
            capture.assert_not_called()

    def test_completed_and_unverified_identity_do_not_modify_entitlement(self):
        for field,value in [('status','COMPLETED'),('id','OTHER')]:
            result=self.result('COMPLETED');result[field]=value
            with patch('agentvault_reconcile.PayPalOrders.get_order',return_value=result):
                reviewed=reconcile_payments(self.app)
            self.assertEqual(reviewed['new_holds'],0)
            self.assertEqual(reviewed['verification_failures'],int(field=='id'))
        self.assertEqual(self.client.put('/v1/checkpoint',data=b'allowed',headers=self.headers).status_code,201)
