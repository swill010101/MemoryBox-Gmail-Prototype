# MBBS-001 Increment 6 — Definition (review only — not authorized to build)

**Status:** **LOCKED FOR REVIEW ONLY — NOT AUTHORIZED TO BUILD**  
**Date:** 2026-08-09  
**Proposed owner acceptance gate:** Tom can teach MemoryBox that a provider face/person is a named Person, confirm or reject a candidate mapping, and (when needed) merge two MB Persons — then Ask photo retrieval for that Person uses the MB identity mapping — **without developer intervention** on FlightSim.  
**Charter source:** [MBBS-001](MBBS-001_MEMORYBOX_BUILD_SPECIFICATION.md) § Increment 6  
**Governed by:** [MB_P1_ENGINEERING_RULES.md](../source/MB_P1_ENGINEERING_RULES.md) · [MB_LOCKED_DECISIONS_P1.md](../source/MB_LOCKED_DECISIONS_P1.md)  
**EVS catalog (authoritative):** [MBEVS-001_EVS_Catalog_v0.8.xlsx](../source/MBEVS-001_EVS_Catalog_v0.8.xlsx)  
**Depends on:** Increment 1 (Person / ProviderIdentity / Assertion schema) · Increment 2 (PhotoProvider; Immich IDs as `external_id` only) · Increment 4 Ask (accepted; photo-by-name path exists but is **not** yet MB-Person-authoritative)  
**Prior:** [MBBS-001_INCREMENT_5A_ACCEPTANCE.md](MBBS-001_INCREMENT_5A_ACCEPTANCE.md) — **ACCEPTED**  
**Authorization gate:** Do **not** implement until Tom explicitly authorizes *Build Increment 6 only*.

---

## 0. Proposed locked decisions (for Tom to confirm)

| Topic | Proposed decision |
|-------|-------------------|
| Product slice | **Person & Identity Service** + owner **teach / confirm / reject / merge (thin)** + Ask photo resolution via MB Person → `provider_identities` |
| Flows | **EF-07 / EF-08 thin** only — not full Review & Learn (Inc 7), not EVS-014 cross-provider video (Inc 10) |
| MB Person PK | Always MemoryBox `people.id` UUID — **never** Immich/HVRT UUID as Person PK (I2 lock stands) |
| Provider mapping | `provider_identities` is the SoT for provider face/person ↔ MB Person |
| Teach authority | Owner teach/confirm = `authority='owner'` durable knowledge; survives Immich reprocess |
| Negatives | Rejected mappings / “not this person” retained (`assertions` rejected and/or identity rows tombstoned — see §5); must not silently reappear as auto-confirm |
| Merge | **Owner-led merge** before any ranked auto-candidate loops; merge preserves provenance; loser `status='merged_away'` + `merged_into_id` |
| Ask earn-in | Photo Ask for a named person **prefers** MB Person → Immich `external_id` mapping; Immich display-name string match remains fallback only when no mapping exists |
| Reindex | Thin: invalidate/refresh derived lookup used by Ask photo path; **not** full library rebuild productization |
| UX | Thin functional Person/Identity client (parallel to Story/Journal shells) — **no** visual polish |
| Out | HVRT/video teach (Inc 7), EVS-014 full (Inc 10), Guided Capture, SMS, multi-user, polish, auto-merge without owner |

---

## 1. Problem / why now

Ask can find photos by **provider display-name string match**, and Story/Journal already attach People by ad-hoc `ensure_person` name lookup. That is not durable identity:

- Immich renames / face cluster churn can break Ask.  
- Owner teaching (“that face is Peggy”) is not a first-class MB Person assertion.  
- Duplicate `people` rows accumulate without a merge path.  
- EVS-022 / EVS-023 and later EVS-014 require **MemoryBox-owned Person** with mapped provider identities.

Increment 6 productizes Person & Identity **thinly** so owner teaching sticks and Ask photo retrieval can use MB mappings — without pulling Review/HVRT or full cross-provider Person (Inc 10).

---

## 2. Objective

