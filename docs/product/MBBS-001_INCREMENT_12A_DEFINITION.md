# MBBS-001 Increment 12A — Thin Status Screen — Definition + Implementation Note

**Status:** **AUTHORIZED TO BUILD** (Tom: I12 accepted + write definition then implement Status)  
**Date:** 2026-08-11  
**Roadmap:** After **I12 MV Export (ACCEPTED)** · P1/P2 **bridge utility** — **not** final P2 Dashboard  
**Route:** `/status/ui`  
**API:** `GET /status/summary` (all tabs’ payload; Refresh re-fetches)  
**Owner gate:** Open Status on FlightSim; land on Archive Summary; navigate all tabs; see real counts / explicit Not available; drill to existing UIs; Refresh without SQL.

**Product intent:** Let the owner quickly see what MemoryBox contains, what is understood vs unknown/unreviewed, what processing is pending/failing, and where small owner effort yields large archive gains — without a P2 polish project.

**OUT:** Final Dashboard styling · charts · new IQ engine · kinship inference · new Timeline · provider admin redesign · notifications · multi-user · fake universal health score · inventing unsupported counts as `0`

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

Legend: **YES** = show real count · **NA** = show `Not available` / `Not connected` with reason · **DEFER** = omit or label deferred (no fake zero)

### 2.1 Archive Summary

| Metric | Status | Source |
|--------|--------|--------|
| People | YES | `COUNT(people)` active statuses |
| Stories | YES | `stories` active |
| Journal Entries | YES | `journal_entries` active |
| Guided Capture Responses | YES | `guided_capture_responses` |
| Artifacts / Keepsakes | YES | `artifacts` active |
| Photos indexed | YES* | Immich statistics/search if healthy; else NA (provider down) — no fake 0 |
| Source videos | YES* | HVRT `list_videos` bounded total if healthy; else NA |
| Searchable video moments | YES* | HVRT spans/search bounded if healthy; else NA |
| Audio recordings | PARTIAL | GC + journal/story audio URIs present (PG); Immich audio NA |
| Emails indexed | YES | `evidence` `communication` |
| Calendar events | YES | `evidence` `calendar_event` |
| SMS / Text Messages | NA | Not connected (P1) |
| Documents / scans | PARTIAL | Artifact kinds letter/document + mb_managed reps |
| Unknown face clusters | YES* | Immich people without MB mapping / HVRT faces — bounded; else NA |
| Unreviewed identity candidates | PARTIAL | Unresolved people + GC-adjacent; Review faces when HVRT up |
| New Guided Capture responses | YES | `new_response_count()` |
| Videos awaiting analysis | DEFER | No durable pending-analysis queue in PG |
| Audio awaiting transcription | PARTIAL | GC `stt_status=failed` / pending if column used |
| Documents awaiting OCR | DEFER | No OCR queue |
| Processing errors | YES | `jobs` status=`error` |
| Last activity | YES | Max of recent domain/job timestamps |

### 2.2 People & Identity

| Metric | Status | Source / drill |
|--------|--------|----------------|
| Known / named People | YES | people with display_name · `/people/ui` |
| Owner-confirmed | YES | `status=confirmed` |
| Provisional / unresolved | YES | `status=unresolved` |
| Provider identities | YES | `provider_identities` |
| Relationships recorded | YES | `person_relationship_assertions` current |
| Direct family (subset) | PARTIAL | role_kind in thin vocab if present |
| Photo/video % linked | DEFER | Needs expensive Immich/HVRT corpus join — deferred |
| Unknown face clusters | YES* | provider · `/review/ui` |

### 2.3 Photos

| Metric | Status | Source |
|--------|--------|--------|
| Total photos | YES* | Immich stats if available |
| Dates / location / favorites / duplicates / blur | DEFER | Not wrapped; omit rather than invent |

### 2.4 Video (required distinction)

| Metric | Status | Source |
|--------|--------|--------|
| Source video count | YES* | HVRT list |
| Duration total | PARTIAL | Sum duration_sec when present |
| Dated / undated source | PARTIAL | Library treats video undated today → undated count ≈ source count when no date on DTO |
| Transcripts / face analysis pending | DEFER / PARTIAL | Only if worker exposes; else NA |
| Searchable moments | YES* | presence spans count (bounded) |
| High-leverage dating task | YES only if computable | If moments link to undated sources with counts — else omit |

### 2.5 Stories & Knowledge / Artifacts / Communications / Timeline / Processing / Health

Implement from PG counts listed above; SMS = Not connected; Timeline earliest/latest from journals described dates + evidence payloads + story created_at as weak signal (label provenance); Processing from `jobs` only (`processing_states` unused); Archive Health derives 3–5 tasks from real non-zero attention metrics.

---

## 3. Drill-down destinations

| Count | Destination |
|-------|-------------|
| People / confirmed / unresolved | `/people/ui` |
| Review / faces / unknown | `/review/ui` |
| Stories | `/story/ui` |
| Journals | `/journal/ui` |
| Artifacts | `/artifact/ui` |
| Guided Capture / new | `/guided-capture/ui` |
| Library / undated | `/library/ui` |
| Export | `/export/ui` |
| Ask | `/ask/ui` |

No destination → count only.

---

## 4. Performance

- Prefer `COUNT(*)` / `GROUP BY` on PG.  
- Bound Immich/HVRT calls (timeouts; no full asset pagination).  
- Provider down → explicit unavailable, not zero.  
- Single `/status/summary` payload; client Refresh only.

---

## 5. Acceptance (FlightSim)

See §19 of owner request — land on Archive Summary; all tabs; source vs moments; known vs unknown; providers; pending vs failed; high-leverage tasks; drill-downs; Refresh.

---

## 6. Authorization

Build I12A thin Status only under this definition. No P2 Dashboard expansion.

---

*End I12A definition / implementation note.*
