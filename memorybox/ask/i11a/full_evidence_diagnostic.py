"""Peggy full-fidelity evidence diagnostic (measurement/export only).

Exports the complete eligible Peggy evidence set *before* OBSERVATION_EXTRACT /
semantic compression. Does not call any LLM. Does not change production I11A
inference behavior.

Exact duplicate elimination and provider-neutral normalization are allowed and
must be counted. Sampling, significance ranking, semantic selection, caps, and
silent discard are forbidden.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from memorybox.ask.authored import authored_email_text
from memorybox.ask.i11a.historian_fixture import HISTORIAN_CASES
from memorybox.ask.i11a.historian_prepared import count_ho_units, count_rollups
from memorybox.ask.i11a.person_context import build_person_context, slim_person_context_for_model
from memorybox.context import AskContext
from memorybox.planner import plan_ask

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_OUT_DIR = _REPO_ROOT / "docs" / "test-output" / "full-evidence"

DIAGNOSTIC_VERSION = 1
CHUNK_TRIGGER_TOKENS = 200_000
CHUNK_TARGET_MIN_TOKENS = 100_000
CHUNK_TARGET_MAX_TOKENS = 150_000

PEGGY_ASK = HISTORIAN_CASES["peggy"]

# Address-centric Peggy gate: Immich may duplicate exact "Peggy George". Prefer
# the unique person holding the archive probe address over an arbitrary row.
_PEGGY_PROBE_ADDR = "peggo417@hotmail.com"


def _pick_exact_peggy_george(people: list[Any]) -> Any | None:
    """Pick Peggy George among exact-name hits; prefer peggo417 claimant."""
    if not people:
        return None
    if len(people) == 1:
        return people[0]
    try:
        from memorybox.db import connection as _db_conn
        from memorybox.person.comm_identity import normalize_handle

        addr = normalize_handle(_PEGGY_PROBE_ADDR)
        claimants: list[Any] = []
        with _db_conn() as conn:
            for cand in people:
                pid = getattr(cand, "id", None)
                if not pid:
                    continue
                hit = conn.execute(
                    """
                    SELECT 1
                    FROM person_contact_points
                    WHERE person_id = %s::uuid
                      AND contact_kind = 'email'
                      AND status = 'confirmed'
                      AND lower(value_text) = %s
                    LIMIT 1
                    """,
                    (pid, addr),
                ).fetchone()
                if hit:
                    claimants.append(cand)
        if len(claimants) == 1:
            return claimants[0]
    except Exception:  # noqa: BLE001
        pass
    return None


_SOURCE_ORDER = (
    "person",
    "sms",
    "email",
    "calendar",
    "story",
    "journal",
    "travel",
    "photo",
    "video",
    "artifact",
    "guided_capture",
    "other",
)


def _utc_stamp(when: datetime | None = None) -> str:
    return (when or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")


def _git_commit() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=_REPO_ROOT,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return out.strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def estimate_tokens(text: str) -> int:
    """Byte/4 token estimate — same convention as historian cloud export."""
    if not text:
        return 0
    return max(1, len(text.encode("utf-8")) // 4)


def estimate_tokens_of(obj: Any) -> int:
    if isinstance(obj, str):
        return estimate_tokens(obj)
    return estimate_tokens(json.dumps(obj, default=str, ensure_ascii=False))


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _stable_item_id(source: str, native_id: str, *, suffix: str = "") -> str:
    base = f"{source}:{native_id}"
    if suffix:
        base = f"{base}:{suffix}"
    return base


def _fingerprint(fields: dict[str, Any]) -> str:
    blob = json.dumps(fields, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _fmt_addrs(val: Any) -> str | None:
    if val is None:
        return None
    if isinstance(val, (list, tuple)):
        bits = [str(x).strip() for x in val if str(x).strip()]
        return ", ".join(bits) or None
    s = str(val).strip()
    return s or None


def _structured_email_fields(payload: dict[str, Any], hit: dict[str, Any]) -> dict[str, Any]:
    """From/To/CC/BCC + parsed addresses only. Never people[]."""
    from_parsed = [
        r
        for r in list((payload or {}).get("from_parsed") or [])
        if isinstance(r, dict)
    ]
    to_parsed = [
        r for r in list((payload or {}).get("to_parsed") or []) if isinstance(r, dict)
    ]
    cc_parsed = [
        r for r in list((payload or {}).get("cc_parsed") or []) if isinstance(r, dict)
    ]
    bcc_parsed = [
        r for r in list((payload or {}).get("bcc_parsed") or []) if isinstance(r, dict)
    ]
    addrs: list[str] = []
    names: list[str] = []
    for rec in from_parsed + to_parsed + cc_parsed + bcc_parsed:
        addr = str(rec.get("normalized") or rec.get("address") or "").strip().lower()
        if addr and "@" in addr and addr not in addrs:
            addrs.append(addr)
        dn = str(rec.get("display_name") or "").strip()
        if dn and dn not in names:
            names.append(dn)
    from_h = hit.get("from_header") or (payload or {}).get("from")
    if not from_h and from_parsed:
        rec = from_parsed[0]
        addr = str(rec.get("address") or rec.get("normalized") or "").strip()
        dn = str(rec.get("display_name") or "").strip()
        from_h = f"{dn} <{addr}>".strip() if dn and addr else addr
    return {
        "from": from_h,
        "to": hit.get("to_header") or _fmt_addrs((payload or {}).get("to")),
        "cc": _fmt_addrs((payload or {}).get("cc")),
        "bcc": _fmt_addrs((payload or {}).get("bcc")),
        "from_parsed": from_parsed,
        "to_parsed": to_parsed,
        "cc_parsed": cc_parsed,
        "addresses": addrs,
        "participants": names,
    }


def _mailbox_skip(payload: dict[str, Any]) -> str | None:
    skip = str(payload.get("mailbox_skip") or payload.get("skip_reason") or "").strip().lower()
    if skip in {"spam", "trash"}:
        return skip
    labels = payload.get("gmail_labels") or payload.get("labels") or []
    blob = " ".join(str(x).lower() for x in labels)
    if "spam" in blob:
        return "spam"
    if "trash" in blob:
        return "trash"
    return None


def _complete_email_body(raw: str) -> tuple[str, dict[str, bool]]:
    """Provider-neutral authored normalization without the production 8k truncate."""
    flags = {"quote_uncertain": False, "boilerplate_uncertain": False}
    authored, base_flags = authored_email_text(raw or "")
    flags.update(base_flags or {})
    # authored_email_text caps at 8000; if the raw body is longer and authored
    # was truncated, re-run quote strip on the full body without the cap.
    if len(raw or "") > 8000 and len(authored) >= 8000:
        from memorybox.explore.email_attach import split_quoted_email

        turns = split_quoted_email(raw or "")
        lead = str((turns[0] or {}).get("body") or "").strip() if turns else (raw or "").strip()
        authored = lead or (raw or "").strip()
        flags["quote_uncertain"] = True
    return authored, flags


def resolve_peggy_plan(*, photo: Any = None, ask: str | None = None) -> Any:
    """Same Peggy ask + Person resolution as the historian fixture, without LLM planning."""
    import os
    from dataclasses import replace

    from memorybox.person import AmbiguousIdentityError, find_ask_person_by_name
    from memorybox.profile import resolve_relational_ask

    ask_text = (ask or PEGGY_ASK).strip()
    ctx = AskContext(session_id=f"full-evidence-{uuid4()}")
    plan = plan_ask(ask_text, ctx)
    rel = resolve_relational_ask(ask_text)
    # FlightSim / P1: never Immich-lazy-seed a single-token \"Peggy\" stub during
    # Full-Evidence — that Person has no email contacts and blocks address-centric
    # retrieve. Prefer existing multi-token People only.
    lazy_seed = (os.environ.get("MEMORYBOX_P1_RUNTIME_HOST") or "").strip().lower() not in {
        "1",
        "true",
        "yes",
    }
    if (
        rel.intent == "none"
        and plan.person_names
        and not getattr(plan, "person_ids", ())
        and (
            plan.want_visual
            or plan.want_communication
            or plan.want_calendar
            or getattr(plan, "want_spoken", False)
        )
    ):
        pids: list[str] = []
        labels: list[str] = []
        for name in sorted(plan.person_names, key=lambda n: (-len(n), n.lower())):
            nl = name.lower()
            if any(nl == lab.lower() or nl in lab.lower() or lab.lower() in nl for lab in labels):
                continue
            try:
                view = find_ask_person_by_name(name, photo=photo, lazy_seed=lazy_seed)
            except AmbiguousIdentityError as amb:
                # Prefer the unique candidate with a confirmed email (address-centric),
                # else exact Peggy George / Peg Legg when present among candidates.
                view = None
                cands = list(getattr(amb, "candidates", None) or [])
                email_hits: list[Any] = []
                try:
                    from memorybox.person import (
                        _person_has_confirmed_email,
                        get_person,
                    )

                    for c in cands:
                        pid = str(
                            (c or {}).get("person_id")
                            or (c or {}).get("id")
                            or ""
                        )
                        if pid and _person_has_confirmed_email(pid):
                            email_hits.append(pid)
                    if len(set(email_hits)) == 1:
                        view = get_person(email_hits[0])
                    if view is None:
                        # Prefer exact George/Legg from the ambiguity list before
                        # another Ask round-trip (FlightSim multi-Peggy* noise).
                        for prefer in ("Peggy George", "Peg Legg"):
                            prefer_l = prefer.lower()
                            hits = [
                                str(
                                    (c or {}).get("person_id")
                                    or (c or {}).get("id")
                                    or ""
                                )
                                for c in cands
                                if str((c or {}).get("display_name") or "")
                                .strip()
                                .lower()
                                == prefer_l
                            ]
                            hits = [h for h in hits if h]
                            if len(set(hits)) == 1:
                                view = get_person(hits[0])
                                break
                except Exception:  # noqa: BLE001
                    view = None
                if view is None:
                    # Exact ledger Person (cold-created Peggy George) may not be in
                    # the AmbiguousIdentity candidate list yet — prefer it over abort.
                    # Multiple Immich "Peggy George" rows: prefer unique peggo417
                    # claimant (same rule as address-centric e2e bootstrap).
                    try:
                        from memorybox.person import list_people_by_exact_name

                        exact = list_people_by_exact_name("Peggy George")
                        view = _pick_exact_peggy_george(exact)
                    except Exception:  # noqa: BLE001
                        view = None
                if view is None:
                    for prefer in ("Peggy George", "Peg Legg"):
                        try:
                            view = find_ask_person_by_name(
                                prefer, photo=photo, lazy_seed=False
                            )
                        except AmbiguousIdentityError:
                            view = None
                        except Exception:  # noqa: BLE001
                            view = None
                        if view is not None:
                            break
            except Exception:  # noqa: BLE001
                view = None
            if not view:
                continue
            pids.append(view.id)
            labels.append(view.display_name or name)
        if not pids and any(
            "peggy" in str(n).lower() or "peg legg" in str(n).lower()
            for n in (plan.person_names or ())
        ):
            # Last resort: Peggy George (unique, or unique peggo417 claimant when
            # Immich duplicated the exact display name).
            try:
                from memorybox.person import list_people_by_exact_name

                exact = list_people_by_exact_name("Peggy George")
                picked = _pick_exact_peggy_george(exact)
                if picked is not None:
                    pids = [picked.id]
                    labels = [picked.display_name or "Peggy George"]
            except Exception:  # noqa: BLE001
                pass
        if pids:
            note = (
                "resolved_person_ids_for_comms"
                if plan.want_communication or plan.want_calendar
                else "resolved_person_ids_for_visual"
            )
            plan = replace(
                plan,
                person_ids=tuple(dict.fromkeys(pids)),
                person_names=tuple(dict.fromkeys(labels or list(plan.person_names))),
                notes=tuple(list(plan.notes) + [note, "full_evidence_diagnostic"]),
            )
    return plan


def _payload_for(evidence_id: str) -> dict[str, Any]:
    try:
        from uuid import UUID

        from memorybox.ingest.store import get_evidence

        row = get_evidence(UUID(str(evidence_id)))
    except Exception:  # noqa: BLE001
        return {}
    if not row:
        return {}
    payload = row.get("payload_json") or row.get("payload") or {}
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:  # noqa: BLE001
            payload = {}
    return payload if isinstance(payload, dict) else {}


def _story_bodies(story_ids: list[str]) -> dict[str, dict[str, Any]]:
    if not story_ids:
        return {}
    try:
        from memorybox.db import connection
    except Exception:  # noqa: BLE001
        return {}
    out: dict[str, dict[str, Any]] = {}
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT
                s.id AS story_id,
                COALESCE(sv.title, s.title) AS title,
                sv.body_text,
                (
                    SELECT string_agg(b.text, E'\\n')
                    FROM story_version_blocks b
                    WHERE b.version_id = sv.id AND COALESCE(b.text, '') <> ''
                ) AS block_text
            FROM stories s
            JOIN story_versions sv ON sv.id = s.current_saved_version_id
            WHERE s.id = ANY(%s)
            """,
            (story_ids,),
        ).fetchall()
        for r in rows:
            body = (r["body_text"] or r.get("block_text") or "") or ""
            out[str(r["story_id"])] = {
                "title": r.get("title"),
                "body_text": body,
            }
    return out


