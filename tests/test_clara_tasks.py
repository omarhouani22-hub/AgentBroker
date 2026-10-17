import json
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from flask import Flask
import clara_tasks as tasks
import clara_advisor as advisor
import clara_speech as speech
import moltbook as m

class ClaraTasks(unittest.TestCase):
    def setUp(self):
        local = patch('local_speech.configured', return_value=False)
        local.start(); self.addCleanup(local.stop)
        self.temp=tempfile.TemporaryDirectory();self.db=lambda:sqlite3.connect(self.temp.name+'/state.sqlite')
        self.app=Flask('tasks');m.install_dialogue(self.app,self.db,lambda:None,lambda r:None)
        from clara_documents import install_routes
        install_routes(self.app,self.db);speech.install_routes(self.app,self.db);self.client=self.app.test_client()
    def tearDown(self):self.temp.cleanup()
    def test_content_plan_is_saved_as_private_text_not_claimed_as_video(self):
        contexts=[]
        def generate(c):contexts.append(c);return {'skip':False,'content':'Draft video plan: title, script, shots and description. Rendering is not connected.'}
        with patch.object(m,'free_model_key',return_value='test'),patch.object(m,'free_dialogue_json',side_effect=generate),patch('mem0_memory.remember',return_value=False):
            response=self.client.post('/companion/messages',json={'content':'Make a YouTube video about teamwork','tone':'frisky','appearance':{'scene':'beach','outfit':'summer','framing':'close','pose':'seated'}})
        self.assertEqual(response.status_code,200);self.assertEqual(response.json['content_task'],'youtube_video');self.assertFalse(response.json['capabilities']['video_rendering'])
        self.assertIn('No video-rendering',contexts[0]['task']);self.assertEqual(contexts[0]['ui_appearance']['scene'],'beach');self.assertEqual(contexts[0]['tone'],'frisky')
        download=self.client.get(response.json['download']);self.assertEqual(download.status_code,200);self.assertIn(b'Draft video plan',download.data)
        caps=self.client.get('/companion/capabilities').json;self.assertFalse(caps['external_account_tools_connected']);self.assertFalse(caps['content_tasks']['facebook_page']['page_creation'])
    def test_bad_presets_fail_before_model(self):
        with patch.object(m,'free_dialogue_json') as generate:
            for payload in ({'appearance':{'scene':'https://evil.test','outfit':'summer'}},{'appearance':{'scene':'beach','outfit':'summer','pose':'standing'}},{'content_task':'publish_facebook'}):
                self.assertEqual(self.client.post('/companion/messages',json={'content':'Hello',**payload}).status_code,400)
            generate.assert_not_called()
        self.assertEqual(advisor.validate_appearance({'scene':'studio','outfit':'business'})['framing'],'wide')
        self.assertEqual(tasks.infer_task('اكتبي محتوى صفحة فيسبوك'),'facebook_page')
        self.assertEqual(tasks.infer_task('Do you know Facebook pages?'),'chat')
    def test_neural_voice_cannot_bill_by_default_or_with_key_alone(self):
        with patch.dict(os.environ,{'CLARA_TTS_API_KEY':'test-only-key'},clear=True),patch.object(m.TRANSPORT,'open') as remote:
            self.assertFalse(self.client.get('/companion/speech/status').json['available'])
            self.assertEqual(self.client.post('/companion/speech',json={'text':'Hello'}).status_code,503);remote.assert_not_called()
    def test_neural_voice_requires_cap_and_never_retries(self):
        with patch.dict(os.environ,{'CLARA_TTS_API_KEY':'test','CLARA_TTS_BILLING_APPROVED':'true','CLARA_TTS_DAILY_CHAR_LIMIT':'10'},clear=True),patch.object(m.TRANSPORT,'open',side_effect=TimeoutError) as remote:
            self.assertTrue(self.client.get('/companion/speech/status').json['available'])
            self.assertEqual(self.client.post('/companion/speech',json={'text':'Hello'}).status_code,503)
            self.assertEqual(remote.call_count,1)
            self.assertEqual(self.client.post('/companion/speech',json={'text':'Too long for cap'}).status_code,429)
            self.assertEqual(remote.call_count,1)
    def test_neural_voice_transport_contract_and_private_audio(self):
        captured=[]
        class Remote:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,n):return b'ID3synthetic-test-mp3'
        def send(req,timeout):captured.append(req);return Remote()
        with patch.dict(os.environ,{'CLARA_TTS_API_KEY':'test','CLARA_TTS_BILLING_APPROVED':'true','CLARA_TTS_DAILY_CHAR_LIMIT':'100'},clear=True),patch.object(m.TRANSPORT,'open',side_effect=send):
            reply=self.client.post('/companion/speech',json={'text':'مرحبا عمر'})
        self.assertEqual(reply.status_code,200);self.assertEqual(reply.headers['Cache-Control'],'no-store');self.assertEqual(reply.mimetype,'audio/mpeg')
        payload=json.loads(captured[0].data);self.assertEqual(payload['voice'],'coral');self.assertEqual(payload['model'],'gpt-4o-mini-tts');self.assertEqual(captured[0].full_url,'https://api.openai.com/v1/audio/speech')

