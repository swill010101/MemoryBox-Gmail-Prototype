import importlib.util
import os
from pathlib import Path
import unittest
from uuid import uuid4
from test_i13_voice_pilot import Database,ROOT
spec=importlib.util.spec_from_file_location('rehearsal',ROOT/'docs/implementation/p2-i13-stage-a/rehearse-voice-pg16.py')
rehearsal=importlib.util.module_from_spec(spec);spec.loader.exec_module(rehearsal)

class Guards(unittest.TestCase):
    def test_only_generated_clone_names(self):
        rehearsal.guard('mb_i13_pre032_restore_'+uuid4().hex)
        for value in ['memorybox','postgres','mb_i13_pre032_restore_',"mb_i13_pre032_restore_"+'g'*32]:
            with self.assertRaises(ValueError):rehearsal.guard(value)

@unittest.skipUnless(os.environ.get('I13_SYNTHETIC_PG_TEST')=='1','isolated PostgreSQL only')
class SQLTests(unittest.TestCase):
    def setUp(self):
        self.fixture=Database();self.fixture.apply_pilot_migration=False;self.fixture.setUp()
        with self.fixture.connection() as c:
            c.execute('CREATE TABLE schema_migrations(version text PRIMARY KEY, filename text)')
            c.execute("INSERT INTO schema_migrations VALUES('031','031_p2_i13_transcript_annotations.sql')")
            for t in ('historian_capture_campaigns','historian_capture_items'):c.execute('CREATE TABLE '+t+'(id integer)')
    def tearDown(self):self.fixture.tearDown()
    def sql(self,commit,extra=''):
        clone='mb_i13_pre032_restore_'+uuid4().hex
        migration=(ROOT/'memorybox/migrations/032_p2_i13_voice_pilot.sql').read_text()+extra
        # Exercise the generated migration/fingerprint SQL in our existing synthetic fixture schema.
        return rehearsal.rehearsal_sql(clone,migration,commit).replace(clone,'i13_annotation_test').replace('public',self.fixture.schema)
    def test_rollback_then_commit_preserves_fingerprints(self):
        with self.fixture.connection() as c:
            c.execute(self.sql(False))
            self.assertIsNone(c.execute("SELECT to_regclass('i13_voice_pilot_runs')").fetchone()['to_regclass'])
            c.commit();c.execute(self.sql(True))
            self.assertEqual(c.execute("SELECT filename FROM schema_migrations WHERE version='032'").fetchone()['filename'],'032_p2_i13_voice_pilot.sql')
    def test_existing_data_change_rejected(self):
        import psycopg
        with self.fixture.connection() as c:
            with self.assertRaises(psycopg.Error):c.execute(self.sql(False,'\nINSERT INTO historian_capture_items VALUES(1);'))
            c.rollback()
            self.assertEqual(c.execute('SELECT count(*) n FROM historian_capture_items').fetchone()['n'],0)
