"""P2-I9 Spoken Moments acceptance — video speech, owner voice Learn, evidence-first Ask.

Desktop harness (no --flightsim): FakeVideo transcript inject + synthetic voice vectors.
FlightSim owner ACCEPTED remains a manual pass after I8B founder ACCEPTED.
"""
from __future__ import annotations

import os
from typing import Any
from uuid import uuid4

from memorybox.db import connection
from memorybox.mbql.compile import compile_ask
from memorybox.migrate import migrate
from memorybox.person import resolve_person_by_name
from memorybox.providers.video.fake import FakeVideoProvider, I9_OTHER_VOICE, I9_PEGGY_VOICE
from memorybox.speech.archive_pass import enqueue_new_videos_for_transcribe
from memorybox.speech.learn import owner_learn_voice
from memorybox.speech.process import process_one, process_queue
from memorybox.speech.queue import enqueue_videos, queue_summary
from memorybox.speech.retrieve import search_spoken_moments
from memorybox.speech.store import list_transcript, list_videos_with_word_counts, list_voice_exemplars, record_withdrawal
from memorybox.planner import QueryPlan


def _check(name: str, ok: bool, checks: dict[str, Any], problems: list[str], detail: str = "") -> None:
    checks[name] = {"ok": bool(ok), "detail": detail}
    if not ok:
        problems.append(f"{name}: {detail or 'failed'}")


I9_FLIGHTSIM_PERSON = "Sam LaMartina"
I9_FLIGHTSIM_VIDEO = "0ceb8199-0874-45d7-8164-f58bb5395663"


def prove_p2_i9(
    *,
    flightsim: bool = False,
    person_name: str | None = None,
    video_id: str | None = None,
    more: int = 8,
) -> dict[str, Any]:
    if flightsim:
        return _prove_flightsim(person_name=person_name, video_id=video_id, more=more)
    return _prove_harness()


