import unittest
from agentvault_market_intel import analyze_public_discussions

class MarketIntelTests(unittest.TestCase):
    def test_deduplicates_and_attributes(self):
        result = analyze_public_discussions([
            {"url":"https://www.moltbook.com/post/abc","content":"I lost agent memory after restart. Looking for a recovery service."},
            {"url":"https://www.moltbook.com/post/abc","content":"duplicate"},
            {"url":"https://www.moltbook.com/post/xyz","content":"Unrelated chat."},
        ])
        self.assertEqual(result["source_count"], 2)
        self.assertEqual(result["matched_count"], 1)
        self.assertEqual(result["signal_counts"]["state_loss"], 1)
        self.assertTrue(result["evidence"][0]["buying_language"])

    def test_rejects_bad_input_and_external_urls(self):
        with self.assertRaises(ValueError):
            analyze_public_discussions([{"content": 2}])
        result = analyze_public_discussions([{"url":"https://evil.example/post/1","content":"lost memory"}])
        self.assertEqual(result["matched_count"], 0)

    def test_does_not_claim_revenue(self):
        result = analyze_public_discussions([{"url":"https://www.moltbook.com/post/a","content":"checkpoint recovery"}])
        self.assertIn("not verified demand", result["limitations"])

if __name__ == "__main__":
    unittest.main()
