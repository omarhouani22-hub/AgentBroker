"""Read-only SkillsMP discovery for Clara. No skill installation or execution.

The anonymous endpoint has a documented 50/day, 10/min limit (2026-11-16).
Third-party descriptions are untrusted and must not be used as instructions.
"""
import json
import re
import urllib.error
import urllib.parse
import urllib.request

API_URL = "https://skillsmp.com/api/v1/skills/search"
MAX_RESPONSE_BYTES = 256 * 1024


def search_skills(query, *, limit=5, timeout=8, opener=None):
    """Return untrusted search metadata. Never download or execute skill scripts."""
    if not isinstance(query, str) or not (2 <= len(query.strip()) <= 100):
        raise ValueError("invalid_query")
    if not re.search(r"[A-Za-z0-9\u0600-\u06ff]", query):
        raise ValueError("invalid_query")
    if not isinstance(limit, int) or isinstance(limit, bool) or not (1 <= limit <= 10):
        raise ValueError("invalid_limit")
    params = urllib.parse.urlencode({"q": query.strip(), "limit": limit, "page": 1})
    request = urllib.request.Request(
        API_URL + "?" + params,
        headers={"Accept": "application/json", "User-Agent": "Clara-SkillsMP-Discovery/1.0"},
        method="GET",
    )
    transport = opener or urllib.request.urlopen
    try:
        with transport(request, timeout=timeout) as response:
            if response.status != 200:
                raise RuntimeError("skillsmp_unavailable")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise RuntimeError("skillsmp_rate_limited") from None
        raise RuntimeError("skillsmp_unavailable") from None
    except (urllib.error.URLError, TimeoutError):
        raise RuntimeError("skillsmp_unavailable") from None
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("skillsmp_response_too_large")
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("skillsmp_invalid_response")
    # Do not assume a particular response schema; return data as untrusted metadata.
    return {"source": "skillsmp.com", "trusted": False, "installation_allowed": False,
            "execution_allowed": False, "results": payload}
