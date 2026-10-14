"""Public intake preview must not invoke a model or persist an order."""
import unittest
from unittest.mock import patch
import app as agent_app


class IntakePreviewTests(unittest.TestCase):
    def setUp(self):
        self.client = agent_app.app.test_client()

    def test_valid_preview_is_free_and_stateless(self):
        with patch.object(agent_app, "model_call", side_effect=AssertionError("model must not run")):
            response = self.client.post("/offers/jd-audit/preview", json={
                "title": "HR specialist", "description": "Review employee requests and update internal records. " * 4
            })
        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertTrue(result["accepted"])
        self.assertFalse(result["stored"])
        self.assertFalse(result["payment_required"])
        self.assertFalse(result["model_called"])
        self.assertTrue(result["human_review_required"])

    def test_invalid_payloads_rejected(self):
        for payload in ({}, {"title": "HR", "description": "short"}, ["invalid"]):
            with self.subTest(payload=payload):
                response = self.client.post("/offers/jd-audit/preview", json=payload)
                self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
