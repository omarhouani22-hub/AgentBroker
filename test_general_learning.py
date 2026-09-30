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
            with patch('general_learning.hermes.runtime_ready', return_value=True), \
                 patch('general_learning.hermes.invoke', return_value={
                     'output': 'A sourced finding [S1] with uncertainty and a practical application. ' * 3}) as invoke:
                with patch.dict(os.environ, {'GENERAL_LEARNING_ENABLED': '0'}):
                    paused = client.post('/general-learning/clock', json={})
                    self.assertEqual(paused.json['status'], 'paused')
                    invoke.assert_not_called()
                with patch.dict(os.environ, {'GENERAL_LEARNING_ENABLED': '1'}):
                    first = client.post('/general-learning/clock', json={
                        'checkpoint': paused.json['checkpoint']})
                    self.assertEqual(first.status_code, 200)
                    self.assertEqual(first.json['status'], 'completed')
                    self.assertEqual(len(saved), 1)
                    self.assertEqual(len(searched), 1)
                    second = client.post('/general-learning/clock', json={
                        'checkpoint': first.json['checkpoint']})
                    self.assertEqual(second.json['status'], 'completed')
                    self.assertEqual(invoke.call_count, 1)
                    recovered = make_app('replacement').post('/general-learning/clock', json={
                        'checkpoint': first.json['checkpoint']})
                    self.assertEqual(recovered.json['status'], 'completed')
                    self.assertEqual(invoke.call_count, 1)
                    self.assertEqual(len(saved), 2)  # Existing note restored to new storage.

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
