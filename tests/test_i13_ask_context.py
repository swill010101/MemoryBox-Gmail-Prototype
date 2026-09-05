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

if __name__ == "__main__":
    unittest.main()
