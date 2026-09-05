"""Offline behavioral tests: no live DB/provider, media or recognition invocation."""
import copy
import unittest
import sys
from types import SimpleNamespace
from unittest.mock import patch
from test_i13_fragment_trace import pure
from memorybox.recognition.source_moments import PILOT_SOURCE, PILOT_RUN, SECOND_SOURCE, SECOND_RUN, project_source_cards
from memorybox.explore.find import items_from_ask_result
from memorybox.ask.retrieve import VideoHit, _dedupe_video_hits


def observation(t, **extra):
    return dict(id=str(t), t_sec=t, person_id="person-a", review_state="assigned", match_score=.7, sample_interval_sec=10, **extra)


def hit(t, **extra):
    row = dict(provider_key="hvrt", external_id="moment-"+str(t), video_external_id=PILOT_SOURCE,
               start_sec=t, end_sec=t+.5, mb_person_id="person-a", mb_person_name="Sample Person",
               appearance_evidence=dict(id="moment-"+str(t), processing_run_id=PILOT_RUN,
                   observation_ids=["observation-"+str(t)], method="mb_native_i8b", authority="ai_inferred",
                   confirmation_state="system_associated", status="accepted", model_version="sample-model"))
    row.update(extra)
    return row


class CadenceTests(unittest.TestCase):
    def setUp(self):
        self.group = pure("memorybox/recognition/observations.py", "group_assigned_into_ranges")

    def test_recorded_cadence_groups_but_missing_sample_splits(self):
        rows=[observation(t) for t in [0.5,10.5,20.5,40.5,50.5]]
        before=copy.deepcopy(rows)
        ranges=self.group(rows)
        self.assertEqual([(r["start_sec"],r["end_sec"]) for r in ranges],[(.5,20.5),(40.5,50.5)])
        self.assertEqual(sum(len(r["observation_ids"]) for r in ranges),5)
        self.assertEqual(rows,before)

    def test_uncertain_and_withdrawn_intervals_block_join(self):
        rows=[observation(.5),observation(10.5)]
        self.assertEqual(len(self.group(rows,barriers=[dict(start_sec=3,end_sec=4)])),2)
        for state in ["uncertain","no_match","withdrawn"]:
            with self.subTest(state=state):
                self.assertEqual(len(self.group(rows+[dict(t_sec=5,person_id=None,review_state=state)])),2)

    def test_partition_changes_never_join(self):
        for field in ["person_id","video_provider_key","video_external_id","processing_run_id","embedding_model"]:
            rows=[observation(.5),observation(10.5)]
            rows[1][field]="different"
            self.assertEqual(len(self.group(rows)),2,field)

    def test_actual_frame_collector_carries_planned_cadence(self):
        collect=pure("memorybox/recognition/frames.py", "sample_faces_from_path")
        sample=pure("memorybox/recognition/frames.py", "sample_times")
        face=SimpleNamespace(embedding=[1.0],bbox=[0,0,1,1])
        cap=SimpleNamespace(isOpened=lambda:True,get=lambda prop:30, set=lambda *a:None,
                            read=lambda:(True,object()),release=lambda:None)
        cv2=SimpleNamespace(VideoCapture=lambda path:cap,CAP_PROP_FPS=1,CAP_PROP_FRAME_COUNT=2,CAP_PROP_POS_MSEC=3)
        collect.__globals__.update(insightface_available=lambda:True,sample_times=sample,
                                   _face_app=lambda:SimpleNamespace(get=lambda frame:[face]))
        with patch.dict(sys.modules,{"cv2":cv2}):
            samples=collect("synthetic-only",duration_sec=1105.104)
        self.assertEqual(len(samples),80)
        self.assertEqual({s["sample_interval_sec"] for s in samples},{10.0})
        rows=[dict(id=str(i),person_id="a",review_state="assigned",match_score=.9,**s)
              for i,s in enumerate(samples)]
        ranges=self.group(rows)
        self.assertEqual(len(ranges),1)
        self.assertEqual(ranges[0]["end_sec"],790.5) # no extrapolation to source end

    def test_unknown_legacy_cadence_not_inferred(self):
        rows=[observation(.5),observation(10.5)]
        for r in rows:r.pop("sample_interval_sec")
        self.assertEqual(len(self.group(rows)),2)


