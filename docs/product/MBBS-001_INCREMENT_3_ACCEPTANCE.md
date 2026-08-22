# MBBS-001 Increment 3 — Acceptance report

**Date:** 2026-08-09  
**Status:** **ACCEPTED**  
**Definition:** [MBBS-001_INCREMENT_3_DEFINITION.md](MBBS-001_INCREMENT_3_DEFINITION.md)  
**Decision log:** [MBBS_DECISION_LOG.md](MBBS_DECISION_LOG.md) § Increment 3  
**Prior:** I1 tag `increment-1-accepted` · I2 accepted  

---

## Acceptance criteria

| ID | Criterion | Result |
|----|-----------|--------|
| **I3-A** | Email → Source + Evidence (`communication`) + payload contract | **PASS** — synthetic mbox |
| **I3-A2** | Calendar → Source + Evidence (`calendar_event`) + payload contract | **PASS** — synthetic ICS (2 events) |
| **I3-B** | Originals untouched | **PASS** — fixture bytes unchanged after ingest |
| **I3-C** | No POC SQLite dual-write | **PASS** — PostgreSQL only |
| **I3-D** | Clear Qdrant → rebuild from PG → Evidence IDs + fixed retrieval | **PASS** — 3 points restored; retrieval ok |
| **I3-E** | Failure visible | **PASS** — missing mbox → job error |
| **I3-F** | Keep runnable | **PASS** — health ok (increment 3) |
| **I3-G** | Config-only portability / no forbidden hardcodes | **PASS** — scanner clean |

### Real-data smoke (where practical)

| Channel | Result |
|---------|--------|
| Email | **SKIPPED** — `MEMORYBOX_SMOKE_MBOX_URI` not set; no local real mbox found under working/archive |
| Calendar | **SKIPPED** — `MEMORYBOX_SMOKE_ICS_URI` not set; no local real ICS found |

When smoke URIs are configured on a host, re-run `python -m memorybox prove-ingest`. Reports must record **counts/IDs only** — never real family content.

### Prove command

```powershell
$env:MEMORYBOX_ALLOW_DEV_DEFAULTS = "1"
$env:MEMORYBOX_DATABASE_URL = "postgresql://…@…/memorybox"   # per host
$env:MEMORYBOX_QDRANT_URL = ":memory:"   # or network URL on P1 runtime host
python -m memorybox prove-ingest
```

Result (2026-08-09): `"ok": true` — synthetic email Evidence ID + 2 calendar Evidence IDs indexed; fixed retrieval passed. **No real message/event content in this report.**

---

## Delivered

| Path | Role |
|------|------|
| `memorybox/ingest/comms_email.py` | mbox → Source + Evidence |
| `memorybox/ingest/comms_calendar.py` | ICS → Source + Evidence |
| `memorybox/ingest/rebuild_index.py` | Qdrant clear/rebuild/retrieve from PG |
| `memorybox/ingest/acceptance.py` | `prove-ingest` |
| `memorybox/providers/calendar/` | ICS CalendarReadProvider |
| `memorybox/providers/_fixtures/i3_synthetic.mbox` | Synthetic email |
| `memorybox/providers/_fixtures/i3_synthetic.ics` | Synthetic calendar |
| `memorybox/config.py` | Host-portable settings (D7) |

---

## Deferred (must remain on P1 plan)

**SMS / iMessage → Source + Evidence** — later communications increment (or Increment 9). Not started.

---

## Stop

**Increment 3 accepted.** Do **not** begin Increment 4 (Ask/UX), SMS, photo ingest, Story, or Journal without explicit authorization.
