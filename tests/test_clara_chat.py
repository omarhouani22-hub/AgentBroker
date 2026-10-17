"""Language switching preserves actual turns and overrides stale preferences."""
import json
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from flask import Flask
import moltbook as m


class ClaraChatTests(unittest.TestCase):
    def test_current_message_can_reset_old_fixed_language(self):
        with tempfile.TemporaryDirectory() as directory:
            db = lambda: sqlite3.connect(directory + '/state.sqlite')
            app = Flask('clara-test')
            m.install_dialogue(app, db, lambda: None, lambda record: None)
            client = app.test_client()
            client.post('/companion/preferences', json={'language':'en'})
            contexts = []
            def generate(context):
                contexts.append(context)
                return {'skip':False, 'content':'رد توضيحي' if m.companion_language(context)=='ar' else 'A clear reply.'}
            with patch.object(m, 'free_model_key', return_value='test'), patch.object(m, 'free_dialogue_json', side_effect=generate), patch('mem0_memory.remember', return_value=False):
                for message, expected in [('شو يعني تخطيط التعاقب؟','ar'),('Explain it in one sentence.','en'),('آه','ar')]:
                    result = client.post('/companion/messages', json={'content':message,'reply_language':'auto'})
                    self.assertEqual(result.status_code, 200)
                    self.assertEqual(m.companion_language(contexts[-1]), expected)
                    self.assertEqual(contexts[-1]['conversation'][-1]['content'], message)
            self.assertEqual(client.get('/companion/messages').json['language'], 'auto')
            with patch.object(m, 'free_dialogue_json') as generate:
                self.assertEqual(client.post('/companion/messages', json={'content':'Hello','reply_language':'invalid'}).status_code,400)
                generate.assert_not_called()

    def test_provider_receives_real_turns_and_clara_identity(self):
        captured = []
        class Response:
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def read(self,limit):
                return json.dumps({'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'skip':False,'content':'Yes, I can explain the example.','lesson':''})}}]}).encode()
        def open_request(req, timeout):
            captured.append(json.loads(req.data)); return Response()
        turns = [{'role':'user','content':'Explain workforce planning.'},{'role':'assistant','content':'It aligns staffing with demand.'},{'role':'user','content':'Can you give an example?'}]
        with patch.dict(os.environ,{'OPENROUTER_API_KEY':'test'},clear=True), patch.object(m.TRANSPORT,'open',side_effect=open_request):
            m.free_dialogue_json({'_companion':True,'language':'auto','conversation':turns})
        self.assertEqual(captured[0]['messages'][-3:],turns)
        self.assertIn('You are Clara',captured[0]['messages'][0]['content'])
        self.assertIn('natural English',captured[0]['messages'][0]['content'])
        self.assertEqual(captured[0]['model'],'openrouter/free')
