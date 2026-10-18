import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch, Mock
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


class VoiceCache(unittest.TestCase):
    def test_old_runtime_and_damaged_metadata_do_not_select_cached_graph(self):
        with tempfile.TemporaryDirectory() as directory:
            model=Path(directory)/'voice.onnx';model.write_bytes(b'fixture')
            meta=Path(directory)/'voice.json'
            ort=SimpleNamespace(__version__='fixture-runtime')
            with patch.object(local_speech,'OPTIMIZED',model),patch.object(local_speech,'OPTIMIZED_META',meta):
                info={'fingerprint':local_speech._cache_fingerprint(ort),'bytes':7}
                meta.write_text(json.dumps(info))
                self.assertEqual(local_speech.cached_model(ort),model)
                ort.__version__='new-runtime'
                self.assertIsNone(local_speech.cached_model(ort))
                ort.__version__='fixture-runtime';model.write_bytes(b'changed-size')
                self.assertIsNone(local_speech.cached_model(ort))
                meta.write_text('broken json')
                self.assertIsNone(local_speech.cached_model(ort))

    def test_incompatible_cache_falls_back_to_original_local_voice(self):
        ort=Mock();ort.InferenceSession.side_effect=[ValueError('incompatible cache'),'original session']
        with patch.object(local_speech,'cached_model',return_value=Path('cached.onnx')):
            self.assertEqual(local_speech.load_session(ort),'original session')
        calls=ort.InferenceSession.call_args_list
        self.assertEqual(calls[0].args[0],'cached.onnx')
        self.assertEqual(calls[1].args[0],str(local_speech.MODEL))
        self.assertEqual(calls[1].kwargs['providers'],['CPUExecutionProvider'])
