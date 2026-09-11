# Consolidated final I13 acceptance review

**I13 status:** **ACCEPTED** — closed 2026-09-11 by founder sign-off.  
**This is not a new increment.** No deploy, restore, requeue, evidence create/withdraw, criteria change, additional processing, I14 build, or cleanup execution is authorized by this close.

**Deployed SHA (FlightSim, frozen):** `b2dd4a2c4cfd613b0d7cd32d9a4426b25be3ebcb`  
**Admission:** `9e1cb49b-ec9d-40cb-ac34-7b3968d5af2a` (stopped, `interactive_learn_enabled`, bounded `acceptance_learning`)  
**Person:** Eugene Will `b67708d8-0262-404d-a230-2cc99900cea4`

**Founder sign:** Tom — “i13 visually verified…. i13 accepted.” (2026-09-11)  
**Reference:** FlightSim live visual pass + face/voice engineering proofs below  
**Dump path (FlightSim, not pasted in chat):** `C:\MemoryBox-backups\i13-interactive-learn-20260910-105354\voice-exemplar-interval-transcript.txt`

Do **not** reopen I13 without explicit founder direction. Do **not** merge to `main` without explicit founder direction.

---

## Engineering processing proofs (accepted 2026-09-11)

| Proof | Identifier | Result |
|---|---|---|
| Face owner_learn queue | `72050a51-91e1-49b9-874a-7726109cfce5` | **completed** on `vid-c57dbd21f993f6d1` (`20111105_1532.MP4`) |
| Voice owner_learn queue | `0886a090-2bae-4895-8ab6-38f73e1bb4a2` | **completed** (upsert from historical `excluded` / `no_voice_exemplars`) on `vid-da41273dbd9ac4bb` |
| Active Eugene voice exemplar | `26be56d0-659f-4a0f-bef5-c89a3a097d99` | `speechbrain-ecapa`, withdrawn false, meta `owner_review_learn` / `mb_native_i9`, interval **1673.48–1718.92 s** |
| Bulk drains | recognition 0, speech 0 | held |
| Archive | locked | held |
| Inspector check 7 | `queue_not_stranded` | **passed** — no scoped owner_learn queued/running; 2 terminal rows |
| Inspector check 8 | `owner_learn_follow_on_succeeded` | **passed** — completed face=1, voice=1, scoped_total=2 |
| Inspector exit | `INSPECTOR_EXIT=0` | `C:\MemoryBox-backups\i13-interactive-learn-20260910-105354\voice-proof-learn-recon.json` |

---

## 1. Voice-evidence quality — **founder passed**

Founder visually verified the learned interval and accepted I13. Speaker purity is therefore **founder-passed**, not independently re-scored from chat (interval dump file was produced on FlightSim; body was not pasted here).

Interval: **1673.48–1718.92 s** on `vid-da41273dbd9ac4bb`. Learn may have labeled overlapping turns Eugene/`owner_confirmed`; founder visual review is the purity authority.

---

## 2. Admin Learned Evidence

**Code (SHA `b2dd4a2`):** `scope=exemplars` lists all non-withdrawn `speech_voice_exemplars` without filtering `owner_review_learn`. Voice `method`/`is_owner_learn` is `owner_learn`. Face requires `method = 'owner_learn'`. UI: Person, source, interval, Withdraw.

**Founder:** visually verified Learned Evidence as part of I13 accept.

---

## 3. Inspectors on record

| Inspector | Result | Limits |
|---|---|---|
| Interactive Learn reconciliation | 2026-09-11: checks **6, 7, 8 passed**; **1–5 not tested**; `gate_passed: true`; `INSPECTOR_EXIT=0` | 1–5 are UI; founder visual checklist covers them |
| Face/voice corroboration | 2026-09-08 FlightSim `ok: true`, 8 assignments | Canonical eight / voice-pilot overlap |
| 22-video fragment gate | Allowlist: two approved source runs (1532 + 1530), `manifest_id` `p2-i13-flightsim-22`. Founder Gallery sample visually verified (no duplicate short-fragment presentations) | Allowlist not expanded at close |
| Archive/drain | `archive=True`, `rec=0`, `speech=0` | Held through close |

---

## 4. Founder visual checklist — **signed**

| # | Check | Result |
|---|---|---|
| V1 | Right-rail Learn available with admission stopped | **passed** (founder visual) |
| V2 | Admin Jobs: face `72050a51-…` and voice `0886a090-…` completed | **passed** (engineering + founder visual) |
| V3 | Admin Learned Evidence: active Eugene face + voice `26be56d0-…` | **passed** (founder visual) |
| V4 | FR-005 playback continues past evidence interval | **passed** (founder visual) |
| V5 | Gallery 22-video sample: no duplicate short-fragment cards | **passed** (founder visual) |

**Sign (founder):**

- [x] Visual checklist complete  
- [x] Voice interval quality accepted by founder visual verification  
- [x] **Accept** P2-I13 closed on completed scope  
- [ ] Reject — n/a  

**Reference:** Tom, FlightSim, SHA `b2dd4a2c4cfd613b0d7cd32d9a4426b25be3ebcb`  
**Date:** 2026-09-11

---

## 5. Explicitly not authorized by this acceptance

- Archive Outcomes C/D/E (register / unlock / start / drains)
- Restore, deploy, requeue, new Learn, withdraw, criteria edits
- I14 implementation
- Codex/Cursor temp-directory cleanup (inventory only)

---

## 6. Cleanup inventory (still not executed)

I13 is signed. Cleanup remains a **separate** I14-prep step. See [I13-CODEX-CURSOR-CLEANUP-INVENTORY.md](I13-CODEX-CURSOR-CLEANUP-INVENTORY.md). Do not delete backups or proof folders until Tom authorizes execution.
