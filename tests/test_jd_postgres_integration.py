"""Integration checks against disposable PostgreSQL in GitHub Actions only.

No production credentials or customer data. Requires TEST_JD_POSTGRES_DSN.
"""
import os
import unittest
from uuid import uuid4

try:
    import psycopg
except ImportError:
    psycopg = None

from jd_order_postgres_executor import execute_transition, OrderNotFound


@unittest.skipUnless(psycopg is not None and os.getenv("TEST_JD_POSTGRES_DSN"),
                     "Requires disposable PostgreSQL and TEST_JD_POSTGRES_DSN")
class PostgresIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.conn = psycopg.connect(os.environ["TEST_JD_POSTGRES_DSN"], autocommit=False)
        self.order_id = uuid4()
        with self.conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO agentbroker_private.jd_orders(id,status) VALUES (%s,%s)",
                (self.order_id, "new"))
        self.conn.commit()

    def tearDown(self):
        self.conn.rollback()
        with self.conn.cursor() as cursor:
            cursor.execute("DELETE FROM agentbroker_private.jd_order_events WHERE order_id=%s",
                           (self.order_id,))
            cursor.execute("DELETE FROM agentbroker_private.jd_orders WHERE id=%s",
                           (self.order_id,))
        self.conn.commit()
        self.conn.close()

    def test_atomic_lifecycle_and_event_history(self):
        stages = [
            ("payment_pending", "system", {}),
            ("paid", "payment_webhook", {"payment_verified": True}),
            ("in_review", "operator", {}),
            ("ready_for_delivery", "operator", {"human_approved": True}),
            ("delivered", "operator", {"delivery_confirmed": True}),
        ]
        for index, (target, actor, flags) in enumerate(stages, 1):
            updated = execute_transition(
                self.conn, self.order_id, target, actor_type=actor,
                event_key=f"test-{self.order_id}-{index}", **flags)
            self.assertEqual(updated["status"], target)
            self.assertEqual(updated["version"], index)
        with self.conn.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM agentbroker_private.jd_order_events WHERE order_id=%s",
                (self.order_id,))
            self.assertEqual(cursor.fetchone()[0], 5)

    def test_rejected_transition_rolls_back(self):
        with self.assertRaises(ValueError):
            execute_transition(
                self.conn, self.order_id, "paid", actor_type="operator",
                event_key=f"bad-{self.order_id}", payment_verified=True)
        with self.conn.cursor() as cursor:
            cursor.execute(
                "SELECT status,version FROM agentbroker_private.jd_orders WHERE id=%s",
                (self.order_id,))
            self.assertEqual(cursor.fetchone(), ("new", 0))
            cursor.execute(
                "SELECT COUNT(*) FROM agentbroker_private.jd_order_events WHERE order_id=%s",
                (self.order_id,))
            self.assertEqual(cursor.fetchone()[0], 0)

    def test_duplicate_event_key_rolls_back_state(self):
        key = f"duplicate-{self.order_id}"
        execute_transition(
            self.conn, self.order_id, "payment_pending",
            actor_type="system", event_key=key)
        with self.assertRaises(psycopg.errors.UniqueViolation):
            execute_transition(
                self.conn, self.order_id, "cancelled",
                actor_type="operator", event_key=key)
        with self.conn.cursor() as cursor:
            cursor.execute(
                "SELECT status,version FROM agentbroker_private.jd_orders WHERE id=%s",
                (self.order_id,))
            self.assertEqual(cursor.fetchone(), ("payment_pending", 1))


if __name__ == "__main__":
    unittest.main()
