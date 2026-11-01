"""Offline experiment and storyboard tests. No network calls."""
import os
import unittest
from unittest.mock import patch
from experiments.clara_media_studio import prepare_video_job
from experiments.clara_google_ai import prepare_request, test_gemini
from experiments.clara_video_storyboard import build_storyboard

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

    def test_storyboard(self):
        result = build_storyboard()
        self.assertEqual(result["duration_seconds"], 7)
        self.assertEqual(sum(s["duration_seconds"] for s in result["shots"]), 7)
        self.assertEqual(result["status"], "storyboard_only_no_video_rendered")
        self.assertFalse(result["job"]["production_enabled"])
        self.assertTrue(result["job"]["requires_owner_approval"])

    def test_google_request(self):
        url, body = prepare_request("Say hello.")
        self.assertIn("generativelanguage.googleapis.com", url)
        self.assertIn(b"Say hello.", body)

    def test_google_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "disabled"):
                test_gemini("Hello")

    def test_google_requires_key(self):
        with patch.dict(os.environ, {"CLARA_EXPERIMENT_GOOGLE_ENABLED":"1"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "not configured"):
                test_gemini("Hello")

    def test_google_rejects_invalid_model(self):
        with self.assertRaises(ValueError):
            prepare_request("Hi", "model/../../unsafe")

if __name__ == "__main__":
    unittest.main()
