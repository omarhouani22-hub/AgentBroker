import unittest
from clara_decision_gate import assess_experiment


class ClaraDecisionGateTests(unittest.TestCase):
    def test_missing_fields_block(self):
        result = assess_experiment({"goal": "Test demand"})
        self.assertFalse(result["can_execute"])
        self.assertIn("hypothesis", result["missing_fields"])

    def test_external_action_requires_approval(self):
        result = assess_experiment({"goal": "Demand", "hypothesis": "Buyers exist",
                                    "next_action": "Post an offer", "actions": ["publish"]})
        self.assertTrue(result["requires_owner_approval"])
        self.assertFalse(result["can_execute"])

    def test_revenue_claim_not_accepted(self):
        result = assess_experiment({"goal": "Sales", "hypothesis": "Sales possible",
                                    "next_action": "Review", "verified_revenue": True})
        self.assertFalse(result["revenue_verified"])
        self.assertEqual(result["outcome"], "inconclusive")

    def test_research_only_can_proceed(self):
        result = assess_experiment({"goal": "Explore", "hypothesis": "Demand exists",
                                    "next_action": "Compare options", "actions": ["research"]})
        self.assertTrue(result["can_execute"])


if __name__ == "__main__":
    unittest.main()
