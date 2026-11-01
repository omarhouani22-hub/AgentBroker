import contextlib
import io
import unittest
from unittest.mock import patch
from agentvault_ops import app, payment_check
from agentvault_paypal import PaymentError


class PaymentPreflightTests(unittest.TestCase):
    def run_check(self, result, expected=''):
        with patch.dict(app.config, {'PUBLIC_ORIGIN':'https://vault.example',
                                     'PAYPAL_MERCHANT_ID':expected}):
            with patch('agentvault_paypal.PayPalOrders.create_order', return_value=result), \
                 patch('agentvault_paypal.PayPalOrders.capture_order') as capture:
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    merchant=payment_check()
                capture.assert_not_called()
                self.assertNotIn('secret-approval-link',output.getvalue())
                return merchant

    def test_identifies_merchant_without_capture_or_logging_provider_response(self):
        result={'status':'CREATED','purchase_units':[{'payee':{'merchant_id':'ABCDEFGH12345'}}],
                'links':[{'href':'secret-approval-link'}]}
        self.assertEqual(self.run_check(result), 'ABCDEFGH12345')

    def test_refuses_incomplete_or_wrong_merchant(self):
        for result,expected in [({'status':'CREATED','purchase_units':[]},''),
                                ({'status':'COMPLETED','purchase_units':[{'payee':{'merchant_id':'ABCDEFGH12345'}}]},''),
                                ({'status':'CREATED','purchase_units':[{'payee':{'merchant_id':'ABCDEFGH12345'}}]},'OTHER12345')]:
            with self.assertRaises(PaymentError): self.run_check(result,expected)


if __name__=='__main__': unittest.main()
