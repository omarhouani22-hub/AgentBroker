"""Bounded, append-only import and lexical retrieval. No network or training."""
import hashlib
import json
import re


def validate_notes(data):
    if not isinstance(data, list) or not 1 <= len(data) <= 100:
        raise ValueError('Expected 1-100 knowledge notes')
    notes = []
    for item in data:
        if not isinstance(item, dict):
            raise ValueError('Each note must be an object')
        for key, limit in [('topic', 1000), ('note', 12000), ('created_at', 100)]:
            value = item.get(key)
            if not isinstance(value, str) or not value.strip() or len(value) > limit:
                raise ValueError('Invalid ' + key)
        sources = item.get('sources')
        if not isinstance(sources, list) or not 1 <= len(sources) <= 10:
            raise ValueError('Each note needs 1-10 sources')
        clean_sources = []
        for source in sources:
            if not isinstance(source, dict):
                raise ValueError('Invalid source')
            title, url = source.get('title'), source.get('url')
            if (not isinstance(title, str) or not 1 <= len(title) <= 500 or
                    not isinstance(url, str) or len(url) > 2000 or
                    not url.startswith(('https://', 'http://'))):
                raise ValueError('Source needs a title and HTTP(S) URL')
            # Preserve bounded excerpts from our own exports, never fetch URLs here.
            content = source.get('content', '')
            if not isinstance(content, str) or len(content) > 3000:
                raise ValueError('Invalid source excerpt')
            clean_sources.append(dict(title=title, url=url, content=content))
        note = {key: item[key] for key in ('topic', 'note', 'created_at')}
        note['sources'] = clean_sources
        canonical = json.dumps(note, sort_keys=True, ensure_ascii=False)
        note['id'] = 'import-' + hashlib.sha256(canonical.encode()).hexdigest()
        notes.append(note)
    return notes


def retrieve(conn, query):
    words = set(re.findall(r'\w{3,}', query.casefold())) - {
        'the', 'and', 'for', 'with', 'what', 'how', 'عن', 'على', 'في'}
    if not words:
        return []
    # Bounded prototype: rank the most recent 500 notes; not semantic search.
    rows = conn.execute('SELECT id, topic, note, sources, created_at FROM knowledge '
                        'ORDER BY created_at DESC LIMIT 500').fetchall()
    ranked = []
    for identity, topic, note, sources, date in rows:
        title_words = set(re.findall(r'\w{3,}', topic.casefold()))
        body_words = set(re.findall(r'\w{3,}', note.casefold()))
        score = 3 * len(words & title_words) + len(words & body_words)
        if score:
            ranked.append((score, dict(id=identity, topic=topic, note=note[:4000],
                                      sources=json.loads(sources), created_at=date)))
    ranked.sort(key=lambda pair: pair[0], reverse=True)
    return [note for _, note in ranked[:3]]
