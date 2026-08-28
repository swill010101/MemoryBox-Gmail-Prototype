"""Acceptance for Peggy full-fidelity evidence diagnostic (no LLM, no archive required)."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from memorybox.ask.i11a.full_evidence_diagnostic import (
    CHUNK_TRIGGER_TOKENS,
    DIAGNOSTIC_VERSION,
    PEGGY_ASK,
    build_chunk_manifest,
    chunk_items,
    downstream_comparison_from_fixture,
    estimate_tokens,
    format_cloud_paste,
    format_full_evidence_text,
    normalize_retrieved,
    run_full_evidence_diagnostic,
)


def _check(name: str, ok: bool, checks: list[str], problems: list[str], *, detail: Any = None) -> None:
    checks.append(name)
    if not ok:
        problems.append(f"{name}: {detail}")


class _Hit:
    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


def _email_hit(
    eid: str,
    *,
    subject: str,
    body: str,
    sent_at: str,
    thread_id: str = "t1",
) -> _Hit:
    return _Hit(
        evidence_id=eid,
        evidence_kind="email_message",
        summary=subject,
        score=1.0,
        excerpt=body[:80],
        source="email_mbox",
        sent_at=sent_at,
        channel="email",
        people=["Peggy"],
        thread_id=thread_id,
        direction="inbound",
        attachments=None,
        identity_mapped=None,
        from_header="friend@example.com",
        to_header="owner@example.com",
        payload={
            "body_text": body,
            "subject": subject,
            "from": "friend@example.com",
            "to": ["owner@example.com"],
            "cc": [],
            "thread_id": thread_id,
            "sent_at": sent_at,
        },
    )


def _sms_hit(eid: str, *, body: str, sent_at: str, thread_id: str = "sms-t1") -> _Hit:
    return _Hit(
        evidence_id=eid,
        evidence_kind="sms_message",
        summary=body[:40],
        score=1.0,
        excerpt=body[:80],
        source="sms_export",
        sent_at=sent_at,
        channel="sms",
        people=["Peggy", "Me"],
        thread_id=thread_id,
        direction="inbound",
        attachments=None,
        identity_mapped=None,
        from_header=None,
        to_header=None,
        payload={
            "body_text": body,
            "participants": ["Peggy", "Me"],
            "sender_name": "Peggy",
            "thread_id": thread_id,
            "sent_at": sent_at,
            "evidence_channel": "sms",
        },
    )


def _person_context() -> dict[str, Any]:
    return {
        "focal_subjects": [
            {
                "person_id": "person-peggy",
                "display_name": "Peggy George",
                "birth_date": "1950-05-01",
                "death_date": None,
                "age_at_period": None,
                "aliases": [],
                "communication_identities": [],
                "known_relationships": [
                    {
                        "from_person_id": "person-peggy",
                        "to_person_id": "person-tom",
                        "role_kind": "child",
                        "authority": "confirmed",
                    }
                ],
                "inferred_relationships": [],
                "allowed_relationship_labels": ["child", "parent"],
            }
        ],
        "requestor": None,
        "allowed_relationship_labels": ["child", "parent"],
        "as_of": None,
    }


def _synthetic_retrieved(*, dupe: bool = True) -> dict[str, Any]:
    emails = [
        _email_hit(
            "e1",
            subject="Hospital visit",
            body="Peggy is at the hospital today and resting.",
            sent_at="2024-03-01T10:00:00Z",
            thread_id="email-thread-a",
        ),
        _email_hit(
            "e2",
            subject="Re: Hospital visit",
            body="Thanks for the update about Peggy.",
            sent_at="2024-03-01T12:00:00Z",
            thread_id="email-thread-a",
        ),
        _email_hit(
            "e3",
            subject="Delta confirmation ABC12",
            body="Your Delta flight SEA → LAS confirmation ABC12345 on 2024-06-01.",
            sent_at="2024-05-15T09:00:00Z",
            thread_id="email-thread-b",
        ),
    ]
    if dupe:
        emails.append(
            _email_hit(
                "e1-dup",
                subject="Hospital visit",
                body="Peggy is at the hospital today and resting.",
                sent_at="2024-03-01T10:00:00Z",
                thread_id="email-thread-a",
            )
        )
    return {
        "evidence": emails
        + [
            _sms_hit(
                "s1",
                body="See you at dinner tonight.",
                sent_at="2024-03-02T18:00:00Z",
            )
        ],
        "photos": [],
        "videos": [],
        "stories": [],
        "journals": [],
        "artifacts": [],
        "guided_capture": [],
    }


class _FakePlan:
    person_ids = ("person-peggy",)
    person_names = ("Peggy George",)
    temporal_windows = ()
    notes = ("full_evidence_diagnostic", "resolved_person_ids_for_comms")
    output_mode = "tell"
    original_ask = PEGGY_ASK


def run_prove_full_evidence_diagnostic(*, flightsim: bool = False) -> dict[str, Any]:
    checks: list[str] = []
    problems: list[str] = []

    _check("diagnostic_version_set", DIAGNOSTIC_VERSION >= 1, checks, problems)
    _check("peggy_ask_matches_historian", PEGGY_ASK == "tell me what you know about Peggy", checks, problems)

    pc = _person_context()
    retrieved = _synthetic_retrieved(dupe=True)
    norm = normalize_retrieved(retrieved, person_context=pc)
    items = norm["items"]

    _check(
        "includes_person_facts",
        any(it.get("source") == "person" for it in items),
        checks,
        problems,
    )
    _check(
        "includes_sms_complete_body",
        any(
            it.get("source") == "sms" and "dinner" in str(it.get("body") or "")
            for it in items
        ),
        checks,
        problems,
    )
    _check(
        "includes_email_complete_body",
        any(
            it.get("source") == "email"
            and "hospital" in str(it.get("body") or "").lower()
            for it in items
        ),
        checks,
        problems,
    )
    _check(
        "exact_duplicates_counted",
        int(norm.get("duplicates_removed_total") or 0) >= 1,
        checks,
        problems,
        detail=norm.get("duplicates_removed"),
    )
    derived_n = sum(1 for it in items if it.get("source") == "travel")
    expected_norm = (
        int(norm.get("retrieved_total") or 0)
        - int(norm.get("duplicates_removed_total") or 0)
        - int(norm.get("ineligible_total") or 0)
        + derived_n
    )
    _check(
        "no_silent_cap_on_synthetic",
        int(norm.get("normalized_total") or 0) == expected_norm,
        checks,
        problems,
        detail={
            "normalized": norm.get("normalized_total"),
            "retrieved": norm.get("retrieved_total"),
            "dupes": norm.get("duplicates_removed_total"),
            "derived_travel": derived_n,
            "expected": expected_norm,
        },
    )

    # Travel derived from Delta email should appear without replacing the email.
    travel_n = sum(1 for it in items if it.get("source") == "travel")
    email_n = sum(1 for it in items if it.get("source") == "email")
    _check("travel_derived_present", travel_n >= 1, checks, problems, detail=travel_n)
    _check("email_still_present_with_travel", email_n >= 2, checks, problems, detail=email_n)

    text = format_full_evidence_text(items, ask=PEGGY_ASK, person_context=pc)
    paste = format_cloud_paste(items, ask=PEGGY_ASK, person_context=pc)
    _check("human_readable_nonempty", len(text) > 100, checks, problems)
    _check("paste_has_person_context", "PERSON CONTEXT" in paste, checks, problems)
    _check("paste_has_evidence", "COMPLETE NORMALIZED EVIDENCE" in paste, checks, problems)
    _check(
        "paste_excludes_embeddings_trace_noise",
        "embedding" not in paste.lower() and "ai_trace" not in paste.lower(),
        checks,
        problems,
    )

    # Chunk union proof with oversized synthetic corpus.
    big: list[dict[str, Any]] = []
    for i in range(40):
        body = ("evidence-body-" + str(i) + "-") * 2500  # ~ large tokens
        big.append(
            {
                "item_id": f"email:big{i}",
                "source": "email",
                "native_id": f"big{i}",
                "timestamp": f"2022-01-{(i % 28) + 1:02d}T00:00:00Z",
                "subject": f"Subject {i}",
                "body": body,
                "thread_id": f"thread-{i // 4}",
                "from": "a@b.c",
                "to": "d@e.f",
                "cc": None,
                "content_fingerprint": f"fp-big-{i}",
            }
        )
    total_tok = estimate_tokens("\n".join(
        f"{it['item_id']}\n{it['body']}" for it in big
    ))
    _check(
        "synthetic_exceeds_chunk_trigger",
        total_tok > CHUNK_TRIGGER_TOKENS or estimate_tokens(
            "\n".join(it["body"] for it in big)
        ) > CHUNK_TRIGGER_TOKENS,
        checks,
        problems,
        detail=total_tok,
    )
    chunks = chunk_items(big)
    manifest = build_chunk_manifest(big, chunks)
    _check("chunk_count_ge_2", len(chunks) >= 2, checks, problems, detail=len(chunks))
    _check(
        "chunk_union_equals_all",
        bool(manifest.get("union_equals_normalized")),
        checks,
        problems,
        detail={
            "missing": manifest.get("missing_item_ids"),
            "extra": manifest.get("extra_item_ids"),
        },
    )
    # Threads not split: all items sharing a thread_id appear in one chunk.
    thread_to_chunk: dict[str, set[int]] = {}
    for ch in chunks:
        for it in ch["items"]:
            tid = str(it.get("thread_id") or "")
            thread_to_chunk.setdefault(tid, set()).add(int(ch["chunk_index"]))
    split_threads = {t: sorted(cs) for t, cs in thread_to_chunk.items() if len(cs) > 1}
    _check("email_threads_not_split", not split_threads, checks, problems, detail=split_threads)

    # End-to-end write with injected plan/retrieved (no DB / no LLM).
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        result = run_full_evidence_diagnostic(
            out_dir=out,
            ask=PEGGY_ASK,
            plan=_FakePlan(),
            person_context=pc,
            retrieved=_synthetic_retrieved(dupe=True),
            fixture_path=None,
        )
        _check("cli_result_ok", bool(result.get("ok")), checks, problems, detail=result)
        _check("llm_calls_zero", result.get("llm_calls") == 0, checks, problems)
        for name in (
            "PEGGY_FULL_EVIDENCE.txt",
            "PEGGY_FULL_EVIDENCE_METRICS.json",
            "CLOUDREQ_peggy_full_evidence_paste.txt",
        ):
            p = out / name
            _check(f"wrote_{name}", p.is_file() and p.stat().st_size > 0, checks, problems)
        metrics = json.loads((out / "PEGGY_FULL_EVIDENCE_METRICS.json").read_text(encoding="utf-8"))
        _check(
            "metrics_has_by_source",
            isinstance(metrics.get("by_source"), dict) and bool(metrics.get("by_source")),
            checks,
            problems,
        )
        total = metrics.get("total") or {}
        for key in (
            "retrieved_item_count",
            "normalized_item_count",
            "exact_duplicates_removed",
            "bytes",
            "characters",
            "estimated_tokens",
        ):
            _check(f"metrics_total_{key}", key in total, checks, problems)
        _check(
            "metrics_llm_calls_zero",
            metrics.get("llm_calls") == 0,
            checks,
            problems,
        )
        _check(
            "production_inference_not_modified_flag",
            metrics.get("production_inference_modified") is False,
            checks,
            problems,
        )
        ds = downstream_comparison_from_fixture(None)
        _check(
            "downstream_without_fixture_reported",
            ds.get("available") is False,
            checks,
            problems,
        )

    return {
        "ok": not problems,
        "prove": "full_evidence_diagnostic",
        "flightsim": bool(flightsim),
        "checks": checks,
        "problems": problems,
        "ask": PEGGY_ASK,
    }
