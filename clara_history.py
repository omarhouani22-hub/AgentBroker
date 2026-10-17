"""Owner-only complete chat archive, separate from the bounded model context.

Durability follows AGENT_DB_PATH's backing storage; this module cannot make an
otherwise ephemeral Render filesystem permanent.
"""
import json
import sqlite3
from clara_advisor import words


def schema(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS clara_private_history (
        seq INTEGER PRIMARY KEY AUTOINCREMENT, message_id TEXT UNIQUE NOT NULL,
        role TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL,
        search_words TEXT NOT NULL)''')


def persist(conn, companion):
    schema(conn)
    for message in companion.get('archive',[]) + companion.get('messages',[]):
        if not isinstance(message.get('id'),str) or message.get('role') not in ('user','assistant'):
            continue
        content=message.get('content','')
        if not isinstance(content,str) or not content: continue
        conn.execute('INSERT OR IGNORE INTO clara_private_history (message_id,role,content,created_at,search_words) SELECT ?,?,?,?,? WHERE NOT EXISTS (SELECT 1 FROM clara_private_history WHERE message_id=?)',
                     (message['id'],message['role'],content[:2000],message.get('created_at',''), ' '+' '.join(sorted(words(content)))+' ', message['id']))


def recall(db,query,excluded=()):
    tokens=sorted(words(query))[:20]
    if not tokens: return []
    try:
        with db() as conn:
            schema(conn)
            # Parameterized lexical ranking searches the full archive, not a rolling window.
            terms=' + '.join('CASE WHEN search_words LIKE ? THEN 1 ELSE 0 END' for _ in tokens)
            excluded=list(excluded)[:50]
            where='WHERE message_id NOT IN ('+','.join('?' for _ in excluded)+')' if excluded else ''
            rows=conn.execute('SELECT message_id,role,content,created_at,('+terms+') AS relevance FROM clara_private_history '+where+' ORDER BY relevance DESC,seq DESC LIMIT 4',
                              ['% '+t+' %' for t in tokens]+excluded).fetchall()
        return [{'role':role,'content':content,'created_at':date,'memory_kind':'private_archived_conversation'}
                for identity,role,content,date,score in rows if score>0]
    except sqlite3.OperationalError:
        return []


def count(db):
    with db() as conn:
        schema(conn)
        return conn.execute('SELECT COUNT(*) FROM clara_private_history').fetchone()[0]


def export(db,after=0):
    with db() as conn:
        schema(conn)
        rows=conn.execute('SELECT seq,message_id,role,content,created_at FROM clara_private_history WHERE seq>? ORDER BY seq LIMIT 500',(after,)).fetchall()
    return [{'sequence':seq,'id':identity,'role':role,'content':content,'created_at':date}
            for seq,identity,role,content,date in rows]
