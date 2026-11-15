"""Read-only SkillsMP discovery for Clara. No skill installation or execution.

The anonymous endpoint has a documented 50/day, 10/min limit (2026-11-16).
Third-party descriptions are untrusted and must not be used as instructions.
"""
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from flask import jsonify, request

API_URL = "https://skillsmp.com/api/v1/skills/search"
MAX_RESPONSE_BYTES = 256 * 1024
_RATE_LOCK = threading.Lock()
_LAST_REQUEST = 0.0
_REQUEST_TIMES = []


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def reserve_anonymous_request():
    """Conservatively bound process-local calls; provider quotas still apply globally."""
    global _LAST_REQUEST
    now = time.monotonic()
    with _RATE_LOCK:
        _REQUEST_TIMES[:] = [t for t in _REQUEST_TIMES if now - t < 86400]
        if len(_REQUEST_TIMES) >= 45 or now - _LAST_REQUEST < 7:
            raise RuntimeError("skillsmp_rate_limited")
        _REQUEST_TIMES.append(now)
        _LAST_REQUEST = now


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
    reserve_anonymous_request()
    transport = opener or urllib.request.build_opener(NoRedirect()).open
    try:
        with transport(request, timeout=timeout) as response:
            if response.status != 200:
                raise RuntimeError("skillsmp_unavailable")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise RuntimeError("skillsmp_rate_limited") from None
        raise RuntimeError("skillsmp_unavailable") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise RuntimeError("skillsmp_unavailable") from None
    if len(raw) > MAX_RESPONSE_BYTES:
        raise RuntimeError("skillsmp_response_too_large")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeError):
        raise RuntimeError("skillsmp_invalid_response") from None
    if not isinstance(payload, dict):
        raise RuntimeError("skillsmp_invalid_response")
    # Do not assume a particular response schema; return data as untrusted metadata.
    return {"source": "skillsmp.com", "trusted": False, "installation_allowed": False,
            "execution_allowed": False, "results": payload}



def install_routes(app):
    """Register a read-only owner-authenticated endpoint on the Clara Flask app.

    Existing app.before_request authentication must run for this endpoint.
    Do not add it to any public-route allowlist.
    """
    @app.get("/skillsmp/search")
    def skillsmp_search():
        query = request.args.get("q", "")
        try:
            limit = int(request.args.get("limit", "5"))
            result = search_skills(query, limit=limit)
        except (ValueError, TypeError):
            return jsonify(error="invalid_search_parameters"), 400
        except RuntimeError as exc:
            code = str(exc)
            return jsonify(error=code), 429 if code == "skillsmp_rate_limited" else 502
        except (json.JSONDecodeError, UnicodeError):
            return jsonify(error="skillsmp_invalid_response"), 502
        response = jsonify(result)
        response.headers["Cache-Control"] = "no-store"
        return response
