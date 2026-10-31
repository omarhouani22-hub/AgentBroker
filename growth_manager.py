"""Approval-controlled AgentVault growth. Read-only discovery, no paid inference.

Never reads owner memory, customer checkpoints, PayPal credentials or private
messages. A timer may discover evidence and draft; it cannot approve or publish.
"""
import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import time
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler

SOURCES = ('moltbook', 'github')
QUERIES = ('agent memory loss', 'agent checkpoint restore', 'persistent agent state')
POLICY = {
    'product': 'AgentVault focuses on recoverable agent-state checkpoints. Production sales are closed. A closed-beta request requires owner review; no trial access or storage durability is promised by this answer.',
    'demonstration': 'Use synthetic state only: save a small checkpoint, record its SHA-256, reconstruct the application, restore, and compare the bytes and digest. This is a proposed demonstration, not evidence that a deployed service passed it.',
    'trial': 'Closed-beta participation is subject to owner approval. Never put access keys, private prompts or checkpoint contents in chat. Growth Manager does not itself activate trials.',
    'limits': 'No unlimited storage, zero-knowledge encryption, SLA, guaranteed recovery or autonomous learning is promised. Consult the current owner-approved service terms before using real data.',
    'payments': 'Production sales remain closed. Clara cannot charge, discount, refund, extend entitlements or open sales. Those decisions require the operator and a separately authorized implementation.',
    'support': 'Ask the operator about access, failed restore or trial feedback. Do not send vault keys, invitation codes or checkpoint contents. This answer does not create a support ticket or contact anyone.'}
POLICY_ORIGIN = 'AgentVault conservative beta policy; derived from repository AGENTVAULT.md and PR #66 AGENTVAULT_LAUNCH.md. Requires owner review before public answers or publishing.'
STAGES = ('discovered', 'reviewed', 'permission_requested', 'opted_in', 'conversation', 'trial_requested', 'feedback', 'closed')
FEEDBACK = ('not_tested', 'restore_passed', 'restore_failed', 'access_issue', 'declined', 'other')
SCHEMA = '''
CREATE TABLE IF NOT EXISTS growth_settings (id INTEGER PRIMARY KEY CHECK(id=1), config TEXT NOT NULL, next_scan INTEGER NOT NULL DEFAULT 0, lease_until INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS growth_policies (id TEXT PRIMARY KEY, body TEXT NOT NULL, state TEXT NOT NULL, origin TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS growth_sources (id TEXT PRIMARY KEY, platform TEXT NOT NULL, remote_id TEXT NOT NULL, url TEXT NOT NULL UNIQUE, author TEXT NOT NULL, title TEXT NOT NULL, excerpt TEXT NOT NULL, signals TEXT NOT NULL, fetched_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS growth_leads (id TEXT PRIMARY KEY, source_id TEXT NOT NULL UNIQUE, stage TEXT NOT NULL, verified_at INTEGER NOT NULL DEFAULT 0, followup_at INTEGER NOT NULL DEFAULT 0, feedback TEXT NOT NULL DEFAULT 'not_tested', note TEXT NOT NULL DEFAULT '', updated_at INTEGER NOT NULL, created_at INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS growth_drafts (id TEXT PRIMARY KEY, lead_id TEXT NOT NULL, payload TEXT NOT NULL, digest TEXT NOT NULL, policy_id TEXT NOT NULL, state TEXT NOT NULL, created_at INTEGER NOT NULL, approved_at INTEGER NOT NULL DEFAULT 0, approved_digest TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS growth_actions (id TEXT PRIMARY KEY, kind TEXT NOT NULL, request_meta TEXT NOT NULL, state TEXT NOT NULL, outcome TEXT NOT NULL, created_at INTEGER NOT NULL, completed_at INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS growth_receipts (id TEXT PRIMARY KEY, source TEXT NOT NULL, body TEXT NOT NULL, digest TEXT NOT NULL, received_at INTEGER NOT NULL, issuer_fingerprint TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS growth_reports (day TEXT PRIMARY KEY, body TEXT NOT NULL, created_at INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS growth_leads_followup ON growth_leads(followup_at);
CREATE INDEX IF NOT EXISTS growth_actions_time ON growth_actions(created_at);
'''
POLICY_ID = hashlib.sha256(json.dumps(POLICY, sort_keys=True).encode()).hexdigest()


class GrowthError(ValueError):
    def __init__(self, message, code=400): self.message, self.code = message, code


def setup(db):
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        for statement in SCHEMA.split(';'):
            if statement.strip(): c.execute(statement)
        if 'created_at' not in [row[1] for row in c.execute('PRAGMA table_info(growth_leads)')]:
            c.execute('ALTER TABLE growth_leads ADD COLUMN created_at INTEGER NOT NULL DEFAULT 0')
        if 'issuer_fingerprint' not in [row[1] for row in c.execute('PRAGMA table_info(growth_receipts)')]:
            c.execute("ALTER TABLE growth_receipts ADD COLUMN issuer_fingerprint TEXT NOT NULL DEFAULT ''")
        c.execute('INSERT OR IGNORE INTO growth_settings(id,config) VALUES (1,?)', (json.dumps({'enabled': False, 'sources': []}),))
        c.execute('INSERT OR IGNORE INTO growth_policies VALUES (?,?,?,?)', (POLICY_ID, json.dumps(POLICY), 'pending', POLICY_ORIGIN))


