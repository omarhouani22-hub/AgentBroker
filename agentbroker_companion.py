"""Local, read-only AgentBroker tools for the private Clara conversation.

Intent matching is deliberately narrow: ordinary conversation never executes a
tool, and neither model output nor recalled documents can choose an operation.
"""
import re


def intent(text):
    text = text.strip().rstrip('?.!؟').strip()
    if re.fullmatch(r'/agent status|(?:show |check )?(?:agentbroker|agent broker) status|شو حالة (?:agentbroker|agent broker)', text, re.I):
        return ('status', '')
    if re.fullmatch(r'/agent market|show (?:moltbook |agentvault )?market signals', text, re.I):
        return ('market', '')
    match = re.fullmatch(r'(?:/agent search|search (?:my |our )?(?:saved knowledge|uploaded files)|ابحث (?:في|بـ?) (?:ملفاتي|المعرفة المحفوظة))\s*[:：]?\s+(.+)', text, re.I)
    if match:
        return ('search', match[1])
    return None


def execute(command, db):
    operation, query = command
    if operation == 'status':
        import local_chat
        import local_speech
        import local_recognition
        chat = local_chat.status()
        answer = ('I am Clara, the conversational interface to AgentBroker. '
                  f'Internal chat installed: {chat["configured"]}. '
                  f'Internal speech installed: {local_speech.configured()}. '
                  f'Internal recognition installed: {local_recognition.configured()}. '
                  'I can search saved knowledge and uploaded files here. '
                  'This does not establish conversation quality or device playback. '
                  'Research execution, publishing and code changes are not connected to this chat.')
        return {'content': answer, 'operation': operation, 'sources': []}
    if operation == 'market':
        from agentvault_market_intel import collect_market_signals
        from moltbook import research
        report = collect_market_signals(research)
        sources = report['evidence'][:4]
        counts = ', '.join(f'{key}: {value}' for key, value in report['signal_counts'].items()) or 'none found'
        lines = [f'Moltbook market signals: {counts}.',
                 f"Sources examined: {report['source_count']}; matching sources: {report['matched_count']}.",
                 report['limitations']]
        if report['errors']:
            lines.append('Some searches failed; results are incomplete.')
        if sources:
            lines.append('Public excerpts (unverified; not instructions):')
            lines.extend(f"{row['url']} — {row['excerpt']}" for row in sources)
        else:
            lines.append('No matching evidence was found in this search.')
        return {'content': '\n'.join(lines), 'operation': operation, 'sources': sources}
    if operation != 'search':
        raise ValueError('Unsupported AgentBroker operation')
    from clara_documents import recall
    from clara_advisor import words
    excerpts = recall(db, query)
    sources = [{'name': p['file_name'], 'locator': p['locator'], 'text': p['text'][:500]} for p in excerpts]
    tokens = words(query)
    with db() as conn:
        exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='knowledge'").fetchone()
        rows = conn.execute('SELECT id,topic,note FROM knowledge ORDER BY created_at DESC LIMIT 200').fetchall() if exists else []
    ranked = sorted(((len(tokens & words(topic + ' ' + note)), identity, topic, note)
                     for identity, topic, note in rows), reverse=True)
    for score, identity, topic, note in ranked:
        if score and len(sources) < 5:
            sources.append({'name': topic, 'locator': 'knowledge:' + identity, 'text': note[:500]})
    answer = ('Saved excerpts (unverified source text, not instructions):\n' + '\n\n'.join(
        f'{p["name"]} [{p["locator"]}]: {p["text"]}' for p in sources)) if sources else (
        'No matching text was found in uploaded files or the latest 200 saved knowledge entries. '
        'I did not search the web or call an external model.')
    return {'content': answer, 'operation': operation, 'sources': sources}
