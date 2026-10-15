"""Read-only public smoke checks for a deployed AgentBroker service.

Never send credentials, create orders, invoke models or change production data.
This script deliberately expects the operator routes to reject anonymous users.
"""
import argparse
import json
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def request_status(url, *, timeout=15):
    req = Request(url, headers={"User-Agent": "AgentBroker-readonly-smoke/1.0"})
    try:
        with urlopen(req, timeout=timeout) as response:
            return response.status, response.read(16384)
    except HTTPError as error:
        return error.code, error.read(16384)


def run(base_url, *, attempts=3, wait=5):
    parsed = urlsplit(base_url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("Expected an HTTPS origin without embedded credentials")
    origin = f"{parsed.scheme}://{parsed.netloc}"
    paths = (
        ("/health", {200}),
        ("/offers/jd-audit/operator-dashboard", {401, 503}),
        ("/offers/jd-audit/operator-queue-preview", {401, 503}),
    )
    failures = []
    for path, allowed in paths:
        status = None
        for attempt in range(attempts):
            try:
                status, body = request_status(origin + path)
                if status in allowed:
                    break
            except (URLError, TimeoutError) as exc:
                status = f"network-error:{type(exc).__name__}"
            if attempt < attempts - 1:
                time.sleep(wait)
        print(f"{path}: {status}")
        if status not in allowed:
            failures.append(path)
    if failures:
        raise RuntimeError("Smoke check failed: " + ", ".join(failures))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="https://agentbroker-jayk.onrender.com")
    args = parser.parse_args()
    try:
        run(args.base_url)
    except (ValueError, RuntimeError) as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
