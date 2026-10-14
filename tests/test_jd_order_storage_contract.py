"""No-I/O storage contract tests for future durable JD orders."""
import sqlite3
import unittest
from uuid import uuid4

from jd_order_storage_contract import SQLITE_SCHEMA, new_order_record, proposed_transition


class StorageContractTests(unittest.TestCase):
    def test_schema_and_unique_event_key(self):
        conn = sqlite3.connect(":memory:")
        conn.executescript("PRAGMA foreign_keys=ON;" + SQLITE_SCHEMA)
        order = new_order_record(str(uuid4()), now="2026-10-14T00:00:00+00:00")
        conn.execute("INSERT INTO jd_orders(id,status,created_at,updated_at,version) VALUES (?,?,?,?,?)",
                     (order["id"], order["status"], order["created_at"], order["updated_at"], 0))
        event = (order["id"], "new", "payment_pending", order["created_at"], "system", "evt-1")
        conn.execute("INSERT INTO jd_order_events(order_id,previous_status,next_status,occurred_at,actor_type,event_key) VALUES (?,?,?,?,?,?)", event)
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO jd_order_events(order_id,previous_status,next_status,occurred_at,actor_type,event_key) VALUES (?,?,?,?,?,?)", event)
        conn.close()

    def test_optimistic_version_and_approval(self):
        record = new_order_record(str(uuid4()), now="2026-10-14T00:00:00+00:00")
        next_record = proposed_transition(record, "payment_pending")
        self.assertEqual(next_record["version"], 1)
        self.assertEqual(record["version"], 0)
        with self.assertRaises(ValueError):
            proposed_transition(next_record, "paid")

    def test_invalid_order_id(self):
        with self.assertRaises(ValueError):
            new_order_record("not-an-id")


if __name__ == "__main__":
    unittest.main()
