import unittest
from opportunity_intelligence import evaluate, WEIGHTS

class OpportunityTests(unittest.TestCase):
    def evidence(self, rating=4):
        return {k: {"rating": rating, "note": "Interview or source to verify"}
                for k in WEIGHTS}

    def test_weighted_score(self):
        self.assertEqual(evaluate(self.evidence())["score"], 80)

    def test_missing_evidence(self):
        data = self.evidence()
        del data["demand"]
        with self.assertRaises(ValueError):
            evaluate(data)

    def test_rejects_out_of_range(self):
        data = self.evidence()
        data["demand"]["rating"] = 6
        with self.assertRaises(ValueError):
            evaluate(data)

if __name__ == "__main__":
    unittest.main()
