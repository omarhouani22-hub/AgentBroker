"""Real PostgreSQL integration checks; disposable loopback CI database only."""
import hashlib
import os
import time
import unittest
import tempfile
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from cryptography.fernet import Fernet
from agentvault_service import create_app, PLAN, TERMS_VERSION
from agentvault_backup import TABLES, encode_snapshot, seal_snapshot, restore_local

DSN = os.getenv('AGENTVAULT_TEST_POSTGRES_URL', '')

@unittest.skipUnless(DSN, 'Disposable PostgreSQL test database not configured')
class PostgresTests(unittest.TestCase):
    def setUp(self):
        from psycopg.conninfo import conninfo_to_dict
        target = conninfo_to_dict(DSN)
        if target.get('host') not in ('127.0.0.1', 'localhost') or target.get('dbname') != 'agentvault_ci':
            raise RuntimeError('Only loopback disposable agentvault_ci database is permitted')
        self.config = dict(TESTING=True, DATABASE_URL=DSN, ENCRYPTION_KEY=Fernet.generate_key().decode(),
            SALES_ENABLED=True, RECOVERY_VERIFIED=True, PUBLIC_ORIGIN='https://vault.example',
            PAYPAL_ENVIRONMENT='sandbox', PAYPAL_CLIENT_ID='mock', PAYPAL_CLIENT_SECRET='mock',
            PAYPAL_MERCHANT_ID='TESTMERCHANT')
        self.app = create_app(self.config)
        self.store = self.app.extensions['vault_store']
        self.store.migrate()
        with self.store.transaction() as conn:
            self.store.sql(conn, 'TRUNCATE av_checkpoints,av_orders,av_audit,av_limits,av_vaults')
        self.client = self.app.test_client()
        self.vault = self.client.post('/v1/vaults', json={'accept_terms': TERMS_VERSION}).get_json()
        self.headers = {'X-Vault-Id': self.vault['vault_id'], 'Authorization': 'Bearer '+self.vault['secret']}

    def activate(self):
        with self.store.transaction() as conn:
            self.store.sql(conn, 'UPDATE av_vaults SET expires_at=? WHERE id=?',
                (int(time.time())+86400, self.vault['vault_id']))

    def test_parallel_checkpoint_versions_are_serialized_and_bounded(self):
        self.activate()
        def save(i):
            with self.app.test_client() as client:
                response = client.put('/v1/checkpoint', data=('parallel-'+str(i)).encode(), headers=self.headers)
                return response.status_code, response.get_json()
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(save, range(8)))
        self.assertEqual([status for status,_ in results], [201]*8)
        self.assertEqual(sorted(body['version'] for _,body in results), list(range(1,9)))
        status = self.client.get('/v1/vault', headers=self.headers).get_json()
        self.assertEqual([item['version'] for item in status['versions']], [8,7,6,5,4])
        restarted = create_app(self.config).test_client()
        response = restarted.get('/v1/checkpoint', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['X-Content-SHA256'], hashlib.sha256(response.data).hexdigest())

    def test_postgres_snapshot_restores_with_separate_key(self):
        self.activate()
        payload = b'postgres snapshot recovery synthetic state'
        self.assertEqual(self.client.put('/v1/checkpoint', data=payload, headers=self.headers).status_code, 201)
        with self.store.transaction() as conn:
            self.store.sql(conn, 'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            rows = {table:[dict(row) for row in self.store.sql(conn, 'SELECT * FROM '+table).fetchall()] for table in TABLES}
        recovery_key = Fernet.generate_key()
        archive = seal_snapshot(encode_snapshot(rows,self.config['ENCRYPTION_KEY']), recovery_key)
        with tempfile.TemporaryDirectory() as temp:
            path = temp+'/restored.sqlite'
            result = restore_local(archive,recovery_key,path)
            self.assertTrue(result['checkpoint_integrity_verified'])
            restored = create_app({**self.config,'DATABASE_URL':path}).test_client()
            response = restored.get('/v1/checkpoint',headers=self.headers)
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.data,payload)
        self.assertNotIn(payload,archive)

    def test_parallel_capture_grants_exactly_once(self):
        with patch('agentvault_service.PayPalOrders.create_order',return_value={'id':'PGORDER','links':[{'rel':'approve','href':'https://www.sandbox.paypal.com/checkoutnow?token=PGORDER'}]}):
            self.assertEqual(self.client.post('/v1/orders',json={'plan_id':PLAN['id']},headers=self.headers).status_code,200)
        with self.store.transaction() as conn:
            ref = self.store.sql(conn,'SELECT reference FROM av_orders').fetchone()['reference']
        result = {'status':'COMPLETED','purchase_units':[{'reference_id':ref,'payee':{'merchant_id':'TESTMERCHANT'},'payments':{'captures':[{'status':'COMPLETED','amount':{'currency_code':'USD','value':'5.00'}}]}}]}
        def capture(_):
            with self.app.test_client() as client:
                return client.post('/v1/orders/PGORDER/capture',headers=self.headers).status_code
        with patch('agentvault_service.PayPalOrders.capture_order',return_value=result) as provider_capture, patch('agentvault_service.PayPalOrders.get_order',return_value=result):
            with ThreadPoolExecutor(max_workers=4) as pool:
                self.assertEqual(list(pool.map(capture,range(4))),[200]*4)
            self.assertEqual(provider_capture.call_count,1)
        with self.store.transaction() as conn:
            self.assertEqual(self.store.sql(conn,"SELECT COUNT(*) AS n FROM av_audit WHERE event='payment_activated'").fetchone()['n'],1)
            expiry = self.store.sql(conn,'SELECT expires_at FROM av_vaults').fetchone()['expires_at']
        self.assertLessEqual(abs(expiry-int(time.time())-30*86400),10)

if __name__ == '__main__':
    unittest.main()
