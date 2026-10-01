import json
import unittest
from unittest.mock import patch
import moltbook as m
import trained_model as t


class TrainedRoutingTests(unittest.TestCase):
    def result(self, content='I am AgentBroker, your experimental trained assistant.'):
        return {'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'skip':False,'content':content,'lesson':''})}}]}

    def test_explicit_private_selection_routes_to_actual_weights(self):
        with patch.object(t,'configured',return_value=True), patch.object(t,'generate',return_value=self.result()) as generate:
            out=m.free_dialogue_json({'_companion':True,'model':'trained','language':'en'})
        self.assertEqual(out['_model'],'agentbroker_trained')
        generate.assert_called_once()

    def test_normal_and_public_dialogue_do_not_use_failed_candidate(self):
        for context in ({'_companion':True,'model':'free'},{'model':'trained'}):
            with patch.object(t,'configured',return_value=True), patch.object(t,'generate') as generate, patch.object(m,'_dialogue_json',return_value={'skip':True}):
                self.assertEqual(m.free_dialogue_json(context)['_model'],'free_router')
            generate.assert_not_called()

    def test_bad_or_unfinished_local_output_falls_back_with_true_provenance(self):
        for reason in ('Invalid local output', 'Incomplete local output'):
            def invoke(context,use_trained=False):
                if use_trained:
                    raise ValueError(reason)
                return {'skip':False,'content':'The free fallback answered this actual request.','lesson':''}
            with patch.object(t,'configured',return_value=True), patch.object(m,'_dialogue_json',side_effect=invoke):
                out=m.free_dialogue_json({'_companion':True,'model':'trained'})
            self.assertEqual(out['_model'],'free_router')

    def test_compaction_keeps_recent_order_without_mutating_history(self):
        history=[{'role':'user' if i%2==0 else 'assistant','content':str(i)+'x'*300} for i in range(10)]
        original=json.dumps(history)
        out=t.compact_context({'_companion':True,'conversation':history})
        self.assertEqual([m['content'][0] for m in out['conversation']],list('89'))
        self.assertTrue(all(len(m['content'])<=450 for m in out['conversation']))
        self.assertEqual(json.dumps(history),original)

    def test_long_user_question_is_not_silently_cut(self):
        with self.assertRaises(RuntimeError):
            t.compact_context({'_companion':True,'conversation':[{'role':'user','content':'x'*1000}]})


if __name__=='__main__':
    unittest.main()
