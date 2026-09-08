"""Read-only reconciliation of interactive Learn vs accepted I13 PRD on FlightSim.

Never starts processing, Learn, drains, or archive actions. Classifies six PRD
interactive-Learn checkpoints from database aggregates, env, and static route inventory.

Optional JSON: MEMORYBOX_I13_LEARN_RECON_OUTPUT (prefer E: paths).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

APP = ROOT / "memorybox" / "app.py"
EXPLORE_JS = ROOT / "memorybox" / "explore" / "static" / "explore.js"

CHECKS = (
    "face_box_person_learn",
    "transcript_person_voice_learn",
    "admin_learned_evidence",
    "admin_jobs",
    "learned_evidence_correction_removal",
    "interactive_learn_enabled_while_archive_locked",
)


def _static_route_inventory() -> dict:
    text = APP.read_text(encoding="utf-8")
    return {
        "explore_ui": '"/explore/ui"' in text or "@app.get(\"/explore/ui\")" in text,
        "recognition_learn_post": '"/recognition/learn"' in text,
        "speech_learn_post": '"/speech/learn"' in text,
        "appearances_correct_post": '"/recognition/appearances/correct"' in text,
        "speech_moments_correct_post": '"/speech/moments/correct"' in text,
        "admin_landing": '"/admin/ui"' in text or "@app.get(\"/admin/ui\")" in text,
        "admin_learned_evidence": '"/admin/learned-evidence/ui"' in text,
        "admin_jobs_i13": '"/admin/jobs/ui"' in text,
        "status_ui_archive_health": '"/status/ui"' in text,
        "review_ui": '"/review/ui"' in text,
    }


def _explore_learn_surface() -> dict:
    js = EXPLORE_JS.read_text(encoding="utf-8")
    return {
        "submitExploreLearn": "function submitExploreLearn" in js,
        "learn_rail": 'data-rail="learn"' in js or "renderLearnRail" in js,
        "box_face": "Box face" in js or "startLearnBoxing" in js,
        "transcript_selection": "bindSpeechTranscript" in js,
        "annotation_separate_from_learn": "Annotation saved" in js or "annotate" in js.lower(),
    }


def _playback_binder_note() -> dict:
    js = EXPLORE_JS.read_text(encoding="utf-8")
    snippet = js[js.index("function bindAppearanceView"): js.index("function bindSourceMoments")]
    return {
        "seeks_to_start_only": "relevance end is metadata" in snippet,
        "no_end_pause_in_binder": "pause()" not in snippet and "end_sec" not in snippet.split("seekToStart")[1][:400],
        "offline_unit_test": "test_real_binder_seeks_and_never_clamps_or_restarts",
        "offline_browser_proof": str(
            ROOT / "docs/implementation/p2-i13-stage-a/browser-playback-proof.json"
        ),
    }


def _query_db(conn) -> dict:
    admissions = conn.execute(
        """
        SELECT id::text, state, created_at,
               interactive_learn_enabled,
               interactive_learn_ref,
               plan_json->>'purpose' AS purpose,
               plan_json->>'scope_kind' AS scope_kind,
               plan_json->'lanes' AS lanes
        FROM i13_processing_admissions
        ORDER BY created_at DESC
        LIMIT 20
        """
    ).fetchall()
    started = [dict(r) for r in admissions if r["state"] == "started"]
    face_owner_learn = conn.execute(
        """
        SELECT count(*) AS n
        FROM face_exemplars
        WHERE method = 'owner_learn'
        """
    ).fetchone()["n"]
    voice_owner_learn = conn.execute(
        """
        SELECT count(*) AS n
        FROM speech_voice_exemplars
        WHERE method = 'owner_learn'
        """
    ).fetchone()["n"]
    rec_owner_learn_q = conn.execute(
        """
        SELECT count(*) AS n
        FROM recognition_queue_items
        WHERE enqueue_reason = 'owner_learn'
        """
    ).fetchone()["n"]
    speech_owner_learn_q = conn.execute(
        """
        SELECT count(*) AS n
        FROM speech_queue_items
        WHERE enqueue_reason = 'owner_learn'
        """
    ).fetchone()["n"]
    face_withdrawn = conn.execute(
        """
        SELECT count(*) AS n
        FROM face_appearance_moments
        WHERE status = 'withdrawn' OR confirmation_state = 'withdrawn'
        """
    ).fetchone()["n"]
    speech_withdrawn = conn.execute(
        """
        SELECT count(*) AS n
        FROM speech_voice_moments
        WHERE withdrawn IS TRUE
        """
    ).fetchone()["n"]
    annotation_withdrawn = conn.execute(
        """
        SELECT count(*) AS n
        FROM i13_transcript_annotations
        WHERE action = 'withdraw'
        """
    ).fetchone()["n"]
    archive_unlocked = conn.execute(
        """
        SELECT count(*) AS n
        FROM i13_processing_admissions
        WHERE plan_json->>'scope_kind' = 'archive'
          AND state IN ('unlocked', 'started')
        """
    ).fetchone()["n"]
    return {
        "admissions_recent": [dict(r) for r in admissions],
        "started_admissions": started,
        "owner_learn_face_exemplars": int(face_owner_learn),
        "owner_learn_voice_exemplars": int(voice_owner_learn),
        "recognition_queue_owner_learn": int(rec_owner_learn_q),
        "speech_queue_owner_learn": int(speech_owner_learn_q),
        "face_moments_withdrawn": int(face_withdrawn),
        "speech_moments_withdrawn": int(speech_withdrawn),
        "annotation_withdrawals": int(annotation_withdrawn),
        "archive_admissions_unlocked_or_started": int(archive_unlocked),
    }


def _classify(*, routes: dict, explore: dict, db: dict | None, env: dict) -> list[dict]:
    admission_id = env.get("MEMORYBOX_I13_ADMISSION_ID", "").strip()
    active = None
    if db and admission_id:
        for row in (db.get("admissions_recent") or []):
            if row.get("id") == admission_id:
                active = row
                break
    started = (db or {}).get("started_admissions") or []
    started_learning = [
        a
        for a in started
        if a.get("purpose") == "acceptance_learning"
        and a.get("scope_kind") == "bounded"
        and any(lane in (a.get("lanes") or []) for lane in ("face", "voice"))
    ]
    learn_enabled = bool(
        admission_id
        and active
        and active.get("purpose") == "acceptance_learning"
        and active.get("scope_kind") == "bounded"
        and any(lane in (active.get("lanes") or []) for lane in ("face", "voice"))
        and (
            (active.get("state") == "started" and bool(started_learning))
            or (
                active.get("state") == "stopped"
                and bool(active.get("interactive_learn_enabled"))
            )
        )
    )
    archive_locked = (db or {}).get("archive_admissions_unlocked_or_started", 0) == 0

    face_ex = (db or {}).get("owner_learn_face_exemplars", 0)
    voice_ex = (db or {}).get("owner_learn_voice_exemplars", 0)

    items = []

    # 1 Face box -> Person -> Learn
    if not explore.get("submitExploreLearn"):
        c, e = "failed", "Explore Learn UI surface missing in checkout."
    elif not routes.get("recognition_learn_post"):
        c, e = "failed", "POST /recognition/learn route missing."
    elif not learn_enabled:
        c, e = (
            "failed",
            "No interactive Learn authorization: need started bounded acceptance_learning during proof, "
            "or stopped admission with interactive_learn_enabled and MEMORYBOX_I13_ADMISSION_ID retained. "
            f"DB owner_learn face exemplars={face_ex} (not proof of this bounded session).",
        )
    elif face_ex == 0:
        c, e = "not tested", "Learn admission appears enabled but no owner_learn face exemplars in DB."
    else:
        c, e = (
            "not tested",
            f"Admission enabled and {face_ex} owner_learn exemplars exist, but no scripted live UI proof recorded.",
        )
    items.append({"id": 1, "key": CHECKS[0], "classification": c, "evidence": e})

    # 2 Transcript -> Person -> voice Learn
    if not explore.get("transcript_selection"):
        c, e = "failed", "Transcript selection UI missing."
    elif not routes.get("speech_learn_post"):
        c, e = "failed", "POST /speech/learn route missing."
    elif not learn_enabled:
        c, e = (
            "failed",
            "No interactive Learn authorization for voice lane (see enable-interactive-learn after stop). "
            f"DB owner_learn voice exemplars={voice_ex}.",
        )
    elif voice_ex == 0:
        c, e = "not tested", "Learn admission appears enabled but no owner_learn voice exemplars in DB."
    else:
        c, e = "not tested", f"Admission enabled and {voice_ex} voice exemplars exist; no live UI proof recorded."
    items.append({"id": 2, "key": CHECKS[1], "classification": c, "evidence": e})

    # 3 Admin Learned Evidence
    if routes.get("admin_learned_evidence"):
        c, e = "not tested", "Admin Learned Evidence UI exists; live withdraw/list proof required after acceptance_learning admission."
    else:
        c, e = (
            "failed",
            "No I13 Admin -> Learned Evidence page or route. Partial read surfaces: /review/ui, People, voice-pilot results.",
        )
    items.append({"id": 3, "key": CHECKS[2], "classification": c, "evidence": e})

    # 4 Admin Jobs
    if routes.get("admin_jobs_i13"):
        c, e = "not tested", "Admin Jobs UI exists; live scoped queue proof required after acceptance_learning start."
    else:
        c, e = (
            "failed",
            "No I13 Admin -> Jobs page. Archive Health (/status/ui) exposes legacy owner jobs only, not I13 scoped processing jobs.",
        )
    items.append({"id": 4, "key": CHECKS[3], "classification": c, "evidence": e})

    # 5 Correction / removal
    apis = routes.get("appearances_correct_post") and routes.get("speech_moments_correct_post")
    ann = (db or {}).get("annotation_withdrawals", 0) if db else 0
    if not apis:
        c, e = "failed", "Correction/removal APIs incomplete in checkout."
    elif ann > 0 or (db and (db.get("face_moments_withdrawn") or db.get("speech_moments_withdrawn"))):
        c, e = (
            "not tested",
            "Withdraw/correct APIs exist; DB shows withdrawal history, but no unified Learned Evidence admin correction UI.",
        )
    else:
        c, e = (
            "not tested",
            "APIs exist (appearances/correct, moments/correct, annotations/transcript); unified Learned Evidence correction UI missing; no bounded live exercise recorded.",
        )
    items.append({"id": 5, "key": CHECKS[4], "classification": c, "evidence": e})

    # 6 Learn enabled while archive locked
    lock_ok = archive_locked and env.get("MEMORYBOX_RECOGNITION_DRAIN", "0") == "0" and env.get("MEMORYBOX_SPEECH_DRAIN", "0") == "0"
    if lock_ok and not learn_enabled:
        c, e = (
            "failed",
            "Archive register/unlock/start correctly absent and drains off, but interactive Learn is not authorized "
            "(missing MEMORYBOX_I13_ADMISSION_ID, started proof window, or enable-interactive-learn after stop).",
        )
    elif lock_ok and learn_enabled:
        c, e = "passed", "Archive locked, drains off, bounded acceptance_learning enables user-selected Learn (started or post-stop interactive flag)."
    elif not lock_ok:
        c, e = "failed", "Archive unlocked/started admission present or drains enabled — violates closeout locks."
    else:
        c, e = "failed", "Lock state could not be confirmed."
    items.append({"id": 6, "key": CHECKS[5], "classification": c, "evidence": e})

    return items


def build_report() -> dict:
    routes = _static_route_inventory()
    explore = _explore_learn_surface()
    env = {
        "MEMORYBOX_I13_ADMISSION_ID": os.environ.get("MEMORYBOX_I13_ADMISSION_ID", ""),
        "MEMORYBOX_RECOGNITION_DRAIN": os.environ.get("MEMORYBOX_RECOGNITION_DRAIN", "0"),
        "MEMORYBOX_SPEECH_DRAIN": os.environ.get("MEMORYBOX_SPEECH_DRAIN", "0"),
    }
    db = None
    db_error = None
    try:
        from memorybox.db import connection

        with connection() as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            db = _query_db(conn)
    except Exception as exc:
        db_error = f"{type(exc).__name__}: {exc}"

    items = _classify(routes=routes, explore=explore, db=db, env=env)
    counts: dict[str, int] = {}
    for row in items:
        counts[row["classification"]] = counts.get(row["classification"], 0) + 1

    return {
        "ok": True,
        "read_only": True,
        "processing_started": False,
        "limits": (
            "Static route/UI inventory plus read-only DB aggregates. "
            "Does not exercise Explore UI or infer voice-pilot annotations as interactive Learn."
        ),
        "env": env,
        "routes": routes,
        "explore_learn_surface": explore,
        "playback_binder": _playback_binder_note(),
        "db": db,
        "db_error": db_error,
        "interactive_learn_checks": items,
        "classification_counts": counts,
        "voice_pilot_is_not_interactive_learn": True,
    }


def main() -> int:
    if not os.environ.get("MEMORYBOX_DATABASE_URL", "").strip():
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "MEMORYBOX_DATABASE_URL absent; load deployment env first.",
                    "flightsim_hint": "Use TitaNet venv Python from configured FlightSim shell.",
                },
                indent=2,
            )
        )
        return 2
    try:
        report = build_report()
    except ModuleNotFoundError as exc:
        if exc.name == "psycopg":
            print(
                json.dumps(
                    {
                        "ok": False,
                        "error": str(exc),
                        "flightsim_hint": r"C:\MemoryBox-releases\p2-i13-voice-pilot-6d56da5\.titanet-venv\Scripts\python.exe",
                    },
                    indent=2,
                )
            )
            return 2
        raise

    out = os.environ.get("MEMORYBOX_I13_LEARN_RECON_OUTPUT", "").strip()
    if out:
        path = Path(out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        report["output_file"] = str(path)

    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
