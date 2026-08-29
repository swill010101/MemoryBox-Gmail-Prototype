#!/usr/bin/env python3
"""Requirement-by-requirement audit of ADDRESS_CENTRIC_GATE.json.

Goal completion requires a FlightSim Takeout archive gate with ok=true AND
flightsim=true. This verifier rejects waiting placeholders and local-only proves.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


DEFAULT_PATH = Path(
    "docs/test-output/historian-full-evidence/peggy-v2/ADDRESS_CENTRIC_GATE.json"
)


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

    reqs = gate.get("requirements") or {}
    counts = gate.get("counts") or {}
    inv = gate.get("inventory") or {}
    ledger = gate.get("ledger") or {}
    person = gate.get("person") or {}
    runtime = gate.get("runtime") or {}
    stop = str(gate.get("stop") or "")

    # Hard completion gates — never complete on waiting or non-FlightSim.
    check(
        "C1",
        "not a waiting placeholder",
        gate.get("waiting") is not True,
        {"waiting": gate.get("waiting")},
    )
    check(
        "C2",
        "flightsim=true (Takeout archive host)",
        gate.get("flightsim") is True,
        {
            "flightsim": gate.get("flightsim"),
            "runtime_flightsim": runtime.get("flightsim"),
            "hostname": runtime.get("hostname"),
        },
    )
    check(
        "C2a",
        "not ALLOW_DEV defaults (rejects cloud/local fake flightsim stamps)",
        runtime.get("allow_dev_defaults") is not True,
        {"allow_dev_defaults": runtime.get("allow_dev_defaults")},
    )
    check(
        "C2b",
        "P1 runtime host stamped",
        runtime.get("p1_runtime_host") is True,
        {"p1_runtime_host": runtime.get("p1_runtime_host")},
    )
    _hn = str(runtime.get("hostname") or "").strip().lower()
    check(
        "C2c",
        "hostname is not cloud agent sandbox",
        _hn not in {"", "cursor", "cursor-cloud"} and not _hn.startswith("sandbox"),
        {"hostname": runtime.get("hostname")},
    )
    check(
        "C3",
        "ok=true",
        gate.get("ok") is True,
        {"ok": gate.get("ok"), "problems": gate.get("problems")},
    )
    check(
        "C4",
        "stop before historian summarization",
        "historian" not in stop.lower()
        or "no historian" in stop.lower()
        or "gallery_and_full_evidence" in stop.lower(),
        {"stop": stop},
    )

    # PRD success criteria 1–6.
    check(
        "PRD1",
        "probe/inventory reports structured Peg Legg on peggo417",
        bool(inv.get("structured_has_peg_legg"))
        or bool(reqs.get("probe_structured_has_peg_legg")),
        {
            "structured_has_peg_legg": inv.get("structured_has_peg_legg"),
            "structured_occurrence_count": inv.get("structured_occurrence_count"),
        },
    )
    check(
        "PRD2",
        "Peg Legg / Peggy George pairing reported (George optional on thin Takeout)",
        bool(inv.get("structured_has_peg_legg"))
        or bool(inv.get("structured_has_peggy_george"))
        or bool(inv.get("quoted_has_peggy_george")),
        {
            "structured_has_peg_legg": inv.get("structured_has_peg_legg"),
            "structured_has_peggy_george": inv.get("structured_has_peggy_george"),
            "quoted_has_peggy_george": inv.get("quoted_has_peggy_george"),
        },
    )
    check(
        "PRD3",
        "ledger stores address → resolved person",
        bool(reqs.get("ledger_resolved_to_person"))
        or (
            str(ledger.get("address") or "") == "peggo417@hotmail.com"
            and bool(ledger.get("resolved_person_id"))
            and str(ledger.get("resolution_status") or "") == "confirmed"
        ),
        ledger,
    )
    check(
        "PRD4",
        "discover without requiring prior Person email",
        bool(reqs.get("discover_without_prior_email"))
        or ledger.get("had_peggo_contact_before_resolve") is False,
        {
            "discover_without_prior_email": reqs.get("discover_without_prior_email"),
            "had_peggo_contact_before_resolve": ledger.get(
                "had_peggo_contact_before_resolve"
            ),
        },
    )
    check(
        "PRD5a",
        "Gallery email > 0",
        int(counts.get("gallery_email_n") or 0) > 0
        or bool(reqs.get("gallery_email_gt_0")),
        {"gallery_email_n": counts.get("gallery_email_n")},
    )
    check(
        "PRD5b",
        "Full-Evidence V2 email > 0",
        int(counts.get("full_evidence_email_items") or 0) > 0
        or bool(reqs.get("full_evidence_email_gt_0")),
        {"full_evidence_email_items": counts.get("full_evidence_email_items")},
    )
    check(
        "PRD5c",
        "retrieve includes Peg Legg–labeled mail",
        int(counts.get("retrieve_peg_legg_labeled") or 0) > 0
        or bool(reqs.get("retrieve_peg_legg_labeled_gt_0")),
        {"retrieve_peg_legg_labeled": counts.get("retrieve_peg_legg_labeled")},
    )
    check(
        "PRD5d",
        "Person is Peggy George (multi-token)",
        (str(person.get("display_name") or "").strip().lower() == "peggy george")
        or bool(reqs.get("person_is_peggy_george")),
        person,
    )
    check(
        "PRD6",
        "peggo417 confirmed on Person addresses",
        bool(reqs.get("peggo417_confirmed"))
        or "peggo417@hotmail.com"
        in [str(a).lower() for a in (person.get("addresses") or [])],
        {"addresses": person.get("addresses"), "peggo417_confirmed": reqs.get("peggo417_confirmed")},
    )

    goal_complete = (
        gate.get("ok") is True
        and gate.get("flightsim") is True
        and gate.get("waiting") is not True
        and not problems
    )
    return {
        "goal_complete": goal_complete,
        "ok": not problems,
        "problems": problems,
        "checks": checks,
        "gate_summary": {
            "ok": gate.get("ok"),
            "flightsim": gate.get("flightsim"),
            "waiting": gate.get("waiting"),
            "error": gate.get("error"),
            "person": person.get("display_name"),
            "counts": counts,
        },
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "path",
        nargs="?",
        default=str(DEFAULT_PATH),
        help=f"Gate JSON path (default: {DEFAULT_PATH})",
    )
    ap.add_argument(
        "--require-flightsim",
        action="store_true",
        default=True,
        help="Require flightsim=true for goal_complete (default)",
    )
    ap.add_argument(
        "--allow-local",
        action="store_true",
        help="Allow flightsim=false for local dry-run of checks (not goal_complete)",
    )
    args = ap.parse_args(argv)
    path = Path(args.path)
    if not path.is_file():
        print(json.dumps({"ok": False, "error": f"missing {path}"}, indent=2))
        return 2
    gate = json.loads(path.read_text(encoding="utf-8-sig"))
    report = audit_gate(gate)
    if args.allow_local and gate.get("flightsim") is not True:
        # Local dry-run: drop FlightSim host checks, but never goal_complete.
        report["goal_complete"] = False
        report["local_dry_run"] = True
        report["problems"] = [
            p
            for p in report["problems"]
            if not (p.startswith("C2:") or p.startswith("C2a:") or p.startswith("C2b:") or p.startswith("C2c:"))
        ]
        # Recompute ok without C2* host checks.
        non_c2 = [c for c in report["checks"] if not str(c["id"]).startswith("C2")]
        report["ok"] = all(c["ok"] for c in non_c2) and gate.get("waiting") is not True
    print(json.dumps(report, indent=2, default=str))
    if report.get("goal_complete"):
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
