"""Mocked DB-API tests; these do not claim a real Postgres integration."""
import unittest
from unittest.mock import Mock
from jd_order_postgres_executor import (
    execute_transition, OrderNotFound, OrderConflict,
)


class ExecutorTests(unittest.TestCase):
    def setUp(self):
        self.connection = Mock(autocommit=False)
        self.cursor = self.connection.cursor.return_value

    def test_success_commits_state_and_event(self):
        self.cursor.fetchone.side_effect = [
            ("order-1", "payment_pending", 2), ("order-1", "paid", 3)]
        result = execute_transition(
            self.connection, "order-1", "paid", actor_type="payment_webhook",
            event_key="payment-event-1", payment_verified=True)
        self.assertEqual(result["status"], "paid")
        self.assertEqual(result["version"], 3)
        self.assertEqual(self.cursor.execute.call_count, 3)
        self.connection.commit.assert_called_once()
        self.connection.rollback.assert_not_called()
        self.cursor.close.assert_called_once()

    def test_missing_order_rolls_back(self):
        self.cursor.fetchone.return_value = None
        with self.assertRaises(OrderNotFound):
            execute_transition(self.connection, "missing", "payment_pending",
                               actor_type="system", event_key="evt-1")
        self.connection.rollback.assert_called_once()
        self.connection.commit.assert_not_called()

    def test_fake_payment_rolls_back(self):
        self.cursor.fetchone.return_value = ("order-1", "payment_pending", 0)
        with self.assertRaises(ValueError):
            execute_transition(self.connection, "order-1", "paid",
                               actor_type="operator", event_key="evt-2",
                               payment_verified=True)
        self.assertEqual(self.cursor.execute.call_count, 1)
        self.connection.rollback.assert_called_once()

    def test_duplicate_event_failure_rolls_back(self):
        self.cursor.fetchone.side_effect = [
            ("order-1", "new", 0), ("order-1", "payment_pending", 1)]
        self.cursor.execute.side_effect = [None, None, RuntimeError("unique violation")]
        with self.assertRaises(RuntimeError):
            execute_transition(self.connection, "order-1", "payment_pending",
                               actor_type="system", event_key="evt-dup")
        self.connection.rollback.assert_called_once()
        self.connection.commit.assert_not_called()

    def test_version_conflict_rolls_back(self):
        self.cursor.fetchone.side_effect = [("order-1", "new", 0), None]
        with self.assertRaises(OrderConflict):
            execute_transition(self.connection, "order-1", "payment_pending",
                               actor_type="system", event_key="evt-conflict")
        self.connection.rollback.assert_called_once()

    def test_autocommit_not_allowed(self):
        self.connection.autocommit = True
        with self.assertRaises(ValueError):
            execute_transition(self.connection, "order-1", "payment_pending",
                               actor_type="system", event_key="evt-3")
        self.connection.cursor.assert_not_called()


if __name__ == "__main__":
    unittest.main()
