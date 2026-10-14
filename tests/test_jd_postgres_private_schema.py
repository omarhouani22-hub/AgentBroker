"""Static guardrails for future JD Postgres schema; no database is contacted."""
import unittest
from pathlib import Path


class PrivateSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sql = (Path(__file__).resolve().parents[1] /
                   "db/reference/jd_orders_private_postgres.sql").read_text()

    def test_schema_not_public(self):
        self.assertIn("CREATE SCHEMA IF NOT EXISTS agentbroker_private", self.sql)
        self.assertNotIn("CREATE TABLE public.", self.sql)
        self.assertIn("REVOKE ALL ON SCHEMA agentbroker_private FROM PUBLIC, anon, authenticated", self.sql)

    def test_rls_and_restricted_tables(self):
        self.assertIn("jd_orders ENABLE ROW LEVEL SECURITY", self.sql)
        self.assertIn("jd_order_events ENABLE ROW LEVEL SECURITY", self.sql)
        self.assertIn("REVOKE ALL ON ALL TABLES IN SCHEMA agentbroker_private", self.sql)
        self.assertIn("event_key text NOT NULL UNIQUE", self.sql)


if __name__ == "__main__":
    unittest.main()