def config(db):
    setup(db)
    with db() as c: return dict(zip(('config', 'next_scan', 'lease_until'), c.execute('SELECT config,next_scan,lease_until FROM growth_settings WHERE id=1').fetchone()))


def safe_text(value, cap=1500):
    if not isinstance(value, str): return ''
    value = re.sub(r'[^\s@]+@[^\s@]+\.[^\s@]+', '[contact omitted]', value)
    value = re.sub(r'(?i)(?:bearer\s+\S+|(?:api[_ -]?key|password|secret|token)\s*[:=]\s*\S+|\bsk-[\w-]+|moltbook_sk_[\w-]+)', '[credential omitted]', value)
    value = re.sub(r'\b[A-Za-z0-9_-]{32,}\b', '[opaque value omitted]', value)
    return ' '.join(value.split())[:cap]


def checked_text(value, cap):
    if not isinstance(value, str) or len(value) > cap or safe_text(value, cap) != ' '.join(value.split()):
        raise GrowthError('Use bounded text without contact details, credentials or checkpoint data')
    if re.search(r'(?i)checkpoint\s*(?:contents|data)\s*[:=]|\{\s*"', value):
        raise GrowthError('Do not enter checkpoint contents')
    return value.strip()


def source_url(platform, identity):
    if platform == 'moltbook' and re.fullmatch(r'[A-Za-z0-9-]{1,100}', identity or ''):
        return 'https://www.moltbook.com/post/' + identity
    if platform == 'github' and re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/issues/[1-9][0-9]{0,9}', identity or ''):
        if any(part in ('.','..') for part in identity.split('/')): raise GrowthError('Invalid public source')
        return 'https://github.com/' + identity
    raise GrowthError('Invalid public source')


def signals(text):
    from agentvault_market_intel import PATTERNS
    if not re.search(r'\b(agent|agents|llm|autonomous)\b', text, re.I): return []
    return [name for name, pattern in PATTERNS.items() if re.search(pattern, text, re.I) and name != 'cost']


def action_begin(db, kind, meta):
    identity = secrets.token_hex(16)
    with db() as c:
        c.execute('INSERT INTO growth_actions VALUES (?,?,?,?,?,?,0)', (identity, kind, json.dumps(meta), 'started', '{}', int(time.time())))
    return identity


def action_end(db, identity, state, outcome):
    with db() as c:
        c.execute('UPDATE growth_actions SET state=?,outcome=?,completed_at=? WHERE id=?', (state, json.dumps(outcome), int(time.time()), identity))


def external_read(db, platform, path, call, query=None):
    identity = action_begin(db, 'public_read', {'source': platform, 'method':'GET', 'path': path, 'query':query})
    try:
        result = call()
        if not isinstance(result, dict): raise ValueError('Invalid public response')
        action_end(db, identity, 'succeeded', {'response_received': True})
        return result
    except Exception as error:
        action_end(db, identity, 'failed', {'error_type': type(error).__name__, 'code': getattr(error, 'code', None) if type(getattr(error, 'code', None)) is int else None})
        return None


def discover_moltbook(db):
    # Do not call moltbook.research: its older feedback collector has a separate
    # participation workflow. Growth discovery uses fixed GET operations only.
    from moltbook import api
    found, seen = [], set()
    profile=external_read(db,'moltbook','/agents/me',lambda:api('GET','/agents/me')) or {}
    own=profile.get('agent') if isinstance(profile.get('agent'),dict) else {}
    own_names={'agent_broker','agentbroker',str(own.get('name','')).casefold()}
    for query in QUERIES:
        result = external_read(db, 'moltbook', '/search', lambda q=query: api('GET', '/search', query={'q': q, 'type': 'posts', 'limit': 3}), query={'q':query,'type':'posts','limit':3})
        items=(result or {}).get('results',[])
        for item in (items if isinstance(items,list) else [])[:3]:
            if not isinstance(item, dict) or item.get('type') != 'post': continue
            identity = item.get('post_id') or item.get('id')
            try: source_url('moltbook', identity)
            except (GrowthError, TypeError): continue
            if identity in seen or len(seen) >= 3: continue
            seen.add(identity)
            result = external_read(db, 'moltbook', '/posts/'+identity, lambda i=identity: api('GET', '/posts/'+i))
            post = (result or {}).get('post', {})
            if not isinstance(post, dict) or post.get('id', identity) != identity: continue
            author = post.get('author') if isinstance(post.get('author'), dict) else {}
            if str(author.get('name','')).casefold() in own_names: continue
            found.append({'platform': 'moltbook', 'remote_id': identity, 'title': post.get('title', ''), 'content': post.get('content', ''), 'author': author.get('name', '')})
    return found


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs): return None


def github_public(query):
    url = 'https://api.github.com/search/issues?' + urlencode({'q': query, 'per_page': 3, 'sort': 'updated'})
    req = Request(url, headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'AgentBroker-Growth/1.0'})
    with build_opener(NoRedirect()).open(req, timeout=15) as response: raw = response.read(200001)
    if len(raw) > 200000: raise ValueError('Public response too large')
    data = json.loads(raw)
    return data if isinstance(data, dict) else {}


