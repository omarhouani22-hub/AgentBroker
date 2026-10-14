import unittest
from jd_order_postgres_contract import (
    READ_ORDER_FOR_UPDATE, UPDATE_ORDER_VERSIONED,
    INSERT_ORDER_EVENT, transition_plan,
)


class PostgresContractTests(unittest.TestCase):
    def test_sql_uses_parameters_and_locking(self):
        self.assertIn("FOR UPDATE", READ_ORDER_FOR_UPDATE)
        self.assertIn("version = %s", UPDATE_ORDER_VERSIONED)
        self.assertIn("RETURNING id, status, version", UPDATE_ORDER_VERSIONED)
        self.assertIn("VALUES (%s, %s, %s, %s, %s)", INSERT_ORDER_EVENT)
        self.assertNotIn("{", UPDATE_ORDER_VERSIONED)

    def test_requires_appropriate_actors(self):
        with self.assertRaises(ValueError):
            transition_plan("payment_pending", "paid", actor_type="operator",
                            event_key="evt-1", payment_verified=True)
        with self.assertRaises(ValueError):
            transition_plan("in_review", "ready_for_delivery",
                            actor_type="system", event_key="evt-2", human_approved=True)
        plan = transition_plan("payment_pending", "paid",
                               actor_type="payment_webhook",
                               event_key="evt-3", payment_verified=True)
        self.assertEqual(plan["target_status"], "paid")

    def test_cannot_skip_states(self):
        with self.assertRaises(ValueError):
            transition_plan("new", "delivered", actor_type="operator",
                            event_key="evt-4", delivery_confirmed=True)


if __name__ == "__main__":
    unittest.main()
