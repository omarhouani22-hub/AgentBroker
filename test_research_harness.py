import json
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock
from research_harness import Harness, check_output

GOOD = 'A sufficiently detailed research draft based on the supplied excerpt. This conclusion remains preliminary [S1].'

class HarnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, 'test.sqlite')
        def db():
            conn = sqlite3.connect(self.path)
            conn.execute('CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, record TEXT NOT NULL)')
            conn.execute('CREATE TABLE IF NOT EXISTS knowledge(id TEXT PRIMARY KEY, note TEXT NOT NULL)')
            return conn
        def save(r):
            with db() as c:
                c.execute('INSERT OR REPLACE INTO runs VALUES (?,?)', (r['id'], json.dumps(r)))
        def store(r):
            with db() as c:
                c.execute('INSERT OR REPLACE INTO knowledge VALUES (?,?)', (r['id'], r['output']))
        self.model = Mock(return_value={'content': GOOD})
        self.search = Mock(return_value=[{'title': 'Source', 'url': 'https://example.org', 'content': 'Example excerpt'}])
        self.h = Harness(db, save, lambda c,g: [], self.search, self.model, store)
    def tearDown(self):
        self.temp.cleanup()
    def test_completion_and_idempotent_resume(self):
        r, status = self.h.execute(goal='test')
        self.assertEqual(status, 200)
        self.assertTrue(r['verification']['storage_confirmed'])
        self.assertFalse(r['verification']['factual_accuracy_verified'])
        self.h.execute(run_id=r['id'])
        self.model.assert_called_once()
    def test_repair_unknown_reference(self):
        self.model.side_effect = [{'content': GOOD.replace('[S1]', '[S9]')}, {'content': GOOD}]
        r, status = self.h.execute(goal='test')
        self.assertEqual(status, 200)
        self.assertEqual(r['model_calls'], 2)
    def test_budget_survives_resume(self):
        self.model.return_value = {'content': 'bad'}
        r, status = self.h.execute(goal='test')
        self.assertEqual(status, 502)
        self.h.execute(run_id=r['id'])
        self.assertEqual(self.model.call_count, 2)
        with self.h.db() as c:
            self.assertEqual(c.execute('SELECT count(*) FROM knowledge').fetchone()[0], 0)
    def test_failed_search_resume_does_not_repeat_memory(self):
        self.search.side_effect = [TimeoutError(), [{'title': 'Source', 'url': 'https://example.org', 'content': 'text'}]]
        r, status = self.h.execute(goal='test')
        self.assertEqual(status, 502)
        r, status = self.h.execute(run_id=r['id'])
        self.assertEqual(status, 200)
        self.assertEqual(r['search_calls'], 2)
    def test_lease_blocks_parallel_execution(self):
        r, _ = self.h.execute(goal='test')
        owner = self.h.claim(r['id'])
        self.assertEqual(self.h.execute(run_id=r['id'])[1], 409)
        self.h.release(r['id'], owner)
    def test_storage_failure_resume_uses_existing_draft(self):
        original = self.h.store
        self.h.store = Mock(side_effect=sqlite3.OperationalError('secret'))
        r, status = self.h.execute(goal='test')
        self.assertEqual(status, 502)
        self.assertNotIn('secret', json.dumps(r))
        self.h.store = original
        self.assertEqual(self.h.execute(run_id=r['id'])[1], 200)
        self.model.assert_called_once()
    def test_empty_sources_never_call_model(self):
        self.search.return_value = []
        self.assertEqual(self.h.execute(goal='test')[1], 502)
        self.model.assert_not_called()
    def test_unknown_memory_citation(self):
        self.assertIn('unknown_citation', check_output(GOOD + ' [M1]', [1], []))

if __name__ == '__main__':
    unittest.main()
