"""Local-only transactional JD order adapter tests."""
import sqlite3
import unittest
from uuid import uuid4

from jd_order_sqlite_adapter import JDOrderStore


class JDOrderAdapterTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        self.store = JDOrderStore(self.connection)
        self.order_id = str(uuid4())
        self.store.create(self.order_id, now="2026-10-14T00:00:00+00:00")

    def tearDown(self):
        self.connection.close()

    def test_transactional_happy_path(self):
        self.store.transition(self.order_id, "payment_pending",
                              event_key="evt-start", actor_type="system")
        self.store.transition(self.order_id, "paid", event_key="evt-paid",
                              actor_type="payment_webhook", payment_verified=True)
        self.store.transition(self.order_id, "in_review",
                              event_key="evt-review", actor_type="operator")
        self.store.transition(self.order_id, "ready_for_delivery",
                              event_key="evt-ready", actor_type="operator",
                              human_approved=True)
        self.assertEqual(self.store.get(self.order_id)["version"], 4)

    def test_failed_payment_does_not_modify_order(self):
        self.store.transition(self.order_id, "payment_pending",
                              event_key="evt-start", actor_type="system")
        with self.assertRaises(ValueError):
            self.store.transition(self.order_id, "paid", event_key="evt-fake",
                                  actor_type="payment_webhook")
        self.assertEqual(self.store.get(self.order_id)["status"], "payment_pending")

    def test_actor_cannot_self_attest_payment_or_approval(self):
        self.store.transition(self.order_id, "payment_pending",
                              event_key="evt-start", actor_type="system")
        with self.assertRaises(ValueError):
            self.store.transition(self.order_id, "paid",
                                  event_key="evt-fake-operator", actor_type="operator",
                                  payment_verified=True)
        self.assertEqual(self.store.get(self.order_id)["status"], "payment_pending")
        self.store.transition(self.order_id, "paid", event_key="evt-paid",
                              actor_type="payment_webhook", payment_verified=True)
        self.store.transition(self.order_id, "in_review",
                              event_key="evt-review", actor_type="operator")
        with self.assertRaises(ValueError):
            self.store.transition(self.order_id, "ready_for_delivery",
                                  event_key="evt-fake-approval", actor_type="system",
                                  human_approved=True)
        self.assertEqual(self.store.get(self.order_id)["status"], "in_review")

    def test_duplicate_event_rolls_back(self):
        self.store.transition(self.order_id, "payment_pending",
                              event_key="evt-duplicate", actor_type="system")
        before = self.store.get(self.order_id)
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.transition(self.order_id, "cancelled",
                                  event_key="evt-duplicate", actor_type="operator")
        self.assertEqual(self.store.get(self.order_id), before)
        self.assertEqual(self.connection.execute(
            "SELECT COUNT(*) FROM jd_order_events").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
