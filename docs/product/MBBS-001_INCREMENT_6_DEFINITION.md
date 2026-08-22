# MBBS-001 Increment 6 — Definition

**Status:** **ACCEPTED** (see [MBBS-001_INCREMENT_6_ACCEPTANCE.md](MBBS-001_INCREMENT_6_ACCEPTANCE.md))  
**Date:** 2026-08-10  
**Owner acceptance gate (locked):** On FlightSim, Tom can use the thin Person UI **without developer intervention** to select **one real Immich provider identity**, teach/confirm its MB Person identity, and then use Ask to retrieve photos for that MB Person **through the confirmed provider mapping**. Synthetic harnesses may prove reject, negatives, bulk confirm, and merge. — **PASSED**  
**Charter source:** [MBBS-001](MBBS-001_MEMORYBOX_BUILD_SPECIFICATION.md) § Increment 6  
**Governed by:** [MB_P1_ENGINEERING_RULES.md](../source/MB_P1_ENGINEERING_RULES.md) · [MB_LOCKED_DECISIONS_P1.md](../source/MB_LOCKED_DECISIONS_P1.md)  
**EVS catalog (authoritative):** [MBEVS-001_EVS_Catalog_v0.8.xlsx](../source/MBEVS-001_EVS_Catalog_v0.8.xlsx)  
**Depends on:** Increment 1 (Person / ProviderIdentity / Assertion schema) · Increment 2 (PhotoProvider; Immich IDs as `external_id` only) · Increment 4 Ask (accepted) · Increment 5 / 5A (Story/Journal must **stop** ad-hoc Person creation after I6 — see §6)  
**Prior:** [MBBS-001_INCREMENT_5A_ACCEPTANCE.md](MBBS-001_INCREMENT_5A_ACCEPTANCE.md) — **ACCEPTED**  
**Related ops (not I6):** [P1_REMOTE_BROWSER_MIC_HTTPS.md](../ops/P1_REMOTE_BROWSER_MIC_HTTPS.md) — remote-browser mic requires trusted HTTPS; deployment/ops workstream  
**Authorization:** *Build Increment 6 only* — **complete / accepted**.

---

## 0. Locked decisions (final)

| Topic | Decision |
|-------|----------|
| Product slice | **Central Person & Identity Service** + owner **teach / confirm / reject / merge (thin)** + basic **display-name correction** + Ask photo resolution via confirmed MB mapping |
| Flows | **EF-07 / EF-08 thin** only — not Review & Learn (Inc 7), not EVS-014 full (Inc 10) |
| MB Person durability | MemoryBox Person identity and **owner teaching** are durable knowledge |
| Provider external ID durability | Do **not** claim Immich `external_id` / cluster IDs necessarily survive Immich reprocessing. If Immich later emits a **new** cluster/external identity, owner (or later tooling) may **map it to the existing MB Person** while **preserving prior mapping provenance** |
| Mapping SoT | Confirmed MB Person → `provider_identities` is **authoritative** for photo identity resolution |
| Fallback trust | Immich **display-name** matching is **candidate/fallback evidence only**. It must **never** silently become a confirmed MB identity. If a confirmed MB Person exists but **lacks** an Immich mapping, provider-name matches must appear as **unconfirmed candidates**, not as normal confirmed Person results |
| Negatives | Rejection durably means **“provider identity X is not MB Person Y”**. Future automatic/candidate resolution **must consult** negatives so the rejected pairing does not silently reappear. Rejection must **not** prevent X from later mapping to a **different** Person |
| Merge | Owner-led, **non-destructive**. `merged_away` + `merged_into_id` appropriate. Do **not** rewrite historical assertions so the original referenced Person becomes unknowable. Preserve enough merge history for **future logical reversal**; Unmerge UX **not** required in I6 |
| Central resolution | I6 is the **common** Person/Identity service. Story/Journal/`ensure_person` **must not** continue independently creating duplicate Persons via raw name matching after I6. Callers **reuse** the shared resolver or **stop and report** an integration gap |
| Name correction | **Minimal** owner correction of an MB Person’s canonical/display name is **IN**. Full Person CRUD, aliases, family-tree, rich Person UX = **OUT** |
| Immich write-back | **OUT** — MB owns Person; Immich remains provider |
| Email/phone identity productization | **OUT** of I6 |
| Auto-merge / ranked loops without owner | **OUT** |
| HVRT/video Review, EVS-014 full, multi-user, polish | **OUT** |
| Remote-browser mic HTTPS | **OUT of I6** — recorded as separate P1 ops requirement (5A discovery) |
| Acceptance | Synthetic + real FlightSim; opaque IDs/counts/status only |

---

## 1. Problem / why now

Ask can find photos by Immich display-name string match, and Story/Journal create People via ad-hoc name lookup. That is not durable identity:

- Immich renames / face-cluster churn can break Ask and create silent false confidence.  
- Owner teaching (“that face is Peggy”) is not a first-class MB Person assertion.  
- Duplicate `people` rows accumulate without merge or shared resolution.  
- EVS-022 / EVS-023 (and later EVS-014) require MemoryBox-owned Person with mapped provider identities.

