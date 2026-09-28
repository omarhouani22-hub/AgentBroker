import os
import unittest
from unittest.mock import patch
import app
from hr_toolkit import MODULES


class HRToolkitTest(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()
        self.headers = {'Authorization': 'Bearer private-test-token'}
        self.data = {'module': 'onboarding', 'brief': 'Plan the first 90 days for a new operations coordinator in a 12-person company. They own scheduling and weekly reporting.'}

    def test_private_modules_and_validation(self):
        with patch.dict(os.environ, {'AGENT_ACCESS_TOKEN': 'private-test-token', 'DEEPSEEK_API_KEY': 'test-key'}):
            self.assertEqual(self.client.get('/hr/tools').status_code, 401)
            self.assertEqual(len(self.client.get('/hr/tools', headers=self.headers).get_json()['modules']), 12)
            self.assertEqual(self.client.post('/hr/draft', json={**self.data, 'module': 'unknown'}, headers=self.headers).status_code, 400)
            self.assertEqual(self.client.post('/hr/draft', json={**self.data, 'brief': 'short'}, headers=self.headers).status_code, 400)
            with patch('app.model_call', return_value={'content': 'Draft plan with 30, 60, and 90 day outcomes and human review. ' * 3}) as call:
                result = self.client.post('/hr/draft', json=self.data, headers=self.headers)
            self.assertEqual(result.status_code, 200)
            self.assertTrue(result.get_json()['human_review_required'])
            self.assertIn('12-person company', call.call_args.args[0][1]['content'])
            self.assertIn('Do not invent labor laws', call.call_args.args[0][0]['content'])
            self.assertNotIn('Word toolkit', str(MODULES))

    def test_incomplete_output_is_not_returned(self):
        with patch.dict(os.environ, {'AGENT_ACCESS_TOKEN': 'private-test-token', 'DEEPSEEK_API_KEY': 'test-key'}):
            with patch('app.model_call', return_value={'content': 'brief'}):
                result = self.client.post('/hr/draft', json=self.data, headers=self.headers)
        self.assertEqual(result.status_code, 502)


if __name__ == '__main__':
    unittest.main()
