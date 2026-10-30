"""Local, read-only AgentBroker tools for the private Clara conversation.

Intent matching is deliberately narrow: ordinary conversation never executes a
tool, and neither model output nor recalled documents can choose an operation.
"""
import re


def intent(text):
    from clara_initiative import intent as initiative_intent
    initiative = initiative_intent(text)
    if initiative:
        return initiative
    text = text.strip().rstrip('?.!؟').strip()
    if text.lower() in ('/memory', 'what do you remember about me', 'شو بتتذكري عني'):
        return ('memory', '')
    match = re.fullmatch(r'(?:/remember|remember that|تذكري ان|تذكري أن)\s+(.+)', text, re.I | re.S)
    if match:
        return ('remember', match[1].strip())
    match = re.fullmatch(r'(?:my name is|اسمي)\s+(.+)', text, re.I)
    if match:
        return ('remember_name', match[1].strip())
    match = re.fullmatch(r'/forget\s+(\d+)', text, re.I)
    if match:
        return ('forget', match[1])
    if re.fullmatch(r'/agent income|(?:hi[, ]+)?(?:can|could|are) you (?:able to )?(?:harness your knowledge to )?(?:make|earn) me (?:money|income)|(?:help me|work on) (?:making|earning) money|اعملي مصاري|جيبلي مصاري', text, re.I):
        return ('income', '')
    if re.fullmatch(r'/agent status|(?:show |check )?(?:agentbroker|agent broker) status|شو حالة (?:agentbroker|agent broker)', text, re.I):
        return ('status', '')
    match = re.fullmatch(r'(?:/agent search|search (?:my |our )?(?:saved knowledge|uploaded files)|ابحث (?:في|بـ?) (?:ملفاتي|المعرفة المحفوظة))\s*[:：]?\s+(.+)', text, re.I)
    if match:
        return ('search', match[1])
    return None


def execute(command, db, companion=None):
    operation, query = command
    if operation in ('memory', 'remember', 'remember_name', 'forget'):
        if companion is None:
            raise ValueError('Private conversation state is required')
        from clara_advisor import validate_profile
        from datetime import datetime, timezone
        entries = list(companion.get('owner_profile', []))
        if operation == 'memory':
            answer = ('Saved private profile:\n' + '\n'.join(f'{i+1}. {e["fact"]}' for i,e in enumerate(entries))) if entries else 'Your private profile is empty. Say "My name is Omar" or use /remember followed by a preference.'
            answer = answer[:1700] + '\nUse /forget <number> to remove an entry. These entries are used in private model requests; storage follows the server database.'
        elif operation == 'forget':
            index = int(query)-1
            if 0 <= index < len(entries):
                entries.pop(index)
                companion['owner_profile'] = entries
                answer = 'Removed that entry from your active private profile. It may still exist in conversation history or exports.'
            else:
                answer = 'No profile entry has that number. Use /memory to review entries.'
        else:
            fact = 'Name: ' + query if operation == 'remember_name' else query
            category = 'identity' if operation == 'remember_name' else 'communication_preferences'
            if operation == 'remember_name':
                entries = [e for e in entries if e['category'] != 'identity']
            if not any(e['fact'].casefold() == fact.casefold() for e in entries):
                entries.append({'category':category, 'fact':fact, 'as_of':datetime.now(timezone.utc).date().isoformat()})
            try:
                companion['owner_profile'] = validate_profile(entries)
                answer = 'Saved to your private profile: ' + fact + '\nI will include it in future private conversation context. Use /memory to review or /forget <number> to remove it. Storage follows the server database.'
            except ValueError:
                answer = 'Could not save that entry. Use a short fact or preference, omit credentials, and keep fewer than 100 entries.'
        return {'content':answer[:2000], 'operation':operation, 'sources':[]}
    if operation == 'income':
        evidence = execute(('search', 'AgentVault storage pricing customers payment revenue demand'), db)
        sources = evidence['sources']
        answer = ('I can do concrete preparation toward revenue. I have just searched your saved files and knowledge for AgentVault, pricing, payments and demand.\n\n'
                  + (f'Found {len(sources)} matching saved excerpts. These are private records, not verified current demand or sales.\n\n' if sources else
                     'No matching saved evidence was found, so I cannot establish current pricing, checkout readiness or customers.\n\n')
                  + 'My next step is to validate one AgentVault offer: recoverable storage for agent state. '
                  'Draft offer: "Keep a recoverable copy of your agent state. Test saving and restoring a sample before paying." '
                  'This is proposed copy; storage durability and recovery still need verification.\n\n'
                  'Go/no-go checks: a successful save-and-restore test, a working checkout, and an explicit request to try it from a potential buyer. '
                  'No revenue is verified by this review. Live research, publishing, payment collection and code changes are not connected to this conversation. '
                  'I can review the offer or checkout evidence you provide and prepare the next deliverable here. '
                  'Use /agent income to repeat this local evidence check.')
        return {'content': answer, 'operation': operation, 'sources': sources}
    if operation in ('goal', 'next', 'pause'):
        from clara_initiative import execute as initiative_execute
        return initiative_execute(command, db, execute)
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

