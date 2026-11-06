"""Owner-only Wix inbox route for Clara. Read-only; no automatic outreach."""
import json
import os
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from flask import jsonify

from integrations.localsite_inbox import prepare_inquiry

WIX_URL = "https://www.wixapis.com/form-submission-service/v4/submissions/namespace/query"
FORM_ID = "0624063e-6ab5-4ba4-a5bc-46273057e367"
SITE_ID = "3cbc13ce-b099-4bb1-b81f-5b9fff88ba6e"


def fetch_wix_inbox():
    token = os.getenv("WIX_API_TOKEN", "")
    if not token:
        raise RuntimeError("WIX_API_TOKEN not configured")
    body = {"query": {"filter": {"formId": FORM_ID, "namespace": "wix.form_app.form"}, "cursorPaging": {"limit": 20}}}
    req = Request(WIX_URL, data=json.dumps(body).encode(), method="POST", headers={
        "Authorization": token if token.startswith("Bearer ") else "Bearer " + token,
        "wix-site-id": SITE_ID,
        "Content-Type": "application/json",
    })
    try:
        with urlopen(req, timeout=12) as response:
            result = json.load(response)
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        raise RuntimeError("Wix inbox unavailable") from exc
    return [prepare_inquiry(item) for item in result.get("submissions", [])[:20]]


def register_routes(app):
    @app.get("/clara/localsite/inquiries")
    def clara_localsite_inquiries():
        try:
            inquiries = fetch_wix_inbox()
        except RuntimeError:
            response = jsonify(error="Wix inbox not configured or unavailable")
            response.status_code = 503
        else:
            response = jsonify(inquiries=inquiries, read_only=True, outbound_enabled=False)
        response.headers["Cache-Control"] = "no-store"
        return response
