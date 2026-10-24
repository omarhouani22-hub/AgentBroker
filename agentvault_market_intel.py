"""Read-only, deterministic market intelligence for AgentVault.

This module NEVER posts to Moltbook, calls a paid model, or alters production.
Only explicitly supplied public discussion excerpts are analyzed.
"""
import re
from collections import Counter

PATTERNS = {
    "state_loss": r"\\b(lost|lose|losing|forgot|forget|memory loss|state loss|wiped|reset)\\b",
    "restore_failure": r"\\b(restore|recovery|recover|rollback|checkpoint|snapshot)\\b",
    "durability": r"\\b(persist|durab|ephemeral|restart|redeploy|crash|outage)\\w*",
    "security": r"\\b(encrypt|privacy|secret|credential|access control|leak)\\w*",
    "cost": r"\\b(price|pricing|cost|pay|budget|expensive|subscription)\\b",
}
BUYING = re.compile(r"\\b(would pay|willing to pay|looking for|need a tool|need a service|recommend a service|buy)\\b", re.I)
MAX_ITEMS = 200
MAX_TEXT = 1500

def analyze_public_discussions(items):
    """Return counts and attributed candidate needs; never infer willingness to pay."""
    if not isinstance(items, list) or len(items) > MAX_ITEMS:
        raise ValueError("Expected a list of at most 200 discussions")
    counts = Counter()
    evidence = []
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Each discussion must be an object")
        content = item.get("content", "")
        url = item.get("url", "")
        if not isinstance(content, str) or not isinstance(url, str):
            raise ValueError("Invalid discussion fields")
        if len(content) > MAX_TEXT:
            content = content[:MAX_TEXT]
        if not url.startswith(("https://www.moltbook.com/post/", "https://moltbook.com/post/")):
            continue
        if url in seen:
            continue
        seen.add(url)
        labels = [key for key, pattern in PATTERNS.items() if re.search(pattern, content, re.I)]
        if not labels:
            continue
        counts.update(labels)
        evidence.append({"url": url, "signals": labels,
                         "buying_language": bool(BUYING.search(content)),
                         "excerpt": " ".join(content.split())[:240]})
    evidence.sort(key=lambda row: (-int(row["buying_language"]), -len(row["signals"]), row["url"]))
    return {"source_count": len(seen), "matched_count": len(evidence),
            "signal_counts": dict(sorted(counts.items())),
            "evidence": evidence[:30],
            "limitations": "Keyword-based hypotheses, not verified demand or customers.",
            "next_action": "Ask operators about a concrete failure and request an opt-in beta trial."}
