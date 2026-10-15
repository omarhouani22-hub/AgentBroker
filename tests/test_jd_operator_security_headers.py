"""Security response headers for JD operator-only pages."""
import os
import tempfile
import unittest
from unittest.mock import patch
import app as agent_app


class OperatorHeaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            "AGENT_ACCESS_TOKEN": "test-operator-token-123",
            "AGENT_DB_PATH": os.path.join(self.temp.name, "agent.sqlite3"),
        })
        self.env.start()
        self.client = agent_app.app.test_client()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_protected_operator_pages_have_no_store_and_no_frame(self):
        for path in (
            "/offers/jd-audit/operator-dashboard",
            "/offers/jd-audit/operator-queue-preview",
        ):
            with self.subTest(path=path):
                response = self.client.get(path, headers={
                    "Authorization": "Bearer test-operator-token-123"})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers.get("Cache-Control"), "no-store, private")
                self.assertEqual(response.headers.get("X-Frame-Options"), "DENY")
                self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")
                self.assertEqual(response.headers.get("Referrer-Policy"), "no-referrer")

    def test_denied_responses_are_not_cached(self):
        response = self.client.get("/offers/jd-audit/operator-dashboard")
        self.assertEqual(response.status_code, 401)
        self.assertIn("no-store", response.headers.get("Cache-Control", ""))


if __name__ == "__main__":
    unittest.main()
