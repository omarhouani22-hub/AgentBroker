"""Regression tests for companion multilingual preferences (no provider calls)."""
import unittest
from unittest.mock import patch
import moltbook


class MultilingualCompanionTests(unittest.TestCase):
    def test_explicit_languages_override_conversation_detection(self):
        for code in ('ar', 'en', 'fr', 'es', 'de', 'tr', 'pt', 'it', 'zh', 'ja'):
            with self.subTest(language=code):
                context = {'language': code, 'conversation': [
                    {'role': 'user', 'content': 'Hello, how are you?'}]}
                self.assertEqual(moltbook.companion_language(context), code)

    def test_auto_keeps_arabic_and_english_detection(self):
        self.assertEqual(moltbook.companion_language({
            'language': 'auto', 'conversation': [{'role': 'user', 'content': 'كيف حالك اليوم؟'}]}), 'ar')
        self.assertEqual(moltbook.companion_language({
            'language': 'auto', 'conversation': [{'role': 'user', 'content': 'How are you today?'}]}), 'en')

    def test_companion_state_accepts_supported_languages(self):
        for code in ('auto', 'ar', 'en', 'fr', 'es', 'de', 'tr', 'pt', 'it', 'zh', 'ja'):
            with self.subTest(language=code):
                state = {'messages': [], 'reply_calls': 0, 'language': code}
                moltbook.validate_companion(state)

    def test_unknown_language_rejected(self):
        with self.assertRaises(ValueError):
            moltbook.validate_companion({'messages': [], 'reply_calls': 0, 'language': 'xx'})


if __name__ == '__main__':
    unittest.main()
