"""Clara's opt-in OmniRoute gateway is pinned, free-only and private-chat only."""
import json
import os
import unittest
from unittest.mock import patch
import moltbook as m


class Response:
    def __init__(self, content='A clear reply.'):
        self.body = json.dumps({'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'skip':False,'content':content,'lesson':''})}}]}).encode()
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def read(self,limit): return self.body


GATEWAY = {'LLM_PROVIDER':'omniroute','LLM_BASE_URL':'https://gateway.example/v1',
           'LLM_MODEL':'oc/test-free-model','LLM_API_KEY':'test-gateway-token-0000'}
TURNS = [{'role':'user','content':'Explain workforce planning.'}]


class ClaraOmniRouteTests(unittest.TestCase):
    def test_companion_reply_uses_pinned_gateway_route(self):
        captured = []
        def open_request(req, timeout):
            captured.append(req); return Response()
        with patch.dict(os.environ,dict(GATEWAY,OPENROUTER_API_KEY='unused'),clear=True), patch.object(m.TRANSPORT,'open',side_effect=open_request):
            result = m.free_dialogue_json({'_companion':True,'language':'auto','conversation':TURNS})
        self.assertEqual(len(captured),1)
        self.assertEqual(captured[0].full_url,'https://gateway.example/v1/chat/completions')
        self.assertEqual(captured[0].get_header('Authorization'),'Bearer test-gateway-token-0000')
        payload = json.loads(captured[0].data)
        self.assertEqual(payload['model'],'oc/test-free-model')
        self.assertNotIn('provider',payload)
        self.assertIn('You are Clara',payload['messages'][0]['content'])
        self.assertEqual(payload['messages'][-1],TURNS[-1])
        self.assertEqual(result['_model'],'omniroute')

    def test_local_gateway_may_omit_token(self):
        captured = []
        env = dict(GATEWAY,LLM_BASE_URL='http://127.0.0.1:20128/v1',LLM_API_KEY='')
        with patch.dict(os.environ,env,clear=True), patch.object(m.TRANSPORT,'open',side_effect=lambda req,timeout:captured.append(req) or Response()):
            m.free_dialogue_json({'_companion':True,'language':'en','conversation':TURNS})
        self.assertEqual(captured[0].full_url,'http://127.0.0.1:20128/v1/chat/completions')
        self.assertIsNone(captured[0].get_header('Authorization'))

    def test_unsafe_configuration_fails_closed_without_fallback(self):
        unsafe = [{'LLM_MODEL':'auto'},{'LLM_MODEL':'auto/cheap'},{'LLM_MODEL':'oc/'},
                  {'LLM_MODEL':'kr/claude-sonnet-4.5'},{'LLM_BASE_URL':'http://gateway.example/v1'},
                  {'LLM_BASE_URL':'https://user:pass@gateway.example/v1'},{'LLM_API_KEY':''}]
        for change in unsafe:
            with self.subTest(change=change), patch.dict(os.environ,dict(GATEWAY,OPENROUTER_API_KEY='present',**change),clear=True), \
                    patch.object(m.TRANSPORT,'open') as transport:
                self.assertFalse(m.dialogue_model_configured())
                with self.assertRaises(ValueError):
                    m.free_dialogue_json({'_companion':True,'language':'en','conversation':TURNS})
                transport.assert_not_called()

    def test_public_dialogue_does_not_use_gateway(self):
        captured = []
        with patch.dict(os.environ,dict(GATEWAY,OPENROUTER_API_KEY='test'),clear=True), patch.object(m.TRANSPORT,'open',side_effect=lambda req,timeout:captured.append(req) or Response('A substantive public reply that is long enough.')):
            result = m.free_dialogue_json({'task':'Reply','conversation':[]})
        self.assertEqual(captured[0].full_url,'https://openrouter.ai/api/v1/chat/completions')
        self.assertEqual(result['_model'],'free_router')

    def test_default_remains_openrouter(self):
        with patch.dict(os.environ,{'OPENROUTER_API_KEY':'test'},clear=True):
            self.assertTrue(m.dialogue_model_configured())
            self.assertFalse(m.omniroute_selected())


if __name__ == '__main__':
    unittest.main()
