"""Storage-independent JD order persistence contract (not wired to HTTP).

Use a durable database before enabling real customer orders. This module
contains schema and serialization helpers only: no credentials, I/O, payments
or personal job-description contents.
"""
import json
from datetime import datetime, timezone
from uuid import UUID

from jd_order_workflow import OrderStatus, next_status

SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS jd_orders (
  id TEXT PRIMARY KEY,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  version INTEGER NOT NULL DEFAULT 0,
  payment_reference TEXT UNIQUE,
  delivery_reference TEXT,
  CHECK (version >= 0)
);
CREATE TABLE IF NOT EXISTS jd_order_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id TEXT NOT NULL REFERENCES jd_orders(id),
  previous_status TEXT NOT NULL,
  next_status TEXT NOT NULL,
  occurred_at TEXT NOT NULL,
  actor_type TEXT NOT NULL,
  event_key TEXT NOT NULL UNIQUE
);
"""


def validate_order_id(order_id):
    if not isinstance(order_id, str):
        raise ValueError("Order ID must be a UUID string")
    return str(UUID(order_id))


def new_order_record(order_id, *, now=None):
    order_id = validate_order_id(order_id)
    timestamp = now or datetime.now(timezone.utc).isoformat()
    return {"id": order_id, "status": OrderStatus.NEW.value,
            "created_at": timestamp, "updated_at": timestamp, "version": 0}


def proposed_transition(record, target, *, payment_verified=False,
                        human_approved=False, delivery_confirmed=False, now=None):
    """Return a new immutable-style record; caller must persist atomically.

    Persist only with compare-and-swap on version, plus unique event_key,
    inside one transaction to prevent duplicate/reordered callbacks.
    """
    if not isinstance(record, dict) or type(record.get("version")) is not int or record["version"] < 0:
        raise ValueError("Invalid stored order")
    status = next_status(record.get("status"), target, payment_verified=payment_verified,
                         human_approved=human_approved, delivery_confirmed=delivery_confirmed)
    updated = dict(record)
    updated["status"] = status.value
    updated["version"] += 1
    updated["updated_at"] = now or datetime.now(timezone.utc).isoformat()
    return updated
