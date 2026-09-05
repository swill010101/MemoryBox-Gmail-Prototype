"""Offline contract tests. Real PostgreSQL integration uses an explicit test flag."""
import os
import json
import unittest
from pathlib import Path
from uuid import uuid4
from contextlib import contextmanager
from unittest.mock import patch
import psycopg
from psycopg.rows import dict_row
from fastapi import FastAPI
from fastapi.testclient import TestClient
from memorybox.speech import annotations as a
from memorybox.speech import store
from memorybox.speech.annotation_api import router

ROOT=Path(__file__).resolve().parents[1]
SOURCE='vid-c57dbd21f993f6d1'
class Contracts(unittest.TestCase):
    def test_selection_rejects_gaps_and_foreign_words(self):
        ids=[str(uuid4()) for _ in range(3)]
        machine={'words':[{'id':x,'t_start':i,'t_end':i+.5} for i,x in enumerate(ids)]}
        self.assertEqual(a.validate_span(machine,ids),(0,2.5))
        for selected in ([ids[0],ids[2]],[ids[0],ids[0]],[str(uuid4())]):
            with self.assertRaises(a.AnnotationError): a.validate_span(machine,selected)
    def test_exact_manifest(self):
        self.assertEqual(len(a.corpus()['sources']),22)
        with self.assertRaises(a.AnnotationError): a.require_member('hvrt','other')
    def test_owner_boundary_rejects_remote_and_cross_origin(self):
        app=FastAPI();app.include_router(router)
        body={'provider_key':'hvrt','source_id':SOURCE,'version_id':str(uuid4()),'expected_head':None,'word_ids':[str(uuid4())],'speaker_state':'unknown','reason':'test','request_id':str(uuid4())}
        for host,headers in [('10.0.0.2',{'X-MB-Annotation':'1'}),('127.0.0.1',{'X-MB-Annotation':'1','Origin':'https://foreign.example'}),('127.0.0.1',{})]:
            client=TestClient(app,base_url='http://127.0.0.1',client=(host,50000))
            with patch.object(a,'save_annotation') as save:
                self.assertEqual(client.post('/annotations/transcript',json=body,headers=headers).status_code,403)
                save.assert_not_called()

