"""Native, text-only Claude transport; one attempt, no paid fallback."""
import json
from urllib.request import Request


def call_claude(config, messages, transport, incomplete_error):
    system, conversation = [], []
    for message in messages:
        role, content = message.get('role'), message.get('content')
        if role not in ('system', 'user', 'assistant') or not isinstance(content, str):
            raise ValueError('Claude requires text messages with supported roles')
        if role == 'system':
            if conversation:
                raise ValueError('System instructions must precede conversation')
            system.append(content)
        else:
            conversation.append({'role': role, 'content': content})
    if not conversation or conversation[0]['role'] != 'user' or conversation[-1]['role'] != 'user':
        raise ValueError('Claude conversation must start and end with a user turn')
    payload = {'model': config['model'], 'messages': conversation,
               'max_tokens': 8192, 'stream': False}
    if system:
        payload['system'] = '\n\n'.join(system)
    req = Request(config['endpoint'], data=json.dumps(payload).encode(), headers={
        'Content-Type': 'application/json', 'x-api-key': config['key'],
        'anthropic-version': '2023-06-01'})
    with transport.open(req, timeout=60) as response:
        raw = response.read(200001)
    if len(raw) > 200000:
        raise ValueError('Provider response too large')
    body = json.loads(raw)
    if not isinstance(body, dict):
        raise ValueError('Invalid Claude response')
    if body.get('stop_reason') != 'end_turn':
        raise incomplete_error('Claude response did not finish normally')
    blocks = body.get('content')
    if not isinstance(blocks, list) or any(
            not isinstance(block, dict) or block.get('type') != 'text'
            or not isinstance(block.get('text'), str) for block in blocks):
        raise ValueError('Invalid Claude text response')
    content = '\n'.join(block['text'] for block in blocks)
    if not content.strip():
        raise ValueError('Empty Claude response')
    return {'role': 'assistant', 'content': content}
