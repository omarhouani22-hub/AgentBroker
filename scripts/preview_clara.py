"""Local-only Clara UI preview: temporary DB, synthetic replies, prerecorded speech.
Never point this at production data. No external providers or hosting changes.
"""
import argparse
import os
from pathlib import Path
import sys
import tempfile

parser=argparse.ArgumentParser()
parser.add_argument('--port',type=int,default=8765)
parser.add_argument('--root',default=str(Path(__file__).resolve().parents[1]))
parser.add_argument('--audio',required=True)
args=parser.parse_args()
audio=Path(args.audio).resolve().read_bytes()
with tempfile.TemporaryDirectory(prefix='clara-avatar-preview-') as directory:
    for name in ('OPENROUTER_API_KEY','LLM_API_KEY','CLARA_TTS_API_KEY','MOLTBOOK_API_KEY','MEM0_API_KEY'):
        os.environ.pop(name,None)
    os.environ.update(AGENT_DB_PATH=directory+'/preview.sqlite',AGENT_ACCESS_TOKEN='preview-only-avatar',AGENT_LOGIN_PASSWORD='',CLARA_LOCAL_ONLY='',MEM0_ENABLED='',CLARA_GROWTH_WORKER_ENABLED='',CLARA_GROWTH_PUBLISH_ENABLED='')
    sys.path.insert(0,args.root)
    import app as server
    import moltbook
    from flask import jsonify,Response
    server.app.testing=True
    moltbook.dialogue_model_configured=lambda:True
    moltbook.free_dialogue_json=lambda context:{'skip':False,'content':'Hello Omar. Your reply is ready. I will return to idle when the audio finishes.','lesson':'','_model':'synthetic_preview'}
    server.app.view_functions['clara_speech_status']=lambda:jsonify(available=True,internal=True,max_characters=800,provider='Prerecorded English preview fixture',billing_enabled=False)
    server.app.view_functions['clara_speech']=lambda:Response(audio,mimetype='audio/wav',headers={'Cache-Control':'no-store'})
    @server.app.after_request
    def preview_label(response):
        if response.mimetype=='text/html' and '/clara/' in __import__('flask').request.path:
            response.set_data(response.get_data().replace(b'<main>',b'<main><p id="preview-label" class="status">Development preview: synthetic chat and prerecorded English speech. No live data or accounts.</p>'))
        response.headers['X-Clara-Preview']='synthetic-only'
        return response
    print('Local preview: http://127.0.0.1:'+str(args.port)+'/clara/ ; password: preview-only-avatar',flush=True)
    server.app.run(host='127.0.0.1',port=args.port,use_reloader=False,threaded=True)
