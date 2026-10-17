"""Bounded local-service engineering experiments, with no API keys or paid fallback.

Builds only the checksum-pinned runtime via the existing builder. It does not
execute generated code, change production, train weights, or call cloud models.
"""
import json
import subprocess
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, build_opener, ProxyHandler

ROOT = Path(__file__).resolve().parent
PORT = 18932
PROFILES = (
    {'name': 'small-context', 'context': 512, 'batch': 16},
    {'name': 'minimal-context', 'context': 256, 'batch': 8},
)
CASES = (
    ('arithmetic', 'What is 17 plus 25? Answer with just the number.', '42'),
    ('memory', 'Remember this fictional code: BLUE17. What code did I just give you?', 'BLUE17'),
    ('identity', 'Your name is Clara. What is your name? Answer with just your name.', 'clara'),
)


def accepted(text, expected):
    # Narrow smoke checks, not a certification of general model quality.
    import re
    return isinstance(text, str) and len(text) < 500 and bool(
        re.search(r'(?<!\w)' + re.escape(expected) + r'(?!\w)', text, re.I))


def stop(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)


def experiment(profile):
    # cgroup caps physical RAM on hosted CI. No misleading virtual-address cap:
    # mmap reserves address space that does not equal resident memory.
    command = [str(ROOT / '.trained-runtime/bin/llama-server'), '-m',
               str(ROOT / '.trained-runtime/agentbroker-q3.gguf'),
               '--host', '127.0.0.1', '--port', str(PORT), '--no-webui',
               '--ctx-size', str(profile['context']), '--threads', '2',
               '--threads-batch', '2', '--batch-size', str(profile['batch']),
               '--ubatch-size', str(profile['batch']), '--parallel', '1',
               '--log-disable']
    result = {'profile': profile, 'passed': False, 'checks': []}
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    opener = build_opener(ProxyHandler({}))
    try:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if process.poll() is not None:
                result['failure'] = 'runtime_exited'
                return result
            try:
                with opener.open(f'http://127.0.0.1:{PORT}/health', timeout=1) as response:
                    if response.status == 200:
                        break
            except (URLError, TimeoutError):
                time.sleep(.2)
        else:
            result['failure'] = 'startup_timeout'
            return result
        for name, prompt, expected in CASES:
            started = time.monotonic()
            payload = {'messages': [
                {'role': 'system', 'content': 'You are Clara. Reply briefly in English. /no_think'},
                {'role': 'user', 'content': prompt}],
                'max_tokens': 64, 'temperature': 0,
                'chat_template_kwargs': {'enable_thinking': False}}
            request = Request(f'http://127.0.0.1:{PORT}/v1/chat/completions',
                              data=json.dumps(payload).encode(),
                              headers={'Content-Type': 'application/json'})
            with opener.open(request, timeout=30) as response:
                raw = response.read(100001)
            if len(raw) > 100000:
                raise ValueError('oversized response')
            answer = json.loads(raw)['choices'][0]
            seconds = round(time.monotonic() - started, 2)
            passed = (answer.get('finish_reason') == 'stop' and seconds <= 15
                      and accepted(answer['message']['content'], expected))
            result['checks'].append({'case': name, 'passed': passed, 'seconds': seconds})
        result['passed'] = all(check['passed'] for check in result['checks'])
    except Exception as error:
        # Do not put arbitrary provider bodies, credentials, or text in reports.
        result['failure'] = type(error).__name__
    finally:
        stop(process)
    return result


def run(evaluate=experiment):
    attempts = []
    for profile in PROFILES:
        result = evaluate(profile)
        attempts.append(result)
        if result['passed']:
            break
    winner = next((r['profile'] for r in attempts if r['passed']), None)
    return {'version': 1, 'objective': 'English local chat without external inference fees',
            'state': 'candidate_ready' if winner else 'blocked', 'candidate': winner,
            'attempts': attempts, 'production_changed': False,
            'limitations': ['Synthetic smoke tests only; no general quality certification.',
                            'CI resources do not establish performance on Render.',
                            'No speech, camera, document editing or avatar generation.']}


if __name__ == '__main__':
    # Outputs are deliberately restricted to synthetic checks in this public repo.
    report = run()
    destination = ROOT / 'self-service-report.json'
    destination.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
