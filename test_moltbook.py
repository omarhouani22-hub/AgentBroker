import json
import os
import unittest
from unittest.mock import patch

from flask import Flask
import moltbook


class MoltbookTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        moltbook.install_routes(app)
        self.client = app.test_client()

    def test_no_key_makes_no_request(self):
        with patch.dict(os.environ, {'MOLTBOOK_API_KEY': ''}), patch.object(moltbook.TRANSPORT, 'open') as open_:
            self.assertFalse(self.client.get('/moltbook/status').json['connected'])
            self.assertEqual(self.client.get('/moltbook/research?q=agents').status_code, 502)
            open_.assert_not_called()

    def test_search_preserves_provenance_and_blocks_redirect(self):
        class Reply:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, n):
                if 'status' in calls[-1].full_url:
                    return b'{"status":"claimed"}'
                return json.dumps({'success': True, 'results': [
                    {'id': 'a-b1', 'type': 'post', 'title': 'Memory practice',
                     'content': 'A' * 100, 'author': {'name': 'AnotherAgent'}}]}).encode()
        calls = []
        def open_(req, timeout):
            calls.append(req)
            return Reply()
        with patch.dict(os.environ, {'MOLTBOOK_API_KEY': 'test-key'}), patch.object(moltbook.TRANSPORT, 'open', side_effect=open_):
            notes = moltbook.research('agent memory')
        self.assertEqual(notes[0]['url'], 'https://www.moltbook.com/post/a-b1')
        self.assertEqual(notes[0]['author'], 'AnotherAgent')
        self.assertTrue(all(req.full_url.startswith('https://www.moltbook.com/api/v1/') for req in calls))
        self.assertTrue(all(req.get_header('Authorization') == 'Bearer test-key' for req in calls))

    def test_unclaimed_agent_does_not_publish(self):
        with patch.object(moltbook, 'ready', return_value=False), patch.object(moltbook, 'api') as api:
            result = self.client.post('/moltbook/posts', json={'title': 'AgentBroker intro', 'content': 'We are an AI agent project.'})
        self.assertEqual(result.status_code, 409)
        api.assert_not_called()


if __name__ == '__main__':
    unittest.main()
