# Phase C correctness diagnosis (stop before deploy)

**Date:** 2026-09-16  
**Code:** unreleased Gallery/Ask fix on `codex/p2-i14-communications` (this commit). Prepared v3 data unchanged.  
**Tests:** `python -m unittest tests.test_i14_phase_c_correctness tests.test_i14_gallery_scope tests.test_i14_gallery_prepared`  
**Do not recycle FlightSim serve until founder authorizes.**

## Root causes

| Defect | Cause |
|--------|--------|
| ~25–40 s Ask, year-bounded no faster | Blocking Ask path retrieved raw communications (PG/Qdrant) **before photos**, then `_attach_hidden_sms` with cap **10,000**. Prepared-email SQL is hundreds of ms ([PHASE-C-GALLERY-TIMINGS.json](PHASE-C-GALLERY-TIMINGS.json)). Year window did not skip that SMS/comms retrieve. |
| Curator omits email threads | First Curator is built with `thread_n=0` while prepared buckets are pending; Communications pill used `scopedThreads` still 0. |
| Communications pill without email | Same: pill `id=email` sums threads+SMS only after prepared JSON; first paint had threads=0. Label is Communications. |
| Tom: 90 threads, one **1970** card | v3 stores missing timestamps as **`1970-01-01`** (loader `MISSING_TS`). Tom has **90 threads / 91 messages** on that sentinel. Timeline treated 1970 as a real year and hid **22 real years** (25,278 other Tom threads). Not a one-card SQL collapse of all mail. |
| Cora unrelated Stories | `search_stories` token-matched Ask words. “Cora **Will**” matched any Story mentioning Will/Tom/Sue/Peggy/Mom/Dad. Direct `about_person` / `story_version_people` was not required. |
| Immich vs MB | Not equated in this pass. Needs a live Immich person-asset probe vs MB photo/video items after deploy. Unexplained is **not** zero. |

## Timing (evidence, not a served FlightSim capture)

Serve was **not** recycled, so browser cold/warm of the five Asks was not re-timed on production. Instrumented stages now on the Ask token: orchestrator `stage_clock`, `explore_state.pipeline_ms.sms_attach_ms`, `ask_correlation_id`, background prepared-comms + `/explore/api/sms-hydrate`.

| Stage | Blocking on old serve | After this code (once deployed) |
|-------|------------------------|----------------------------------|
| Person / date | orchestrator `person_resolution_ms` | same, blocking |
| Raw email/SMS retrieve | blocking, before photos | **deferred** unless explicit SMS/email Ask |
| Photos / video | after comms | first, blocking |
| Stories / artifacts / calendar | blocking, small | blocking, small |
| Prepared-email buckets | background fetch | background |
| SMS hydrate | blocking `_attach_hidden_sms` | background `sms-hydrate` |
| First Gallery | after SMS | after photos/stories, before SMS/email complete |
| Curator/pills | photos-only then overwrite | shell first; counts update on hydrate |

**Hypothesis for the fixed 25–40 s:** SMS retrieve + comms merge at cap 10k, not prepared email. Confirm on FlightSim with `explore_state.pipeline_ms` after recycle.

## Tom email counts (v3, read-only)

- Sentinel 1970-01-01 messages: **91**; threads: **90**
- Real years 2005–2026: **22** year buckets, **25,278** threads
- NULL `sent_at`: **0**
- After Gallery SQL excludes the sentinel, unbounded Tom Ask should show **22 year cards**, not one 1970 card. Undated_n reports the 90.

## Fixes in this SHA (Ask/Gallery only)

- Bucket SQL ignores `sent_at::date = 1970-01-01`; JS treats that prefix as undated.
- Person-scoped Stories require a Story–Person link; last-name token match is not enough.
- I14 mixed Person Ask defers raw comms retrieve and blocking SMS attach; SMS hydrates in background; new Ask aborts both fetches.
- `scoped_counts` object: photos, videos, SMS, email threads, Stories, Artifacts, calendar, communications=SMS+email.
- Communications pill uses that sum. Cache `explore.js?v=i14-c7`.

## Immich equation (not closed)

Immich person assets  
− videos counted separately  
− duplicates / unavailable / archived  
− MB evidence not from Immich  
− face/Person map  
− date/Ask filters  
− pagination  
= MB Gallery photos. **Unexplained still unknown.** Do not declare match.

## Proof plan after authorized recycle

1. Cold/warm the five Asks; save `ask_correlation_id` + `pipeline_ms` + prepared `query_ms`.
2. Tom unbounded: 22 year cards, Communications count = email threads + SMS, no 1970 card.
3. Open 2024: months/threads for 2024 only.
4. Cora: no Tom/Sue/Peggy/Mom/Dad Stories unless linked to Cora.
5. Screenshots: Curator, Communications pill, Tom year strip, Cora Stories.

## Deploy (not this turn)

```powershell
cd C:\MemoryBox
git fetch
git checkout <this-sha>
# recycle serve with repo venv — founder go only
```

Pending must stay empty. No migrate.

## Remaining risks

- Background SMS hydrate can still take tens of seconds; first paint should not wait.
- `render()` after hydrate may still jump scroll (mitigate in follow-up if seen).
- Orchestrator photo retrieve can still dominate some Asks.
- Immich unexplained not closed.
- 90 sentinel threads stay in v3 data; Gallery hides them from year cards only.
