"""Synthetic pilot tests; never uses private sources, model or production DB."""
from copy import deepcopy
from contextlib import contextmanager
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch, MagicMock
from uuid import uuid4
import psycopg
from psycopg.rows import dict_row
from memorybox.processing import scope, voice_pilot as v, voice_pilot_store as store, voice_pilot_runner as runner
ROOT=Path(__file__).resolve().parents[1]

def fixture():
    person=str(uuid4()); sources=[{'provider_key':'synthetic','video_external_id':f'source-{i}','relative_path':f'{i}.wav','duration_sec':30,'source_sha256':f'{i+1:064x}'} for i in range(22)]
    manifest={'id':'synthetic','version':'1','sources':sources}
    spans=[]
    for i in range(4):
        s=sources[0 if i==0 else 1]
        spans.append({'key':str(i),'role':'training' if i==0 else 'held_out','source_id':s['video_external_id'],'source_sha256':s['source_sha256'],'provider_key':'synthetic','annotation_id':str(uuid4()),'version_id':str(uuid4()),'person_id':person if i!=2 else str(uuid4()),'word_ids':[str(uuid4())],'start':float(i),'end':float(i)+.5})
    return {'purpose':'voice_pilot','scope_kind':'bounded','lanes':['voice'],'person_ids':[person],'manifest':manifest,'parent_manifest_sha256':scope.digest(manifest),'spans':spans,'model':{'format':'torchscript_ecapa_192','sha256':'a'*64,'revision':'synthetic-only'},'thresholds':{'match':.55,'uncertain':.4},**v.LIMITS}

