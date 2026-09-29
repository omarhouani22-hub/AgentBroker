"""Browser access never stores or sends the API token after sign-in."""
import os
import tempfile
import unittest
from unittest.mock import patch

from app import app


class BrowserSessionTests(unittest.TestCase):
    def test_login_cookie_and_api_compatibility(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
            'AGENT_DB_PATH': directory + '/test.sqlite3',
            'AGENT_ACCESS_TOKEN': 'example-api-token-for-tests',
            'AGENT_LOGIN_PASSWORD': 'example-owner-password-for-tests',
        }):
            app.testing = True
            client = app.test_client()
            page = client.get('/')
            self.assertNotIn(b'id="token"', page.data)
            self.assertNotIn(b'Bearer ', page.data)
            self.assertEqual(client.get('/knowledge').status_code, 401)
            self.assertEqual(client.post('/session/login', json={'secret': 'wrong'}).status_code, 401)
            response = client.post('/session/login', json={'secret': 'example-owner-password-for-tests'})
            self.assertEqual(response.status_code, 200)
            self.assertIn('HttpOnly', response.headers['Set-Cookie'])
            self.assertIn('SameSite=Strict', response.headers['Set-Cookie'])
            self.assertNotIn('example-api-token-for-tests', response.headers['Set-Cookie'])
            self.assertTrue(client.get('/session/status').json['authenticated'])
            self.assertEqual(client.get('/knowledge').status_code, 200)
            with patch.dict(os.environ, {'AGENT_ACCESS_TOKEN': 'a-rotated-api-token-for-tests'}):
                self.assertEqual(client.get('/knowledge').status_code, 401)
            self.assertEqual(client.post('/knowledge/import', json={}).status_code, 401)
            self.assertNotEqual(client.post('/knowledge/import', json={},
                                      headers={'X-AgentBroker-Request': '1'}).status_code, 401)
            client.post('/session/logout')
            self.assertEqual(client.get('/knowledge').status_code, 401)
            self.assertEqual(client.get('/knowledge', headers={
                'Authorization': 'Bearer example-api-token-for-tests'}).status_code, 200)


if __name__ == '__main__':
    unittest.main()