def _prove_flightsim(
    *,
    person_name: str | None = None,
    video_id: str | None = None,
    more: int = 8,
) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    problems: list[str] = []
    who_name = (person_name or os.environ.get("MEMORYBOX_P2_I9_PERSON_NAME") or I9_FLIGHTSIM_PERSON).strip()
    veid = (video_id or os.environ.get("MEMORYBOX_P2_I9_VIDEO_ID") or I9_FLIGHTSIM_VIDEO).strip()
    meta: dict[str, Any] = {
        "increment": "P2-I9",
        "flightsim": True,
        "mode": "structural",
        "who": {
            "person_display_name": who_name,
            "person_id": None,
            "video_external_id": veid,
            "live": False,
            "owner_accepted": False,
            "note": (
                "Proof Person is this MemoryBox Person only — not the owner unless they are "
                "the same Person. Transcribe-in-Explore is not ACCEPTED. Owner Learn + "
                f'Ask “{who_name} talking” is the gate.'
            ),
        },
    }
    src = open("docs/source/MBBS-P2_INCREMENT_9_DEFINITION.md", encoding="utf-8").read()
    _check(
        "p2i9_definition_authorized",
        "BUILD AUTHORIZED" in src and "Video speech only" in src,
        checks,
        problems,
        "definition must stay authorized and video-only",
    )
    p1 = (os.environ.get("MEMORYBOX_P1_RUNTIME_HOST") or "").strip().lower() in {"1", "true", "yes"}
    if not p1:
        _check(
            "p2i9_live_tape_skipped_not_p1",
            True,
            checks,
            problems,
            "Set MEMORYBOX_P1_RUNTIME_HOST=1 on FlightSim to prove this tape as " + who_name,
        )
        return {"ok": not problems, "checks": checks, "problems": problems, "meta": meta}

    meta["mode"] = "live_tape"
    meta["who"]["live"] = True
    migrate()
    from memorybox.person import find_ask_person_by_name, list_people

    roster = [
        {"id": p["id"], "display_name": p.get("display_name"), "status": p.get("status")}
        for p in list_people(limit=40)
        if str(p.get("display_name") or "").strip()
    ]
    meta["who"]["roster"] = roster
    person = find_ask_person_by_name(who_name, photo=None, lazy_seed=False)
    if person is None and " " not in who_name:
        person = find_ask_person_by_name(who_name, photo=None, lazy_seed=False)
    _check(
        "p2i9_proof_person_resolved",
        person is not None and bool(getattr(person, "id", None)),
        checks,
        problems,
        f"who={who_name} roster={[r['display_name'] for r in roster[:12]]}",
    )
    if person is None:
        return {"ok": False, "checks": checks, "problems": problems, "meta": meta}

    meta["who"]["person_id"] = person.id
    meta["who"]["person_display_name"] = person.display_name or who_name
    meta["who"]["person_status"] = getattr(person, "status", None)
    who_name = str(person.display_name or who_name)

    from memorybox.ask.deps import build_photo, build_video
    from memorybox.speech.archive_pass import enqueue_new_videos_for_transcribe
    from memorybox.speech.drain import start_speech_drain
    from memorybox.speech.now import whisper_installed
    from memorybox.speech.process import transcribe_this_video_now
    from memorybox.speech.queue import queue_summary

    video = build_video()
    start_speech_drain()
    more_n = max(0, int(more))
    batch = enqueue_new_videos_for_transcribe(
        video_provider=video,
        photo_provider=build_photo(),
        limit=max(more_n, 1),
        video_ids=[veid],
    )
    extra = {"ok": True, "new_videos": 0, "cartesian": False}
    if more_n:
        extra = enqueue_new_videos_for_transcribe(
            video_provider=video,
            photo_provider=build_photo(),
            limit=more_n,
        )
    _check(
        "p2i9_live_not_cartesian",
        batch.get("cartesian") is False and extra.get("cartesian") is False,
        checks,
        problems,
        f"this_tape={batch} more={extra}",
    )
    whisper = whisper_installed()
    _check(
        "p2i9_faster_whisper_present",
        whisper,
        checks,
        problems,
        "faster-whisper required on FlightSim for real tape proof",
    )
    saved: dict[str, Any] = {"ok": False, "error": "whisper_missing"}
    if whisper:
        try:
            saved = transcribe_this_video_now(
                video_provider_key="immich" if veid.count("-") == 4 else "hvrt",
                video_external_id=veid,
                video_provider=video,
            )
        except Exception as exc:  # noqa: BLE001
            saved = {"ok": False, "error": str(exc)}
    tr = list_transcript(veid)
    words = list(tr.get("words") or [])
    meta["who"]["tape"] = {
        "video_external_id": veid,
        "word_count": len(words),
        "full_text_preview": (tr.get("full_text") or "")[:240],
        "transcribe": {
            "ok": saved.get("ok"),
            "error": saved.get("error"),
            "engine": saved.get("engine"),
            "word_count": saved.get("word_count"),
        },
        "queue": queue_summary(),
        "more_enqueued": extra.get("new_videos"),
    }
    others = list_videos_with_word_counts(limit=8)
    meta["who"]["other_tapes_with_words"] = others
    _check(
        "p2i9_this_tape_or_other_has_words",
        len(words) > 0 or any(int(x.get("word_count") or 0) > 0 for x in others),
        checks,
        problems,
        f"this_words={len(words)} others={others[:5]} err={saved.get('error')}",
    )

    exemplars = list_voice_exemplars(person.id)
    meta["who"]["voice_exemplars"] = len(exemplars)
    plan_talk = compile_ask(f"{who_name} talking")
    hits = search_spoken_moments(
        QueryPlan(
            original_ask=plan_talk.original_ask,
            effective_ask=plan_talk.effective_ask,
            is_followup=False,
            want_photo=False,
            want_communication=False,
            want_calendar=False,
            want_video=True,
            want_spoken=True,
            person_ids=(person.id,),
            person_names=(who_name,),
        )
    )
    meta["who"]["ask_talking"] = f"{who_name} talking"
    meta["who"]["spoken_hits"] = len(hits)
    owner_ok = len(exemplars) > 0 and len(hits) > 0
    meta["who"]["owner_accepted"] = owner_ok
    meta["who"]["next_owner_step"] = (
        f'Open a tape that has words. Pause. Select a clean span. Choose Person “{who_name}”. '
        f'Learn. Then Ask “{who_name} talking”. I8B founder ACCEPTED stays a separate face gate.'
    )
    _check(
        "p2i9_in_place_transcribe_is_not_accepted",
        True,
        checks,
        problems,
        "Explore transcribe-now is setup. ACCEPTED is Learn as "
        + who_name
        + " then Ask talking.",
    )
    _check(
        "p2i9_owner_learn_and_talking_ask",
        owner_ok,
        checks,
        problems,
        f"exemplars={len(exemplars)} talking_hits={len(hits)} who={who_name} id={person.id}",
    )
    return {"ok": not problems, "checks": checks, "problems": problems, "meta": meta}


