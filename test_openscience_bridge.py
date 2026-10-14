import json
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch, Mock
from flask import Flask
import openscience_bridge as bridge


def events(status='completed', code=0):
    return '\n'.join(json.dumps(e) for e in [
        {'type': 'text', 'sessionID': 'worker', 'parentID': 'root', 'part': {'text': 'worker output'}},
        {'type': 'text', 'sessionID': 'root', 'part': {'text': 'Original manuscript with bibliography'}},
        {'type': 'done', 'sessionID': 'root', 'status': status, 'exitCode': code, 'cost': 0},
    ]).encode()


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = self.temp.name + '/test.sqlite'
        self.app = Flask(__name__)
        bridge.install_routes(self.app, lambda: sqlite3.connect(self.path))
        self.client = self.app.test_client()
        self.data = {'topic': 'AI for HR', 'request_id': 'research-001', 'mode': 'book'}

    def tearDown(self):
        self.temp.cleanup()

    def test_root_answer_only(self):
        result = bridge.parse_events(events(), 0)
        self.assertNotIn('worker', result['output'])
        self.assertFalse(result['published'])
        self.assertTrue(result['requires_editorial_review'])

    def test_rejected_or_missing_completion_fails(self):
        for raw, code in [(events('rejected', 3), 3), (events(), 1),
                          (b'{"type":"text"}', 0), (b'not json', 0)]:
            with self.assertRaises(ValueError):
                bridge.parse_events(raw, code)

    def test_disabled_does_not_launch(self):
        with patch.object(bridge, 'status', return_value={'ready': False}), patch.object(bridge, 'run_research') as run:
            self.assertEqual(self.client.post('/openscience/runs', json=self.data).status_code, 503)
            run.assert_not_called()

    def test_retry_returns_saved_result_and_conflict(self):
        with patch.object(bridge, 'status', return_value={'ready': True}), patch.object(bridge, 'run_research', return_value={'output': 'draft', 'published': False}) as run:
            self.assertEqual(self.client.post('/openscience/runs', json=self.data).status_code, 200)
            self.assertEqual(self.client.post('/openscience/runs', json=self.data).status_code, 200)
            self.assertEqual(self.client.post('/openscience/runs', json={**self.data, 'topic': 'different'}).status_code, 409)
            run.assert_called_once()
            self.assertEqual(self.client.get('/openscience/runs/research-001').json['output'], 'draft')

    def test_failure_is_reserved_not_replayed(self):
        with patch.object(bridge, 'status', return_value={'ready': True}), patch.object(bridge, 'run_research', side_effect=ValueError('SECRET')) as run:
            response = self.client.post('/openscience/runs', json=self.data)
            self.assertEqual(response.status_code, 502)
            self.assertNotIn('SECRET', response.get_data(as_text=True))
            self.assertEqual(self.client.post('/openscience/runs', json=self.data).status_code, 409)
            run.assert_called_once()

    def test_subprocess_uses_explicit_model_no_app_credentials(self):
        def launch(command, **kwargs):
            kwargs['stdout'].write(events())
            self.assertIn('--deny-prompts', command)
            self.assertIn('--delegation', command)
            self.assertNotIn('--auto-approve', command)
            self.assertNotIn('MOLTBOOK_API_KEY', kwargs['env'])
            self.assertNotIn('AGENT_ACCESS_TOKEN', kwargs['env'])
            self.assertEqual(kwargs['env']['OPENAI_API_KEY'], 'dedicated')
            return Mock(returncode=0)
        env = {'OPENSCIENCE_ENABLED': '1', 'OPENSCIENCE_MODEL': 'openai/test',
               'OPENSCIENCE_PROVIDER_KEY_ENV': 'OPENAI_API_KEY',
               'OPENSCIENCE_PROVIDER_API_KEY': 'dedicated', 'MOLTBOOK_API_KEY': 'private', 'AGENT_ACCESS_TOKEN': 'private'}
        with patch.dict(os.environ, env, clear=True), patch.object(bridge.shutil, 'which', return_value='/bin/openscience'), patch.object(bridge.subprocess, 'Popen', side_effect=launch):
            self.assertFalse(bridge.run_research('topic', 'English', True)['published'])

    def test_existing_app_auth_protects_new_routes(self):
        with patch.dict(os.environ, {'AGENT_ACCESS_TOKEN': 'test-long-token', 'AGENT_DB_PATH': self.path}):
            from app import app
            client = app.test_client()
            self.assertEqual(client.get('/openscience/status').status_code, 401)
            self.assertEqual(client.get('/openscience/status', headers={'Authorization': 'Bearer test-long-token'}).status_code, 200)


if __name__ == '__main__':
    unittest.main()
