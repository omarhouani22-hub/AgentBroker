import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from cryptography.fernet import Fernet
from flask import Flask
from general_learning import install_routes


class GeneralLearningTest(unittest.TestCase):
    def test_gated_daily_learning_and_encrypted_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            key = Fernet.generate_key()
            saved = []
            searched = []
            def make_app(name):
                app = Flask(name)
                def db(): return sqlite3.connect(directory + '/' + name + '.db')
                def search(topic):
                    searched.append(topic)
                    return [{'title': 'Study', 'url': 'https://example.org/study',
                             'content': 'A bounded source excerpt about the topic.'}]
                install_routes(app, db, lambda: {'model': 'test'}, lambda: Fernet(key),
                               search, saved.append)
                return app.test_client()
            client = make_app('first')
            public = [{'title': 'Study', 'url': 'https://en.wikipedia.org/?curid=42',
                       'excerpt': 'A public introductory passage about collaboration and research. ' * 3}]
            with patch('general_learning.public_search', return_value=public) as free_search, \
                 patch('general_learning.hermes.runtime_ready', return_value=True), \
                 patch('general_learning.hermes.invoke', return_value={
                     'output': 'A sourced finding [S1] with uncertainty and a practical application. ' * 3}) as invoke:
                with patch.dict(os.environ, {'GENERAL_LEARNING_ENABLED': '0'}):
                    free = client.post('/general-learning/clock', json={})
                    self.assertEqual(free.json['status'], 'completed')
                    self.assertEqual(len(saved), 1)
                    self.assertEqual(len(searched), 0)
                    self.assertEqual(free_search.call_count, 1)
                    invoke.assert_not_called()
                with patch.dict(os.environ, {'GENERAL_LEARNING_ENABLED': '1'}):
                    paid_client = make_app('paid')
                    first = paid_client.post('/general-learning/clock', json={})
                    self.assertEqual(first.status_code, 200)
                    self.assertEqual(first.json['status'], 'completed')
                    self.assertEqual(len(saved), 2)
                    self.assertEqual(len(searched), 1)
                    second = paid_client.post('/general-learning/clock', json={
                        'checkpoint': first.json['checkpoint']})
                    self.assertEqual(second.json['status'], 'completed')
                    self.assertEqual(invoke.call_count, 1)
                    recovered = make_app('replacement').post('/general-learning/clock', json={
                        'checkpoint': first.json['checkpoint']})
                    self.assertEqual(recovered.json['status'], 'completed')
                    self.assertEqual(invoke.call_count, 1)
                    self.assertEqual(len(saved), 3)  # Existing note restored to new storage.

    def test_public_search_uses_fixed_host_and_bounded_source_text(self):
        from contextlib import closing
        from io import BytesIO
        import json
        from general_learning import public_search
        response = {'query': {'pages': [{'pageid': 42, 'title': 'Collaboration',
                    'extract': 'Public encyclopedia passage. ' * 8}]}}
        class Response(BytesIO):
            pass
        with patch('general_learning.PUBLIC_TRANSPORT.open', return_value=Response(json.dumps(response).encode())) as opened:
            result = public_search('public research methods')
        self.assertEqual(result[0]['url'], 'https://en.wikipedia.org/?curid=42')
        request = opened.call_args.args[0]
        self.assertEqual(request.full_url.split('?')[0], 'https://en.wikipedia.org/w/api.php')
        self.assertIn('public+research+methods', request.full_url)

    def test_invalid_citation_fails_without_retry(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.dict(os.environ, {'GENERAL_LEARNING_ENABLED': '1'}), \
             patch('general_learning.hermes.runtime_ready', return_value=True), \
             patch('general_learning.hermes.invoke', return_value={'output': 'Unsupported claim [S9]. ' * 9}) as invoke:
            app = Flask('failure')
            def db(): return sqlite3.connect(directory + '/state.db')
            saved = []
            install_routes(app, db, lambda: {'model': 'test'}, lambda: Fernet(Fernet.generate_key()),
                           lambda topic: [{'title': 'Source', 'url': 'https://example.org', 'content': 'Excerpt'}], saved.append)
            client = app.test_client()
            self.assertEqual(client.post('/general-learning/clock', json={}).json['status'], 'failed')
            self.assertEqual(client.post('/general-learning/clock', json={}).json['status'], 'failed')
            self.assertEqual(invoke.call_count, 1)
            self.assertEqual(saved, [])


if __name__ == '__main__':
    unittest.main()
