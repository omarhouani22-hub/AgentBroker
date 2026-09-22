import json
from unittest.mock import patch
from test_hermes import HermesTests, result
import app
import hermes_pilot as h
import hermes_team as team

class TeamTests(HermesTests):
    def tick(self, checkpoint=None):
        with patch.object(app, 'clock_identity', return_value=True):
            return self.client.post('/hermes/team/clock',json={'checkpoint':checkpoint})

    def test_clock_requires_scheduler_identity(self):
        with patch.object(app,'clock_identity',return_value=False):
            self.assertEqual(self.client.post('/hermes/team/clock',json={}).status_code,403)

    def test_team_controls_plan_steps_persistence_and_cooldown(self):
        self.assertEqual(self.client.post('/hermes/team',json={'enabled':True}).status_code,401)
        self.assertEqual(self.client.post('/hermes/team',json={'enabled':True},headers=self.headers).status_code,200)
        with patch.object(h,'runtime_ready',return_value=True):
            first=self.tick()
            self.assertEqual(first.status_code,200)
            self.assertEqual(first.json['status'],'ready')
            self.assertTrue(first.json['experiment']['team_owned'])
            self.assertNotEqual(first.json['experiment']['cases'],h.EXTENDED_CASES)
            self.assertEqual(self.client.post('/hermes/experiments',json={},headers=self.headers).status_code,409)
        exp=first.json['experiment']
        self.assertEqual(self.step(exp['id']).status_code,409)
        with patch.object(h,'invoke',side_effect=[result('{}'),result('Teach units'),result('saved',{'units/SKILL.md':'Check units'}),result('{}')]) as invoke, patch.object(h,'deepseek_teacher',return_value={'output':'A lesson','provider':'deepseek'}):
            for _ in range(5): final=self.tick()
        self.assertEqual(final.json['experiment']['status'],'completed')
        self.assertEqual(final.json['team']['round'],1)
        self.assertEqual(len(final.json['team']['history']),1)
        with patch.object(h,'invoke') as invoke:
            self.assertEqual(self.tick().json['team']['round'],1)
            invoke.assert_not_called()
        checkpoint=final.json['checkpoint']
        with app.db() as conn:conn.execute('DELETE FROM hermes_pilot')
        restored=self.tick(checkpoint)
        self.assertEqual(restored.json['team']['round'],1)
        self.assertEqual(restored.json['experiment']['id'],exp['id'])
        self.assertEqual(self.client.post('/hermes/team',json={'enabled':False},headers=self.headers).json['team']['enabled'],False)
        self.assertEqual(self.tick(checkpoint).json['team']['enabled'],False)

    def test_plan_targets_previous_failure(self):
        state=h.initial_state()
        state['experiment']={'retest':{'evaluation':{'checks':[{'id':'seconds','passed':False}]}}}
        focus,cases,reason=team.plan(state)
        self.assertEqual(focus,'seconds')
        self.assertEqual(cases[0]['id'],'seconds')
