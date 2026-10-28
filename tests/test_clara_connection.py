import json
import os
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

import app as a
import clara_connection as c
import moltbook as m


class ConnectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'AGENT_DB_PATH': self.temp.name+'/state.sqlite',
            'AGENT_ACCESS_TOKEN':'private-test-token', 'OPENROUTER_API_KEY':'sk-private-test',
            'CLARA_LOCAL_ONLY':'false'}, clear=True)
        self.env.start()
        self.client = a.app.test_client()
        self.headers = {'Authorization':'Bearer private-test-token'}
        c._LAST = None

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_auth_and_cookie_write_protection(self):
        for path in ('/companion/connection', '/companion/connection/test'):
            response = self.client.get(path) if path.endswith('connection') else self.client.post(path,json={})
            self.assertEqual(response.status_code,401)
            self.assertEqual(response.headers['Cache-Control'],'no-store')
        self.assertEqual(self.client.post('/session/login',json={'secret':'private-test-token'}).status_code,200)
        self.assertEqual(self.client.post('/companion/connection/test',json={}).status_code,401)
        self.assertEqual(self.client.get('/companion/connection').status_code,200)

    def test_status_has_no_network_side_effect_or_private_state(self):
        with patch.object(m,'free_dialogue_json') as generate:
            response = self.client.get('/companion/connection',headers=self.headers)
        generate.assert_not_called()
        self.assertEqual(response.json['selected_route'],'openrouter_free')
        self.assertIsNone(response.json['last_observation'])
        self.assertNotIn('sk-private',response.get_data(as_text=True))
        with patch('local_chat.enabled',return_value=True):
            self.assertEqual(self.client.get('/companion/connection',headers=self.headers).json['selected_route'],'local')

    def test_fixed_test_uses_real_free_adapter_and_preserves_history(self):
        state=m.dialogue_state(a.db)
        owner=m.companion_state(state)
        m.append_companion(owner,'user','Private conversation never shared with diagnostic')
        m.save_dialogue_state(a.db,state)
        captured=[]
        class Response:
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def read(self,limit):
                return json.dumps({'model':'vendor/actual-free-model','choices':[{'finish_reason':'stop',
                    'message':{'content':json.dumps({'skip':False,'content':'Hello! How can I help?','lesson':''})}}]}).encode()
        def transport(req,timeout):
            captured.append((req.full_url,json.loads(req.data)))
            return Response()
        with patch.object(m.TRANSPORT,'open',side_effect=transport),patch('team_provider.dual_model_call') as paid:
            response=self.client.post('/companion/connection/test',json={},headers=self.headers)
        paid.assert_not_called()
        self.assertEqual(response.status_code,200)
        self.assertEqual(captured[0][0],'https://openrouter.ai/api/v1/chat/completions')
        self.assertEqual(captured[0][1]['model'],'openrouter/free')
        self.assertNotIn('Private conversation',json.dumps(captured))
        self.assertEqual(response.json['last_observation']['model'],'vendor/actual-free-model')
        self.assertEqual(response.json['last_observation']['route'],'openrouter_free')
        self.assertGreaterEqual(response.json['last_observation']['duration_ms'],0)
        self.assertNotIn('Hello!',response.get_data(as_text=True))
        owner=m.companion_state(m.dialogue_state(a.db))
        self.assertEqual(len(owner['messages']),1)
        self.assertEqual(owner['reply_calls'],1)

    def test_limits_arbitrary_prompts_and_busy_checks_do_not_generate(self):
        with patch.object(m,'free_dialogue_json') as generate:
            self.assertEqual(self.client.post('/companion/connection/test',json={'message':'custom'},headers=self.headers).status_code,400)
            m.DIALOGUE_LOCK.acquire()
            try:
                self.assertEqual(self.client.post('/companion/connection/test',json={},headers=self.headers).status_code,409)
            finally: m.DIALOGUE_LOCK.release()
            state=m.dialogue_state(a.db)
            owner=m.companion_state(state)
            owner.update(reply_day=c.datetime.now(c.timezone.utc).date().isoformat(),reply_calls=12)
            m.save_dialogue_state(a.db,state)
            self.assertEqual(self.client.post('/companion/connection/test',json={},headers=self.headers).status_code,429)
        generate.assert_not_called()

    def test_error_is_categorized_and_not_exposed_or_retried(self):
        error=HTTPError('https://openrouter.ai/api/v1/chat/completions',429,'sensitive provider detail',{},None)
        with patch.object(m.TRANSPORT,'open',side_effect=error) as transport:
            response=self.client.post('/companion/connection/test',json={},headers=self.headers)
        self.assertEqual(transport.call_count,1)
        self.assertEqual(response.status_code,503)
        self.assertEqual(response.json['last_observation']['error'],'rate_limited')
        self.assertEqual(response.json['last_observation']['model'],'unknown')
        self.assertNotIn('sensitive',response.get_data(as_text=True))

    def test_metadata_is_not_invented(self):
        for model in (None,'','sk-secret','https://example.test','password=value','unsafe model'):
            self.assertEqual(c.reported_model(model),'unknown')
        result={'_model':'agentbroker_local','content':'Hello'}
        with patch('local_chat.enabled',return_value=True):
            c.observe(lambda context:result,{'model':'free'})
        self.assertEqual(c._LAST['route'],'local')
        self.assertEqual(c._LAST['model'],'unknown')

    def test_real_messages_are_observed(self):
        with patch.object(m,'_free_dialogue_json',return_value={'_model':'free_router','_reported_model':'vendor/model','content':'A useful answer.'}),patch('mem0_memory.remember',return_value=False):
            response=self.client.post('/companion/messages',json={'content':'Explain gravity in one sentence.'},headers=self.headers)
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.client.get('/companion/connection',headers=self.headers).json['last_observation']['model'],'vendor/model')


if __name__ == '__main__': unittest.main()
