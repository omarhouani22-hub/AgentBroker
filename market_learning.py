"""Store bounded market observations and explicit experiment outcomes.

This ledger does not post, call models, spend money, or claim validated demand.
Durability depends entirely on the SQLite database backing it.
"""
import json
import uuid
from datetime import datetime, timezone

def setup(conn):
    conn.execute('CREATE TABLE IF NOT EXISTS market_snapshots (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, payload TEXT NOT NULL)')
    conn.execute('CREATE TABLE IF NOT EXISTS market_experiments (id TEXT PRIMARY KEY, hypothesis TEXT NOT NULL, prediction TEXT NOT NULL, outcome TEXT, created_at TEXT NOT NULL, observed_at TEXT)')

def save_snapshot(db, report, now=None):
    # Only data emitted by the existing bounded analyzer is stored.
    data = {key: report[key] for key in ('source_count', 'matched_count', 'signal_counts', 'evidence', 'queries', 'errors', 'limitations')}
    if len(data['evidence']) > 30 or len(json.dumps(data, ensure_ascii=False)) > 40000:
        raise ValueError('Market snapshot exceeds limits')
    now = now or datetime.now(timezone.utc).isoformat()
    identity = uuid.uuid4().hex
    with db() as conn:
        setup(conn)
        conn.execute('INSERT INTO market_snapshots VALUES (?, ?, ?)', (identity, now, json.dumps(data, ensure_ascii=False)))
        conn.execute('DELETE FROM market_snapshots WHERE id NOT IN (SELECT id FROM market_snapshots ORDER BY created_at DESC, rowid DESC LIMIT 100)')
    return identity

def recent_snapshots(db, limit=5):
    if type(limit) is not int or not 1 <= limit <= 20: raise ValueError('Invalid limit')
    with db() as conn:
        setup(conn)
        rows = conn.execute('SELECT id, created_at, payload FROM market_snapshots ORDER BY created_at DESC, rowid DESC LIMIT ?', (limit,)).fetchall()
    return [{'id': identity, 'created_at': created, 'report': json.loads(payload)} for identity, created, payload in rows]

def create_experiment(db, hypothesis, prediction):
    if not all(isinstance(v, str) and 1 <= len(v.strip()) <= 1000 for v in (hypothesis, prediction)):
        raise ValueError('Provide bounded hypothesis and prediction')
    identity = uuid.uuid4().hex
    with db() as conn:
        setup(conn)
        conn.execute('INSERT INTO market_experiments VALUES (?, ?, ?, NULL, ?, NULL)', (identity, hypothesis.strip(), prediction.strip(), datetime.now(timezone.utc).isoformat()))
    return identity

def record_outcome(db, identity, outcome):
    if not isinstance(outcome, str) or not 1 <= len(outcome.strip()) <= 2000: raise ValueError('Provide a bounded observed outcome')
    with db() as conn:
        setup(conn)
        changed = conn.execute('UPDATE market_experiments SET outcome=?, observed_at=? WHERE id=? AND outcome IS NULL', (outcome.strip(), datetime.now(timezone.utc).isoformat(), identity)).rowcount
        if changed != 1: raise ValueError('Experiment missing or already recorded')