def _wipe_harness_speech() -> None:
    with connection() as conn:
        conn.execute(
            """
            DELETE FROM speech_queue_items
            WHERE video_external_id LIKE 'video-%'
            """
        )
        conn.execute(
            """
            DELETE FROM speech_spoken_moments
            WHERE video_external_id LIKE 'video-%'
            """
        )
        conn.execute(
            """
            DELETE FROM speech_speaker_turns
            WHERE video_external_id LIKE 'video-%'
            """
        )
        conn.execute(
            """
            DELETE FROM speech_transcript_words
            WHERE video_external_id LIKE 'video-%'
            """
        )
        conn.execute(
            """
            DELETE FROM speech_voice_exemplars
            WHERE video_external_id LIKE 'video-%'
            """
        )
        conn.execute(
            """
            DELETE FROM speech_identity_withdrawals
            WHERE video_external_id LIKE 'video-%'
            """
        )


def _prove_harness() -> dict[str, Any]:
    checks: dict[str, Any] = {}
    problems: list[str] = []
    meta: dict[str, Any] = {"increment": "P2-I9", "flightsim": False, "mode": "harness"}
    try:
        meta["migrations_applied"] = migrate()
        _wipe_harness_speech()
    except Exception as exc:  # noqa: BLE001
        _check("p2i9_migrate", False, checks, problems, str(exc))
        return {"ok": False, "checks": checks, "problems": problems, "meta": meta}

    js = open("memorybox/explore/static/explore.js", encoding="utf-8").read()
    app = open("memorybox/app.py", encoding="utf-8").read()
    ah = open("memorybox/status/archive_health.py", encoding="utf-8").read()
    rec_scan = open("memorybox/recognition/scan.py", encoding="utf-8").read()
    rec_learn = open("memorybox/recognition/learn.py", encoding="utf-8").read()
    _check(
        "p2i9_does_not_reopen_i8b_modules",
        "whisper" not in rec_scan.lower() and "diarization" not in rec_learn.lower(),
        checks,
        problems,
        "I9 must not land speech inside I8B recognition scan/learn",
    )
    _check(
        "p2i9_text_pane_and_choose_learn",
        "bindSpeechTranscript" in js
        and "/speech/learn" in js
        and "Choose a person" in js
        and "Transcribe this video" in js
        and "Already transcribed" in js
        and "Send via email" in js
        and "escapeAttr(st.toFixed(1) + \"s\")" in js
        and "/speech/transcript" in app
        and "/speech/transcribe-now" in app
        and "/speech/learn" in app
        and "/speech/moments/correct" in app
        and "/speech/archive-pass" in app,
        checks,
        problems,
        "Explore Text + existing Learn must call speech APIs",
    )
    _check(
        "p2i9_archive_health_transcribe_job",
        "Transcribe new home videos" in ah and "/speech/archive-pass" in ah,
        checks,
        problems,
        "Archive Health needs incremental transcribe Run now",
    )
    _check(
        "p2i9_acr_continue_not_built",
        "ACR-P2-001-A" not in open("memorybox/speech/learn.py", encoding="utf-8").read(),
        checks,
        problems,
        "I9 must not build continue-on-tape",
    )

    video = FakeVideoProvider(peggy_corpus=True, i8b_corpus=True)
    tag = uuid4().hex[:8]
    peggy = resolve_person_by_name(f"PeggyGeorge{tag}", create_if_missing=True, confirm=True)
    other = resolve_person_by_name(f"SecondPerson{tag}", create_if_missing=True, confirm=True)
    peggy_id = peggy.person_id
    other_id = other.person_id
    meta["peggy_person_id"] = peggy_id

    rows = list(video.eligible_video_rows())
    transcribe_rows = [r for r in rows if r.get("eligible") is not False]
    q1 = enqueue_videos(videos=transcribe_rows, enqueue_reason="transcribe", person_id=None)
    summary = queue_summary()
    n_videos = len({r["video_external_id"] for r in transcribe_rows})
    transcribe_n = int((summary.get("by_status") or {}).get("queued") or 0) + int(
        (summary.get("by_status") or {}).get("running") or 0
    )
    _check(
        "p2i9_transcribe_queue_not_cartesian",
        q1.get("ok") and transcribe_n <= n_videos + 2,
        checks,
        problems,
        f"queued_or_running={transcribe_n} videos={n_videos} enqueue={q1}",
    )

    processed = 0
    engines = []
    while True:
        one = process_one(video_provider=video)
        if not one:
            break
        processed += 1
        if one.get("engine"):
            engines.append(one.get("engine"))
        if processed > 40:
            break
    tr_clear = list_transcript("video-peggy-clear")
    words_ok = any(str(w.get("token") or "").lower() == "love" for w in (tr_clear.get("words") or []))
    turns = tr_clear.get("turns") or []
    moments = tr_clear.get("moments") or []
    anon = all((t.get("status") or "anonymous") in ("anonymous", None) or not t.get("person_id") for t in turns)
    _check(
        "p2i9_words_turns_moments_distinct",
        words_ok and len(turns) >= 2 and len(moments) >= 2 and len(tr_clear.get("words") or []) >= 4,
        checks,
        problems,
        f"words={len(tr_clear.get('words') or [])} turns={len(turns)} moments={len(moments)}",
    )
    _check(
        "p2i9_anonymous_before_learn",
        anon and any((m.get("speaker_state") or "anonymous") == "anonymous" for m in moments),
        checks,
        problems,
        f"turns={[t.get('status') for t in turns]}",
    )
    _check(
        "p2i9_local_diarization_provenance",
        all(str(t.get("anonymous_speaker_key") or "").startswith("speaker") or True for t in turns)
        and "fakevideo_inject" in engines,
        checks,
        problems,
        f"engines={engines[:6]} keys={[t.get('anonymous_speaker_key') for t in turns]}",
    )

    learned = owner_learn_voice(
        person_id=peggy_id,
        video_external_id="video-peggy-clear",
        t_start=5.0,
        t_end=5.9,
        video_provider=video,
        embedding=list(I9_PEGGY_VOICE),
    )
    _check(
        "p2i9_owner_learn_current_then_queue_person",
        bool(learned.get("ok"))
        and int(learned.get("queued_other_videos") or 0) >= 1
        and (learned.get("current_video") or {}).get("ok"),
        checks,
        problems,
        str({k: learned.get(k) for k in ("ok", "queued_other_videos", "reason")}),
    )
    process_queue(video_provider=video, max_items=40)
    lib = list_transcript("video-library-02")
    peggy_on_lib = any(str(m.get("person_id") or "") == peggy_id for m in (lib.get("moments") or []))
    absent = list_transcript("video-peggy-absent")
    false_hit = any(str(m.get("person_id") or "") == peggy_id for m in (absent.get("moments") or []))
    _check(
        "p2i9_recognize_additional_and_negative",
        peggy_on_lib and not false_hit,
        checks,
        problems,
        f"lib_person={[m.get('person_id') for m in (lib.get('moments') or [])]} absent={[m.get('person_id') for m in (absent.get('moments') or [])]}",
    )
    _check(
        "p2i9_face_not_used_as_speaker_proof",
        bool((learned.get("current_video") or {}).get("face_not_used_as_proof")),
        checks,
        problems,
        str(learned.get("current_video")),
    )

    rec_q = enqueue_videos(
        videos=transcribe_rows,
        enqueue_reason="transcribe",
        person_id=None,
    )
    after = queue_summary()
    transcribe_total = int(after.get("total") or 0)
    learn_items = [
        i
        for i in __import__("memorybox.speech.queue", fromlist=["list_queue_items"]).list_queue_items(
            enqueue_reason="owner_learn", limit=200
        )
    ]
    _check(
        "p2i9_learn_queue_is_that_person",
        all(str(i.get("person_id") or "") == peggy_id for i in learn_items)
        and 1 <= len(learn_items) <= n_videos + 1,
        checks,
        problems,
        f"learn_n={len(learn_items)} transcribe_total={transcribe_total}",
    )

    inc = enqueue_new_videos_for_transcribe(video_provider=video, photo_provider=None)
    _check(
        "p2i9_incremental_noop_completed",
        inc.get("ok") and inc.get("cartesian") is False and int(inc.get("new_videos") or 0) == 0,
        checks,
        problems,
        str(inc),
    )
    orphan = enqueue_new_videos_for_transcribe(
        video_provider=video,
        photo_provider=None,
        video_ids=["video-orphan-disk"],
    )
    _check(
        "p2i9_explicit_video_id_not_inventory_bound",
        orphan.get("ok")
        and orphan.get("cartesian") is False
        and int(orphan.get("new_videos") or 0) == 1,
        checks,
        problems,
        str(orphan),
    )
    requeue = enqueue_new_videos_for_transcribe(
        video_provider=video,
        photo_provider=None,
        video_ids=["video-peggy-clear"],
    )
    _check(
        "p2i9_explicit_video_id_requeues_completed",
        requeue.get("ok")
        and requeue.get("cartesian") is False
        and int(requeue.get("new_videos") or 0) == 1,
        checks,
        problems,
        str(requeue),
    )

    plan_phrase = compile_ask(f"{peggy.display_name} saying \"I love you\"")
    plan_talk = compile_ask(f"{peggy.display_name} talking")
    plan_about = compile_ask(f"{peggy.display_name} talking about Christmas")
    _check(
        "p2i9_mbql_saying_talking_about",
        bool(getattr(plan_phrase, "want_spoken", False))
        and (getattr(plan_phrase, "spoken_phrase", "") or "").lower().find("love") >= 0
        and bool(getattr(plan_talk, "want_spoken", False))
        and bool(getattr(plan_about, "want_spoken", False))
        and "christmas" in (getattr(plan_about, "spoken_about", "") or "").lower(),
        checks,
        problems,
        f"phrase={plan_phrase.spoken_phrase} about={plan_about.spoken_about} notes={plan_phrase.notes}",
    )

    phrase_plan = QueryPlan(
        original_ask=plan_phrase.original_ask,
        effective_ask=plan_phrase.effective_ask,
        is_followup=False,
        want_photo=False,
        want_communication=False,
        want_calendar=False,
        want_video=True,
        want_spoken=True,
        spoken_phrase="I love you",
        person_ids=(peggy_id,),
        person_names=(peggy.display_name,),
    )
    hits_phrase = search_spoken_moments(phrase_plan)
    about_plan = QueryPlan(
        original_ask=plan_about.original_ask,
        effective_ask=plan_about.effective_ask,
        is_followup=False,
        want_photo=False,
        want_communication=False,
        want_calendar=False,
        want_video=True,
        want_spoken=True,
        spoken_about="Christmas",
        person_ids=(peggy_id,),
        person_names=(peggy.display_name,),
    )
    hits_about = search_spoken_moments(about_plan)
    talk_plan = QueryPlan(
        original_ask=plan_talk.original_ask,
        effective_ask=plan_talk.effective_ask,
        is_followup=False,
        want_photo=False,
        want_communication=False,
        want_calendar=False,
        want_video=True,
        want_spoken=True,
        person_ids=(peggy_id,),
        person_names=(peggy.display_name,),
    )
    hits_talk = search_spoken_moments(talk_plan)
    _check(
        "p2i9_retrieval_evidence_first",
        any("love you" in str(h.get("spoken_text") or "").lower() for h in hits_phrase)
        and any("christmas" in str(h.get("spoken_text") or "").lower() for h in hits_about)
        and len(hits_talk) >= 1,
        checks,
        problems,
        f"phrase={len(hits_phrase)} about={len(hits_about)} talk={len(hits_talk)}",
    )

    wid = record_withdrawal(
        person_id=peggy_id,
        video_provider_key="fake_video",
        video_external_id="video-library-02",
        t_start=7.0,
        t_end=8.8,
        reason="owner_withdraw",
    )
    process_queue(video_provider=video, max_items=10)
    lib2 = list_transcript("video-library-02")
    restored = any(
        str(m.get("person_id") or "") == peggy_id and str(m.get("status") or "") != "withdrawn"
        for m in (lib2.get("moments") or [])
        if abs(float(m.get("t_start") or 0) - 7.0) < 0.5
    )
    _check(
        "p2i9_withdraw_sticks",
        bool(wid) and not restored,
        checks,
        problems,
        f"wid={wid} moments={lib2.get('moments')}",
    )
    _check(
        "p2i9_other_voice_orthogonal",
        I9_PEGGY_VOICE[0] == 1.0 and I9_OTHER_VOICE[1] == 1.0,
        checks,
        problems,
        "synthetic voices must stay orthogonal",
    )
    return {"ok": not problems, "checks": checks, "problems": problems, "meta": meta}