1. **Person & Identity Service** — create/confirm Person; map/unmap Immich (and future HVRT) identities; reject/negative; owner-led merge.  
2. **Durable owner teach** — EF-07/EF-08 thin; “Archive Updated” feedback allowed (quiet).  
3. **Ask earn-in** — named-person photo asks resolve through MB Person mappings when present.  
4. **FlightSim prove** — synthetic + real owner teach against Immich people.

| Field | Content |
|-------|---------|
| **Modules** | Person & Identity Service; provider identity map APIs; thin Person UX; Ask photo resolution via mapping; reindex/refresh trigger thin |
| **Flows** | **EF-07**, **EF-08 thin** |
| **EVSs in** | **EVS-022**, **EVS-023**; improves **EVS-001 / 028-class** photo-by-person |

---

## 3. Success criteria (acceptance)

Final acceptance on **FlightSim**.

| ID | Criterion | Proof |
|----|-----------|-------|
| **I6-A** | Create / confirm MB Person (owner authority) | Harness |
| **I6-B** | Map Immich person/face `external_id` → MB Person via `provider_identities` | Harness; PK ≠ Immich UUID |
| **I6-C** | Owner teach “that person is \<Name\>” (EVS-022 thin) | Harness + FlightSim opaque ids |
| **I6-D** | Bulk confirm selected provider identities → one Person (EVS-023 thin) | Harness |
| **I6-E** | Reject / negative retained; not auto-reconfirmed | Harness |
| **I6-F** | Owner-led merge: loser `merged_away`; mappings + provenance preserved | Harness |
| **I6-G** | Ask photo-by-person uses MB mapping when present | Harness + FlightSim |
| **I6-H** | No Immich UUID as `people.id` | Prove invariant (I2 continues) |
| **I6-OWNER** | FlightSim owner path (no developer intervention) | Tom teaches one real Immich person → confirms mapping → Ask retrieves photos for that Person name |
| **I6-I** | Provider failure visible (Immich down ≠ “no person”) | Harness / FlightSim status |
| **I6-J** | Generalized synthetic subjects (opaque in reports) | Harness |
| **I6-K** | I1–I5A proves remain runnable | health + prior prove commands |
| **I6-L** | Living specs | Decision log + acceptance report |

---

## 4. Scope

### In

- Person & Identity Service over existing `people` / `provider_identities` / `assertions` (extend only if gaps proven)  
- Owner teach / confirm / reject for Immich person identities (`provider_key='immich'`)  
- Thin bulk confirm (selected set → one Person) for EVS-023  
- Owner-led merge (two MB Persons)  
- Ask photo resolution: Person name → MB Person → `provider_identities.external_id` → PhotoProvider  
- Thin `/people/ui` (or equivalent) + minimal API  
- `prove-person` (name TBD) synthetic + `--flightsim` owner path  
- Quiet “Archive Updated” after successful teach (optional but preferred)

### Out

| Out | Notes |
|-----|--------|
| HVRT / video Review & Learn | Increment 7 |
| EVS-014 full (teach in video → Immich+video Ask) | Increment 10 |
| Auto-merge / ranked candidate loops without owner | Forbidden in I6 |
| Writing identity back into Immich as SoT | MB owns Person; Immich remains provider |
| Guided Capture, SMS, multi-user, polish | Out |
| Full relationship graph / eras / family tree UX | Out |
| Email/phone identity productization beyond schema allowlist | Optional thin later; not required for I6 acceptance unless Tom expands |

---

## 5. Domain intent (schema — mostly exists)

I1 already has:

- `people` (`status`: unresolved \| confirmed \| merged_away; `merged_into_id`)  
- `provider_identities` UNIQUE `(provider_key, identity_kind, external_id)`  
- `assertions` with `authority` / `status` including **rejected**

### 5.1 Teach / confirm

- Confirm Person → `people.status='confirmed'`, owner-authority assertion recorded.  
- Map Immich identity → `provider_identities.person_id = people.id` (`identity_kind` e.g. `external_person` or `face` as used by provider).  
- **Never** set `people.id` from Immich UUID.

### 5.2 Negatives

- Owner “not this person” → retain as rejected assertion and/or clear `person_id` with durable negative marker so re-ingest cannot silently re-bind the same external_id as confirmed without owner action.  
- Exact persistence shape (assertion-only vs identity tombstone) — **open question** if both are needed; default proposal: **rejected assertion + do not auto-attach**.

