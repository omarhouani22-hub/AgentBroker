"""Pure Job Description Audit order-state rules.

No database, checkout, customer data, delivery, or external calls. Integrate only
after durable storage, authenticated staff actions, and verified payment exist.
"""
from enum import Enum


class OrderStatus(str, Enum):
    NEW = "new"
    PAYMENT_PENDING = "payment_pending"
    PAID = "paid"
    IN_REVIEW = "in_review"
    READY = "ready_for_delivery"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


_ALLOWED = {
    OrderStatus.NEW: frozenset({OrderStatus.PAYMENT_PENDING, OrderStatus.CANCELLED}),
    OrderStatus.PAYMENT_PENDING: frozenset({OrderStatus.PAID, OrderStatus.CANCELLED}),
    OrderStatus.PAID: frozenset({OrderStatus.IN_REVIEW, OrderStatus.REFUNDED}),
    OrderStatus.IN_REVIEW: frozenset({OrderStatus.READY, OrderStatus.REFUNDED}),
    OrderStatus.READY: frozenset({OrderStatus.DELIVERED, OrderStatus.IN_REVIEW, OrderStatus.REFUNDED}),
    OrderStatus.DELIVERED: frozenset({OrderStatus.REFUNDED}),
    OrderStatus.CANCELLED: frozenset(),
    OrderStatus.REFUNDED: frozenset(),
}


def next_status(current, target, *, payment_verified=False, human_approved=False,
                delivery_confirmed=False):
    """Validate a single proposed transition; return target or raise ValueError."""
    current, target = OrderStatus(current), OrderStatus(target)
    if target not in _ALLOWED[current]:
        raise ValueError("Invalid order transition")
    if target is OrderStatus.PAID and payment_verified is not True:
        raise ValueError("Server-verified payment required")
    if target is OrderStatus.READY and human_approved is not True:
        raise ValueError("Human approval required")
    if target is OrderStatus.DELIVERED and delivery_confirmed is not True:
        raise ValueError("Verified delivery required")
    return target
