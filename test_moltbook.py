import json
import os
import unittest
from unittest.mock import patch

from flask import Flask
import moltbook


class MoltbookTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        moltbook.install_routes(app)
        self.client = app.test_client()

    def test_no_key_makes_no_request(self):
        with patch.dict(os.environ, {'MOLTBOOK_API_KEY': ''}), patch.object(moltbook.TRANSPORT, 'open') as open_:
            self.assertFalse(self.client.get('/moltbook/status').json['connected'])
            self.assertEqual(self.client.get('/moltbook/research?q=agents').status_code, 502)
            open_.assert_not_called()

    def test_search_preserves_provenance_and_blocks_redirect(self):
        class Reply:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, n):
                if 'status' in calls[-1].full_url:
                    return b'{"status":"claimed"}'
                return json.dumps({'success': True, 'results': [
                    {'id': 'a-b1', 'type': 'post', 'title': 'Memory practice',
                     'content': 'A' * 100, 'author': {'name': 'AnotherAgent'}}]}).encode()
        calls = []
        def open_(req, timeout):
            calls.append(req)
            return Reply()
        with patch.dict(os.environ, {'MOLTBOOK_API_KEY': 'test-key'}), patch.object(moltbook.TRANSPORT, 'open', side_effect=open_), patch.object(moltbook, 'collect_feedback', return_value=[]):
            notes = moltbook.research('agent memory')
        self.assertEqual(notes[0]['url'], 'https://www.moltbook.com/post/a-b1')
        self.assertEqual(notes[0]['author'], 'AnotherAgent')
        self.assertTrue(all(req.full_url.startswith('https://www.moltbook.com/api/v1/') for req in calls))
        self.assertTrue(all(req.get_header('Authorization') == 'Bearer test-key' for req in calls))

    def test_unclaimed_agent_does_not_publish(self):
        with patch.object(moltbook, 'ready', return_value=False), patch.object(moltbook, 'api') as api:
            result = self.client.post('/moltbook/posts', json={'title': 'AgentBroker intro', 'content': 'We are an AI agent project.'})
        self.assertEqual(result.status_code, 409)
        api.assert_not_called()

    def test_owner_email_not_echoed_or_logged(self):
        with patch.object(moltbook, 'api', return_value={'success': True}) as api:
            result = self.client.post('/moltbook/owner-email', json={'email': 'owner@example.com'})
        self.assertEqual(result.status_code, 200)
        self.assertNotIn('owner@example.com', result.get_data(as_text=True))
        api.assert_called_once_with('POST', '/agents/me/setup-owner-email', {'email': 'owner@example.com'})

    def test_wrong_identity_blocks_community_actions(self):
        with patch.object(moltbook, 'api', return_value={'agent': {'name': 'AnotherAgent'}}) as api:
            with self.assertRaises(ValueError): moltbook.own_profile()
        self.assertEqual(api.call_count, 1)

    def test_existing_intro_never_posts_again(self):
        profile = {'recentPosts': [{'title': moltbook.INTRO_TITLE, 'id': 'already-published', 'verification_status': 'verified'}]}
        with patch.object(moltbook, 'own_profile', return_value=profile), patch.object(moltbook, 'api') as api:
            moltbook.ensure_introduction(Flask('intro'))
        api.assert_not_called()

    def test_obfuscated_arithmetic_and_ambiguous_challenges(self):
        self.assertEqual(moltbook.challenge_answer('A] lO^bSt-Er S[wImS aT/ tW]eNn-Tyy mE^tE[rS aNd] SlO/wS bY^ fI[vE'), '15.00')
        self.assertIsNone(moltbook.challenge_answer('twenty plus five minus two'))
        with patch.object(moltbook, 'api') as api:
            self.assertFalse(moltbook.verify_content({'post': {'verification': {'challenge_text': 'unclear challenge'}}}, 'post'))
        api.assert_not_called()

    def test_feedback_reply_only_once_and_no_paid_calls(self):
        profile = {'recentComments': []}
        candidate = ('post-1', 'comment-1', 'source quality', 'checkable citations')
        with patch.object(moltbook, 'LAST_REPLY_DAY', None), patch.object(moltbook, 'api', return_value={'comment': {'id': 'reply-1'}}) as api:
            moltbook.respond_to_feedback(profile, candidate)
            moltbook.respond_to_feedback(profile, candidate)
        self.assertEqual(api.call_count, 1)
        self.assertEqual(api.call_args.args[:2], ('POST', '/posts/post-1/comments'))


if __name__ == '__main__':
    unittest.main()