@unittest.skipUnless(os.environ.get('I13_SYNTHETIC_PG_TEST')=='1','explicit disposable PostgreSQL test only')
class Database(unittest.TestCase):
    def setUp(self):
        self.schema='i13_test_'+uuid4().hex
        self.dsn='host=127.0.0.1 port=55439 dbname=i13_annotation_test user=i13_test'
        with psycopg.connect(self.dsn,autocommit=True) as c:c.execute('CREATE SCHEMA '+self.schema)
        @contextmanager
        def connection():
            with psycopg.connect(self.dsn,options='-c search_path='+self.schema, row_factory=dict_row) as c:yield c
        self.connection=connection
        self.patches=[patch.object(a,'connection',connection),patch.object(store,'connection',connection)]
        for p in self.patches:p.start()
        self.actor=str(uuid4());self.person=str(uuid4());self.ids=[str(uuid4()) for _ in range(4)]
        with connection() as c:
            c.execute('CREATE TABLE people(id uuid PRIMARY KEY)')
            c.execute('INSERT INTO people VALUES (%s),(%s)',(self.actor,self.person))
            c.execute((ROOT/'memorybox/migrations/013_p2_i9_spoken.sql').read_text())
            for i,x in enumerate(self.ids):c.execute("INSERT INTO speech_transcript_words(id,video_provider_key,video_external_id,t_start,t_end,token,model_version) VALUES (%s,'hvrt',%s,%s,%s,%s,'synthetic')",(x,SOURCE,i,i+.5,['old','sample','three','four'][i]))
            c.execute((ROOT/'memorybox/migrations/031_p2_i13_transcript_annotations.sql').read_text())
        self.v=a.transcript('hvrt',SOURCE)['version_id']
    def tearDown(self):
        for p in self.patches:p.stop()
        # Keep synthetic schema evidence until the private cluster is stopped.
    def payload(self,**changes):
        d={'version_id':self.v,'expected_head':None,'word_ids':self.ids[:2],'speaker_state':'person','person_id':self.person,'correction':'corrected phrase','action':'assign','reason':'synthetic owner review','supersedes':None,'request_id':str(uuid4())}
        d.update(changes);return d
    def save(self,d):return a.save_annotation('hvrt',SOURCE,self.actor,d)
    def test_save_display_search_and_no_processing(self):
        self.save(self.payload())
        tr=a.transcript('hvrt',SOURCE)
        self.assertEqual([w['token'] for w in tr['words']],['corrected phrase','','three','four'])
        self.assertEqual(tr['machine']['words'][0]['token'],'old')
        with self.connection() as c:
            found=c.execute("SELECT * FROM i13_effective_moments WHERE text ILIKE %s AND person_id=%s",('%corrected phrase%',self.person,)).fetchall()
            self.assertEqual(len(found),1)
            for t in ['speech_queue_items','speech_voice_exemplars','speech_processing_runs']:
                self.assertEqual(c.execute('SELECT count(*) AS n FROM '+t).fetchone()['n'],0)
    def test_revision_withdrawal_and_history(self):
        first=self.save(self.payload())['annotation']['id']
        second=self.save(self.payload(expected_head=first,supersedes=first,speaker_state='unknown',person_id=None))['annotation']['id']
        self.assertEqual(a.transcript('hvrt',SOURCE)['words'][0]['speaker_state'],'unknown')
        self.save(self.payload(expected_head=second,supersedes=second,action='withdraw'))
        tr=a.transcript('hvrt',SOURCE)
        self.assertEqual(tr['words'][0]['token'],'old');self.assertEqual(len(tr['history']),3)
    def test_idempotency_and_stale_overlap(self):
        body=self.payload();first=self.save(body)
        self.assertTrue(self.save(body)['replayed'])
        for body in [self.payload(),self.payload(expected_head=first['annotation']['id'],word_ids=self.ids[1:3]),self.payload(request_id=body['request_id'],correction='different')]:
            with self.assertRaises(a.AnnotationError):self.save(body)
    def test_invalid_person_words_and_version(self):
        for b in [self.payload(person_id=str(uuid4())),self.payload(word_ids=[str(uuid4())]),self.payload(version_id=str(uuid4()))]:
            with self.assertRaises(a.AnnotationError):self.save(b)
    def test_append_new_version_preserves_and_stales(self):
        self.save(self.payload())
        run=store.start_run(video_provider_key='hvrt',video_external_id=SOURCE,run_kind='transcribe')
        store.replace_video_transcript(video_provider_key='hvrt',video_external_id=SOURCE,run_id=run,words=[{'token':'new','t_start':0,'t_end':1}],turns=[],moments=[])
        tr=a.transcript('hvrt',SOURCE)
        self.assertNotEqual(tr['version_id'],self.v);self.assertTrue(tr['history'][0]['stale'])
        self.assertEqual(tr['words'][0]['token'],'new')
        with self.connection() as c:self.assertEqual(c.execute('SELECT count(*) AS n FROM speech_transcript_words').fetchone()['n'],5)
        with self.assertRaises(ValueError):store.replace_video_transcript(video_provider_key='hvrt',video_external_id=SOURCE,run_id=run,words=[],turns=[],moments=[])
    def test_concurrent_saves_conflict_without_duplicate_overlays(self):
        from concurrent.futures import ThreadPoolExecutor
        def save_once(_):
            try:self.save(self.payload());return 'saved'
            except a.AnnotationError:return 'conflict'
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(save_once,range(2))),['conflict','saved'])
        self.assertEqual(len(a.transcript('hvrt',SOURCE)['history']),1)
    def test_no_match_and_unselected_words(self):
        self.save(self.payload(speaker_state='no_match',person_id=None,correction=None))
        words=a.transcript('hvrt',SOURCE)['words']
        self.assertEqual(words[0]['speaker_state'],'no_match')
        self.assertEqual(words[2]['speaker_state'],'anonymous')
        self.assertIsNone(words[2]['annotation_id'])
    def test_raw_coverage_inventory_is_read_only_and_exact(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('coverage_inventory',ROOT/'docs/implementation/p2-i13-stage-a/inventory-transcript-coverage.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with psycopg.connect(self.dsn,options='-c search_path='+self.schema) as c:
            c.execute('SET TRANSACTION READ ONLY')
            data=module.inventory(c,a.corpus())
        self.assertTrue(data['read_only']);self.assertEqual(len(data['sources']),22)
        self.assertEqual(next(x['stored_word_rows'] for x in data['sources'] if x['source_id']==SOURCE),4)
    def test_immutable_database_guards(self):
        self.save(self.payload())
        for table in ['speech_transcript_words','i13_transcript_versions','i13_transcript_annotations']:
            with self.assertRaises(psycopg.Error):
                with self.connection() as c:c.execute('DELETE FROM '+table)
    def test_coverage_honest_and_off_manifest(self):
        self.save(self.payload())
        data=a.export_coverage();self.assertEqual(len(data['sources']),22)
        source=next(s for s in data['sources'] if s['source_id']==SOURCE)
        self.assertEqual(source['reviewed_words'],2);self.assertEqual(source['unreviewed_words'],2)
        self.assertFalse(source['coverage_review_complete'])
        with self.assertRaises(a.AnnotationError):a.save_annotation('hvrt','unapproved',self.actor,self.payload())
    def test_api_persists_with_server_owner(self):
        app=FastAPI();app.include_router(router)
        client=TestClient(app,base_url='http://127.0.0.1',client=('127.0.0.1',50000))
        with patch('memorybox.profile.owner.get_owner_person_id',return_value=self.actor):
            r=client.post('/annotations/transcript',json=dict(self.payload(),provider_key='hvrt',source_id=SOURCE),headers={'X-MB-Annotation':'1'})
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['annotation']['actor_id'],self.actor)
if __name__=='__main__':unittest.main()
