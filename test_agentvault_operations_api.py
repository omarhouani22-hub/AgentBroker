import tempfile
import unittest
from unittest.mock import patch
from cryptography.fernet import Fernet
from agentvault_service import create_app
from agentvault_backup import open_snapshot

class OperationsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.key=Fernet.generate_key()
        self.app=create_app(dict(TESTING=True,DATABASE_URL=self.temp.name+'/db',ENCRYPTION_KEY=self.key.decode(),OPERATIONS_TOKEN='s'*43))
        self.app.extensions['vault_store'].migrate();self.client=self.app.test_client()
        self.headers={'X-AgentVault-Operations':'s'*43}
    def tearDown(self):self.temp.cleanup()
    def test_disabled_and_wrong_token_cannot_access_any_operation(self):
        for route in ('backup','review','maintenance'):
            self.assertEqual(self.client.post('/internal/operations/'+route).status_code,401)
            self.app.config['OPERATIONS_TOKEN']=''
            self.assertEqual(self.client.post('/internal/operations/'+route,headers=self.headers).status_code,503)
            self.app.config['OPERATIONS_TOKEN']='s'*43
        self.app.config.update(SALES_ENABLED=True,RECOVERY_VERIFIED=True,PUBLIC_ORIGIN='https://vault.example',PAYPAL_CLIENT_ID='mock',PAYPAL_CLIENT_SECRET='mock')
        self.assertEqual(self.client.post('/v1/orders/ANY/capture',headers=self.headers).status_code,401)
    def test_archive_excludes_original_key_and_needs_owner_key(self):
        response=self.client.post('/internal/operations/backup',headers=self.headers)
        self.assertEqual(response.status_code,200)
        self.assertNotIn(self.key,response.data)
        snapshot=open_snapshot(response.data,self.key)
        self.assertIsNone(snapshot['encryption_key'])
        self.assertEqual(snapshot['tables']['av_checkpoints'],[])
        with self.assertRaises(Exception):open_snapshot(response.data,Fernet.generate_key())
    def test_review_is_bounded_and_failures_are_not_reported_as_success(self):
        with patch('agentvault_reconcile.reconcile_payments',return_value={'checked':0,'new_holds':0,'verification_failures':1}) as review:
            response=self.client.post('/internal/operations/review',headers=self.headers)
            self.assertEqual(response.status_code,502)
            review.assert_called_once_with(self.app,limit=1)
    def test_backup_never_triggers_maintenance_and_rate_limit_bounds_downloads(self):
        with patch('agentvault_ops.maintenance') as maintenance:
            for _ in range(6):self.assertEqual(self.client.post('/internal/operations/backup',headers=self.headers).status_code,200)
            self.assertEqual(self.client.post('/internal/operations/backup',headers=self.headers).status_code,429)
            maintenance.assert_not_called()
