"""Dedicated exact-span runner; never routes through Learn or legacy queues."""
from __future__ import annotations
import array
import concurrent.futures
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import wave
from .scope import ScopeDenied, digest
from .voice_pilot import score, vector
from . import voice_pilot_store as store

def remaining(deadline, cap):
    seconds=min(cap,deadline-time.monotonic())
    if seconds<=0: raise ScopeDenied('pilot_deadline_exceeded')
    return seconds

def sha(path, deadline):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        while True:
            remaining(deadline,1200)
            chunk=f.read(1024*1024)
            if not chunk: return h.hexdigest()
            h.update(chunk)

def preflight(plan, media_root, model, ffmpeg, deadline):
    root=Path(media_root).resolve(strict=True)
    model=Path(model).resolve(strict=True); ffmpeg=Path(ffmpeg).resolve(strict=True)
    if not model.is_file() or not ffmpeg.is_file(): raise ScopeDenied('pilot_local_files_required')
    if sha(model,deadline)!=plan['model']['sha256']: raise ScopeDenied('pilot_model_changed')
    sources={(s['provider_key'],s['video_external_id']):s for s in plan['manifest']['sources']}
    paths={}
    for span in plan['spans']:
        key=(span['provider_key'],span['source_id'])
        if key in paths: continue
        source=sources[key]; path=(root/source['relative_path']).resolve(strict=True)
        if not path.is_relative_to(root) or not path.is_file(): raise ScopeDenied('pilot_source_outside_root')
        if sha(path,deadline)!=span['source_sha256']: raise ScopeDenied('pilot_source_changed')
        paths[key]=path
    return paths,model,ffmpeg

def extract(ffmpeg, source, span, destination, timeout):
    duration=span['end']-span['start']
    args=[str(ffmpeg),'-nostdin','-v','error','-ss',format(span['start'],'.6f'),'-i',str(source),
          '-t',format(duration,'.6f'),'-map','0:a:0','-vn','-ac','1','-ar','16000',
          '-c:a','pcm_s16le','-n',str(destination)]
    result=subprocess.run(args,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=timeout)
    if result.returncode: raise ScopeDenied('pilot_audio_extraction_failed')
    with wave.open(str(destination),'rb') as f:
        if (f.getnchannels(),f.getsampwidth(),f.getframerate())!=(1,2,16000): raise ScopeDenied('pilot_audio_format')
        seconds=f.getnframes()/16000
        if abs(seconds-duration)>.1: raise ScopeDenied('pilot_audio_duration_mismatch')
        samples=array.array('h',f.readframes(f.getnframes()))
    if not samples: raise ScopeDenied('pilot_empty_audio')
    rms=math.sqrt(sum((x/32768.)**2 for x in samples)/len(samples))
    clipped=sum(abs(x)>=32760 for x in samples)/len(samples)
    if rms<1e-5 or clipped>.01: raise ScopeDenied('pilot_audio_quality_rejected')
    return {'duration_sec':seconds,'rms':rms,'clipped_fraction':clipped}

class Encoder:
    def __init__(self, model, deadline):
        env=dict(os.environ,HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',PYTHONDONTWRITEBYTECODE='1')
        self.proc=subprocess.Popen([sys.executable,'-B','-m','memorybox.processing.voice_pilot_worker',str(model)],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,env=env,
            **({'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}))
        self.pool=concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            if self.read(remaining(deadline,120))!={'ready':True}: raise ScopeDenied('pilot_model_not_ready')
        except BaseException:
            self.close(); raise
    def read(self, timeout):
        try:
            line=self.pool.submit(self.proc.stdout.readline).result(timeout=timeout)
            if not line or len(line)>100000: raise ValueError()
            data=json.loads(line)
            if 'error_type' in data: raise ValueError()
            return data
        except Exception as exc: raise ScopeDenied('pilot_encoder_failed_or_timed_out') from exc
    def embed(self, wav, timeout):
        self.proc.stdin.write(json.dumps({'wav':str(wav)})+'\n'); self.proc.stdin.flush()
        return vector(self.read(timeout)['vector'])
    def close(self):
        if self.proc.poll() is None: self.proc.kill()
        self.proc.wait(timeout=10)
        self.pool.shutdown(wait=True)
        self.proc.stdin.close(); self.proc.stdout.close()

def run(identifier, expected_sha, media_root, model, ffmpeg):
    deadline=time.monotonic()+1200
    plan=store.load(identifier)
    if digest(plan)!=expected_sha: raise ScopeDenied('pilot_reviewed_plan_hash_mismatch')
    paths,model,ffmpeg=preflight(plan,media_root,model,ffmpeg,deadline)
    store.claim(identifier)  # Whole admission is single-use, including failures.
    encoder=None
    try:
        provenance={'plan_sha256':expected_sha,'model':plan['model'],'thresholds':plan['thresholds'],
          'preprocessing':'first audio stream; mono PCM16 16000Hz; exact source span',
          'ffmpeg_sha256':sha(ffmpeg,deadline),'audio':[], 'synthetic':False}
        vectors=[]
        with tempfile.TemporaryDirectory(prefix='mb-i13-pilot-') as tmp:
            for index, span in enumerate(plan['spans']):
                store.reserve(identifier,span['key'])
                source=paths[(span['provider_key'],span['source_id'])]
                wav=Path(tmp)/f'{index}.wav'
                quality=extract(ffmpeg,source,span,wav,remaining(deadline,plan['extract_timeout_sec']))
                store.load(identifier)  # Stop/revision/retirement check before model work.
                if encoder is None: encoder=Encoder(model,deadline)
                vectors.append(encoder.embed(wav,remaining(deadline,plan['embedding_timeout_sec'])))
                provenance['audio'].append({'key':span['key'],**quality})
            results=[{'key':s['key'],'annotation_id':s['annotation_id'],
               'expected_match':s.get('expected_match',s.get('person_id')==plan['person_ids'][0]),
               **score(vectors[0],v,plan['thresholds'])} for s,v in zip(plan['spans'][1:],vectors[1:])]
            # Detect changed source/model content before durable publication.
            preflight(plan,media_root,model,ffmpeg,deadline)
            remaining(deadline,1)
            store.publish(identifier,vectors,results,provenance)
            return {'admission_id':identifier,'results':results,'legacy_writes':0}
    except Exception as exc:
        store.failed(identifier,type(exc).__name__)
        raise
    finally:
        if encoder is not None: encoder.close()
