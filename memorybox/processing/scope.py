"""Fail-closed video work admission. Importing this module never opens a database.

A reviewed immutable plan is registered by an operator, then separately started.
Archive plans require a founder acceptance reference and an explicit unlock first.
All entry points re-read persisted state; environment IDs alone grant no authority.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
import math
import os
from uuid import UUID

class ScopeDenied(ValueError):
    pass

COVERAGE = {"face_only", "off_camera_voice", "simultaneous_modalities", "multiple_people", "poor_audio", "occlusion", "short_appearance", "sustained_appearance", "no_match"}
LANES = {"face", "voice", "transcribe"}
MAX_WORK_ITEMS = 10_000
MAX_ATTEMPTS_PER_ITEM = 3

def digest(plan: dict) -> str:
    return hashlib.sha256(json.dumps(plan, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()

def preview(plan: dict) -> dict:
    """Validate exact membership/truth and calculate the whole authorized workload, no I/O."""
    try:
        kind = plan["scope_kind"]
        if kind not in {"bounded", "archive"}: raise ValueError()
        manifest = plan["manifest"]
        if any(not isinstance(manifest[k], str) or not manifest[k].strip() for k in ("id", "version")): raise ValueError()
        sources = manifest["sources"]
        if not isinstance(sources, list) or not sources: raise ValueError()
        if kind == "bounded" and len(sources) != 22:
            raise ScopeDenied("bounded_manifest_requires_exactly_22_sources")
        seen = set(); coverage = set()
        for source in sources:
            key = (source["provider_key"], source["video_external_id"])
            if any(not isinstance(x,str) or not x.strip() or "*" in x for x in key) or key in seen: raise ValueError()
            seen.add(key)
            duration = source["duration_sec"]
            if isinstance(duration,bool) or not math.isfinite(duration) or duration <= 0: raise ValueError()
            fingerprint = source["source_sha256"]
            if len(fingerprint) != 64 or any(c not in "0123456789abcdef" for c in fingerprint): raise ValueError()
            if not source.get("owner_truth_ref") or source.get("owner_confirmed") is not True: raise ValueError()
            truth = source["truth"]
            if not isinstance(truth,list) or not truth: raise ValueError()
            for t in truth:
                if t["modality"] not in {"face", "voice", "no_match"}: raise ValueError()
                if t["modality"] != "no_match": UUID(t["person_id"])
                a,b=t["start_sec"],t["end_sec"]
                if not all(isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x) for x in (a,b)) or not 0 <= a < b <= duration: raise ValueError()
            coverage.update(source["coverage_tags"])
        if kind == "bounded" and not COVERAGE <= coverage: raise ScopeDenied("corpus_coverage_incomplete")
        people = plan["person_ids"]
        if not isinstance(people,list) or len(set(people)) != len(people): raise ValueError()
        for person in people: UUID(person)
        lanes = plan["lanes"]
        if not isinstance(lanes,list) or not lanes or len(set(lanes)) != len(lanes) or not set(lanes) <= LANES: raise ValueError()
        if set(lanes)&{"face","voice"} and not people: raise ValueError()
        count = len(sources) * (len(people)*len(set(lanes)&{"face","voice"}) + int("transcribe" in lanes))
        limit = plan["max_work_items"]; attempts = plan["max_attempts_per_item"]
        if type(limit) is not int or not 0 < limit <= MAX_WORK_ITEMS or type(attempts) is not int or not 1 <= attempts <= MAX_ATTEMPTS_PER_ITEM: raise ValueError()
        if count > limit: raise ScopeDenied("workload_limit_exceeded")
        return {"scope_kind":kind,"source_count":len(sources),"person_count":len(people),"work_items":count,"max_work_items":limit,"max_attempts":count*attempts,"plan_sha256":digest(plan)}
    except ScopeDenied: raise
    except (KeyError,TypeError,ValueError,OverflowError):
        raise ScopeDenied("invalid_scope_plan_or_owner_truth") from None

@dataclass(frozen=True)
class Admission:
    id: str
    plan: dict
    state: str
    plan_sha256: str
    acceptance_ref: str | None = None
    unlock_ref: str | None = None
    start_ref: str | None = None

    @property
    def videos(self):
        return [{"video_provider_key":s["provider_key"],"video_external_id":s["video_external_id"],"eligible":True} for s in self.plan["manifest"]["sources"]]

    def check(self, lane: str, videos: list[dict], person_ids: list[str]) -> None:
        preview(self.plan)
        if digest(self.plan) != self.plan_sha256: raise ScopeDenied("scope_plan_changed")
        if self.state != "started" or not self.start_ref: raise ScopeDenied("processing_not_started")
        if self.plan["scope_kind"] == "archive" and not (self.acceptance_ref and self.unlock_ref): raise ScopeDenied("archive_locked")
        if lane not in self.plan["lanes"]: raise ScopeDenied("modality_not_admitted")
        allowed={(v["video_provider_key"],v["video_external_id"]) for v in self.videos}
        keys=[(v.get("video_provider_key"),v.get("video_external_id")) for v in videos]
        if len(set(keys)) != len(keys) or any(k not in allowed for k in keys): raise ScopeDenied("off_manifest_or_duplicate_source")
        if len(set(person_ids)) != len(person_ids) or any(p not in self.plan["person_ids"] for p in person_ids): raise ScopeDenied("person_not_admitted")
        if lane != "transcribe" and not person_ids: raise ScopeDenied("person_required")
        if lane == "transcribe" and person_ids: raise ScopeDenied("transcription_is_per_source")
        if len(keys)*max(1,len(person_ids)) > self.plan["max_work_items"]: raise ScopeDenied("workload_limit_exceeded")

def load_admission() -> Admission:
    raw=os.environ.get("MEMORYBOX_I13_ADMISSION_ID", "").strip()
    try: UUID(raw)
    except ValueError: raise ScopeDenied("processing_locked_no_admission") from None
    try:
        from memorybox.db import connection
        with connection() as conn:
            row=conn.execute("SELECT * FROM i13_processing_admissions WHERE id=%s::uuid",(raw,)).fetchone()
        if not row: raise ScopeDenied("admission_not_found")
        plan=row["plan_json"]
        if isinstance(plan,str): plan=json.loads(plan)
        return Admission(raw,plan,row["state"],row["plan_sha256"],row.get("acceptance_ref"),row.get("unlock_ref"),row.get("start_ref"))
    except ScopeDenied: raise
    except Exception: raise ScopeDenied("admission_store_unavailable") from None

def require_admission(lane: str, *, archive: bool = False) -> Admission:
    a=load_admission()
    a.check(lane, [], [] if lane=="transcribe" else a.plan.get("person_ids",[]))
    if archive and a.plan["scope_kind"] != "archive": raise ScopeDenied("archive_locked")
    return a

def admit(lane: str, videos: list[dict], person_ids: list[str] | None = None) -> Admission:
    a=require_admission(lane)
    a.check(lane,videos,list(person_ids or []))
    return a

def require_source(lane: str, provider: str, video: str, person: str | None = None) -> Admission:
    return admit(lane,[{"video_provider_key":provider,"video_external_id":video}], [str(person)] if person else [])

def begin_work(lane: str, provider: str, video: str, person: str | None = None) -> Admission:
    """Atomically bound retries across all entry points, processes and enqueue reasons."""
    a=require_source(lane,provider,video,person)
    from memorybox.db import connection
    with connection() as conn:
        # Lock admission against concurrent stop/revoke before reserving an attempt.
        state=conn.execute("SELECT state,plan_sha256 FROM i13_processing_admissions WHERE id=%s::uuid FOR SHARE",(a.id,)).fetchone()
        if not state or state["state"] != "started" or state["plan_sha256"] != a.plan_sha256: raise ScopeDenied("admission_changed")
        row=conn.execute("""INSERT INTO i13_work_attempts(admission_id,lane,provider_key,video_external_id,person_key,attempts)
            VALUES(%s::uuid,%s,%s,%s,%s,1)
            ON CONFLICT(admission_id,lane,provider_key,video_external_id,person_key)
            DO UPDATE SET attempts=i13_work_attempts.attempts+1
            WHERE i13_work_attempts.attempts < %s RETURNING attempts""",
            (a.id,lane,provider,video,str(person or ""),a.plan["max_attempts_per_item"])).fetchone()
        if not row: raise ScopeDenied("work_attempt_limit_exceeded")
    return a

def deny_legacy() -> None:
    raise ScopeDenied("legacy_processing_has_no_reviewed_source_mapping")


def reserve_queue_item(conn, admission: Admission, lane: str, video: dict, person: str | None, reason: str) -> None:
    """One queue reason per admitted unit; new reasons cannot multiply the work set."""
    admission.check(lane,[video],[str(person)] if person else [])
    state=conn.execute("SELECT state,plan_sha256 FROM i13_processing_admissions WHERE id=%s::uuid FOR SHARE",(admission.id,)).fetchone()
    if not state or state["state"]!="started" or state["plan_sha256"]!=admission.plan_sha256:
        raise ScopeDenied("admission_changed")
    row=conn.execute("""INSERT INTO i13_queue_units(admission_id,lane,provider_key,video_external_id,person_key,enqueue_reason)
        VALUES(%s::uuid,%s,%s,%s,%s,%s)
        ON CONFLICT(admission_id,lane,provider_key,video_external_id,person_key)
        DO UPDATE SET enqueue_reason=i13_queue_units.enqueue_reason
        RETURNING enqueue_reason""",(admission.id,lane,video["video_provider_key"],video["video_external_id"],str(person or ""),reason)).fetchone()
    if row["enqueue_reason"]!=reason: raise ScopeDenied("work_unit_already_admitted_with_another_reason")
