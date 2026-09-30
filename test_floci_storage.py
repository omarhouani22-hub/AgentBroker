import os
import tempfile
import unittest
from unittest.mock import patch

import boto3
from moto import mock_aws
import app


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.env = patch.dict(os.environ, {'AGENT_DB_PATH': self.directory.name+'/notes.sqlite3',
            'AGENT_ACCESS_TOKEN':'x'*32, 'FLOCI_ENDPOINT_URL':'https://s3.amazonaws.com',
            'FLOCI_BUCKET':'agentbroker-private'})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.mock = mock_aws()
        self.mock.start()
        self.addCleanup(self.mock.stop)
        self.s3 = boto3.client('s3', region_name='us-east-1', aws_access_key_id='test', aws_secret_access_key='test')
        self.s3.create_bucket(Bucket='agentbroker-private')
        self.client = app.app.test_client()
        self.headers = {'Authorization':'Bearer '+'x'*32}

    def test_private_and_encrypted_roundtrip(self):
        import io
        self.assertEqual(self.client.get('/storage/files').status_code, 401)
        result = self.client.post('/storage/files', data={'file':(io.BytesIO(b'private text'), 'note.txt')}, headers=self.headers)
        self.assertEqual(result.status_code, 201)
        identity = result.json['id']
        stored = self.s3.get_object(Bucket='agentbroker-private', Key='files/'+identity)['Body'].read()
        self.assertNotIn(b'private text', stored)
        self.assertEqual(self.client.get('/storage/files/'+identity, headers=self.headers).data,b'private text')
        self.assertEqual(self.client.get('/storage/files', headers=self.headers).json['ids'],[identity])

    def test_restore_after_local_database_loss(self):
        record = dict(id='original', goal='HR knowledge', output='A sourced note',
            sources=[dict(title='Source',url='https://example.org')], created_at='2026-10-01')
        app.save_knowledge(record)
        with app.db() as conn:
            conn.execute('DELETE FROM knowledge')
        self.assertEqual(self.client.post('/storage/sync',headers=self.headers).status_code,200)
        self.assertEqual(self.client.get('/knowledge',headers=self.headers).json[0]['id'],'original')
        self.client.post('/storage/sync',headers=self.headers)
        self.assertEqual(len(self.client.get('/knowledge',headers=self.headers).json),1)

    def test_outage_retains_local_note_and_reports_failure(self):
        with patch('floci_storage.Storage',side_effect=RuntimeError('offline')):
            app.save_knowledge(dict(id='kept',goal='topic',output='note',sources=[],created_at='now'))
            self.assertEqual(self.client.post('/storage/sync',headers=self.headers).status_code,503)
        self.assertEqual(self.client.get('/knowledge',headers=self.headers).json[0]['id'],'kept')

    def test_tampered_object_is_not_imported(self):
        self.s3.put_object(Bucket='agentbroker-private',Key='knowledge/bad.json',Body=b'bad ciphertext')
        self.assertEqual(self.client.post('/storage/sync',headers=self.headers).status_code,503)
        self.assertEqual(self.client.get('/knowledge',headers=self.headers).json,[])

    def test_size_limit_and_disabled(self):
        import io
        result=self.client.post('/storage/files',data={'file':(io.BytesIO(b'x'*1_000_001),'big')},headers=self.headers)
        self.assertEqual(result.status_code,413)
        with patch.dict(os.environ,{'FLOCI_ENDPOINT_URL':''}):
            self.assertEqual(self.client.get('/storage/status',headers=self.headers).json,dict(enabled=False,reachable=False))
