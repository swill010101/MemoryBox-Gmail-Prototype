"""Offline Stage A tests: synthetic plans and doubles, no runtime/model access."""
from __future__ import annotations
import ast
from contextlib import contextmanager
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import types
import unittest
from unittest.mock import patch
from uuid import UUID

from memorybox.processing import scope, control
ROOT=Path(__file__).resolve().parents[1]
PERSON="00000000-0000-4000-8000-000000000001"
ADMISSION="00000000-0000-4000-8000-000000000002"

def plan():
    return {"scope_kind":"bounded","manifest":{"id":"synthetic-test-only","version":"1","sources":[
        {"provider_key":"synthetic","video_external_id":f"video-{i}","source_sha256":f"{i:064x}","duration_sec":60,
         "owner_confirmed":True,"owner_truth_ref":"synthetic test fixture, not real owner truth",
         "coverage_tags":sorted(scope.COVERAGE),"truth":[{"modality":"face","person_id":PERSON,"start_sec":1,"end_sec":2}]}
        for i in range(22)]},"person_ids":[PERSON],"lanes":["face","voice","transcribe"],"max_work_items":66,"max_attempts_per_item":2}

def admission(p=None,state="started",**kw):
    p=p or plan()
    return scope.Admission(ADMISSION,p,state,scope.digest(p),start_ref="synthetic start" if state=="started" else None,**kw)

def function(path,name,env=None):
    """Load the complete actual function without module-level provider/DB imports."""
    tree=ast.parse((ROOT/path).read_text(encoding="utf-8"))
    node=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name==name)
    ns=dict(env or {})
    body=[ast.ImportFrom(module="__future__",names=[ast.alias(name="annotations")],level=0),node]
    exec(compile(ast.fix_missing_locations(ast.Module(body=body,type_ignores=[])),str(path),"exec"),ns)
    return ns[name]

class ScopeTests(unittest.TestCase):
    def test_whole_workload_preview(self):
        self.assertEqual(scope.preview(plan())["work_items"],66)
        p=plan();p["person_ids"]=[str(UUID(int=i+1)) for i in range(80)]
        with self.assertRaisesRegex(scope.ScopeDenied,"workload_limit"):scope.preview(p)
    def test_exact_corpus_not_nineteen(self):
        p=plan();p["manifest"]["sources"]=p["manifest"]["sources"][:19]
        with self.assertRaisesRegex(scope.ScopeDenied,"exactly_22"):scope.preview(p)
    def test_truth_fingerprint_coverage_and_times_required(self):
        for field,value in [("owner_confirmed",False),("source_sha256","unknown"),("duration_sec",float("nan")),("truth",[])]:
            p=plan();p["manifest"]["sources"][0][field]=value
            with self.subTest(field=field),self.assertRaises(scope.ScopeDenied):scope.preview(p)
        p=plan();p["manifest"]["sources"][0]["truth"][0]["end_sec"]=61
        with self.assertRaises(scope.ScopeDenied):scope.preview(p)
        p=plan()
        for s in p["manifest"]["sources"]:s["coverage_tags"]=[]
        with self.assertRaisesRegex(scope.ScopeDenied,"coverage"):scope.preview(p)
    def test_duplicate_and_wildcard_sources_rejected(self):
        p=plan();p["manifest"]["sources"][1]=deepcopy(p["manifest"]["sources"][0])
        with self.assertRaises(scope.ScopeDenied):scope.preview(p)
        p=plan();p["manifest"]["sources"][0]["video_external_id"]="*"
        with self.assertRaises(scope.ScopeDenied):scope.preview(p)
    def test_off_manifest_and_wrong_person(self):
        a=admission()
        a.check("face",a.videos,[PERSON])
        for rows,people in [([{"video_provider_key":"other","video_external_id":"video-0"}],[PERSON]),(a.videos,[str(UUID(int=55))]),([a.videos[0],a.videos[0]],[PERSON])]:
            with self.assertRaises(scope.ScopeDenied):a.check("face",rows,people)
    def test_registered_unlocked_stopped_do_not_admit_work(self):
        for state in ["registered","unlocked","stopped"]:
            with self.subTest(state=state),self.assertRaises(scope.ScopeDenied):admission(state=state).check("face",[],[PERSON])
    def test_archive_requires_acceptance_unlock_and_start(self):
        p=plan();p["scope_kind"]="archive"
        with self.assertRaisesRegex(scope.ScopeDenied,"archive_locked"):admission(p).check("face",[],[PERSON])
        admission(p,acceptance_ref="accepted",unlock_ref="unlocked").check("face",[],[PERSON])
        with patch.object(scope,"load_admission",return_value=admission()):
            with self.assertRaisesRegex(scope.ScopeDenied,"archive_locked"):scope.require_admission("face",archive=True)
    def test_plan_changes_invalidate_grant(self):
        a=admission();a.plan["max_attempts_per_item"]=3
        with self.assertRaisesRegex(scope.ScopeDenied,"plan_changed"):a.check("face",[],[PERSON])
    def test_missing_admission_never_opens_database(self):
        with patch.dict(os.environ,{"MEMORYBOX_I13_ADMISSION_ID":""}):
            with self.assertRaisesRegex(scope.ScopeDenied,"no_admission"):scope.load_admission()
    def test_queue_reason_cannot_multiply_units(self):
        a=admission();c=FakeConnection(a)
        scope.reserve_queue_item(c,a,"face",a.videos[0],PERSON,"owner_learn")
        scope.reserve_queue_item(c,a,"face",a.videos[0],PERSON,"owner_learn")
        with self.assertRaisesRegex(scope.ScopeDenied,"another_reason"):
            scope.reserve_queue_item(c,a,"face",a.videos[0],PERSON,"new_video")
        self.assertEqual(len(c.units),1)
    def test_attempt_cap_shared_across_entrypoints(self):
        a=admission();c=FakeConnection(a)
        with fake_db(c),patch.object(scope,"load_admission",return_value=a):
            scope.begin_work("face","synthetic","video-0",PERSON)
            scope.begin_work("face","synthetic","video-0",PERSON)
            with self.assertRaisesRegex(scope.ScopeDenied,"attempt_limit"):
                scope.begin_work("face","synthetic","video-0",PERSON)
            self.assertEqual(c.attempts[('face','synthetic','video-0',PERSON)],2)

