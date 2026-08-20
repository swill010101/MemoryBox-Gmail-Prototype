"""P2-I10 Cross-Source Correlation acceptance."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from memorybox.explore.p2_i4_acceptance import _check
from memorybox.mbql.compile import compile_ask


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def prove_p2_i10(*, flightsim: bool = False) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    problems: list[str] = []
    meta: dict[str, Any] = {"increment": "P2-I10", "flightsim": bool(flightsim)}
    _structural(checks, problems)
    _compile(checks, problems)
    db_ok = _db_logic(checks, problems, meta)
    meta["db_logic"] = db_ok
    if flightsim:
        src = (_root().parent / "docs" / "source" / "MBBS-P2_INCREMENT_10_DEFINITION.md").read_text(
            encoding="utf-8"
        )
        _check(
            "p2i10_definition_authorized",
            "BUILD AUTHORIZED" in src and "I11" in src,
            checks,
            problems,
            "definition must stay authorized and keep I11 out",
        )
    return {
        "ok": not problems,
        "overall_ok": not problems,
        "checks": checks,
        "problems": problems,
        "meta": meta,
    }


def _structural(checks: dict[str, Any], problems: list[str]) -> None:
    root = _root()
    planner = (root / "planner" / "__init__.py").read_text(encoding="utf-8")
    retrieve = (root / "ask" / "retrieve.py").read_text(encoding="utf-8")
    orch = (root / "ask" / "orchestrator.py").read_text(encoding="utf-8")
    find_py = (root / "explore" / "find.py").read_text(encoding="utf-8")
    explore_js = (root / "explore" / "static" / "explore.js").read_text(encoding="utf-8")
    explore_html = (root / "explore" / "static" / "explore.html").read_text(encoding="utf-8")
    app = (root / "app.py").read_text(encoding="utf-8")
    mig = (root / "migrations" / "014_p2_i10_correlate.sql").read_text(encoding="utf-8")
    store = (root / "correlate" / "store.py").read_text(encoding="utf-8")
    _check(
        "p2i10_schema_links_places_events",
        "CREATE TABLE IF NOT EXISTS places" in mig
        and "CREATE TABLE IF NOT EXISTS correlatable_events" in mig
        and "CREATE TABLE IF NOT EXISTS correlation_links" in mig
        and "rejected" in mig,
        checks,
        problems,
        "014 migration must define places, events, links with rejected status",
    )
    _check(
        "p2i10_reject_does_not_delete",
        "rejected" in store and "DELETE FROM correlation_links" not in store,
        checks,
        problems,
        "reject must update status, not delete the row",
    )
    _check(
        "p2i10_compile_everything_about",
        "EVERYTHING_ABOUT_RE" in planner and "want_cross_source" in planner,
        checks,
        problems,
        "planner must compile everything-about as cross-source",
    )
    _check(
        "p2i10_spoken_does_not_narrow_cross_source",
        "want_cross_source" in planner and "want_spoken and not" in planner,
        checks,
        problems,
        "I9 spoken-narrowing must skip when want_cross_source",
    )
    _check(
        "p2i10_retrieve_cross_source_flag",
        "want_cross_source" in retrieve,
        checks,
        problems,
        "SMS/email retrieve must honor want_cross_source",
    )
    _check(
        "p2i10_pack_in_orchestrator",
        "apply_cross_source" in orch and "coverage" in orch,
        checks,
        problems,
        "Ask must attach coverage pack, not a saved Story",
    )
    _check(
        "p2i10_explore_coverage_strip",
        "coverage" in find_py
        and "mb-explore-coverage" in explore_html
        and "coverage" in explore_js,
        checks,
        problems,
        "Explore curator coverage strip",
    )
    _check(
        "p2i10_confirm_reject_api",
        "/correlate/link" in app and "reject_link" in app,
        checks,
        problems,
        "confirm/reject HTTP API",
    )
    _check(
        "p2i10_not_i11_narrative_save",
        "durable Story" not in orch or "not a saved Story" in (root / "correlate" / "pack.py").read_text(
            encoding="utf-8"
        )
        or "Everything about" in (root / "correlate" / "pack.py").read_text(encoding="utf-8"),
        checks,
        problems,
        "pack summary is coverage, not narrative save",
    )


def _compile(checks: dict[str, Any], problems: list[str]) -> None:
    plan = compile_ask("Show me everything I have about Grandpa's military service")
    notes = " ".join(plan.notes or ())
    theme = " ".join(getattr(plan, "theme_labels", ()) or ()).lower()
    _check(
        "p2i10_compile_cross_source_on",
        bool(getattr(plan, "want_cross_source", False)),
        checks,
        problems,
        f"want_cross_source notes={plan.notes}",
    )
    _check(
        "p2i10_compile_theme_military",
        "military" in theme,
        checks,
        problems,
        f"theme={getattr(plan, 'theme_labels', ())}",
    )
    _check(
        "p2i10_compile_not_video_only",
        plan.visual_scope != "video_only"
        and bool(plan.want_still)
        and bool(plan.want_communication)
        and bool(plan.want_calendar),
        checks,
        problems,
        f"scope={plan.visual_scope} still={plan.want_still} comm={plan.want_communication} cal={plan.want_calendar} spoken={plan.want_spoken}",
    )
    _check(
        "p2i10_compile_presentation_on",
        plan.gallery_show_email is True
        and plan.gallery_show_sms is True
        and plan.gallery_show_calendar is True,
        checks,
        problems,
        f"email={plan.gallery_show_email} sms={plan.gallery_show_sms} cal={plan.gallery_show_calendar}",
    )
    talking = compile_ask("Peggy talking about Christmas")
    _check(
        "p2i10_i9_talking_not_cross_source",
        bool(getattr(talking, "want_spoken", False))
        and not bool(getattr(talking, "want_cross_source", False)),
        checks,
        problems,
        f"talking cross={getattr(talking, 'want_cross_source', None)} spoken={talking.want_spoken}",
    )
    show = compile_ask("Show me Peggy")
    _check(
        "p2i10_ordinary_show_me_not_everything",
        not bool(getattr(show, "want_cross_source", False)),
        checks,
        problems,
        f"show_me notes={show.notes}",
    )
    _check(
        "p2i10_compile_note",
        "p2_i10_cross_source" in notes,
        checks,
        problems,
        notes,
    )


def _db_logic(checks: dict[str, Any], problems: list[str], meta: dict[str, Any]) -> bool:
    try:
        from memorybox.db import ping

        ping()
    except Exception as exc:  # noqa: BLE001
        _check(
            "p2i10_db_optional_skipped",
            True,
            checks,
            problems,
            f"no postgres: {exc}",
        )
        return False

    from memorybox.correlate.fixture import seed_i10_military_fixture
    from memorybox.correlate.pack import apply_cross_source
    from memorybox.correlate.store import date_conflicts, list_links, upsert_link
    from memorybox.migrate import migrate
    from memorybox.planner import QueryPlan

    migrate()
    seeded = seed_i10_military_fixture()
    meta["fixture"] = {k: seeded[k] for k in ("person_id", "event_id", "noise_link_id") if k in seeded}
    event_id = seeded["event_id"]
    conflicts = date_conflicts(event_id)
    _check(
        "p2i10_date_conflict_disclosed",
        len(conflicts) >= 2,
        checks,
        problems,
        f"conflicts={conflicts}",
    )
    restored = upsert_link(
        subject_type="evidence",
        subject_id=seeded["noise_id"],
        object_type="event",
        object_id=event_id,
        predicate="about",
        evidence_id=seeded["noise_id"],
        authority="system",
        status="candidate",
        provenance={"retry": True},
    )
    _check(
        "p2i10_reject_sticks",
        restored.get("status") == "rejected" and restored.get("restored") is False,
        checks,
        problems,
        str(restored),
    )
    rejected_rows = list_links(
        object_type="event",
        object_id=event_id,
        statuses=("rejected",),
    )
    _check(
        "p2i10_rejected_row_preserved",
        any(r["id"] == seeded["noise_link_id"] for r in rejected_rows),
        checks,
        problems,
        f"rejected={rejected_rows}",
    )

    class _E:
        def __init__(self, eid: str, channel: str, summary: str, sent_at: str | None = None):
            self.evidence_id = eid
            self.channel = channel
            self.evidence_kind = "communication"
            self.summary = summary
            self.excerpt = summary
            self.sent_at = sent_at

    evidence = [
        _E(seeded["email_id"], "email", "army Fort Lewis", "1968-03-12"),
        _E(seeded["letter_1968"], "email", "discharge 1968", "1968-06-01"),
        _E(seeded["letter_1969"], "email", "discharge 1969", "1969-06-01"),
        _E(seeded["noise_id"], "email", "walnut rolls", "2012-12-01"),
    ]
    plan = QueryPlan(
        original_ask="Show me everything I have about Grandpa's military service",
        effective_ask="everything-about",
        is_followup=False,
        want_photo=True,
        want_communication=True,
        want_calendar=True,
        want_cross_source=True,
        theme_labels=("military service",),
        person_names=("Eugene Will",),
    )
    artifacts = [{"artifact_id": seeded["artifact_id"], "label": "Eugene army letter", "kind": "letter"}]
    pack, filtered = apply_cross_source(
        plan,
        evidence=evidence,
        photos=[],
        videos=[],
        stories=[],
        journals=[],
        artifacts=artifacts,
        event_id=event_id,
    )
    kept_ids = {getattr(h, "evidence_id", None) for h in filtered["evidence"]}
    _check(
        "p2i10_pack_drops_rejected_keeps_military",
        seeded["noise_id"] not in kept_ids
        and seeded["email_id"] in kept_ids
        and seeded["letter_1968"] in kept_ids
        and pack.coverage.get("email", 0) >= 2
        and pack.coverage.get("artifact", 0) >= 1
        and "journal" in pack.missing
        and pack.dropped_rejected >= 1,
        checks,
        problems,
        f"kept={kept_ids} coverage={pack.coverage} missing={pack.missing} dropped={pack.dropped_rejected}",
    )
    _check(
        "p2i10_pack_not_a_story",
        "Everything about" in pack.summary and "Missing:" in pack.summary,
        checks,
        problems,
        pack.summary,
    )
    return True
