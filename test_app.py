import os
import unittest
from unittest.mock import patch

import app


class BrowserPageTest(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()

    def test_home_is_browser_page(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/html', response.content_type)
        self.assertIn(b'<form id="run-form">', response.data)
        self.assertIn(b"fetch('/runs'", response.data)

    @patch.dict(os.environ, {'AGENT_ACCESS_TOKEN': 'x' * 32, 'DEEPSEEK_API_KEY': 'test-key'})
    @patch('app.model_call', return_value={'content': 'A usable result'})
    @patch('app.save')
    def test_browser_api_path_returns_result(self, _save, _model_call):
        response = self.client.post(
            '/runs', json={'goal': 'Prepare an HR offer'},
            headers={'Authorization': 'Bearer ' + 'x' * 32})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['output'], 'A usable result')


if __name__ == '__main__':
    unittest.main()
