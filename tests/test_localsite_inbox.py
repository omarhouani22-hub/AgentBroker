import unittest

from integrations.localsite_inbox import prepare_inquiry


class LocalSiteInboxTests(unittest.TestCase):
    def test_test_submission_does_not_generate_reply(self):
        item = prepare_inquiry({"id": "test-1", "submissions": {
            "form_field_ad8e": "LSF-TEST-2026 internal test"
        }})
        self.assertTrue(item["is_test"])
        self.assertIsNone(item["reply_draft"])
        self.assertTrue(item["owner_approval_required"])

    def test_customer_inquiry_produces_draft_only(self):
        item = prepare_inquiry({"id": "lead-1", "submissions": {
            "form_field_5d13": "Example Plumbing",
            "form_field_bdd5": "Plumbing",
            "form_field_ad8e": "Need a website"
        }})
        self.assertFalse(item["is_test"])
        self.assertIn("proposal", item["reply_draft"])
        self.assertTrue(item["owner_approval_required"])


if __name__ == "__main__":
    unittest.main()
