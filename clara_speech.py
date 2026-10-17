"""Optional neural speech. Billing is off unless separately approved and capped."""
import json
import os
from datetime import datetime, timezone
from urllib.request import Request
from flask import jsonify, request, make_response


def settings():
    try:
        limit = int(os.getenv('CLARA_TTS_DAILY_CHAR_LIMIT', '0'))
    except ValueError:
        limit = 0
    ready = (os.getenv('CLARA_TTS_BILLING_APPROVED') == 'true'
             and bool(os.getenv('CLARA_TTS_API_KEY')) and 1 <= limit <= 20000)
    return ready, limit


def install_routes(app, db):
    @app.get('/companion/speech/status')
    def clara_speech_status():
        ready, limit = settings()
        return jsonify(available=ready, provider='OpenAI', voice='coral', model='gpt-4o-mini-tts',
                       daily_character_limit=limit if ready else 0,
                       billing_enabled=ready, synthetic_voice=True)

    @app.post('/companion/speech')
    def clara_speech():
        ready, limit = settings()
        if not ready:
            return jsonify(error='Natural voice is not connected. API billing approval and a daily limit are required.'),503
        data = request.get_json(silent=True)
        text = data.get('text') if isinstance(data, dict) else None
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= 2000:
            return jsonify(error='Provide 1–2000 characters for speech'),400
        import moltbook as m
        if not m.DIALOGUE_LOCK.acquire(False):
            return jsonify(error='Clara is busy; try shortly'),409
        try:
            day = datetime.now(timezone.utc).date().isoformat()
            with db() as conn:
                conn.execute('CREATE TABLE IF NOT EXISTS clara_speech_usage (day TEXT PRIMARY KEY,characters INTEGER NOT NULL)')
                conn.execute('BEGIN IMMEDIATE')
                row = conn.execute('SELECT characters FROM clara_speech_usage WHERE day=?',(day,)).fetchone()
                if (row[0] if row else 0) + len(text) > limit:
                    return jsonify(error='Natural voice daily character allowance reached. Device voices remain available.'),429
                # Reserve before network I/O; failed attempts are not automatically retried.
                conn.execute('INSERT INTO clara_speech_usage VALUES (?,?) ON CONFLICT(day) DO UPDATE SET characters=characters+excluded.characters',(day,len(text)))
            instructions = ('Use a warm, natural, conversational feminine delivery, clear and relaxed, with human-like phrasing. '
                            'Speak English naturally. For Arabic, use clear conversational Arabic with a gentle Jordanian accent. '
                            'Read only the provided text, without introductions or extra words.')
            payload = {'model':'gpt-4o-mini-tts','voice':'coral','input':text,'instructions':instructions,'response_format':'mp3'}
            req = Request('https://api.openai.com/v1/audio/speech',data=json.dumps(payload).encode(),
                          headers={'Authorization':'Bearer '+os.environ['CLARA_TTS_API_KEY'],'Content-Type':'application/json'},method='POST')
            with m.TRANSPORT.open(req,timeout=35) as remote:
                audio = remote.read(4_000_001)
                if not audio or len(audio)>4_000_000:
                    raise ValueError('Invalid speech response')
            response = make_response(audio)
            response.headers['Content-Type']='audio/mpeg'
            response.headers['Cache-Control']='no-store'
            response.headers['X-Content-Type-Options']='nosniff'
            return response
        except Exception:
            return jsonify(error='Natural speech failed. No automatic paid retry was attempted.'),503
        finally:
            m.DIALOGUE_LOCK.release()
