"""Non-destructive, source-scoped Gallery projection; no DB or model access."""
from copy import deepcopy

PILOT_SOURCE = "vid-c57dbd21f993f6d1"
PILOT_RUN = "7aa4cda7-2d49-456c-a107-9d896cc37b53"
POLICY = "i13-source-moments-v1"


def is_pilot_evidence(source, provider, evidence):
    e = evidence or {}
    return (source == PILOT_SOURCE and provider == "hvrt"
            and e.get("processing_run_id") == PILOT_RUN
            and e.get("method") == "mb_native_i8b"
            and e.get("status") == "accepted"
            and e.get("authority") == "ai_inferred"
            and e.get("confirmation_state") == "system_associated")


def project_source_cards(items):
    """Retain all query-returned moments inside one card per evidence partition.

    No interval union, full-source fetch or continuous-presence assertion. Unknown,
    withdrawn, owner evidence and other sources are not regrouped.
    """
    out = []
    groups = {}
    for original in items:
        e = original.get("appearance_evidence") or {}
        if (original.get("presentation_policy") == POLICY or original.get("spoken_text") or not original.get("mb_person_id")
                or not is_pilot_evidence(original.get("video_external_id"), original.get("provider_key"), e)):
            out.append(original)
            continue
        key = (original["mb_person_id"], e.get("processing_run_id"), e.get("model_version"))
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
        card["duration_sec"] = None  # evidence length is not source duration
        card["preview"] = f"{len(moments)} moments in this result"
        card["detail"] = "One source video. Choose a moment to jump to its evidence."
    return out
