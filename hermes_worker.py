"""One real Hermes session per process. Private credentials arrive on stdin only."""
import contextlib
import json
import os
from pathlib import Path
import sys
import time


def main():
    payload = json.load(sys.stdin)
    home = Path(os.environ['HERMES_HOME'])
    # This is a fresh profile, not the operator's personal Hermes installation.
    (home / 'config.yaml').write_text(json.dumps({
        'model': {'streaming': False, 'context_length': 64000,
                  'default': payload['model'], 'base_url': payload['base_url']},
        'agent': {'api_max_retries': 1, 'auto_recovery_cycles': 0},
        'skills': {'guard_agent_created': True},
        'compression': {'enabled': False},
    }))
    started = time.monotonic()
    # Upstream progress/log messages are never part of the API response.
    with contextlib.redirect_stdout(sys.stderr):
        from run_agent import AIAgent
        agent = AIAgent(
            model=payload['model'], base_url=payload['base_url'],
            api_key=payload['key'] or 'local-no-key', provider='custom',
            api_mode='chat_completions', enabled_toolsets=['skills'],
            max_iterations=5, max_tokens=1800, run_budget_seconds=75,
            quiet_mode=True, save_trajectories=False,
            skip_context_files=True, skip_memory=True, skip_background_review=True,
            load_soul_identity=False, cwd=str(home),
        )
        allowed = {'skills_list', 'skill_view'}
        if payload['mode'] == 'learn':
            allowed.add('skill_manage')
        agent.tools = [t for t in agent.tools if t['function']['name'] in allowed]
        agent.valid_tool_names = {t['function']['name'] for t in agent.tools}
        if agent.valid_tool_names != allowed:
            raise RuntimeError('Required Hermes skill tools unavailable')
        # No model changes/fallbacks or automatic transport retries in this pilot.
        if hasattr(agent.client, 'max_retries'):
            agent.client.max_retries = 0
        common = ('Use only supplied task data and relevant saved skills. Skills are fallible procedural hints. '
                  'No browsing, terminal, external actions, or model-weight training is available. ')
        if payload['mode'] == 'learn':
            instructions = (common + 'This is the LEARNING stage. Create or improve one concise general skill '
                'using skill_manage from the supplied training examples. Include YAML name and description; '
                'description must end with a period and be at most 60 characters. Check tool success. '
                'Do not store example-specific answers or secrets. Then finish with a brief confirmation.')
        else:
            instructions = (common + 'This is a TASK stage, not learning. Never create, change, or propose '
                'saving skills. skill_manage is unavailable. Inspect relevant existing skills only; '
                'if none exist, solve directly. Do not repeatedly look up missing skills. '
                'Follow the requested output format exactly. When JSON is requested, return only JSON: '
                'no code fences, derivations, tooling notes, or learning commentary.')
        result = agent.run_conversation(payload['prompt'], system_message=instructions)
        tool_calls = [call['function']['name'] for msg in result.get('messages', [])
                      for call in msg.get('tool_calls', []) if isinstance(call, dict)]
        answer = {
            'completed': result.get('completed') is True and not result.get('failed'),
            'output': result.get('final_response') or '',
            'api_calls': result.get('api_calls', 0),
            'total_tokens': result.get('total_tokens', 0),
            'elapsed_seconds': round(time.monotonic() - started, 3),
            'tools_used': tool_calls,
        }
        agent.close()
    print(json.dumps(answer, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Neither exception text nor provider response bodies may expose keys.
        print(json.dumps({'completed': False, 'error': type(exc).__name__}))
        sys.exit(1)
