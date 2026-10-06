import os
import unittest
from unittest.mock import Mock, patch
import mem0_memory as m


class Mem0Tests(unittest.TestCase):
    def test_platform_uses_custom_instructions_and_only_user_facts(self):
        sdk = Mock()
        with patch.dict(os.environ, {'MEM0_ENABLED': 'true', 'MEM0_BACKEND': 'platform',
                                     'MEM0_OWNER_ID': 'owner-test'}), patch.object(m, '_client', sdk):
            self.assertTrue(m.remember('I prefer Arabic', 'invented assistant fact'))
        self.assertEqual(sdk.add.call_args.args[0], [{'role': 'user', 'content': 'I prefer Arabic'}])
        self.assertIn('custom_instructions', sdk.add.call_args.kwargs)
        self.assertNotIn('prompt', sdk.add.call_args.kwargs)

    def test_disabled_does_not_initialize_or_send(self):
        with patch.dict(os.environ, {'MEM0_ENABLED': 'false'}), patch.object(m, '_client', Mock()) as sdk:
            self.assertEqual(m.recall('hello'), [])
            self.assertFalse(m.remember('hello', 'hi'))
            sdk.search.assert_not_called()
            sdk.add.assert_not_called()

    def test_search_and_write_share_private_owner_scope(self):
        sdk = Mock()
        sdk.search.return_value = {'results': [{'memory': 'User prefers Arabic'}]}
        with patch.dict(os.environ, {'MEM0_ENABLED': 'true', 'MEM0_OWNER_ID': 'owner-test'}), patch.object(m, '_client', sdk):
            self.assertEqual(m.recall('language'), [{'memory': 'User prefers Arabic'}])
            self.assertTrue(m.remember('I prefer Arabic', 'Understood'))
        self.assertEqual(sdk.search.call_args.kwargs['filters'],
                         {'user_id': 'owner-test', 'agent_id': 'agentbroker-private'})
        self.assertEqual(sdk.add.call_args.kwargs['user_id'], 'owner-test')
        self.assertEqual(sdk.add.call_args.kwargs['agent_id'], 'agentbroker-private')

    def test_service_failure_keeps_chat_memory_optional(self):
        sdk = Mock()
        sdk.search.side_effect = TimeoutError('secret must not be logged')
        sdk.add.side_effect = TimeoutError('secret must not be logged')
        with patch.dict(os.environ, {'MEM0_ENABLED': 'true', 'MEM0_OWNER_ID': 'owner-test'}), patch.object(m, '_client', sdk):
            self.assertEqual(m.recall('hello'), [])
            self.assertFalse(m.remember('hello', 'hi'))

    def test_context_receives_memories(self):
        import moltbook
        companion = moltbook.companion_state({})
        moltbook.append_companion(companion, 'user', 'What language do I prefer?')
        with patch.object(m, 'recall', return_value=[{'memory': 'Arabic'}]) as recall:
            context = moltbook.companion_context(companion, 'Reply')
        recall.assert_called_once_with('What language do I prefer?')
        self.assertEqual(context['private_mem0_memories'], [{'memory': 'Arabic'}])

    def test_status_requires_auth(self):
        import app
        with patch.dict(os.environ, {'AGENT_ACCESS_TOKEN': 'x' * 32}):
            c = app.app.test_client()
            self.assertEqual(c.get('/memory/status').status_code, 401)
            self.assertEqual(c.get('/memory/status', headers={'Authorization': 'Bearer ' + 'x' * 32}).status_code, 200)
