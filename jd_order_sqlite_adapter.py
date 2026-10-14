"""Opt-in SQLite transaction adapter for local JD order tests.

Not connected to public routes, Render disk, payments, or customer intake.
A production implementation needs a durable managed database and proper
server-side payment verification.
"""
import sqlite3
from jd_order_storage_contract import SQLITE_SCHEMA, new_order_record, proposed_transition


class VersionConflict(RuntimeError):
    pass


class JDOrderStore:
    def __init__(self, connection):
        self.connection = connection
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.executescript(SQLITE_SCHEMA)

    def create(self, order_id, *, now=None):
        record = new_order_record(order_id, now=now)
        with self.connection:
            self.connection.execute(
                "INSERT INTO jd_orders(id,status,created_at,updated_at,version) VALUES (?,?,?,?,?)",
                (record["id"], record["status"], record["created_at"],
                 record["updated_at"], record["version"]))
        return record

    def get(self, order_id):
        row = self.connection.execute(
            "SELECT id,status,created_at,updated_at,version FROM jd_orders WHERE id=?",
            (order_id,)).fetchone()
        if row is None:
            return None
        return dict(zip(("id", "status", "created_at", "updated_at", "version"), row))

    def transition(self, order_id, target, *, event_key, actor_type,
                   payment_verified=False, human_approved=False,
                   delivery_confirmed=False, now=None):
        if not isinstance(event_key, str) or not 1 <= len(event_key) <= 150:
            raise ValueError("Nonempty idempotency event key required")
        if actor_type not in ("system", "operator", "payment_webhook"):
            raise ValueError("Invalid actor type")
        with self.connection:
            prior = self.get(order_id)
            if prior is None:
                raise KeyError("Order not found")
            updated = proposed_transition(
                prior, target, payment_verified=payment_verified,
                human_approved=human_approved, delivery_confirmed=delivery_confirmed,
                now=now)
            cursor = self.connection.execute(
                "UPDATE jd_orders SET status=?,updated_at=?,version=? WHERE id=? AND version=?",
                (updated["status"], updated["updated_at"], updated["version"],
                 order_id, prior["version"]))
            if cursor.rowcount != 1:
                raise VersionConflict("Order changed concurrently")
            self.connection.execute(
                "INSERT INTO jd_order_events(order_id,previous_status,next_status,occurred_at,actor_type,event_key) VALUES (?,?,?,?,?,?)",
                (order_id, prior["status"], updated["status"],
                 updated["updated_at"], actor_type, event_key))
        return updated
