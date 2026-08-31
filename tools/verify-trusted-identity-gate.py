#!/usr/bin/env python3
"""Requirement audit of TRUSTED_IDENTITY_GATE.json / PHASE1_prove.json.

Goal completion needs FlightSim Takeout prove: trusted retrieve only,
unsupported=0, Gallery>0. Rejects waiting placeholders and ALLOW_DEV fakes.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

DEFAULT_PATH = Path("docs/test-output/trusted-full-evidence-v2/TRUSTED_IDENTITY_GATE.json")
FALLBACK_PATH = Path("docs/test-output/trusted-full-evidence-v2/PHASE1_prove.json")


def audit_gate(gate: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    problems: list[str] = []

    def check(req_id: str, name: str, ok: bool, evidence: Any = None) -> None:
        checks.append(
            {
                "id": req_id,
                "requirement": name,
                "ok": bool(ok),
                "evidence": evidence,
            }
        )
        if not ok:
            problems.append(f"{req_id}: {name}")

    runtime = gate.get("runtime") or {}
    phase1 = gate.get("phase1") or gate.get("flightsim_report") or gate
    if not isinstance(phase1, dict):
        phase1 = {}

    check("C1", "not a waiting placeholder", gate.get("waiting") is not True, {"waiting": gate.get("waiting")})
    check(
        "C2",
        "flightsim=true (Takeout archive host)",
        gate.get("flightsim") is True or runtime.get("flightsim") is True,
        {"flightsim": gate.get("flightsim"), "runtime_flightsim": runtime.get("flightsim")},
    )
    check(
        "C2a",
        "not ALLOW_DEV defaults",
        runtime.get("allow_dev_defaults") is not True,
        {"allow_dev_defaults": runtime.get("allow_dev_defaults")},
    )
    check(
        "C2b",
        "P1 runtime host stamped",
        runtime.get("p1_runtime_host") is True,
        {"p1_runtime_host": runtime.get("p1_runtime_host")},
    )
    hn = str(runtime.get("hostname") or "").strip().lower()
    check(
        "C2c",
        "hostname is not cloud agent sandbox",
        hn not in {"", "cursor", "cursor-cloud"} and not hn.startswith("sandbox"),
        {"hostname": runtime.get("hostname")},
    )
    check("C3", "ok=true", gate.get("ok") is True, {"ok": gate.get("ok"), "problems": gate.get("problems")})

    trusted = list(phase1.get("trusted_addresses") or [])
    per = list(phase1.get("per_trusted_address") or [])
    check("R1", "at least one trusted retrieve identity", bool(trusted), {"trusted_addresses": trusted})
    check(
        "R2",
        "unsupported retrieve addresses = 0",
        not (phase1.get("unsupported_retrieve_addresses") or []),
        {"unsupported_retrieve_addresses": phase1.get("unsupported_retrieve_addresses")},
    )
    check(
        "R3",
        "unsupported retrieve hits = 0",
        int(phase1.get("unsupported_retrieve_hit_count") or 0) == 0,
        {"unsupported_retrieve_hit_count": phase1.get("unsupported_retrieve_hit_count")},
    )
    check(
        "R4",
        "retrieve hit count > 0",
        int(phase1.get("retrieve_hit_count") or 0) > 0,
        {"retrieve_hit_count": phase1.get("retrieve_hit_count")},
    )
    check(
        "R5",
        "Gallery email count > 0",
        int(phase1.get("gallery_email_count") or 0) > 0,
        {"gallery_email_count": phase1.get("gallery_email_count")},
    )
    why_ok = True
    if per:
        why_ok = all(
            bool(row.get("why_trusted") or row.get("reason")) for row in per if isinstance(row, dict)
        )
    elif trusted:
        why_ok = False
    check("R6", "every trusted identity has why", why_ok, {"per_trusted_address": per})
    check(
        "R7",
        "unique-only vs shared counts present",
        isinstance(phase1.get("unique_only_via_trusted_address"), dict)
        or isinstance(phase1.get("unique_emails_by_trusted_address"), dict),
        {
            "unique_only_via_trusted_address": phase1.get("unique_only_via_trusted_address"),
            "unique_emails_by_trusted_address": phase1.get("unique_emails_by_trusted_address"),
        },
    )
    # PR #74 FlightSim gate: 700 keys → 42,554 hits. That scope is the bug.
    check(
        "R8",
        "not the address-centric 700-key / 42554-hit dump",
        not (
            len(trusted) >= 100
            and int(phase1.get("retrieve_hit_count") or 0) >= 20_000
        ),
        {
            "trusted_n": len(trusted),
            "retrieve_hit_count": phase1.get("retrieve_hit_count"),
        },
    )

    return {
        "ok": not problems,
        "goal_complete": not problems,
        "problems": problems,
        "checks": checks,
        "flightsim": bool(gate.get("flightsim") or runtime.get("flightsim")),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", default="", help="Gate JSON path")
    args = parser.parse_args(argv)
    path = Path(args.path) if args.path else DEFAULT_PATH
    if not path.is_file():
        path = FALLBACK_PATH
    if not path.is_file():
        print(f"FAIL  missing gate file: {DEFAULT_PATH}", file=sys.stderr)
        return 1
    gate = json.loads(path.read_text(encoding="utf-8"))
    audit = audit_gate(gate)
    print(json.dumps(audit, indent=2, default=str))
    if not audit.get("ok"):
        print("FAIL  trusted-identity FlightSim gate", file=sys.stderr)
        return 1
    print("PASS  trusted-identity FlightSim gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
