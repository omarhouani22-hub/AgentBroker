import json
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import moltbook as m


class Response:
    status = 200
    def __init__(self, value): self.value = value
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self, count): return self.value


def envelope(text, finish='stop'):
    return json.dumps({'choices':[{'finish_reason':finish,'message':{'content':text}}]}).encode()


class ResponseRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'OPENROUTER_API_KEY':'test-only','MOLTBOOK_API_KEY':'test-only'}, clear=True)
        self.env.start()
    def tearDown(self): self.env.stop()

    def test_json_repair_once_with_strict_free_routing(self):
        correct=json.dumps({'skip':False,'content':'This is a complete useful English answer about checking evidence.','lesson':''})
        captured=[]
        def call(req, timeout):
            captured.append(json.loads(req.data))
            return Response(envelope('plain malformed answer' if len(captured)==1 else correct))
        with patch.object(m.TRANSPORT,'open',side_effect=call):
            result=m.free_dialogue_json({'_companion':True,'language':'en'})
        self.assertEqual(result['_model'],'free_router')
        self.assertEqual(len(captured),2)
        self.assertTrue(all(p['model']=='openrouter/free' and p['provider']['require_parameters'] for p in captured))
        self.assertIn('previous output could not be decoded',captured[1]['messages'][0]['content'])

    def test_second_malformed_output_stops_and_does_not_leak_body(self):
        with patch.object(m.TRANSPORT,'open',return_value=Response(envelope('private body'))) as call:
            with self.assertRaisesRegex(m.ModelOutputError,'model_output_not_json'):
                m.free_dialogue_json({'_companion':True,'language':'en'})
        self.assertEqual(call.call_count,2)

    def test_wire_failure_and_quota_are_not_retried_as_formatting(self):
        for raw,category in [(b'<html>private body</html>','free_router_response_not_json'),
                             (json.dumps({'error':{'code':429,'message':'private body'}}).encode(),'free_router_error')]:
            with patch.object(m.TRANSPORT,'open',return_value=Response(raw)) as call:
                with self.assertRaises(m.RemoteResponseError) as error:
                    m.free_dialogue_json({'_companion':True,'language':'en'})
            self.assertEqual(error.exception.category,category)
            self.assertNotIn('private body',str(error.exception))
            self.assertEqual(call.call_count,1)

    def test_fenced_json_bom_is_decoded_but_multiple_objects_are_rejected(self):
        self.assertEqual(m.model_object('\ufeff```JSON\n{"skip":true}\n```'),{'skip':True})
        with self.assertRaises(m.ModelOutputError): m.model_object('{"skip":true}{"skip":false}')
        with self.assertRaises(m.ModelOutputError): m.model_object('[{"skip":true}]')

    def test_incomplete_model_output_cannot_be_repaired_or_published(self):
        with patch.object(m.TRANSPORT,'open',return_value=Response(envelope('{"skip":true}',finish='length'))) as call:
            with self.assertRaisesRegex(ValueError,'Incomplete free model response'):
                m.free_dialogue_json({'task':'comment'})
        self.assertEqual(call.call_count,1)

    def test_moltbook_http_keeps_safe_status(self):
        from urllib.error import HTTPError
        with patch.object(m.TRANSPORT,'open',side_effect=HTTPError('https://www.moltbook.com/api/v1/posts/gone',404,'Not found',{},None)):
            with self.assertRaises(m.RemoteResponseError) as error: m.api('GET','/posts/gone')
        self.assertEqual(error.exception.code,404)
        self.assertEqual(str(error.exception),'moltbook_http_error')

    def test_removed_thread_does_not_block_live_feed(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=lambda:sqlite3.connect(tmp+'/state.sqlite')
            state=m.dialogue_state(db)
            state['cycle']=1
            state['actions']=[{'post_id':'dead-thread','status':'completed','kind':'comment','key':'old'}]
            calls=[]
            def api(method,path,payload=None,query=None):
                calls.append(path)
                if path=='/home':return {'activity_on_your_posts':[]}
                if path=='/posts/dead-thread':raise m.RemoteResponseError('moltbook_http_error',404)
                if path=='/posts':return {'posts':[]}
                raise AssertionError(path)
            with patch.object(m,'own_profile',return_value={}),patch.object(m,'api',side_effect=api),patch.object(m,'improve_memory'),patch.object(m,'free_dialogue_json',return_value={'skip':True}):
                result=m.run_dialogue(db,state,lambda x:None)
            self.assertIn('/posts',calls)
            self.assertEqual(result['status'],'idle_no_useful_contribution')

    def test_failed_cycle_recovery_cooldown_and_uncertain_write_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=lambda:sqlite3.connect(tmp+'/state.sqlite')
            state=m.dialogue_state(db)
            state.update(status='read_failed',last_check=1000)
            with patch('time.time',return_value=1100),patch.object(m,'own_profile') as profile:
                m.run_dialogue(db,state,lambda x:None)
                profile.assert_not_called()
            state['actions']=[{'status':'uncertain'}]
            with patch('time.time',return_value=2000),patch.object(m,'own_profile') as profile:
                result=m.run_dialogue(db,state,lambda x:None)
                profile.assert_not_called()
                self.assertEqual(result['status'],'attention_required')

if __name__=='__main__':unittest.main()