class GalleryTests(unittest.TestCase):
    def items(self, hits):
        return items_from_ask_result(dict(video_hits=hits))

    def test_one_source_card_retains_each_query_moment_and_lineage(self):
        hits=[hit(t) for t in [.5,10.5,20.5,30.5,40.5,60.5,70.5]]
        before=copy.deepcopy(hits)
        items=self.items(hits)
        self.assertEqual(len(items),1)
        self.assertEqual(items[0]["video_external_id"],PILOT_SOURCE)
        self.assertEqual(len(items[0]["source_moments"]),7)
        self.assertEqual([m["start_sec"] for m in items[0]["source_moments"]],[.5,10.5,20.5,30.5,40.5,60.5,70.5])
        self.assertEqual(items[0]["end_sec"],1)  # no fabricated continuous presence
        self.assertIsNone(items[0]["duration_sec"])
        self.assertEqual(hits,before)
        for m,h in zip(items[0]["source_moments"],hits):
            self.assertEqual(m["appearance_evidence"],h["appearance_evidence"])
        self.assertEqual(project_source_cards(items),items) # no nested regrouping

    def test_query_subset_not_expanded(self):
        items=self.items([hit(60.5),hit(70.5)])
        self.assertEqual(len(items),1)
        self.assertEqual(items[0]["start_sec"],60.5)
        self.assertEqual(len(items[0]["source_moments"]),2)
        self.assertIn("t=60.500",items[0]["play_url"])

    def test_other_source_speech_unknown_and_owner_evidence_not_projected(self):
        for change in [dict(video_external_id="another"),dict(spoken_text="Selected speech"),dict(appearance_evidence=None)]:
            items=self.items([hit(.5,**change),hit(20.5,**change)])
            self.assertTrue(all("source_moments" not in i for i in items))
        for field,value in [("authority","owner_confirmed"),("status","withdrawn"),("processing_run_id","different")]:
            h=hit(.5);h["appearance_evidence"][field]=value
            self.assertNotIn("source_moments",self.items([h])[0])

    def test_different_people_and_models_remain_separate(self):
        h=hit(10.5,mb_person_id="person-b")
        self.assertEqual(len(self.items([hit(.5),h])),2)
        h=hit(10.5);h["appearance_evidence"]["model_version"]="other"
        self.assertEqual(len(self.items([hit(.5),h])),2)

    def test_two_sources_retain_fifteen_points_in_two_cards(self):
        first=[hit(t) for t in [.5,10.5,20.5,30.5,40.5,60.5,70.5]]
        second=[hit(i*10+.5,video_external_id=SECOND_SOURCE,external_id="second-"+str(i)) for i in range(8)]
        for row in second:
            row["appearance_evidence"]["processing_run_id"]=SECOND_RUN
            row["appearance_evidence"]["id"]=row["external_id"]
        incoming=first+second
        before=copy.deepcopy(incoming)
        items=self.items(incoming)
        self.assertEqual(len(items),2)
        by_source={i["video_external_id"]:i for i in items}
        self.assertEqual(len(by_source[PILOT_SOURCE]["source_moments"]),7)
        self.assertEqual(len(by_source[SECOND_SOURCE]["source_moments"]),8)
        for source,card in by_source.items():
            self.assertTrue(all(m["video_external_id"]==source for m in card["source_moments"]))
            self.assertIn(source,card["play_url"])
        self.assertEqual(incoming,before)

    def test_source_and_run_must_match_the_reviewed_pair(self):
        for source,run in [(SECOND_SOURCE,PILOT_RUN),(PILOT_SOURCE,SECOND_RUN),
                           ("vid-65a960554926d31a",SECOND_RUN),(SECOND_SOURCE,"new-unreviewed-run")]:
            row=hit(.5,video_external_id=source)
            row["appearance_evidence"]["processing_run_id"]=run
            self.assertNotIn("source_moments",self.items([row])[0])

    def test_retrieval_dedupe_preserves_pilot_evidence_even_same_slot(self):
        hits=[VideoHit(**hit(.5)),VideoHit(**hit(1.0))]
        with patch("memorybox.ask.retrieve._origin_on_video_hit",side_effect=lambda h:h):
            kept=_dedupe_video_hits(hits,limit=48)
        self.assertEqual(len(kept),2)
        self.assertEqual([h.start_sec for h in kept],[.5,1.0])

if __name__ == "__main__": unittest.main()
