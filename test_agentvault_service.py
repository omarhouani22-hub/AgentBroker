import hashlib
import os
import tempfile
import time
import unittest
from unittest.mock import patch
from cryptography.fernet import Fernet
from agentvault_paypal import PaymentError
from agentvault_service import create_app, Store, PLAN, TERMS_VERSION

class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.config={'TESTING':True,'DATABASE_URL':self.temp.name+'/service.sqlite',
          'ENCRYPTION_KEY':Fernet.generate_key().decode(),'SALES_ENABLED':True,'RECOVERY_VERIFIED':True,
          'PUBLIC_ORIGIN':'https://vault.example','PAYPAL_ENVIRONMENT':'sandbox',
          'PAYPAL_CLIENT_ID':'test-id','PAYPAL_CLIENT_SECRET':'test-secret','PAYPAL_MERCHANT_ID':'MERCHANT'}
        self.app=create_app(self.config);self.store=self.app.extensions['vault_store'];self.store.migrate()
        self.client=self.app.test_client()
        self.vault=self.client.post('/v1/vaults',json={'accept_terms':TERMS_VERSION}).get_json()
        self.headers={'X-Vault-Id':self.vault['vault_id'],'Authorization':'Bearer '+self.vault['secret']}
    def tearDown(self): self.temp.cleanup()
    def activate(self,seconds=86400):
        with self.store.transaction() as c:
            self.store.sql(c,'UPDATE av_vaults SET expires_at=? WHERE id=?',(int(time.time())+seconds,self.vault['vault_id']))
    def capture_result(self,reference,amount='5.00',merchant='MERCHANT',status='COMPLETED'):
        return {'status':status,'purchase_units':[{'reference_id':reference,'payee':{'merchant_id':merchant},
            'payments':{'captures':[{'status':'COMPLETED','amount':{'currency_code':'USD','value':amount}}]}}]}
    def pending(self):
        with patch('agentvault_service.PayPalOrders.create_order',return_value={'id':'ORDER123','links':[{'rel':'payer-action','href':'https://www.sandbox.paypal.com/checkoutnow?token=ORDER123'}]}):
            response=self.client.post('/v1/orders',json={'plan_id':PLAN['id']},headers=self.headers)
        self.assertEqual(response.status_code,200,response.data)
        with self.store.transaction() as c:
            return dict(self.store.sql(c,'SELECT * FROM av_orders WHERE provider_id=?',('ORDER123',)).fetchone())
    def test_production_refuses_sqlite_and_missing_configuration(self):
        with self.assertRaises(RuntimeError):Store('/tmp/unsafe.sqlite')
        app=create_app({'TESTING':True,'DATABASE_URL':'','ENCRYPTION_KEY':''})
        self.assertEqual(app.test_client().get('/healthz').status_code,503)
        self.assertFalse(app.test_client().get('/v1/plans').get_json()['sales_enabled'])
    def test_payment_gate_blocks_registration_and_writes(self):
        self.assertEqual(self.client.put('/v1/checkpoint',data=b'state',headers=self.headers).status_code,402)
        for setting in ('SALES_ENABLED','RECOVERY_VERIFIED'):
            self.app.config[setting]=False
            self.assertEqual(self.client.post('/v1/vaults',json={'accept_terms':TERMS_VERSION}).status_code,503)
            self.app.config[setting]=True
        self.assertEqual(self.client.post('/v1/vaults',json={}).status_code,400)
    def test_encrypted_restart_restore_and_tenant_isolation(self):
        self.activate();payload=b'important-agent-state'
        self.assertEqual(self.client.put('/v1/checkpoint',data=payload,headers=self.headers).status_code,201)
        with self.store.transaction() as c:
            stored=self.store.sql(c,'SELECT encrypted FROM av_checkpoints').fetchone()['encrypted']
        self.assertNotIn(payload,bytes(stored))
        restarted=create_app(self.config).test_client()
        response=restarted.get('/v1/checkpoint',headers=self.headers)
        self.assertEqual(response.data,payload)
        self.assertEqual(response.headers['X-Content-SHA256'],hashlib.sha256(payload).hexdigest())
        other=self.client.post('/v1/vaults',json={'accept_terms':TERMS_VERSION}).get_json()
        bad={**self.headers,'X-Vault-Id':other['vault_id']}
        self.assertEqual(self.client.get('/v1/checkpoint',headers=bad).status_code,401)
    def test_versions_integrity_quota_and_delete(self):
        self.activate()
        for i in range(7):self.assertEqual(self.client.put('/v1/checkpoint',data=str(i).encode(),headers=self.headers).status_code,201)
        data=self.client.get('/v1/vault',headers=self.headers).get_json()
        self.assertEqual([r['version'] for r in data['versions']],[7,6,5,4,3])
        self.assertEqual(self.client.get('/v1/checkpoint?version=2',headers=self.headers).status_code,404)
        self.assertEqual(self.client.get('/v1/checkpoint?version=3',headers=self.headers).data,b'2')
        self.assertEqual(self.client.put('/v1/checkpoint',data=b'x'*(1024*1024+1),headers=self.headers).status_code,413)
        self.assertEqual(self.client.put('/v1/checkpoint',data=b'',headers=self.headers).status_code,400)
        with self.store.transaction() as c:self.store.sql(c,'UPDATE av_vaults SET quota_bytes=0')
        self.assertEqual(self.client.put('/v1/checkpoint',data=b'x',headers=self.headers).status_code,409)
        self.assertEqual(self.client.delete('/v1/checkpoints',headers=self.headers).status_code,400)
        self.assertEqual(self.client.delete('/v1/checkpoints',headers={**self.headers,'X-Confirm-Delete':'all-checkpoints'}).status_code,200)
        self.assertEqual(self.client.get('/v1/checkpoint',headers=self.headers).status_code,404)
    def test_expired_read_grace_and_write_stop(self):
        self.activate();self.client.put('/v1/checkpoint',data=b'last',headers=self.headers)
        self.activate(-1)
        self.assertEqual(self.client.get('/v1/checkpoint',headers=self.headers).data,b'last')
        self.assertEqual(self.client.put('/v1/checkpoint',data=b'new',headers=self.headers).status_code,402)
        self.activate(-8*86400)
        self.assertEqual(self.client.get('/v1/checkpoint',headers=self.headers).status_code,410)
    def test_payment_amount_server_controlled_and_activation_idempotent(self):
        order=self.pending()
        with patch('agentvault_service.PayPalOrders.capture_order',return_value=self.capture_result(order['reference'])) as capture:
            self.assertEqual(self.client.post('/v1/orders/ORDER123/capture',headers=self.headers).status_code,200)
            first=self.client.get('/v1/vault',headers=self.headers).get_json()['expires_at']
            self.assertEqual(self.client.post('/v1/orders/ORDER123/capture',headers=self.headers).status_code,200)
            self.assertEqual(capture.call_count,1)
        self.assertEqual(self.client.get('/v1/vault',headers=self.headers).get_json()['expires_at'],first)
        self.assertEqual(self.client.post('/v1/orders',json={'plan_id':'cheaper','amount':'0.01'},headers=self.headers).status_code,400)
    def test_wrong_merchant_amount_or_pending_does_not_activate(self):
        order=self.pending()
        for result in [self.capture_result(order['reference'],amount='0.01'),
                       self.capture_result(order['reference'],merchant='WRONG'),
                       self.capture_result(order['reference'],status='PENDING')]:
            with self.store.transaction() as c:self.store.sql(c,"UPDATE av_orders SET state='pending'")
            with patch('agentvault_service.PayPalOrders.capture_order',return_value=result):
                self.assertEqual(self.client.post('/v1/orders/ORDER123/capture',headers=self.headers).status_code,502)
            self.assertFalse(self.client.get('/v1/vault',headers=self.headers).get_json()['active'])
    def test_capture_timeout_reconciles_without_second_capture(self):
        order=self.pending()
        with patch('agentvault_service.PayPalOrders.capture_order',side_effect=PaymentError('timeout')) as capture:
            self.assertEqual(self.client.post('/v1/orders/ORDER123/capture',headers=self.headers).status_code,502)
            with patch('agentvault_service.PayPalOrders.get_order',return_value=self.capture_result(order['reference'])):
                self.assertEqual(self.client.post('/v1/orders/ORDER123/capture',headers=self.headers).status_code,200)
            self.assertEqual(capture.call_count,1)
    def test_corruption_is_not_returned_and_keys_not_in_status(self):
        self.activate();self.client.put('/v1/checkpoint',data=b'state',headers=self.headers)
        with self.store.transaction() as c:self.store.sql(c,'UPDATE av_checkpoints SET encrypted=?',(b'bad',))
        self.assertEqual(self.client.get('/v1/checkpoint',headers=self.headers).status_code,503)
        response=self.client.get('/v1/vault',headers=self.headers)
        self.assertNotIn(self.vault['secret'].encode(),response.data)
        self.assertIn("default-src 'self'",response.headers['Content-Security-Policy'])
    def test_registration_and_api_rate_limits(self):
        self.activate()
        for _ in range(120):self.assertEqual(self.client.get('/v1/vault',headers=self.headers).status_code,200)
        self.assertEqual(self.client.get('/v1/vault',headers=self.headers).status_code,429)
    def test_static_assets_and_no_third_party_scripts(self):
        for path in ('/','/console','/styles.css','/console.js','/docs.html','/privacy.html','/terms.html'):
            with self.client.get(path) as response:
                self.assertEqual(response.status_code,200,path)
        self.assertEqual(self.client.get('/agentvault_service.py').status_code,404)

if __name__=='__main__':unittest.main()