class Result:
    def __init__(self,row=None,rows=None):self.row=row;self.rows=rows or []
    def fetchone(self):return self.row
    def fetchall(self):return self.rows

class FakeConnection:
    def __init__(self,a):
        self.row={"id":a.id,"plan_json":a.plan,"plan_sha256":a.plan_sha256,"state":a.state,"acceptance_ref":a.acceptance_ref,"unlock_ref":a.unlock_ref,"start_ref":a.start_ref}
        self.units={};self.attempts={};self.calls=[]
    def execute(self,sql,args=()):
        self.calls.append((sql,args))
        if sql.count("%s")!=len(args):raise AssertionError("SQL parameter mismatch")
        if sql.startswith("SELECT") and "i13_processing_admissions" in sql:return Result(self.row.copy())
        if sql.startswith("INSERT INTO i13_queue_units"):
            key=tuple(args[1:5]);self.units.setdefault(key,args[5]);return Result({"enqueue_reason":self.units[key]})
        if sql.startswith("INSERT INTO i13_work_attempts"):
            key=tuple(args[1:5]);n=self.attempts.get(key,0)
            if n>=args[5]:return Result()
            self.attempts[key]=n+1;return Result({"attempts":n+1})
        if sql.startswith("UPDATE i13_processing_admissions"):
            if "state='unlocked'" in sql:self.row.update(state="unlocked",acceptance_ref=args[0],unlock_ref=args[1])
            elif "state='started'" in sql:self.row.update(state="started",start_ref=args[0])
            elif "state='stopped'" in sql:self.row.update(state="stopped")
            return Result()
        if sql.startswith("INSERT INTO i13_admission_events"):return Result()
        raise AssertionError("Unexpected database operation: "+sql)

@contextmanager
def fake_db(c):
    mod=types.ModuleType("memorybox.db")
    @contextmanager
    def connection():yield c
    mod.connection=connection
    with patch.dict(sys.modules,{"memorybox.db":mod}):yield

