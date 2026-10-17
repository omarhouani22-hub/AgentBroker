"""Load the real web process and keep it resident during the voice benchmark."""
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ['CLARA_LOCAL_ONLY']='true'
import app
import internal_voice_check
import json
print(json.dumps(internal_voice_check.evaluate()))
