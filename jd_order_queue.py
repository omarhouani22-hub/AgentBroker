"""Pure operator queue projections for JD orders.

This is not an HTTP endpoint or database adapter. It excludes job-description
contents, purchaser contact details and payment secrets from queue summaries.
"""
from collections import Counter
from datetime import datetime, timezone
from jd_order_workflow import OrderStatus


def order_queue_summary(records):
    if not isinstance(records, list):
        raise ValueError("Records must be a list")
    counts = Counter()
    cards = []
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Invalid order")
        status = OrderStatus(record.get("status"))
        counts[status.value] += 1
        cards.append({
            "id": str(record.get("id", "")),
            "status": status.value,
            "updated_at": str(record.get("updated_at", "")),
            "version": record.get("version", 0),
        })
    cards.sort(key=lambda item: item["updated_at"], reverse=True)
    return {
        "total": len(cards),
        "counts": {status.value: counts[status.value] for status in OrderStatus},
        "orders": cards,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
