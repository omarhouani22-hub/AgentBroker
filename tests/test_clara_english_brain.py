import json
import unittest
from unittest.mock import patch, MagicMock
import trained_model as model


class ClaraEnglishBrainTests(unittest.TestCase):
    def invoke(self, answer, language='ar', companion=True):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps({
            'choices': [{'finish_reason': 'stop', 'message': {
                'content': json.dumps({'skip': False, 'content': answer, 'lesson': ''})
            }}]
        }).encode()
        context = {'_companion': companion, 'language': language,
                   'conversation': [{'role': 'user', 'content': 'Hello'}]}
        with patch.object(model, '_start'), patch.object(model, '_process', None), patch.object(model, 'urlopen', return_value=response) as call:
            result = model.generate(context)
            payload = json.loads(call.call_args.args[0].data)
            return result, payload

    def test_clara_identity_and_english_instruction(self):
        result, payload = self.invoke('I am Clara, your digital AI assistant.')
        self.assertIn('You are Clara', payload['messages'][0]['content'])
        self.assertIn('American English', payload['messages'][0]['content'])

    def test_arabic_output_rejected(self):
        with self.assertRaisesRegex(ValueError, 'English text'):
            self.invoke('مرحبا كيف حالك')

    def test_non_companion_arabic_remains_supported(self):
        result, payload = self.invoke('مرحبا كيف حالك', companion=False)
        self.assertIn('Jordanian Arabic', payload['messages'][0]['content'])

    def test_empty_output_rejected(self):
        with self.assertRaisesRegex(ValueError, 'English text'):
            self.invoke('')


if __name__ == '__main__':
    unittest.main()
