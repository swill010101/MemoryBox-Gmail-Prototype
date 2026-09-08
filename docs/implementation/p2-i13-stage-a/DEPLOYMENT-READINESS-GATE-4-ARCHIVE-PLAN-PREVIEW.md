# FlightSim readiness: Gate 4 archive plan preview (Outcome B)

**Status:** Plan-only — **no register, unlock, start, or drains**  
**Waiver:** [NARROW-ACCEPTANCE-WAIVER.md](NARROW-ACCEPTANCE-WAIVER.md)  
**Plan:** [archive-manifest-proposal.json](archive-manifest-proposal.json)

Tom deferred Gate 4 execution (Outcome A) then authorized narrow bounded voice acceptance (option 2). This document covers **Outcome B only**: validate the five-source archive plan on FlightSim.

---

## Expected preview (dev checkout 2026-09-08)

| Field | Value |
|---|---|
| `purpose` | `acceptance_learning` |
| `scope_kind` | `archive` |
| `source_count` | 5 |
| `person_count` | 2 |
| `work_items` | 10 |
| `max_work_items` | 100 |
| `max_attempts` | 20 |
| `plan_sha256` | `f36cdb19c51abe13234b80c08b746901d5d195c5e8be621e10e5f2a85f46316c` |

If SHA or counts differ after pull, stop and reconcile plan bytes vs FlightSim checkout SHA.

---

## FlightSim commands (read-only)

```powershell
cd C:\MemoryBox
git pull --ff-only origin codex/p2-i13-stage-a

python -B -m memorybox.processing.control preview --plan docs\implementation\p2-i13-stage-a\archive-manifest-proposal.json
```

Optional: re-export owner truth and confirm annotation IDs still match plan intervals (do not commit export JSON):

```powershell
# With serve running:
# GET http://127.0.0.1:8790/annotations/transcript/coverage
```

---

## Explicitly not authorized by this step

- `register --plan …`
- `unlock --acceptance-ref …`
- `start --reference …`
- Recognition or speech drains
- Learn or queue enqueue

Next Gate 4 step after successful preview review: fresh founder sign-off for Outcome C (register only) or higher.

---

## Rollback

No runtime writes in Outcome B. No rollback required.
