"""Opt-in transport to a same-container openai-oauth@2.0.0 proxy.

No OAuth credentials enter Python. The proxy must stay on IPv4 loopback.
This module does not install, start, authenticate, or persist the proxy.
"""
import json
import os
import re
from time import monotonic
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler

URL = 'http://127.0.0.1:10531/v1/chat/completions'


class Unavailable(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


# Loopback traffic must not send private conversations through HTTP_PROXY.
TRANSPORT = build_opener(ProxyHandler({}), NoRedirect())


def configured():
    return (os.getenv('CLARA_OAUTH_ENABLED') == 'true'
            and re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._-]{0,99}',
                             os.getenv('CLARA_OAUTH_MODEL', '')) is not None)


def complete(payload, deadline):
    if not configured():
        raise Unavailable('oauth_disabled')
    remaining = deadline - monotonic()
    if remaining < 1:
        raise Unavailable('oauth_deadline')
    # Do not forward OpenRouter-specific routing fields or any API key.
    body = {'model': os.environ['CLARA_OAUTH_MODEL'],
            'messages': payload['messages'], 'stream': False}
    req = Request(URL, data=json.dumps(body).encode(),
                  headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
                  method='POST')
    try:
        with TRANSPORT.open(req, timeout=min(8, remaining)) as response:
            raw = response.read(100001)
        if len(raw) > 100000:
            raise ValueError()
        result = json.loads(raw)
        if not isinstance(result, dict) or result.get('error'):
            raise ValueError()
        model = result.get('model')
        if not isinstance(model, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._/-]{0,149}', model):
            raise ValueError()
        return result
    except Exception:
        # Never expose upstream bodies, exceptions, credentials, or prompts.
        raise Unavailable('oauth_unavailable') from None
