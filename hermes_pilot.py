"""Bounded Hermes integration with measured skill promotion and encrypted recovery."""
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile
import threading
from datetime import datetime, timezone
import uuid

from flask import jsonify, request

ROOT = Path(__file__).resolve().parent
REVISION = 'f80d888e2f6b3268c72c5ac32a55a63432751c0d'
LOCK = threading.Lock()
SCOPE = 'Four synthetic workforce calculations only; not general intelligence or factual reliability.'
CASES = [
    {'id': 'minutes', 'volume': 15000, 'time': 30, 'unit': 'minutes', 'annual_hours': 1500},
    {'id': 'rounding', 'volume': 1000, 'time': 20, 'unit': 'minutes', 'annual_hours': 1500},
    {'id': 'hours', 'volume': 2400, 'time': 1.25, 'unit': 'hours', 'annual_hours': 1600},
    {'id': 'missing', 'volume': 1200, 'time': 15, 'unit': 'minutes', 'annual_hours': None},
]


def validate_skills(skills):
    if not isinstance(skills, dict) or len(skills) > 20:
        raise ValueError('Invalid skills')
    for name, content in skills.items():
        p = PurePosixPath(name)
        if (not isinstance(name, str) or len(name) > 200 or p.is_absolute()
                or len(p.parts) not in (2, 3) or p.name != 'SKILL.md'
                or any(not re.fullmatch(r'[a-zA-Z0-9_.-]+', part) or part in ('.', '..') for part in p.parts)
                or not isinstance(content, str) or len(content.encode()) > 12000):
            raise ValueError('Invalid skill document')
    return skills


def runtime_path():
    return Path(os.getenv('HERMES_PYTHON', str(ROOT / '.hermes-runtime' / 'bin' / 'python')))


def runtime_ready():
    return runtime_path().is_file()


def invoke(config, prompt, skills, mode='task'):
    """No shell, no inherited provider/account credentials, one temporary profile."""
    validate_skills(skills)
    if not runtime_ready():
        raise ValueError('Hermes runtime is not installed')
    with tempfile.TemporaryDirectory(prefix='agentbroker-hermes-') as directory:
        home = Path(directory)
        for name, content in skills.items():
            path = home / 'skills' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')
        env = {k: os.environ[k] for k in ('PATH', 'LANG', 'SSL_CERT_FILE', 'SSL_CERT_DIR') if k in os.environ}
        env.update(HERMES_HOME=directory, PYTHONUNBUFFERED='1')
        payload = dict(model=config['model'], key=config['key'],
                       base_url=config['endpoint'].removesuffix('/chat/completions'),
                       mode=mode, prompt=prompt)
        # Temporary logs are deleted with this profile; never returned to the client.
        with (home / 'stdout').open('w+') as out, (home / 'stderr').open('w+') as err:
            subprocess.run([str(runtime_path()), str(ROOT / 'hermes_worker.py')],
                           input=json.dumps(payload), text=True, env=env, cwd=directory,
                           stdout=out, stderr=err, timeout=100, check=True)
            out.seek(0)
            raw = out.read(100001)
        if len(raw) > 100000:
            raise ValueError('Hermes output too large')
        result = json.loads(raw)
        if result.get('completed') is not True or not isinstance(result.get('output'), str):
            raise ValueError('Hermes session did not complete')
        updated = {}
        for path in (home / 'skills').rglob('SKILL.md'):
            if path.is_symlink() or home not in path.resolve().parents or path.stat().st_size > 12000:
                raise ValueError('Invalid skill file')
            updated[path.relative_to(home / 'skills').as_posix()] = path.read_text(encoding='utf-8')
        result['skills'] = validate_skills(updated)
        return result


def evaluate(output):
    try:
        answers = json.loads(re.sub(r'^```(?:json)?\s*|\s*```$', '', output.strip()))
    except (ValueError, TypeError):
        answers = {}
    checks = []
    for case in CASES:
        item = answers.get(case['id'], {}) if isinstance(answers, dict) else {}
        if not isinstance(item, dict):
            item = {}
        if case['annual_hours'] is None:
            passed = item.get('status') == 'insufficient_data' and item.get('fte') is None and item.get('staff') is None
        else:
            hours = case['volume'] * case['time'] / (60 if case['unit'] == 'minutes' else 1)
            expected = hours / case['annual_hours']
            fte, staff = item.get('fte'), item.get('staff')
            passed = (type(fte) in (int, float) and math.isfinite(fte)
                      and abs(fte - expected) <= .001 and type(staff) is int
                      and staff == math.ceil(expected))
        checks.append({'id': case['id'], 'passed': bool(passed)})
    return {'score': sum(c['passed'] for c in checks), 'total': len(checks), 'checks': checks}


