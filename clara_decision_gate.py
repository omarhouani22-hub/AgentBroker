"""Deterministic evidence gate for Clara's proposed commercial experiments.

No network, model inference, spending or side effects.
"""
from urllib.parse import urlsplit

REQUIRED = ("goal", "hypothesis", "next_action")
APPROVAL_TRIGGERS = ("spend", "publish", "outreach", "deploy", "delete", "private_data", "payment")


def assess_experiment(proposal):
    """Return an auditable decision, never claim unverified success."""
    if not isinstance(proposal, dict):
        raise ValueError("proposal must be an object")
    missing = [key for key in REQUIRED if not isinstance(proposal.get(key), str)
               or not proposal[key].strip()]
    evidence = proposal.get("evidence", [])
    if not isinstance(evidence, list):
        raise ValueError("evidence must be a list")
    valid_evidence = []
    for item in evidence:
        if not isinstance(item, dict):
            continue
        url = item.get("url", "")
        parsed = urlsplit(url) if isinstance(url, str) else urlsplit("")
        if parsed.scheme == "https" and parsed.netloc and isinstance(item.get("observation"), str) and item["observation"].strip():
            valid_evidence.append({"url": url, "observation": item["observation"].strip()})
    actions = proposal.get("actions", [])
    if not isinstance(actions, list) or not all(isinstance(x, str) for x in actions):
        raise ValueError("actions must be a list of strings")
    approvals = sorted(set(actions).intersection(APPROVAL_TRIGGERS))
    unknown_actions = sorted(set(actions) - set(APPROVAL_TRIGGERS) - {"research", "compare", "draft", "offline_test"})
    verified_revenue = proposal.get("verified_revenue", False)
    # Evidence URLs alone never establish that payment was received.
    return {
        "ready_for_review": not missing,
        "missing_fields": missing,
        "evidence_count": len(valid_evidence),
        "evidence_status": "provided_unverified" if valid_evidence else "missing",
        "requires_owner_approval": bool(approvals),
        "approval_reasons": approvals,
        "can_execute": not missing and not approvals and not unknown_actions,
        "unknown_actions": unknown_actions,
        "outcome": "inconclusive",
        "revenue_verified": False,
        "warnings": (["No independently verified demand or revenue."] +
                     (["Claimed revenue requires independent payment verification."] if verified_revenue else [])),
    }
