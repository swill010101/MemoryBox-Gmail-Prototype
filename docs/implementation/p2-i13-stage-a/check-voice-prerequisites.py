"""Read-only FlightSim voice prerequisites. No MB/model import, download or media access."""
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import sys

packages={}
for name in ('torch','torchaudio','speechbrain','psycopg'):
    try: packages[name]=importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError: packages[name]=None
roots=[Path.home()/'.cache'/'huggingface',Path.home()/'.cache'/'torch',
       Path(os.environ.get('TEMP',str(Path.home())))/'memorybox_voice_model']
print(json.dumps({'read_only':True,'python':sys.executable,'packages':packages,
  'ffmpeg':shutil.which('ffmpeg'),'cache_roots':[{'path':str(p),'exists':p.exists()} for p in roots],
  'model_loaded':False,'recognition_started':False,
  'required_next_fact':'Exact local voice model path and provenance/revision; cache existence is not model readiness.'},indent=2))
