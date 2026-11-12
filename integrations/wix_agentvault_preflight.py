"""Read-only HTTP preflight for Wix -> AgentVault integration.

Run: python integrations/wix_agentvault_preflight.py
No credentials are used; no customer data is read or written.
Exit 0 only if both public GET checks return expected JSON.
"""
import json
import sys
import urllib.error
import urllib.request

BASE_URL = "https://agentvault-service.onrender.com"
TIMEOUT_SECONDS = 15

def check(path):
    req = urllib.request.Request(
        BASE_URL + path,
        headers={"Accept": "application/json", "User-Agent": "AgentVault-ReadOnly-Preflight/1.0"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as response:
            status = response.status
            content_type = response.headers.get("Content-Type", "")
            data = response.read(8192)
            try:
                payload = json.loads(data)
            except (ValueError, UnicodeError):
                payload = None
            return {
                "path": path,
                "status": status,
                "json": isinstance(payload, dict),
                "content_type": content_type.split(";")[0],
                "error": None,
            }
    except urllib.error.HTTPError as error:
        return {
            "path": path,
            "status": error.code,
            "json": False,
            "content_type": None,
            "error": "HTTP_ERROR",
        }
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        return {
            "path": path,
            "status": None,
            "json": False,
            "content_type": None,
            "error": type(error).__name__,
        }

def main():
    checks = [check("/healthz"), check("/v1/plans")]
    print(json.dumps({"target": BASE_URL, "checks": checks}, indent=2))
    return 0 if all(item["status"] == 200 and item["json"] for item in checks) else 1

if __name__ == "__main__":
    sys.exit(main())
