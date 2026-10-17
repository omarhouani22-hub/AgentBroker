import base64
import json
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from flask import Flask
import moltbook as m
from clara_camera import validate_frame
from clara_advisor import references, advisor_context, ground_legal_output, validate_profile, ADVISOR_POLICY

# Bounded synthetic JPEG header, used only for validation/transport contract tests.
def frame(width=640,height=480):
    raw=b'\xff\xd8\xff\xc0\x00\x11\x08'+height.to_bytes(2,'big')+width.to_bytes(2,'big')+b'\x03\x01\x11\x00\x02\x11\x00\x03\x11\x00\xff\xd9'
    return 'data:image/jpeg;base64,'+base64.b64encode(raw).decode()

class ClaraPrivacyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.db=lambda:sqlite3.connect(self.temp.name+'/state.sqlite')
        self.app=Flask('clara-privacy')
        m.install_dialogue(self.app,self.db,lambda:None,lambda record:None)
        self.client=self.app.test_client()
    def tearDown(self): self.temp.cleanup()

    def test_saved_legal_text_has_provenance_and_no_live_claim(self):
        result=references('المادة 43 من نظام الموارد البشرية')
        self.assertEqual(result[0]['page'],25)
        self.assertIn('المادة', result[0]['text'])
        self.assertEqual(result[0]['extraction_quality'],'machine_extracted_unverified')
        self.assertTrue(result[0]['source_url'].startswith('https://spac.gov.jo/'))
        self.assertIn('13/8/2026',result[0]['title'])
        self.assertEqual(advisor_context('زميلتي ما سلمت علي',{})['legal_references'],[])

    def test_legal_unsupported_number_and_missing_citation_fail_closed(self):
        context=advisor_context('المادة 43 من نظام الموارد البشرية',{})|{'language':'ar'}
        for answer in ('لك حق مؤكد بالمادة 999 [L1]','المادة 43 تعطيك حقاً مؤكداً.','إجابة [L99]'):
            out=ground_legal_output(answer,context)
            self.assertIn('ما بتكفي',out)
        out=ground_legal_output('يحتاج تطبيق النص إلى قراءة شروطه [L1]',context)
        self.assertIn('ص. 25',out)
        self.assertIn('يحتاجان تحققاً',out)

    def test_private_profile_import_is_explicit_and_retrieval_is_relevant(self):
        entries=[{'category':'communication_preferences','fact':'يفضّل الحوار الصريح الودود.','as_of':'2026-10-17'},
                 {'category':'career العمل','fact':'يعمل عمر في سياسات الموارد البشرية.','as_of':'2026-10-17'},
                 {'category':'health','fact':'معلومة صحية خاصة فقط للسؤال الصحي.','as_of':'2026-10-17'}]
        self.assertEqual(self.client.post('/companion/profile',json={'entries':entries}).status_code,400)
        result=self.client.post('/companion/profile',json={'confirm_private_import':True,'entries':entries})
        self.assertEqual(result.json['entries'],3)
        owner=m.companion_state(m.dialogue_state(self.db))
        out=advisor_context('احكي عن عملي في الموارد البشرية',owner)
        self.assertTrue(any(e['category']=='career العمل' for e in out['owner_profile']))
        self.assertFalse(any(e['category']=='health' for e in out['owner_profile']))
        self.assertNotIn('owner_profile',self.client.get('/companion/advisor/status').json)
        with self.assertRaises(ValueError):validate_profile([{'category':'secret','fact':'password=not-allowed','as_of':'today'}])

    def test_camera_validation_rejects_remote_urls_oversize_and_bad_jpeg(self):
        self.assertEqual(validate_frame(frame()),frame())
        for value in ('https://example.com/photo.jpg','data:image/jpeg;base64,AAAA',frame(5000,5000),'data:image/jpeg;base64,'+'A'*360001):
            with self.assertRaises(ValueError):validate_frame(value)
        with patch.object(m,'free_dialogue_json') as generate:
            self.assertEqual(self.client.post('/companion/messages',json={'content':'Describe this','camera_image':'https://example.com/image'}).status_code,400)
            generate.assert_not_called()

    def test_camera_image_not_persisted_or_written_to_memory(self):
        captured=[]
        def answer(context):captured.append(context);return {'skip':False,'content':'I can see a synthetic test scene.'}
        with patch.object(m,'free_model_key',return_value='test'),patch.object(m,'free_dialogue_json',side_effect=answer),patch('mem0_memory.remember') as remember:
            result=self.client.post('/companion/messages',json={'content':'Describe this image','camera_image':frame(),'tone':'serious'})
        self.assertEqual(result.status_code,200)
        self.assertEqual(captured[0]['camera_image'],frame())
        self.assertEqual(captured[0]['tone'],'serious')
        self.assertNotIn('data:image',json.dumps(m.dialogue_state(self.db)))
        remember.assert_not_called()

    def test_provider_receives_one_frame_only_in_latest_turn(self):
        captured=[]
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,limit):return json.dumps({'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'skip':False,'content':'There is a blue object in the image.','lesson':''})}}]}).encode()
        def open_request(req,timeout):captured.append(json.loads(req.data));return Response()
        with patch.dict(os.environ,{'OPENROUTER_API_KEY':'test'},clear=True),patch.object(m.TRANSPORT,'open',side_effect=open_request):
            m.free_dialogue_json({'_companion':True,'conversation':[{'role':'user','content':'Describe this image'}],'camera_image':frame()})
        payload=captured[0]
        self.assertEqual(payload['model'],'openrouter/free')
        self.assertNotIn('data:image',payload['messages'][1]['content'])
        self.assertEqual(payload['messages'][-1]['content'][1]['image_url']['url'],frame())
        self.assertEqual(json.dumps(payload).count('data:image'),1)
        self.assertIn('not a live feed',payload['messages'][0]['content'])

    def test_english_tutoring_is_opt_in_and_does_not_claim_audio_assessment(self):
        self.assertIn('only when the owner requests',ADVISOR_POLICY)
        self.assertIn('speech-to-text transcript',ADVISOR_POLICY)

    def test_clara_app_shell_is_installable_and_private_apis_stay_protected(self):
        import app
        with patch.dict(os.environ,{'AGENT_ACCESS_TOKEN':'test-token'},clear=True),app.app.test_client() as client:
            shell=client.get('/clara/')
            self.assertEqual(shell.status_code,200)
            html=shell.get_data(as_text=True)
            self.assertIn('I am Clara, your AI assistant.',html)
            self.assertNotIn('tools-panel',html)
            self.assertIn('apple-mobile-web-app-capable',html)
            self.assertEqual(shell.headers['Cache-Control'],'no-store')
            manifest=client.get('/clara/manifest.webmanifest').json
            self.assertEqual(manifest['start_url'],'/clara/')
            self.assertEqual(manifest['display'],'standalone')
            for endpoint in ('/companion/messages','/companion/advisor/status','/companion/history/export','/companion/capabilities','/companion/speech/status'):
                self.assertEqual(client.get(endpoint).status_code,401)
            self.assertEqual(client.post('/companion/profile',json={'entries':[]}).status_code,401)
            self.assertEqual(client.post('/companion/speech',json={'text':'Hello'}).status_code,401)

class CompleteHistoryTests(unittest.TestCase):
    def test_archive_survives_context_rollover_and_is_idempotent(self):
        import clara_history
        with tempfile.TemporaryDirectory() as directory:
            db=lambda:sqlite3.connect(directory+'/history.sqlite')
            state=m.dialogue_state(db)
            owner=m.companion_state(state)
            for i in range(245):
                m.append_companion(owner,'user','Cedar publishing was my first project.' if i==0 else 'Different message number '+str(i))
                m.save_dialogue_state(db,state)
            self.assertEqual(clara_history.count(db),245)
            m.save_dialogue_state(db,state)
            self.assertEqual(clara_history.count(db),245)
            self.assertFalse(any('Cedar' in x['content'] for x in owner['archive']))
            recalled=clara_history.recall(db,'What was my Cedar publishing project?')
            self.assertIn('Cedar',recalled[0]['content'])
            self.assertEqual(len(clara_history.export(db)),245)
            cursor=clara_history.export(db)[239]['sequence']
            self.assertEqual(len(clara_history.export(db,after=cursor)),5)
            m.append_companion(owner,'user','Tell me about Cedar publishing.')
            context=m.companion_context(owner,'Reply',db=db)
            self.assertTrue(any('first project' in x['content'] for x in context['archived_private_conversation']))