def discover_github(db):
    result = external_read(db, 'github', '/search/issues', lambda: github_public('agent checkpoint restore is:issue is:public'), query={'q':'agent checkpoint restore is:issue is:public','per_page':3,'sort':'updated'})
    found = []
    items=(result or {}).get('items',[])
    for item in (items if isinstance(items,list) else [])[:3]:
        if not isinstance(item, dict): continue
        url = item.get('html_url', '')
        if not isinstance(url, str) or not url.startswith('https://github.com/'): continue
        identity = url[len('https://github.com/'):]
        try: source_url('github', identity)
        except GrowthError: continue
        author=item.get('user') if isinstance(item.get('user'),dict) else {}
        found.append({'platform': 'github', 'remote_id': identity, 'title': item.get('title', ''), 'content': item.get('body', ''), 'author': author.get('login', '')})
    return found


def ingest(db, records, now):
    added = []
    for item in records[:6]:
        url = source_url(item['platform'], item['remote_id'])
        title = safe_text(item.get('title'), 200)
        content = safe_text(item.get('content'))
        matched = signals(title + ' ' + content)
        if not matched or not safe_text(item.get('author'), 100): continue
        sid = hashlib.sha256(url.encode()).hexdigest()
        lead = 'lead-' + sid[:24]
        with db() as c:
            old=c.execute('SELECT author,title,excerpt FROM growth_sources WHERE id=?',(sid,)).fetchone()
            if old and tuple(old)!=(safe_text(item.get('author'),100),title,content):
                c.execute('UPDATE growth_leads SET verified_at=0 WHERE source_id=?',(sid,))
                c.execute("UPDATE growth_drafts SET state='retired' WHERE lead_id=? AND state IN ('pending','approved')",(lead,))
            c.execute('INSERT INTO growth_sources VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET author=excluded.author,title=excluded.title,excerpt=excluded.excerpt,signals=excluded.signals,fetched_at=excluded.fetched_at',
                      (sid, item['platform'], item['remote_id'], url, safe_text(item.get('author'), 100), title, content, json.dumps(matched), now))
            c.execute('INSERT OR IGNORE INTO growth_leads(id,source_id,stage,updated_at,created_at) VALUES (?,?,?,?,?)', (lead, sid, 'discovered', now, now))
        added.append(lead)
        draft_for_lead(db, lead, now)
    return added


def draft_for_lead(db, lead, now=None):
    now = int(time.time()) if now is None else now
    with db() as c:
        row = c.execute('SELECT s.platform,s.remote_id,s.url,s.signals,s.title,s.excerpt,s.author FROM growth_leads l JOIN growth_sources s ON s.id=l.source_id WHERE l.id=?', (lead,)).fetchone()
        if not row: raise GrowthError('Unknown lead', 404)
    platform, remote_id, url, labels, title, excerpt, author = row
    labels = json.loads(labels)
    angle = ('Restoring a checkpoint is only useful if the restored bytes match the saved digest.' if 'restore_failure' in labels else
             'An agent restart is a useful point to test which state actually survives.' if 'state_loss' in labels or 'durability' in labels else
             'A recovery test should avoid putting access keys or private checkpoint contents in public discussions.')
    content = (angle + ' A small synthetic test: save a checkpoint, record its SHA-256, reconstruct the application, restore, and compare bytes and digest. '
               'AgentVault is being evaluated for recoverable agent state. Production sales are closed; any closed-beta participation requires owner review. '
               'This is a proposed test, not a claim of verified service durability or a customer testimonial.')
    payload = {'kind': 'educational_comment' if platform == 'moltbook' else 'educational_draft', 'platform': platform,
               'target_id': remote_id, 'content': content, 'source_url': url, 'source_platform':platform, 'evidence_author':author, 'evidence_hash':hashlib.sha256(json.dumps([title,excerpt,author]).encode()).hexdigest(), 'evidence_quote':excerpt[:240], 'evidence_scope': 'Public use-case hypothesis; not a customer or willingness-to-pay claim.'}
    return add_draft(db, lead, payload, POLICY_ID, now)


