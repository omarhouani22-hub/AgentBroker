import json
import unittest
from unittest.mock import Mock, patch
import local_chat


class LocalReplyRecovery(unittest.TestCase):
    def test_slow_inference_gets_remaining_budget_and_next_turn_runs(self):
        process = Mock()
        process.poll.return_value = None
        health = Mock(status=200)
        health.__enter__ = Mock(return_value=health)
        health.__exit__ = Mock(return_value=False)
        reply = Mock()
        reply.__enter__ = Mock(return_value=reply)
        reply.__exit__ = Mock(return_value=False)
        reply.read.return_value = json.dumps({'choices':[{'finish_reason':'stop','message':{'content':'Hello, I am Clara.'}}]}).encode()
        opener = Mock()
        opener.open.side_effect = [health, TimeoutError('slow CPU'), health, reply]
        context = {'conversation':[{'role':'user','content':'Hello'}]}
        with patch.object(local_chat,'configured',return_value=True), patch.object(local_chat,'memory_headroom'), patch.object(local_chat.subprocess,'Popen',return_value=process), patch.object(local_chat,'build_opener',return_value=opener), patch.object(local_chat.time,'monotonic',return_value=0):
            with self.assertRaises(TimeoutError): local_chat.generate(context)
            self.assertFalse(local_chat.LOCK.locked())
            self.assertEqual(local_chat.generate(context)['content'],'Hello, I am Clara.')
        self.assertFalse(local_chat.LOCK.locked())
        self.assertEqual(process.terminate.call_count,2)
        self.assertEqual(opener.open.call_args_list[1].kwargs['timeout'],90)
        self.assertEqual(opener.open.call_args_list[3].kwargs['timeout'],90)


class LocalReplyBudget(unittest.TestCase):
    def test_sentence_cap_english_and_arabic(self):
        self.assertEqual(local_chat.complete_sentences('First sentence. Incomplete tail'),
                         'First sentence.')
        self.assertEqual(local_chat.complete_sentences('هذه جملة مكتملة؟ وهذه غير مكتملة'),
                         'هذه جملة مكتملة؟')

    def test_no_complete_sentence_rejected(self):
        self.assertEqual(local_chat.complete_sentences('An unfinished response'), '')

    def test_context_history_bounded(self):
        history = [{'role': 'user' if i % 2 == 0 else 'assistant',
                    'content': 'x' * 300} for i in range(12)]
        turns = local_chat.messages({'conversation': history})
        self.assertLessEqual(len(turns), 6)
        self.assertLessEqual(sum(len(t['content']) for t in turns[1:]), 1400)

    def test_reply_token_limit(self):
        self.assertEqual(local_chat.MAX_REPLY_TOKENS, 110)
