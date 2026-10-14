"""Operator dashboard should remain authenticated and clearly synthetic."""
import os
import unittest
from unittest.mock import patch
import app as agent_app


class QueueDashboardTests(unittest.TestCase):
    def setUp(self):
        self.client = agent_app.app.test_client()

    def test_dashboard_is_protected(self):
        with patch.dict(os.environ, {"AGENT_ACCESS_TOKEN": "test-only-secret-123"}):
            response = self.client.get("/offers/jd-audit/operator-dashboard")
        self.assertEqual(response.status_code, 401)

    def test_demo_dashboard_renders_without_customer_data(self):
        with patch.dict(os.environ, {"AGENT_ACCESS_TOKEN": "test-only-secret-123"}):
            response = self.client.get("/offers/jd-audit/operator-dashboard",
                                       headers={"Authorization": "Bearer test-only-secret-123"})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"DEMO", response.data)
        self.assertIn(b"operator-queue-preview", response.data)
        self.assertNotIn(b"payment_token", response.data)


if __name__ == "__main__":
    unittest.main()
