"""In-program coordinator. An authenticated heartbeat supplies no agent decisions."""
import copy
import json
import threading
from datetime import datetime, timezone, timedelta
from flask import g, jsonify, request
import hermes_pilot as h

TEAM_LOCK = threading.Lock()
ROLES = {'coordinator': 'Choose weakest category, rotate fresh cases, assign next stage',
         'hermes': 'Ask the teacher and build a reusable candidate skill',
         'deepseek': 'Answer Hermes with a separate teaching conversation',
         'evaluator': 'Independent arithmetic checks; accept only measured improvement'}


def team_state(state):
    return state.setdefault('team', {'enabled': False, 'round': 0, 'history': [],
                                    'next_at': None, 'decision': 'Waiting for activation', 'failures': 0})


def plan(state):
    team = team_state(state)
    exp = state.get('experiment') or {}
    checks = exp.get('retest', exp.get('baseline', {})).get('evaluation', {}).get('checks', [])
    weak = [c['id'] for c in checks if not c['passed']]
    focus = weak[0] if weak else h.EXTENDED_CASES[team['round'] % len(h.EXTENDED_CASES)]['id']
    cases = copy.deepcopy(h.EXTENDED_CASES)
    # Reproducible new quantities, unchanged independently scored task semantics.
    for index, case in enumerate(cases):
        case['volume'] += (team['round'] + 1) * (index + 3) * 17
    cases.sort(key=lambda c: c['id'] != focus)
    return focus, cases, 'Revisit a failed category' if weak else 'All previous checks passed; rotate to fresh quantities'


def install_team(app, db, model_config, cipher):
    def reply(state, status='completed'):
        return jsonify(status=status, stage=(state.get('experiment') or {}).get('stage', 'waiting'),
                       checkpoint=cipher().encrypt(json.dumps(state).encode()).decode(), **h.summary(state))

    @app.post('/hermes/team')
    def control():
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or type(data.get('enabled')) is not bool:
            return jsonify(error='Supply enabled as a boolean.'), 400
        if not TEAM_LOCK.acquire(False): return jsonify(error='Coordinator busy; check status.'), 409
        try:
            if not h.LOCK.acquire(False): return jsonify(error='Hermes busy; check status.'), 409
            try:
                state = h.read_state(db)
                team = team_state(state)
                team['enabled'] = data['enabled']
                team['failures'] = 0
                team['decision'] = 'Ready for next heartbeat' if team['enabled'] else 'Paused by owner'
                h.write_state(db, state)
                return jsonify(h.summary(state))
            finally: h.LOCK.release()
        finally: TEAM_LOCK.release()

    @app.post('/hermes/team/clock')
    def tick():
        from cryptography.fernet import InvalidToken
        if not TEAM_LOCK.acquire(False): return jsonify(error='Coordinator busy.'), 409
        try:
            data = request.get_json(silent=True) or {}
            if not isinstance(data, dict): raise ValueError('Invalid request')
            # Restore only a newer authenticated encrypted snapshot; no keys in scheduler.
            if not h.LOCK.acquire(False): return jsonify(error='Hermes busy.'), 409
            try:
                state = h.read_state(db)
                sealed = data.get('checkpoint')
                if sealed:
                    if not isinstance(sealed, str) or len(sealed) > 650000: raise ValueError('Invalid checkpoint')
                    restored = json.loads(cipher().decrypt(sealed.encode()))
                    if restored.get('updated_at', '') > state.get('updated_at', ''):
                        h.restore_state(db, restored)
                        state = restored
                team = team_state(state)
                if not team['enabled']: return reply(state)
                now = datetime.now(timezone.utc)
                exp = state.get('experiment')
                if exp and exp['status'] in ('ready', 'running'):
                    if not exp.get('team_owned'):
                        team['decision'] = 'Waiting for the existing manual experiment'
                        h.write_state(db, state)
                        return reply(state)
                else:
                    if team.get('next_at') and now < datetime.fromisoformat(team['next_at']):
                        return reply(state)
                    if not h.runtime_ready(): return jsonify(error='Hermes runtime unavailable.'), 503
                    focus, cases, reason = plan(state)
                    team['round'] += 1
                    team.update(focus=focus, decision=reason, next_at=(now + timedelta(hours=1)).isoformat())
                    state['experiment'] = {'id': __import__('uuid').uuid4().hex, 'stage': 'baseline', 'status': 'ready',
                        'model_identity': h.model_identity(model_config()), 'suite': 'capacity-team-v1',
                        'cases': cases, 'teacher_enabled': True, 'team_owned': True, 'focus': focus,
                        'created_at': now.isoformat()}
                    h.write_state(db, state)
                    return reply(state, 'ready')
                identity = exp['id']
            finally: h.LOCK.release()
            # Invoke the same bounded engine without a network request or browser driver.
            with app.test_request_context('/hermes/experiments/' + identity + '/step', method='POST', json={}):
                g.hermes_team_internal = True
                app.view_functions['experiment_step'](identity)
            with h.LOCK:
                state = h.read_state(db)
                team, exp = team_state(state), state['experiment']
                if exp['status'] in ('completed', 'failed'):
                    item = {'id': exp['id'], 'round': team['round'], 'focus': exp.get('focus'),
                            'status': exp['status'], 'adopted': exp.get('adopted', False),
                            'before': exp.get('baseline', {}).get('evaluation', {}).get('score'),
                            'after': exp.get('retest', {}).get('evaluation', {}).get('score'),
                            'at': datetime.now(timezone.utc).isoformat()}
                    if not any(x['id'] == item['id'] for x in team['history']):
                        team['history'] = (team['history'] + [item])[-30:]
                        team['failures'] = team['failures'] + 1 if exp['status'] == 'failed' else 0
                    delay = 6 if exp['status'] == 'failed' else (1 if exp.get('adopted') else 3)
                    team['next_at'] = (datetime.now(timezone.utc) + timedelta(hours=delay)).isoformat()
                    team['decision'] = ('Failure: wait before a new experiment; no step retry' if exp['status'] == 'failed'
                                        else 'Accepted improvement; continue testing' if exp.get('adopted')
                                        else 'No measured gain; slow down and choose fresh cases next time')
                    if team['failures'] >= 3:
                        team.update(enabled=False, decision='Paused after three failed rounds; owner review required')
                else:
                    team['decision'] = 'Assigned next stage: ' + exp['stage']
                h.write_state(db, state)
                return reply(state, 'ready' if exp['status'] == 'ready' else 'completed')
        except (InvalidToken, ValueError, TypeError, KeyError):
            return jsonify(error='Invalid state or configuration; no automatic retry.'), 400
        finally: TEAM_LOCK.release()
