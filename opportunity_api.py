"""Authenticated Opportunity Intelligence API blueprint.

Register in app.py with:
    from opportunity_api import opportunity_api
    app.register_blueprint(opportunity_api)
The existing app.before_request authentication applies to these endpoints.
"""
from flask import Blueprint, jsonify, request, render_template_string
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

@opportunity_api.get("/opportunities/")
def opportunity_dashboard():
    fields = list(__import__("opportunity_intelligence").WEIGHTS.items())
    return render_template_string("""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Opportunity Intelligence</title>
<style>body{background:#101728;color:#eef2ff;font:16px system-ui;margin:auto;max-width:720px;padding:22px}label{display:block;margin:16px 0}input,textarea{box-sizing:border-box;width:100%;padding:12px;background:#1b2842;color:white;border:1px solid #6b7a9d;border-radius:8px}button{padding:13px;background:#758aff;border:0;border-radius:8px;font-weight:bold}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style>
<h1>Opportunity Intelligence</h1><p>Manual evidence scoring pilot. A high score does not prove market demand.</p><form id="f"><label>Opportunity title<input id="title" maxlength="160" required></label>
{% for name,weight in fields %}<label>{{name.replace('_',' ').title()}} ({{weight}}%)
<input name="{{name}}_rating" type="number" min="0" max="5" required placeholder="Rating 0–5"><textarea name="{{name}}_note" required placeholder="Evidence and source / interview notes"></textarea></label>{% endfor %}
<button>Evaluate</button></form><pre id="out" role="status"></pre><script>
document.getElementById('f').onsubmit=async e=>{e.preventDefault();let f=new FormData(e.target),evidence={};for(let k of {{ names|tojson }})evidence[k]={rating:Number(f.get(k+'_rating')),note:f.get(k+'_note')};try{let r=await fetch('/opportunities/evaluate',{method:'POST',headers:{'Content-Type':'application/json','X-AgentBroker-Request':'1'},body:JSON.stringify({title:document.getElementById('title').value,evidence})});document.getElementById('out').textContent=JSON.stringify(await r.json(),null,2)}catch(err){document.getElementById('out').textContent=String(err)}};</script></html>""",fields=fields,names=[name for name,_ in fields])
