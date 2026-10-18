import io
import os
import unittest
import wave
from unittest.mock import patch
import local_chat
import local_recognition
import moltbook as m
from tests import test_clara_tasks as fixtures


class InternalRouting(unittest.TestCase):
    setUp = fixtures.ClaraTasks.setUp
    tearDown = fixtures.ClaraTasks.tearDown

    def test_local_selection_never_falls_back_even_when_external_key_exists(self):
        with patch.dict(os.environ, {'CLARA_LOCAL_ONLY':'true','OPENROUTER_API_KEY':'unused'}), \
             patch.object(local_chat,'generate',side_effect=RuntimeError), \
             patch.object(m,'_dialogue_json') as external:
            with self.assertRaises(RuntimeError):
                m.free_dialogue_json({'_companion':True,'conversation':[{'role':'user','content':'Hello'}]})
            external.assert_not_called()

    def test_local_replies_bypass_the_old_daily_quota_and_hosted_memory(self):
        state = m.dialogue_state(self.db)
        owner = m.companion_state(state)
        from datetime import datetime,timezone
        owner.update(reply_calls=12, reply_day=datetime.now(timezone.utc).date().isoformat())
        m.save_dialogue_state(self.db,state)
        answer = {'skip':False,'content':'I am Clara. How can I help you today?', 'lesson':'','_model':'agentbroker_local'}
        with patch.dict(os.environ,{'CLARA_LOCAL_ONLY':'true'}), \
             patch.object(local_chat,'configured',return_value=True), \
             patch.object(local_chat,'generate',return_value=answer), \
             patch.object(m.TRANSPORT,'open') as external, \
             patch('mem0_memory.recall') as recall, patch('mem0_memory.remember') as remember:
            for _ in range(15):
                response = self.client.post('/companion/messages',json={'content':'Hello'})
                self.assertEqual(response.status_code,200)
                self.assertEqual(response.json['messages'][-1]['model'],'agentbroker_local')
            external.assert_not_called(); recall.assert_not_called(); remember.assert_not_called()
        self.assertEqual(m.companion_state(m.dialogue_state(self.db))['reply_calls'],12)

    def test_documents_cannot_bypass_the_internal_only_setting(self):
        import clara_documents
        with patch.dict(os.environ,{'CLARA_LOCAL_ONLY':'true'}), patch.object(m.TRANSPORT,'open') as external:
            with self.assertRaises(ValueError): clara_documents.model_plan({},'Review','review','en')
            external.assert_not_called()

    def test_public_dialogue_never_uses_private_local_conversation(self):
        with patch.dict(os.environ, {'CLARA_LOCAL_ONLY':'true'}), \
             patch.object(local_chat,'generate') as private, \
             patch.object(m,'_dialogue_json', return_value={'skip':True}):
            m.free_dialogue_json({'task':'Public conversation'})
            private.assert_not_called()

    def test_latest_message_is_not_silently_truncated(self):
        question = 'What can I do? '*100
        turns = local_chat.messages({'conversation':[{'role':'assistant','content':'old '*2000},{'role':'user','content':question}]})
        self.assertEqual(turns[-1]['content'],question)
        self.assertFalse(any('old old' in m['content'] for m in turns))

    def test_audio_checks_report_text_arrival_without_guessing_audio_quality(self):
        with patch.object(local_chat.subprocess, 'Popen') as engine:
            for question in ('Can you hear me?', 'Is my voice clear?', "isn't that my voice is not clear"):
                answer = local_chat.generate({'conversation':[{'role':'user','content':question}]})
                self.assertIn('reached me as text', answer['content'])
                self.assertNotIn('voice is not clear', answer['content'])
            engine.assert_not_called()
        for question in ('How are you today?', 'I lost my voice. What should I do?',
                         'Help me make my voice clear during presentations.'):
            self.assertIsNone(local_chat.audio_check_reply(question))

    def test_old_hearing_reply_does_not_replace_the_latest_question(self):
        turns = local_chat.messages({'conversation':[
            {'role':'user','content':'Can you hear me?'},
            {'role':'assistant','content':"I'm not sure if I can hear you."},
            {'role':'user','content':'how are you today'}]})
        self.assertEqual(turns[-1], {'role':'user','content':'how are you today'})
        self.assertIn('not audio', turns[0]['content'])


class RecognitionContract(unittest.TestCase):
    def waveform(self,rate=16000):
        out=io.BytesIO()
        with wave.open(out,'wb') as audio:
            audio.setnchannels(1);audio.setsampwidth(2);audio.setframerate(rate);audio.writeframes(b'\0\0'*1600)
        return out.getvalue()

    def test_pcm_contract_and_bounds(self):
        self.assertEqual(len(local_recognition.validate(self.waveform())),3200)
        for bad in (b'not-a-wave', self.waveform(48000), b'x'*960045):
            with self.assertRaises(ValueError):local_recognition.validate(bad)

    def test_new_private_routes_are_authenticated(self):
        import app
        with patch.dict(os.environ,{'AGENT_ACCESS_TOKEN':'synthetic-test-access'}):
            client=app.app.test_client()
            self.assertEqual(client.get('/companion/local/status').status_code,401)
            self.assertEqual(client.post('/companion/transcribe',data=self.waveform(),content_type='audio/wav').status_code,401)


class ReadinessLatency(unittest.TestCase):
    def test_readiness_never_launches_or_waits_for_voice_inference(self):
        import tempfile
        import app
        with tempfile.TemporaryDirectory() as directory, \
             patch.dict(os.environ,{'CLARA_LOCAL_ONLY':'true','AGENT_DB_PATH':directory+'/state.sqlite'}), \
             patch('internal_voice_check.start') as start:
            self.assertTrue(m.DIALOGUE_LOCK.acquire(False))
            try:
                self.assertEqual(app.app.test_client().get('/health').status_code,200)
                self.assertEqual(app.app.test_client().get('/health').status_code,200)
                start.assert_not_called()
            finally:
                m.DIALOGUE_LOCK.release()
