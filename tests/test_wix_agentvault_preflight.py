"""Offline tests for Wix-AgentVault preflight (zero network calls)."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
import urllib.error

spec = importlib.util.spec_from_file_location(
    "probe", Path(__file__).resolve().parents[1] / "integrations" / "wix_agentvault_preflight.py"
)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)

class FakeResponse:
    status = 200
    def __init__(self, body): self.body = body
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, limit): return self.body

class WixAgentVaultPreflightTests(unittest.TestCase):
    @patch.object(probe.urllib.request, "urlopen")
    def test_health_schema_and_get(self, mock_open):
        mock_open.return_value = FakeResponse(
            b'{"status":"ok","service":"agentvault","durable_database":true,"recovery_verified":false}'
        )
        result = probe.check("/healthz")
        self.assertTrue(result["ready"])
        self.assertFalse(result["recovery_verified"])
        self.assertEqual(mock_open.call_args.args[0].get_method(), "GET")

    @patch.object(probe.urllib.request, "urlopen")
    def test_closed_sales_is_valid_readiness(self, mock_open):
        mock_open.return_value = FakeResponse(
            b'{"plans":[],"sales_enabled":false,"terms_version":"2026-10-24"}'
        )
        result = probe.check("/v1/plans")
        self.assertTrue(result["ready"])
        self.assertFalse(result["sales_enabled"])

    @patch.object(probe.urllib.request, "urlopen")
    def test_wrong_schema_fails(self, mock_open):
        mock_open.return_value = FakeResponse(b'{"status":"ok"}')
        self.assertFalse(probe.check("/healthz")["ready"])

    @patch.object(probe.urllib.request, "urlopen")
    def test_html_response_fails(self, mock_open):
        mock_open.return_value = FakeResponse(b"<html>Oops</html>")
        self.assertFalse(probe.check("/v1/plans")["ready"])

    @patch.object(probe.urllib.request, "urlopen")
    def test_network_error_fails_closed(self, mock_open):
        mock_open.side_effect = urllib.error.URLError("offline")
        self.assertEqual(probe.check("/healthz")["error"], "URLError")

if __name__ == "__main__":
    unittest.main()
