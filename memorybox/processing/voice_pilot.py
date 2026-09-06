"""Exact-span voice pilot validation. No media, database or model I/O at import."""
from __future__ import annotations
import math
from uuid import UUID
from .scope import ScopeDenied, digest

PURPOSE = "voice_pilot"
TITANET_SHA256 = "e838520693f269e7984f55bc8eb3c2d60ccf246bf4b896d4be9bcabe3e4b0fe3"
LIMITS = {"max_work_items": 4, "max_attempts_per_item": 1,
          "extract_timeout_sec": 120, "embedding_timeout_sec": 120,
          "overall_timeout_sec": 1200}

def valid_uuid(value):
    return isinstance(value, str) and str(UUID(value)) == value

def number(value):
    return type(value) in (int, float) and math.isfinite(value)

def validate(plan):
    try:
        if plan["purpose"] != PURPOSE or plan["scope_kind"] != "bounded": raise ValueError()
        if plan["lanes"] != ["voice"]: raise ValueError()
        if len(plan["person_ids"]) != 1 or not valid_uuid(plan["person_ids"][0]): raise ValueError()
        for key, value in LIMITS.items():
            if type(plan[key]) is not int or plan[key] != value: raise ValueError()
        manifest = plan["manifest"]
        if not manifest["id"] or not manifest["version"]: raise ValueError()
        if len(manifest["sources"]) != 22: raise ValueError()
        sources = {(s["provider_key"], s["video_external_id"]): s for s in manifest["sources"]}
        if len(sources) != 22 or plan["parent_manifest_sha256"] != digest(manifest): raise ValueError()
        for source in sources.values():
            if not number(source["duration_sec"]) or source["duration_sec"] <= 0: raise ValueError()
            if len(source["source_sha256"]) != 64 or any(x not in "0123456789abcdef" for x in source["source_sha256"]): raise ValueError()
        spans = plan["spans"]
        if len(spans) != 4 or [s["role"] for s in spans] != ["training", "held_out", "held_out", "held_out"]: raise ValueError()
        if len({s["key"] for s in spans}) != 4 or len({s["annotation_id"] for s in spans}) != 4: raise ValueError()
        for s in spans:
            if not s["key"] or len(s["key"]) > 80: raise ValueError()
            if not all(valid_uuid(s[k]) for k in ("annotation_id", "version_id", "person_id")): raise ValueError()
            if not 1 <= len(s["word_ids"]) <= 500 or len(set(s["word_ids"])) != len(s["word_ids"]): raise ValueError()
            if not all(valid_uuid(w) for w in s["word_ids"]): raise ValueError()
            source = sources[(s["provider_key"], s["source_id"])]
            if s["source_sha256"] != source["source_sha256"]: raise ValueError()
            if not all(number(s[k]) for k in ("start", "end")) or not 0 <= s["start"] < s["end"] <= source["duration_sec"]: raise ValueError()
            if s["end"] - s["start"] > 60: raise ValueError()
        if spans[0]["person_id"] != plan["person_ids"][0]: raise ValueError()
        if sum(s["end"] - s["start"] for s in spans) > 120: raise ValueError()
        for i, a in enumerate(spans):
            for b in spans[i+1:]:
                # Content hash also catches identical content under different IDs.
                if a["source_sha256"] == b["source_sha256"] and max(a["start"], b["start"]) < min(a["end"], b["end"]):
                    raise ScopeDenied("pilot_training_test_or_span_overlap")
        model = plan["model"]
        if model["format"] != "nemo_titanet_large_192" or model["sha256"] != TITANET_SHA256: raise ValueError()
        if not isinstance(model["revision"], str) or not model["revision"].strip(): raise ValueError()
        low, high = plan["thresholds"]["uncertain"], plan["thresholds"]["match"]
        if not number(low) or not number(high) or not -1 <= low < high <= 1: raise ValueError()
        return {"purpose": PURPOSE, "source_count": len({(s['provider_key'],s['source_id']) for s in spans}),
                "person_count": 1, "work_items": 4, "max_attempts": 4,
                "audio_seconds": round(sum(s['end']-s['start'] for s in spans), 6), "plan_sha256": digest(plan)}
    except ScopeDenied: raise
    except (KeyError, TypeError, ValueError, OverflowError):
        raise ScopeDenied("invalid_voice_pilot_plan") from None

def vector(value):
    if not isinstance(value, list) or len(value) != 192 or not all(number(v) for v in value):
        raise ScopeDenied("invalid_voice_vector")
    norm = math.sqrt(sum(v*v for v in value))
    if not math.isfinite(norm) or norm < 1e-12: raise ScopeDenied("invalid_voice_vector")
    return [v/norm for v in value]

def score(reference, probe, thresholds):
    a,b = vector(reference),vector(probe)
    value = max(-1., min(1., sum(x*y for x,y in zip(a,b))))
    label = "match" if value >= thresholds["match"] else "uncertain" if value >= thresholds["uncertain"] else "no_match"
    return {"score":value,"decision":label}
