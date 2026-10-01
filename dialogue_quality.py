"""One bounded deployment smoke check using public fixtures, never owner chats.

Language and fixture checks are not a measurement of general intelligence.
"""
import threading

_lock = threading.Lock()
_started = False
_status = {'state': 'not_started', 'scope': 'public_fixture_smoke_check_not_general_intelligence'}

CASES = [
    {'id': 'arabic_direct', 'language': 'ar',
     'conversation': [{'role': 'user', 'content': 'اشرحلي بجملتين كيف بفرّق بين حفظ المعلومة وفهمها، مع مثال بسيط.'}]},
    {'id': 'arabic_memory', 'language': 'ar',
     'conversation': [{'role': 'user', 'content': 'للتجربة فقط، اسم مشروعي التجريبي هو زيتونة.'},
                      {'role': 'assistant', 'content': 'تمام، اسم المشروع التجريبي زيتونة ضمن هذا الحوار.'},
                      {'role': 'user', 'content': 'شو اسم المشروع اللي حكيتلك عنه؟ وضّح من وين عرفت الاسم.'}],
     'expected': 'زيتونة', 'minimum': 2},
    {'id': 'english_switch', 'language': 'auto',
     'conversation': [{'role': 'user', 'content': 'خلينا نحكي بالعربي.'},
                      {'role': 'assistant', 'content': 'تمام، احكيلي شو الموضوع.'},
                      {'role': 'user', 'content': 'Now answer in English: explain one way to check whether an AI answer is correct.'}]},
]


def evaluate(generate, resolve_language, validate_language):
    results = []
    for case in CASES:
        context = {'_companion': True, 'model': 'free', 'task': 'Reply to the latest message.',
                   'language': case['language'], 'conversation': case['conversation']}
        row = {'id': case['id'], 'passed': False}
        try:
            output = generate(context)
            content = output.get('content', '')
            validate_language(content, resolve_language(context))
            row['passed'] = len(content) >= case.get('minimum', 40) and case.get('expected', '') in content
            row['provider'] = output.get('_model')
        except Exception as error:
            row['error'] = 'generation_or_fixture_check_failed'
            row['error_type'] = type(error).__name__
            if isinstance(getattr(error, 'category', None), str):
                row['category'] = error.category
            elif type(error).__name__ == 'ModelOutputError':
                row['category'] = str(error)
            if isinstance(getattr(error, 'code', None), int):
                row['provider_status'] = error.code
            # Only our fixed validation messages, never a raw provider body.
            if str(error) in ('Invalid generated dialogue', 'Incomplete free model response',
                              'The answer did not follow Arabic', 'The answer did not follow English',
                              'Dialogue response time budget exhausted'):
                row['validation_error'] = str(error)
        results.append(row)
    return {'state': 'passed' if all(row['passed'] for row in results) else 'failed',
            'scope': 'public_fixture_smoke_check_not_general_intelligence',
            'cases': results, 'human_semantic_review': 'still_required'}


def status():
    with _lock:
        return dict(_status)


def start():
    global _started
    import moltbook
    if not moltbook.free_model_key():
        return
    with _lock:
        if _started:
            return
        _started = True
        _status['state'] = 'running'
    def run():
        result = evaluate(moltbook.free_dialogue_json, moltbook.companion_language,
                          moltbook.validate_companion_language)
        with _lock:
            _status.update(result)
    threading.Thread(target=run, daemon=True, name='public-dialogue-smoke-check').start()
