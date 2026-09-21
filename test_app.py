import os
import json
import tempfile
import unittest
from unittest.mock import patch

import app


class BrowserPageTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        env = patch.dict(os.environ, {'AGENT_DB_PATH': os.path.join(directory.name, 'test.sqlite3')})
        env.start()
        self.addCleanup(env.stop)
        self.client = app.app.test_client()

    def test_home_is_browser_page(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/html', response.content_type)
        self.assertIn(b'<form id="run-form">', response.data)
        self.assertIn(b"fetch('/runs'", response.data)

    @patch.dict(os.environ, {'AGENT_ACCESS_TOKEN': 'x' * 32, 'DEEPSEEK_API_KEY': 'test-key'})
    @patch.dict(os.environ, {'TAVILY_API_KEY': 'search-key'})
    @patch('app.search_web', return_value=[{'title': 'Source', 'url': 'https://example.com', 'content': 'Evidence'}])
    @patch('app.model_call', return_value={'content': 'A grounded note [S1]'})
    @patch('app.save_knowledge')
    @patch('app.save')
    def test_browser_api_path_returns_research(self, _save, _save_knowledge, _model_call, _search_web):
        response = self.client.post(
            '/runs', json={'goal': 'AI in recruitment'},
            headers={'Authorization': 'Bearer ' + 'x' * 32})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['output'], 'A grounded note [S1]')
        self.assertEqual(response.get_json()['sources'][0]['url'], 'https://example.com')

    @patch.dict(os.environ, {'AGENT_ACCESS_TOKEN': 'x' * 32, 'DEEPSEEK_API_KEY': 'test-key'}, clear=False)
    def test_research_requires_search_key(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('TAVILY_API_KEY', None)
            response = self.client.post(
                '/runs', json={'goal': 'AI in recruitment'},
                headers={'Authorization': 'Bearer ' + 'x' * 32})
        self.assertEqual(response.status_code, 503)
        self.assertIn('TAVILY_API_KEY', response.get_json()['error'])

    @patch.dict(os.environ, {'AGENT_ACCESS_TOKEN': 'x' * 32})
    def test_knowledge_is_saved_and_exported(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
                os.environ, {'AGENT_DB_PATH': os.path.join(directory, 'test.sqlite3')}):
            record = {
                'id': 'note-1', 'goal': 'AI in recruitment', 'output': 'Grounded note [S1]',
                'sources': [{'title': 'Source', 'url': 'https://example.com', 'content': 'Evidence'}],
                'created_at': '2026-09-21T00:00:00+00:00'
            }
            app.save_knowledge(record)
            headers = {'Authorization': 'Bearer ' + 'x' * 32}
            listed = self.client.get('/knowledge', headers=headers)
            exported = self.client.get('/knowledge/export', headers=headers)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.get_json()[0]['id'], 'note-1')
        self.assertEqual(json.loads(exported.data)[0]['topic'], 'AI in recruitment')
        self.assertIn('attachment;', exported.headers['Content-Disposition'])


if __name__ == '__main__':
    unittest.main()
