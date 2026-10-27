import json
import unittest
from unittest.mock import patch
import local_chat


class ResponseQuality(unittest.TestCase):
    def test_first_person_refers_to_user(self):
        turns = local_chat.messages({'conversation': [{'role':'user', 'content':'How can I improve my focus?'}]})
        self.assertIn("user's actual question", turns[0]['content'])
        self.assertEqual(turns[-1]['content'], 'How can I improve my focus?')

    def test_rejects_self_focused_answer_but_accepts_useful_answer(self):
        class Process:
            def poll(self): return None
            def terminate(self): pass
            def wait(self, timeout): pass
        class Response:
            status = 200
            def __init__(self, text): self.text = text
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, size):
                return json.dumps({'choices':[{'finish_reason':'stop','message':{'content':self.text}}]}).encode()
        class Opener:
            def __init__(self, text): self.text = text
            def open(self, request, timeout): return Response(self.text)
        context = {'conversation':[{'role':'user','content':'How can I improve my focus?'}]}
        with patch.object(local_chat, 'configured', return_value=True), patch.object(local_chat, 'memory_headroom'), patch.object(local_chat.subprocess, 'Popen', return_value=Process()):
            with patch.object(local_chat, 'build_opener', return_value=Opener("As an AI, I cannot improve my own focus.")):
                with self.assertRaises(ValueError): local_chat.generate(context)
            with patch.object(local_chat, 'build_opener', return_value=Opener("Try one short focused work session, then take a break.")):
                self.assertIn('focused', local_chat.generate(context)['content'])

if __name__ == '__main__': unittest.main()
