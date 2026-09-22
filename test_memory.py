import json
import os
import tempfile
import unittest
from unittest.mock import patch
import app


class MemoryTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        env = patch.dict(os.environ, {
            'AGENT_DB_PATH': os.path.join(directory.name, 'memory.sqlite3'),
            'AGENT_ACCESS_TOKEN': 'x' * 32, 'DEEPSEEK_API_KEY': 'fake', 'TAVILY_API_KEY': 'fake'})
        env.start()
        self.addCleanup(env.stop)
        self.client = app.app.test_client()
        self.headers = {'Authorization': 'Bearer ' + 'x' * 32}
        self.note = dict(topic='Automation skills الأتمتة المهارات', note='Historical summary, not current evidence.',
                         sources=[dict(title='Paper', url='https://example.org/paper')],
                         created_at='2026-09-21T00:00:00+00:00')

    def post(self, notes):
        return self.client.post('/knowledge/import', json=notes, headers=self.headers)

    def test_auth(self):
        self.assertEqual(self.client.post('/knowledge/import', json=[self.note]).status_code, 401)

    def test_validation_is_atomic(self):
        bad = dict(self.note, sources=[dict(title='bad', url='file:///secret')])
        self.assertEqual(self.post([self.note, bad]).status_code, 400)
        self.assertEqual(self.client.get('/knowledge', headers=self.headers).get_json(), [])

    def test_idempotent_import_and_export(self):
        self.assertEqual(self.post([self.note]).get_json()['imported'], 1)
        self.assertEqual(self.post([self.note]).get_json()['skipped'], 1)
        exported = self.client.get('/knowledge/export', headers=self.headers).get_json()
        self.assertEqual(self.post(exported).get_json()['skipped'], 1)

    @patch('app.search_web', return_value=[dict(title='Current', url='https://example.org/current', content='Evidence')])
    @patch('app.model_call', return_value={'content': 'Comparison [M1] [S1]'})
    def test_memory_reaches_model(self, model, search):
        self.post([self.note])
        response = self.client.post('/runs', json={'goal': 'Automation skills'}, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertIn('Historical summary', model.call_args.args[0][1]['content'])
        self.assertEqual(len(response.get_json()['memory_used']), 1)
        self.assertIn('https://example.org/paper', response.get_json()['output'])

    def test_arabic_and_irrelevant_retrieval(self):
        self.post([self.note])
        with app.db() as conn:
            self.assertEqual(len(app.retrieve(conn, 'الأتمتة المهارات')), 1)
            self.assertEqual(app.retrieve(conn, 'astronomy galaxies'), [])

    def test_export_not_truncated_at_100(self):
        for i in range(101):
            self.post([dict(self.note, topic=f'topic {i}')])
        self.assertEqual(len(self.client.get('/knowledge/export', headers=self.headers).get_json()), 101)

    def test_seed_pack_valid(self):
        from memory import validate_notes
        if not os.path.exists('knowledge-starter.json'):
            self.skipTest('Optional seed pack is not included in this repository')
        with open('knowledge-starter.json', encoding='utf-8') as source:
            self.assertEqual(len(validate_notes(json.load(source))), 2)

if __name__ == '__main__':
    unittest.main()
