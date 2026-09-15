"""I14 Phase C Gallery prepared-comms reads. No live DSN."""
from __future__ import annotations

import os
import types
import unittest
from unittest.mock import patch

from memorybox.explore import prepared_comms as pc
from memorybox.explore.find import build_explore_find


class _Rows:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def fetchone(self) -> dict | None:
        return self._rows[0] if self._rows else None

    def fetchall(self) -> list[dict]:
        return list(self._rows)


def _thread_row(display_id: str, latest: str | None = "2020-01-02") -> dict:
    return {
        "display_id": display_id,
        "earliest_at": latest,
        "latest_at": latest,
        "message_count": 2,
        "identity_confidence": "authenticated_focal",
        "gallery_eligibility": "show_by_default",
        "subject": "Hello",
        "preview": "Hi there",
        "attachment_count": 1,
        "participants": "Peggy, Tom",
    }


class FakeConn:
    def __init__(self, *, active: str | None = "gen-active", threads: list[dict] | None = None) -> None:
        self.active = active
        self.sql: list[str] = []
        self.thread_rows = threads or [_thread_row("T-100"), _thread_row("T-100")]
        self.eligibility = [
            {"gallery_eligibility": "show_by_default", "n": 3},
            {"gallery_eligibility": "suppress_default", "n": 2},
            {"gallery_eligibility": "hold_uncertain", "n": 1},
        ]
        self.years = [{"y": 2020, "n": 3}]

        self.bucket_rows = [{"y": 2020, "mo": 1, "thread_n": 3, "message_n": 6}]

    def execute(self, sql: str, params: tuple | None = None) -> _Rows:
        text = " ".join(sql.split())
        self.sql.append(text)
        if "FROM comms_prepared_active_generations" in text:
            return _Rows([{"id": self.active}] if self.active else [])
        if "GROUP BY t.gallery_eligibility" in text:
            return _Rows(self.eligibility)
        if "gallery_buckets" in text:
            return _Rows(self.bucket_rows)
        if "gallery_threads" in text or "scoped.in_scope_latest" in text:
            assert "voice_corpus" not in text
            rows = list(self.thread_rows)
            fetch_n = 81
            before_id = None
            if params:
                fetch_n = int(params[-1])
                if len(params) >= 9:
                    before_id = params[-4]
            if before_id:
                ids = [str(r["display_id"]) for r in rows]
                if str(before_id) in ids:
                    rows = rows[ids.index(str(before_id)) + 1 :]
            out = []
            for rec in rows[:fetch_n]:
                row = dict(rec)
                row["in_scope_latest"] = rec.get("latest_at")
                out.append(row)
            return _Rows(out)
        if "FROM comms_prepared_threads" in text and "display_id" in text:
            return _Rows(
                [
                    {
                        "id": "tid",
                        "identity_confidence": "authenticated_focal",
                    }
                ]
            )
        if "FROM comms_prepared_messages" in text:
            return _Rows(
                [
                    {
                        "id": "mid",
                        "ordinal": 1,
                        "evidence_ref": "EV-1",
                        "evidence_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                        "subject": "Hello",
                        "sent_at": None,
                        "cleaned_authored_text": "Hi there",
                        "quote_quality": "uncertain",
                        "identity_quality": "unverified",
                        "voice_corpus": False,
                        "commercial_class": "not_commercial",
                    }
                ]
            )
        if "FROM comms_prepared_participants" in text:
            return _Rows(
                [
                    {
                        "role": "from",
                        "display_name": "Peggy",
                        "identity_confidence": "authenticated_focal",
                        "person_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                    },
                    {
                        "role": "to",
                        "display_name": "Tom",
                        "identity_confidence": "authenticated_other",
                        "person_id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
                    },
                    {
                        "role": "cc",
                        "display_name": "someone",
                        "identity_confidence": "unverified",
                        "person_id": None,
                    },
                ]
            )
        if "FROM comms_prepared_attachments" in text:
            return _Rows(
                [
                    {
                        "filename": "photo.jpg",
                        "mime_type": "image/jpeg",
                        "byte_size": 12,
                        "gallery_action": "view_image",
                        "attachment_evidence_id": None,
                        "source_locator": "mbox:1",
                        "attachment_ordinal": 0,
                    },
                    {
                        "filename": "note.bin",
                        "mime_type": "application/octet-stream",
                        "byte_size": 1,
                        "gallery_action": "record_only",
                        "attachment_evidence_id": None,
                        "source_locator": None,
                        "attachment_ordinal": 1,
                    },
                ]
            )
        return _Rows([])


class Flag(unittest.TestCase):
    def test_default_off(self) -> None:
        os.environ.pop("MEMORYBOX_I14_GALLERY_COMMS", None)
        self.assertFalse(pc.gallery_comms_enabled())

    def test_on(self) -> None:
        os.environ["MEMORYBOX_I14_GALLERY_COMMS"] = "1"
        self.assertTrue(pc.gallery_comms_enabled())
        os.environ.pop("MEMORYBOX_I14_GALLERY_COMMS", None)


class ListThreads(unittest.TestCase):
    def tearDown(self) -> None:
        pc._last_complete.clear()
        pc._tokens.clear()

    def test_active_only_dedupes_and_hides_commercial(self) -> None:
        token = pc.new_ask_token()
        out = pc.list_person_threads(FakeConn(), person_id="person-p", token=token)
        self.assertTrue(out["active_generation"])
        self.assertEqual(len(out["items"]), 1)
        self.assertEqual(out["items"][0]["id"], "prepared:T-100")
        self.assertEqual(out["excluded"]["suppress_default"], 2)
        self.assertEqual(out["excluded"]["hold_uncertain"], 1)
        self.assertEqual(out["view"], "threads")
        self.assertEqual(out["person_match"]["status"], "linked")
        self.assertFalse(out["items"][0]["gallery_default_hidden"])

    def test_pages_stay_bounded_and_cursor_continues(self) -> None:
        token = pc.new_ask_token()
        rows = [_thread_row(f"T-{i}", "2020-02-01") for i in range(5, 0, -1)]
        conn = FakeConn(threads=rows)
        conn.eligibility = [{"gallery_eligibility": "show_by_default", "n": 5}]
        page1 = pc.list_person_threads(conn, person_id="person-p", token=token, cap=2)
        self.assertEqual(len(page1["items"]), 2)
        self.assertTrue(page1["has_more"])
        self.assertLessEqual(len(page1["items"]), 2)
        ids1 = {i["display_id"] for i in page1["items"]}
        cur = page1["next_cursor"]
        page2 = pc.list_person_threads(
            conn,
            person_id="person-p",
            token=token,
            cap=2,
            before_latest=cur["before_latest"],
            before_id=cur["before_id"],
        )
        ids2 = {i["display_id"] for i in page2["items"]}
        self.assertTrue(ids1.isdisjoint(ids2))
        token2 = pc.new_ask_token()
        abandoned = pc.list_person_threads(
            conn,
            person_id="person-p",
            token=token,
            cap=2,
            before_id=cur["before_id"],
        )
        self.assertTrue(abandoned["cancelled"])

    def test_mismatch_status(self) -> None:
        token = pc.new_ask_token()
        conn = FakeConn(threads=[])
        conn.eligibility = []
        conn.bucket_rows = []
        out = pc.list_person_buckets(conn, person_id="missing", token=token)
        self.assertEqual(out["person_match"]["status"], "no_prepared_participant")
        self.assertEqual(out["scoped_thread_total"], 0)
        self.assertEqual(out["reachable_total"], 0)

    def test_cancel_after_abandon(self) -> None:
        token = pc.new_ask_token()
        pc.abandon_token(token)
        out = pc.list_person_threads(FakeConn(), person_id="person-p", token=token)
        self.assertTrue(out["cancelled"])
        self.assertEqual(out["items"], [])

    def test_new_ask_cancels_previous_token(self) -> None:
        first = pc.new_ask_token()
        pc.new_ask_token()
        self.assertFalse(pc.token_live(first))

    def test_stale_uses_last_complete_buckets(self) -> None:
        token = pc.new_ask_token()
        first = pc.list_person_buckets(FakeConn(), person_id="person-p", token=token)
        token2 = pc.new_ask_token()
        stale = pc.list_person_buckets(
            FakeConn(active=None), person_id="person-p", token=token2
        )
        self.assertTrue(stale["stale"])
        self.assertEqual(len(stale["buckets"]), len(first["buckets"]))
        self.assertTrue(stale["updated_through"])

    def test_year_ask_month_buckets_are_complete_not_paged(self) -> None:
        token = pc.new_ask_token()
        conn = FakeConn()
        conn.bucket_rows = [
            {"y": 2017, "mo": 3, "thread_n": 4, "message_n": 9},
            {"y": 2017, "mo": 6, "thread_n": 6, "message_n": 11},
        ]
        out = pc.list_person_buckets(
            conn,
            person_id="sue",
            token=token,
            date_from="2017-01-01",
            date_to="2017-12-31",
        )
        self.assertEqual(out["grain"], "month")
        self.assertEqual(out["scope_year"], 2017)
        self.assertEqual(len(out["items"]), 0)
        self.assertEqual(out["scoped_thread_total"], 10)
        keys = [b["key"] for b in out["buckets"]]
        self.assertEqual(set(keys), {"2017-06", "2017-03"})
        self.assertEqual(sum(b["thread_n"] for b in out["buckets"]), 10)
        listing = "\n".join(conn.sql)
        self.assertNotIn("LIMIT 80", listing)

    def test_unbounded_year_counts_ignore_page_size(self) -> None:
        token = pc.new_ask_token()
        conn = FakeConn()
        conn.bucket_rows = [
            {"y": 2016, "mo": 1, "thread_n": 100, "message_n": 100},
            {"y": 2017, "mo": 1, "thread_n": 200, "message_n": 200},
            {"y": 2018, "mo": 1, "thread_n": 50, "message_n": 50},
        ]
        out = pc.list_person_buckets(conn, person_id="sue", token=token)
        self.assertEqual(out["grain"], "year")
        self.assertEqual(out["scoped_thread_total"], 350)
        by = {b["key"]: b["thread_n"] for b in out["buckets"]}
        self.assertEqual(by["2017"], 200)
        self.assertEqual(by["2016"], 100)

    def test_new_ask_cancels_bucket_and_thread_reads(self) -> None:
        first = pc.new_ask_token()
        pc.new_ask_token()
        self.assertTrue(pc.list_person_buckets(FakeConn(), person_id="p", token=first)["cancelled"])
        self.assertTrue(pc.list_person_threads(FakeConn(), person_id="p", token=first)["cancelled"])

    def test_roles_not_voice_only(self) -> None:
        token = pc.new_ask_token()
        conn = FakeConn()
        pc.list_person_threads(conn, person_id="person-p", token=token)
        listing = "\n".join(conn.sql)
        self.assertIn("EXISTS", listing)
        self.assertNotIn("voice_corpus", listing)
        self.assertNotIn("role = 'from'", listing)


class LoadThread(unittest.TestCase):
    def test_story_and_unverified_cc(self) -> None:
        out = pc.load_thread(FakeConn(), "T-100")
        self.assertTrue(out["ok"])
        self.assertEqual(out["story_memory"]["source_kind"], "email_thread")
        self.assertEqual(out["story_memory"]["source_id"], "T-100")
        cc = out["messages"][0]["cc"][0]
        self.assertFalse(cc["trusted"])
        self.assertTrue(out["messages"][0]["from"][0]["trusted"])
        self.assertIn("Hi there", out["story_body"])
        proof = pc.interaction_proof(out)
        self.assertTrue(proof["original_on_demand"])
        self.assertTrue(proof["story_covers_authored"])
        self.assertTrue(proof["story_kind_email_thread"])
        self.assertTrue(proof["attachments_linked_not_copied"])
        self.assertTrue(any("quote_quality_uncertain" in (m.get("warnings") or []) for m in out["messages"]))
        self.assertTrue(any("participant_identity_uncertain" in (m.get("warnings") or []) for m in out["messages"]))
        atts = out["messages"][0]["attachments"]
        self.assertTrue(atts[0]["available"])
        self.assertFalse(atts[1]["available"])
        self.assertEqual(atts[1]["gallery_action"], "record_only")
        self.assertIn("not viewable", atts[1]["state_label"])
        self.assertIn("Image preview", atts[0]["state_label"])
        self.assertFalse(out["messages"][0]["empty_prepared_text"])


class ExploreFind(unittest.TestCase):
    def setUp(self) -> None:
        self._sms_patch = patch(
            "memorybox.ask.retrieve.search_sms_messages", return_value=[]
        )
        self._cal_patch = patch(
            "memorybox.ask.retrieve.search_calendar_events", return_value=[]
        )
        self._sms_patch.start()
        self._cal_patch.start()

    def tearDown(self) -> None:
        self._sms_patch.stop()
        self._cal_patch.stop()
        os.environ.pop("MEMORYBOX_I14_GALLERY_COMMS", None)
        pc._tokens.clear()

    def test_flag_off_person_ask_does_not_pending_prepared(self) -> None:
        os.environ.pop("MEMORYBOX_I14_GALLERY_COMMS", None)
        orch = types.SimpleNamespace(
            ask=lambda *a, **k: {
                "plan": {
                    "person_ids": ["11111111-1111-1111-1111-111111111111"],
                    "person_names": ["Peggy"],
                    "output_mode": "show",
                },
                "photo_hits": [],
                "video_hits": [],
                "evidence_hits": [],
                "provider_status": {},
            }
        )
        payload = build_explore_find(
            ask_text="Show me Peggy", session_id="s", orchestrator=orch
        )
        self.assertFalse(payload["explore_state"]["prepared_comms_pending"])
        self.assertFalse(payload["explore_state"]["gallery_show_email"])

    def test_flag_off_explicit_email_still_uses_raw_retrieve(self) -> None:
        os.environ.pop("MEMORYBOX_I14_GALLERY_COMMS", None)
        orch = types.SimpleNamespace(
            ask=lambda *a, **k: {
                "plan": {
                    "person_ids": ["11111111-1111-1111-1111-111111111111"],
                    "person_names": ["Peggy"],
                    "output_mode": "show",
                },
                "photo_hits": [],
                "video_hits": [],
                "evidence_hits": [],
                "provider_status": {},
            }
        )
        with patch("memorybox.ask.retrieve.search_email_messages", return_value=[]) as search:
            payload = build_explore_find(
                ask_text="Show me Peggy emails", session_id="s", orchestrator=orch
            )
        self.assertFalse(payload["explore_state"]["prepared_comms_pending"])
        search.assert_called()

    def test_flag_on_skips_raw_email(self) -> None:
        os.environ["MEMORYBOX_I14_GALLERY_COMMS"] = "1"
        orch = types.SimpleNamespace(
            ask=lambda *a, **k: {
                "plan": {
                    "person_ids": ["11111111-1111-1111-1111-111111111111"],
                    "person_names": ["Peggy"],
                    "output_mode": "show",
                },
                "photo_hits": [
                    {"external_id": "photo-1", "people": ["Peggy"], "taken_at": "2010-01-02"}
                ],
                "video_hits": [],
                "evidence_hits": [],
                "provider_status": {},
            }
        )
        with patch(
            "memorybox.ask.retrieve.search_email_messages",
            side_effect=AssertionError("raw email parse forbidden"),
        ):
            payload = build_explore_find(
                ask_text="Show me Peggy", session_id="s", orchestrator=orch
            )
        self.assertTrue(payload["explore_state"]["prepared_comms_pending"])
        self.assertTrue(payload["explore_state"]["prepared_comms_token"])
        self.assertFalse(payload["explore_state"]["gallery_show_email"])
        types_ = {str(i.get("type")) for i in payload["items"]}
        self.assertIn("photo", types_)
        self.assertNotIn("email", types_)

    def test_unresolved_person_is_observable(self) -> None:
        os.environ["MEMORYBOX_I14_GALLERY_COMMS"] = "1"
        orch = types.SimpleNamespace(
            ask=lambda *a, **k: {
                "plan": {
                    "person_ids": [],
                    "person_names": ["Peggy"],
                    "output_mode": "show",
                },
                "photo_hits": [
                    {"external_id": "photo-1", "people": ["Peggy"], "taken_at": "2010-01-02"}
                ],
                "video_hits": [],
                "evidence_hits": [],
                "provider_status": {},
            }
        )
        payload = build_explore_find(
            ask_text="Show me Peggy", session_id="s", orchestrator=orch
        )
        self.assertTrue(payload["explore_state"]["prepared_comms_unresolved"])
        self.assertFalse(payload["explore_state"]["prepared_comms_pending"])
        self.assertIn("photo", {str(i.get("type")) for i in payload["items"]})

    def test_dated_ask_excludes_undated_stories_and_other_years(self) -> None:
        os.environ["MEMORYBOX_I14_GALLERY_COMMS"] = "1"
        orch = types.SimpleNamespace(
            ask=lambda *a, **k: {
                "plan": {
                    "person_ids": ["11111111-1111-1111-1111-111111111111"],
                    "person_names": ["Sue Will"],
                    "output_mode": "show",
                    "time_start": "2017-01-01",
                    "time_end": "2017-12-31",
                },
                "photo_hits": [
                    {
                        "external_id": "photo-2017",
                        "people": ["Sue"],
                        "taken_at": "2017-04-02",
                    },
                    {
                        "external_id": "photo-2016",
                        "people": ["Sue"],
                        "taken_at": "2016-04-02",
                    },
                ],
                "story_hits": [
                    {"story_id": "s-undated", "title": "Undated story", "taken_at": ""},
                    {
                        "story_id": "s-2017",
                        "title": "Dated story",
                        "taken_at": "2017-08-01",
                    },
                ],
                "video_hits": [],
                "evidence_hits": [],
                "provider_status": {},
            }
        )
        payload = build_explore_find(
            ask_text="Show me Sue Will in 2017", session_id="s", orchestrator=orch
        )
        types_dates = [
            (str(i.get("type")), str(i.get("date") or ""), bool(i.get("undated")))
            for i in payload["items"]
        ]
        self.assertIn(("photo", "2017-04-02", False), types_dates)
        self.assertNotIn(("photo", "2016-04-02", False), types_dates)
        self.assertNotIn(("story", "", True), types_dates)
        story_dates = [i.get("date") for i in payload["items"] if i.get("type") == "story"]
        self.assertEqual(story_dates, ["2017-08-01"])
        self.assertFalse(payload["explore_state"]["gallery_show_email"])
        self.assertTrue(payload["explore_state"]["prepared_comms_pending"])
        self.assertIn("2017", payload.get("title") or payload.get("ask_text") or "")

    def test_dated_person_ask_hydrates_sms_from_existing_path(self) -> None:
        os.environ["MEMORYBOX_I14_GALLERY_COMMS"] = "1"
        from memorybox.ask.retrieve import EvidenceHit

        hit = EvidenceHit(
            evidence_id="sms-2017-1",
            evidence_kind="sms",
            summary="hello",
            score=1.0,
            excerpt="hello",
            source="sms_export",
            sent_at="2017-06-02",
            channel="sms",
            people=["Sue Will"],
            match_total=328,
        )
        orch = types.SimpleNamespace(
            ask=lambda *a, **k: {
                "plan": {
                    "person_ids": ["11111111-1111-1111-1111-111111111111"],
                    "person_names": ["Sue Will"],
                    "output_mode": "show",
                    "time_start": "2017-01-01",
                    "time_end": "2017-12-31",
                },
                "photo_hits": [
                    {
                        "external_id": "photo-2017",
                        "people": ["Sue"],
                        "taken_at": "2017-04-02",
                    }
                ],
                "video_hits": [],
                "evidence_hits": [],
                "provider_status": {},
            }
        )
        self._sms_patch.stop()
        with patch("memorybox.ask.retrieve.search_sms_messages", return_value=[hit]):
            payload = build_explore_find(
                ask_text="Show me Sue Will in 2017", session_id="s", orchestrator=orch
            )
        self.assertFalse(payload["explore_state"]["gallery_show_sms"])
        self.assertFalse(payload["explore_state"]["gallery_show_email"])
        self.assertTrue(payload["explore_state"]["gallery_mixed_comms"])
        self.assertEqual(payload["explore_state"]["sms_available"], 328)
        self.assertEqual(payload["explore_state"]["sms_match_total"], 328)
        sms = [i for i in payload["items"] if i.get("type") == "sms"]
        self.assertEqual(len(sms), 1)
        self.assertFalse(sms[0].get("gallery_default_hidden"))
        self.assertIn("328 text message", payload["summary"])
        self.assertNotIn("retrieval", payload["summary"].lower())
        self.assertNotIn("80 of", payload["summary"])

    def test_partial_orchestrator_sms_does_not_block_mixed_retrieve(self) -> None:
        os.environ["MEMORYBOX_I14_GALLERY_COMMS"] = "1"
        from memorybox.ask.retrieve import EvidenceHit

        hit = EvidenceHit(
            evidence_id="sms-2017-full",
            evidence_kind="sms",
            summary="hello",
            score=1.0,
            excerpt="hello",
            source="sms_export",
            sent_at="2017-06-02",
            channel="sms",
            people=["Sue Will"],
            match_total=328,
        )
        orch = types.SimpleNamespace(
            ask=lambda *a, **k: {
                "plan": {
                    "person_ids": ["11111111-1111-1111-1111-111111111111"],
                    "person_names": ["Sue Will"],
                    "output_mode": "show",
                    "time_start": "2017-01-01",
                    "time_end": "2017-12-31",
                },
                "photo_hits": [],
                "video_hits": [],
                "evidence_hits": [
                    {
                        "evidence_id": "sms-partial",
                        "evidence_kind": "sms",
                        "channel": "sms",
                        "source": "sms_export",
                        "sent_at": "2017-03-01",
                        "excerpt": "partial",
                    }
                ],
                "provider_status": {},
            }
        )
        self._sms_patch.stop()
        with patch("memorybox.ask.retrieve.search_sms_messages", return_value=[hit]) as search:
            payload = build_explore_find(
                ask_text="Show me Sue Will in 2017", session_id="s", orchestrator=orch
            )
        search.assert_called()
        self.assertEqual(payload["explore_state"]["sms_match_total"], 328)
        self.assertFalse(payload["explore_state"]["gallery_show_sms"])
        hidden = [
            i
            for i in payload["items"]
            if i.get("type") == "sms" and i.get("gallery_default_hidden")
        ]
        self.assertEqual(hidden, [])


if __name__ == "__main__":
    unittest.main()
