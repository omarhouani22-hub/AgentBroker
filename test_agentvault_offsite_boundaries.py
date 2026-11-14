"""Regression tests for offsite archive input boundaries.

Synthetic inputs only. No production DB, credentials, or network access.
Run: python -m unittest -v test_agentvault_offsite_boundaries
"""
import hashlib
import io
import unittest
import zipfile
from unittest.mock import patch

from cryptography.fernet import Fernet
from agentvault_offsite_drill import drill


class OffsiteBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.key = Fernet.generate_key()

    def check(self, data, expected_error):
        digest = hashlib.sha256(data).hexdigest()
        with patch("socket.socket", side_effect=AssertionError("network forbidden")):
            with self.assertRaisesRegex(expected_error[0], expected_error[1]):
                drill(data, digest, self.key)

    def make_zip(self, members, compression=zipfile.ZIP_STORED):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", compression=compression, allowZip64=True) as z:
            for name, value in members:
                z.writestr(name, value)
        return stream.getvalue()

    def test_outer_zip_over_20_mib_rejected(self):
        data = b"x" * (20 * 1024 * 1024 + 1)
        self.check(data, (ValueError, "zip_too_large"))

    def test_inner_member_over_16_mib_rejected_even_if_compressed(self):
        data = self.make_zip(
            [("agentvault-backup.fernet", b"A" * (16 * 1024 * 1024 + 1)),
             ("agentvault-backup.sha256", b"placeholder")],
            compression=zipfile.ZIP_DEFLATED,
        )
        self.assertLess(len(data), 20 * 1024 * 1024)
        self.check(data, (ValueError, "archive_too_large"))

    def test_unexpected_extra_member_rejected(self):
        data = self.make_zip(
            [("agentvault-backup.fernet", b"dummy"),
             ("agentvault-backup.sha256", b"dummy"),
             ("unexpected.txt", b"dummy")])
        self.check(data, (ValueError, "unexpected_zip_contents"))

    def test_bad_inner_checksum_rejected(self):
        data = self.make_zip(
            [("agentvault-backup.fernet", b"dummy"),
             ("agentvault-backup.sha256", b"0" * 64 + b"  agentvault-backup.fernet\n")])
        self.check(data, (ValueError, "archive_digest_mismatch"))

    def test_malformed_zip_rejected(self):
        self.check(b"not a zip archive", (zipfile.BadZipFile, ".*"))


if __name__ == "__main__":
    unittest.main()
