import os
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.get("/")
def home():
    return jsonify({
        "name": "AgentBroker",
        "version": "0.8-live-bootstrap",
        "status": "online",
        "payments_enabled": False
    })

@app.get("/health")
def health():
    return jsonify({"ok": True})

@app.post("/quote")
def quote():
    data = request.get_json(silent=True) or {}
    goal = str(data.get("goal", "")).strip()
    try:
        budget = float(data.get("budget", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "budget must be numeric"}), 400
    if not goal:
        return jsonify({"error": "goal is required"}), 400
    if budget < 0:
        return jsonify({"error": "budget must be >= 0"}), 400
    return jsonify({
        "status": "quote_only",
        "goal": goal,
        "budget": budget,
        "payment_enabled": False,
        "next_stage": "live discovery + free-tool benchmark"
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
