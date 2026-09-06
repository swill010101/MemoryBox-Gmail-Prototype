"""Read-only voice model discovery: no MB/model import, network, database or media."""
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

packages={}
for name in ('torch','torchaudio','speechbrain','psycopg'):
    try: packages[name]=importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError: packages[name]=None
hf_home=Path(os.environ.get('HF_HOME',str(Path.home()/'.cache'/'huggingface')))
hub=Path(os.environ.get('HF_HUB_CACHE',os.environ.get('HUGGINGFACE_HUB_CACHE',str(hf_home/'hub'))))
roots=[Path(tempfile.gettempdir())/'mb-spkrec-ecapa-voxceleb',
       hub/'models--speechbrain--spkrec-ecapa-voxceleb']
files=[]
for root in roots:
    candidates=[root]
    snapshots=root/'snapshots'
    if snapshots.is_dir(): candidates.extend(sorted(snapshots.iterdir())[:20])
    for folder in candidates:
        for name in ('hyperparams.yaml','embedding_model.ckpt','mean_var_norm_emb.ckpt','classifier.ckpt','label_encoder.txt'):
            p=folder/name
            if p.is_file(): files.append({'path':str(p),'resolved_path':str(p.resolve()),'bytes':p.stat().st_size})
print(json.dumps({'read_only':True,'python':sys.executable,'packages':packages,
 'ffmpeg':shutil.which('ffmpeg'),'cache_roots':[{'path':str(p),'exists':p.exists()} for p in roots],
 'candidate_files':files,'snapshot_limit_per_root':20,'model_loaded':False,'recognition_started':False,
 'limits':'Known model filenames only; cache presence does not prove compatibility. No model contents read.'},indent=2))
