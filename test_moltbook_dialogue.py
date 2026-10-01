import json
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import moltbook as m


class DialogueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = lambda: sqlite3.connect(self.temp.name + '/state.sqlite')
        self.state = m.dialogue_state(self.db)
        self.state['cycle'] = 1
        self.writes = []
        self.notes = []
        self.post = {'id': 'other-post', 'author': {'name': 'other_agent'},
                     'title': 'Evidence and persistent memory',
                     'content': 'A remembered claim can be wrong. We need evidence and a reproducible comparison before treating it as an improvement.'}
        self.env = patch.dict(os.environ, {'OPENROUTER_API_KEY': 'test-only'}, clear=True)
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def api(self, method, path, payload=None, query=None):
        if method == 'POST':
            self.writes.append((path, payload))
            return {'comment': {'id': 'remote-comment'}, 'post': {'id': 'remote-post'}}
        if path == '/home': return {'activity_on_your_posts': []}
        if path == '/posts': return {'posts': [self.post]}
        if path.endswith('/comments'): return {'comments': []}
        return {'post': self.post}

    def run_cycle(self, generated):
        with patch.object(m, 'own_profile', return_value={}), patch.object(m, 'api', side_effect=self.api), patch.object(m, 'free_dialogue_json', return_value=generated):
            return m.run_dialogue(self.db, self.state, self.notes.append)

    def test_missing_free_key_never_calls_paid_or_moltbook(self):
        with patch.dict(os.environ, {'DEEPSEEK_API_KEY': 'paid-key'}, clear=True), patch.object(m, 'api') as api:
            result = m.run_dialogue(self.db, self.state, self.notes.append)
        self.assertEqual(result['status'], 'free_model_key_required')
        api.assert_not_called()

    def test_comment_is_generated_and_remembered(self):
        result = self.run_cycle({'skip': False, 'content': 'Could you describe the comparison that changed your confidence in this claim?', 'lesson': 'Treat memory entries as hypotheses; test retrieval accuracy before adoption.'})
        self.assertEqual(result['status'], 'published')
        self.assertEqual(self.writes[0][0], '/posts/other-post/comments')
        self.assertEqual(len(self.notes), 1)
        self.assertIn('hypotheses', self.notes[0]['output'])
        self.assertEqual(m.dialogue_state(self.db)['actions'][0]['remote_id'], 'remote-comment')

    def test_periodic_cycle_starts_original_discussion(self):
        self.state['cycle'] = 0
        self.run_cycle({'skip': False, 'title': 'What would disprove your memory policy?', 'content': 'What evidence would make you discard a remembered rule? I would compare several tasks before and after the change.', 'lesson': ''})
        self.assertEqual(self.writes[0][0], '/posts')
        self.assertEqual(self.writes[0][1]['title'], 'What would disprove your memory policy?')

    def test_skip_does_not_publish(self):
        result = self.run_cycle({'skip': True})
        self.assertEqual(result['status'], 'idle_no_useful_contribution')
        self.assertEqual(self.writes, [])

    def test_uncertain_write_is_not_retried(self):
        self.state['actions'] = [{'key': 'comment:x', 'status': 'uncertain'}]
        with patch.object(m, 'api') as api:
            result = m.run_dialogue(self.db, self.state, self.notes.append)
        api.assert_not_called()
        self.assertEqual(result['status'], 'attention_required')

    def test_quota_failure_does_not_publish(self):
        with patch.object(m, 'own_profile', return_value={}), patch.object(m, 'api', side_effect=self.api), patch.object(m, 'free_dialogue_json', side_effect=ValueError('quota')):
            with self.assertRaises(ValueError):
                m.run_dialogue(self.db, self.state, self.notes.append)
        self.assertEqual(self.writes, [])
        self.assertGreater(m.dialogue_state(self.db)['last_check'], 0)

    def test_reply_target_is_preserved(self):
        self.state['actions'] = [{'key': 'post:mine', 'kind': 'post', 'status': 'published', 'post_id': 'mine'}]
        own = {'id': 'mine', 'author': {'name': 'agent_broker'}}
        target = {'id': 'c1', 'author': {'name': 'other'}, 'content': 'Here is a concrete alternative to your memory design, with evaluation before adoption and review afterwards.'}
        candidate = m.select_dialogue_candidate([(own, [target])], self.state)
        self.assertEqual(candidate[1], 'c1')
        self.state['actions'].append({'key': 'reply:c1', 'status': 'published'})
        self.assertIsNone(m.select_dialogue_candidate([(own, [target])], self.state))

    def test_provider_request_is_pinned_to_free_router(self):
        captured = {}
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, count):
                return json.dumps({'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps({'skip': True})}}]}).encode()
        def open_request(request, timeout):
            captured['url'] = request.full_url
            captured['payload'] = json.loads(request.data)
            return Response()
        with patch.object(m.TRANSPORT, 'open', side_effect=open_request):
            m.free_dialogue_json({'task': 'comment'})
        self.assertEqual(captured['url'], 'https://openrouter.ai/api/v1/chat/completions')
        self.assertEqual(captured['payload']['model'], 'openrouter/free')
        self.assertNotIn('models', captured['payload'])

    def test_model_credential_text_is_rejected(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, count):
                output = {'skip': False, 'content': 'Here is an API key: sk-abcdefghijklmnopqrstuvwxyz123456', 'lesson': ''}
                return json.dumps({'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(output)}}]}).encode()
        with patch.object(m.TRANSPORT, 'open', return_value=Response()):
            with self.assertRaises(ValueError):
                m.free_dialogue_json({'task': 'comment'})

    def test_public_labels_removed_without_losing_internal_sources(self):
        self.assertEqual(m.clean_public_dialogue('Compare evidence [S1, S2] and memory [M1]. S3 Is it repeatable?'),
                         'Compare evidence and memory. Is it repeatable?')


class ImprovementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = lambda: sqlite3.connect(self.temp.name + '/state.sqlite')
        self.state = m.dialogue_state(self.db)
        self.state['lessons'] = [{'id': 'one', 'output': 'Unverified memory lesson: evaluate relevance before use.',
                                 'sources': [{'url': 'https://www.moltbook.com/post/one'}]}]
        self.good = {'relevance_weight': 4, 'deduplicate': True, 'max_per_source': 1}

    def tearDown(self):
        self.temp.cleanup()

    def test_improvement_promotes_only_measured_gain(self):
        with patch.object(m, 'free_dialogue_json', return_value={'policy': self.good, 'rationale': 'Prefer relevant and diverse memories.'}):
            m.improve_memory(self.db, self.state)
        learning = self.state['improvement']
        self.assertEqual(learning['status'], 'adopted')
        self.assertGreater(learning['history'][0]['after'], learning['history'][0]['before'])
        self.assertEqual(learning['policy'], self.good)
        self.assertEqual(learning['previous_policy'], m.BASE_MEMORY_POLICY)

    def test_worse_candidate_is_rejected(self):
        learning = m.improvement_state(self.state)
        learning['policy'] = dict(self.good)
        with patch.object(m, 'free_dialogue_json', return_value={'policy': dict(m.BASE_MEMORY_POLICY), 'rationale': 'Test a recency-only alternative.'}):
            m.improve_memory(self.db, self.state)
        self.assertEqual(learning['status'], 'rejected')
        self.assertEqual(learning['policy'], self.good)

    def test_failed_experiment_not_repeated_same_day(self):
        with patch.object(m, 'free_dialogue_json', side_effect=ValueError('quota')) as model:
            m.improve_memory(self.db, self.state)
            m.improve_memory(self.db, self.state)
        self.assertEqual(model.call_count, 1)
        self.assertEqual(self.state['improvement']['policy'], m.BASE_MEMORY_POLICY)
        self.assertEqual(self.state['improvement']['status'], 'failed_policy_unchanged')

    def test_restore_rejects_unbounded_policy(self):
        m.improvement_state(self.state)['policy']['relevance_weight'] = 500
        with self.assertRaises(ValueError):
            m.validate_dialogue_state(self.state)

    def test_selected_memory_uses_relevance_not_only_recency(self):
        rows = [{'id': 'good', 'output': 'employee onboarding evidence',
                 'sources': [{'url': 'good'}]}]
        rows += [{'id': str(i), 'output': 'irrelevant weather catalog ' + str(i),
                  'sources': [{'url': str(i)}]} for i in range(5)]
        selected = m.select_memory('employee onboarding', rows, self.good)
        self.assertEqual(selected[0]['id'], 'good')

    def test_proposer_sees_aggregate_scores_not_holdout_content(self):
        with patch.object(m, 'free_dialogue_json', return_value={'policy': self.good, 'rationale': 'Prefer relevant and diverse memories.'}) as model:
            m.improve_memory(self.db, self.state)
        context = model.call_args.args[0]
        self.assertIn('aggregate_retrieval_scores', context)
        self.assertNotIn('cases', context)
        self.assertNotIn('battery storage', json.dumps(context))


class CompanionTests(unittest.TestCase):
    def setUp(self):
        from flask import Flask
        self.temp = tempfile.TemporaryDirectory()
        self.db = lambda: sqlite3.connect(self.temp.name + '/state.sqlite')
        self.app = Flask('companion-tests')
        m.install_dialogue(self.app, self.db, lambda: None, lambda record: None)
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp.cleanup()

    def test_initiates_once_daily_without_public_post(self):
        state = m.dialogue_state(self.db)
        generated = {'skip': False, 'content': 'خلينا نحكي عن فكرة جديدة: شو مهارة بسيطة تحب تتعلمها هالأسبوع؟', 'lesson': ''}
        with patch.object(m, 'free_model_key', return_value='test'), patch.object(m, 'free_dialogue_json', return_value=generated) as model, patch.object(m, 'api') as public:
            m.initiate_companion(self.db, state)
            m.initiate_companion(self.db, state)
        self.assertEqual(model.call_count, 1)
        public.assert_not_called()
        self.assertTrue(state['companion']['messages'][0]['initiated'])

    def test_missing_key_never_generates(self):
        with patch.object(m, 'free_model_key', return_value=''), patch.object(m, 'free_dialogue_json') as model:
            result = self.client.post('/companion/check', json={})
        self.assertFalse(result.json['model_configured'])
        model.assert_not_called()

    def test_reply_does_not_publish_private_conversation(self):
        generated = {'skip': False, 'content': 'خلينا نفكر فيها خطوة خطوة. شو النتيجة اللي بتتمنى توصل إلها؟', 'lesson': ''}
        with patch.object(m, 'free_model_key', return_value='test'), patch.object(m, 'free_dialogue_json', return_value=generated), patch.object(m, 'api') as public:
            result = self.client.post('/companion/messages', json={'content': 'بدي أطور مهاراتي بالشغل'})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(len(result.json['messages']), 2)
        public.assert_not_called()
        self.assertEqual(m.dialogue_state(self.db)['lessons'], [])

    def test_quota_prevents_more_free_calls(self):
        state = m.dialogue_state(self.db)
        c = m.companion_state(state)
        c.update(reply_day=m.datetime.now(m.timezone.utc).date().isoformat(), reply_calls=12)
        m.save_dialogue_state(self.db, state)
        with patch.object(m, 'free_model_key', return_value='test'), patch.object(m, 'free_dialogue_json') as model:
            result = self.client.post('/companion/messages', json={'content': 'Hello'})
        self.assertEqual(result.status_code, 429)
        model.assert_not_called()

    def test_no_new_topic_over_unanswered_owner_message(self):
        state = m.dialogue_state(self.db)
        m.append_companion(m.companion_state(state), 'user', 'Let us finish this conversation.')
        with patch.object(m, 'free_model_key', return_value='test'), patch.object(m, 'free_dialogue_json') as model:
            m.initiate_companion(self.db, state)
        model.assert_not_called()


if __name__ == '__main__':
    unittest.main()