def draft_digest(payload, policy_id):
    return hashlib.sha256(json.dumps({'payload': payload, 'policy_id': policy_id}, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def add_draft(db, lead, payload, policy_id, now):
    digest = draft_digest(payload, policy_id)
    identity = 'draft-' + digest[:28]
    with db() as c:
        c.execute('INSERT OR IGNORE INTO growth_drafts(id,lead_id,payload,digest,policy_id,state,created_at) VALUES (?,?,?,?,?,?,?)', (identity, lead, json.dumps(payload), digest, policy_id, 'pending', now))
    return identity


def review_draft(db, identity, decision, digest):
    if decision not in ('approve', 'reject', 'revoke'): raise GrowthError('Choose approve, reject or revoke')
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        row = c.execute('SELECT digest,policy_id,state FROM growth_drafts WHERE id=?', (identity,)).fetchone()
        if not row: raise GrowthError('Unknown draft', 404)
        if row[0] != digest or row[2] not in (('approved',) if decision == 'revoke' else ('pending',)): raise GrowthError('Draft changed or was already reviewed', 409)
        policy = c.execute('SELECT state FROM growth_policies WHERE id=?', (row[1],)).fetchone()
        if decision == 'approve' and (not policy or policy[0] != 'approved'): raise GrowthError('Approve the product policy before a draft', 409)
        c.execute('UPDATE growth_drafts SET state=?,approved_at=?,approved_digest=? WHERE id=?', ('approved' if decision == 'approve' else 'pending' if decision == 'revoke' else 'rejected', int(time.time()), digest if decision == 'approve' else '', identity))


def publishing_ready():
    path = os.getenv('AGENT_DB_PATH', '')
    return (os.getenv('CLARA_GROWTH_PUBLISH_ENABLED') == 'true' and os.getenv('CLARA_GROWTH_DURABLE_STORAGE_CONFIRMED') == 'true'
            and os.path.isabs(path) and path != ':memory:' and bool(os.getenv('MOLTBOOK_API_KEY','').strip()))


def publish(db, identity, expected_digest):
    if not publishing_ready(): raise GrowthError('Publishing disabled: server enablement, durable storage and a configured Moltbook account are required', 409)
    now = int(time.time())
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        row = c.execute('SELECT payload,digest,policy_id,state,approved_at,approved_digest FROM growth_drafts WHERE id=?', (identity,)).fetchone()
        if not row: raise GrowthError('Unknown draft', 404)
        payload = json.loads(row[0])
        policy = c.execute('SELECT state FROM growth_policies WHERE id=?', (row[2],)).fetchone()
        if (row[3] != 'approved' or row[1] != expected_digest or row[5] != row[1]
                or row[2] != POLICY_ID or draft_digest(payload, row[2]) != row[1] or not policy or policy[0] != 'approved'
                or not 0 <= now-row[4] <= 86400): raise GrowthError('Current, unexpired approval for these exact bytes is required', 409)
        if payload['platform'] != 'moltbook' or payload['kind'] not in ('educational_comment','educational_post'): raise GrowthError('This source is read-only; no publishing adapter', 409)
        if payload['kind'] == 'educational_comment': source_url('moltbook', payload['target_id'])
        elif payload['target_id'] != 'general': raise GrowthError('Unsupported post destination')
        recent=c.execute("SELECT request_meta FROM growth_actions WHERE kind IN ('publish_comment','publish_post') AND created_at>?",(now-86400,)).fetchall()
        prospect_hash=hashlib.sha256((payload['source_platform']+':'+payload['evidence_author'].casefold()).encode()).hexdigest()
        if len(recent)>=3: raise GrowthError('Initial-beta limit: at most three external publishing attempts per day',429)
        if any(json.loads(meta[0]).get('target_id')==payload['target_id'] for meta in recent):
            raise GrowthError('This target already had a publishing attempt today; inspect its outcome instead of retrying',409)
        if any(json.loads(meta[0]).get('prospect_hash')==prospect_hash for meta in recent):
            raise GrowthError('This public account already had a publishing attempt today',409)
        # Reserve before I/O. A crash/timeout cannot cause an automatic second post.
        c.execute("UPDATE growth_drafts SET state='reserved' WHERE id=?", (identity,))
        action_id = secrets.token_hex(16)
        c.execute('INSERT INTO growth_actions VALUES (?,?,?,?,?,?,0)', (action_id, 'publish_comment' if payload['kind']=='educational_comment' else 'publish_post', json.dumps({'draft_id': identity, 'digest': row[1], 'target_id': payload['target_id'], 'prospect_hash':prospect_hash, 'method':'POST','path':'/posts/'+payload['target_id']+'/comments' if payload['kind']=='educational_comment' else '/posts'}), 'reserved', '{}', now))
    try:
        from moltbook import api
        from growth_publication import approved_publication
        path = '/posts/'+payload['target_id']+'/comments' if payload['kind']=='educational_comment' else '/posts'
        body = {'content':payload['content']} if payload['kind']=='educational_comment' else {'submolt_name':'general','title':payload['title'],'content':payload['content']}
        with approved_publication(action_id, 'POST', path, body):
            result = api('POST', path, body)
        comment = (result.get('comment') or result.get('data', {}).get('comment') or {}) if payload['kind']=='educational_comment' else (result.get('post') or {})
        remote_id = comment.get('id')
        confirmed = (isinstance(remote_id, str) and re.fullmatch(r'[A-Za-z0-9-]{1,100}', remote_id)
                     and comment.get('content') == payload['content'] and not result.get('verification') and not result.get('verification_required') and not comment.get('verification_required') and not comment.get('verification') and comment.get('verification_status') not in ('pending','required'))
        state = 'published' if confirmed else 'submitted_unverified'
        action_end(db, action_id, state, {'remote_id': remote_id if isinstance(remote_id, str) and re.fullmatch(r'[A-Za-z0-9-]{1,100}', remote_id) else None, 'content_verified': bool(confirmed)})
    except Exception as error:
        state = 'uncertain'
        action_end(db, action_id, state, {'error_type': type(error).__name__, 'retry_permitted': False})
    with db() as c: c.execute('UPDATE growth_drafts SET state=? WHERE id=?', (state, identity))
    return {'state': state, 'action_id': action_id, 'automatic_retry': False}


def edit_draft(db, identity, content):
    content = checked_text(content, 1800)
    if not content: raise GrowthError('Provide draft text')
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        row = c.execute('SELECT lead_id,payload,policy_id,state FROM growth_drafts WHERE id=?', (identity,)).fetchone()
        if not row: raise GrowthError('Unknown draft', 404)
        if row[3] not in ('pending', 'approved', 'rejected'): raise GrowthError('A reserved/submitted draft cannot be edited or retried', 409)
        payload = json.loads(row[1]); payload['content'] = content
        if draft_digest(payload, row[2]) == draft_digest(json.loads(row[1]), row[2]): raise GrowthError('No change')
        payload['revision']=secrets.token_hex(8)
        c.execute("UPDATE growth_drafts SET state='retired' WHERE id=?", (identity,))
    return add_draft(db, row[0], payload, row[2], int(time.time()))


def synthetic_demo(db, lead):
    """Run reviewed repository code with throwaway keys and synthetic state only."""
    import tempfile
    from cryptography.fernet import Fernet
    from agentvault import AgentVault
    with db() as c:
        row=c.execute('SELECT s.signals FROM growth_leads l JOIN growth_sources s ON s.id=l.source_id WHERE l.id=?',(lead,)).fetchone()
    if not row: raise GrowthError('Unknown lead',404)
    labels=json.loads(row[0])
    case='restore_failure' if 'restore_failure' in labels else 'state_loss' if 'state_loss' in labels else 'security'
    # No customer inputs, environment vault directory/key or checkpoint contents.
    sample=json.dumps({'synthetic':True,'agent':'demo-agent','use_case':case,'step':1},sort_keys=True).encode()
    token=secrets.token_urlsafe(32);key=Fernet.generate_key()
    hashes={'synthetic-demo':hashlib.sha256(token.encode()).hexdigest()}
    event=action_begin(db,'synthetic_demo',{'lead_id':lead,'scope':'isolated_local_prototype'})
    try:
        with tempfile.TemporaryDirectory(prefix='growth-synthetic-') as directory:
            vault=AgentVault(directory,key,hashes)
            version=vault.save('synthetic-demo',token,sample)
            recovered=AgentVault(directory,key,hashes).restore('synthetic-demo',token)
            if recovered!=sample: raise ValueError('Synthetic comparison failed')
            try: vault.restore('synthetic-demo','wrong-fixture-token')
            except PermissionError: pass
            else: raise ValueError('Synthetic authorization failed')
        evidence={'scope':'isolated_local_prototype','verified':True,'byte_count':len(sample),'sha256':hashlib.sha256(sample).hexdigest(),'version':version,
                  'checks':['encrypted save','application reconstruction','exact restore bytes','wrong token rejected'],
                  'hosted_durability_verified':False,'customer_data_used':False}
        action_end(db,event,'completed',evidence)
    except Exception as error:
        action_end(db,event,'failed',{'error_type':type(error).__name__})
        raise GrowthError('Synthetic demo failed; no hosted storage or customer data was changed',503) from None
    base=draft_for_lead(db,lead)
    with db() as c: payload=json.loads(c.execute('SELECT payload FROM growth_drafts WHERE id=?',(base,)).fetchone()[0])
    payload['demo_evidence']={'action_id':event,**evidence}
    payload['content']+=' An isolated local prototype demonstration passed exact synthetic-byte restore and rejected a wrong access token. This does not verify deployed service durability, disaster recovery or customer results.'
    return {'evidence':evidence,'draft_id':add_draft(db,lead,payload,POLICY_ID,int(time.time())),'approved':False,'published':False}


def update_lead(db, identity, data):
    if set(data) - {'stage', 'followup_at', 'feedback', 'note', 'verify_source'}: raise GrowthError('Unsupported lead field')
    if type(data.get('verify_source', False)) is not bool: raise GrowthError('Invalid verification choice')
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        row = c.execute('SELECT stage,followup_at,feedback,note,verified_at FROM growth_leads WHERE id=?', (identity,)).fetchone()
        if not row: raise GrowthError('Unknown lead', 404)
        stage = data.get('stage',row[0]); followup = data.get('followup_at',row[1])
        feedback = data.get('feedback',row[2]); note = checked_text(data.get('note',row[3]),400)
        if stage not in STAGES or feedback not in FEEDBACK or type(followup) is not int or not 0 <= followup < 10**12: raise GrowthError('Invalid lead state or follow-up')
        c.execute('UPDATE growth_leads SET stage=?,followup_at=?,feedback=?,note=?,verified_at=?,updated_at=? WHERE id=?',
                  (stage, followup, feedback, note, int(time.time()) if data.get('verify_source') else row[4], int(time.time()), identity))


def authenticate_receipt(source, raw, signature):
    """Authenticate before any owner-database access or initialization."""
    keys = {'trial': 'CLARA_GROWTH_TRIAL_RECEIPT_KEY', 'revenue': 'CLARA_GROWTH_REVENUE_RECEIPT_KEY'}
    key = os.getenv(keys.get(source, ''), '')
    if len(key) < 32:  raise GrowthError('Receipt issuer is not configured', 503)
    if not isinstance(signature,str) or not re.fullmatch('[a-f0-9]{64}',signature): raise GrowthError('Invalid receipt signature',403)
    expected = hmac.new(key.encode(), raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected): raise GrowthError('Invalid receipt signature', 403)
    return hashlib.sha256(key.encode()).hexdigest()


def receive_receipt(db, source, raw, signature):
    # Issuer adapters are not provisioned here. Unsigned owner-entered claims
    # cannot become verified trial activations or revenue.
    issuer_fingerprint=authenticate_receipt(source,raw,signature)
    try: data = json.loads(raw)
    except (ValueError, UnicodeError): raise GrowthError('Invalid receipt')
    if not isinstance(data, dict) or set(data) != {'id', 'lead_id', 'kind', 'occurred_at', 'amount_minor', 'currency', 'environment', 'evidence_kind'}: raise GrowthError('Invalid receipt fields')
    if (not isinstance(data['id'], str) or not re.fullmatch('[A-Za-z0-9_-]{1,100}', data['id'])
            or not isinstance(data['lead_id'], str) or type(data['occurred_at']) is not int
            or not 0 < data['occurred_at'] <= int(time.time())+60 or type(data['amount_minor']) is not int): raise GrowthError('Invalid receipt values')
    allowed = ('trial_activated', 'conversation_verified') if source == 'trial' else ('revenue_settled', 'revenue_reversed')
    if data['kind'] not in allowed: raise GrowthError('Receipt kind is outside issuer scope')
    if source == 'revenue' and (data['environment'] != 'live' or data['evidence_kind'] != 'merchant_settlement'):
        raise GrowthError('Sandbox orders, captures and unverified settlements are not actual revenue')
    if source == 'trial' and (data['environment'] != 'staging' or data['evidence_kind'] != ('committed_trial_activation' if data['kind']=='trial_activated' else 'authenticated_conversation')):
        raise GrowthError('A committed staging event is required')
    if source == 'trial' and (data['amount_minor'] != 0 or data['currency'] != ''): raise GrowthError('Trial issuer cannot report money')
    if source == 'revenue' and (not 1 <= data['amount_minor'] <= 100000000 or data['currency'] != 'USD'): raise GrowthError('Invalid settlement receipt')
    identity = source+':'+data['id']; digest = hashlib.sha256(raw).hexdigest()
    with db() as c:
        if not c.execute('SELECT 1 FROM growth_leads WHERE id=?', (data['lead_id'],)).fetchone(): raise GrowthError('Unknown lead', 404)
        old = c.execute('SELECT digest FROM growth_receipts WHERE id=?', (identity,)).fetchone()
        if old and old[0] != digest: raise GrowthError('Conflicting receipt ID', 409)
        c.execute('INSERT INTO growth_receipts(id,source,body,digest,received_at,issuer_fingerprint) VALUES (?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET received_at=excluded.received_at,issuer_fingerprint=excluded.issuer_fingerprint', (identity, source, json.dumps(data), digest, int(time.time()), issuer_fingerprint))
    return {'accepted': True, 'duplicate': bool(old)}


def observe_conversations(db):
    from moltbook import api
    with db() as c:
        rows = c.execute("SELECT d.lead_id,d.payload,a.outcome,s.author FROM growth_drafts d JOIN growth_leads l ON l.id=d.lead_id JOIN growth_sources s ON s.id=l.source_id JOIN growth_actions a ON json_extract(a.request_meta,'$.draft_id')=d.id WHERE d.state='published' AND a.state='published' ORDER BY a.created_at DESC LIMIT 2").fetchall()
    for lead, payload, outcome, author in rows:
        payload, outcome = json.loads(payload), json.loads(outcome)
        target = outcome['remote_id'] if payload['kind'] == 'educational_post' else payload['target_id']
        result = external_read(db, 'moltbook', '/posts/'+target+'/comments', lambda: api('GET', '/posts/'+target+'/comments', query={'limit': 20, 'sort': 'new'}))
        comments=(result or {}).get('comments',[])
        for comment in (comments if isinstance(comments,list) else [])[:20]:
            if not isinstance(comment, dict): continue
            responder = comment.get('author') if isinstance(comment.get('author'),dict) else {}
            name=responder.get('name','')
            if not isinstance(name,str) or name.casefold() != author.casefold(): continue
            if payload['kind'] == 'educational_comment' and comment.get('parent_id') != outcome.get('remote_id'): continue
            identity = comment.get('id')
            if not isinstance(identity, str) or not re.fullmatch('[A-Za-z0-9-]{1,100}', identity): continue
            if not isinstance(comment.get('content'), str) or len(comment['content'].strip()) < 2: continue
            body = {'kind': 'conversation_verified', 'lead_id': lead, 'evidence_url': payload['source_url'], 'amount_minor': 0, 'currency': ''}
            with db() as c: c.execute('INSERT OR IGNORE INTO growth_receipts(id,source,body,digest,received_at) VALUES (?,?,?,?,?)', ('moltbook:'+identity, 'moltbook', json.dumps(body), hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest(), int(time.time())))


def integration_status(cfg, actions, receipt_rows):
    """Configuration and observed deliveries are not live service-health probes."""
    result={}
    for source in SOURCES:
        configured=source=='github' or bool(os.getenv('MOLTBOOK_API_KEY','').strip())
        enabled=source in cfg['sources']
        last=next((a for a in actions if a['kind']=='public_read' and a['request'].get('source')==source),None)
        state=('not_enabled' if not enabled else 'not_connected' if not configured else
               'not_verified' if not last else 'unavailable' if last['state']=='failed' else
               'historical_read_succeeded' if last['state']=='succeeded' else 'checking')
        result[source]={'status':state,'configured':configured,'permitted':enabled,
                        'last_attempt_at':last['created_at'] if last else None,'live_health_verified':False}
    for source,env in (('trial','CLARA_GROWTH_TRIAL_RECEIPT_KEY'),('revenue','CLARA_GROWTH_REVENUE_RECEIPT_KEY')):
        key=os.getenv(env,''); configured=len(key)>=32
        fingerprint=hashlib.sha256(key.encode()).hexdigest() if configured else None
        matching=[r for r in receipt_rows if r[0]==source and fingerprint and r[3]==fingerprint]
        result[source]={'status':'not_connected' if not configured else 'awaiting_receipts' if not matching else 'receipts_received',
                        'configured':configured,'last_received_at':max((r[2] for r in matching),default=None),
                        'live_health_verified':False}
    result['customer_inbox']={'status':'not_connected','configured':False,'live_health_verified':False}
    return result


def snapshot(db):
    setting = config(db); cfg = json.loads(setting['config'])
    with db() as c:
        leads = [dict(zip(('id','stage','verified_at','followup_at','feedback','note','updated_at','platform','url','author','title','excerpt','signals','fetched_at'), row)) for row in c.execute('SELECT l.id,l.stage,l.verified_at,l.followup_at,l.feedback,l.note,l.updated_at,s.platform,s.url,s.author,s.title,s.excerpt,s.signals,s.fetched_at FROM growth_leads l JOIN growth_sources s ON s.id=l.source_id ORDER BY l.updated_at DESC LIMIT 200')]
        drafts = [dict(zip(('id','lead_id','payload','digest','policy_id','state','created_at','approved_at'), row)) for row in c.execute('SELECT id,lead_id,payload,digest,policy_id,state,created_at,approved_at FROM growth_drafts ORDER BY created_at DESC LIMIT 100')]
        policies = [dict(zip(('id','body','state','origin'), row)) for row in c.execute('SELECT * FROM growth_policies')]
        receipt_rows=[(source,json.loads(body),received,fingerprint) for source,body,received,fingerprint in c.execute('SELECT source,body,received_at,issuer_fingerprint FROM growth_receipts')]
        receipts = [(row[0],row[1]) for row in receipt_rows]
        totals = dict(c.execute('SELECT stage,COUNT(*) FROM growth_leads GROUP BY stage'))
        verified = c.execute('SELECT COUNT(*) FROM growth_leads WHERE verified_at>0').fetchone()[0]
        total_leads = c.execute('SELECT COUNT(*) FROM growth_leads').fetchone()[0]
        actions = [dict(zip(('id','kind','request','state','outcome','created_at','completed_at'), row)) for row in c.execute('SELECT * FROM growth_actions ORDER BY created_at DESC LIMIT 100')]
        report = c.execute('SELECT body FROM growth_reports ORDER BY day DESC LIMIT 1').fetchone()
    for row in leads: row['signals'] = json.loads(row['signals'])
    for row in drafts: row['payload'] = json.loads(row['payload'])
    for row in policies: row['body'] = json.loads(row['body'])
    for row in actions: row['request'] = json.loads(row['request']); row['outcome'] = json.loads(row['outcome'])
    integrations=integration_status(cfg,actions,receipt_rows)
    trial_history=any(source=='trial' and r['kind']=='trial_activated' for source,r in receipts)
    revenue_history=any(source=='revenue' for source,_ in receipts)
    trial_received=trial_history and integrations['trial']['status']=='receipts_received'
    revenue_received=revenue_history and integrations['revenue']['status']=='receipts_received'
    activated = {r['lead_id'] for _, r in receipts if r['kind'] == 'trial_activated'}
    converted = {r['lead_id'] for _, r in receipts if r['kind'] == 'revenue_settled'}
    for lead in leads:
        lead['verified_trial_activation']=lead['id'] in activated
        lead['verified_historical_conversion']=lead['id'] in (activated & converted)
    net = sum((1 if r['kind'] == 'revenue_settled' else -1)*r['amount_minor'] for _,r in receipts if r['kind'] in ('revenue_settled', 'revenue_reversed'))
    metrics = {'discovered_use_cases': total_leads, 'owner_verified_public_leads': verified,
               'verified_conversations': len({r['lead_id'] for _,r in receipts if r['kind'] == 'conversation_verified'}),
               'trial_activations': len(activated) if trial_received else None,
               'converted_trials': len(activated & converted) if trial_received and revenue_received else None,
               'trial_to_paid_rate': len(activated & converted)/len(activated) if activated and trial_received and revenue_received else None,
               'actual_net_revenue_minor': net if revenue_received else None, 'currency': 'USD',
               'trial_receipts_connected': trial_received, 'revenue_receipts_connected': revenue_received}
    historical_metrics={'trial_activations':len(activated) if trial_history else None,
                        'actual_net_revenue_minor':net if revenue_history else None,
                        'converted_trials':len(activated & converted) if trial_history and revenue_history else None,
                        'scope':'Previously signature-verified received events only; not a live connection or a complete business ledger.'}
    recommendations = []
    for lead in sorted(leads, key=lambda x:(not bool(x['followup_at'] and x['followup_at']<=int(time.time())), -len(x['signals']))):
        if lead['stage'] == 'closed': continue
        action = (
            'Review the public use case, then review its educational draft. Do not send a direct message.' if not lead['verified_at'] else
            'Review the due internal follow-up; contact only with documented permission and approval.' if lead['followup_at'] and lead['followup_at'] <= int(time.time()) else
            'Triage the owner-reported restore failure with a synthetic reproduction; never request customer checkpoint contents.' if lead['feedback']=='restore_failed' else
            'Review the beta intake request with the operator. Growth Manager cannot activate the trial.' if lead['stage']=='trial_requested' else
            'Prepare a synthetic restore walkthrough for the owner to review; do not promise trial access.' if lead['stage'] in ('opted_in','conversation') else
            'Ask the owner to review one bounded synthetic restore demonstration for this use case.')
        recommendations.append({'lead_id': lead['id'], 'source_url': lead['url'], 'action':action})
        if len(recommendations) == 3: break
    if not recommendations: recommendations = [{'action': 'Enable permitted public sources and collect evidence before proposing outreach.'}]
    return {'settings': cfg, 'next_scan': setting['next_scan'], 'leads': leads, 'drafts': drafts, 'policies': policies,
            'actions': actions, 'metrics': metrics, 'integrations':integrations,'historical_metrics':historical_metrics, 'stages': totals, 'recommendations': recommendations,
            'daily_report': json.loads(report[0]) if report else None, 'sales_enabled': False,
            'publishing_enabled': publishing_ready(), 'worker_configured': os.getenv('CLARA_GROWTH_WORKER_ENABLED') == 'true',
            'limits': ['Public evidence is not customer consent, a sale, or willingness to pay.', 'Follow-ups and feedback entered here are owner-reported, not verified conversations or activations.', 'Trial and settlement issuer adapters are not connected by this installation.', 'SQLite hosting durability and continuous uptime are unverified.']}


def daily_report(db, now, refresh=False):
    setup(db)
    day = datetime.fromtimestamp(now, timezone.utc).date().isoformat()
    with db() as c:
        if not refresh and c.execute('SELECT 1 FROM growth_reports WHERE day=?', (day,)).fetchone(): return
    data = snapshot(db)
    with db() as c:
        new_today=c.execute('SELECT COUNT(*) FROM growth_leads WHERE created_at>=? AND created_at<?',(now-now%86400,now-now%86400+86400)).fetchone()[0]
        activity=dict(c.execute("SELECT state,COUNT(*) FROM growth_actions WHERE created_at>=? AND kind IN ('public_read','publish_comment','publish_post') GROUP BY state",(now-now%86400,)))
        pending=c.execute("SELECT COUNT(*) FROM growth_drafts WHERE state='pending'").fetchone()[0]
    body = {'new_public_use_cases_today':new_today,'external_action_outcomes_today':activity,'metric_window':'lifetime as of report time','day': day, 'as_of': now, 'metrics': data['metrics'], 'pipeline': data['stages'],
            'integrations':data['integrations'],'historical_metrics':data['historical_metrics'],
            'pending_owner_approvals': pending,
            'recommendations': data['recommendations'], 'sales_enabled': False,
            'evidence_limits': data['limits']}
    with db() as c: c.execute('INSERT OR REPLACE INTO growth_reports VALUES (?,?,?)', (day, json.dumps(body), now))


def tick(db, now=None):
    now = int(time.time()) if now is None else now
    config(db)
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        raw, next_scan, lease = c.execute('SELECT config,next_scan,lease_until FROM growth_settings WHERE id=1').fetchone()
        cfg = json.loads(raw)
        if not cfg['enabled'] or lease > now or next_scan > now: return {'scanned': False}
        c.execute('UPDATE growth_settings SET lease_until=?,next_scan=? WHERE id=1', (now+1800, now+3600))
    try:
        records = []
        for source in cfg['sources']:
            try:
                if source == 'moltbook': records += discover_moltbook(db)
                elif source == 'github': records += discover_github(db)
            except Exception as error:
                event=action_begin(db,'source_validation',{'source':source})
                action_end(db,event,'failed',{'error_type':type(error).__name__})
        leads = ingest(db, records, now)
        if 'moltbook' in cfg['sources']: observe_conversations(db)
        daily_report(db, now, refresh=True)
        return {'scanned': True, 'matching_use_cases': len(leads), 'external_publishing': False}
    finally:
        with db() as c: c.execute('UPDATE growth_settings SET lease_until=0 WHERE id=1')


_WORKER_LOCK = threading.Lock()
_WORKERS = set()

def start_worker(db):
    if os.getenv('CLARA_GROWTH_WORKER_ENABLED') != 'true': return
    key = os.path.abspath(os.getenv('AGENT_DB_PATH', 'agentbroker.sqlite3'))
    with _WORKER_LOCK:
        if key in _WORKERS: return
        _WORKERS.add(key)
    def run():
        while True:
            try: tick(db)
            except Exception: pass  # No source bodies, secrets or private notes in logs.
            threading.Event().wait(60)
    threading.Thread(target=run, name='clara-growth-readonly', daemon=True).start()
