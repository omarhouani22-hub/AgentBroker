import base64
import copy
import hashlib
import io
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

    def test_empty_snapshot_does_not_claim_checkpoint_restore(self):
        probe = copy.deepcopy(self.snapshot['tables']['av_checkpoints'][0])
        self.snapshot['tables'] = {name:[] for name in self.snapshot['tables']}
        result = drill(*self.zip(self.snapshot),self.key,probe=probe)
        self.assertEqual(result['archived_checkpoints_verified'],0)
        self.assertTrue(result['separate_synthetic_probe_verified'])
        self.assertTrue(result['temporary_database_removed'])


if __name__ == '__main__': unittest.main()
