# Consolidated final I13 acceptance review (template — after FlightSim proof)

**Status:** **DRAFT — pending live FlightSim proof**  
I13 must **not** close on FR-005 playback or the two-source fragment pilot alone.

Complete [CONSOLIDATED-DEPLOYMENT-REQUEST-ACCEPTANCE-LEARNING.md](CONSOLIDATED-DEPLOYMENT-REQUEST-ACCEPTANCE-LEARNING.md) and [LEGACY-HVRT-FRAGMENT-RECONCILIATION-GATE.md](LEGACY-HVRT-FRAGMENT-RECONCILIATION-GATE.md) before founder sign-off.

---

## Prerequisites completed (desktop)

- [x] Admin landing, Jobs, Learned Evidence implemented
- [x] Bounded `acceptance-learning-bounded-plan.json` validates (88 work items, SHA `edd2ddc39…`)
- [x] FR-005 offline binder passed ([fr005-playback-spotcheck-proof.json](fr005-playback-spotcheck-proof.json))
- [x] Interactive Learn two-lane separation + async follow-on (commit on `codex/p2-i13-stage-a`)
- [x] Legacy fragment reconciliation gate tooling + offline tests (manifest-scoped; not archive-wide)
- [x] Founder decision B recorded

## Live FlightSim proof (fill after deploy)

### Interactive Learn + Admin

| # | Checkpoint | Class | Evidence |
|---|---|---|---|
| 1 | Face box → Person → Learn | | |
| 2 | Transcript → Person → voice Learn | | |
| 3 | Admin → Learned Evidence | | |
| 4 | Admin → Jobs (async follow-on rows) | | |
| 5 | Correction / removal | | |
| 6 | Learn on after stop + enable-interactive-learn | | |
| 7 | Bounded acceptance_learning admission | | admission UUID, start/stop refs |
| 8 | FR-005 Explore spot-check | | manual note + binder JSON |

### Legacy HVRT fragment reconciliation (manifest-scoped)

| # | Checkpoint | Class | Evidence |
|---|---|---|---|
| F1 | Full manifest inventory | | `legacy-hvrt-fragment-inventory.json` |
| F2 | Founder-reviewed preview | | `legacy-hvrt-fragment-preview.json` |
| F3 | Allowlist published + deployed | | `publish-fragment-allowlist.py` reference |
| F4 | Source/observation/provenance preserved | | inventory + DB spot-check |
| F5 | Duplicate presentations removed | | before/after counts |
| F6 | Timing gaps preserved | | preview partitions |
| F7 | Pipeline anti-fragment (future scans) | | unit tests + cadence proof |
| F8 | Live Gallery/retrieval representative proof | | owner notes + `verify-fragment-reconciliation.py` |

Inspector outputs to attach:

- `inspect-interactive-learn-reconciliation.py` → Learn checks **passed**
- `inspect-face-voice-corroboration.py` → `ok: true`
- `verify-fragment-reconciliation.py` → `ok: true` (after F1 inventory JSON attached)

---

## Founder acceptance (after proof)

- [ ] **Accept** P2-I13 closed on completed scope  
- [ ] **Reject** — return for: ___________________

**Reference:** ___________________  
**Date:** ___________________
