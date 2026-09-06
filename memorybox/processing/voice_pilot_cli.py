"""Operator pilot preparation/check/run. No default processing action."""
import argparse
import json
import time
from pathlib import Path
from memorybox.db import connection
from memorybox.speech.annotations import corpus
from .scope import digest, ScopeDenied
from .voice_pilot import validate, LIMITS

def prepare(selection, model, revision):
    from .voice_pilot_runner import sha
    parent=corpus(); spans=[]
    with connection() as c:
        c.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        for requested in selection['selections']:
            row=c.execute("""SELECT a.*,v.provider_key,v.source_id FROM i13_active_annotations a
            JOIN i13_current_transcripts v ON v.id=a.version_id WHERE a.id=%s::uuid""",(requested['annotation_id'],)).fetchone()
            if not row or str(row['version_id'])!=requested['version_id'] or row['source_id']!=requested['source_id'] or row['t_start']!=requested['start'] or row['t_end']!=requested['end']:
                raise ScopeDenied('selected_annotation_changed')
            spans.append({k:requested[k] for k in ('key','role','source_id','version_id','annotation_id','start','end','provider_key','source_sha256')})
            spans[-1].update(person_id=str(row['person_id']),word_ids=[str(w) for w in row['word_ids']])
    plan={'purpose':'voice_pilot','scope_kind':'bounded','lanes':['voice'],
      'manifest':parent,'parent_manifest_sha256':digest(parent),'person_ids':[selection['target_person_id']],
      'spans':spans,'thresholds':{'match':.55,'uncertain':.40},
      'model':{'format':'torchscript_ecapa_192','sha256':sha(Path(model),time.monotonic()+1200),'revision':revision},**LIMITS}
    validate(plan);return plan

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='action',required=True)
    prep=sub.add_parser('prepare');prep.add_argument('--selection',required=True);prep.add_argument('--model',required=True);prep.add_argument('--revision',required=True);prep.add_argument('--output',required=True)
    for verb in ('check','run'):
        q=sub.add_parser(verb)
        for flag in ('id','expected-plan-sha','media-root','model','ffmpeg'):q.add_argument('--'+flag,required=True)
    q=sub.add_parser('retire');q.add_argument('--annotation-id',required=True);q.add_argument('--reason',required=True)
    a=p.parse_args(argv)
    try:
        if a.action=='prepare':
            plan=prepare(json.loads(Path(a.selection).read_text(encoding='utf-8')),a.model,a.revision)
            with Path(a.output).open('x',encoding='utf-8') as f:json.dump(plan,f,indent=2,allow_nan=False)
            result=validate(plan)
        elif a.action=='retire':
            from .voice_pilot_store import retire
            result=retire(a.annotation_id,a.reason)
        elif a.action=='check':
            from .voice_pilot_runner import preflight
            from .voice_pilot_store import load
            plan=load(a.id)
            if digest(plan)!=a.expected_plan_sha: raise ScopeDenied('pilot_reviewed_plan_hash_mismatch')
            preflight(plan,a.media_root,a.model,a.ffmpeg,time.monotonic()+1200)
            result={'read_only':True,'files_verified':True,'model_execution_verified':False,**validate(plan)}
        else:
            from .voice_pilot_runner import run
            result=run(a.id,a.expected_plan_sha,a.media_root,a.model,a.ffmpeg)
        print(json.dumps(result,indent=2));return 0
    except Exception as exc:
        # Avoid credential/path-bearing native exceptions in operator output.
        print(json.dumps({'ok':False,'error':str(exc) if isinstance(exc,ScopeDenied) else type(exc).__name__}));return 2
if __name__=='__main__':raise SystemExit(main())
