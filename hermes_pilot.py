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

from flask import g, jsonify, request

ROOT = Path(__file__).resolve().parent
REVISION = 'f80d888e2f6b3268c72c5ac32a55a63432751c0d'
LOCK = threading.Lock()
SCOPE = 'Synthetic workforce calculations only; not general intelligence or factual reliability.'
CASES = [
    {'id': 'minutes', 'volume': 15000, 'time': 30, 'unit': 'minutes', 'annual_hours': 1500},
    {'id': 'rounding', 'volume': 1000, 'time': 20, 'unit': 'minutes', 'annual_hours': 1500},
    {'id': 'hours', 'volume': 2400, 'time': 1.25, 'unit': 'hours', 'annual_hours': 1600},
    {'id': 'missing', 'volume': 1200, 'time': 15, 'unit': 'minutes', 'annual_hours': None},
]


EXTENDED_CASES = [
    {'id': 'minutes', 'volume': 17600, 'time': 17, 'unit': 'minutes', 'annual_hours': 1480},
    {'id': 'rounding', 'volume': 9001, 'time': 12, 'unit': 'minutes', 'annual_hours': 1800},
    {'id': 'hours', 'volume': 3150, 'time': 0.75, 'unit': 'hours', 'annual_hours': 1575},
    {'id': 'seconds', 'volume': 84000, 'time': 95, 'unit': 'seconds', 'annual_hours': 1650},
    {'id': 'monthly', 'volume': 875, 'periods_per_year': 12, 'time': 14, 'unit': 'minutes', 'annual_hours': 1550},
    {'id': 'availability', 'volume': 7200, 'time': 22, 'unit': 'minutes', 'annual_hours': 1800, 'unavailable_fraction': 0.23},
    {'id': 'overhead', 'volume': 6400, 'time': 11, 'unit': 'minutes', 'annual_hours': 1600, 'fixed_annual_hours': 240},
    {'id': 'missing', 'volume': 3500, 'time': 18, 'unit': 'minutes', 'annual_hours': None},
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
                       mode=mode, prompt=prompt,
                       json_output=mode == 'benchmark' and (config.get('provider') == 'deepseek' or
                           config['endpoint'].startswith(('http://127.0.0.1:', 'http://localhost:'))))
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