class ReleaseTests(unittest.TestCase):
    def test_unlock_does_not_start_or_enqueue(self):
        p=plan();p["scope_kind"]="archive";c=FakeConnection(admission(p,state="registered"))
        with fake_db(c):
            with self.assertRaises(scope.ScopeDenied):control.transition(ADMISSION,"start","start review")
            r=control.transition(ADMISSION,"unlock","unlock review","bounded acceptance")
            self.assertEqual(c.row["state"],"unlocked");self.assertEqual(r["enqueued"],0)
            self.assertIsNone(c.row["start_ref"])
            r=control.transition(ADMISSION,"start","separate start review")
            self.assertEqual(c.row["state"],"started");self.assertEqual(r["enqueued"],0)
            self.assertFalse(r["workers_launched"])
            with self.assertRaises(scope.ScopeDenied):control.transition(ADMISSION,"start","again")
            control.transition(ADMISSION,"stop","stop review")
            self.assertEqual(c.row["state"],"stopped")

class EntryTests(unittest.TestCase):
    def test_native_denials_before_any_side_effect(self):
        cases=[
            ('recognition/queue.py','enqueue_full_eligible_archive',dict(person_id=PERSON,videos=[])),
            ('speech/queue.py','enqueue_videos',dict(videos=[])),
            ('recognition/queue.py','claim_next_item',{}),
            ('speech/queue.py','claim_next_item',{}),
            ('recognition/queue.py','retry_failed_items',{}),
            ('recognition/scan.py','scan_video_for_person',dict(person_id=PERSON,video_provider=object(),video_external_id='video-0')),
            ('recognition/learn.py','owner_learn_from_review',dict(person_id=PERSON,face_external_id='face',video_provider=object(),video_external_id='video-0')),
            ('speech/learn.py','owner_learn_voice',dict(person_id=PERSON,video_external_id='video-0',t_start=1,t_end=2,video_provider=object())),
            ('speech/process.py','persist_transcript',dict(video_provider_key='synthetic',video_external_id='video-0')),
            ('speech/process.py','recognize_person_on_video',dict(person_id=PERSON,video_provider_key='synthetic',video_external_id='video-0')),
            ('speech/now.py','start_transcribe_now',dict(video_external_id='video-0',video_provider=object(),video_provider_key='synthetic')),
            ('recognition/archive_pass.py','enqueue_known_people_archive',dict(video_provider=object(),full=True)),
            ('speech/archive_pass.py','enqueue_new_videos_for_transcribe',dict(video_provider=object())),
        ]
        with patch.dict(os.environ,{"MEMORYBOX_I13_ADMISSION_ID":""}):
            for path,name,args in cases:
                with self.subTest(path=path,name=name),self.assertRaises(scope.ScopeDenied):function('memorybox/'+path,name)(**args)
    def test_archive_fanout_is_limited_to_reviewed_plan(self):
        a=admission();captured=[]
        def enqueue(**kw):captured.append(kw);return {}
        fn=function('memorybox/recognition/archive_pass.py','enqueue_known_people_archive',{'enqueue_full_eligible_archive':enqueue})
        with patch.object(scope,'load_admission',return_value=a):
            result=fn(video_provider=object())
            self.assertEqual(result['video_count'],22);self.assertEqual(len(captured),1)
            self.assertEqual(captured[0]['person_id'],PERSON)
            with self.assertRaises(scope.ScopeDenied):fn(video_provider=object(),full=True)
    def test_active_admission_rejects_off_manifest_batch_before_queue_write(self):
        a=admission()
        with patch.object(scope,"load_admission",return_value=a):
            for module,name,kwargs in [
                ("recognition/queue.py","enqueue_full_eligible_archive",{"person_id":PERSON}),
                ("speech/queue.py","enqueue_videos",{}),
            ]:
                fn=function("memorybox/"+module,name)
                with self.subTest(module=module),self.assertRaisesRegex(scope.ScopeDenied,"off_manifest"):
                    fn(videos=[a.videos[0],{"video_provider_key":"synthetic","video_external_id":"outside"}],**kwargs)
    def test_claim_leaves_legacy_rows_untouched_and_rejects_bad_stamped_row(self):
        a=admission()
        class Claims(FakeConnection):
            def __init__(self,a,bad=False):super().__init__(a);self.bad=bad;self.updates=0
            def execute(self,sql,args=()):
                if "FROM recognition_queue_items" in sql:
                    assert "i13_admission_id=%s::uuid" in sql and args[0]==ADMISSION
                    if self.bad:return Result({"id":str(UUID(int=77)),"person_id":PERSON,"video_provider_key":"synthetic","video_external_id":"outside"})
                    return Result() # legacy NULL-stamped rows do not match
                if sql.startswith("UPDATE recognition_queue_items"):self.updates+=1;return Result()
                return super().execute(sql,args)
        for bad in [False,True]:
            c=Claims(a,bad)
            @contextmanager
            def connection():yield c
            fn=function("memorybox/recognition/queue.py","claim_next_item",{"connection":connection})
            with patch.object(scope,"load_admission",return_value=a):
                if bad:
                    with self.assertRaises(scope.ScopeDenied):fn()
                else:self.assertIsNone(fn())
            self.assertEqual(c.updates,0)
    def test_legacy_manager_and_model_entries_are_closed(self):
        for path,name,args in [
            ("hvrt/hvrt/learning.py","start",{"self":object()}),
            ("hvrt/hvrt/process_jobs.py","start",{"self":object()}),
            ("hvrt/hvrt/face_learn.py","rescan_faces",{"conn":object(),"gallery_dirs":[],"working_dir":Path("unused")}),
            ("hvrt/hvrt/voice_learn.py","recognize_voices",{"conn":object(),"working_dir":Path("unused")}),
        ]:
            with self.subTest(path=path),self.assertRaisesRegex(scope.ScopeDenied,"legacy_processing"):
                function(path,name)(**args)
    def test_cli_denies_without_provider_imports(self):
        env=dict(os.environ,MEMORYBOX_I13_ADMISSION_ID='',PYTHONDONTWRITEBYTECODE='1')
        for command in ['recognition-archive-pass','speech-archive-pass']:
            r=subprocess.run([sys.executable,'-B','-m','memorybox',command],cwd=ROOT,env=env,capture_output=True,text=True)
            self.assertEqual(r.returncode,2,r.stderr);self.assertIn('no_admission',r.stdout)
    def test_drains_do_not_start_when_locked(self):
        with patch.dict(os.environ,{"MEMORYBOX_I13_ADMISSION_ID":""}):
            for module,fn in [('recognition/drain.py','start_recognition_drain'),('speech/drain.py','start_speech_drain')]:
                self.assertIsNone(function('memorybox/'+module,fn)())

