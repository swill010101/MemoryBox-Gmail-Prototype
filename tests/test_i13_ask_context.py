"""Offline Ask context and provider membership regressions."""
import unittest
from memorybox.context import AskContext, InMemoryContextStore
from memorybox.ask.context_commands import is_clear_all, prepare_context
from memorybox.providers.photo._immich_http import asset_matches_people
from memorybox.planner import plan_ask

class AskContextTests(unittest.TestCase):
    def setUp(self):
        self.store = InMemoryContextStore()
        self.old = self.store.save(AskContext(session_id="old", person_names=("Previous Person",), place_names=("New York",), event_labels=("Christmas",), time_start="2018", time_end="2018", result_selection=("old-asset",), modalities_active=("video",)))
    def resolve(self, name):
        return object() if name.casefold() == "example person" else None
    def test_clear_all_clears_every_slot_and_rotates_session(self):
        ctx, reset = prepare_context(self.store, " CLEAR ALL. ", "old", self.resolve)
        self.assertTrue(reset)
        self.assertTrue(ctx.is_empty())
        self.assertTrue(self.store.get("old").is_empty())
        self.assertNotEqual(ctx.session_id, "old")
        self.store.save(self.old) # An older request cannot populate the new session.
        self.assertTrue(self.store.get(ctx.session_id).is_empty())
    def test_named_search_drops_all_prior_context(self):
        ctx, reset = prepare_context(self.store, "show me Example Person", "old", self.resolve)
        self.assertTrue(reset)
        self.assertTrue(ctx.is_empty())
        plan = plan_ask("show me Example Person", ctx)
        self.assertFalse(plan.place_names)
        self.assertFalse(plan.event_labels)
        self.assertIsNone(plan.time_start)
    def test_followups_keep_person_context(self):
        ctx = self.store.save(AskContext(session_id="person", person_names=("Example Person",)))
        for text in ("in Alaska", "at Christmas", "in 2018"):
            with self.subTest(text=text):
                inherited, reset = prepare_context(self.store, text, ctx.session_id, self.resolve)
                self.assertFalse(reset)
                self.assertEqual(plan_ask(text, inherited).person_names, ctx.person_names)
    def test_clear_all_is_exact_command(self):
        for text in ("clear all but person", "clear filters", "show me clear all"):
            self.assertFalse(is_clear_all(text))
    def test_missing_person_does_not_claim_name_resolution(self):
        _, reset = prepare_context(self.store, "show me missing person", "old", self.resolve)
        self.assertFalse(reset)

class CommandBoundaryTests(unittest.TestCase):
    def test_clear_returns_before_trace_and_retrieval(self):
        import types
        from unittest.mock import patch
        from test_i13_stage_a import function
        person = types.ModuleType("memorybox.person")
        person.AmbiguousIdentityError = type("AmbiguousIdentityError", (Exception,), {})
        def forbidden(*args, **kwargs):
            raise AssertionError("clear all must not resolve names or retrieve")
        person.find_ask_person_by_name = forbidden
        ask = function("memorybox/ask/orchestrator.py", "ask", {"AskResult": lambda **kw: types.SimpleNamespace(**kw)})
        store = InMemoryContextStore()
        store.save(AskContext(session_id="old", person_names=("Previous Person",)))
        with patch.dict("sys.modules", {"memorybox.person": person}):
            result = ask(types.SimpleNamespace(store=store), "clear all", session_id="old")
        self.assertEqual(result.answer_kind, "context_cleared")
        self.assertTrue(result.context["empty"])
        self.assertEqual(result.photo_hits, [])
    def test_explore_clear_payload_has_no_gallery_items(self):
        import types
        from test_i13_stage_a import function
        build = function("memorybox/explore/find.py", "build_explore_find")
        orch = types.SimpleNamespace(ask=lambda *a, **k: {"answer_kind":"context_cleared", "session_id":"new", "context":{"reset":True}})
        payload = build(ask_text="clear all", session_id="old", orchestrator=orch)
        self.assertEqual(payload["items"], [])
        self.assertEqual(payload["chips"], [])
        self.assertEqual(payload["session_id"], "new")

class MembershipTests(unittest.TestCase):
    def test_unscoped_asset_and_other_person_are_rejected(self):
        for asset in ({"id":"city"}, {"id":"city","people":[]}, {"id":"other","people":[{"id":"other-person"}]}):
            self.assertFalse(asset_matches_people(asset, ["requested"]))
    def test_explicit_asset_membership_and_face_edges(self):
        for asset in ({"people":[{"id":"requested"}]}, {"faces":[{"person":{"id":"requested"}}]}, {"faces":[{"personId":"requested"}]}):
            self.assertTrue(asset_matches_people(asset, ["requested"]))
    def test_face_id_is_not_person_id(self):
        self.assertFalse(asset_matches_people({"faces":[{"id":"requested"}]}, ["requested"]))

class CompactTimelineTests(unittest.TestCase):
    def client(self, fail_metadata=False):
        from memorybox.providers.photo._immich_http import ImmichHttpClient
        client = object.__new__(ImmichHttpClient)
        client._reset_call_log = lambda: None
        client._circuit = lambda: False
        client._read_person_lib_cache = lambda *a, **k: None
        client._reported_person_asset_count = lambda ids: 100
        client._merge_map_marker_gps = lambda rows: None
        client._filter_assets_to_windows = lambda rows, windows: rows
        client._finalize_person_library = lambda rows, windowed, target: windowed[:target]
        client._note_transport_fail = lambda exc: None
        client._write_person_lib_cache = lambda *a: self.fail("Incomplete library must not be cached")
        client._assets_from_person_faces = lambda *a: [{"id":"feature", "people":[{"id":"person"}]}]
        client._assets_from_person_timeline = lambda *a: client._list_person_bucket_assets("person", "2018-01-01T00:00:00.000Z")
        calls = []
        def request(method, path, **kwargs):
            calls.append((method, path, kwargs.get("body")))
            if method == "GET":
                return 200, {"id":["photo"], "isImage":[True], "fileCreatedAt":["2018-01-02"]}
            if fail_metadata:
                raise TimeoutError("synthetic provider timeout")
            body = kwargs["body"]
            people = [{"id":"person"}] if body.get("withPeople") else []
            return 200, {"assets":{"items":[
                {"id":"photo", "type":"IMAGE", "people":people},
                {"id":"feature", "type":"IMAGE", "people":people, "fileCreatedAt":"2018-01-02"},
                {"id":"unrelated", "people":[{"id":"other"}]}
            ]}}
        client._request = request
        return client, calls

    def test_compact_timeline_and_feature_face_do_not_hide_photos(self):
        client, calls = self.client()
        rows = client.search_by_person_ids(["person"], size=10)
        self.assertEqual({r["id"] for r in rows}, {"photo", "feature"})
        self.assertEqual(next(r for r in rows if r["id"]=="feature")["fileCreatedAt"], "2018-01-02")
        posts = [body for method, path, body in calls if method=="POST"]
        self.assertTrue(posts)
        self.assertTrue(all(b["withPeople"] and b["personIds"]==["person"] for b in posts))
        self.assertEqual(sum(method=="GET" for method, _, _ in calls), 1)

    def test_timeout_never_accepts_unverified_compact_assets(self):
        client, calls = self.client(fail_metadata=True)
        rows = client.search_by_person_ids(["person"], size=10)
        self.assertEqual([r["id"] for r in rows], ["feature"])
        self.assertTrue(client._person_lib_incomplete)

if __name__ == "__main__":
    unittest.main()
