import base64
import copy
import hashlib
import io
import unittest
import zipfile
from unittest.mock import patch
from cryptography.fernet import Fernet, InvalidToken
from agentvault_backup import seal_snapshot
from agentvault_offsite_drill import drill, main, verdict, CHECKPOINTS_RECOVERED, ROWS_ONLY, EMPTY
import json, os, sys, tempfile
from contextlib import redirect_stdout
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
        self.assertEqual(result['recovery_verdict'],CHECKPOINTS_RECOVERED)
        self.assertTrue(result['customer_data_recovery_verified'])
        self.assertLess(result['snapshot_age_hours'],1)
        self.assertRegex(result['snapshot_sealed_at'],r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$')

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
        # A passing synthetic probe must never upgrade an empty archive.
        self.assertEqual(result['recovery_verdict'],EMPTY)
        self.assertFalse(result['customer_data_recovery_verified'])

    def test_rows_without_checkpoints_are_not_customer_recovery(self):
        self.snapshot['tables']['av_checkpoints'] = []
        result = drill(*self.zip(self.snapshot),self.key)
        self.assertEqual(result['counts']['av_vaults'],1)
        self.assertEqual(result['recovery_verdict'],ROWS_ONLY)
        self.assertFalse(result['customer_data_recovery_verified'])

    def test_verdict_requires_every_archived_checkpoint_verified(self):
        self.assertEqual(verdict({'av_vaults':1,'av_checkpoints':2},1),ROWS_ONLY)
        self.assertEqual(verdict({'av_vaults':0,'av_checkpoints':0},0),EMPTY)
        self.assertEqual(verdict({'av_vaults':1,'av_checkpoints':1},1),CHECKPOINTS_RECOVERED)

    def run_cli(self, data, digest, *extra):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder,'backup.zip')
            with open(path,'wb') as handle: handle.write(data)
            argv = ['drill','--zip',path,'--sha256',digest,'--key-from-environment',*extra]
            out = io.StringIO()
            with patch.object(sys,'argv',argv), patch.dict(os.environ,{'AGENTVAULT_KEY':self.key.decode()}), redirect_stdout(out):
                try: main(); code = 0
                except SystemExit as exit: code = exit.code
        line = [x for x in out.getvalue().splitlines() if x.startswith('AGENTVAULT_OFFSITE_DRILL ')][0]
        return code, json.loads(line.split(' ',1)[1])

    def test_cli_fails_closed_on_empty_archive_unless_explicitly_allowed(self):
        self.snapshot['tables'] = {name:[] for name in self.snapshot['tables']}
        data, digest = self.zip(self.snapshot)
        code, evidence = self.run_cli(data,digest)
        self.assertIn(EMPTY,str(code))
        self.assertFalse(evidence['customer_data_recovery_verified'])
        code, evidence = self.run_cli(data,digest,'--allow-empty')
        self.assertEqual(code,0)

    def test_cli_succeeds_when_archived_checkpoint_recovered(self):
        code, evidence = self.run_cli(*self.zip(self.snapshot))
        self.assertEqual(code,0)
        self.assertTrue(evidence['customer_data_recovery_verified'])


if __name__ == '__main__': unittest.main()
