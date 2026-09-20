"""Bounded DeepSeek agent. No external actions other than model requests."""
import hmac
import json
import math
import os
import sqlite3
import uuid
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from flask import Flask, jsonify, request

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16000
VERSION = '1.0-deepseek-agent'

def db():
    conn = sqlite3.connect(os.getenv('AGENT_DB_PATH', 'agentbroker.sqlite3'), timeout=10)
    conn.execute('CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, record TEXT NOT NULL)')
    return conn

def save(record):
    with db() as conn:
        conn.execute('INSERT OR REPLACE INTO runs VALUES (?, ?)', (record['id'], json.dumps(record)))

@app.before_request
def authenticate():
    if request.path in ('/', '/health'):
        return
    token = os.getenv('AGENT_ACCESS_TOKEN', '')
    if len(token) < 32:
        return jsonify(error='Configure AGENT_ACCESS_TOKEN with at least 32 characters'), 503
    if not hmac.compare_digest(request.headers.get('Authorization', ''), 'Bearer ' + token):
        return jsonify(error='Unauthorized'), 401

@app.get('/')
def home():
    return jsonify(name='AgentBroker', version=VERSION, status='online',
                   configured=bool(os.getenv('DEEPSEEK_API_KEY')) and len(os.getenv('AGENT_ACCESS_TOKEN', '')) >= 32,
                   payments_enabled=False)

@app.get('/health')
def health():
    return jsonify(ok=True, version=VERSION)

def tool(name, args):
    if name != 'calculate_service_margin':
        return {'error': 'Tool not allowed'}
    if not isinstance(args, dict) or set(args) != {'price', 'hours', 'hourly_cost', 'other_cost'}:
        return {'error': 'Expected price, hours, hourly_cost, other_cost'}
    if any(type(x) not in (float, int) or not math.isfinite(x) or x < 0 or x > 1000000 for x in args.values()):
        return {'error': 'Inputs must be finite numbers from 0 to 1000000'}
    cost = args['hours'] * args['hourly_cost'] + args['other_cost']
    profit = args['price'] - cost
    return {'cost': round(cost, 2), 'profit': round(profit, 2),
            'margin_percent': round(100 * profit / args['price'], 2) if args['price'] else None,
            'basis': 'User/model assumptions; not evidence of demand or realized revenue'}

TOOLS = [{'type': 'function', 'function': {
    'name': 'calculate_service_margin',
    'description': 'Calculate service cost, profit and margin from explicit assumptions in a single currency.',
    'parameters': {'type': 'object', 'properties': {key: {'type': 'number'} for key in ('price', 'hours', 'hourly_cost', 'other_cost')},
                   'required': ['price', 'hours', 'hourly_cost', 'other_cost'], 'additionalProperties': False}}}]

def model_call(messages):
    payload = {'model': os.getenv('DEEPSEEK_MODEL', 'deepseek-chat'), 'messages': messages,
               'tools': TOOLS, 'max_tokens': 1200, 'stream': False}
    req = Request('https://api.deepseek.com/chat/completions', data=json.dumps(payload).encode(),
                  headers={'Authorization': 'Bearer ' + os.environ['DEEPSEEK_API_KEY'], 'Content-Type': 'application/json'})
    with urlopen(req, timeout=20) as response:
        raw = response.read(200001)
    if len(raw) > 200000:
        raise ValueError('Provider response too large')
    return json.loads(raw)['choices'][0]['message']

@app.post('/runs')
def run():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get('goal'), str) or not 1 <= len(data['goal'].strip()) <= 4000:
        return jsonify(error='goal must be a non-empty string, at most 4000 characters'), 400
    if not os.getenv('DEEPSEEK_API_KEY'):
        return jsonify(error='DEEPSEEK_API_KEY is not configured'), 503
    record = {'id': uuid.uuid4().hex, 'goal': data['goal'].strip(), 'status': 'running', 'events': [], 'output': None}
    save(record)
    messages = [{'role': 'system', 'content': (
        'You prepare practical small-business service offers. Respond in the user language. '
        'Produce a usable offer draft, deliverables, pricing assumptions and a measurable validation experiment. '
        'Use the calculator when estimating profit. Distinguish assumptions from evidence. '
        'You have NO browsing, email, payment, publishing or self-modification tools. '
        'Never claim research, sales, messages or payments occurred. No revenue guarantees. '
        'Only available tool outputs count as executed actions. Ask for missing critical context when needed.')},
        {'role': 'user', 'content': record['goal']}]
    try:
        for _ in range(4):
            message = model_call(messages)
            calls = message.get('tool_calls') or []
            messages.append(message)
            if not calls:
                output = message.get('content')
                if not isinstance(output, str) or not output.strip():
                    raise ValueError('Empty model response')
                record.update(status='completed', output=output)
                break
            if len(calls) > 4:
                raise ValueError('Too many tool calls')
            for call in calls:
                name = call['function']['name']
                try:
                    args = json.loads(call['function']['arguments'])
                    result = tool(name, args)
                except (TypeError, ValueError):
                    result = {'error': 'Invalid tool arguments'}
                record['events'].append({'tool': name, 'result': result})
                messages.append({'role': 'tool', 'tool_call_id': call['id'], 'content': json.dumps(result)})
            save(record)
        else:
            record.update(status='stopped', error='Four model requests reached; no final answer produced')
    except HTTPError as error:
        record.update(status='failed', error=f'DeepSeek returned HTTP {error.code}; check API configuration and credit')
    except (URLError, TimeoutError, ValueError, KeyError, TypeError, IndexError):
        record.update(status='failed', error='Provider timeout or invalid response; no automatic retry performed')
    save(record)
    return jsonify(record), 200 if record['status'] == 'completed' else 502

@app.get('/runs/<run_id>')
def read_run(run_id):
    with db() as conn:
        row = conn.execute('SELECT record FROM runs WHERE id = ?', (run_id,)).fetchone()
    return jsonify(json.loads(row[0])) if row else (jsonify(error='Run not found'), 404)

@app.post('/quote')
def quote():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get('goal'), str) or not data['goal'].strip():
        return jsonify(error='goal is required'), 400
    try:
        budget = float(data.get('budget', 0))
        if not math.isfinite(budget) or budget < 0:
            raise ValueError()
    except (TypeError, ValueError):
        return jsonify(error='budget must be finite and >= 0'), 400
    return jsonify(status='quote_only', goal=data['goal'], budget=budget, payment_enabled=False)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', '10000')))
