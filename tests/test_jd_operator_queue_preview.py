"""Operator queue preview must stay protected and synthetic."""
import os
import unittest
from unittest.mock import patch
import app as agent_app


class OperatorQueuePreviewTests(unittest.TestCase):
    def setUp(self):
        self.client = agent_app.app.test_client()

    def test_requires_operator_token(self):
        with patch.dict(os.environ, {"AGENT_ACCESS_TOKEN": "test-only-secret-123"}):
            response = self.client.get("/offers/jd-audit/operator-queue-preview")
        self.assertEqual(response.status_code, 401)

    def test_authorized_queue_contains_demo_only(self):
        with patch.dict(os.environ, {"AGENT_ACCESS_TOKEN": "test-only-secret-123"}):
            response = self.client.get("/offers/jd-audit/operator-queue-preview",
                                       headers={"Authorization": "Bearer test-only-secret-123"})
        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertEqual(result["mode"], "synthetic_demo_only")
        self.assertFalse(result["live_orders_connected"])
        self.assertFalse(result["payment_enabled"])
        self.assertEqual(result["total"], 3)
        self.assertTrue(all(order["id"].startswith("DEMO-") for order in result["orders"]))


if __name__ == "__main__":
    unittest.main()
