"""Real upstream Hermes + local scripted model. Tests plumbing, NOT learning efficacy."""
import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import hermes_pilot as h


@unittest.skipUnless(os.getenv('HERMES_INTEGRATION_TEST') == '1', 'Opt-in test requires installed Hermes runtime')
class RealHermesIntegration(unittest.TestCase):
    def test_real_skill_write_then_read_in_fresh_process(self):
        requests = []
        content = ('---\nname: capacity\ndescription: Calculate workforce capacity and whole employees.\n---\n'
                   '# Capacity\nConvert minutes to hours, divide by productive hours and round employee counts upward.\n')

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                request = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                requests.append(request)
                tools = {t['function']['name'] for t in request.get('tools', [])}
                messages = request['messages']
                has_tool_result = any(m['role'] == 'tool' for m in messages)
                if not has_tool_result and 'skill_manage' in tools:
                    call = {'name': 'skill_manage', 'arguments': json.dumps({'operations': [
                        {'action': 'create', 'name': 'capacity', 'content': content}]})}
                elif not has_tool_result and 'skill_view' in tools:
                    call = {'name': 'skill_view', 'arguments': json.dumps({'name': 'capacity'})}
                else:
                    call = None
                message = {'role': 'assistant', 'content': None if call else 'Skill action complete.'}
                if call:
                    message['tool_calls'] = [{'id': 'call_1', 'type': 'function', 'function': call}]
                body = json.dumps({'id': 'fixture', 'object': 'chat.completion', 'created': 1,
                                   'model': 'fixture-model', 'choices': [{'index': 0, 'message': message,
                                   'finish_reason': 'tool_calls' if call else 'stop'}],
                                   'usage': {'prompt_tokens': 20, 'completion_tokens': 10, 'total_tokens': 30}}).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(body)

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        config = {'model': 'fixture-model', 'key': '',
                  'endpoint': f'http://127.0.0.1:{server.server_port}/v1/chat/completions'}
        learned = h.invoke(config, 'Create a workforce capacity skill using skill_manage.', {}, 'learn')
        self.assertIn('capacity/SKILL.md', learned['skills'],
                      [m.get('content') for r in requests for m in r['messages'] if m['role'] == 'tool'])
        self.assertEqual(learned['skills']['capacity/SKILL.md'], content)
        replay = h.invoke(config, 'Read the capacity skill, then acknowledge it.', learned['skills'])
        self.assertIn('skill_view', replay['tools_used'])
        self.assertEqual(replay['skills'], learned['skills'])
        self.assertTrue(any('Convert minutes' in m.get('content', '') for r in requests
                            for m in r['messages'] if m['role'] == 'tool'))
        for request in requests:
            names = {t['function']['name'] for t in request.get('tools', [])}
            self.assertLessEqual(names, {'skills_list', 'skill_view', 'skill_manage'})


if __name__ == '__main__':
    unittest.main()