class HttpTests(unittest.TestCase):
    def test_api_locked_and_read_navigation_unchanged(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from memorybox.processing.http import enforce_scope
        app=FastAPI();app.middleware('http')(enforce_scope)
        calls=[]
        @app.post('/recognition/archive-pass')
        def run():calls.append('run');return {'ok':True}
        @app.get('/historian-capture/ui')
        def hc():return {'preserved':True}
        with patch.dict(os.environ,{'MEMORYBOX_I13_ADMISSION_ID':''}),TestClient(app) as c:
            r=c.post('/recognition/archive-pass?full=true');self.assertEqual(r.status_code,403)
            self.assertEqual(c.post('/people/sync/immich').status_code,403)
            self.assertEqual(calls,[]);self.assertEqual(c.get('/historian-capture/ui').status_code,200)

class PlaybackTests(unittest.TestCase):
    def test_real_binder_seeks_and_never_clamps_or_restarts(self):
        js=(ROOT/'memorybox/explore/static/explore.js').read_text(encoding='utf-8')
        code=js[js.index('  function appearanceViewBounds('):js.index('  function bindExploreVideoPlayer(')]
        code+="""
const handlers={};const el={currentTime:0,pauses:0,addEventListener(k,f){handlers[k]=f;},removeEventListener(k){delete handlers[k];},pause(){this.pauses++;}};
bindAppearanceView(el,{start_sec:12,end_sec:14});const initial=el.currentTime;
handlers.loadedmetadata();el.currentTime=25;
for(const k of ['timeupdate','seeking','seeked','play'])if(handlers[k])handlers[k]();
console.log(JSON.stringify({initial,current:el.currentTime,pauses:el.pauses}));
"""
        r=subprocess.run(['node','-e',code],capture_output=True,text=True,check=True)
        self.assertEqual(json.loads(r.stdout),{'initial':12,'current':25,'pauses':0})
    def test_gallery_context_functions_preserved(self):
        path='memorybox/explore/static/explore.js'
        original=subprocess.check_output(['git','show','bc2b967274d51ffce356a12895df2cd8f77d73b0:'+path],cwd=ROOT).decode('utf-8')
        changed=(ROOT/path).read_text(encoding='utf-8')
        for name in ['openModal','closeModal']:
            def segment(text):
                a=text.index('  function '+name+'(');b=text.index('\n  function ',a+1);return text[a:b]
            self.assertEqual(segment(original),segment(changed))

if __name__=='__main__':unittest.main(verbosity=2)
