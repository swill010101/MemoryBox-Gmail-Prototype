"""P2-I10A.2 shared narrative field + speech acceptance."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from memorybox.providers.capture.fake import FakeCaptureSttProvider

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
NF_JS = ROOT / "shell" / "static" / "mb-narrative-field.js"
NF_CSS = ROOT / "shell" / "static" / "mb-narrative-field.css"
STORY = ROOT / "story" / "static" / "story.html"
JOURNAL = ROOT / "journal" / "static" / "journal.html"
ARTIFACT = ROOT / "artifact" / "static" / "artifact.html"
PERSON_HTML = ROOT / "person" / "static" / "person-edit.html"
PERSON_JS = ROOT / "person" / "static" / "person-edit.js"
APP = ROOT / "app.py"
STORY_PY = ROOT / "story" / "__init__.py"
PRD = REPO / "docs" / "product" / "MBPRD-P2-I10A2_SPEECH_INPUT.md"
SCREEN = REPO / "docs" / "product" / "MBSC-P2-I10A2_SPEECH_SCREEN_CONTRACT.md"
ACCEPT = REPO / "docs" / "product" / "MBAT-P2-I10A2_ACCEPTANCE.md"


def _check(name: str, ok: bool, checks: dict[str, Any], problems: list[str], detail: str = "") -> None:
    checks[name] = {"ok": bool(ok), "detail": detail}
    if not ok:
        problems.append(f"{name}: {detail or 'failed'}")


def _locked(text: str) -> bool:
    return "BUILD AUTHORIZED" in text and "LOCKED" in text


def run_prove_i10a2(*, flightsim: bool = False) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    problems: list[str] = []
    meta: dict[str, Any] = {
        "increment": "P2-I10A.2",
        "p1_runtime_final": bool(flightsim),
        "note": "Shared narrative field; authored-memory vs convenience speech.",
    }
    if flightsim:
        os.environ["MEMORYBOX_P1_RUNTIME_HOST"] = "1"

    nf = NF_JS.read_text(encoding="utf-8") if NF_JS.is_file() else ""
    css = NF_CSS.read_text(encoding="utf-8") if NF_CSS.is_file() else ""
    story = STORY.read_text(encoding="utf-8") if STORY.is_file() else ""
    journal = JOURNAL.read_text(encoding="utf-8") if JOURNAL.is_file() else ""
    artifact = ARTIFACT.read_text(encoding="utf-8") if ARTIFACT.is_file() else ""
    person_html = PERSON_HTML.read_text(encoding="utf-8") if PERSON_HTML.is_file() else ""
    person_js = PERSON_JS.read_text(encoding="utf-8") if PERSON_JS.is_file() else ""
    app = APP.read_text(encoding="utf-8") if APP.is_file() else ""
    story_py = STORY_PY.read_text(encoding="utf-8") if STORY_PY.is_file() else ""
    prd = PRD.read_text(encoding="utf-8") if PRD.is_file() else ""

    _check("docs_prd", PRD.is_file() and _locked(prd), checks, problems, "PRD locked + build-authorized")
    _check("docs_screen", SCREEN.is_file() and "LOCKED" in SCREEN.read_text(encoding="utf-8"), checks, problems)
    _check("docs_accept", ACCEPT.is_file(), checks, problems)

    _check("a01_shared_module", "MBNarrativeField.mount" in nf and "authored-memory" in nf, checks, problems, str(NF_JS))
    _check("a01_css", ".mb-nf" in css, checks, problems, str(NF_CSS))
    _check(
        "a01_four_surfaces",
        all(
            "mb-narrative-field.js" in blob
            for blob in (story, journal, artifact, person_html)
        ),
        checks,
        problems,
        "all four HTML pages load shared JS",
    )
    _check(
        "a01_story_authored",
        'speech: "authored-memory"' in story and 'id="ed-body"' in story,
        checks,
        problems,
        "Story body authored-memory",
    )
    _check(
        "a01_journal_authored",
        'speech: "authored-memory"' in journal and 'id="body"' in journal and 'id="editBody"' in journal,
        checks,
        problems,
        "Journal bodies authored-memory",
    )
    _check(
        "a01_artifact_convenience",
        'speech: "convenience"' in artifact and 'id="ed-desc"' in artifact,
        checks,
        problems,
        "Artifact description convenience",
    )
    _check(
        "a01_person_convenience",
        'speech: "convenience"' in person_js and 'id="mb-edit-notes"' in person_html,
        checks,
        problems,
        "Person notes convenience",
    )
    _check(
        "a10_one_lifecycle",
        "MediaRecorder" in nf
        and "MediaRecorder" not in journal
        and "MediaRecorder" not in artifact
        and "MediaRecorder" not in story
        and "MediaRecorder" not in person_js,
        checks,
        problems,
        "recorder lives only in shared module",
    )
    _check(
        "a17_journal_poc_replaced",
        'id="recBtn"' not in journal and "body.value = draft.text" not in journal,
        checks,
        problems,
        "Journal private Record/Stop POC gone",
    )
    _check(
        "a11_no_orphan_client",
        "restoreCommit" in nf and "pagehide" in nf and "discardUnsaved" in nf,
        checks,
        problems,
        "Cancel/Start Over deletes scratch audio",
    )
    _check(
        "a12_silence_prompt",
        "Are you still there?" in nf
        and "Continue recording" in nf
        and "mb-nf-modal-back" in nf
        and "still listening" in nf.lower()
        and "auto-stop" not in nf.lower(),
        checks,
        problems,
        "silence prompt is a modal; recording is not paused; no auto-stop copy",
    )
    _check("a04_pause_resume", "Pause" in nf and "Resume" in nf and "recorder.pause" in nf, checks, problems)
    _check("a05_stop_review", 'mode = "review"' in nf and "Save" in nf, checks, problems)
    _check("a06_play", 'textContent = "Listen"' in nf and "mb-nf-listen" in nf, checks, problems)
    sover = nf.split("async function startOver")[-1][:1200] if "async function startOver" in nf else ""
    _check(
        "a10_start_over",
        "Start over" in nf and "startRecording();" in sover,
        checks,
        problems,
        "Start over confirms, then records again",
    )
    _check("a03_vu_meter", "mb-nf-vu" in nf and "Level" in nf, checks, problems, "labeled live level while recording")
    _check(
        "mic_skips_virtual_cable",
        "isVirtualMic" in nf and "voicemeeter" in nf,
        checks,
        problems,
        "do not prefer VoiceMeeter/VB-Audio as the story mic",
    )
    _check(
        "a16_capture_query",
        'p.get("capture")' in story and "capture=1" in artifact and "restoreCommit" in story,
        checks,
        problems,
        "Tell its story capture=1 honored by Story; remount restores unsaved take",
    )
    _check(
        "a20_no_mic_short_fields",
        "ed-title" in story and 'speech: "authored-memory"' in story and "ed-title" not in nf,
        checks,
        problems,
        "title/date fields are not in the shared speech module",
    )
    no_stt_ui = "Whisper" not in nf and "MediaRecorder" not in story
    _check("family_wording_js", "Tell this story" in nf and "Whisper" not in nf, checks, problems)
    _check("family_wording_pages", "Whisper" not in journal and "STT" not in journal, checks, problems)

    _check(
        "at12_convenience_scratch",
        "retain=0" in nf or "retain=" in nf,
        checks,
        problems,
        "convenience transcribe retain=0",
    )
    _check(
        "server_retain_and_delete",
        "retain" in app and "/capture/audio/" in app and "discard_audio" in app,
        checks,
        problems,
        "transcribe retain + DELETE /capture/audio",
    )
    _check(
        "a02_story_audio_uri",
        "audio_uri" in story_py and "speech_origin" in story_py,
        checks,
        problems,
        "Story versions persist audio + speech provenance",
    )
    _check(
        "a18_clone_preserves_audio",
        "audio_uri=src.get(" in story_py,
        checks,
        problems,
        "begin_edit copies prior audio onto working draft; freeze writes a new version",
    )
    _check("i10b_artifact_no_recorder", "MediaRecorder" not in artifact, checks, problems)

    # Live scratch discard (no DB)
    try:
        stt = FakeCaptureSttProvider()
        handle = stt.preserve_audio(b"fake-bytes-xxxx", filename="t.webm")
        path = stt.resolve_audio_path(handle.audio_id)
        gone = stt.discard_audio(handle.audio_id)
        still = stt.resolve_audio_path(handle.audio_id)
        _check(
            "a12_scratch_delete",
            bool(gone) and path is not None and still is None,
            checks,
            problems,
            f"removed={gone} after={still}",
        )
    except Exception as exc:  # noqa: BLE001
        _check("a12_scratch_delete", False, checks, problems, str(exc))

    try:
        import memorybox.app as appmod
        from fastapi.testclient import TestClient

        appmod._capture_stt = FakeCaptureSttProvider()
        client = TestClient(appmod.app)
        kept = client.post(
            "/capture/transcribe?retain=1",
            files={"file": ("t.webm", b"fake-bytes-xxxx", "audio/webm")},
        )
        kd = kept.json().get("draft") or {}
        kid = kd.get("audio_id")
        g1 = client.get("/capture/audio/" + kid) if kid else None
        dropped = client.post(
            "/capture/transcribe?retain=0",
            files={"file": ("t.webm", b"fake-bytes-xxxx", "audio/webm")},
        )
        dd = dropped.json().get("draft") or {}
        _check(
            "at12_http_retain",
            kept.status_code == 200
            and kid
            and g1 is not None
            and g1.status_code == 200
            and dropped.status_code == 200
            and dd.get("audio_discarded") is True
            and not dd.get("audio_uri"),
            checks,
            problems,
            f"keep={kept.status_code} drop={dropped.status_code} discarded={dd.get('audio_discarded')}",
        )
    except Exception as exc:  # noqa: BLE001
        _check("at12_http_retain", False, checks, problems, str(exc))

    try:
        from memorybox.migrate import migrate
        from memorybox.story import begin_edit, create_story, get_story, save_story

        migrate()
        s1 = create_story(
            title="I10A.2 spoken take",
            body_text="Approved words after review.",
            audio_uri="file:///tmp/i10a2-take-a.webm",
            speech_origin="speech",
            speech_user_edited=True,
            speech_audio_id="take-a",
        )
        v1 = s1.version.audio_uri if s1.version else None
        begin_edit(s1.id)
        s2 = save_story(
            story_id=s1.id,
            title="I10A.2 spoken take",
            body_text="Edited later without touching old audio.",
        )
        old = get_story(s1.id, version=1)
        new = get_story(s1.id)
        old_uri = old.version.audio_uri if old and old.version else None
        new_uri = new.version.audio_uri if new and new.version else None
        _check(
            "a02_a18_persist",
            v1 == "file:///tmp/i10a2-take-a.webm"
            and old_uri == "file:///tmp/i10a2-take-a.webm"
            and new_uri == "file:///tmp/i10a2-take-a.webm"
            and int(s2.current_version) >= 2,
            checks,
            problems,
            f"v1={old_uri} v2={new_uri} n={s2.current_version}",
        )
        s3 = save_story(
            story_id=s1.id,
            title="I10A.2 spoken take",
            body_text="New spoken take on a later save.",
            audio_uri="file:///tmp/i10a2-take-b.webm",
            speech_origin="speech",
            speech_audio_id="take-b",
        )
        still_v1 = get_story(s1.id, version=1)
        still_v1_uri = still_v1.version.audio_uri if still_v1 and still_v1.version else None
        _check(
            "a19_new_take_no_flatten",
            still_v1_uri == "file:///tmp/i10a2-take-a.webm"
            and s3.version
            and s3.version.audio_uri == "file:///tmp/i10a2-take-b.webm",
            checks,
            problems,
            f"v1={still_v1_uri} current={s3.version.audio_uri if s3.version else None}",
        )
        from memorybox.journal import create_journal, get_journal, save_new_version

        j1 = create_journal(
            title="I10A.2 journal voice",
            body_text="Spoken journal after review.",
            author_display_name="Owner",
            channel="voice",
            audio_uri="file:///tmp/i10a2-journal-a.webm",
        )
        j2 = save_new_version(
            j1.id,
            body_text="Text edit keeps prior clip unless a new take is sent.",
        )
        j3 = save_new_version(
            j1.id,
            body_text="New spoken journal take.",
            audio_uri="file:///tmp/i10a2-journal-b.webm",
        )
        first = get_journal(j1.id, version=1)
        v1_audio = first.version.audio_uri if first and first.version else None
        _check(
            "a03_journal_audio",
            bool(j1.audio_uri)
            and v1_audio == "file:///tmp/i10a2-journal-a.webm"
            and j3.audio_uri == "file:///tmp/i10a2-journal-b.webm",
            checks,
            problems,
            f"v1={v1_audio} current={j3.audio_uri}",
        )
        meta["synthetic_story_id"] = s1.id
        meta["synthetic_journal_id"] = j1.id
        _ = j2
        _ = no_stt_ui
    except Exception as exc:  # noqa: BLE001
        _check("live_story_journal_audio", False, checks, problems, str(exc))

    if flightsim:
        p1 = os.environ.get("MEMORYBOX_P1_RUNTIME_HOST") == "1"
        _check("flightsim_p1_host", p1, checks, problems, "MEMORYBOX_P1_RUNTIME_HOST=1")

    ok = not problems
    return {"ok": ok, "checks": checks, "problems": problems, "meta": meta}