Increment 6 productizes a **central** Person & Identity service so owner teaching sticks, Ask uses confirmed mappings with honest fallbacks, and other modules stop minting duplicate Persons.

---

## 2. Objective

1. **Person & Identity Service** — teach/confirm/reject/merge; basic display-name correction; durable negatives; mapping provenance.  
2. **Central Person resolution** — shared API used by Ask, Story, Journal, and future callers.  
3. **Ask earn-in** — photo-by-person prefers confirmed mappings; candidates never silently promoted.  
4. **FlightSim prove** — owner teach one real Immich identity → Ask via mapping; harness covers reject/negatives/bulk/merge.

| Field | Content |
|-------|---------|
| **Modules** | Person & Identity Service; provider identity map; thin Person UX; Ask photo resolution; thin reindex/refresh; shared Person resolver |
| **Flows** | **EF-07**, **EF-08 thin** |
| **EVSs in** | **EVS-022**, **EVS-023**; improves **EVS-001 / 028-class** photo-by-person |

---

## 3. Success criteria (acceptance)

Final acceptance on **FlightSim** for I6-OWNER; harness for the rest.

| ID | Criterion | Proof |
|----|-----------|-------|
| **I6-A** | Create / confirm MB Person (owner authority) | Harness |
| **I6-B** | Map Immich provider identity `external_id` → MB Person via `provider_identities`; `people.id` ≠ Immich UUID | Harness |
| **I6-C** | Owner teach “that person is \<Name\>” (EVS-022 thin) | Harness |
| **I6-D** | Bulk confirm selected provider identities → one Person (EVS-023 thin) | Harness |
| **I6-E** | Negative “X is not Y” retained; consulted by candidate resolution; X may still map to Z≠Y | Harness |
| **I6-F** | Owner merge non-destructive: `merged_away` + `merged_into_id`; historical assertion subjects remain knowable; merge history supports future logical reversal | Harness |
| **I6-G** | Ask photo-by-person uses **confirmed** MB→provider mapping when present | Harness + FlightSim |
| **I6-H** | Immich display-name hits never silently become confirmed MB identity; if confirmed Person lacks Immich mapping, name matches shown as **unconfirmed candidates** | Harness |
| **I6-I** | Basic owner correction of Person display/canonical name | Harness |
| **I6-J** | Shared Person resolver: Story/Journal (and other callers) do not independently `ensure_person` by raw name after I6 — reuse service or report gap | Harness / integration check |
| **I6-K** | Remap: new Immich external identity can be mapped to existing MB Person without erasing prior mapping provenance | Harness |
| **I6-OWNER** | FlightSim thin Person UI: select one real Immich identity → teach/confirm → Ask retrieves photos via confirmed mapping — **no developer intervention** | Tom on FlightSim |
| **I6-L** | Provider failure visible (Immich down ≠ “no person” / empty success) | Harness / FlightSim status |
| **I6-M** | Generalized synthetic subjects (opaque in reports) | Harness |
| **I6-N** | I1–I5A proves remain runnable | health + prior prove commands |
| **I6-O** | Living specs | Decision log + acceptance report |

---

## 4. Scope

### In

- Central Person & Identity Service over `people` / `provider_identities` / `assertions` (+ minimal migration if gaps proven)  
- Owner teach / confirm / reject for Immich person identities (`provider_key='immich'`)  
- Thin bulk confirm (selected set → one Person) for EVS-023 — harness may prove; owner FlightSim gate does not require bulk  
- Owner-led merge with non-destructive provenance + merge history for future reversal  
- Durable negatives consulted by candidate/auto resolution  
- Remap new Immich external IDs onto existing MB Person while preserving prior mapping provenance  
- Minimal display/canonical name correction  
- Shared Person resolution API; migrate Story/Journal off independent `ensure_person` name minting (or hard-fail with gap report)  
- Ask photo resolution per §7  
- Thin `/people/ui` + minimal API  
- `prove-person` synthetic + `--flightsim` owner path  
- Quiet “Archive Updated” after successful teach (preferred)

### Out

| Out | Notes |
|-----|--------|
| Email/phone identity productization | Locked **OUT** of I6 |
| Immich write-back of identity as SoT | Locked **OUT** |
| HVRT / video Review & Learn | Increment 7 |
| EVS-014 full cross-provider identity | Increment 10 |
| Auto-merge / ranked candidate loops without owner | Forbidden |
| Full Person CRUD, aliases, family-tree, rich Person UX | Later |
| Guided Capture, SMS, multi-user, polish | Out |
| Remote-browser mic HTTPS termination | **Ops/deploy workstream** — not I6 ([ops note](../ops/P1_REMOTE_BROWSER_MIC_HTTPS.md)) |

---

## 5. Domain intent

I1 already has `people`, `provider_identities`, `assertions` (incl. rejected).

### 5.1 Teach / confirm / remap

- Confirm Person → `people.status='confirmed'`; owner-authority teaching recorded.  
- Map Immich identity → `provider_identities.person_id = people.id`.  
- **Never** set `people.id` from Immich UUID.  
- If Immich later presents a **new** `external_id` for the same human, allow mapping that new id to the **existing** MB Person; **retain** prior identity rows / provenance (do not pretend the old external id “was never mapped”).

