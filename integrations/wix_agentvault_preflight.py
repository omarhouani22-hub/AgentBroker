"""Read-only preflight for Wix -> AgentVault. No secrets or writes."""
import json
import sys
import urllib.error
import urllib.request

BASE_URL = "https://agentvault-service.onrender.com"
TIMEOUT_SECONDS = 15

def check(path):
    req = urllib.request.Request(
        BASE_URL + path,
        headers={"Accept": "application/json", "User-Agent": "AgentVault-ReadOnly-Preflight/1.1"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as response:
            status = response.status
            try:
                payload = json.loads(response.read(8192))
            except (ValueError, UnicodeError):
                payload = None
    except urllib.error.HTTPError as error:
        return {"path": path, "http_status": error.code, "ready": False, "error": "HTTP_ERROR"}
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        return {"path": path, "http_status": None, "ready": False, "error": type(error).__name__}

    if path == "/healthz":
        valid = (isinstance(payload, dict)
                 and payload.get("status") == "ok"
                 and payload.get("service") == "agentvault"
                 and isinstance(payload.get("durable_database"), bool)
                 and isinstance(payload.get("recovery_verified"), bool))
        result = {"path": path, "http_status": status, "ready": status == 200 and valid, "schema_valid": bool(valid)}
        if valid:
            result.update(durable_database=payload["durable_database"], recovery_verified=payload["recovery_verified"])
        return result
    if path == "/v1/plans":
        valid = (isinstance(payload, dict)
                 and isinstance(payload.get("plans"), list)
                 and isinstance(payload.get("sales_enabled"), bool)
                 and isinstance(payload.get("terms_version"), str))
        result = {"path": path, "http_status": status, "ready": status == 200 and valid, "schema_valid": bool(valid)}
        if valid:
            result["sales_enabled"] = payload["sales_enabled"]
        return result
    raise ValueError("Unsupported preflight path")

def main():
    checks = [check("/healthz"), check("/v1/plans")]
    print(json.dumps({"target": BASE_URL, "checks": checks}, indent=2))
    return 0 if all(item["ready"] for item in checks) else 1

if __name__ == "__main__":
    sys.exit(main())
