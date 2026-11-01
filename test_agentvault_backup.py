import hashlib
import tempfile
import unittest
from pathlib import Path
from cryptography.fernet import Fernet, InvalidToken
from agentvault_backup import encode_snapshot,seal_snapshot,open_snapshot,restore_local,TABLES
from agentvault_service import create_app


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.master=Fernet.generate_key()
        self.recovery=Fernet.generate_key()
        self.vid='a'*32
        self.token='x'*40
        self.payload=b'independent-offsite-recovery'
        rows={table:[] for table in TABLES}
        rows['av_vaults']=[dict(id=self.vid,token_hash=hashlib.sha256(self.token.encode()).hexdigest(),created_at=1,
            expires_at=4102444800,version=1,quota_bytes=10485760,terms_version='operator-drill',deleted_at=0)]
        rows['av_checkpoints']=[dict(vault_id=self.vid,version=1,created_at=1,byte_count=len(self.payload),
            digest=hashlib.sha256(self.payload).hexdigest(),encrypted=Fernet(self.master).encrypt(self.vid.encode()+b'\0'+self.payload))]
        self.snapshot=encode_snapshot(rows,self.master.decode())

    def test_independent_key_and_database_restore_deliver_original_bytes(self):
        archive=seal_snapshot(self.snapshot,self.recovery)
        self.assertNotIn(self.master,archive)
        self.assertNotIn(self.payload,archive)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'restored.sqlite'
            result=restore_local(archive,self.recovery,path)
            self.assertEqual(result['counts']['av_checkpoints'],1)
            client=create_app({'TESTING':True,'DATABASE_URL':str(path),'ENCRYPTION_KEY':self.master.decode()}).test_client()
            response=client.get('/v1/checkpoint',headers={'X-Vault-Id':self.vid,'Authorization':'Bearer '+self.token})
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.data,self.payload)
            with self.assertRaises(FileExistsError):restore_local(archive,self.recovery,path)

    def test_wrong_key_tampering_and_tenant_mismatch_are_rejected(self):
        archive=seal_snapshot(self.snapshot,self.recovery)
        with self.assertRaises(InvalidToken):open_snapshot(archive,Fernet.generate_key())
        with self.assertRaises(InvalidToken):open_snapshot(archive[:-8]+b'xxxxxxxx',self.recovery)
        self.snapshot['tables']['av_checkpoints'][0]['vault_id']='b'*32
        with self.assertRaises(ValueError):open_snapshot(seal_snapshot(self.snapshot,self.recovery),self.recovery)

    def test_data_only_backup_does_not_claim_key_recovery(self):
        self.snapshot['encryption_key']=None
        with tempfile.TemporaryDirectory() as tmp:
            result=restore_local(seal_snapshot(self.snapshot,self.recovery),self.recovery,Path(tmp)/'restored.sqlite')
            self.assertFalse(result['checkpoint_integrity_verified'])
            self.assertEqual(result['counts']['av_checkpoints'],1)


if __name__=='__main__':unittest.main()
