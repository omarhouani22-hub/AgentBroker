"""Authenticated Opportunity Intelligence API blueprint.

Register in app.py with:
    from opportunity_api import opportunity_api
    app.register_blueprint(opportunity_api)
The existing app.before_request authentication applies to these endpoints.
"""
from flask import Blueprint, jsonify, request
from opportunity_intelligence import evaluate

opportunity_api = Blueprint("opportunity_intelligence", __name__)

@opportunity_api.post("/opportunities/evaluate")
def evaluate_opportunity():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Expected JSON object"), 400
    title = data.get("title")
    if not isinstance(title, str) or not 1 <= len(title.strip()) <= 160:
        return jsonify(error="Title must be 1-160 characters"), 400
    try:
        result = evaluate(data.get("evidence"))
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    return jsonify(title=title.strip(), **result)
