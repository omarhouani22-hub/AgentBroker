"""End-to-end in-memory JD order lifecycle, no real payments or customer data."""
import sqlite3
import unittest
from uuid import uuid4

from jd_order_sqlite_adapter import JDOrderStore
from jd_order_queue import order_queue_summary


class FullLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        self.store = JDOrderStore(self.connection)
        self.order_id = str(uuid4())
        self.store.create(self.order_id, now="2026-10-14T00:00:00+00:00")

    def tearDown(self):
        self.connection.close()

    def test_mocked_full_lifecycle_and_queue(self):
        events = (
            ("payment_pending", "system", {}),
            ("paid", "payment_webhook", {"payment_verified": True}),
            ("in_review", "operator", {}),
            ("ready_for_delivery", "operator", {"human_approved": True}),
            ("delivered", "operator", {"delivery_confirmed": True}),
        )
        for number, (status, actor, flags) in enumerate(events, start=1):
            updated = self.store.transition(
                self.order_id, status, event_key=f"synthetic-{number}",
                actor_type=actor, **flags)
            self.assertEqual(updated["version"], number)
        summary = order_queue_summary([self.store.get(self.order_id)])
        self.assertEqual(summary["counts"]["delivered"], 1)
        self.assertEqual(summary["total"], 1)
        self.assertEqual(self.connection.execute(
            "SELECT COUNT(*) FROM jd_order_events").fetchone()[0], 5)

    def test_rejected_invalid_transition_preserves_state(self):
        with self.assertRaises(ValueError):
            self.store.transition(self.order_id, "delivered",
                                  event_key="skip-to-delivery",
                                  actor_type="operator", delivery_confirmed=True)
        self.assertEqual(self.store.get(self.order_id)["status"], "new")
        self.assertEqual(self.connection.execute(
            "SELECT COUNT(*) FROM jd_order_events").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
