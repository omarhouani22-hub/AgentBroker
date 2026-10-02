import json
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

import app
import team_provider


class QuestionLengthTest(unittest.TestCase):
    def test_long_question_and_answer_preserved(self):
        question = ('Explain workforce planning بالتفصيل مع أمثلة. ' * 500) + ' succession'
        answer = 'Detailed answer [S1]. ' * 700
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
            'AGENT_DB_PATH': directory + '/test.db', 'AGENT_ACCESS_TOKEN': 'x' * 32,
            'DEEPSEEK_API_KEY': 'test', 'TAVILY_API_KEY': 'test'}), \
            patch('app.search_web', return_value=[{'title': 'Source', 'url': 'https://example.com', 'content': 'Evidence'}]) as search, \
            patch('app.model_call', return_value={'content': answer}) as model:
            client = app.app.test_client()
            response = client.post('/runs', json={'goal': question, 'include_sources': True}, headers={'Authorization': 'Bearer ' + 'x' * 32})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json['output'], answer)
            self.assertEqual(response.json['goal'], question)
            search.assert_called_once_with(question)
            self.assertEqual(json.loads(model.call_args.args[0][-1]['content'])['goal'], question)
            self.assertEqual(client.post('/runs', json={'goal': '  '}, headers={'Authorization': 'Bearer ' + 'x' * 32}).status_code, 400)

    def test_search_query_is_bounded_without_cutting_model_prompt(self):
        prompt = 'planning ' * 1000 + 'succession leadership تعاقب وظيفي'
        query = app.search_query(prompt)
        self.assertLessEqual(len(query), 400)
        self.assertIn('succession', query)
        self.assertIn('تعاقب', query)
        self.assertEqual(app.search_query('short question'), 'short question')

    def test_both_provider_paths_allow_longer_answers(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps({'choices': [{'finish_reason': 'stop', 'message': {'content': 'answer'}}]}).encode()
        with patch.dict(os.environ, {'DUAL_MODEL_MODE': 'false', 'DEEPSEEK_API_KEY': 'test'}), patch.object(app.model_transport, 'open', return_value=response) as single:
            app.model_call([{'role': 'user', 'content': 'question'}])
            self.assertEqual(json.loads(single.call_args.args[0].data)['max_tokens'], 8192)
        with patch('team_provider.urlopen', return_value=response) as dual:
            team_provider._call('https://example.com', 'test', 'test-model', [], 'max_completion_tokens')
            self.assertEqual(json.loads(dual.call_args.args[0].data)['max_completion_tokens'], 8192)


if __name__ == '__main__':
    unittest.main()

