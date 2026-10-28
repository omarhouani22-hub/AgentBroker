"""Offline boundary tests. These do not establish a live ChatGPT session."""
import ast
import io
import json
import os
from pathlib import Path
import types
import unittest
from unittest.mock import Mock, patch
from time import monotonic
from urllib.error import HTTPError

import clara_oauth


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'CLARA_OAUTH_ENABLED': 'true', 'CLARA_OAUTH_MODEL': 'test-model'})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_disabled_by_default_and_requires_safe_explicit_model(self):
        for env in ({}, {'CLARA_OAUTH_ENABLED': 'true'},
                    {'CLARA_OAUTH_ENABLED': 'true', 'CLARA_OAUTH_MODEL': 'https://other-host'}):
            with patch.dict(os.environ, env, clear=True):
                self.assertFalse(clara_oauth.configured())
                with self.assertRaises(clara_oauth.Unavailable):
                    clara_oauth.complete({}, monotonic()+10)

    def test_loopback_no_credentials_or_openrouter_fields(self):
        response = io.BytesIO(json.dumps({'model': 'actual-model'}).encode())
        with patch.object(clara_oauth.TRANSPORT, 'open', return_value=response) as send:
            result = clara_oauth.complete({'messages': [{'role':'user','content':'hello'}],
                                          'provider': {'order':['paid']}, 'response_format': {}}, monotonic()+55)
        req = send.call_args.args[0]
        self.assertEqual(req.full_url, clara_oauth.URL)
        self.assertNotIn('Authorization', req.headers)
        self.assertEqual(set(json.loads(req.data)), {'messages','model','stream'})
        self.assertEqual(result['model'], 'actual-model')
        self.assertLessEqual(send.call_args.kwargs['timeout'], 8)

    def test_rejects_redirects(self):
        self.assertIsNone(clara_oauth.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://example.com'))

    def test_ignores_environment_proxies_for_loopback(self):
        from urllib.request import ProxyHandler
        self.assertFalse(any(isinstance(h, ProxyHandler) and h.proxies for h in clara_oauth.TRANSPORT.handlers))

    def test_errors_are_sanitized(self):
        with patch.object(clara_oauth.TRANSPORT, 'open', side_effect=HTTPError(clara_oauth.URL,401,'secret-body',{},None)):
            with self.assertRaisesRegex(clara_oauth.Unavailable, '^oauth_unavailable$'):
                clara_oauth.complete({'messages':[]}, monotonic()+10)

    def test_rejects_oversize_malformed_and_missing_model(self):
        for raw in (b'x'*100001, b'not json', b'[]', b'{"error":"private"}', b'{"choices":[]}'):
            with patch.object(clara_oauth.TRANSPORT, 'open', return_value=io.BytesIO(raw)):
                with self.assertRaises(clara_oauth.Unavailable):
                    clara_oauth.complete({'messages':[]}, monotonic()+10)

    def test_expired_deadline_does_not_call_proxy(self):
        with patch.object(clara_oauth.TRANSPORT, 'open') as send:
            with self.assertRaises(clara_oauth.Unavailable):
                clara_oauth.complete({'messages':[]}, monotonic()-1)
            send.assert_not_called()


class RoutingTests(unittest.TestCase):
    def setUp(self):
        # Execute the real routing function without importing unrelated runtime
        # models/Flask. This tests the production boundary and fallback ordering.
        tree = ast.parse(Path(__file__).with_name('moltbook.py').read_text())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'free_dialogue_json')
        self.call = Mock()
        self.proxy = types.SimpleNamespace(configured=lambda:True)
        self.ns = {'local_chat':types.SimpleNamespace(enabled=lambda:False),
                   'trained_model':types.SimpleNamespace(configured=lambda:False),
                   'clara_oauth':self.proxy, '_dialogue_json':self.call,
                   'companion_language':lambda c:'en', 'monotonic':monotonic,
                   'HTTPError':HTTPError, 'URLError':__import__('urllib.error',fromlist=['URLError']).URLError,
                   'TimeoutError':TimeoutError, 'RemoteResponseError':type('RemoteResponseError',(Exception,),{}),
                   'DialogueLanguageError':type('DialogueLanguageError',(ValueError,),{}),
                   'ModelOutputError':type('ModelOutputError',(ValueError,),{})}
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'<production-routing>','exec'),self.ns)

    def test_success_preserves_actual_model(self):
        self.call.return_value = {'content':'hello','_model':'openai_oauth/actual-model'}
        result = self.ns['free_dialogue_json']({'_companion':True, '_owner_request':True})
        self.assertEqual(result['_model'],'openai_oauth/actual-model')
        self.assertEqual(self.call.call_count,1)
        self.assertTrue(self.call.call_args.kwargs['use_oauth'])

    def test_proxy_transport_and_validation_failures_use_existing_fallback(self):
        for error in (clara_oauth.Unavailable(), ValueError('invalid output'), self.ns['DialogueLanguageError']()):
            self.call.reset_mock()
            self.call.side_effect = [error, {'content':'fallback'}]
            result = self.ns['free_dialogue_json']({'_companion':True, '_owner_request':True})
            self.assertEqual(result['_model'],'free_router')
            self.assertEqual(self.call.call_count,2)
            self.assertEqual(self.call.call_args.kwargs,{})

    def test_public_agent_never_uses_account(self):
        self.call.return_value = {'content':'public'}
        self.ns['free_dialogue_json']({'_companion':False})
        self.assertEqual(self.call.call_count,1)
        self.assertEqual(self.call.call_args.kwargs,{})

    def test_background_companion_never_uses_account(self):
        self.call.return_value = {'content':'opening'}
        self.ns['free_dialogue_json']({'_companion':True})
        self.assertEqual(self.call.call_args.kwargs,{})

    def test_disabled_uses_existing_fallback(self):
        self.proxy.configured = lambda:False
        self.call.return_value = {'content':'fallback'}
        self.ns['free_dialogue_json']({'_companion':True, '_owner_request':True})
        self.assertEqual(self.call.call_count,1)
        self.assertEqual(self.call.call_args.kwargs,{})


if __name__ == '__main__':
    unittest.main()
