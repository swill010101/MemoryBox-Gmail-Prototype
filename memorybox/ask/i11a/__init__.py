"""I11A requestor vs focal subject — independent of output_mode."""
from __future__ import annotations

from typing import Any

from memorybox.ask.retrieve import visual_library_person_ids
from memorybox.profile.owner import get_requestor_person_id


def resolve_request_context(plan: Any) -> dict[str, Any]:
    """Who is asking vs who/what the Ask is about."""
    requestor = None
    try:
        requestor = get_requestor_person_id()
    except Exception:  # noqa: BLE001
        requestor = None
    names = [str(n).strip() for n in (getattr(plan, "person_names", ()) or ()) if str(n).strip()]
    ids = [str(p) for p in (getattr(plan, "person_ids", ()) or ()) if p]
    focal_ids = list(dict.fromkeys(ids))
    if not names and not ids and requestor:
        focal_ids = [requestor]
    return {
        "requestor_person_id": requestor,
        "focal_subject_person_ids": focal_ids,
        "focal_subject_names": names,
        "visual_library_person_ids": visual_library_person_ids(plan)[0],
    }


def needs_semantic_inference(plan: Any) -> bool:
    """Tell/summarize/know-about synthesis. Simple gallery show bypasses."""
    if getattr(plan, "journal_capture_intent", False):
        return False
    if str(getattr(plan, "output_mode", "") or "") == "tell":
        return True
    notes = getattr(plan, "notes", ()) or ()
    return "exploratory_about_subject" in notes
