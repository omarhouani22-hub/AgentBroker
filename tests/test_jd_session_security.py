"""Regression checks for operator cookie security and browser-session write guard.

Uses temporary SQLite and Flask test client; no production services.
"""
import os
import tempfile
import unittest
from unittest.mock import patch

import app as agent_app


class OperatorSessionSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            "AGENT_ACCESS_TOKEN": "test-only-access-token-123",
            "AGENT_LOGIN_PASSWORD": "test-only-login-password-123",
            "AGENT_DB_PATH": os.path.join(self.temp.name, "sessions.sqlite3"),
        })
        self.env.start()
        self.client = agent_app.app.test_client()
        with agent_app._LOGIN_LOCK:
            agent_app._LOGIN_FAILURES.clear()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_login_cookie_is_httponly_samesite_and_no_store(self):
        result = self.client.post("/session/login", json={
            "secret": "test-only-login-password-123"})
        self.assertEqual(result.status_code, 200)
        cookie = result.headers.get("Set-Cookie", "")
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Strict", cookie)
        self.assertIn("Path=/", cookie)
        self.assertEqual(result.headers.get("Cache-Control"), "no-store")

    def test_cookie_only_write_requires_custom_header(self):
        self.client.post("/session/login", json={
            "secret": "test-only-login-password-123"})
        # Existing authenticated write endpoint; missing header must be denied
        # before endpoint validation or any model invocation.
        denied = self.client.post("/offers/jd-audit/draft", json={})
        self.assertEqual(denied.status_code, 401)
        # A valid custom header passes the authentication gate; empty payload
        # is rejected by input validation without invoking the model.
        accepted = self.client.post("/offers/jd-audit/draft", json={},
                                    headers={"X-AgentBroker-Request": "1"})
        self.assertNotEqual(accepted.status_code, 401)

    def test_anonymous_status_never_leaks_session_secret(self):
        response = self.client.get("/session/status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"authenticated": False})
        self.assertEqual(response.headers.get("Cache-Control"), "no-store")


if __name__ == "__main__":
    unittest.main()
