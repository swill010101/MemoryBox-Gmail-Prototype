"""Synthetic-only TitaNet process smoke test. Does not open DB or private media."""
import argparse
import array
import hashlib
import json
import math
from pathlib import Path
import tempfile
import time
import wave
from .voice_pilot_runner import Encoder, sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model',required=True);p.add_argument('--sha256',required=True)
    a=p.parse_args();deadline=time.monotonic()+240
    if sha(a.model,deadline)!=a.sha256:raise ValueError('model_hash_mismatch')
    encoder=None
    try:
        with tempfile.TemporaryDirectory(prefix='mb-titanet-synthetic-') as tmp:
            wav=Path(tmp)/'generated.wav'
            with wave.open(str(wav),'wb') as f:
                f.setparams((1,2,16000,0,'NONE','not compressed'))
                f.writeframes(array.array('h',(int(5000*math.sin(i*.09)+2000*math.sin(i*.21)) for i in range(48000))).tobytes())
            encoder=Encoder(a.model,deadline)
            one=encoder.embed(wav,60);two=encoder.embed(wav,60)
            delta=max(abs(a-b) for a,b in zip(one,two))
            if delta>1e-5:raise ValueError('repeatability_check_failed')
            print(json.dumps({'synthetic_only':True,'model_sha256':a.sha256,'dimensions':len(one),
              'finite':all(math.isfinite(x) for x in one),'max_repeat_delta':delta,
              'model_loaded_once':True,'private_media_processed':False,'recognition_accuracy_verified':False}))
    finally:
        if encoder is not None:encoder.close()
if __name__=='__main__':main()
