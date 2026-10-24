"""Standalone AgentVault HTTP API for a controlled beta.

Start with: AGENTVAULT_KEY=... AGENTVAULT_TOKEN_HASHES='{"agent-id":"sha256hex"}'
AGENTVAULT_DIR=/persistent/vault gunicorn agentvault_api:app

This is not production-ready without durable storage, quotas, rate limiting,
monitoring and independently tested disaster recovery.
"""
import json
import os
from flask import Flask, jsonify, request
from agentvault import AgentVault

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024


def _vault():
    key = os.environ.get("AGENTVAULT_KEY")
    directory = os.environ.get("AGENTVAULT_DIR")
    hashes = os.environ.get("AGENTVAULT_TOKEN_HASHES")
    if not key or not directory or not hashes:
        raise RuntimeError("AgentVault is not configured")
    return AgentVault(directory, key.encode(), json.loads(hashes))


def _credentials():
    agent = request.headers.get("X-Agent-Id", "")
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer ") or len(auth) > 512 or len(auth) <= 7:
        raise PermissionError("Unauthorized")
    return agent, auth[7:]


@app.errorhandler(413)
def too_large(_):
    return jsonify(error="checkpoint_too_large"), 413


@app.route("/healthz", methods=["GET"])
def health():
    return jsonify(status="ok", service="agentvault", storage_ready=bool(
        os.environ.get("AGENTVAULT_KEY") and os.environ.get("AGENTVAULT_DIR") and os.environ.get("AGENTVAULT_TOKEN_HASHES")))


@app.route("/v1/checkpoint", methods=["PUT"])
def save_checkpoint():
    try:
        agent, token = _credentials()
        payload = request.get_data()
        version = _vault().save(agent, token, payload)
        return jsonify(version=version), 200
    except PermissionError:
        return jsonify(error="unauthorized"), 401
    except ValueError:
        return jsonify(error="invalid_checkpoint"), 400
    except RuntimeError:
        return jsonify(error="unavailable"), 503


@app.route("/v1/checkpoint", methods=["GET"])
def restore_checkpoint():
    try:
        agent, token = _credentials()
        result = _vault().restore(agent, token)
        if result is None:
            return jsonify(error="not_found"), 404
        return result, 200, {"Content-Type": "application/octet-stream",
                             "Cache-Control": "no-store",
                             "X-Content-Type-Options": "nosniff"}
    except PermissionError:
        return jsonify(error="unauthorized"), 401
    except ValueError:
        return jsonify(error="invalid_checkpoint"), 400
    except RuntimeError:
        return jsonify(error="unavailable"), 503
