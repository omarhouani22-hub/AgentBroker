"""Pure PostgreSQL transaction plan for future JD order persistence.

No driver, connection string, database calls or public API. Intended for a
server-only adapter after database provisioning and authorization review.
"""
from jd_order_workflow import OrderStatus, next_status

READ_ORDER_FOR_UPDATE = """
SELECT id, status, version FROM agentbroker_private.jd_orders
WHERE id = %s FOR UPDATE
"""

UPDATE_ORDER_VERSIONED = """
UPDATE agentbroker_private.jd_orders
SET status = %s, version = version + 1, updated_at = now()
WHERE id = %s AND version = %s
RETURNING id, status, version
"""

INSERT_ORDER_EVENT = """
INSERT INTO agentbroker_private.jd_order_events
(order_id, previous_status, next_status, actor_type, event_key)
VALUES (%s, %s, %s, %s, %s)
"""


def transition_plan(current_status, target_status, *, actor_type, event_key,
                    payment_verified=False, human_approved=False,
                    delivery_confirmed=False):
    """Validate a proposed transition before any SQL transaction is opened."""
    if not isinstance(event_key, str) or not 1 <= len(event_key) <= 150:
        raise ValueError("Invalid event key")
    if actor_type not in ("system", "operator", "payment_webhook"):
        raise ValueError("Invalid actor type")
    if payment_verified and actor_type != "payment_webhook":
        raise ValueError("Payment confirmation requires webhook actor")
    if human_approved and actor_type != "operator":
        raise ValueError("Human approval requires operator actor")
    if delivery_confirmed and actor_type != "operator":
        raise ValueError("Delivery confirmation requires operator actor")
    target = next_status(current_status, target_status,
                         payment_verified=payment_verified,
                         human_approved=human_approved,
                         delivery_confirmed=delivery_confirmed)
    return {"target_status": target.value, "actor_type": actor_type,
            "event_key": event_key}


# Required execution protocol:
# BEGIN; SELECT ... FOR UPDATE; validate transition with locked current status;
# UPDATE ... WHERE version = expected RETURNING ...; INSERT event; COMMIT.
# Roll back on any failure, including duplicate event_key.
# Verify payment webhook signature and operator authorization *before* this plan.
