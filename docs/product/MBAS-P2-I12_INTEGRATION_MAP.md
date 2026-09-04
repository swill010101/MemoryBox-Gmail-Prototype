# MBAS-P2-I12 — Historian Collection Integration Map

**Status:** **ACCEPTED** 2026-09-04 (Tom: “i12 is accepted”) · Definition **LOCKED** 2026-09-03 · **BUILD AUTHORIZED S1–S5** 2026-09-03  
**PRD:** [MBPRD-P2-I12_HISTORIAN_COLLECTION_CAMPAIGNS.md](MBPRD-P2-I12_HISTORIAN_COLLECTION_CAMPAIGNS.md)  
**Domain:** [MBDC-P2-I12_DOMAIN_MODEL.md](MBDC-P2-I12_DOMAIN_MODEL.md)

---

## 1. Integration overview

```text
                    ┌─────────────────────┐
                    │  Owner UI (HC-*)    │
                    └──────────┬──────────┘
                               │
         ┌─────────────────────┼─────────────────────┐
         ▼                     ▼                     ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ People /        │  │ Historian       │  │ Email transport │
│ contacts        │  │ Capture domain  │  │ (dedicated MB)  │
│ (I10A.1)        │  │ (Postgres)      │  │                 │
└────────┬────────┘  └────────┬────────┘  └────────┬────────┘
         │                    │                     │
         │                    ├──────► Stories (I10A)
         │                    ├──────► Artifacts (I10B)
         │                    ├──────► Evidence / provenance
         │                    ├──────► Ask / narration (I11)
         │                    └──────► Archive Health (I2)
         │
         └──────────────────────────────────────────────►
```

---

## 2. People and contacts

| Integration | Direction | Contract |
|-------------|-----------|----------|
| **MB People** (`people` table) | Read + FK | Every campaign respondent `people_id` required before send |
| **Person profile contacts** (`profile.facts` email) | Read | Suggest routes; owner confirms one |
| **Person picker** (I10A.1 UI) | Reuse | HC-03 respondent selection |
| **Auto-create Person from email** | **Blocked** | Unmatched From: → quarantine; owner links manually |

**Change from I11 `guided_capture`:** `guided_capture_contacts` as parallel identity is **deprecated** in favor of Person-first model with confirmed route snapshot on `campaign_respondents`.

---

## 3. Stories and revisions

| Integration | When | Behavior |
|-------------|------|----------|
| **Create Story** | Promotion | New Story row; `narrator_person_id` = respondent; body from Review Draft |
| **Append to Story** | Promotion option | New Story revision; provenance link preserved |
| **Story editor** (I10A) | Post-promotion | Owner may further edit Story; capture chain immutable |
| **Ask retrieval** | After promotion | Story indexed with testimony provenance metadata |

**Provenance junction:** `historian_capture_promotions` → `stories.id` + `capture_item_id` + `review_draft_id`.

---

## 4. Artifacts

| Integration | When | Behavior |
|-------------|------|----------|
| **Create Artifact** | Optional promotion | When attachment or body describes object-worthy content |
| **Representation** | Optional | Email body or attachment becomes Artifact representation |
| **I10B prove** | Regression | Existing Artifacts unaffected |

V1 acceptance may be Story-only; Artifact path wired in S5 if authorized.

---

## 5. Evidence and provenance

| Integration | Behavior |
|-------------|----------|
| **Raw preservation** | `.eml` + attachments under MemoryBox archive layout (align with I5A Capture storage patterns) |
| **Hashes** | `content_hash`, attachment `sha256` on Capture Item |
| **Provenance JSON** | Campaign, question snapshot, delivery, respondent, owner verdict, assessment |
| **I7A trace** | Optional: log promotion and assessment events for observability |
| **Cross-source correlation (I10)** | Promoted testimony may link to related comms/media; no auto-merge |

**Separation:** Historian Capture mailbox (`memorybox@marvinbot.net`) is **not** the family Gmail ingest path (I6/I8). Do not conflate with optimized communications gallery ([2026-09-03 decision](../decisions/2026-09-03-comms-preparation-and-unified-gallery.md)).

---

## 6. Ask and narration (I11)

| Integration | Behavior |
|-------------|----------|
| **Retrieval** | `search_historian_capture_for_ask()` — promoted Stories + optionally retained items per policy |
| **Attribution string** | “{Person} wrote in response to historian question … (owner assessment: {code})” |
| **Uncertainty** | Verdict `rejected` excluded from affirmative narration; assessment informs framing only |
| **Narrative pack** | Add unit kind `historian_testimony` or extend `story` with capture provenance |
| **Guided capture hits** | Migrate `guided_capture` search to historian capture model |

**I11A inference:** Promoted testimony may appear in evidence packs; claim-specific trust rules still apply — testimony ≠ verified fact.

---

## 7. Email provider and transport

| Layer | Integration |
|-------|-------------|
| **Interface** | `HistorianEmailAdapter` (evolve `GuidedEmailAdapter`) |
| **Outbound** | SMTP/send via `memorybox@marvinbot.net` (Namecheap) |
| **Inbound** | Poll Gmail API for Capture account integration |
| **Harness** | `FakeHistorianEmailAdapter` for `prove-historian-capture` |
| **Config** | Env vars outside Git; no credentials in repo |
| **Correlation** | `[MB-HC-<token>]` in subject; delivery table authoritative |

**Not reused as production path:** Marvin PoC plus-address (`+MEM`, `+JRN`), Trash-after-verify, owner personal Gmail as send-from.

---

## 8. Archive Health and notifications

| Signal | Surface |
|--------|---------|
| Unmatched capture count | HC-06 inbox + optional Archive Health tile |
| Send failures | Campaign detail delivery log + optional Health |
| Poll errors | Log + Health degraded state |
| New items awaiting review | Shell badge on Review & Learn |

Minimal V1: inbox badges sufficient; Health hooks in S5.

---

## 9. Scheduler and ops

| Component | Integration |
|-----------|-------------|
| **Campaign tick** | Extend `tick_scheduler` pattern from `guided_capture` |
| **Poll loop** | Cron or MemoryBox service tick: `poll_and_ingest()` |
| **FlightSim** | Document in ops runbook (not in this planning commit) |
| **docker-compose** | No new public services required for V1 |

---

## 10. Existing code touchpoints (current repo)

| Module | Role |
|--------|------|
| `memorybox/guided_capture/__init__.py` | Campaign/delivery/response logic — **adapt** |
| `memorybox/guided_capture/email_adapter.py` | Transport interface — **adapt** for dedicated mailbox |
| `memorybox/migrations/007_guided_capture_i11.sql` | Schema predecessor — **new migration** |
| `memorybox/ask/retrieve.py` | `search_guided_capture` — **rename/extend** |
| `memorybox/ask/orchestrator.py` | Guided capture hits in narration — **extend** |
| `application/marvin_capture/*` (PoC branch) | Gmail client, reply_extract — **selective reuse** behind adapter |

---

## 11. Optimized communications ingestion (placement)

Per [2026-09-03 comms decision](../decisions/2026-09-03-comms-preparation-and-unified-gallery.md):

- **Family mbox / SMS optimized threads** → P2-I6 ingestion backfill + Gallery/Ask consumption — **not blocking I12**  
- **Historian Capture mailbox** → **P2-I12 only** — separate channel, separate poll/send credentials  
- Ask should eventually consume optimized threads for family email; historian testimony arrives via promotion/retrieval paths above  

**Open:** exact milestone for Ask to stop raw comms cleanup at query time (O8 in PRD) — does not block I12 build.

---

**PLANNING LOCKED 2026-09-03.**