def task_prompt():
    return ('Calculate the annual full-time equivalent workload (fte) and whole employees needed (staff). '
            'Do not invent missing inputs. Return only a JSON object keyed by case id. Each value must contain '
            'status (ok or insufficient_data), fte (number or null), staff (integer or null). Data: '
            + json.dumps(CASES))


def training_prompt(baseline):
    # Distinct training examples: the candidate never receives holdout numbers/answers.
    return ('Create or improve a reusable workforce-capacity calculation skill. Evaluation categories: '
            + json.dumps(baseline['evaluation']['checks'])
            + '. Worked training examples: 600 tasks/year at 10 minutes, 1000 productive hours/person/year '
            'means 100 workload hours, 0.1 FTE, one whole employee. 400 tasks at 3 hours with 1000 '
            'productive hours means 1.2 FTE, two whole employees. Without productive annual hours, '
            'request the missing input; never assume 2080. Explain units and ceiling versus nearest rounding. '
            'Store one general SKILL.md using skill_manage, then finish. Do not embed these example numbers '
            'or evaluation case ids in the skill. No scripts or other files are needed.')


def initial_state():
    return {'version': 1, 'skills': {}, 'experiment': None}


def model_identity(config):
    return hashlib.sha256(json.dumps({k: config[k] for k in ('model', 'endpoint')}, sort_keys=True).encode()).hexdigest()


def read_state(db):
    with db() as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS hermes_pilot (id INTEGER PRIMARY KEY, payload TEXT NOT NULL)')
        row = conn.execute('SELECT payload FROM hermes_pilot WHERE id=1').fetchone()
    return json.loads(row[0]) if row else initial_state()


def write_state(db, state):
    with db() as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS hermes_pilot (id INTEGER PRIMARY KEY, payload TEXT NOT NULL)')
        conn.execute('INSERT OR REPLACE INTO hermes_pilot VALUES (1, ?)', (json.dumps(state),))


def restore_state(db, state):
    if not isinstance(state, dict) or state.get('version') != 1:
        raise ValueError('Invalid Hermes checkpoint')
    validate_skills(state.get('skills'))
    experiment = state.get('experiment')
    if experiment is not None:
        if not isinstance(experiment, dict) or experiment.get('stage') not in ('baseline', 'learn', 'retest', 'done'):
            raise ValueError('Invalid experiment')
        validate_skills(experiment.get('candidate', {}))
    if len(json.dumps(state)) > 400000:
        raise ValueError('Checkpoint too large')
    write_state(db, state)


def summary(state):
    experiment = state.get('experiment')
    if experiment:
        experiment = {k: v for k, v in experiment.items() if k != 'candidate'}
    return {'runtime_installed': runtime_ready(), 'upstream_revision': REVISION,
            'skill_count': len(state['skills']), 'skills': list(state['skills']),
            'experiment': experiment, 'scope': SCOPE}


