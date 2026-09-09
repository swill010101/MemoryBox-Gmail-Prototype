# Consolidated P2-I13 deployment request (final)

**Date:** 2026-09-09  
**Branch:** `codex/p2-i13-stage-a`  
**Release SHA:** see [I13-FINAL-RELEASE.json](I13-FINAL-RELEASE.json) — **deploy this pin only, not branch tip**  
**Founder session:** one authorization → Phases 1–6 without routine pauses  

---

## Request

Authorize **one** FlightSim deployment and **one** founder test session covering:

| Scope | Deliverables |
|-------|----------------|
| **A. Interactive Learn + Admin** | Explore face/voice Learn; Admin Jobs + Learned Evidence; correction/withdrawal; bounded jobs in Admin |
| **B. Persistent interactive Learn** | Two authorization lanes; stop → `enable-interactive-learn`; retain `MEMORYBOX_I13_ADMISSION_ID`; 22-video manifest only; archive locked |
| **C. Legacy HVRT fragments** | Manifest-scoped presentation reconciliation; preserve evidence; suppress duplicate cards; timing gaps preserved |
| **D. Explicit deferral** | No Scan for New Assets, archive intake, job-progress expansion, nightly scan (I18); no archive C/D/E |

---

## Baseline verified (desktop)

| Commit | Role |
|--------|------|
| `306c079272f4561b83412576d77e6a44c7cf2fa9` | Learn/Admin baseline |
| `bd76228a76d5b4b029814a77e82d6c64eafcd7a0` | Interactive Learn lifecycle + migration 033 |
| `8beb1a09f0dc5d44d3a936a6ce040d210b337e7b` | Fragment reconciliation gate |
| *consolidation commit* | This runbook + release pin |

**Tests:** 184 passed, 24 skipped (`test_i13*.py`).  
**Migration:** `033_p2_i13_interactive_learn.sql` exactly once; sole new migration for this release when 030–032 already applied.

---

## Execute

**Runbook (authoritative):** [CONSOLIDATED-I13-FINAL-DEPLOYMENT-AND-FOUNDER-TEST.md](CONSOLIDATED-I13-FINAL-DEPLOYMENT-AND-FOUNDER-TEST.md)

**Plan:** [acceptance-learning-bounded-plan.json](acceptance-learning-bounded-plan.json)  
**Plan SHA-256:** `edd2ddc39e960992f2479d92578d8b9a870fbdc566386ce52df908495b291ca4`

**Disk:** backup + proof on **E:** only. No worktree, media copy, or C: backup.

**Not authorized:** archive Outcomes C/D/E; I18 Admin & Settings features listed in runbook.

---

## After Phases 1–6

Phase 7 founder sign-off via [CONSOLIDATED-FINAL-I13-ACCEPTANCE-REVIEW.md](CONSOLIDATED-FINAL-I13-ACCEPTANCE-REVIEW.md). I13 remains **OPEN** until Tom signs.

---

## Supersedes

- [CONSOLIDATED-DEPLOYMENT-REQUEST-ACCEPTANCE-LEARNING.md](CONSOLIDATED-DEPLOYMENT-REQUEST-ACCEPTANCE-LEARNING.md) (partial Learn/Admin deploy — merged here)
- Separate fragment pilot deploy requests (merged into Phase 1–5 of final runbook)
