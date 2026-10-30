"""Single-operator private profile, independent of conversation resets.

Only authenticated companion handlers call this store. Never consult it from
Moltbook/public generation. Host durability requires a real persistent mount.
"""
import json
import os
from pathlib import Path
from clara_advisor import validate_profile


def storage_status():
    path = Path(os.getenv('AGENT_DB_PATH', 'agentbroker.sqlite3')).resolve()
    # On Render a root filesystem is ephemeral. An absolute filename or a flag
    # alone does not make it durable. Require a separate mounted backing volume.
    mounted = any(os.path.ismount(parent) for parent in path.parents if parent != Path('/'))
    return {'backend': 'server_sqlite', 'durable_mount_detected': mounted,
            'durability_verified': False,
            'restart_persistence': 'mounted_storage_requires_operator_verification' if mounted else 'unverified_host_storage',
            'scope': 'authenticated_single_owner'}


def schema(conn):
    conn.execute('CREATE TABLE IF NOT EXISTS clara_owner_profile (id INTEGER PRIMARY KEY CHECK(id=1), entries TEXT NOT NULL)')


def save(db, entries):
    entries = validate_profile(entries)
    with db() as conn:
        schema(conn)
        conn.execute('INSERT OR REPLACE INTO clara_owner_profile VALUES (1,?)', (json.dumps(entries, ensure_ascii=False),))
    return entries


def load(db, legacy=()):
    with db() as conn:
        schema(conn)
        row = conn.execute('SELECT entries FROM clara_owner_profile WHERE id=1').fetchone()
        if row is not None:
            return validate_profile(json.loads(row[0]))
        entries = validate_profile(list(legacy))
        if entries:
            conn.execute('INSERT OR IGNORE INTO clara_owner_profile VALUES (1,?)', (json.dumps(entries, ensure_ascii=False),))
            row = conn.execute('SELECT entries FROM clara_owner_profile WHERE id=1').fetchone()
            return validate_profile(json.loads(row[0]))
        return entries


def reject_public_memory(context):
    """Fail closed before any provider receives a misrouted private context."""
    if context.get('_companion') is True:
        return
    private = {'owner_profile', 'private_mem0_memories', 'recalled_private_conversation',
               'archived_private_conversation', 'private_document_excerpts', 'owner_feedback', 'companion'}
    def contains(value):
        if isinstance(value, dict):
            return bool(private.intersection(value)) or any(contains(v) for v in value.values())
        return isinstance(value, list) and any(contains(v) for v in value)
    if contains(context):
        raise ValueError('Private context cannot be sent to public generation')
