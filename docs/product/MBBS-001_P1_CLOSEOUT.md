# MBBS-001 — P1 closeout

**Status:** **CLOSED** (owner 2026-08-11)  
**Final P1 increment:** [Increment 12A — Thin Status](MBBS-001_INCREMENT_12A_ACCEPTANCE.md) — **ACCEPTED**  
**Next:** P2 — owner will supply the next build document under `docs/product/` (new agent / new authorization). Do **not** start P2 build from this closeout alone.

## What P1 proved (summary)

| Track | Outcome |
|-------|---------|
| Providers / Ask / Review / People | Accepted through I1–I8 path (see Decision Log) |
| Artifacts / kinship thin / EVS-014 | I9 / I9A / I10 accepted |
| Guided Capture | I11 accepted |
| MV Export (EF-16) | I12 accepted — exit package `memorybox_export_format: 1` |
| Thin Status | I12A accepted — `/status/ui` orientation bridge (not final P2 Dashboard) |

## Explicitly parked for P2 / later (do not reopen as P1)

See living backlog: [MBBS_P1_P2_BACKLOG.md](MBBS_P1_P2_BACKLOG.md)

| ID | Topic |
|----|--------|
| **TASK-P1P2-004** | **Immich Status / Photos inventory** — ping OK; library totals Not available (API key / endpoint access). Fix early in P2. |
| TASK-P1P2-001 | Universal Immich lazy-teach |
| TASK-P1P2-002 | Kinship inference graph |
| TASK-P1P2-003 | Export import-back / restore |
| (ops / ingest) | Full Gmail mbox from staged Sources → Evidence; SMS ingest; real HVRT serve env for video counts |

## Authoritative staged Sources (media-server)

`\\media-server\photos\memorybox\sources` — `email/`, `sms/`, `calendar/` (+ MANIFEST). Status Communications can inventory staged vs PG Evidence. Full ingest is **not** a silent P1 leftover — authorize explicitly in P2+.

## Stop line

No further P1 increments. No P1 polish. Next work only under an explicit P2 (or named TASK) authorization and definition document.
