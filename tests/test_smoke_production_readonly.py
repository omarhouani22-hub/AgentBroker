"""Offline tests for the read-only production smoke checker."""
import unittest
from unittest.mock import patch
from scripts.smoke_production_readonly import run


class SmokeTests(unittest.TestCase):
    def test_expected_protection_and_health(self):
        with patch("scripts.smoke_production_readonly.request_status",
                   side_effect=[(200, b"ok"), (401, b""), (401, b"")]) as req:
            run("https://example.com", attempts=1, wait=0)
        self.assertEqual(req.call_count, 3)

    def test_public_operator_dashboard_is_failure(self):
        with patch("scripts.smoke_production_readonly.request_status",
                   side_effect=[(200, b"ok"), (200, b""), (401, b"")]):
            with self.assertRaises(RuntimeError):
                run("https://example.com", attempts=1, wait=0)

    def test_misconfigured_auth_is_failure(self):
        with patch("scripts.smoke_production_readonly.request_status",
                   side_effect=[(200, b"ok"), (503, b""), (401, b"")]):
            with self.assertRaises(RuntimeError):
                run("https://example.com", attempts=1, wait=0)

    def test_rejects_non_https_and_credentials(self):
        for url in ("http://example.com", "https://user:pass@example.com"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                run(url, attempts=1, wait=0)


if __name__ == "__main__":
    unittest.main()
