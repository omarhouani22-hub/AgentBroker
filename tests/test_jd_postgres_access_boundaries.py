"""Security integration tests on disposable PostgreSQL only.

The runner creates restricted anon/authenticated roles. Verify that neither
role can read or write JD orders through the private schema.
"""
import os
import unittest

try:
    import psycopg
except ImportError:
    psycopg = None


@unittest.skipUnless(psycopg is not None and os.getenv("TEST_JD_POSTGRES_DSN"),
                     "Requires isolated PostgreSQL integration database")
class PostgresAccessBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.conn = psycopg.connect(os.environ["TEST_JD_POSTGRES_DSN"])

    def tearDown(self):
        self.conn.close()

    def test_unprivileged_roles_cannot_select_or_insert(self):
        for role in ("anon", "authenticated"):
            for query in (
                "SELECT * FROM agentbroker_private.jd_orders LIMIT 1",
                "INSERT INTO agentbroker_private.jd_orders(id,status) VALUES "
                "('00000000-0000-0000-0000-000000000001','new')",
            ):
                with self.subTest(role=role, query=query):
                    with self.conn.cursor() as cursor:
                        cursor.execute("SET LOCAL ROLE " + role)
                        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                            cursor.execute(query)
                    self.conn.rollback()

    def test_rls_enabled_on_both_tables(self):
        with self.conn.cursor() as cursor:
            cursor.execute("""
                SELECT relname, relrowsecurity
                FROM pg_class
                JOIN pg_namespace ON pg_namespace.oid=pg_class.relnamespace
                WHERE nspname='agentbroker_private'
                  AND relname IN ('jd_orders','jd_order_events')
            """)
            self.assertEqual(dict(cursor.fetchall()),
                             {"jd_orders": True, "jd_order_events": True})


if __name__ == "__main__":
    unittest.main()
