"""Single-use, exact-request permit issued only after durable Growth approval."""
from contextlib import contextmanager
from contextvars import ContextVar
import json

_permit = ContextVar('growth_publication_permit', default=None)

def fingerprint(method, path, payload):
    return (method.upper(), path, json.dumps(payload, sort_keys=True, separators=(',', ':')))

@contextmanager
def approved_publication(action_id, method, path, payload):
    if not action_id:
        raise ValueError('A reserved audit action is required')
    token = _permit.set([fingerprint(method, path, payload), False])
    try:
        yield
    finally:
        _permit.reset(token)

def consume_publication(method, path, payload):
    permit = _permit.get()
    if permit is None or permit[1] or permit[0] != fingerprint(method, path, payload):
        raise ValueError('Publication requires an exact, single-use Growth Manager approval')
    permit[1] = True
