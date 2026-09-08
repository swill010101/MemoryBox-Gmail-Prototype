"""Non-destructive, manifest-scoped Gallery projection; no DB or model access."""
from copy import deepcopy

from memorybox.recognition.fragment_reconciliation import (
    PILOT_RUN,
    PILOT_SOURCE,
    POLICY,
    SECOND_RUN,
    SECOND_SOURCE,
    approved_source_runs,
    is_pilot_evidence,
    is_reconcilable_fragment,
)

# Backward-compatible test constants.
APPROVED_SOURCE_RUNS = approved_source_runs()


def project_source_cards(items):
    """Retain all query-returned moments inside one card per evidence partition.

    Legacy HVRT half-second fragments on the accepted manifest collapse to one
    source card per (source, Person, run, model). No interval union, no archive
    sweep, and no deletion of underlying moment rows.
    """
    out = []
    groups = {}
    for original in items:
        e = original.get("appearance_evidence") or {}
        if (
            original.get("presentation_policy") == POLICY
            or original.get("spoken_text")
            or not original.get("mb_person_id")
            or not is_reconcilable_fragment(
                original.get("video_external_id"),
                original.get("provider_key"),
                e,
                start_sec=original.get("start_sec"),
                end_sec=original.get("end_sec"),
            )
        ):
            out.append(original)
            continue
        key = (
            original["provider_key"],
            original["video_external_id"],
            original["mb_person_id"],
            e.get("processing_run_id"),
            e.get("model_version"),
        )
        if key not in groups:
            card = deepcopy(original)
            card["source_moments"] = []
            groups[key] = card
            out.append(card)
        groups[key]["source_moments"].append(deepcopy(original))
    for card in groups.values():
        moments = sorted(card["source_moments"], key=lambda x: (float(x["start_sec"]), x["id"]))
        first = moments[0]
        card.update(deepcopy(first))
        card["source_moments"] = moments
        card["presentation_policy"] = POLICY
        card["id"] = "video:source:" + first["id"]
        card["duration_sec"] = None
        card["preview"] = f"{len(moments)} moments in this result"
        card["detail"] = "One source video. Choose a moment to jump to its evidence."
    return out
