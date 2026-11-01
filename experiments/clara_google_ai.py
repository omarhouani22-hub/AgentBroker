"""Opt-in, isolated Google Gemini test. Never used in production routing."""
import json
import os
from urllib.request import Request, urlopen
from urllib.parse import quote

DEFAULT_MODEL = "gemini-2.5-flash"

def prepare_request(prompt: str, model: str = DEFAULT_MODEL) -> tuple[str, bytes]:
    if not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 500:
        raise ValueError("Prompt must be 1–500 characters")
    if not model.replace("-", "").replace(".", "").isalnum():
        raise ValueError("Invalid model")
    url = "https://generativelanguage.googleapis.com/v1beta/models/" + quote(model, safe="") + ":generateContent"
    body = json.dumps({"contents": [{"role": "user", "parts": [{"text": prompt.strip()}]}],
                       "generationConfig": {"maxOutputTokens": 160}}).encode("utf-8")
    return url, body

def test_gemini(prompt: str) -> str:
    """Only runs with explicit opt-in and user-configured key; no paid fallback."""
    if os.getenv("CLARA_EXPERIMENT_GOOGLE_ENABLED") != "1":
        raise RuntimeError("Google experiment disabled")
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not configured")
    url, body = prepare_request(prompt, os.getenv("CLARA_EXPERIMENT_GOOGLE_MODEL", DEFAULT_MODEL))
    req = Request(url, data=body, method="POST",
                  headers={"Content-Type": "application/json", "x-goog-api-key": key})
    with urlopen(req, timeout=20) as response:
        data = json.load(response)
    candidates = data.get("candidates", [])
    parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
    answer = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
    if not answer.strip():
        raise RuntimeError("Provider returned no text")
    return answer[:2000]
