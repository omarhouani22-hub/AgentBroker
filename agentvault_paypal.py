"""PayPal Orders v2 adapter for AgentVault (server-side, sandbox by default).

No payment is initiated on import. Merchant credentials must be configured as
environment secrets. Never grant storage based on a browser redirect alone.
"""
import base64
import json
import os
import re
from urllib.request import Request, urlopen
from urllib.error import HTTPError


class PaymentError(Exception):
    pass


class PayPalOrders:
    def __init__(self, client_id=None, client_secret=None, environment=None):
        self.client_id = client_id if client_id is not None else os.getenv("PAYPAL_CLIENT_ID", "")
        self.client_secret = client_secret if client_secret is not None else os.getenv("PAYPAL_CLIENT_SECRET", "")
        self.environment = environment or os.getenv("PAYPAL_ENVIRONMENT", "sandbox")
        if self.environment not in ("sandbox", "live"):
            raise ValueError("Invalid PayPal environment")
        self.base = ("https://api-m.paypal.com" if self.environment == "live"
                     else "https://api-m.sandbox.paypal.com")

    def _request(self, path, payload=None, token=None, headers=None):
        if not self.client_id or not self.client_secret:
            raise PaymentError("PayPal credentials not configured")
        data = json.dumps(payload).encode() if payload is not None else None
        h = dict(headers or {})
        if token:
            h["Authorization"] = "Bearer " + token
        if data is not None:
            h["Content-Type"] = "application/json"
        req = Request(self.base + path, data=data, headers=h,
                      method="POST" if data is not None else "GET")
        try:
            with urlopen(req, timeout=20) as response:
                return json.load(response)
        except (HTTPError, ValueError, OSError) as exc:
            raise PaymentError("PayPal request failed") from exc

    def access_token(self):
        raw = base64.b64encode((self.client_id + ":" + self.client_secret).encode()).decode()
        req = Request(self.base + "/v1/oauth2/token", data=b"grant_type=client_credentials",
                      headers={"Authorization": "Basic " + raw,
                               "Content-Type": "application/x-www-form-urlencoded"}, method="POST")
        try:
            with urlopen(req, timeout=20) as response:
                return json.load(response)["access_token"]
        except (HTTPError, KeyError, ValueError, OSError) as exc:
            raise PaymentError("PayPal authentication failed") from exc

    def create_order(self, order_reference, amount_usd, return_url, cancel_url):
        """Amount is server-controlled; caller must map plan IDs to fixed prices."""
        if not isinstance(order_reference, str) or not order_reference or len(order_reference) > 100:
            raise ValueError("Invalid order reference")
        if not isinstance(amount_usd, str) or not amount_usd.replace(".", "", 1).isdigit():
            raise ValueError("Invalid amount")
        cents = amount_usd.split(".")
        if len(cents) > 2 or (len(cents) == 2 and len(cents[1]) > 2) or float(amount_usd) <= 0:
            raise ValueError("Invalid amount")
        return self._request("/v2/checkout/orders", {
            "intent": "CAPTURE",
            "purchase_units": [{"reference_id": order_reference,
                                "amount": {"currency_code": "USD", "value": amount_usd}}],
            "payment_source": {"paypal": {"experience_context": {
                "return_url": return_url, "cancel_url": cancel_url,
                "user_action": "PAY_NOW"}}}},
            self.access_token(), {"PayPal-Request-Id": order_reference, "Prefer": "return=representation"})

    def capture_order(self, paypal_order_id):
        """Capture server-to-server; validate status, amount and reference before provisioning."""
        if not isinstance(paypal_order_id, str) or not paypal_order_id.isascii() or not paypal_order_id.isalnum() or len(paypal_order_id) > 64:
            raise ValueError("Invalid PayPal order ID")
        return self._request("/v2/checkout/orders/" + paypal_order_id + "/capture", {},
                             self.access_token(), {"PayPal-Request-Id": "capture-" + paypal_order_id,
                                                   "Prefer": "return=representation"})

    def get_order(self, paypal_order_id):
        """Reconcile an ambiguous capture without making a second charge request."""
        if not isinstance(paypal_order_id, str) or not re.fullmatch(r"[A-Z0-9]{1,36}", paypal_order_id):
            raise ValueError("Invalid PayPal order ID")
        return self._request("/v2/checkout/orders/" + paypal_order_id, token=self.access_token())

    @staticmethod
    def verify_capture(result, expected_reference, expected_amount):
        if result.get("status") != "COMPLETED":
            return False
        units = result.get("purchase_units", [])
        if len(units) != 1 or units[0].get("reference_id") != expected_reference:
            return False
        captures = units[0].get("payments", {}).get("captures", [])
        return (len(captures) == 1 and captures[0].get("status") == "COMPLETED"
                and captures[0].get("amount", {}).get("currency_code") == "USD"
                and captures[0].get("amount", {}).get("value") == expected_amount)
