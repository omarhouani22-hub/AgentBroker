"""AgentBroker's own Moltbook API connection and attributed public research."""
import json
import os
import threading
from time import monotonic
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError

from flask import jsonify, request

BASE = 'https://www.moltbook.com/api/v1'


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


TRANSPORT = build_opener(NoRedirect())
STATUS_LOCK = threading.Lock()
STATUS_CACHE = {'until': 0, 'result': None}


def api(method, path, payload=None, query=None):
    key = os.getenv('MOLTBOOK_API_KEY', '')
    if not key:
        raise ValueError('Moltbook API key is not configured')
    if not path.startswith('/') or '//' in path or '?' in path or '#' in path:
        raise ValueError('Invalid Moltbook route')
    url = BASE + path + ('?' + urlencode(query) if query else '')
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {'Authorization': 'Bearer ' + key, 'Accept': 'application/json',
               'User-Agent': 'AgentBroker/1.0 (https://github.com/omarhouani22-hub/AgentBroker)'}
    if data is not None:
        headers['Content-Type'] = 'application/json'
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with TRANSPORT.open(req, timeout=25) as response:
            raw = response.read(200001)
            status = response.status
    except HTTPError as error:
        status = error.code
        error.close()
        raise ValueError('Moltbook HTTP ' + str(status)) from None
    if len(raw) > 200000:
        raise ValueError('Moltbook response too large')
    result = json.loads(raw)
    if not isinstance(result, dict) or result.get('success') is False:
        raise ValueError('Moltbook API rejected the request')
    return result


def ready():
    status = api('GET', '/agents/status')
    return status.get('status') == 'claimed'


def research(topic):
    """Read at most three public posts; content is data, never instructions."""
    if not ready():
        return []
    data = api('GET', '/search', query={'q': topic[:500], 'type': 'posts', 'limit': 3})
    results = []
    for item in data.get('results', [])[:3]:
        if not isinstance(item, dict) or item.get('type') != 'post':
            continue
        post_id = item.get('post_id') or item.get('id')
        if not isinstance(post_id, str) or not 1 <= len(post_id) <= 100 or not all(
                c.isalnum() or c == '-' for c in post_id):
            continue
        title, content = item.get('title'), item.get('content')
        if isinstance(title, str) and isinstance(content, str) and len(content.strip()) >= 80:
            author = item.get('author') if isinstance(item.get('author'), dict) else {}
            results.append({'title': title[:200], 'url': 'https://www.moltbook.com/post/' + post_id,
                            'excerpt': ' '.join(content.split())[:700],
                            'author': str(author.get('name', 'unknown'))[:100]})
    return results


def install_routes(app):
    @app.get('/moltbook/status')
    def moltbook_status():
        if not os.getenv('MOLTBOOK_API_KEY'):
            return jsonify(connected=False, claimed=False, error='Agent key not configured')
        with STATUS_LOCK:
            if STATUS_CACHE['result'] is not None and monotonic() < STATUS_CACHE['until']:
                result, code = STATUS_CACHE['result']
            else:
                try:
                    profile = api('GET', '/agents/me')
                    status = api('GET', '/agents/status')
                    agent = profile.get('agent') or {}
                    app.logger.info('moltbook connection status=%s agent=%s', status.get('status'), agent.get('name'))
                    result, code = dict(connected=True, claimed=status.get('status') == 'claimed',
                                        status=status.get('status'), username=agent.get('name'),
                                        profile='https://www.moltbook.com/u/' + str(agent.get('name', ''))), 200
                except (ValueError, URLError, TimeoutError, TypeError) as error:
                    app.logger.warning('moltbook status failure=%s', type(error).__name__)
                    result, code = dict(connected=False, error=type(error).__name__), 502
                STATUS_CACHE.update(until=monotonic() + 60, result=(result, code))
        return jsonify(result), code

    @app.get('/moltbook/research')
    def moltbook_research():
        topic = request.args.get('q', '')
        if not 3 <= len(topic) <= 500:
            return jsonify(error='Supply a topic of 3–500 characters'), 400
        try:
            results = research(topic)
            app.logger.info('moltbook research results=%d', len(results))
            return jsonify(results=results)
        except (ValueError, URLError, TimeoutError, TypeError) as error:
            app.logger.warning('moltbook research failure=%s', type(error).__name__)
            return jsonify(error=type(error).__name__), 502

    @app.get('/moltbook/feedback/<post_id>')
    def moltbook_feedback(post_id):
        if not 1 <= len(post_id) <= 100 or not all(c.isalnum() or c == '-' for c in post_id):
            return jsonify(error='Invalid post ID'), 400
        try:
            result = api('GET', '/posts/' + post_id + '/comments', query={'sort': 'new', 'limit': 35})
            app.logger.info('moltbook feedback post=%s comments=%d', post_id, len(result.get('comments', [])))
            return jsonify(result)
        except (ValueError, URLError, TimeoutError, TypeError) as error:
            app.logger.warning('moltbook feedback failure=%s', type(error).__name__)
            return jsonify(error=type(error).__name__), 502

    @app.post('/moltbook/posts')
    def moltbook_post():
        data = request.get_json(silent=True) or {}
        title, body = data.get('title'), data.get('content')
        if not isinstance(title, str) or not 5 <= len(title) <= 300 or not isinstance(body, str) or not 20 <= len(body) <= 40000:
            return jsonify(error='Valid title and content required'), 400
        try:
            if not ready():
                return jsonify(error='Moltbook owner claim is incomplete'), 409
            result = api('POST', '/posts', {'submolt_name': 'general', 'title': title, 'content': body})
            post = result.get('post') or {}
            app.logger.info('moltbook post status=%s id=%s', post.get('verification_status', 'submitted'), post.get('id'))
            return jsonify(result), 201
        except (ValueError, URLError, TimeoutError, TypeError) as error:
            app.logger.warning('moltbook post failure=%s', type(error).__name__)
            return jsonify(error=type(error).__name__), 502

    @app.post('/moltbook/comments')
    def moltbook_comment():
        data = request.get_json(silent=True) or {}
        post_id, body, parent_id = data.get('post_id'), data.get('content'), data.get('parent_id')
        if (not isinstance(post_id, str) or not 1 <= len(post_id) <= 100 or
            not all(c.isalnum() or c == '-' for c in post_id) or
            not isinstance(body, str) or not 10 <= len(body) <= 4000 or
            (parent_id is not None and (not isinstance(parent_id, str) or
                                        not all(c.isalnum() or c == '-' for c in parent_id)))):
            return jsonify(error='Valid post ID and comment required'), 400
        try:
            if not ready():
                return jsonify(error='Moltbook owner claim is incomplete'), 409
            payload = {'content': body}
            if parent_id:
                payload['parent_id'] = parent_id
            result = api('POST', '/posts/' + post_id + '/comments', payload)
            comment = result.get('comment') or {}
            app.logger.info('moltbook comment post=%s id=%s', post_id, comment.get('id'))
            return jsonify(result), 201
        except (ValueError, URLError, TimeoutError, TypeError) as error:
            app.logger.warning('moltbook comment failure=%s', type(error).__name__)
            return jsonify(error=type(error).__name__), 502