### 5.2 Negatives (locked)

- Rejection = durable fact: **provider identity X is not MB Person Y**.  
- Candidate / automatic resolution **must read** this negative and must not re-propose X→Y as a silent confirmed bind.  
- X may later be confirmed as Person Z (Z ≠ Y).  
- Persistence may use rejected assertions and/or an explicit negative identity row — implementation choice under this semantic lock.

### 5.3 Merge (locked)

- Owner selects survivor + loser.  
- Loser → `status='merged_away'`, `merged_into_id=survivor`.  
- Non-destructive: do **not** rewrite historical assertions so the original subject Person becomes unknowable (keep loser row as historical referent; survivors get current mappings).  
- Preserve merge history sufficient for **future logical Unmerge** (Unmerge UX **not** in I6).  
- Current `provider_identities` for the loser are associated with the survivor for forward resolution, without erasing that they previously attached to the loser.  
- No silent similarity-based merge in I6.

### 5.4 Name correction (locked thin)

- Owner may correct `display_name` (canonical label for Ask/UI).  
- No aliases table, no rich profile editor in I6.

### 5.5 Reindex (thin)

- After teach/merge/reject/rename: refresh lookup used by Ask photo resolution.  
- Full Qdrant/comms rebuild not required for I6 acceptance.

---

## 6. Central Person resolution (locked)

After I6 ships:

1. **One** Person & Identity service is the SoT for resolve-or-create / teach / map / reject / merge / rename.  
2. Story, Journal, and any other module that today calls ad-hoc `ensure_person` by raw display-name **must** call the shared resolver (or equivalent service API).  
3. If a caller cannot be wired in the same increment, implementation must **stop and report** an integration gap — not leave a second Person minting path live.  
4. Goal: stop duplicate Persons from independent name matching.

---

## 7. Ask integration (earn-in, not Inc 10)

**Authoritative path (confirmed mapping present):**

1. Resolve ask person name → confirmed MB Person (via shared resolver).  
2. Load confirmed Immich `provider_identities` for that Person.  
3. PhotoProvider search by those `external_id`s.  
4. Citations/attribution show **MB Person** + mapping provenance.

**Fallback / candidate path (locked trust rules):**

- Immich display-name matching is **never** sufficient to create or silently confirm an MB identity.  
- If a **confirmed** MB Person exists for the asked name but has **no** Immich mapping: any Immich name-similar hits must be labeled **unconfirmed candidates** (not presented as normal confirmed Person photo results).  
- If **no** confirmed MB Person exists: Immich name matches may appear only as candidates / provider-labeled hits with clear non-confirmed provenance — still must not mint confirmed MB Person automatically.

Provider down → visible failure status (not empty success).

No video/HVRT required for I6.

---

## 8. UX (thin)

- `/people/ui`: list/search MB Persons; list Immich provider people; select one identity → Teach/Confirm; Reject; Merge; edit display name.  
- Owner FlightSim gate uses this UI only (no developer SQL/API babysitting).  
- No taxonomy chrome; no polish; no full Immich album browser required for acceptance (selected Immich people list is enough for EVS-023 harness).

---

## 9. EVS scope (MBEVS-001 v0.8)

### 9.1 In

| EVS ID | Role in I6 |
|--------|------------|
| **EVS-022** | “That person is Peggy.” — owner confirmation; durable; no silent overwrite |
| **EVS-023** | “These pictures are all Peggy.” — bulk confirm selected provider identities → one MB Person (harness) |
| **EVS-001 / 028-class** | Improved via confirmed mapping; candidates disclosed when mapping absent |

### 9.2 Out (later)

| Slice | Increment |
|-------|-----------|
| EVS-014, richer multi-provider | 10 |
| Video teach / Review | 7 |
| Guided Capture identity prompts | 11 |

---

## 10. Architecture notes

- PG authoritative for Person, mappings, negatives, merge history, owner assertions.  
- Immich remote PhotoProvider (D7); IDs only as `external_id`.  
- Durable = **MB Person + owner teaching + mapping provenance**, not a promise that Immich cluster IDs are immortal.  
- Earn-in from I2 `provider_identities` and I4 Ask photo path; replace trust model per §7.

---

## 11. Build plan (only after *Build Increment 6 only*)

1. Person & Identity Service (teach/confirm/reject/merge/rename/remap) + negatives semantics.  
2. Shared Person resolver; migrate Story/Journal off ad-hoc `ensure_person` (or gap-fail).  
3. Thin `/people/ui` + API.  
4. Ask photo resolution with confirmed vs candidate trust rules.  
5. `prove-person` harness (reject/negatives/bulk/merge) + FlightSim I6-OWNER.  
6. Confirm I1–I5A proves.  
7. Acceptance report; **stop**.

---

## 12. Authorization gate

**Status: ACCEPTED.**

Do **not** begin Increment 7 / Guided Capture / polish beyond locked I6 scope without explicit authorization.
