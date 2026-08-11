# MBBS-001 Increment 12A — Thin Status Screen — Final Definition

**Status:** **BUILT — READY FOR OWNER ACCEPTANCE** (truthfulness refinements locked 2026-08-11)  
**Date:** 2026-08-11  
**Roadmap:** After **I12 MV Export (ACCEPTED)** · P1/P2 **bridge utility** — **not** final P2 Dashboard  
**Route:** `/status/ui`  
**API:** `GET /status/summary` (all tabs’ payload; Refresh re-fetches)  
**Owner gate:** Open Status on FlightSim; land on Archive Summary; navigate all tabs; see real counts / explicit Not available; drill to existing UIs; Refresh without SQL.

**Product intent:** Let the owner quickly see what MemoryBox contains, what is understood vs unknown/unreviewed, what processing is pending/failing, and where small owner effort yields large archive gains — without a P2 polish project.

**OUT:** Final Dashboard styling · charts · new IQ engine · kinship inference · new Timeline · provider admin redesign · notifications · multi-user · **universal archive-health %** · inventing unsupported counts as `0` · collapsing distinct identity states into one synthetic “unknown face clusters” number

---

## 0. Locked truthfulness refinements (2026-08-11)

1. **Identity states stay separate.** Prefer distinct metrics: provider identity clusters not linked to MB Person; unresolved MB People; unreviewed identity candidates. Do **not** collapse into one “unknown face clusters” number unless the provider exposes that exact state reliably. If exact provider cluster count is unavailable → **Not available** (do not synthesize).  
2. **Timeline dates:** described/effective where available; genuine evidence/event dates where appropriate. **Do not** treat Story `created_at` as life/event chronology (record-creation metadata only, if shown). No meaningful date → **undated**.  
3. **Video dated/undated:** Do **not** infer “undated ≈ all source videos” because the DTO lacks a date field. If reliable source-video date is not exposed → `Not available — provider/domain does not currently expose reliable source date`. High-leverage dating tasks only when **computable** from real source→moment relationships.  
4. **Narrow partial labels:** MemoryBox-managed audio → `MemoryBox-managed audio recordings`. Artifact-backed documents → label/disclose partial coverage (not generic “Documents / scans”).  
5. **Archive Health:** Strong coverage · Needs attention · High-leverage help (3–5 real items). **No** universal health percentage.  
6. **`/status/summary` metric contract** (provider-derived / partial): `value`, `state` ∈ `available|unavailable|partial|deferred`, `source`, `last_updated`, `reason`. Client must **not** treat unavailable as zero.

---

## 1. Tabs (order; Archive Summary = default)

1. Archive Summary  
2. People & Identity  
3. Photos  
4. Video  
5. Stories & Knowledge  
6. Artifacts  
7. Communications  
8. Timeline  
9. Sources & Providers  
10. Processing  
11. Archive Health  

---

## 2. Metrics matrix (available now vs deferred)

Legend: **YES** = real count · **NA** = unavailable/not connected · **PARTIAL** = disclosed partial · **DEFER** = deferred (no fake zero)

### 2.1 Archive Summary

| Metric | Status | Source |
|--------|--------|--------|
| People | YES | `people` confirmed+unresolved |
| Stories | YES | `stories` active |
| Journal Entries | YES | `journal_entries` active |
| Guided Capture Responses | YES | `guided_capture_responses` |
| Artifacts / Keepsakes | YES | `artifacts` active |
| Photos indexed | YES* / NA | Immich statistics if healthy; else unavailable |
| Source videos | YES* / NA | HVRT bounded list if healthy |
| Searchable video moments | YES* / NA | HVRT presence spans bounded |
| MemoryBox-managed audio recordings | PARTIAL | GC/Journal/Story `audio_uri` rows only |
| Emails indexed | YES | `evidence` communication |
| Calendar events | YES | `evidence` calendar_event |
| SMS / Text Messages | NA | Not yet connected |
| Artifact-backed documents / letters | PARTIAL | Artifact kinds letter+document |
| Provider identity clusters not linked | NA unless exact | Do not synthesize from Immich people list |
| Unresolved MB People | YES | `people.status=unresolved` |
| Unreviewed identity candidates | NA / PARTIAL | Only if durable review queue exists; else NA |
| New Guided Capture responses | YES | `new_response_count()` |
| Videos awaiting analysis | DEFER | No durable queue |
| Audio awaiting transcription (GC) | PARTIAL | GC `stt_status` pending/failed |
| Documents awaiting OCR | DEFER | No OCR queue |
| Processing errors | YES | `jobs` error |
| Last activity | YES | Max recent domain/job timestamps |

### 2.2–2.5

People tab mirrors separate identity states. Photos: Immich total if available; date/location/favorites/duplicates/blur deferred. Video: source vs moments required; **dated/undated source = NA** until reliable date exposed. Stories/Journal/GC/Artifacts/Communications as prior I12A definition. Timeline: Journal described dates + evidence event dates; Stories without event date = undated; no Story `created_at` chronology. Processing: jobs pending vs failed distinct. Archive Health: three sections, no score.

---

## 3. Metric object contract

```json
{
  "key": "photos_indexed",
  "label": "Photos indexed",
  "value": null,
  "display": "Not available",
  "state": "unavailable",
  "available": false,
  "source": "immich:/server/statistics",
  "last_updated": "2026-08-11T…",
  "reason": "Provider unavailable",
  "href": "/library/ui",
  "note": "optional human detail"
}
```

`available` mirrors `state == "available"` for simple clients. **Never** coerce unavailable/deferred to `value: 0`.

---

## 4. Drill-down / performance / acceptance / auth

Unchanged from authorized I12A definition (existing UIs only; PG counts + bounded provider probes; FlightSim §19 gate; no P2 Dashboard expansion).

---

*End I12A Final Definition — truthfulness locked.*
