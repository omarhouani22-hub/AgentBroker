import unittest
from agentvault_paypal import PayPalOrders


class PayPalAdapterTests(unittest.TestCase):
    def test_sandbox_default(self):
        p = PayPalOrders("id", "secret", "sandbox")
        self.assertEqual(p.base, "https://api-m.sandbox.paypal.com")

    def test_cannot_verify_browser_redirect_as_payment(self):
        self.assertFalse(PayPalOrders.verify_capture({"status": "COMPLETED"}, "a", "3.00"))

    def test_only_exact_server_verified_capture(self):
        result = {"status": "COMPLETED", "purchase_units": [
            {"reference_id": "ref-1", "payments": {"captures": [
                {"status": "COMPLETED", "amount": {"currency_code": "USD", "value": "3.00"}}]}}]}
        self.assertTrue(PayPalOrders.verify_capture(result, "ref-1", "3.00"))
        self.assertFalse(PayPalOrders.verify_capture(result, "ref-2", "3.00"))
        self.assertFalse(PayPalOrders.verify_capture(result, "ref-1", "9.00"))

    def test_reject_invalid_ids_without_network(self):
        p = PayPalOrders("id", "secret")
        with self.assertRaises(ValueError):
            p.capture_order("../invalid")


if __name__ == "__main__":
    unittest.main()
