import io
import unittest
from unittest.mock import patch
import wave
import local_speech
from tests import test_clara_tasks as fixtures
import moltbook as m


class InternalSpeech(unittest.TestCase):
    setUp = fixtures.ClaraTasks.setUp
    tearDown = fixtures.ClaraTasks.tearDown
    def test_internal_status_and_audio_never_use_external_transport(self):
        output = io.BytesIO()
        with wave.open(output, 'wb') as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050)
            w.writeframes(b'\0\0' * 100)
        with patch.object(local_speech, 'configured', return_value=True), \
             patch.object(local_speech, 'generate', return_value=output.getvalue()), \
             patch.object(m.TRANSPORT, 'open') as external:
            status = self.client.get('/companion/speech/status').json
            self.assertTrue(status['internal']); self.assertFalse(status['billing_enabled'])
            response = self.client.post('/companion/speech', json={'text': 'Hello Clara'})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.mimetype, 'audio/wav')
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
            external.assert_not_called()

    def test_internal_failure_does_not_fall_through_to_paid_voice(self):
        with patch.object(local_speech, 'configured', return_value=True), \
             patch.object(local_speech, 'generate', side_effect=TimeoutError), \
             patch.object(m.TRANSPORT, 'open') as external:
            self.assertEqual(self.client.post('/companion/speech', json={'text':'Hello'}).status_code, 503)
            external.assert_not_called()

    def test_input_limits_and_english_only(self):
        for text in ('', 'x' * 801, 'مرحبا'):
            with self.assertRaises(ValueError): local_speech.validate(text)
