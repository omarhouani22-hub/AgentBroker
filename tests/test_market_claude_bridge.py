"""Offline tests: no Anthropic account, network or paid API calls needed."""
import io
import json
import os
import unittest
from unittest.mock import patch

from market_claude_bridge import analyze_market, estimate_max_usd

EVIDENCE = [{"source_id": "S1", "url": "https://example.org/review",
             "retrieved_at": "2026-10-23", "observation": "Users report slow exports."}]


class FakeResponse:
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, limit):
        return json.dumps({"model": "test-model", "content": [{"type": "text", "text": "Hypothesis [S1]"}],
                           "usage": {"input_tokens": 100, "output_tokens": 30}}).encode()


class ClaudeBridgeTests(unittest.TestCase):
    def test_disabled_by_default(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "dummy"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "disabled"):
                analyze_market(EVIDENCE, model="test-model")

    def test_requires_cost_limit(self):
        with patch.dict(os.environ, {"CLAUDE_API_ENABLED": "true", "ANTHROPIC_API_KEY": "dummy"}):
            with self.assertRaisesRegex(ValueError, "prices"):
                analyze_market(EVIDENCE, model="test-model")

    def test_budget_prevents_network(self):
        with patch.dict(os.environ, {"CLAUDE_API_ENABLED": "true", "ANTHROPIC_API_KEY": "dummy"}):
            with self.assertRaisesRegex(ValueError, "approved ceiling"):
                analyze_market(EVIDENCE, model="test-model", input_usd_per_million=100,
                               output_usd_per_million=100, max_call_usd=0.00001,
                               transport=lambda *a, **k: self.fail("Network should not run"))

    def test_mocked_response(self):
        calls = []
        def transport(request, timeout):
            calls.append(json.loads(request.data))
            return FakeResponse()
        with patch.dict(os.environ, {"CLAUDE_API_ENABLED": "true", "ANTHROPIC_API_KEY": "dummy"}):
            result = analyze_market(EVIDENCE, model="test-model", input_usd_per_million=3,
                                    output_usd_per_million=15, max_call_usd=0.1,
                                    transport=transport)
        self.assertEqual(result["source_ids"], ["S1"])
        self.assertEqual(result["text"], "Hypothesis [S1]")
        self.assertEqual(len(calls), 1)
        self.assertAlmostEqual(result["estimated_usd"], .00075)

    def test_estimator(self):
        self.assertEqual(estimate_max_usd(1_000_000, 1_000_000, 2, 10), 12)


if __name__ == "__main__":
    unittest.main()
