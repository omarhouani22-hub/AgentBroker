"""Server-only JD order transition executor using a supplied DB-API connection.

No connection is created and this module is not wired into Flask. The caller
must authenticate operator identity or verify the payment webhook signature.
Never pass verification flags derived directly from an HTTP request body.
"""
from jd_order_postgres_contract import (
    READ_ORDER_FOR_UPDATE, UPDATE_ORDER_VERSIONED,
    INSERT_ORDER_EVENT, transition_plan,
)


class OrderNotFound(LookupError):
    pass


class OrderConflict(RuntimeError):
    pass


def execute_transition(connection, order_id, target_status, *, actor_type,
                       event_key, payment_verified=False, human_approved=False,
                       delivery_confirmed=False):
    """Atomically change one order and record one event.

    Expects a DB-API PostgreSQL connection with autocommit disabled.
    Transaction boundary is owned here. Call only with a dedicated connection;
    do not reuse a connection holding unrelated uncommitted work.
    """
    if getattr(connection, "autocommit", False):
        raise ValueError("Transaction connection must have autocommit disabled")
    cursor = connection.cursor()
    try:
        cursor.execute(READ_ORDER_FOR_UPDATE, (order_id,))
        row = cursor.fetchone()
        if row is None:
            raise OrderNotFound("Order does not exist")
        _, current_status, version = row
        plan = transition_plan(
            current_status, target_status, actor_type=actor_type,
            event_key=event_key, payment_verified=payment_verified,
            human_approved=human_approved,
            delivery_confirmed=delivery_confirmed)
        cursor.execute(UPDATE_ORDER_VERSIONED,
                       (plan["target_status"], order_id, version))
        updated = cursor.fetchone()
        if updated is None:
            raise OrderConflict("Order changed during transaction")
        cursor.execute(INSERT_ORDER_EVENT,
                       (order_id, current_status, plan["target_status"],
                        plan["actor_type"], plan["event_key"]))
        connection.commit()
        return {"id": str(updated[0]), "status": updated[1],
                "version": updated[2]}
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