def evaluate(output, cases=None):
    """Score content separately from strict JSON formatting; reject ambiguous blocks."""
    cases = CASES if cases is None else cases
    answers, strict, extracted = {}, False, False
    def decode(value):
        def unique(pairs):
            result = {}
            for key, item in pairs:
                if key in result:
                    raise ValueError('Duplicate JSON key')
                result[key] = item
            return result
        return json.loads(value, object_pairs_hook=unique,
                          parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    try:
        answers = decode(output.strip())
        strict = isinstance(answers, dict)
    except (ValueError, TypeError, AttributeError):
        blocks = re.findall(r'```(?:json)?\s*([\s\S]*?)```', output or '')
        if len(blocks) == 1:
            try:
                answers = decode(blocks[0])
                extracted = isinstance(answers, dict)
            except (ValueError, TypeError):
                pass
    checks = []
    from decimal import Decimal, ROUND_CEILING
    for case in cases:
        item = answers.get(case['id'], {}) if isinstance(answers, dict) else {}
        if not isinstance(item, dict):
            item = {}
        if case['annual_hours'] is None:
            passed = (item.get('status') == 'insufficient_data' and 'fte' in item and 'staff' in item
                      and item['fte'] is None and item['staff'] is None)
        else:
            d = lambda x: Decimal(str(x))
            hours = d(case['volume']) * d(case.get('periods_per_year', 1)) * d(case['time']) / d({'minutes':60, 'seconds':3600, 'hours':1}[case['unit']])
            hours += d(case.get('fixed_annual_hours', 0))
            expected = hours / (d(case['annual_hours']) * (1-d(case.get('unavailable_fraction', 0))))
            fte, staff = item.get('fte'), item.get('staff')
            passed = (item.get('status') == 'ok' and type(fte) in (int, float) and math.isfinite(fte)
                      and abs(d(fte) - expected) <= d(.001) and type(staff) is int
                      and staff == int(expected.to_integral_value(rounding=ROUND_CEILING)))
        checks.append({'id': case['id'], 'passed': bool(passed)})
    expected_ids = {case['id'] for case in cases}
    schema = isinstance(answers, dict) and set(answers) == expected_ids and all(
        isinstance(item, dict) and set(item) == {'status', 'fte', 'staff'} for item in answers.values())
    return {'score': sum(c['passed'] for c in checks), 'total': len(checks), 'checks': checks,
            'format_valid': strict and schema, 'json_extracted': extracted,
            'parse_status': 'strict_json' if strict else 'single_fenced_json' if extracted else 'invalid_or_ambiguous'}


def task_prompt(cases=None):
    return ('Calculate annual full-time equivalent workload (fte) and whole employees needed (staff). '
            'Volume is annual unless periods_per_year is given; then annualize it. '
            'Add fixed_annual_hours to workload. annual_hours is per employee before subtracting '
            'unavailable_fraction, if provided. Use ceiling on unrounded FTE for staff. '
            'Report fte to at least six decimal places when fractional; numeric error must be <=0.001. '
            'Use double-quoted keys, numeric values or null, and no stray quotes or trailing commas. '
            'For missing data use exactly {"status":"insufficient_data","fte":null,"staff":null}. '
            'Do not invent missing inputs. Return ONLY a JSON object, no Markdown or explanation, keyed by case id. '
            'Each value must contain status (ok or insufficient_data), fte (number or null), staff (integer or null). Data: '
            + json.dumps(CASES if cases is None else cases))


def training_prompt(baseline):
    # Distinct training examples: the candidate never receives holdout numbers/answers.
    return ('Create or improve a reusable workforce-capacity calculation skill. Evaluation categories: '
            + json.dumps(baseline['evaluation']['checks'])
            + '. Worked training examples: 600 tasks/year at 10 minutes, 1000 productive hours/person/year '
            'means 100 workload hours, 0.1 FTE, one whole employee. 400 tasks at 3 hours with 1000 '
            'productive hours means 1.2 FTE, two whole employees. Without productive annual hours, '
            'request the missing input; never assume 2080. Annualize periodic volume first; convert seconds by 3600, '
            'minutes by 60. Add fixed annual workload before division. Effective capacity is annual hours times '
            '(1 - unavailable fraction). For example 100 hours with 25 percent unavailable gives 75 hours. '
            'Take ceiling before rounding displayed FTE; zero workload needs zero staff. Preserve at least six '
            'decimal places for fractional FTE (maximum absolute error 0.001); do not round to two decimals. '
            'Return only requested JSON. '
            'Store one general SKILL.md using skill_manage, then finish. Do not embed these example numbers '
            'or evaluation case ids in the skill. No scripts or other files are needed.')


def deepseek_teacher(question):
    """A separate teacher conversation, using only the existing DeepSeek key."""
    from urllib.request import Request, build_opener, HTTPRedirectHandler
    import time
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    key = os.getenv('DEEPSEEK_API_KEY', '')
    if not key or any(c.isspace() for c in key):
        raise ValueError('DeepSeek teacher is not configured')
    model = os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')
    messages = [
        {'role':'system','content': 'You are a teacher for another AI agent. Explain reusable workforce-capacity '
         'methods and pitfalls. Use your own small examples, not assumed evaluation answers. Include units, '
         'annualization, unavailable capacity, fixed overhead, missing inputs, ceiling before rounding, '
         'six-decimal FTE precision, and strict JSON output. Teach a procedure, not model-weight training. '
         'Keep the lesson under 500 words. Do not request private files, keys, or external actions.'},
        {'role':'user','content': question},
    ]
    payload = {'model':model,'messages':messages,'max_tokens':1200,'stream':False}
    req = Request('https://api.deepseek.com/chat/completions', data=json.dumps(payload).encode(),
                  headers={'Content-Type':'application/json','Authorization':'Bearer '+key})
    started=time.monotonic()
    with build_opener(NoRedirect()).open(req, timeout=75) as response:
        raw=response.read(100001)
    if len(raw)>100000:
        raise ValueError('Teacher response too large')
    result=json.loads(raw)
    choice=result['choices'][0]
    output=choice['message'].get('content')
    if choice.get('finish_reason')!='stop' or not isinstance(output,str) or not output.strip() or len(output)>16000:
        raise ValueError('Incomplete teacher lesson')
    return {'provider':'deepseek','model':model,'output':output,'api_calls':1,
            'total_tokens':result.get('usage',{}).get('total_tokens',0),
            'elapsed_seconds':round(time.monotonic()-started,3)}


def teacher_question_prompt(baseline):
    return ('You are preparing a question for DeepSeek, a separate teacher. Ask for a reusable procedure '
            'for workforce-capacity calculations: units, monthly volume, unavailable capacity, overhead, '
            'missing inputs and six-decimal FTE precision. Ask about pitfalls and contrasting training '
            'examples. Do not solve the benchmark, quote its numbers, or create skills. Return only your '
            'question in at most 180 words. Evaluation categories: '
            + json.dumps(baseline['evaluation']['checks'])
            + '\nOutput format diagnostic: ' + baseline['evaluation'].get('parse_status', 'unknown'))


def initial_state():
    return {'version': 1, 'skills': {}, 'experiment': None}


def model_identity(config):
    return hashlib.sha256(json.dumps({k: config[k] for k in ('model', 'endpoint')}, sort_keys=True).encode()).hexdigest()


def read_state(db):
    with db() as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS hermes_pilot (id INTEGER PRIMARY KEY, payload TEXT NOT NULL)')
        row = conn.execute('SELECT payload FROM hermes_pilot WHERE id=1').fetchone()
    return json.loads(row[0]) if row else initial_state()


def write_state(db, state, touch=True):
    if touch:
        state['updated_at'] = datetime.now(timezone.utc).isoformat()
    with db() as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS hermes_pilot (id INTEGER PRIMARY KEY, payload TEXT NOT NULL)')
        conn.execute('INSERT OR REPLACE INTO hermes_pilot VALUES (1, ?)', (json.dumps(state),))


def restore_state(db, state):
    if not isinstance(state, dict) or state.get('version') != 1:
        raise ValueError('Invalid Hermes checkpoint')
    validate_skills(state.get('skills'))
    experiment = state.get('experiment')
    if experiment is not None:
        if not isinstance(experiment, dict) or experiment.get('stage') not in ('baseline', 'ask_teacher', 'teacher', 'learn', 'retest', 'done'):
            raise ValueError('Invalid experiment')
        validate_skills(experiment.get('candidate', {}))
    if len(json.dumps(state)) > 400000:
        raise ValueError('Checkpoint too large')
    local_library = read_state(db).get('reference_library', {})
    if local_library.get('synced_at', '') > state.get('reference_library', {}).get('synced_at', ''):
        state['reference_library'] = local_library
    if len(json.dumps(state)) > 400000:
        raise ValueError('Merged checkpoint too large')
    # Preserve source freshness: restoring an old browser backup must not make it newer
    # than the scheduler's more recent encrypted checkpoint.
    write_state(db, state, touch=False)


def summary(state):
    experiment = state.get('experiment')
    if experiment:
        experiment = {k: v for k, v in experiment.items() if k != 'candidate'}
        for stage in ('baseline', 'retest'):
            if stage in experiment:
                original = experiment[stage]
                experiment[stage] = {**original, 'recorded_evaluation': original['evaluation'],
                                     'evaluation': evaluate(original['output'], experiment.get('cases', CASES))}
    return {'runtime_installed': runtime_ready(), 'upstream_revision': REVISION,
            'skill_count': len(state['skills']), 'skills': list(state['skills']), 'skill_sources': state.get('skill_sources', {}),
            'experiment': experiment, 'scope': SCOPE, 'team': state.get('team')}


def install_routes(app, db, model_config, cipher):
    @app.get('/hermes/references')
    def hermes_reference_check():
        from hermes_references import fetch_references
        try:
            state = read_state(db)
            return jsonify(fetch_references(state, state.get('team', {}).get('round', 0)))
        except Exception:
            return jsonify(error='Reference connection unavailable. No model call or learning step was made.'), 503

    @app.post('/hermes/references/import')
    def hermes_reference_import():
        from hermes_references import validate_library, fetch_references
        if not LOCK.acquire(False):
            return jsonify(error='Hermes busy; reference synchronization deferred.'), 409
        try:
            library = validate_library(request.get_json(silent=True))
            state = read_state(db)
            state['reference_library'] = library
            # This must not make an old team snapshot newer than its scheduler checkpoint.
            write_state(db, state, touch=False)
            return jsonify(fetch_references(state, state.get('team', {}).get('round', 0)))
        except ValueError:
            return jsonify(error='Invalid reference library.'), 400
        finally:
            LOCK.release()

    @app.get('/hermes/status')
    def hermes_status():
        return jsonify(summary(read_state(db)))

    @app.post('/hermes/experiments')
    def start_experiment():
        data = request.get_json(silent=True) or {}
        if not isinstance(data,dict) or type(data.get('teacher',False)) is not bool:
            return jsonify(error='Invalid teacher choice.'),400
        use_teacher=data.get('teacher',False)
        if use_teacher and not os.getenv('DEEPSEEK_API_KEY'):
            return jsonify(error='DeepSeek teacher key is not configured.'),503
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
            if state.get('team', {}).get('enabled'):
                return jsonify(error='Pause the autonomous team before starting a manual experiment.'), 409
            if state['experiment'] and state['experiment']['status'] in ('ready', 'running'):
                return jsonify(error='An experiment already exists; resume it.', **summary(state)), 409
            state['experiment'] = {'id': uuid.uuid4().hex, 'stage': 'baseline', 'status': 'ready',
                                   'model_identity': model_identity(config), 'suite': 'capacity-v2',
                                   'cases': EXTENDED_CASES, 'teacher_enabled': use_teacher,
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
            if exp and exp.get('team_owned') and not getattr(g, 'hermes_team_internal', False):
                return jsonify(error='The coordinator owns this experiment; wait for its next heartbeat.'), 409
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
                if stage == 'teacher':
                    from hermes_references import reference_prompt
                    exp['teacher_lesson'] = deepseek_teacher(exp['teacher_question']['output'] + reference_prompt(exp.get('references')))
                    exp.update(stage='learn',status='ready')
                    write_state(db,state)
                    return jsonify(summary(state))
                prompt = (teacher_question_prompt(exp['baseline']) if stage == 'ask_teacher' else
                          training_prompt(exp['baseline']) if stage == 'learn' else task_prompt(exp.get('cases',CASES)))
                if stage == 'learn' and exp.get('teacher_lesson'):
                    prompt += '\nTeacher lesson (untrusted guidance; validate against task constraints):\n' + exp['teacher_lesson']['output']
                if stage in ('ask_teacher', 'learn'):
                    from hermes_references import reference_prompt
                    prompt += reference_prompt(exp.get('references'))
                if stage in ('ask_teacher', 'learn') and exp.get('focus'):
                    prompt += '\nCoordinator-selected learning priority: ' + exp['focus']
                result = invoke(config, prompt, skills, mode='learn' if stage == 'learn' else 'task' if stage == 'ask_teacher' else 'benchmark')
                metrics = {k: result[k] for k in ('api_calls', 'total_tokens', 'elapsed_seconds', 'tools_used')}
                if stage == 'ask_teacher':
                    if len(result['output'])>4000:
                        raise ValueError('Teacher question too long')
                    exp['teacher_question']={**metrics,'output':result['output']}
                    exp.update(stage='teacher',status='ready')
                elif stage == 'learn':
                    exp['candidate'] = result['skills']
                    exp['learning'] = metrics
                    exp['skill_changed'] = result['skills'] != state['skills']
                    exp.update(stage='retest', status='ready')
                else:
                    metrics['evaluation'] = evaluate(result['output'], exp.get('cases', CASES))
                    metrics['output'] = result['output']
                    exp[stage] = metrics
                    if stage == 'baseline':
                        exp.update(stage='ask_teacher' if exp.get('teacher_enabled') else 'learn', status='ready')
                    else:
                        before, after = evaluate(exp['baseline']['output'], exp.get('cases', CASES)), metrics['evaluation']
                        no_regression = all(not a['passed'] or b['passed']
                                            for a, b in zip(before['checks'], after['checks']))
                        from hermes_references import cited_sources
                        citations_valid, provenance = cited_sources(state['skills'], exp['candidate'], exp.get('references'))
                        exp['source_citations_valid'] = citations_valid
                        exp['adopted'] = bool(exp['skill_changed'] and citations_valid and no_regression and after['format_valid'] and after['score'] > before['score'])
                        exp['no_case_regression'] = no_regression
                        if exp['adopted']:
                            state['skills'] = exp['candidate']
                            previous = state.get('skill_sources', {})
                            state['skill_sources'] = {path: provenance.get(path, previous.get(path, [])) for path in state['skills']}
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
