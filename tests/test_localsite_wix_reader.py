import json
import unittest
from unittest.mock import patch

from integrations.localsite_wix_reader import fetch_wix_inbox, register_routes
from flask import Flask


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return b""

class WixReaderTests(unittest.TestCase):
    def test_missing_credentials_fails_closed(self):
        with patch.dict("os.environ", {"WIX_API_TOKEN": ""}):
            with self.assertRaises(RuntimeError):
                fetch_wix_inbox()

    def test_mock_wix_response_drafts_without_sending(self):
        response = {"submissions": [{"id": "lead-1", "submissions": {
            "form_field_5d13": "Example Plumbing",
            "form_field_ad8e": "Need a site"
        }}]}
        with patch.dict("os.environ", {"WIX_API_TOKEN": "test-token"}):
            with patch("integrations.localsite_wix_reader.urlopen") as call:
                call.return_value.__enter__.return_value = response
                with patch("integrations.localsite_wix_reader.json.load", return_value=response):
                    inquiries = fetch_wix_inbox()
        self.assertEqual(len(inquiries), 1)
        self.assertTrue(inquiries[0]["owner_approval_required"])
        self.assertIn("proposal", inquiries[0]["reply_draft"])
        self.assertEqual(call.call_count, 1)

    def test_endpoint_is_read_only(self):
        app = Flask(__name__)
        register_routes(app)
        with patch("integrations.localsite_wix_reader.fetch_wix_inbox", return_value=[]):
            result = app.test_client().get("/clara/localsite/inquiries")
        self.assertEqual(result.status_code, 200)
        self.assertFalse(result.json["outbound_enabled"])


if __name__ == "__main__":
    unittest.main()
