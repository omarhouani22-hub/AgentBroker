"""Browser-session integration checks for the synthetic JD operator queue.

All requests use Flask's in-memory test client and a temporary SQLite file.
No external service, model invocation, payment, or customer order.
"""
import os
import tempfile
import unittest
from unittest.mock import patch

import app as agent_app


class JDOperatorBrowserSessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.settings = patch.dict(os.environ, {
            "AGENT_ACCESS_TOKEN": "test-only-token-not-for-production",
            "AGENT_LOGIN_PASSWORD": "test-only-password-not-for-production",
            "AGENT_DB_PATH": os.path.join(self.temp.name, "sessions.sqlite3"),
        })
        self.settings.start()
        self.client = agent_app.app.test_client()
        with agent_app._LOGIN_LOCK:
            agent_app._LOGIN_FAILURES.clear()

    def tearDown(self):
        self.settings.stop()
        self.temp.cleanup()

    def test_login_queue_and_logout(self):
        anonymous = self.client.get("/offers/jd-audit/operator-dashboard")
        self.assertEqual(anonymous.status_code, 401)
        login = self.client.post("/session/login", json={
            "secret": "test-only-password-not-for-production"
        })
        self.assertEqual(login.status_code, 200)
        self.assertTrue(login.get_json()["authenticated"])
        self.assertTrue(self.client.get("/session/status").get_json()["authenticated"])
        dashboard = self.client.get("/offers/jd-audit/operator-dashboard")
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn(b"DEMO", dashboard.data)
        queue = self.client.get("/offers/jd-audit/operator-queue-preview")
        self.assertEqual(queue.status_code, 200)
        payload = queue.get_json()
        self.assertEqual(payload["mode"], "synthetic_demo_only")
        self.assertFalse(payload["live_orders_connected"])
        self.assertFalse(payload["payment_enabled"])
        self.assertEqual(payload["total"], 3)
        self.assertTrue(all(order["id"].startswith("DEMO-") for order in payload["orders"]))
        logout = self.client.post("/session/logout")
        self.assertEqual(logout.status_code, 200)
        self.assertFalse(self.client.get("/session/status").get_json()["authenticated"])
        self.assertEqual(self.client.get("/offers/jd-audit/operator-dashboard").status_code, 401)

    def test_wrong_password_never_authorizes(self):
        self.assertEqual(self.client.post("/session/login", json={
            "secret": "incorrect-password"
        }).status_code, 401)
        self.assertEqual(self.client.get("/offers/jd-audit/operator-queue-preview").status_code, 401)


if __name__ == "__main__":
    unittest.main()