### 5.3 Merge

- Owner selects survivor + loser.  
- Loser → `merged_away` + `merged_into_id=survivor`.  
- Move/repoint `provider_identities` and relevant relationships/assertions to survivor **without deleting provenance history**.  
- No silent merge from similarity scores in I6.

### 5.4 Reindex (thin)

- After teach/merge/reject: refresh in-process / derived lookup used by Ask photo resolution.  
- Full Qdrant/comms rebuild **not** required for I6 acceptance.

---

## 6. Ask integration (earn-in, not Inc 10)

Today (`search_photos`): Immich `list_people(query=name)` string match → `person_external_ids`.

**I6 change:**

1. Resolve ask person name → MB `people` (confirmed preferred).  
2. Load `provider_identities` for `provider_key='immich'`.  
3. Search PhotoProvider with those `external_id`s.  
4. If no MB mapping: existing Immich name fallback (disclose weaker provenance if useful).  
5. Citations/attribution should show **MB Person** when mapping was used.

Do **not** require video hits or HVRT for I6.

---

## 7. UX (thin)

- `/people/ui` (name TBD): list/search MB Persons; list Immich people (via provider); Teach / Confirm / Reject / Merge actions.  
- First-class intents optional: “Who is this?” deferred to Review (Inc 7); I6 may use explicit teach from listed Immich person → name.  
- No taxonomy chrome; no polish.

---

## 8. EVS scope (MBEVS-001 v0.8)

### 8.1 In scope for I6

| EVS ID | Role in I6 |
|--------|------------|
| **EVS-022** | “That person is Peggy.” — owner confirmation → high-authority identity; no silent overwrite of conflicts |
| **EVS-023** | “These pictures are all Peggy.” — bulk confirm selected provider identities / face cluster members → one MB Person |
| **EVS-001 / 028-class** | Improved: photo-by-person Ask uses MB mapping when taught |

### 8.2 Out (later)

| EVS / slice | Increment |
|-------------|-----------|
| EVS-014, richer EVS-009 | 10 |
| Video teach / Review loop | 7 |
| Guided Capture identity prompts | 11 |

---

## 9. Architecture notes

- PG authoritative for Person + mappings + owner assertions.  
- Immich remains remote PhotoProvider (D7); IDs only as `external_id`.  
- Human teaching durable across provider reprocessing (engineering rules).  
- Provider failure visible — never “empty people list” as success when Immich is down.  
- Earn-in from I2 `provider_identities` prove pattern and I4 Ask photo path.

---

## 10. Build plan (only after *Build Increment 6 only*)

1. Person & Identity Service (teach/confirm/reject/merge) over existing tables + any minimal migration.  
2. API + thin `/people/ui`.  
3. Ask photo resolution via MB Person mapping.  
4. `prove-person` harness + FlightSim owner teach path (EVS-022/023 opaque).  
5. Confirm I1–I5A proves.  
6. Acceptance report; **stop**.

---

## 11. Open questions for Tom

1. **Owner gate wording** — confirm or rewrite the proposed I6-OWNER sentence above.  
2. **UX entry** — is `/people/ui` enough, or must teach also be reachable from Ask (“Archive Updated” after teach)?  
3. **Negatives persistence** — assertion-only OK, or require explicit identity blocklist row?  
4. **Bulk EVS-023** — confirm “selected Immich people / face ids in UI” is enough (not full Immich album browser).  
5. **Email/phone identities** — in or out of I6 acceptance? Proposal: **out** unless you expand.  
6. **Immich write-back** — confirm **out** (MB mapping only).  
7. **Merge conflicts** — if two confirmed Persons both mapped to different Immich ids, survivor keeps both mappings unless owner rejects — OK?

---

## 12. Authorization gate

**Status: NOT AUTHORIZED TO BUILD.**

Do **not** write I6 product code, migrations, Ask photo rewiring, or Person UX until Tom explicitly says **Build Increment 6 only**.

Unauthorized increments must not start. Guided Capture / Inc 7+ remain out.
