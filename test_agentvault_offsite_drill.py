import base64
import copy
import hashlib
import io
import os
import sys
import tempfile
from pathlib import Path
from contextlib import redirect_stdout
import unittest
import zipfile
from unittest.mock import patch
from cryptography.fernet import Fernet, InvalidToken
from agentvault_backup import seal_snapshot
from agentvault_offsite_drill import drill
import test_agentvault_backup as backup_tests


class OffsiteDrillTests(unittest.TestCase):
    def setUp(self):
        fixture = backup_tests.BackupTests(); fixture.setUp()
        self.key = fixture.master
        self.snapshot = fixture.snapshot
        self.snapshot['encryption_key'] = None

    def zip(self, snapshot):
        encrypted = seal_snapshot(snapshot, self.key)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            archive.writestr('agentvault-backup.fernet', encrypted)
            archive.writestr('agentvault-backup.sha256', hashlib.sha256(encrypted).hexdigest()+'  agentvault-backup.fernet\n')
        data = buffer.getvalue()
        return data, hashlib.sha256(data).hexdigest()

    def test_full_roundtrip_preserves_all_tables_without_network(self):
        self.snapshot['tables']['av_orders'] = [dict(reference='ref',vault_id='a'*32,provider_id='ORDER',amount='5.00',state='paid',created_at=1,granted_at=2)]
        self.snapshot['tables']['av_limits'] = [dict(bucket='save:1',count=2)]
        self.snapshot['tables']['av_audit'] = [dict(id='audit',vault_id='a'*32,event='test',created_at=1)]
        with patch('socket.socket',side_effect=AssertionError('network forbidden')):
            result = drill(*self.zip(self.snapshot),self.key)
        self.assertTrue(result['all_rows_identical'])
        self.assertTrue(result['temporary_database_removed'])
        self.assertEqual(result['archived_checkpoints_verified'],1)
        self.assertEqual(list(result['counts'].values()),[1]*5)
        self.assertFalse(result['production_database_accessed'])

    def test_wrong_key_transfer_corruption_and_tenant_corruption_fail(self):
        data, digest = self.zip(self.snapshot)
        with self.assertRaises(InvalidToken): drill(data,digest,Fernet.generate_key())
        with self.assertRaises(ValueError): drill(data+b'x',digest,self.key)
        self.snapshot['tables']['av_checkpoints'][0]['vault_id'] = 'b'*32
        with self.assertRaises(ValueError): drill(*self.zip(self.snapshot),self.key)

    def test_distinct_archive_and_checkpoint_keys_roundtrip(self):
        archive_key = Fernet.generate_key()
        self.assertNotEqual(archive_key, self.key)
        encrypted = seal_snapshot(self.snapshot, archive_key)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            archive.writestr('agentvault-backup.fernet', encrypted)
            archive.writestr('agentvault-backup.sha256', hashlib.sha256(encrypted).hexdigest()+'  agentvault-backup.fernet\n')
        data = buffer.getvalue()
        digest = hashlib.sha256(data).hexdigest()
        with patch('socket.socket', side_effect=AssertionError('network forbidden')):
            result = drill(data, digest, archive_key, checkpoint_key=self.key)
        self.assertEqual(result['archived_checkpoints_verified'], 1)
        self.assertTrue(result['all_rows_identical'])
        self.assertTrue(result['temporary_database_removed'])
        with self.assertRaises(InvalidToken):
            drill(data, digest, self.key, checkpoint_key=self.key)
        with self.assertRaises(InvalidToken):
            drill(data, digest, archive_key, checkpoint_key=Fernet.generate_key())

    def test_cli_reads_separate_keys_without_exposing_them(self):
        import agentvault_offsite_drill
        archive_key = Fernet.generate_key()
        encrypted = seal_snapshot(self.snapshot, archive_key)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            archive.writestr('agentvault-backup.fernet', encrypted)
            archive.writestr('agentvault-backup.sha256', hashlib.sha256(encrypted).hexdigest()+'  agentvault-backup.fernet\n')
        data = buffer.getvalue()
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)/'synthetic.zip'
            source.write_bytes(data)
            args = ['agentvault_offsite_drill.py', '--zip', str(source),
                    '--sha256', hashlib.sha256(data).hexdigest(),
                    '--key-from-environment', '--checkpoint-key-from-environment']
            env = {'AGENTVAULT_BACKUP_RECOVERY_KEY':archive_key.decode(),
                   'AGENTVAULT_KEY':self.key.decode()}
            output = io.StringIO()
            with patch.dict(os.environ, env, clear=True), patch.object(sys,'argv',args), \
                    patch('socket.socket',side_effect=AssertionError('network forbidden')), redirect_stdout(output):
                agentvault_offsite_drill.main()
            self.assertIn('"archived_checkpoints_verified": 1', output.getvalue())
            self.assertNotIn(archive_key.decode(), output.getvalue())
            self.assertNotIn(self.key.decode(), output.getvalue())

    def test_empty_snapshot_does_not_claim_checkpoint_restore(self):
        probe = copy.deepcopy(self.snapshot['tables']['av_checkpoints'][0])
        self.snapshot['tables'] = {name:[] for name in self.snapshot['tables']}
        result = drill(*self.zip(self.snapshot),self.key,probe=probe)
        self.assertEqual(result['archived_checkpoints_verified'],0)
        self.assertTrue(result['separate_synthetic_probe_verified'])
        self.assertTrue(result['temporary_database_removed'])


if __name__ == '__main__': unittest.main()
