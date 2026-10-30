"""Synthetic owner fixtures only; never commit the owner's actual profile."""
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError

import app as server
import clara_owner_memory as memory
import local_chat
import moltbook as m
import trained_model
from clara_advisor import profile_context

QUESTION = 'What do you know about my career and goals?'
ENTRIES = [
    {'category': 'communication_preferences', 'fact': 'Use English. ' * 25, 'as_of': '2026-10-30'},
    {'category': 'career العمل', 'fact': 'Synthetic owner works in workforce planning at Cedar Lab.', 'as_of': '2026-10-30'},
    {'category': 'ambitions طموحات', 'fact': 'Synthetic owner aims to launch the Juniper training project.', 'as_of': '2026-10-30'},
    {'category': 'health', 'fact': 'SENSITIVE_SYNTHETIC_HEALTH_MARKER', 'as_of': '2026-10-30'},
]


class Response:
    def __init__(self, content):
        self.content = content
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self, limit):
        return json.dumps({'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps({'skip': False, 'content': self.content, 'lesson': ''})}}]}).encode()


class OwnerMemoryIntegration(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = self.directory.name + '/owner.sqlite'
        env = patch.dict(os.environ, {'AGENT_DB_PATH': self.path, 'AGENT_ACCESS_TOKEN': 'synthetic-owner-token',
                                     'OPENROUTER_API_KEY': 'synthetic-free-key', 'CLARA_LOCAL_ONLY': '', 'MEM0_ENABLED': ''})
        env.start(); self.addCleanup(env.stop)
        server.app.testing = True
        self.client = server.app.test_client()
        self.headers = {'Authorization': 'Bearer synthetic-owner-token'}
        self.db = lambda: sqlite3.connect(self.path)

    def import_profile(self):
        result = self.client.post('/companion/profile', json={'confirm_private_import': True, 'entries': ENTRIES}, headers=self.headers)
        self.assertEqual(result.status_code, 200)
        self.assertFalse(result.json['storage']['durability_verified'])

    def fresh_conversation(self):
        # A new conversation/checkpoint without profile fields must not erase the store.
        state = m.dialogue_state(self.db)
        state.pop('companion', None)
        m.save_dialogue_state(self.db, state)

    def profile_from_request(self, request):
        payload = json.loads(request.data)
        background = payload['messages'][1]['content'].split(': ', 1)[1]
        context = json.loads(background)
        selected = context['owner_profile']
        facts = ' '.join(e['fact'] for e in selected)
        self.assertIn('Cedar Lab', facts)
        self.assertIn('Juniper', facts)
        self.assertNotIn('SENSITIVE_SYNTHETIC', facts)
        self.assertEqual(payload['model'], 'openrouter/free')
        return facts

    def test_fresh_owner_chat_uses_imported_memory_in_real_provider_payload(self):
        self.import_profile(); self.fresh_conversation()
        self.assertEqual(self.client.get('/companion/messages', headers=self.headers).json['messages'], [])
        captured = []
        def provider(request, timeout):
            facts = self.profile_from_request(request)
            captured.append(facts)
            return Response('From your saved profile: ' + facts[:350])
        with patch.object(m.TRANSPORT, 'open', side_effect=provider), patch('local_speech.configured', return_value=False):
            response = self.client.post('/companion/messages', json={'content': QUESTION}, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(captured), 1)
        self.assertIn('Cedar Lab', response.json['messages'][-1]['content'])
        self.assertIn('Juniper', response.json['messages'][-1]['content'])
        self.assertNotIn('Cedar Lab', response.json['messages'][0]['content'])

    def test_retry_and_trained_fallback_keep_identical_memory(self):
        self.import_profile(); self.fresh_conversation()
        state = m.dialogue_state(self.db)
        owner = m.companion_state(state)
        owner['model'] = 'trained'
        m.save_dialogue_state(self.db, state)
        captured = []
        def provider(request, timeout):
            captured.append(self.profile_from_request(request))
            if len(captured) == 1: raise URLError('synthetic connection failure')
            return Response('Your saved profile describes workforce planning and a training project.')
        with patch.object(trained_model, 'configured', return_value=True), patch.object(trained_model, 'generate', side_effect=RuntimeError('synthetic runtime unavailable')) as trained, patch.object(m.TRANSPORT, 'open', side_effect=provider), patch('local_speech.configured', return_value=False):
            response = self.client.post('/companion/messages', json={'content': QUESTION}, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(captured), 2)
        self.assertEqual(captured[0], captured[1])
        self.assertIn('Cedar Lab', json.dumps(trained.call_args.args[0]['owner_profile']))

    def test_local_and_trained_serialization_never_drop_selected_facts(self):
        selected = profile_context(ENTRIES, QUESTION)
        context = {'_companion': True, 'owner_profile': selected,
                   'conversation': [{'role': 'user', 'content': QUESTION}]}
        local = local_chat.messages(context)
        self.assertIn('Cedar Lab', local[0]['content'])
        self.assertIn('Juniper', local[0]['content'])
        self.assertEqual(trained_model.compact_context(context)['owner_profile'], selected)
        context['owner_profile'] = [{'category': 'career', 'fact': 'x'*1600, 'as_of': 'today'}]
        with self.assertRaisesRegex(ValueError, 'exceeds local model capacity'):
            local_chat.messages(context)

    def test_process_restart_and_legacy_migration(self):
        state = m.dialogue_state(self.db)
        m.companion_state(state)['owner_profile'] = ENTRIES
        m.save_dialogue_state(self.db, state)
        # First owner context lazily migrates existing profiles, without reimport.
        context = m.companion_context(m.companion_state(state), QUESTION, db=self.db)
        self.assertIn('Juniper', json.dumps(context['owner_profile']))
        self.fresh_conversation()
        code = ('import sqlite3,json; import clara_owner_memory as p; '
                'print(json.dumps(p.load(lambda:sqlite3.connect(' + repr(self.path) + '))))')
        restored = json.loads(subprocess.check_output([sys.executable, '-c', code], text=True))
        self.assertEqual(restored, ENTRIES)

    def test_visitors_wrong_tokens_and_public_output_do_not_retrieve_memory(self):
        self.import_profile()
        visitor = server.app.test_client()
        with patch.object(m.TRANSPORT, 'open') as provider:
            for headers in ({}, {'Authorization': 'Bearer wrong-token'}):
                for path in ('/companion/messages', '/companion/advisor/status', '/companion/history/export'):
                    reply = visitor.get(path, headers=headers)
                    self.assertEqual(reply.status_code, 401)
                    self.assertNotIn('Cedar Lab', reply.get_data(as_text=True))
                self.assertEqual(visitor.post('/companion/messages', json={'content': QUESTION}, headers=headers).status_code, 401)
                self.assertEqual(visitor.post('/companion/profile', json={'entries': []}, headers=headers).status_code, 401)
            provider.assert_not_called()
        for path in ('/', '/clara/', '/health', '/moltbook/status'):
            response = visitor.get(path)
            self.assertNotIn('Cedar Lab', response.get_data(as_text=True))
            self.assertNotIn('Juniper', response.get_data(as_text=True))

    def test_public_generation_rejects_accidental_private_context_before_transport(self):
        with patch.object(m.TRANSPORT, 'open') as provider:
            for context in ({'owner_profile': ENTRIES}, {'nested': {'companion': {'owner_profile': ENTRIES}}}):
                with self.assertRaisesRegex(ValueError, 'Private context'):
                    m.free_dialogue_json(context)
                with self.assertRaisesRegex(ValueError, 'Private context'):
                    trained_model.compact_context(context)
            provider.assert_not_called()
        self.assertEqual(trained_model.compact_context({'task': 'Public topic'}), {'task': 'Public topic'})

    def test_profile_edit_and_forget_use_authoritative_store(self):
        self.import_profile(); self.fresh_conversation()
        result = self.client.post('/companion/messages', json={'content': '/forget 2'}, headers=self.headers)
        self.assertEqual(result.status_code, 200)
        self.assertFalse(any('Cedar Lab' in e['fact'] for e in memory.load(self.db)))
        result = self.client.post('/companion/messages', json={'content': '/remember Prefer short explanations.'}, headers=self.headers)
        self.assertEqual(result.status_code, 200)
        self.assertTrue(any('short explanations' in e['fact'] for e in memory.load(self.db)))

    def test_status_never_calls_ephemeral_storage_durable(self):
        with patch.object(memory.os.path, 'ismount', return_value=False):
            status = memory.storage_status()
        self.assertFalse(status['durability_verified'])
        self.assertFalse(status['durable_mount_detected'])
        self.assertNotIn(self.path, json.dumps(status))

    def test_english_query_selects_arabic_and_compound_categories(self):
        entries = [
            {'category': 'العمل', 'fact': 'معلومة مهنية تجريبية', 'as_of': 'today'},
            {'category': 'الطموحات', 'fact': 'طموح تجريبي', 'as_of': 'today'},
            {'category': 'career_background', 'fact': 'Another synthetic job.', 'as_of': 'today'},
            {'category': 'health', 'fact': 'Unrelated synthetic health detail.', 'as_of': 'today'}]
        selected = profile_context(entries, QUESTION)
        self.assertEqual({e['category'] for e in selected}, {'العمل', 'الطموحات', 'career_background'})

    def test_private_memory_not_logged_on_provider_failure(self):
        self.import_profile(); self.fresh_conversation()
        with patch.object(m.TRANSPORT, 'open', side_effect=TimeoutError('Cedar Lab Juniper sensitive provider text')), self.assertLogs('moltbook', level='WARNING') as logs:
            response = self.client.post('/companion/messages', json={'content': QUESTION}, headers=self.headers)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('Cedar Lab', ' '.join(logs.output))
        self.assertNotIn('Juniper', ' '.join(logs.output))
        self.assertNotIn('Cedar Lab', response.get_data(as_text=True))
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
