"""Offline safety tests; no credentials or network access required."""
import unittest
from experiments.clara_media_studio import prepare_video_job
from experiments.clara_google_ai import prepare_request, test_gemini

class MediaExperiments(unittest.TestCase):
    def test_video_job(self):
        job = prepare_video_job("clara-standing-business.webp", "Hello, I'm Clara.")
        self.assertEqual(job["status"], "prepared_not_rendered")
        self.assertFalse(job["production_enabled"])
        self.assertTrue(job["requires_owner_approval"])

    def test_reject_unknown_image(self):
        with self.assertRaises(ValueError):
            prepare_video_job("https://example.com/image.png", "Hello")

    def test_reject_arabic(self):
        with self.assertRaises(ValueError):
            prepare_video_job("clara-standing-business.webp", "مرحبا")

    def test_google_request(self):
        url, body = prepare_request("Say hello.")
        self.assertIn("generativelanguage.googleapis.com", url)
        self.assertIn(b"Say hello.", body)

    def test_google_disabled_by_default(self):
        import os
        old = os.environ.pop("CLARA_EXPERIMENT_GOOGLE_ENABLED", None)
        try:
            with self.assertRaisesRegex(RuntimeError, "disabled"):
                test_gemini("Hello")
        finally:
            if old is not None:
                os.environ["CLARA_EXPERIMENT_GOOGLE_ENABLED"] = old

if __name__ == "__main__":
    unittest.main()