class Pure(unittest.TestCase):
    def test_preview_and_legacy_entry_rejected(self):
        p=fixture();self.assertEqual(scope.preview(p)['work_items'],4)
        a=scope.Admission(str(uuid4()),p,'started',scope.digest(p),start_ref='test')
        with self.assertRaisesRegex(scope.ScopeDenied,'exact_span'):a.check('voice',[],p['person_ids'])
    def test_invalid_plans(self):
        for mutate in [lambda p:p.update(scope_kind='archive'),lambda p:p.update(lanes=['transcribe']),lambda p:p.update(max_work_items=5),lambda p:p.update(max_attempts_per_item=2),lambda p:p['spans'][1].update(role='training'),lambda p:p['spans'][1].update(source_id='foreign'),lambda p:p['spans'][0].update(end=float('nan')),lambda p:p['thresholds'].update(match=.1),lambda p:p['spans'][1].update(word_ids=[]),lambda p:p['spans'][1].update(annotation_id=p['spans'][0]['annotation_id'])]:
            p=fixture();mutate(p)
            with self.assertRaises(scope.ScopeDenied):v.validate(p)
    def test_duplicate_content_overlap_rejected(self):
        p=fixture();p['manifest']['sources'][1]['source_sha256']=p['manifest']['sources'][0]['source_sha256'];p['parent_manifest_sha256']=scope.digest(p['manifest'])
        for s in p['spans'][1:]:s['source_sha256']=p['spans'][0]['source_sha256']
        p['spans'][1].update(start=.1,end=.4)
        with self.assertRaisesRegex(scope.ScopeDenied,'overlap'):v.validate(p)
    def test_scores_and_invalid_vectors(self):
        a=[1.]+[0.]*191;b=[-1.]+[0.]*191
        self.assertEqual(v.score(a,a,{'match':.55,'uncertain':.4})['decision'],'match')
        self.assertEqual(v.score(a,b,{'match':.55,'uncertain':.4})['decision'],'no_match')
        for vec in [[],[0.]*192,[float('nan')]*192,[1.]*193]:
            with self.assertRaises(scope.ScopeDenied):v.vector(vec)
    def test_deadline_and_traversal(self):
        with self.assertRaises(scope.ScopeDenied):runner.remaining(time.monotonic()-1,5)
        with tempfile.TemporaryDirectory() as d:
            p=fixture();f=Path(d)/'model';f.write_bytes(b'test');p['model']['sha256']=runner.sha(f,time.monotonic()+5)
            p['manifest']['sources'][0]['relative_path']='../outside.wav'
            with self.assertRaises((FileNotFoundError,scope.ScopeDenied)):runner.preflight(p,d,f,f,time.monotonic()+5)
    def test_runner_four_spans_one_model_no_legacy_calls(self):
        p=fixture();vec=[1.]+[0.]*191
        with patch.object(store,'load',return_value=p),patch.object(store,'claim'),patch.object(store,'reserve') as reserve,patch.object(store,'publish') as publish,patch.object(store,'failed') as failed,patch.object(runner,'preflight',return_value=({('synthetic',f'source-{i}'):Path('test') for i in (0,1)},Path('model'),Path('ffmpeg'))),patch.object(runner,'sha',return_value='a'*64),patch.object(runner,'extract',return_value={}) as extract,patch.object(runner,'Encoder') as encoder:
            encoder.return_value.embed.return_value=vec
            result=runner.run('test',scope.digest(p),'root','model','ffmpeg')
            self.assertEqual(len(result['results']),3);self.assertEqual(reserve.call_count,4);self.assertEqual(extract.call_count,4);encoder.assert_called_once();publish.assert_called_once();failed.assert_not_called()
    def test_actual_audio_extraction_is_bounded(self):
        import wave, math, array
        ffmpeg=Path('C:/Program Files/Demucs-GUI_1.3.2_cuda_mkl/ffmpeg/ffmpeg.exe')
        if not ffmpeg.exists(): self.skipTest('local FFmpeg absent')
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/'source.wav'; dest=Path(d)/'span.wav'
            with wave.open(str(source),'wb')as f:
                f.setparams((1,2,16000,0,'NONE','not compressed'))
                f.writeframes(array.array('h',(int(3000*math.sin(i*.1)) for i in range(64000))).tobytes())
            before=source.read_bytes()
            result=runner.extract(ffmpeg,source,{'start':1.,'end':1.5},dest,5)
            self.assertAlmostEqual(result['duration_sec'],.5,places=2)
            self.assertEqual(source.read_bytes(),before)
            with self.assertRaises(scope.ScopeDenied):runner.extract(ffmpeg,source,{'start':5.,'end':5.5},Path(d)/'missing.wav',5)
    def test_encoder_timeout_kills_actual_child(self):
        import subprocess, sys
        original=subprocess.Popen; children=[]
        def child(*args, **kwargs):
            process=original([sys.executable,'-B','-c','import time; time.sleep(30)'],**kwargs)
            children.append(process); return process
        with patch.object(runner.subprocess,'Popen',side_effect=child):
            with self.assertRaisesRegex(scope.ScopeDenied,'timed_out'):
                runner.Encoder('synthetic-model',time.monotonic()+.1)
        self.assertIsNotNone(children[0].poll())

    def test_wrong_model_hash_fails_before_source_access(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'model';f.write_bytes(b'test')
            with self.assertRaisesRegex(scope.ScopeDenied,'model_changed'):runner.preflight(fixture(),d,f,f,time.monotonic()+5)
    def test_failure_consumes_attempt_and_does_not_publish(self):
        p=fixture()
        with patch.object(store,'load',return_value=p),patch.object(store,'claim') as claim,patch.object(store,'reserve'),patch.object(store,'publish') as publish,patch.object(store,'failed') as failed,patch.object(runner,'preflight',return_value=({('synthetic','source-0'):Path('test')},Path('model'),Path('ffmpeg'))),patch.object(runner,'sha',return_value='a'*64),patch.object(runner,'extract',side_effect=scope.ScopeDenied('bad_audio')):
            with self.assertRaises(scope.ScopeDenied):runner.run('test',scope.digest(p),'root','model','ffmpeg')
            claim.assert_called_once();publish.assert_not_called();failed.assert_called_once()

@unittest.skipUnless(os.environ.get('I13_SYNTHETIC_PG_TEST')=='1','explicit synthetic PostgreSQL only')
class Database(unittest.TestCase):
    def setUp(self):
        self.schema='i13_pilot_'+uuid4().hex;self.dsn='host=127.0.0.1 port=55439 dbname=i13_annotation_test user=i13_test connect_timeout=5';self.plan=fixture();self.identifier=str(uuid4())
        with psycopg.connect(self.dsn,autocommit=True)as c:c.execute('CREATE SCHEMA '+self.schema)
        @contextmanager
        def connection():
            with psycopg.connect(self.dsn,options='-c search_path='+self.schema,row_factory=dict_row)as c:yield c
        self.connection=connection
        self.patches=[patch.object(store,'connection',connection),patch.object(store,'corpus',return_value=self.plan['manifest'])]
        for p in self.patches:p.start()
        with connection()as c:
            c.execute('CREATE TABLE people(id uuid PRIMARY KEY)')
            for pid in {s['person_id']for s in self.plan['spans']}:c.execute('INSERT INTO people VALUES(%s)',(pid,))
            c.execute((ROOT/'memorybox/migrations/013_p2_i9_spoken.sql').read_text())
            c.execute('CREATE TABLE recognition_queue_items(id uuid PRIMARY KEY,status text,priority int,created_at timestamptz)')
            c.execute((ROOT/'memorybox/migrations/030_p2_i13_scope_admission.sql').read_text())
            c.execute((ROOT/'memorybox/migrations/031_p2_i13_transcript_annotations.sql').read_text())
            if getattr(self,'apply_pilot_migration',True): c.execute((ROOT/'memorybox/migrations/032_p2_i13_voice_pilot.sql').read_text())
            # One version per source with the exact immutable words.
            for sid in ('source-0','source-1'):
                spans=[s for s in self.plan['spans']if s['source_id']==sid];version=spans[0]['version_id']
                words=[{'id':s['word_ids'][0],'t_start':s['start'],'t_end':s['end'],'token':'synthetic'}for s in spans]
                for s in spans:s['version_id']=version
                c.execute("INSERT INTO i13_transcript_versions(id,provider_key,source_id,machine) VALUES(%s,'synthetic',%s,%s::jsonb)",(version,sid,json.dumps({'words':words,'moments':[],'turns':[]})))
            for s in self.plan['spans']:
                c.execute("""INSERT INTO i13_transcript_annotations(id,version_id,word_ids,t_start,t_end,action,speaker_state,person_id,actor_id,reason,request_id,request_digest)
                VALUES(%s,%s,%s::uuid[],%s,%s,'assign','person',%s,%s,'synthetic',%s,'test')""",(s['annotation_id'],s['version_id'],s['word_ids'],s['start'],s['end'],s['person_id'],s['person_id'],str(uuid4())))
            c.execute("INSERT INTO i13_processing_admissions(id,plan_json,plan_sha256,review_ref,state,start_ref) VALUES(%s,%s::jsonb,%s,'synthetic','started','test')",(self.identifier,json.dumps(self.plan),scope.digest(self.plan)))
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        with psycopg.connect(self.dsn,autocommit=True)as c:c.execute('DROP SCHEMA '+self.schema+' CASCADE')
    def test_single_use_stop_and_off_span(self):
        store.claim(self.identifier)
        with self.assertRaises(scope.ScopeDenied):store.claim(self.identifier)
        with self.assertRaises(scope.ScopeDenied):store.reserve(self.identifier,'other')
        store.reserve(self.identifier,'0')
        with self.assertRaises(scope.ScopeDenied):store.reserve(self.identifier,'0')
        with self.connection()as c:c.execute("UPDATE i13_processing_admissions SET state='stopped' WHERE id=%s",(self.identifier,))
        with self.assertRaises(scope.ScopeDenied):store.reserve(self.identifier,'1')
    def test_retirement_preserves_results_and_blocks_future_work(self):
        store.claim(self.identifier)
        for s in self.plan['spans']:store.reserve(self.identifier,s['key'])
        store.publish(self.identifier,[[1.]+[0.]*191]*4,[{'key':s['key']}for s in self.plan['spans'][1:]],{})
        with self.connection()as c:self.assertFalse(c.execute('SELECT stale FROM i13_voice_pilot_results').fetchone()['stale'])
        store.retire(self.plan['spans'][0]['annotation_id'],'synthetic retirement')
        with self.connection()as c:
            self.assertTrue(c.execute('SELECT stale FROM i13_voice_pilot_results').fetchone()['stale'])
            self.assertEqual(c.execute('SELECT count(*) n FROM speech_voice_exemplars').fetchone()['n'],0)
            self.assertEqual(c.execute('SELECT count(*) n FROM speech_queue_items').fetchone()['n'],0)
        with self.assertRaises(scope.ScopeDenied):store.load(self.identifier)
        with self.connection()as c:
            with self.assertRaises(psycopg.Error):c.execute('DELETE FROM i13_voice_pilot_events')
    def test_retirement_before_publication_blocks_results(self):
        store.claim(self.identifier)
        for s in self.plan['spans']:store.reserve(self.identifier,s['key'])
        store.retire(self.plan['spans'][0]['annotation_id'],'synthetic retirement')
        with self.assertRaises(scope.ScopeDenied):store.publish(self.identifier,[[]]*4,[{}]*3,{})
        with self.connection()as c:self.assertEqual(c.execute('SELECT count(*) n FROM i13_voice_pilot_events').fetchone()['n'],0)

    def test_annotation_revision_invalidates_held_out_result(self):
        store.claim(self.identifier)
        for s in self.plan['spans']:store.reserve(self.identifier,s['key'])
        store.publish(self.identifier,[[1.]+[0.]*191]*4,[{}]*3,{})
        span=self.plan['spans'][1]
        with self.connection() as c:
            c.execute("""INSERT INTO i13_transcript_annotations(version_id,word_ids,t_start,t_end,action,speaker_state,person_id,actor_id,reason,supersedes,request_id,request_digest)
            SELECT version_id,word_ids,t_start,t_end,action,speaker_state,person_id,actor_id,'synthetic revision',id,%s,'test' FROM i13_transcript_annotations WHERE id=%s""",(str(uuid4()),span['annotation_id']))
        with self.assertRaisesRegex(scope.ScopeDenied,'annotation_changed'):store.load(self.identifier)
        with self.connection()as c:self.assertTrue(c.execute('SELECT stale FROM i13_voice_pilot_results').fetchone()['stale'])
    def test_stop_serializes_with_publication_check(self):
        with self.connection()as held:
            store.checked(held,self.identifier)
            with self.connection()as other:
                other.execute("SET LOCAL lock_timeout='100ms'")
                with self.assertRaises(psycopg.errors.LockNotAvailable):other.execute("UPDATE i13_processing_admissions SET state='stopped' WHERE id=%s",(self.identifier,))
        with self.connection()as c:c.execute("UPDATE i13_processing_admissions SET state='stopped' WHERE id=%s",(self.identifier,))
        with self.assertRaises(scope.ScopeDenied):store.load(self.identifier)
