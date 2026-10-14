import unittest
from jd_order_queue import order_queue_summary


class QueueTests(unittest.TestCase):
    def test_summary_excludes_sensitive_details(self):
        summary = order_queue_summary([
            {"id": "order-1", "status": "new", "version": 0,
             "updated_at": "2026-10-14T09:00:00Z", "email": "secret@example.com",
             "description": "Confidential job description", "payment_token": "secret"},
            {"id": "order-2", "status": "in_review", "version": 2,
             "updated_at": "2026-10-14T10:00:00Z"}
        ])
        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["counts"]["in_review"], 1)
        self.assertEqual(summary["orders"][0]["id"], "order-2")
        self.assertNotIn("email", summary["orders"][1])
        self.assertNotIn("description", summary["orders"][1])
        self.assertNotIn("payment_token", summary["orders"][1])

    def test_invalid_status_rejected(self):
        with self.assertRaises(ValueError):
            order_queue_summary([{"id": "1", "status": "made_up"}])


if __name__ == "__main__":
    unittest.main()
