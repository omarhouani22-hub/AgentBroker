import os
import unittest
from unittest.mock import patch

import app


class JobDescriptionOfferTest(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()
        self.payload = {'title': 'HR Officer', 'description': 'Manage recruitment requests, coordinate interviews, maintain personnel files, prepare monthly workforce reports, and communicate with hiring managers. ' * 2}

    def test_public_offer_requires_configured_contact(self):
        with patch.dict(os.environ, {'SALES_CONTACT_EMAIL': 'omar@example.com',
                                    'JD_AUDIT_PAYMENT_URL': 'javascript:alert(1)'}, clear=False):
            response = self.client.get('/services/job-description-audit')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'mailto:omar@example.com', response.data)
        self.assertNotIn(b'javascript:alert', response.data)

    def test_draft_is_private_and_validated(self):
        self.assertEqual(self.client.post('/offers/jd-audit/draft', json=self.payload).status_code, 503)
        with patch.dict(os.environ, {'AGENT_ACCESS_TOKEN': 'test-access-token',
                                    'DEEPSEEK_API_KEY': 'fake-key'}):
            self.assertEqual(self.client.post('/offers/jd-audit/draft', json=self.payload).status_code, 401)
            headers = {'Authorization': 'Bearer test-access-token'}
            self.assertEqual(self.client.post('/offers/jd-audit/draft', json={'title': 'HR'}, headers=headers).status_code, 400)
            with patch('app.model_call', return_value={'content': 'Review draft. ' * 20}) as call:
                response = self.client.post('/offers/jd-audit/draft', json=self.payload, headers=headers)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.get_json()['human_review_required'])
            self.assertIn('HR Officer', call.call_args.args[0][1]['content'])


if __name__ == '__main__':
    unittest.main()