class PresentationCommands(unittest.TestCase):
    setUp=ClaraTasks.setUp
    tearDown=ClaraTasks.tearDown
    def test_approach_command_works_without_model_and_does_not_spend_quota(self):
        with patch.object(m,'dialogue_model_configured',return_value=False),patch.object(m,'free_dialogue_json') as generate:
            response=self.client.post('/companion/messages',json={'content':'تعالي لعندي','presentation_action':'closer','appearance':{'scene':'studio','outfit':'business','framing':'close','pose':'standing'}})
        self.assertEqual(response.status_code,200);self.assertTrue(response.json['presentation_applied']);self.assertIn('بدون تكبير',response.json['messages'][-1]['content']);generate.assert_not_called()
        owner=m.companion_state(m.dialogue_state(self.db));self.assertEqual(owner.get('reply_calls',0),0)
        self.assertEqual(self.client.post('/companion/messages',json={'content':'Come closer','presentation_action':'closer','appearance':{'scene':'studio','outfit':'business','framing':'wide'}}).status_code,400)

    def test_natural_motion_request_is_honest_and_does_not_call_provider(self):
        with patch.object(m,'dialogue_model_configured',return_value=False),patch.object(m,'free_dialogue_json') as generate:
            response=self.client.post('/companion/messages',json={'content':'Come here','presentation_action':'motion_unavailable','appearance':{'scene':'studio','outfit':'business','framing':'wide','pose':'seated'}})
        self.assertEqual(response.status_code,200);self.assertIn('not available',response.json['messages'][-1]['content']);generate.assert_not_called()
        self.assertEqual(m.companion_state(m.dialogue_state(self.db))['appearance']['framing'],'wide')

    def test_provider_quota_is_distinct_localized_and_does_not_expose_remote_body(self):
        from urllib.error import HTTPError
        for text,expected in [('مرحبا','حد الاستخدام'),('Hello','usage or request limit')]:
            with patch.object(m,'dialogue_model_configured',return_value=True),patch.object(m,'free_dialogue_json',side_effect=HTTPError('https://openrouter.ai',429,'private provider detail',None,None)) as generate:
                response=self.client.post('/companion/messages',json={'content':text})
            self.assertEqual(response.status_code,429);self.assertEqual(response.json['error_code'],'provider_rate_limited');self.assertIn(expected,response.json['error']);self.assertNotIn('private provider detail',response.json['error']);self.assertEqual(generate.call_count,1)
            self.assertEqual(self.client.get('/companion/messages').json['status'],'provider_rate_limited')

class FreeTransportRetry(unittest.TestCase):
    def test_private_503_retries_only_the_free_model_once(self):
        from urllib.error import HTTPError
        with patch.object(m,'_dialogue_json',side_effect=[HTTPError('https://openrouter.ai',503,'Unavailable',None,None),{'content':'A valid answer.','skip':False}]) as call:
            self.assertEqual(m.free_dialogue_json({'_companion':True,'language':'en'})['content'],'A valid answer.')
            self.assertEqual(call.call_count,2)
    def test_auth_and_quota_and_public_failures_do_not_retry(self):
        from urllib.error import HTTPError
        for code,context in [(401,{'_companion':True}),(429,{'_companion':True}),(503,{})]:
            with patch.object(m,'_dialogue_json',side_effect=HTTPError('https://openrouter.ai',code,'Failed',None,None)) as call:
                with self.assertRaises(HTTPError):m.free_dialogue_json(context)
                self.assertEqual(call.call_count,1)
