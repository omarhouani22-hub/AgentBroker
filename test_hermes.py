import json
import os
import tempfile
import unittest
from unittest.mock import patch

import app
import hermes_pilot as h


def answers(wrong=False):
    return json.dumps({
        'minutes': {'status': 'ok', 'fte': 5, 'staff': 5},
        'rounding': {'status': 'ok', 'fte': 2/9, 'staff': 0 if wrong else 1},
        'hours': {'status': 'ok', 'fte': 1.875, 'staff': 2},
        'missing': {'status': 'insufficient_data', 'fte': None, 'staff': None},
    })


def result(output, skills=None):
    return dict(completed=True, output=output, skills=skills or {}, api_calls=1,
                total_tokens=40, elapsed_seconds=1, tools_used=[])


class HermesTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        env = patch.dict(os.environ, {'AGENT_DB_PATH': folder.name + '/test.db',
                                     'AGENT_ACCESS_TOKEN': 'x' * 32, 'DEEPSEEK_API_KEY': 'fake-key'})
        env.start()
        self.addCleanup(env.stop)
        self.client = app.app.test_client()
        self.headers = {'Authorization': 'Bearer ' + 'x' * 32}

    def start(self):
        with patch.object(h, 'runtime_ready', return_value=True):
            response = self.client.post('/hermes/experiments', json={}, headers=self.headers)
        self.assertEqual(response.status_code, 201)
        state=h.read_state(app.db)
        state['experiment']['cases']=h.CASES
        h.write_state(app.db,state)
        return response.json['experiment']['id']

    def step(self, identity):
        return self.client.post('/hermes/experiments/' + identity + '/step', json={}, headers=self.headers)

    def test_unauthorized_cannot_run_or_restore(self):
        with patch.object(h, 'invoke') as invoke:
            for url in ('/hermes/tasks', '/hermes/experiments', '/hermes/import'):
                self.assertEqual(self.client.post(url, json={}).status_code, 401)
            self.assertEqual(self.client.get('/hermes/export').status_code, 401)
            invoke.assert_not_called()

    def test_only_improved_skill_promoted_and_reused(self):
        identity = self.start()
        skills = {'capacity/SKILL.md': 'Reusable capacity guidance.'}
        with patch.object(h, 'invoke', side_effect=[result(answers(True)), result('Saved', skills), result(answers(), skills)]) as invoke:
            for _ in range(3):
                response = self.step(identity)
                self.assertEqual(response.status_code, 200)
            self.assertEqual(invoke.call_args_list[-1].args[2], skills)
            # Training receives category outcomes, not holdout numbers or answers.
            self.assertNotIn('15000', invoke.call_args_list[1].args[1])
        self.assertTrue(response.json['experiment']['adopted'])
        with patch.object(h, 'invoke', return_value=result('One employee', skills)) as invoke:
            response = self.client.post('/hermes/tasks', json={'goal': 'Calculate capacity'}, headers=self.headers)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(invoke.call_args.args[2], skills)

    def test_perfect_baseline_does_not_claim_improvement(self):
        identity = self.start()
        with patch.object(h, 'invoke', side_effect=[result(answers()), result('Saved', {'x/SKILL.md': 'candidate'}), result(answers())]):
            for _ in range(3): response = self.step(identity)
        self.assertFalse(response.json['experiment']['adopted'])
        self.assertEqual(response.json['skill_count'], 0)

    def test_failure_retains_skills_and_no_automatic_retry(self):
        identity = self.start()
        with patch.object(h, 'invoke', side_effect=TimeoutError('private provider text')) as invoke:
            response = self.step(identity)
            self.assertEqual(response.status_code, 502)
            self.assertNotIn('private provider text', response.text)
            self.assertEqual(self.step(identity).status_code, 409)
            self.assertEqual(invoke.call_count, 1)

    def test_encrypted_export_survives_new_database(self):
        self.start()
        backup = self.client.get('/hermes/export', headers=self.headers)
        self.assertNotIn('baseline', backup.text)
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'AGENT_DB_PATH': folder + '/new.db'}):
            restored = self.client.post('/hermes/import', json=backup.json, headers=self.headers)
            self.assertEqual(restored.status_code, 200)
            self.assertEqual(restored.json['experiment']['stage'], 'baseline')
            self.assertEqual(self.client.post('/hermes/import', json=backup.json, headers=self.headers).status_code, 409)

    def test_tampered_checkpoint_rejected(self):
        response = self.client.post('/hermes/import', json={'checkpoint': 'tampered'}, headers=self.headers)
        self.assertEqual(response.status_code, 400)

    def test_skill_paths_and_limits(self):
        for bad in ('../SKILL.md', '/tmp/SKILL.md', 'x/../SKILL.md', 'x/script.py', 'x\\SKILL.md'):
            with self.subTest(path=bad), self.assertRaises(ValueError):
                h.validate_skills({bad: 'content'})

    def test_content_and_format_are_independent(self):
        raw='```json\n'+answers()+'\n```\nExplanation.'
        scored=h.evaluate(raw)
        self.assertEqual(scored['score'],4)
        self.assertFalse(scored['format_valid'])
        self.assertTrue(h.evaluate(answers())['format_valid'])
        self.assertEqual(h.evaluate(raw+'\n```json\n'+answers()+'\n```')['score'],0)
        self.assertEqual(h.evaluate('{"minutes":{},"minutes":{}}')['score'],0)

    def test_extended_edge_cases(self):
        expected=[(3.369369369,4),(1.000111111,2),(1.5,2),(1.343434343,2),(1.580645161,2),(1.904761905,2),(0.883333333,1),(None,None)]
        data={case['id']:{'status':'ok' if fte is not None else 'insufficient_data','fte':fte,'staff':staff}
              for case,(fte,staff) in zip(h.EXTENDED_CASES,expected)}
        self.assertEqual(h.evaluate(json.dumps(data),h.EXTENDED_CASES)['score'],8)

    def test_teacher_exchange_is_separate_and_reused_in_learning(self):
        with patch.object(h,'runtime_ready',return_value=True):
            started=self.client.post('/hermes/experiments',json={'teacher':True},headers=self.headers)
        identity=started.json['experiment']['id']
        state=h.read_state(app.db);state['experiment']['cases']=h.CASES;h.write_state(app.db,state)
        lesson={'provider':'deepseek','output':'Preserve six-decimal FTE and ceil unrounded values.'}
        skills={'capacity/SKILL.md':'Reusable skill'}
        with patch.object(h,'invoke',side_effect=[result(answers()),result('How should I handle units and rounding?'),result('Saved',skills),result(answers(),skills)]) as invoke, patch.object(h,'deepseek_teacher',return_value=lesson) as teacher:
            for _ in range(5):
                response=self.step(identity)
                self.assertEqual(response.status_code,200)
            teacher.assert_called_once_with('How should I handle units and rounding?')
            self.assertIn(lesson['output'],invoke.call_args_list[2].args[1])
            self.assertNotIn('15000',invoke.call_args_list[1].args[1])
            self.assertEqual(response.json['experiment']['teacher_lesson']['provider'],'deepseek')
            self.assertEqual(response.json['experiment']['status'],'completed')
            self.assertFalse(response.json['experiment']['adopted'])

    def test_bad_answers_never_pass(self):
        for output in ('not json', '[]', '{"minutes":{"fte":NaN,"staff":5}}'):
            self.assertEqual(h.evaluate(output)['score'], 0)


if __name__ == '__main__':
    unittest.main()
