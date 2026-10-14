"""Smoke-test operator navigation from the authenticated dashboard."""
import unittest
from pathlib import Path


class NavigationTests(unittest.TestCase):
    def test_operator_dashboard_link_and_guard_are_present(self):
        source = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
        self.assertIn('href="/offers/jd-audit/operator-dashboard"', source)
        self.assertIn("@app.get('/offers/jd-audit/operator-dashboard')", source)
        self.assertIn("synthetic_demo_only", source)
        self.assertNotIn("'/offers/jd-audit/operator-dashboard', '/session/login'", source)


if __name__ == "__main__":
    unittest.main()
