# I14 v3 activation closeout (published)

**Date:** 2026-09-16  
**Authorization:** one guarded retry after the first attempt rolled back.  
**Outcome:** **v3 is the sole published/active household-email generation.** v1 is retained superseded. v2 is unchanged (validated, unpublished, inactive). Serve process recycle from this desktop was blocked (no WinRM/SSH/WMI/PsExec). Gallery already reads v3 from the database. Disk on FlightSim is the reviewed fix commit.

No generation UUIDs, addresses, bodies, or dump payloads in this file.

---

## 1. Prove the postcheck fix

| Item | SHA / result |
|------|----------------|
| Commit that first stored `SELECT id, algo_version, status, published, is_active` in v3 postcheck | **`6435677`** (`Record the rolled-back v3 activation attempt and keep the guarded activator.`) |
| Activator diff after that commit | none — the only activation-path correction vs the crashed in-memory script was selecting generation `id` |
| Regression tests | **`b0d3beb`** (`Add a v3 activator regression for the postcheck generation id KeyError.`) |
| Reviewed FlightSim runtime target | **`b0d3beb6f86213d70b9bcb61d9516bfa8c40235b`** (includes 6435677 + tests) |

Disposable PostgreSQL (`python -m unittest tests.test_i14_prepared_activate_v3`, 5 tests, OK):

- omitting `id` reproduces `KeyError: 'id'`
- selecting `id` lets postcheck finish
- guarded `run()` activates and every postcheck completes
- an injected postcheck exception rolls the whole activation back (v1 still sole published)
- v1 → v3 → v1 rollback via 040 `comms_prepared_activate_generation` still works; v2 stays validated unpublished

---

## 2. Preflight (read-only)

FlightSim clone detached **`b0d3beb`**, tracked-clean. Ledger 001–040, `/health` pending empty. v1 was still sole published+active; v2/v3 validated unpublished inactive; failed/building 0; `comms_prepared_assert_generation_ready(v3)` ok. Corrected postcheck queries were run read-only against live v1/v2/v3 rows (child counts, six-way, voice, archive, commercial, quote) before the retry.

v3 commercial (missing from the failed closeout):

| commercial_class | n |
|---|---:|
| not_commercial | 70,214 |
| suppress_default | 18,710 |
| retain_life_evidence | 1,555 |
| uncertain | 768 |

v3 quote:

| quote_quality | n |
|---|---:|
| clean | 56,321 |
| suspected_contamination | 34,926 |

---

## 3. Backup

Prior dump `pre-i14-v3-activate-20260916-150336` was **not reused**: generation rows were unchanged after the rollback, but Historian Capture ticks and other app writes could not be excluded (dump size also differed by 1 byte). Fresh dump:

| Field | Value |
|-------|--------|
| Folder (C:) | `C:\MemoryBox-backups\pre-i14-v3-activate-retry-20260916-153203` |
| Copy (E:) | `E:\MemoryBox-backups\pre-i14-v3-activate-retry-20260916-153203` |
| Bytes | 603,422,223 |
| SHA-256 | `6B028133E69F06676BEC6C64E5A9E3A719314643E387A1BB1F989681D31F3DE2` |
| `pg_dump` / `pg_restore` | PostgreSQL 17.10 |
| `pg_restore -l` non-comment TOC | 693 |
| Validate | **ok** |

---

## 4. Activation (exactly once)

| Field | Value |
|-------|--------|
| Tool | `python -m memorybox.ops.i14_prepared_activate_v3` (not 038) |
| Confirm | `activate-unpublished-v3-retain-v1-v2` |
| Wall start (UTC) | 2026-09-16T20:33:43Z |
| SQL `updated_at` | **2026-09-16 20:34:19.942596+00** |
| Wall end (UTC) | 2026-09-16T20:34:35Z |
| Result | `ok: true`, `activation_called: true` |
| Retry after this | **not performed** |

---

## 5. Exact generation-state table (live)

| algo_version | status | published | is_active |
|--------------|--------|-----------|-----------|
| `i14-prepared-email-v1` | superseded | false | false |
| `i14-prepared-email-v2` | validated | false | false |
| `i14-prepared-email-v3` | published | true | true |

Published **1**, active **1** (v3), failed/building **0**. v1 retained for authorized rollback.

---

## 6. Counts (v3 live)

| Kind | Count |
|------|------:|
| Threads / messages / participants / attachments | 40,996 / 91,247 / 294,061 / 28,467 |
| Completeness | 91,281 = 91,247 + 26 + 2 + 6 + 0 |
| authored_displayable | 90,001 |
| non_substantive | 169 |
| correctly_empty | 323 |
| attachment_only | 695 |
| prepared_text_unavailable | 59 |
| uncertain | 0 |
| Voice Tom / Peggy / Sue | 11,578 / 1,345 / 210 |
| commercial | 70,214 / 18,710 / 1,555 / 768 (not / suppress / retain / uncertain) |
| quote | 56,321 clean / 34,926 suspected_contamination |

Archive unchanged: **188,656 / 27 / 287,010**.

---

## 7. Gallery / originals / health

- `GET /explore/api/prepared-thread/T-39987`: **ok**. Ordinal 2 prepared_chars **129**, voice_corpus **false** (v3 John recovery; v1 was empty). Every message had `original_href`.
- Immutable original HTTP for that ordinal-2 href: **200**.
- `/health`: **ok**, pending empty, `applied_n=40`.
- Historian Capture: Namecheap live **ok**, cadence **active**, last tick **ok**.
- Explore UI loaded; an unscoped Ask shows 0 memories until a person/range is chosen. Prepared-thread API is the v3 identity proof.

---

## 8. Serve recycle / runtime SHA

| Surface | SHA |
|---------|-----|
| FlightSim on-disk clone | **`b0d3beb6f86213d70b9bcb61d9516bfa8c40235b`** (detached, tracked-clean) |
| Live serve process | **not recycled from this desktop** (SSH/WinRM/WMI/PsExec denied). Process still the pre-FF listener. |
| Recycle script staged | `C:\MemoryBox\tmp\i14-recycle-serve-once.ps1` on FlightSim (repo venv `C:\MemoryBox\.venv\Scripts\python.exe -m memorybox serve`) |

Gallery already follows `comms_prepared_active_generations`, so it resolves **v3** without a process recycle. Runtime code SHA is **not** proven as `b0d3beb` until that script (or `startmb.ps1 -Restart -SkipChrome`) runs **on FlightSim**. Startup `migrate()` must apply nothing (pending already empty).

---

## 9. Rollback readiness

- Fresh retry dump above.
- Function path: set v1 `status=validated`, `comms_prepared_assert_generation_ready(v1)`, `comms_prepared_activate_generation(v1)` (disposable-proven; still needs founder go).
- v1/v2/v3 rows were not deleted.

---

## 10. Remaining Phase C defects / stops

- Serve process not yet on `b0d3beb`.
- 59 unavailable (open original); 169 non_substantive; accepted voice drop vs v1.
- SMS/calendar prepared stores, I11A, Gallery/SMS product work, performance: untouched.
- v2 remains unpublished on purpose.

---

## Stop

Stopped after verification. No second activate, no migrate, no reload, no deletes.