def _journal_bodies(journal_ids: list[str]) -> dict[str, dict[str, Any]]:
    if not journal_ids:
        return {}
    try:
        from memorybox.db import connection
    except Exception:  # noqa: BLE001
        return {}
    out: dict[str, dict[str, Any]] = {}
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT
                j.id AS journal_id,
                j.title,
                jv.body_text
            FROM journal_entries j
            JOIN journal_versions jv
              ON jv.journal_id = j.id
             AND jv.version = j.current_saved_version
             AND jv.lifecycle = 'saved'
            WHERE j.id = ANY(%s)
            """,
            (journal_ids,),
        ).fetchall()
        for r in rows:
            out[str(r["journal_id"])] = {
                "title": r.get("title"),
                "body_text": r.get("body_text") or "",
            }
    return out


def retrieve_eligible_hits(
    plan: Any,
    *,
    photo: Any,
    video: Any | None = None,
) -> dict[str, Any]:
    """Retrieve the complete eligible set for broad Person synthesis (no year-fair / no family caps)."""
    from memorybox.ask import retrieve as R

    _rq_tok = None
    try:
        _rq_tok = R.begin_retrieve_accounting()
    except Exception:  # noqa: BLE001
        _rq_tok = None

    evidence: list[Any] = []
    photos: list[Any] = []
    videos: list[Any] = []
    stories: list[Any] = []
    journals: list[Any] = []
    artifacts: list[Any] = []
    guided: list[Any] = []
    photo_status: dict[str, Any] = {}
    video_status: dict[str, Any] = {}

    try:
        if plan.want_communication or plan.want_calendar:
            evidence = list(R.search_evidence_pg(plan) or [])
        if plan.want_still or plan.want_photo:
            # limit=0 → unbounded person library (no year-fair sample for tell).
            photos, photo_status = R.search_photos(plan, photo, limit=0)
            photos = list(photos or [])
        if getattr(plan, "want_spoken", False):
            try:
                from memorybox.speech.retrieve import search_spoken_moments

                spoken_rows = search_spoken_moments(plan)
                videos.extend(
                    [
                        R.VideoHit(
                            provider_key=str(r.get("provider_key") or "hvrt"),
                            external_id=str(r.get("external_id") or r.get("id") or ""),
                            video_external_id=str(r.get("video_external_id") or ""),
                            start_sec=float(r.get("start_sec") or 0),
                            end_sec=float(r.get("end_sec") or 0),
                            label=str(r.get("label") or "Spoken moment"),
                            play_url=r.get("play_url"),
                            identity_trust=str(r.get("identity_trust") or "candidate"),
                            mb_person_id=r.get("mb_person_id"),
                            attribution=str(r.get("attribution") or "spoken_moment"),
                            spoken_text=r.get("spoken_text"),
                        )
                        for r in spoken_rows
                    ]
                )
            except Exception as exc:  # noqa: BLE001
                video_status["spoken_error"] = str(exc)
        if plan.want_video:
            try:
                appearance, appear_status = R.search_videos(
                    plan, video, photo=photo, limit=0
                )
                video_status["appearance"] = appear_status
                seen = {v.external_id for v in videos}
                videos.extend([v for v in (appearance or []) if v.external_id not in seen])
            except Exception as exc:  # noqa: BLE001
                video_status["video_error"] = str(exc)
        immich_va = R.video_assets_from_photo_hits(photos)
        seen_va = {v.external_id for v in videos}
        videos.extend([v for v in immich_va if v.external_id not in seen_va])
        if getattr(plan, "want_story", False):
            stories = list(R.search_stories(plan, limit=0) or [])
        if getattr(plan, "want_journal", False):
            journals = list(R.search_journals(plan, limit=0) or [])
        if getattr(plan, "want_artifact", False):
            artifacts = list(R.search_artifacts(plan, limit=0) or [])
        if getattr(plan, "want_guided_capture", False):
            guided = list(R.search_guided_capture(plan, limit=0) or [])
    finally:
        retrieve_diag = None
        try:
            retrieve_diag = R.retrieve_accounting_snapshot()
        except Exception:  # noqa: BLE001
            retrieve_diag = None
        if _rq_tok is not None:
            try:
                R.reset_retrieve_accounting(_rq_tok)
            except Exception:  # noqa: BLE001
                pass

    return {
        "evidence": evidence,
        "photos": photos,
        "videos": videos,
        "stories": stories,
        "journals": journals,
        "artifacts": artifacts,
        "guided_capture": guided,
        "photo_status": photo_status,
        "video_status": video_status,
        "retrieve_diag": retrieve_diag,
    }


def _normalize_comm_hit(hit: Any, *, retrieved_index: int) -> tuple[dict[str, Any] | None, str | None]:
    d = hit.to_dict() if hasattr(hit, "to_dict") else dict(hit)
    eid = str(d.get("evidence_id") or "")
    payload = getattr(hit, "payload", None)
    if not isinstance(payload, dict) or not payload:
        payload = d.get("payload") if isinstance(d.get("payload"), dict) else {}
    if eid and not payload:
        payload = _payload_for(eid)
    channel = str(d.get("channel") or (payload or {}).get("evidence_channel") or "").lower()
    kind = str(d.get("evidence_kind") or "").lower()

    if channel == "calendar" or kind == "calendar_event":
        skip = None
        title = str(
            (payload or {}).get("title")
            or d.get("summary")
            or ""
        )
        body = str(
            (payload or {}).get("description")
            or (payload or {}).get("body_text")
            or d.get("excerpt")
            or ""
        )
        location = str((payload or {}).get("location") or "") or None
        participants = [
            str(p)
            for p in (
                (payload or {}).get("attendees")
                or d.get("people")
                or []
            )
            if str(p).strip()
        ]
        org = str((payload or {}).get("organizer") or "").strip()
        if org and org not in participants:
            participants.insert(0, org)
        when = str(d.get("sent_at") or (payload or {}).get("start") or "") or None
        item = {
            "item_id": _stable_item_id("calendar", eid),
            "source": "calendar",
            "native_id": eid,
            "timestamp": when,
            "title": title,
            "body": body,
            "location": location,
            "participants": participants,
            "thread_id": d.get("thread_id") or (payload or {}).get("event_uid"),
            "normalization": {"provider_neutral": True},
            "retrieved_index": retrieved_index,
        }
        item["content_fingerprint"] = _fingerprint(
            {
                "source": "calendar",
                "title": title,
                "body": body,
                "timestamp": when,
                "location": location,
                "participants": participants,
            }
        )
        return item, skip

    skip = _mailbox_skip(payload or {})
    if skip:
        return None, skip

    is_sms = channel in {"sms", "text", "imessage", "mms", "rcs"} or kind in {
        "sms_message",
        "text_message",
    }
    raw_body = str((payload or {}).get("body_text") or d.get("excerpt") or "")
    when = str(d.get("sent_at") or (payload or {}).get("sent_at") or "") or None
    thread_id = (
        d.get("thread_id")
        or (payload or {}).get("thread_id")
        or (payload or {}).get("chat_identifier")
        or (payload or {}).get("chat_id")
    )
    people = [str(p) for p in (d.get("people") or (payload or {}).get("participants") or []) if str(p).strip()]

    if is_sms:
        item = {
            "item_id": _stable_item_id("sms", eid),
            "source": "sms",
            "native_id": eid,
            "timestamp": when,
            "participants": people,
            "body": raw_body,
            "thread_id": thread_id,
            "direction": d.get("direction") or (payload or {}).get("direction"),
            "sender_name": (payload or {}).get("sender_name"),
            "attachments": d.get("attachments") or (payload or {}).get("attachments") or [],
            "normalization": {"provider_neutral": True, "exact_body": True},
            "retrieved_index": retrieved_index,
        }
        item["content_fingerprint"] = _fingerprint(
            {
                "source": "sms",
                "body": raw_body,
                "timestamp": when,
                "thread_id": thread_id,
                "participants": people,
                "direction": item.get("direction"),
            }
        )
        return item, None

    # email (default for remaining communication)
    subject = str((payload or {}).get("subject") or d.get("summary") or "")
    body, flags = _complete_email_body(raw_body)
    structured = _structured_email_fields(payload or {}, d)
    from_h = structured["from"]
    to_h = structured["to"]
    cc_h = structured["cc"]
    item = {
        "item_id": _stable_item_id("email", eid),
        "source": "email",
        "native_id": eid,
        "evidence_id": eid,
        "timestamp": when,
        "from": from_h,
        "to": to_h,
        "cc": cc_h,
        "bcc": structured["bcc"],
        "from_parsed": structured["from_parsed"],
        "to_parsed": structured["to_parsed"],
        "addresses": structured["addresses"],
        "subject": subject,
        "body": body,
        "raw_body_chars": len(raw_body),
        "thread_id": thread_id,
        "participants": structured["participants"],
        "direction": d.get("direction") or (payload or {}).get("direction"),
        "attachments": d.get("attachments") or (payload or {}).get("attachments") or [],
        "normalization": {
            "provider_neutral": True,
            "authored_email": True,
            **flags,
        },
        "retrieved_index": retrieved_index,
    }
    item["content_fingerprint"] = _fingerprint(
        {
            "source": "email",
            "subject": subject,
            "body": body,
            "timestamp": when,
            "from": from_h,
            "to": to_h,
            "cc": cc_h,
            "thread_id": thread_id,
        }
    )
    return item, None


def _travel_from_email_item(item: dict[str, Any]) -> dict[str, Any] | None:
    if item.get("source") != "email":
        return None
    try:
        from memorybox.ask.travel import extract_travel
    except Exception:  # noqa: BLE001
        return None
    facts = extract_travel(
        subject=str(item.get("subject") or ""),
        body=str(item.get("body") or ""),
        source_unit_id=str(item.get("item_id") or ""),
        source_evidence_id=str(item.get("native_id") or ""),
    )
    if not facts:
        return None
    route = None
    if facts.get("origin") and facts.get("destination"):
        route = f"{facts['origin']} → {facts['destination']}"
    content_bits = [
        facts.get("travel_kind"),
        route or facts.get("property"),
        facts.get("start"),
        facts.get("confirmation"),
    ]
    body = " ".join(str(x) for x in content_bits if x)
    tid = _stable_item_id(
        "travel",
        str(item.get("native_id") or ""),
        suffix=str(facts.get("travel_kind") or "trip"),
    )
    out = {
        "item_id": tid,
        "source": "travel",
        "native_id": item.get("native_id"),
        "timestamp": facts.get("start") or item.get("timestamp"),
        "title": facts.get("travel_kind") or "travel",
        "body": body,
        "origin": facts.get("origin"),
        "destination": facts.get("destination"),
        "property": facts.get("property"),
        "confirmation": facts.get("confirmation"),
        "derived_from": item.get("item_id"),
        "thread_id": item.get("thread_id"),
        "normalization": {"derived_from_email": True, "never_replaces_original": True},
        "retrieved_index": item.get("retrieved_index"),
    }
    out["content_fingerprint"] = _fingerprint(
        {
            "source": "travel",
            "body": body,
            "derived_from": item.get("item_id"),
            "travel_kind": facts.get("travel_kind"),
        }
    )
    return out


def _normalize_photo(hit: Any, *, retrieved_index: int) -> dict[str, Any]:
    d = hit.to_dict() if hasattr(hit, "to_dict") else dict(hit)
    eid = str(d.get("external_id") or "")
    trust = str(d.get("identity_trust") or "")
    item = {
        "item_id": _stable_item_id("photo", eid),
        "source": "photo",
        "native_id": eid,
        "timestamp": d.get("taken_at"),
        "people": list(d.get("people") or []),
        "mb_person_id": d.get("mb_person_id"),
        "mb_person_name": d.get("mb_person_name"),
        "identity_trust": trust,
        "validated_observation": trust in {"confirmed", "trusted_provider"},
        "place": d.get("place") or d.get("location"),
        "city": d.get("city"),
        "state": d.get("state"),
        "country": d.get("country"),
        "latitude": d.get("latitude"),
        "longitude": d.get("longitude"),
        "original_filename": d.get("original_filename"),
        "media_type": d.get("media_type") or "image",
        "exif": d.get("exif") if isinstance(d.get("exif"), dict) else None,
        "faces": d.get("faces") if isinstance(d.get("faces"), list) else None,
        "thumb_url": d.get("thumb_url"),
        "web_url": d.get("web_url"),
        "normalization": {"provider_neutral": True, "metadata_only": True},
        "retrieved_index": retrieved_index,
    }
    item["content_fingerprint"] = _fingerprint(
        {
            "source": "photo",
            "native_id": eid,
            "timestamp": item.get("timestamp"),
            "place": item.get("place"),
            "latitude": item.get("latitude"),
            "longitude": item.get("longitude"),
            "original_filename": item.get("original_filename"),
            "identity_trust": trust,
        }
    )
    return item


def _normalize_video(hit: Any, *, retrieved_index: int) -> dict[str, Any]:
    d = hit.to_dict() if hasattr(hit, "to_dict") else dict(hit)
    eid = str(d.get("external_id") or "")
    trust = str(d.get("identity_trust") or "")
    spoken = d.get("spoken_text")
    item = {
        "item_id": _stable_item_id("video", eid),
        "source": "video",
        "native_id": eid,
        "timestamp": d.get("taken_at"),
        "label": d.get("label"),
        "spoken_text": spoken,
        "body": spoken or "",
        "mb_person_id": d.get("mb_person_id"),
        "mb_person_name": d.get("mb_person_name"),
        "identity_trust": trust,
        "validated_observation": trust in {"confirmed", "trusted_provider"}
        or bool(spoken),
        "start_sec": d.get("start_sec"),
        "end_sec": d.get("end_sec"),
        "duration_sec": d.get("duration_sec"),
        "place": d.get("place"),
        "city": d.get("city"),
        "state": d.get("state"),
        "latitude": d.get("latitude"),
        "longitude": d.get("longitude"),
        "original_filename": d.get("original_filename"),
        "attribution": d.get("attribution"),
        "play_url": d.get("play_url"),
        "thumb_url": d.get("thumb_url"),
        "normalization": {"provider_neutral": True},
        "retrieved_index": retrieved_index,
    }
    item["content_fingerprint"] = _fingerprint(
        {
            "source": "video",
            "native_id": eid,
            "timestamp": item.get("timestamp"),
            "spoken_text": spoken,
            "start_sec": item.get("start_sec"),
            "end_sec": item.get("end_sec"),
            "identity_trust": trust,
        }
    )
    return item


def _normalize_story(hit: Any, body_map: dict[str, dict[str, Any]], *, retrieved_index: int) -> dict[str, Any]:
    d = hit.to_dict() if hasattr(hit, "to_dict") else dict(hit)
    sid = str(d.get("story_id") or "")
    full = body_map.get(sid) or {}
    body = str(full.get("body_text") or d.get("excerpt") or "")
    title = full.get("title") or d.get("title")
    item = {
        "item_id": _stable_item_id("story", sid),
        "source": "story",
        "native_id": sid,
        "timestamp": d.get("taken_at"),
        "title": title,
        "body": body,
        "narrator_person_id": d.get("narrator_person_id"),
        "narrator_display_name": d.get("narrator_display_name"),
        "people": list(d.get("people") or []),
        "attribution": d.get("attribution"),
        "version": d.get("version"),
        "normalization": {
            "provider_neutral": True,
            "complete_authored_text": True,
            "body_from_db": bool(full.get("body_text")),
        },
        "retrieved_index": retrieved_index,
    }
    item["content_fingerprint"] = _fingerprint(
        {
            "source": "story",
            "native_id": sid,
            "title": title,
            "body": body,
            "version": d.get("version"),
        }
    )
    return item


def _normalize_journal(hit: Any, body_map: dict[str, dict[str, Any]], *, retrieved_index: int) -> dict[str, Any]:
    d = hit.to_dict() if hasattr(hit, "to_dict") else dict(hit)
    jid = str(d.get("journal_id") or "")
    full = body_map.get(jid) or {}
    body = str(full.get("body_text") or d.get("excerpt") or "")
    title = full.get("title") or d.get("title")
    when = d.get("described_start_date") or d.get("captured_at")
    item = {
        "item_id": _stable_item_id("journal", jid),
        "source": "journal",
        "native_id": jid,
        "timestamp": when,
        "title": title,
        "body": body,
        "author_person_id": d.get("author_person_id"),
        "author_display_name": d.get("author_display_name"),
        "captured_at": d.get("captured_at"),
        "described_start_date": d.get("described_start_date"),
        "described_end_date": d.get("described_end_date"),
        "described_precision": d.get("described_precision"),
        "attribution": d.get("attribution"),
        "version": d.get("version"),
        "normalization": {
            "provider_neutral": True,
            "complete_authored_text": True,
            "body_from_db": bool(full.get("body_text")),
        },
        "retrieved_index": retrieved_index,
    }
    item["content_fingerprint"] = _fingerprint(
        {
            "source": "journal",
            "native_id": jid,
            "title": title,
            "body": body,
            "version": d.get("version"),
        }
    )
    return item


def _normalize_artifact(row: dict[str, Any], *, retrieved_index: int) -> dict[str, Any]:
    d = dict(row or {})
    aid = str(d.get("artifact_id") or d.get("id") or d.get("external_id") or "")
    title = d.get("title") or d.get("display_name") or d.get("label")
    body = str(
        d.get("description")
        or d.get("summary")
        or d.get("body_text")
        or d.get("excerpt")
        or ""
    )
    item = {
        "item_id": _stable_item_id("artifact", aid or f"idx{retrieved_index}"),
        "source": "artifact",
        "native_id": aid,
        "timestamp": d.get("created_at") or d.get("updated_at") or d.get("taken_at"),
        "title": title,
        "body": body,
        "metadata": {
            k: v
            for k, v in d.items()
            if k
            not in {
                "description",
                "summary",
                "body_text",
                "excerpt",
                "title",
                "display_name",
                "label",
            }
        },
        "normalization": {"provider_neutral": True},
        "retrieved_index": retrieved_index,
    }
    item["content_fingerprint"] = _fingerprint(
        {"source": "artifact", "native_id": aid, "title": title, "body": body}
    )
    return item


def _normalize_guided(row: dict[str, Any], *, retrieved_index: int) -> dict[str, Any]:
    d = dict(row or {})
    gid = str(d.get("response_id") or d.get("id") or f"gc{retrieved_index}")
    body = str(d.get("response_text") or d.get("body_text") or d.get("text") or "")
    item = {
        "item_id": _stable_item_id("guided_capture", gid),
        "source": "guided_capture",
        "native_id": gid,
        "timestamp": d.get("captured_at") or d.get("created_at"),
        "title": d.get("prompt_label") or d.get("title"),
        "body": body,
        "people": d.get("people") or [],
        "normalization": {"provider_neutral": True, "complete_authored_text": True},
        "retrieved_index": retrieved_index,
    }
    item["content_fingerprint"] = _fingerprint(
        {"source": "guided_capture", "native_id": gid, "body": body, "title": item.get("title")}
    )
    return item


def _person_fact_items(person_context: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    focals = list(person_context.get("focal_subjects") or [])
    for card in focals:
        if not isinstance(card, dict):
            continue
        pid = str(card.get("person_id") or "")
        facts = {
            "display_name": card.get("display_name"),
            "birth_date": card.get("birth_date"),
            "death_date": card.get("death_date"),
            "age_at_period": card.get("age_at_period"),
            "aliases": card.get("aliases") or [],
            "communication_identities": card.get("communication_identities") or [],
            "known_relationships": card.get("known_relationships") or [],
            "inferred_relationships": card.get("inferred_relationships") or [],
            "allowed_relationship_labels": card.get("allowed_relationship_labels") or [],
        }
        body = json.dumps(facts, indent=2, default=str, ensure_ascii=False)
        item = {
            "item_id": _stable_item_id("person", pid or "focal"),
            "source": "person",
            "native_id": pid,
            "timestamp": card.get("birth_date"),
            "title": f"Person canonical facts — {card.get('display_name') or pid}",
            "body": body,
            "facts": facts,
            "normalization": {"canonical_person_facts": True},
            "retrieved_index": 0,
        }
        item["content_fingerprint"] = _fingerprint(
            {"source": "person", "native_id": pid, "facts": facts}
        )
        items.append(item)
    return items


def normalize_retrieved(
    retrieved: dict[str, Any],
    *,
    person_context: dict[str, Any],
) -> dict[str, Any]:
    """Normalize retrieved hits → full-fidelity items; exact-dedupe with counts."""
    retrieved_counts: dict[str, int] = defaultdict(int)
    ineligible: dict[str, int] = defaultdict(int)
    raw_items: list[dict[str, Any]] = []

    # Person facts first (not "retrieved" archive rows, but required context).
    for item in _person_fact_items(person_context):
        retrieved_counts["person"] += 1
        raw_items.append(item)

    evidence = list(retrieved.get("evidence") or [])
    for i, hit in enumerate(evidence):
        channel = str(getattr(hit, "channel", None) or "").lower()
        kind = str(getattr(hit, "evidence_kind", None) or "").lower()
        if channel == "calendar" or kind == "calendar_event":
            family = "calendar"
        elif channel in {"sms", "text", "imessage", "mms", "rcs"} or "sms" in kind:
            family = "sms"
        else:
            family = "email"
        retrieved_counts[family] += 1
        item, skip = _normalize_comm_hit(hit, retrieved_index=i)
        if skip:
            ineligible[f"{family}:{skip}"] += 1
            continue
        if not item:
            ineligible[f"{family}:empty"] += 1
            continue
        raw_items.append(item)
        if item["source"] == "email":
            travel = _travel_from_email_item(item)
            if travel:
                raw_items.append(travel)

    photos = list(retrieved.get("photos") or [])
    for i, hit in enumerate(photos):
        retrieved_counts["photo"] += 1
        raw_items.append(_normalize_photo(hit, retrieved_index=i))

    videos = list(retrieved.get("videos") or [])
    for i, hit in enumerate(videos):
        retrieved_counts["video"] += 1
        raw_items.append(_normalize_video(hit, retrieved_index=i))

    stories = list(retrieved.get("stories") or [])
    story_ids = [str(getattr(s, "story_id", "") or "") for s in stories]
    story_bodies = _story_bodies([s for s in story_ids if s])
    for i, hit in enumerate(stories):
        retrieved_counts["story"] += 1
        raw_items.append(_normalize_story(hit, story_bodies, retrieved_index=i))

    journals = list(retrieved.get("journals") or [])
    journal_ids = [str(getattr(j, "journal_id", "") or "") for j in journals]
    journal_bodies = _journal_bodies([j for j in journal_ids if j])
    for i, hit in enumerate(journals):
        retrieved_counts["journal"] += 1
        raw_items.append(_normalize_journal(hit, journal_bodies, retrieved_index=i))

    for i, row in enumerate(retrieved.get("artifacts") or []):
        retrieved_counts["artifact"] += 1
        raw_items.append(_normalize_artifact(row if isinstance(row, dict) else {}, retrieved_index=i))

    for i, row in enumerate(retrieved.get("guided_capture") or []):
        retrieved_counts["guided_capture"] += 1
        raw_items.append(_normalize_guided(row if isinstance(row, dict) else {}, retrieved_index=i))

    # Exact duplicate elimination by content fingerprint (first wins; stable order).
    seen_fp: set[str] = set()
    seen_ids: set[str] = set()
    normalized: list[dict[str, Any]] = []
    dupes_by_source: dict[str, int] = defaultdict(int)
    for item in raw_items:
        src = str(item.get("source") or "other")
        fp = str(item.get("content_fingerprint") or "")
        iid = str(item.get("item_id") or "")
        if iid and iid in seen_ids:
            dupes_by_source[src] += 1
            continue
        if fp and fp in seen_fp:
            dupes_by_source[src] += 1
            continue
        if fp:
            seen_fp.add(fp)
        if iid:
            seen_ids.add(iid)
        normalized.append(item)

    normalized.sort(
        key=lambda it: (
            str(it.get("timestamp") or "9999"),
            _SOURCE_ORDER.index(it["source"])
            if it.get("source") in _SOURCE_ORDER
            else 99,
            str(it.get("item_id") or ""),
        )
    )
    return {
        "items": normalized,
        "retrieved_counts": dict(retrieved_counts),
        "duplicates_removed": dict(dupes_by_source),
        "duplicates_removed_total": int(sum(dupes_by_source.values())),
        "ineligible": dict(ineligible),
        "ineligible_total": int(sum(ineligible.values())),
        "retrieved_total": int(sum(retrieved_counts.values())),
        "normalized_total": len(normalized),
    }


def _item_text_blob(item: dict[str, Any]) -> str:
    """Canonical text representation used for bytes/chars/tokens metrics."""
    return format_item_block(item)


def format_item_block(item: dict[str, Any]) -> str:
    src = str(item.get("source") or "other").upper()
    lines = [f"### [{src}] {item.get('item_id')}"]
    if item.get("evidence_id") or item.get("native_id"):
        lines.append(f"evidence_id: {item.get('evidence_id') or item.get('native_id')}")
    if item.get("timestamp"):
        lines.append(f"timestamp: {item.get('timestamp')}")
    if item.get("title"):
        lines.append(f"title: {item.get('title')}")
    if item.get("subject"):
        lines.append(f"subject: {item.get('subject')}")
    if item.get("from"):
        lines.append(f"from: {item.get('from')}")
    if item.get("to"):
        lines.append(f"to: {item.get('to')}")
    if item.get("cc"):
        lines.append(f"cc: {item.get('cc')}")
    if item.get("participants") and src != "EMAIL":
        lines.append(f"participants: {', '.join(str(p) for p in item['participants'])}")
    if item.get("people") and src != "EMAIL":
        lines.append(f"people: {', '.join(str(p) for p in item['people'])}")
    if src == "EMAIL" and item.get("addresses"):
        lines.append("addresses: " + ", ".join(str(a) for a in item["addresses"]))
    if item.get("location") or item.get("place"):
        lines.append(f"location: {item.get('location') or item.get('place')}")
    if item.get("thread_id"):
        lines.append(f"thread_id: {item.get('thread_id')}")
    if item.get("direction"):
        lines.append(f"direction: {item.get('direction')}")
    if item.get("identity_trust"):
        lines.append(f"identity_trust: {item.get('identity_trust')}")
    if item.get("validated_observation") is not None and item.get("source") in {
        "photo",
        "video",
    }:
        lines.append(f"validated_observation: {item.get('validated_observation')}")
    if item.get("derived_from"):
        lines.append(f"derived_from: {item.get('derived_from')}")
    body = item.get("body")
    if body is None and item.get("spoken_text"):
        body = item.get("spoken_text")
    if body is not None and str(body) != "":
        lines.append("body:")
        lines.append(str(body))
    elif item.get("source") == "photo":
        meta_bits = []
        for k in (
            "original_filename",
            "media_type",
            "city",
            "state",
            "country",
            "latitude",
            "longitude",
            "mb_person_name",
        ):
            if item.get(k) is not None and item.get(k) != "":
                meta_bits.append(f"{k}={item.get(k)}")
        if meta_bits:
            lines.append("metadata: " + "; ".join(meta_bits))
        if item.get("exif"):
            lines.append(f"exif: {json.dumps(item['exif'], default=str, ensure_ascii=False)}")
    lines.append("")
    return "\n".join(lines)


def format_full_evidence_text(
    items: list[dict[str, Any]],
    *,
    ask: str,
    person_context: dict[str, Any],
    plan_snapshot: dict[str, Any] | None = None,
) -> str:
    header = [
        "PEGGY FULL-FIDELITY EVIDENCE DIAGNOSTIC",
        f"diagnostic_version: {DIAGNOSTIC_VERSION}",
        f"ask: {ask}",
        f"normalized_item_count: {len(items)}",
        "",
        "=== PERSON CONTEXT ===",
        json.dumps(slim_person_context_for_model(person_context), indent=2, default=str, ensure_ascii=False),
        "",
    ]
    if plan_snapshot:
        header.extend(
            [
                "=== PLAN SCOPE (resolved) ===",
                json.dumps(
                    {
                        "person_ids": plan_snapshot.get("person_ids"),
                        "person_names": plan_snapshot.get("person_names"),
                        "temporal_windows": plan_snapshot.get("temporal_windows"),
                        "notes": plan_snapshot.get("notes"),
                        "output_mode": plan_snapshot.get("output_mode"),
                    },
                    indent=2,
                    default=str,
                    ensure_ascii=False,
                ),
                "",
            ]
        )
    header.append("=== EVIDENCE (chronological / source-organized) ===")
    header.append("")

    sections: list[str] = ["\n".join(header)]
    # Chronological global listing, with source section markers when source changes.
    last_src = None
    for it in items:
        src = str(it.get("source") or "other")
        if src != last_src:
            sections.append(f"\n----- SOURCE: {src.upper()} -----\n")
            last_src = src
        sections.append(format_item_block(it))
    return "\n".join(sections).rstrip() + "\n"


def format_cloud_paste(
    items: list[dict[str, Any]],
    *,
    ask: str,
    person_context: dict[str, Any],
) -> str:
    """Clean historian prompt: Person context + complete normalized evidence. No traces/embeddings."""
    slim = slim_person_context_for_model(person_context)
    parts = [
        "You are reviewing the complete eligible evidence archive for a Person Ask.",
        "Use only the Person context and evidence below. Do not invent facts.",
        "",
        f"ASK: {ask}",
        "",
        "===== PERSON CONTEXT =====",
        "",
        json.dumps(slim, indent=2, default=str, ensure_ascii=False),
        "",
        "===== COMPLETE NORMALIZED EVIDENCE =====",
        "",
    ]
    for it in items:
        # Strip internal diagnostic-only keys from paste.
        clean = {
            k: v
            for k, v in it.items()
            if k
            not in {
                "content_fingerprint",
                "retrieved_index",
                "normalization",
                "raw_body_chars",
                "metadata",
            }
        }
        parts.append(format_item_block(clean))
    return "\n".join(parts).rstrip() + "\n"


def _item_group_key(item: dict[str, Any]) -> str:
    src = str(item.get("source") or "")
    thread = item.get("thread_id")
    if src in {"email", "sms"} and thread:
        return f"{src}-thread:{thread}"
    if src == "travel" and item.get("derived_from"):
        # Keep travel adjacent to its email by putting in same thread group when possible.
        return f"email-thread:{item.get('thread_id') or item.get('derived_from')}"
    return f"item:{item.get('item_id')}"


def chunk_items(
    items: list[dict[str, Any]],
    *,
    target_min: int = CHUNK_TARGET_MIN_TOKENS,
    target_max: int = CHUNK_TARGET_MAX_TOKENS,
) -> list[dict[str, Any]]:
    """Deterministic chunks ~100–150K tokens; preserve email threads / SMS segments."""
    # Build ordered groups (first-seen order follows chronological item sort).
    groups: list[tuple[str, list[dict[str, Any]]]] = []
    index: dict[str, int] = {}
    for it in items:
        key = _item_group_key(it)
        if key not in index:
            index[key] = len(groups)
            groups.append((key, [it]))
        else:
            groups[index[key]][1].append(it)

    group_sizes = []
    for key, members in groups:
        text = "\n".join(_item_text_blob(m) for m in members)
        group_sizes.append((key, members, estimate_tokens(text), text))

    chunks: list[dict[str, Any]] = []
    cur_members: list[dict[str, Any]] = []
    cur_tokens = 0
    cur_keys: list[str] = []

    def _flush() -> None:
        nonlocal cur_members, cur_tokens, cur_keys
        if not cur_members:
            return
        text = "\n".join(_item_text_blob(m) for m in cur_members)
        chunks.append(
            {
                "chunk_index": len(chunks),
                "group_keys": list(cur_keys),
                "item_ids": [str(m.get("item_id")) for m in cur_members],
                "item_count": len(cur_members),
                "estimated_tokens": estimate_tokens(text),
                "items": list(cur_members),
                "text": text,
            }
        )
        cur_members = []
        cur_tokens = 0
        cur_keys = []

    for key, members, gtok, _text in group_sizes:
        # Oversized single group stays intact in its own chunk.
        if not cur_members:
            cur_members.extend(members)
            cur_tokens = gtok
            cur_keys.append(key)
            if cur_tokens >= target_min:
                # Prefer flush near target_max; if still under max, keep accumulating.
                if cur_tokens >= target_max:
                    _flush()
            continue
        if cur_tokens + gtok > target_max and cur_tokens >= target_min:
            _flush()
            cur_members.extend(members)
            cur_tokens = gtok
            cur_keys.append(key)
            if cur_tokens >= target_max:
                _flush()
            continue
        if cur_tokens + gtok > target_max and cur_tokens < target_min:
            # Would exceed max before reaching min — flush anyway to respect max when possible,
            # unless current is empty (handled above). Keep group intact.
            _flush()
            cur_members.extend(members)
            cur_tokens = gtok
            cur_keys.append(key)
            continue
        cur_members.extend(members)
        cur_tokens += gtok
        cur_keys.append(key)
        if cur_tokens >= target_max:
            _flush()
    _flush()
    return chunks


def _dates_from_items(items: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    dates = []
    for it in items:
        ts = str(it.get("timestamp") or "").strip()
        if ts:
            dates.append(ts)
    if not dates:
        return None, None
    dates.sort()
    return dates[0], dates[-1]


def _source_metrics(items: list[dict[str, Any]], *, retrieved_counts: dict[str, int], duplicates: dict[str, int]) -> dict[str, Any]:
    by_src: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for it in items:
        by_src[str(it.get("source") or "other")].append(it)
    out: dict[str, Any] = {}
    all_sources = sorted(
        set(by_src) | set(retrieved_counts) | set(duplicates),
        key=lambda s: (_SOURCE_ORDER.index(s) if s in _SOURCE_ORDER else 99, s),
    )
    for src in all_sources:
        members = by_src.get(src) or []
        text = "\n".join(_item_text_blob(m) for m in members)
        b = text.encode("utf-8")
        earliest, latest = _dates_from_items(members)
        out[src] = {
            "retrieved_item_count": int(retrieved_counts.get(src) or 0),
            "normalized_item_count": len(members),
            "exact_duplicates_removed": int(duplicates.get(src) or 0),
            "bytes": len(b),
            "characters": len(text),
            "estimated_tokens": estimate_tokens(text) if text else 0,
            "earliest_date": earliest,
            "latest_date": latest,
        }
    return out


def _total_metrics(items: list[dict[str, Any]], *, retrieved_total: int, duplicates_total: int) -> dict[str, Any]:
    text = "\n".join(_item_text_blob(m) for m in items)
    b = text.encode("utf-8")
    earliest, latest = _dates_from_items(items)
    return {
        "retrieved_item_count": retrieved_total,
        "normalized_item_count": len(items),
        "exact_duplicates_removed": duplicates_total,
        "bytes": len(b),
        "characters": len(text),
        "estimated_tokens": estimate_tokens(text) if text else 0,
        "earliest_date": earliest,
        "latest_date": latest,
    }


def downstream_comparison_from_fixture(fixture_path: Path | str | None) -> dict[str, Any]:
    """Current obs / roll-up / HO sizes from a frozen HISTFIX (no LLM)."""
    if not fixture_path:
        return {
            "available": False,
            "reason": "no_fixture_provided",
        }
    path = Path(fixture_path)
    if not path.is_file():
        return {"available": False, "reason": f"fixture_not_found:{path}"}
    from memorybox.ask.i11a.historian_fixture import load_fixture

    fixture = load_fixture(path)
    prepared = fixture.get("prepared") or {}
    eligible = prepared.get("eligible_observations") or []
    ru = prepared.get("semantic_rollups") or {}
    ho = prepared.get("semantic_higher_order") or {}
    stats = prepared.get("ask_relative_payload_stats") or {}

    obs_text = json.dumps(eligible, default=str, ensure_ascii=False)
    ru_text = json.dumps(ru, default=str, ensure_ascii=False)
    ho_text = json.dumps(ho, default=str, ensure_ascii=False)
    return {
        "available": True,
        "fixture_path": str(path),
        "fixture_input_sha256": fixture.get("input_sha256"),
        "fixture_case_id": fixture.get("case_id"),
        "validated_observation_count": len(eligible),
        "validated_observation_estimated_tokens": estimate_tokens(obs_text),
        "validated_observation_bytes": len(obs_text.encode("utf-8")),
        "rollup_count": count_rollups(ru if isinstance(ru, dict) else {}),
        "rollup_estimated_tokens": estimate_tokens(ru_text),
        "rollup_bytes": len(ru_text.encode("utf-8")),
        "ho_count": count_ho_units(ho if isinstance(ho, dict) else {}),
        "ho_estimated_tokens": estimate_tokens(ho_text),
        "ho_bytes": len(ho_text.encode("utf-8")),
        "ask_relative_payload_stats": stats,
    }


def build_chunk_manifest(
    items: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
) -> dict[str, Any]:
    all_ids = [str(it.get("item_id")) for it in items]
    chunk_ids: list[str] = []
    for ch in chunks:
        chunk_ids.extend(list(ch.get("item_ids") or []))
    union_sorted = sorted(set(chunk_ids))
    all_sorted = sorted(set(all_ids))
    missing = sorted(set(all_sorted) - set(union_sorted))
    extra = sorted(set(union_sorted) - set(all_sorted))
    # Multiset equality (no silent drop, no silent dup across chunks).
    from collections import Counter

    c_all = Counter(all_ids)
    c_chunk = Counter(chunk_ids)
    multiset_ok = c_all == c_chunk
    return {
        "manifest_version": 1,
        "normalized_item_count": len(items),
        "chunk_count": len(chunks),
        "union_item_count": len(union_sorted),
        "union_equals_normalized": union_sorted == all_sorted and multiset_ok,
        "multiset_equal": multiset_ok,
        "missing_item_ids": missing,
        "extra_item_ids": extra,
        "normalized_content_sha256": _sha256_text(
            json.dumps([it.get("content_fingerprint") for it in items], ensure_ascii=False)
        ),
        "chunks_content_sha256": _sha256_text(
            json.dumps(
                [fp for ch in chunks for fp in [
                    next(
                        (
                            it.get("content_fingerprint")
                            for it in items
                            if it.get("item_id") == iid
                        ),
                        "",
                    )
                    for iid in (ch.get("item_ids") or [])
                ]],
                ensure_ascii=False,
            )
        ),
        "chunks": [
            {
                "chunk_index": ch["chunk_index"],
                "filename": ch.get("filename"),
                "item_count": ch["item_count"],
                "estimated_tokens": ch["estimated_tokens"],
                "item_ids": ch["item_ids"],
                "group_keys": ch.get("group_keys"),
            }
            for ch in chunks
        ],
    }


def run_full_evidence_diagnostic(
    *,
    out_dir: Path | str | None = None,
    ask: str | None = None,
    fixture_path: Path | str | None = None,
    photo: Any | None = None,
    video: Any | None = None,
    plan: Any | None = None,
    person_context: dict[str, Any] | None = None,
    retrieved: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build PEGGY_FULL_EVIDENCE* artifacts. Never calls an LLM."""
    from memorybox.ask.deps import build_photo, build_video
    from memorybox.ask.i11a.historian_prepared import plan_to_snapshot

    out = Path(out_dir) if out_dir else _DEFAULT_OUT_DIR
    out.mkdir(parents=True, exist_ok=True)
    ask_text = (ask or PEGGY_ASK).strip()
    stamp = _utc_stamp()
    commit = _git_commit()

    photo = photo if photo is not None else build_photo()
    video = video if video is not None else build_video()

    if plan is None:
        plan = resolve_peggy_plan(photo=photo, ask=ask_text)
    if person_context is None:
        person_context = build_person_context(plan)
    if retrieved is None:
        retrieved = retrieve_eligible_hits(plan, photo=photo, video=video)

    norm = normalize_retrieved(retrieved, person_context=person_context)
    items = list(norm["items"])

    full_text = format_full_evidence_text(
        items,
        ask=ask_text,
        person_context=person_context,
        plan_snapshot=plan_to_snapshot(plan) if hasattr(plan, "__dataclass_fields__") or hasattr(plan, "person_ids") else {},
    )
    paste = format_cloud_paste(items, ask=ask_text, person_context=person_context)

    evidence_path = out / "PEGGY_FULL_EVIDENCE.txt"
    paste_path = out / "CLOUDREQ_peggy_full_evidence_paste.txt"
    metrics_path = out / "PEGGY_FULL_EVIDENCE_METRICS.json"

    evidence_path.write_text(full_text, encoding="utf-8")
    paste_path.write_text(paste, encoding="utf-8")

    by_source = _source_metrics(
        items,
        retrieved_counts=norm["retrieved_counts"],
        duplicates=norm["duplicates_removed"],
    )
    totals = _total_metrics(
        items,
        retrieved_total=norm["retrieved_total"],
        duplicates_total=norm["duplicates_removed_total"],
    )
    downstream = downstream_comparison_from_fixture(fixture_path)

    chunk_files: list[str] = []
    chunk_manifest_path = None
    chunks: list[dict[str, Any]] = []
    if totals["estimated_tokens"] > CHUNK_TRIGGER_TOKENS:
        chunks = chunk_items(items)
        for ch in chunks:
            fname = f"PEGGY_FULL_EVIDENCE_CHUNK_{ch['chunk_index']:03d}.txt"
            ch["filename"] = fname
            header = (
                f"PEGGY FULL EVIDENCE CHUNK {ch['chunk_index'] + 1}/{len(chunks)}\n"
                f"item_count: {ch['item_count']}\n"
                f"estimated_tokens: {ch['estimated_tokens']}\n\n"
            )
            (out / fname).write_text(header + ch["text"], encoding="utf-8")
            chunk_files.append(fname)
        manifest = build_chunk_manifest(items, chunks)
        chunk_manifest_path = out / "PEGGY_FULL_EVIDENCE_CHUNK_MANIFEST.json"
        chunk_manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        if not manifest.get("union_equals_normalized"):
            raise RuntimeError(
                "chunk union != normalized evidence set: "
                f"missing={manifest.get('missing_item_ids')} extra={manifest.get('extra_item_ids')}"
            )

    metrics = {
        "diagnostic_version": DIAGNOSTIC_VERSION,
        "built_at": stamp,
        "source_commit": commit,
        "ask": ask_text,
        "plan_scope": {
            "person_ids": list(getattr(plan, "person_ids", ()) or ()),
            "person_names": list(getattr(plan, "person_names", ()) or ()),
            "temporal_windows": list(getattr(plan, "temporal_windows", ()) or ()),
            "notes": list(getattr(plan, "notes", ()) or ()),
        },
        "by_source": by_source,
        "total": totals,
        "ineligible_excluded": {
            "counts": norm.get("ineligible") or {},
            "total": norm.get("ineligible_total") or 0,
            "note": "spam/trash mailbox skips only — not sampling/ranking/caps",
        },
        "downstream_comparison": downstream,
        "outputs": {
            "PEGGY_FULL_EVIDENCE.txt": str(evidence_path),
            "PEGGY_FULL_EVIDENCE_METRICS.json": str(metrics_path),
            "CLOUDREQ_peggy_full_evidence_paste.txt": str(paste_path),
            "chunk_files": chunk_files,
            "chunk_manifest": str(chunk_manifest_path) if chunk_manifest_path else None,
        },
        "chunking": {
            "triggered": bool(chunk_files),
            "trigger_tokens": CHUNK_TRIGGER_TOKENS,
            "target_min_tokens": CHUNK_TARGET_MIN_TOKENS,
            "target_max_tokens": CHUNK_TARGET_MAX_TOKENS,
            "chunk_count": len(chunk_files),
        },
        "llm_calls": 0,
        "production_inference_modified": False,
    }
    metrics_path.write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    # Compact JSON of normalized items for machine verification (optional companion).
    items_path = out / "PEGGY_FULL_EVIDENCE_ITEMS.json"
    items_doc = {
        "diagnostic_version": DIAGNOSTIC_VERSION,
        "ask": ask_text,
        "item_count": len(items),
        "item_ids": [it.get("item_id") for it in items],
        "content_fingerprints": [it.get("content_fingerprint") for it in items],
        "items": items,
    }
    items_path.write_text(
        json.dumps(items_doc, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    metrics["outputs"]["PEGGY_FULL_EVIDENCE_ITEMS.json"] = str(items_path)
    metrics_path.write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    return {
        "ok": True,
        "out_dir": str(out),
        "ask": ask_text,
        "normalized_item_count": len(items),
        "estimated_tokens": totals["estimated_tokens"],
        "exact_duplicates_removed": totals["exact_duplicates_removed"],
        "chunk_count": len(chunk_files),
        "llm_calls": 0,
        "metrics_path": str(metrics_path),
        "evidence_path": str(evidence_path),
        "paste_path": str(paste_path),
        "chunk_manifest_path": str(chunk_manifest_path) if chunk_manifest_path else None,
        "downstream_available": bool(downstream.get("available")),
        "person_ids": list(getattr(plan, "person_ids", ()) or ()),
        "person_names": list(getattr(plan, "person_names", ()) or ()),
    }


def run_full_evidence_diagnostic_cli(
    *,
    out_dir: Path | str | None = None,
    ask: str | None = None,
    fixture: Path | str | None = None,
    flightsim: bool = False,
) -> dict[str, Any]:
    if flightsim:
        import os

        os.environ["MEMORYBOX_P1_RUNTIME_HOST"] = "1"
    return run_full_evidence_diagnostic(
        out_dir=out_dir,
        ask=ask,
        fixture_path=fixture,
    )
