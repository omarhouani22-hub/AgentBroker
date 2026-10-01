import json
import os
import unittest
from unittest.mock import patch
import moltbook as m
import dialogue_quality as q


class ArabicDialogueTests(unittest.TestCase):
    def test_language_switch_and_product_names(self):
        for text, expected in [('كيف اطور AgentBroker باستخدام OpenRouter؟', 'ar'),
                               ('Please explain memory in English.', 'en')]:
            self.assertEqual(m.companion_language({'conversation':[{'role':'user','content':text}]}), expected)
        self.assertEqual(m.companion_language({'conversation':[{'role':'user','content':'اشرحلي الذاكرة'},
                                                                   {'role':'user','content':'👍'}]}), 'ar')
        self.assertEqual(m.companion_language({'language':'en','conversation':[{'role':'user','content':'اشرح'}]}), 'en')

    def test_arabic_memory_matches_diacritics_and_hamza_without_generic_overlap(self):
        history = [{'id':'one','role':'user','content':'أفضل أن أدرس إستراتيجيات الموارد البشرية.'},
                   {'id':'two','role':'user','content':'أنا في البيت على الهاتف.'}]
        owner = {'messages':[{'id':'three','role':'user','content':'شو حكيت عن استراتيجيات الموارد البشرية؟'}],
                 'archive':history}
        recalled = m.companion_context(owner, 'reply')['recalled_private_conversation']
        self.assertEqual(recalled, [{'role':'user','content':history[0]['content']}])
        self.assertEqual(owner['archive'], history)

    def test_wrong_language_repair_is_bounded_and_stays_free(self):
        good = 'أكيد، حفظ المعلومة يعني تقدر تكررها، وفهمها يعني تعرف تستخدمها بموقف جديد.'
        wrong = 'Memorizing information means recalling it; understanding means applying it in a new situation.'
        class Response:
            def __init__(self, text): self.text=text
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def read(self,count): return json.dumps({'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'skip':False,'content':self.text,'lesson':''})}}]}).encode()
        captured=[]
        def call(request, timeout):
            captured.append(json.loads(request.data))
            return Response(wrong if len(captured)==1 else good)
        with patch.dict(os.environ, {'OPENROUTER_API_KEY':'test-only'}, clear=True), patch.object(m.TRANSPORT,'open',side_effect=call):
            out=m.free_dialogue_json({'_companion':True,'language':'ar','conversation':[]})
        self.assertEqual(out['content'],good)
        self.assertEqual(out['_model'],'free_router')
        self.assertEqual(len(captured),2)
        self.assertTrue(all(p['model']=='openrouter/free' for p in captured))
        with patch.dict(os.environ, {'OPENROUTER_API_KEY':'test-only'}, clear=True), patch.object(m.TRANSPORT,'open',return_value=Response(wrong)) as transport:
            with self.assertRaises(m.DialogueLanguageError):
                m.free_dialogue_json({'_companion':True,'language':'ar'})
        self.assertEqual(transport.call_count,2)

    def test_public_and_specialist_requests_do_not_get_language_repair(self):
        with patch.object(m,'_dialogue_json',side_effect=ValueError('quota')) as generate:
            with self.assertRaises(ValueError): m.free_dialogue_json({'task':'comment'})
        self.assertEqual(generate.call_count,1)

    def test_smoke_check_detects_lost_memory_and_has_no_private_context(self):
        seen=[]
        def generate(context):
            seen.append(context)
            return {'content':'المعلومة موجودة في سياق التجربة فقط، وما بقدر أدعي ذاكرة خارج هالحوار.', '_model':'free_router'}
        result=q.evaluate(generate,m.companion_language,m.validate_companion_language)
        self.assertEqual(result['state'],'failed')
        self.assertFalse(result['cases'][1]['passed'])
        self.assertTrue(all(c['model']=='free' and not c.get('recalled_private_conversation') for c in seen))


if __name__=='__main__': unittest.main()
