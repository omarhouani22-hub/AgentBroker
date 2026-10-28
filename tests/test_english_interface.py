import re
import unittest
import app as server


class EnglishInterface(unittest.TestCase):
    def test_public_landing_page_is_english(self):
        response = server.app.test_client().get('/')
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIsNone(re.search('[\u0600-\u06ff]', html))
        self.assertIn('Clara | AgentVault', html)
        self.assertIn('lang="en" dir="ltr"', html)

    def test_clara_interface_remains_english_only(self):
        html = server.app.test_client().get('/clara/').get_data(as_text=True)
        self.assertIn('value="en-US"', html)
        self.assertNotIn('value="ar-JO"', html)
        self.assertIn('lang="en" dir="ltr"', html)
