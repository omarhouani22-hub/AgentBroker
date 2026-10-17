import re
import unittest
import app as server


class EnglishInterface(unittest.TestCase):
    def test_agentbroker_chrome_and_synthetic_sample_are_english(self):
        response = server.app.test_client().get('/')
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIsNone(re.search('[\u0600-\u06ff]', html))
        self.assertIn('Command Center', html)
        self.assertIn('Internal Piper voice', html)
        self.assertIn('Human Resources Specialist', html)
        self.assertIn('value="ar"', html)  # UI language does not delete language support.

    def test_clara_language_support_is_preserved(self):
        html = server.app.test_client().get('/clara/').get_data(as_text=True)
        self.assertIn('value="ar-JO"', html)
