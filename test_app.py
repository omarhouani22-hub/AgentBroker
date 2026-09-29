import os
import json
import tempfile
import unittest
import sqlite3
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

    @patch.dict(os.environ, {'AGENT_ACCESS_TOKEN': 'test-password-123'})
    def test_home_is_browser_page(self):
        self.assertEqual(self.client.get('/').status_code, 302)
        self.assertEqual(self.client.get('/login').status_code, 200)
        self.assertEqual(self.client.post('/login', data={'password': 'wrong'}).status_code, 200)
        signed_in = self.client.post('/login', data={'password': 'test-password-123'}, base_url='https://agent.example')
        self.assertEqual(signed_in.status_code, 302)
        self.assertIn('HttpOnly', signed_in.headers['Set-Cookie'])
        self.assertIn('Secure', signed_in.headers['Set-Cookie'])
        response = self.client.get('/', base_url='https://agent.example')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/html', response.content_type)
        self.assertIn(b'<form id="run-form">', response.data)
        self.assertIn(b"fetch('/runs'", response.data)
        self.assertNotIn(b'id="token"', response.data)
        self.assertNotIn(b"'Authorization': 'Bearer '", response.data)

    @patch.dict(os.environ, {'AGENT_ACCESS_TOKEN': 'test-password-123', 'DEEPSEEK_API_KEY': 'test-key',
                             'TAVILY_API_KEY': 'search-key'})
    @patch('app.search_web', return_value=[{'title': 'Source', 'url': 'https://example.com', 'content': 'Evidence'}])
    @patch('app.model_call', return_value={'content': 'A grounded note [S1]'})
    def test_browser_session_runs_without_exposing_token(self, _model_call, _search_web):
        self.client.post('/login', data={'password': 'test-password-123'}, base_url='https://agent.example')
        blocked = self.client.post('/runs', json={'goal': 'AI in recruitment'}, base_url='https://agent.example')
        self.assertEqual(blocked.status_code, 403)
        response = self.client.post('/runs', json={'goal': 'AI in recruitment'},
                                    base_url='https://agent.example', headers={'Origin': 'https://agent.example'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['output'], 'A grounded note [S1]')

    def test_health_repairs_missing_storage_schema(self):
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()['ok'])
        with sqlite3.connect(os.environ['AGENT_DB_PATH']) as conn:
            self.assertEqual(conn.execute("SELECT name FROM sqlite_master WHERE name='knowledge'").fetchone()[0], 'knowledge')

    def test_health_reports_storage_failure(self):
        with patch('app.db', side_effect=sqlite3.OperationalError('private path')):
            response = self.client.get('/health')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()['error'], 'storage_unavailable')

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
