import io
import json
import os
import unittest
from unittest.mock import patch
import app as b
import hermes_pilot

class ClaudeTests(unittest.TestCase):
    env = {'LLM_PROVIDER':'anthropic', 'ANTHROPIC_ENABLED':'true',
           'ANTHROPIC_API_KEY':'test-secret', 'ANTHROPIC_MODEL':'chosen-claude',
           'OPENAI_API_KEY':'never-send', 'DEEPSEEK_API_KEY':'never-send'}

    def test_native_routing_even_with_dual_mode(self):
        reply = {'stop_reason':'end_turn', 'content':[{'type':'text','text':'مرحبا'}]}
        with patch.dict(os.environ, self.env, clear=True), patch.object(b.model_transport, 'open', return_value=io.BytesIO(json.dumps(reply).encode())) as opened, patch('team_provider.dual_model_call') as dual:
            answer = b.model_call([{'role':'system','content':'Instructions'}, {'role':'user','content':'Hello'}])
            req = opened.call_args.args[0]
            payload = json.loads(req.data)
            self.assertEqual(req.full_url, 'https://api.anthropic.com/v1/messages')
            self.assertEqual(req.get_header('X-api-key'), 'test-secret')
            self.assertIsNone(req.get_header('Authorization'))
            self.assertEqual(payload['system'], 'Instructions')
            self.assertEqual(payload['messages'], [{'role':'user','content':'Hello'}])
            self.assertEqual(answer['content'], 'مرحبا')
            opened.assert_called_once()
            dual.assert_not_called()

    def test_disabled_or_missing_credentials_no_network(self):
        for change in ({'ANTHROPIC_ENABLED':'false'}, {'ANTHROPIC_API_KEY':''}, {'ANTHROPIC_MODEL':''}):
            with self.subTest(change=change), patch.dict(os.environ, {**self.env, **change}, clear=True), patch.object(b.model_transport,'open') as opened:
                with self.assertRaises(ValueError): b.model_call([{'role':'user','content':'Hello'}])
                opened.assert_not_called()

    def test_incomplete_malformed_and_empty_no_retry(self):
        replies = [[], {'stop_reason':'max_tokens'}, {'stop_reason':'tool_use'},
                   {'stop_reason':'end_turn','content':[]},
                   {'stop_reason':'end_turn','content':[{'type':'text','text':None}]}]
        for reply in replies:
            with self.subTest(reply=reply), patch.dict(os.environ,self.env,clear=True), patch.object(b.model_transport,'open',return_value=io.BytesIO(json.dumps(reply).encode())) as opened:
                with self.assertRaises(ValueError): b.model_call([{'role':'user','content':'Hello'}], bounded=True)
                opened.assert_called_once()

    def test_hermes_rejects_before_subprocess(self):
        with patch('hermes_pilot.subprocess.run') as run:
            with self.assertRaisesRegex(ValueError, 'not the Hermes'):
                hermes_pilot.invoke({'provider':'anthropic'}, 'hello', {})
            run.assert_not_called()
