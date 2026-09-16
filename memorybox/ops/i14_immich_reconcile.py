"""Read-only Immich vs MB visual counts. Never writes prepared data."""
from __future__ import annotations

import json
import os
import sys

NAMES = ("Tom Will", "Sue Will", "Cora Will")


def _allow() -> bool:
    return os.environ.get("MEMORYBOX_I14_IMMICH_RECONCILE_ALLOW_FLIGHTSIM") == "1"


def main(argv: list[str] | None = None) -> int:
    if not _allow():
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "set MEMORYBOX_I14_IMMICH_RECONCILE_ALLOW_FLIGHTSIM=1",
                }
            )
        )
        return 2
    from memorybox.explore.immich_reconcile import reconcile_person_visuals
    from memorybox.person import list_people_by_exact_name

    out = []
    for name in NAMES:
        hits = list_people_by_exact_name(name) or []
        if not hits:
            out.append({"person_name": name, "ok": False, "error": "person_not_found"})
            continue
        pid = str(hits[0].id)
        out.append(reconcile_person_visuals(person_id=pid, person_name=name))
    print(json.dumps({"ok": all(r.get("ok") for r in out), "people": out}, default=str, indent=2))
    return 0 if all(r.get("ok") for r in out) else 1


if __name__ == "__main__":
    sys.exit(main())
