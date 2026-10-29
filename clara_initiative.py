"""Owner-set initiative goals; local evidence only, with an explicit pause."""
import re
from datetime import datetime, timezone

COMMANDS = {
    'goal': '/agent goal <objective>',
    'next': '/agent next',
    'pause': '/agent pause',
}
MAX_GOAL = 600


def intent(text):
    text = text.strip()
    if text.lower() in ('/agent next', '/agent pause'):
        return (text.lower().split()[-1], '')
    match = re.fullmatch(r'/agent goal\s+(.+)', text, re.I | re.S)
    return ('goal', match[1].strip()) if match else None


def schema(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS clara_initiative_goal (
        singleton INTEGER PRIMARY KEY CHECK(singleton=1),
        objective TEXT NOT NULL, active INTEGER NOT NULL CHECK(active IN (0,1)),
        updated_at TEXT NOT NULL)""")


def current(db):
    with db() as conn:
        exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='clara_initiative_goal'").fetchone()
        if not exists:
            return None
        row = conn.execute('SELECT objective,active,updated_at FROM clara_initiative_goal WHERE singleton=1').fetchone()
    return {'objective': row[0], 'active': bool(row[1]), 'updated_at': row[2]} if row else None


def execute(command, db, search):
    operation, objective = command
    if operation == 'goal':
        if not isinstance(objective, str) or not 1 <= len(objective.strip()) <= MAX_GOAL:
            return {'content': 'Use /agent goal followed by an objective of 1–600 characters.', 'operation': 'goal', 'sources': []}
        if re.search(r'(?i)(moltbook_sk_|\bsk-[a-z0-9]|bearer\s|api[_ -]?key\s*[:=]|password\s*[:=])', objective):
            return {'content': 'Do not save credentials as a goal.', 'operation': 'goal', 'sources': []}
        with db() as conn:
            schema(conn)
            conn.execute('INSERT OR REPLACE INTO clara_initiative_goal VALUES (1,?,?,?)',
                         (objective.strip(), 1, datetime.now(timezone.utc).isoformat()))
        return {'content': 'Goal saved. My next proactive opening will use this objective and matching saved evidence. '
                'Use /agent next to review evidence now, or /agent pause to stop goal follow-up. '
                'This does not start background execution or external publishing. Goal storage follows this server\'s SQLite persistence.',
                'operation': 'goal', 'sources': []}
    if operation == 'pause':
        with db() as conn:
            schema(conn)
            conn.execute('UPDATE clara_initiative_goal SET active=0 WHERE singleton=1')
        return {'content': 'Goal follow-up paused. Ordinary conversation remains available. Set a new /agent goal to resume.',
                'operation': 'pause', 'sources': []}
    if operation != 'next':
        raise ValueError('Unsupported initiative operation')
    goal = current(db)
    if not goal or not goal['active']:
        return {'content': 'No active goal. Set one with /agent goal <objective>.', 'operation': 'next', 'sources': []}
    result = search(('search', goal['objective']), db)
    # Preserve source locators and distinguish retrieval from achieved outcomes.
    return {'content': ('Goal: ' + goal['objective'] + '\n\n' + result['content'] +
            '\n\nNext step: review these excerpts and choose one concrete task to prepare here. '
            'These saved excerpts do not establish current market demand or completed work.')[:2000],
            'operation': 'next', 'sources': result['sources']}


def context(db, search):
    goal = current(db)
    if not goal or not goal['active']:
        return {}
    result = search(('search', goal['objective']), db)
    return {
        'objective': goal['objective'],
        'saved_evidence': result['sources'],
        'evidence_scope': 'private_saved_excerpts_not_live_verification',
        'external_execution_connected': False,
        'background_execution_started': False,
    }

