"""Conservative, explainable opportunity scoring; no network calls or payments."""
from dataclasses import dataclass

WEIGHTS = {"demand": 30, "willingness_to_pay": 25, "reachability": 20,
           "delivery_feasibility": 15, "competition_gap": 10}

def evaluate(evidence):
    """Each dimension requires an integer 0..5 and a nonempty evidence note.

    Unknown dimensions are not silently assigned optimistic scores.
    """
    if not isinstance(evidence, dict):
        raise ValueError("evidence must be a dictionary")
    breakdown = {}
    for dimension, weight in WEIGHTS.items():
        item = evidence.get(dimension)
        if not isinstance(item, dict):
            raise ValueError(f"Missing evidence: {dimension}")
        rating, note = item.get("rating"), item.get("note")
        if type(rating) is not int or not 0 <= rating <= 5:
            raise ValueError(f"Invalid rating: {dimension}")
        if not isinstance(note, str) or not note.strip():
            raise ValueError(f"Missing evidence note: {dimension}")
        breakdown[dimension] = {"rating": rating, "note": note.strip(),
                                "points": rating * weight / 5}
    total = round(sum(v["points"] for v in breakdown.values()), 1)
    return {"score": total, "max_score": 100,
            "decision": "test_with_customers" if total >= 70 else "collect_more_evidence",
            "breakdown": breakdown,
            "warning": "Ratings are analyst judgments, not verified market demand or sales."}
