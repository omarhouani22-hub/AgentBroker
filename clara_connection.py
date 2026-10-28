"""Private, content-free connection observations. Reset on process restart."""
from datetime import datetime, timezone
import re
import threading
from time import monotonic
from urllib.error import HTTPError, URLError

_LOCK = threading.Lock()
_LAST = None


def reported_model(value):
    # Provider metadata is untrusted. Never turn arbitrary text into status/logs.
    if (isinstance(value, str) and 1 <= len(value) <= 160
            and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:/-]*', value)
            and not re.search(r'(?i)(sk-|bearer|password|api.?key|https?:)', value)):
        return value
    return 'unknown'


def route(context=None):
    import local_chat
    import trained_model
    if local_chat.enabled():
        return 'local'
    if (context or {}).get('model') == 'trained' and trained_model.configured():
        return 'experimental_local_with_free_fallback'
    return 'openrouter_free'


def observe(generate, context):
    global _LAST
    started = monotonic()
    selected = route(context)
    record = {'selected_route': selected, 'route': 'unknown', 'model': 'unknown',
              'status': 'unavailable', 'error': None,
              'checked_at': datetime.now(timezone.utc).isoformat()}
    try:
        result = generate(context)
        if result.get('skip') or not result.get('content'):
            raise ValueError('Missing answer')
        marker = result.get('_model')
        record['route'] = {'agentbroker_local': 'local',
                           'agentbroker_local_transport': 'local_rule',
                           'agentbroker_trained': 'experimental_local',
                           'free_router': 'openrouter_free'}.get(marker, 'unknown')
        record['model'] = reported_model(result.get('_reported_model'))
        record['status'] = 'ok'
        return result
    except Exception as error:
        code = getattr(error, 'code', None)
        record['error'] = ('rate_limited' if code == 429 else
                           'authentication_failed' if code in (401, 403) else
                           'timeout' if isinstance(error, TimeoutError) else
                           'network_unavailable' if isinstance(error, URLError) and not isinstance(error, HTTPError) else
                           'provider_unavailable' if type(code) is int and code >= 500 else
                           'invalid_or_unavailable_response')
        raise
    finally:
        record['duration_ms'] = round((monotonic() - started) * 1000)
        with _LOCK:
            _LAST = record


def install_routes(app, db):
    from flask import jsonify, request
    import local_chat
    import moltbook as m

    def snapshot():
        companion = m.companion_state(m.dialogue_state(db))
        selected = route(companion)
        today = datetime.now(timezone.utc).date().isoformat()
        used = companion['reply_calls'] if companion['reply_day'] == today else 0
        with _LOCK:
            last = dict(_LAST) if _LAST else None
        return {'selected_route': selected,
                'configured': local_chat.configured() if selected == 'local' else
                    bool(m.free_model_key()) if selected == 'openrouter_free' else True,
                'requested_model': 'openrouter/free' if selected == 'openrouter_free' else 'local configuration',
                'last_observation': last, 'observation_scope': 'this server process; resets on restart',
                'free_only': True, 'paid_fallback': False,
                'daily_limit': None if selected == 'local' else 12,
                'remaining_today': None if selected == 'local' else max(0, 12-used),
                'storage_actions': 'Not connected or tested by this connection check'}

    @app.after_request
    def private_connection_headers(response):
        if request.path.startswith('/companion/connection'):
            response.headers['Cache-Control'] = 'no-store'
            response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @app.get('/companion/connection')
    def connection_status():
        return jsonify(snapshot())

    @app.post('/companion/connection/test')
    def connection_test():
        # No arbitrary prompt, private profile, history, memory or tools.
        if request.get_json(silent=True) != {}:
            return jsonify(error='Send an empty JSON object; this check uses a fixed message'), 400
        if not m.DIALOGUE_LOCK.acquire(False):
            return jsonify(error='Clara is busy; try shortly'), 409
        try:
            state = m.dialogue_state(db)
            companion = m.validate_companion(m.companion_state(state))
            day = datetime.now(timezone.utc).date().isoformat()
            if companion['reply_day'] != day:
                companion.update(reply_day=day, reply_calls=0)
            if not local_chat.enabled():
                if companion['reply_calls'] >= 12:
                    return jsonify(error='Free conversation allowance reached today; try tomorrow'), 429
                companion['reply_calls'] += 1
                m.save_dialogue_state(db, state)
            try:
                result = m.free_dialogue_json({'_companion': True, 'language': 'en',
                    'model': companion.get('model', 'free'),
                    'conversation': [{'role': 'user', 'content': 'Hello Clara. Reply with a short greeting.'}]})
                if result.get('skip') or not result.get('content'):
                    raise ValueError('Missing answer')
                # Return the outcome, never generated text or raw provider errors.
                return jsonify(result='Clara returned a valid response', **snapshot())
            except Exception as error:
                if isinstance(error, HTTPError):
                    error.close()
                return jsonify(error='Connection check failed; see the safe error category', **snapshot()), 503
        finally:
            m.DIALOGUE_LOCK.release()
