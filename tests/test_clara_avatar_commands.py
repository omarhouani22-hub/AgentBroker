"""Synthetic owner requests only; no model, speech generation or live data."""
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import app as server

class AvatarCommands(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        env=patch.dict(os.environ,{'AGENT_DB_PATH':tmp.name+'/preview.sqlite','AGENT_ACCESS_TOKEN':'synthetic-avatar-owner','OPENROUTER_API_KEY':'','MOLTBOOK_API_KEY':''})
        env.start();self.addCleanup(env.stop)
        server.app.testing=True;self.client=server.app.test_client();self.headers={'Authorization':'Bearer synthetic-avatar-owner'}
    def test_close_and_wide_acknowledge_framing_without_claiming_walking(self):
        for action,framing in (('closer','close'),('step_back','wide')):
            with patch('moltbook.free_dialogue_json') as model:
                r=self.client.post('/companion/messages',json={'content':'Come closer' if action=='closer' else 'Step back',
                    'appearance':{'scene':'studio','outfit':'business','pose':'seated','framing':framing},'presentation_action':action},headers=self.headers)
            self.assertEqual(r.status_code,200)
            self.assertIn('framing',r.json['messages'][-1]['content']);self.assertIn('natural walking is not available',r.json['messages'][-1]['content'])
            model.assert_not_called()
    def test_inconsistent_framing_is_rejected(self):
        r=self.client.post('/companion/messages',json={'content':'Come closer','presentation_action':'closer',
            'appearance':{'scene':'studio','outfit':'business','pose':'seated','framing':'wide'}},headers=self.headers)
        self.assertEqual(r.status_code,400)
    def test_visitor_cannot_apply_presentation_changes(self):
        self.assertEqual(self.client.post('/companion/messages',json={'content':'Come closer'}).status_code,401)
    def test_existing_shorts_asset_is_accepted_by_backend(self):
        from clara_advisor import validate_appearance
        self.assertEqual(validate_appearance({'scene':'studio','outfit':'shorts','pose':'seated','framing':'wide'})['outfit'],'shorts')