def install_routes(app, db, model_config, cipher):
    @app.get('/hermes/status')
    def hermes_status():
        return jsonify(summary(read_state(db)))

    @app.post('/hermes/experiments')
    def start_experiment():
        if not runtime_ready():
            return jsonify(error='Hermes runtime is not installed on this server.'), 503
        try:
            config = model_config()
        except ValueError:
            return jsonify(error='Model provider is not configured.'), 503
        if not LOCK.acquire(blocking=False):
            return jsonify(error='Hermes is busy.'), 409
        try:
            state = read_state(db)
            if state['experiment'] and state['experiment']['status'] in ('ready', 'running'):
                return jsonify(error='An experiment already exists; resume it.', **summary(state)), 409
            state['experiment'] = {'id': uuid.uuid4().hex, 'stage': 'baseline', 'status': 'ready',
                                   'model_identity': model_identity(config),
                                   'created_at': datetime.now(timezone.utc).isoformat()}
            write_state(db, state)
            return jsonify(summary(state)), 201
        finally:
            LOCK.release()

    @app.post('/hermes/experiments/<identity>/step')
    def experiment_step(identity):
        if not LOCK.acquire(blocking=False):
            return jsonify(error='Hermes is busy.'), 409
        try:
            state = read_state(db)
            exp = state['experiment']
            if not exp or exp['id'] != identity:
                return jsonify(error='Experiment not found.'), 404
            if exp['status'] == 'running':
                exp.update(status='failed', error='Previous step interrupted; no automatic charged retry.')
                write_state(db, state)
                return jsonify(summary(state)), 409
            if exp['status'] != 'ready':
                return jsonify(summary(state)), 409
            config = model_config()
            if exp.get('model_identity') != model_identity(config):
                exp.update(status='failed', error='Model configuration changed; start a new comparison.')
                write_state(db, state)
                return jsonify(summary(state)), 409
            exp.update(status='running')
            write_state(db, state)
            try:
                stage = exp['stage']
                skills = exp.get('candidate', state['skills'])
                result = invoke(config, training_prompt(exp['baseline']) if stage == 'learn' else task_prompt(),
                                skills, mode='learn' if stage == 'learn' else 'task')
                metrics = {k: result[k] for k in ('api_calls', 'total_tokens', 'elapsed_seconds', 'tools_used')}
                if stage == 'learn':
                    exp['candidate'] = result['skills']
                    exp['learning'] = metrics
                    exp['skill_changed'] = result['skills'] != state['skills']
                    exp.update(stage='retest', status='ready')
                else:
                    metrics['evaluation'] = evaluate(result['output'])
                    metrics['output'] = result['output']
                    exp[stage] = metrics
                    if stage == 'baseline':
                        exp.update(stage='learn', status='ready')
                    else:
                        before, after = exp['baseline']['evaluation'], metrics['evaluation']
                        no_regression = all(not a['passed'] or b['passed']
                                            for a, b in zip(before['checks'], after['checks']))
                        exp['adopted'] = bool(exp['skill_changed'] and no_regression and after['score'] > before['score'])
                        exp['no_case_regression'] = no_regression
                        if exp['adopted']:
                            state['skills'] = exp['candidate']
                        exp.update(stage='done', status='completed')
            except Exception as error:
                app.logger.warning('Hermes step failure=%s', type(error).__name__)
                exp.update(status='failed', error='Hermes step failed. Accepted skills retained; no automatic retry.')
            write_state(db, state)
            return jsonify(summary(state)), 502 if exp['status'] == 'failed' else 200
        except ValueError:
            return jsonify(error='Invalid provider configuration.'), 503
        finally:
            LOCK.release()

    @app.post('/hermes/tasks')
    def hermes_task():
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or not isinstance(data.get('goal'), str) or not 1 <= len(data['goal'].strip()) <= 1000:
            return jsonify(error='Supply a task of 1–1000 characters.'), 400
        if not LOCK.acquire(blocking=False):
            return jsonify(error='Hermes is busy.'), 409
        try:
            result = invoke(model_config(), data['goal'].strip(), read_state(db)['skills'])
            result.pop('skills', None)
            return jsonify(result)
        except Exception as error:
            app.logger.warning('Hermes task failure=%s', type(error).__name__)
            return jsonify(error='Hermes task failed or runtime unavailable. No automatic retry.'), 502
        finally:
            LOCK.release()

    @app.get('/hermes/export')
    def export():
        sealed = cipher().encrypt(json.dumps(read_state(db)).encode()).decode()
        response = jsonify(version=1, checkpoint=sealed)
        response.headers['Content-Disposition'] = 'attachment; filename="agentbroker-hermes-checkpoint.json"'
        return response

    @app.post('/hermes/import')
    def restore():
        from cryptography.fernet import InvalidToken
        if not LOCK.acquire(blocking=False):
            return jsonify(error='Hermes is busy.'), 409
        try:
            current = read_state(db)
            if current['skills'] or current['experiment']:
                return jsonify(error='Hermes state already exists; import never overwrites it.'), 409
            data = request.get_json(silent=True)
            if not isinstance(data, dict) or not isinstance(data.get('checkpoint'), str) or len(data['checkpoint']) > 600000:
                raise ValueError('Invalid checkpoint')
            restored = json.loads(cipher().decrypt(data['checkpoint'].encode()))
            restore_state(db, restored)
            return jsonify(summary(restored))
        except (InvalidToken, ValueError, TypeError, KeyError):
            return jsonify(error='Invalid encrypted Hermes checkpoint.'), 400
        finally:
            LOCK.release()
