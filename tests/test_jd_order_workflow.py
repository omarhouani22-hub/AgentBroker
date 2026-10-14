"""Deterministic safety tests for future JD audit order processing."""
import unittest
from jd_order_workflow import OrderStatus as S, next_status


class OrderWorkflowTests(unittest.TestCase):
    def test_happy_path_requires_all_approvals(self):
        state = next_status(S.NEW, S.PAYMENT_PENDING)
        state = next_status(state, S.PAID, payment_verified=True)
        state = next_status(state, S.IN_REVIEW)
        state = next_status(state, S.READY, human_approved=True)
        self.assertEqual(next_status(state, S.DELIVERED, delivery_confirmed=True), S.DELIVERED)

    def test_cannot_fake_payment(self):
        with self.assertRaises(ValueError):
            next_status(S.PAYMENT_PENDING, S.PAID)
        with self.assertRaises(ValueError):
            next_status(S.NEW, S.PAID, payment_verified=True)

    def test_cannot_skip_human_review_or_delivery(self):
        for current, target, flags in (
            (S.IN_REVIEW, S.READY, {}),
            (S.READY, S.DELIVERED, {}),
            (S.PAID, S.DELIVERED, {"delivery_confirmed": True}),
        ):
            with self.subTest(current=current, target=target), self.assertRaises(ValueError):
                next_status(current, target, **flags)

    def test_terminal_statuses(self):
        for state in (S.CANCELLED, S.REFUNDED):
            with self.assertRaises(ValueError):
                next_status(state, S.NEW)


if __name__ == "__main__":
    unittest.main()
