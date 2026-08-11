# MBBS-001 Increment 10 — Cross-provider Person in Ask (EVS-014) — Definition (final review — decisions locked; not build-authorized)

**Status:** **BUILD COMPLETE** — harness green; awaiting FlightSim owner acceptance  
**Date:** 2026-08-11  
**Roadmap placement:** **After Increment 9A Person Profile (ACCEPTED)** · **Before Increment 11 (Guided Capture)**  
**Owner acceptance gate (locked):** On FlightSim, with the **HVRT/video worker path running**, Tom picks **one real family Person** who already has a **trusted Immich named identity** and appears in **at least one real HVRT-processed family video**. Through the **normal owner UI** (Review / People teach-confirm — no SQL), he teaches/confirms the **HVRT/video identity** onto the **same canonical MB `people.id`** already (or then) linked to Immich — **without recreating that human as a separate Person per provider**. He then retrieves **Immich photos and HVRT video hits** for that Person via **Ask** and via the **existing Library Person filter**, both resolving through **Person X**, with **provider provenance visible**. Photo-only interim acceptance is **invalid** for EVS-014.  
**Charter source:** [MBBS-001](MBBS-001_MEMORYBOX_BUILD_SPECIFICATION.md) § Increment 10  
**Governed by:** [MB_P1_ENGINEERING_RULES.md](../source/MB_P1_ENGINEERING_RULES.md) · [MB_LOCKED_DECISIONS_P1.md](../source/MB_LOCKED_DECISIONS_P1.md)  
**EVS catalog (authoritative):** [MBEVS-001_EVS_Catalog_v0.8.xlsx](../source/MBEVS-001_EVS_Catalog_v0.8.xlsx) (v0.8)  
**Depends on:** **Increment 6 Person & Identity (ACCEPTED)** · Ask (I4) · Library (I8 ACCEPTED) · Review / video (I7) · **Increment 9A (ACCEPTED)** when asks use “my …”  
**Prior:** [MBBS-001_INCREMENT_9A_ACCEPTANCE.md](MBBS-001_INCREMENT_9A_ACCEPTANCE.md) — **ACCEPTED**  
**Acceptance:** [MBBS-001_INCREMENT_10_ACCEPTANCE.md](MBBS-001_INCREMENT_10_ACCEPTANCE.md)  
**Next (after 10):** Increment 11 — Guided Capture (EF-11)  
**Authorization:** **Build authorized and shipped 2026-08-11.** Awaiting FlightSim **I10-OWNER**. Do not start Increment 11 until Tom authorizes.

**Parked (not I10; kinship stays P2):** Full kinship inference → [TASK-P1P2-002](MBBS_P1_P2_BACKLOG.md) (**P2**). Universal Immich lazy-teach → [TASK-P1P2-001](MBBS_P1_P2_BACKLOG.md).

---

## 0. Locked decisions (final review)

| Topic | Decision |
|-------|----------|
| Product slice | **Cross-provider Person consistency** — one canonical MB `people.id` for the same human across **Immich** and **HVRT/video**, driving Ask + existing Library Person filter |
| **Cross-provider teach** | Owner must **not** manually recreate the same human independently in each media provider. When one provider already has a **trusted** identity and another provider identity is **taught/confirmed** for that human, both resolve to the **same** MB `people.id` via the shared **I6/I7 Person & Identity** service. **Required path:** Immich trusted named identity present → teach/confirm HVRT/video identity → reuse/resolve one MB Person → Ask returns Immich photos **and** HVRT video hits. **Forbidden:** join solely because **display-name strings match**. Ambiguous linkage → **require/disclose owner confirmation**; never silent merge |
| **Reprocess durability** | Precisely: (1) **canonical MB Person knowledge** survives; (2) **owner-confirmed identity assertions** survive; (3) **historical provider mapping provenance** survives; (4) **derived indexes are rebuildable**; (5) provider **external IDs / clusters are NOT assumed permanently stable**. If Immich/HVRT reprocessing yields a **new** provider external identity, MB may need **reconciliation** to the existing Person — must **not** lose prior owner knowledge or **silently mint a duplicate** canonical Person |
| Ask + Library | **Same** canonical Person / provider mappings for Ask Person retrieval and **existing** Library Person filter. **No new Library UX.** Example: Ask “show me Peggy” → Person X; Library filter Peggy → Person X; Immich + HVRT results via X; provenance visible |
| Identity SoT | **I6 remains SoT** — I10 does not mint a second Person PK; Immich/HVRT UUIDs never become `people.id` |
| Provenance / degrade | Hits disclose **which provider** contributed; provider down ≠ silent empty success |
| Owner relativity | “my father / me” continues **I9A owner → Relationship → person_id → retrieve**; I10 does not reopen string-hack resolve |
| **HVRT worker** | FlightSim **I10-OWNER requires video worker/provider path running**. **Photo-only interim acceptance is not valid** for EVS-014 |
| **EVS-009** | Include **only** catalog-required shared-identity portion (exact wording §2); do not expand into kinship or new multi-person product |
| Kinship / cousins / uncle composition | **OUT** — [TASK-P1P2-002](MBBS_P1_P2_BACKLOG.md), **P2** (not resequenced into I10) |
| Other exclusions | Universal lazy-teach (TASK-P1P2-001) · Immich write-back · auto family tree · tree visualization · multi-user · Guided Capture · Export · Settings/polish · reopening I9A as I10 deliverable |
| Prove | **`prove-cross-provider-person`** (exact name at build) + `--flightsim` |
| Hosts | FlightSim = app + PG; Immich + HVRT worker + media-server per D7 config |

---

## 1. Why 10 exists (gap)

| Layer | What I6–I9A delivered | Still missing |
|-------|----------------------|---------------|
| **Identity** | Canonical Person; per-provider mappings; teach/confirm/reject; trust | End-to-end proof that **second-provider teach** attaches to the **same** MB Person as an existing trusted Immich identity — without per-provider Person recreation or display-name auto-merge |
| **Ask / Library** | Person filter; relational “my …” → Person id | **Same Person X** drives Immich **and** HVRT retrieve in Ask **and** Library |
| **Review / teach** | Face/person teach paths | Durable owner knowledge across provider reprocess + reconciliation when external IDs change |
| **Kinship** | SoT + direct inverses + thin spouse-of-parent | **P2** (TASK-P1P2-002) |

EVS-014 was sequenced **late in P1** (D5): hardest consistency problem; foundations (Person + photo + video) must already exist.

---

## 2. REQUIRED EVS AUDIT (authoritative catalog v0.8)

**Source audited:** `docs/source/MBEVS-001_EVS_Catalog_v0.8.xlsx` · sheet **EVS Catalog** · header row: `EVS | Taxonomy | Scenario / User Ask | Evidence Types | Phase | Primary Vehicle | Notes`.

### 2.1 Exact catalog wording (verbatim)

| EVS | Taxonomy | Scenario / User Ask | Evidence Types | Phase | Primary Vehicle | Notes |
|-----|----------|---------------------|----------------|-------|-----------------|-------|
| **EVS-014** | Corrections & Learning | Teach a face while watching video → same person in Ask/Immich | Face enroll, person graph | P1 | MBD-001 Review Learn | Unified person identity |
| **EVS-009** | Photos | Show pictures of Peggy with Mom | Photos, multi-person faces | P1–P2 | Ask + Immich/HVRT faces | Shared person identity across sources |

### 2.2 What I10 includes from each EVS

| EVS | I10 status | Bound to |
|-----|------------|----------|
| **EVS-014** | **IN (primary)** | Teach/confirm while watching video (HVRT path) → **same** canonical Person resolves in **Ask** and for **Immich** — unified person identity; no per-provider duplicate Person |
| **EVS-009** | **IN (shared-identity portion only)** | Catalog **Notes:** “Shared person identity across sources” + **Primary Vehicle:** “Ask + Immich/HVRT faces”. I10 proves Person identity is shared across Immich/HVRT sources for Ask retrieve. **Does not** expand I10 into kinship, “Mom” relationship inference, or a new multi-person composition product beyond what shared Person resolve already enables for a multi-face photo ask |
| Kinship / cousin / uncle | **OUT** | TASK-P1P2-002 (P2) |
| Universal lazy-teach | **OUT** | TASK-P1P2-001 |
| Guided Capture / Export | **OUT** | I11 / I12 |
| I9A profile/kinship reopen | **OUT** | Done / deferred separately |

---

## 3. Problem / why now

Without I10, the family still experiences:

1. Immich already “knows” Peggy (trusted named identity).  
2. Video teach creates a **second** mental/model Person, or Ask finds photos but not video (or the reverse).  
3. Display-name coincidence silently joins the wrong people — or forces the owner to recreate the human in every provider.  
4. After Immich/HVRT reprocess, external cluster IDs change and prior owner teaching appears lost or duplicated.

I10 closes the **unified Person** loop for P1 media modalities.

---

## 4. Objective

1. **Cross-provider teach** onto one MB `people.id` (I6/I7) — Immich trusted + HVRT teach/confirm; no per-provider Person recreation; no display-name-only join.  
2. **Ask** returns Immich photos **and** HVRT video hits for that Person.  
3. **Library** existing Person filter uses the **same** Person X / mappings (no new Library UX).  
4. **Reprocess durability** as locked in §0 (Person knowledge, owner assertions, mapping provenance survive; indexes rebuildable; external IDs not assumed stable; reconcile don’t duplicate).  
5. **Honest degrade** when Immich or HVRT worker is down.  
6. FlightSim owner gate with **video worker required**.  
7. **`prove-cross-provider-person`** (+ `--flightsim`).

| Field | Content |
|-------|---------|
| **Modules** | I6/I7 Person & Identity earn-in; cross-provider teach/confirm; Ask + Library Person resolve; reindex/rebuild as needed; provider_status |
| **Flows** | EF-01, EF-07 (EF-02 uses Person context) |
| **EVSs in** | **EVS-014** full P1 intent; **EVS-009** shared-identity-across-sources portion only |

---

## 5. Success criteria (acceptance)

| ID | Criterion | Proof |
|----|-----------|-------|
| **I10-A** | Immich trusted identity + HVRT/video teach/confirm → **one** MB `people.id`; owner did not recreate the human separately per provider | Harness + FlightSim |
| **I10-B** | Ask for that Person returns **Immich photo hits and HVRT video hits** | Harness + FlightSim |
| **I10-C** | Ambiguous cross-provider linkage → owner confirmation / disclosure; **no** display-name-only silent merge | Harness |
| **I10-D** | Ask Person retrieval and **existing Library Person filter** both resolve through the **same** Person X / provider mappings; Immich + HVRT via X; provenance visible; **no new Library UX** | Harness + FlightSim |
| **I10-E** | Reprocess durability: MB Person knowledge, owner-confirmed assertions, and historical mapping provenance **survive**; derived indexes **rebuildable**; new provider external IDs require **reconciliation** to existing Person — **no** silent duplicate Person; external IDs/clusters **not** treated as permanently stable | Harness (+ ops note) |
| **I10-F** | Provider unavailable → visible fail/degrade, not silent empty success | Harness |
| **I10-G** | I6 rules: Immich/HVRT UUID ≠ `people.id`; trust/authority stack unchanged | Harness |
| **I10-H** | I9A “my …” path still resolves to person_id then retrieve (smoke) | Harness |
| **I10-I** | I1–I9A proves remain runnable | Prior proves |
| **I10-OWNER** | FlightSim: one real family Person in **Immich** + **≥1 real HVRT-processed family video**; teach/confirm via normal owner UI; Ask + Library retrieve photo **and** video; **HVRT worker running**; no SQL/dev; no per-provider Person recreation | Tom |
| **I10-J** | Living specs / decision log updated | Docs |
| **I10-K** | Exclusions in §6 **not** claimed | Note |

---

## 6. Scope

### In

- Cross-provider teach/confirm onto one canonical MB Person (I6/I7)  
- Ask retrieve: Immich + HVRT for that Person  
- Library Person filter consistency (existing UX only)  
- Reprocess durability + rebuildable derived indexes + reconciliation path when provider external IDs change  
- Ambiguity disclosure / owner confirmation (no display-name-only merge)  
- `prove-cross-provider-person` + FlightSim owner gate with **HVRT worker required**  
- Docs: acceptance after authorize  

### Out

| Out | Notes |
|-----|--------|
| Full kinship inference / cousin / uncle composition | **TASK-P1P2-002 — P2** |
| Universal Immich lazy-teach all surfaces | **TASK-P1P2-001** |
| Immich write-back | Forbidden |
| Auto family tree from photos | Forbidden |
| Tree visualization / genealogy chrome | Forbidden |
| Multi-user relativity | Single-owner P1 |
| Guided Capture | I11 |
| Export | I12 |
| Settings / polish | Out |
| Reopening I9A fact/relationship schema as the I10 deliverable | Out |
| Photo-only interim “acceptance” of EVS-014 | **Invalid** |
| New Library product / UX | Out — consistency only |

---

## 7. Architecture sketch (non-binding until build)

```
Immich trusted named identity ──┐
                                ├──► I6/I7 Person & Identity
HVRT/video identity teach/confirm ──┘     (one people.id; no name-only join)
                                         │
                    owner-confirmed assertions + mapping provenance (durable)
                                         │
         person_id ──► Immich photo search
                   ──► HVRT video search (worker required on FS acceptance)
                                         │
Ask retrieve ◄───────────────────────────┤  same mappings
Library Person filter ◄──────────────────┘  (existing UX)
                                         │
         rebuild ◄── derived indexes (not SoT; external IDs may change → reconcile)
```

I9A Relationship service is upstream only for relational language; I10 consumes `person_id`.

---

## 8. Build plan (only after *Build Increment 10 only*)

1. Audit FlightSim gap: Immich-mapped Person vs HVRT identity teach → same `people.id` → Ask/Library.  
2. Close teach/confirm + resolve path; ambiguity UI/disclosure; no display-name-only merge.  
3. Reprocess/reconciliation + rebuild job for any derived indexes.  
4. Ask + Library consistency checks; provider degrade.  
5. `prove-cross-provider-person` + `--flightsim` (worker required).  
6. Confirm I1–I9A proves.  
7. Acceptance; **stop** (do not start I11 or TASK-P1P2-002 under this authorization).

---

## 9. Risks

| Risk | Mitigation |
|------|------------|
| Silent same-name merge | Forbidden; owner confirm when ambiguous |
| Duplicate MB Person after reprocess | Reconciliation to existing Person; durability rules §0 |
| Treating provider cluster IDs as SoT | External IDs not assumed stable; indexes rebuildable |
| Photo-only “done” | HVRT worker mandatory for I10-OWNER |
| Scope into kinship / lazy-teach | Explicit OUT + P2 backlog |
| Library UX creep | Consistency only; no new Library surface |

---

## 10. Residual notes (non-blocking)

1. Exact FlightSim Person name / video asset for I10-OWNER — Tom chooses at acceptance time (must be real family Immich + real HVRT-processed video).  
2. Exact prove command name / table shapes — at build, smallest clean model.  
3. Acceptance markdown written only after *Build Increment 10 only*.

No remaining product open questions that block **final review sign-off** of this definition. Kinship sequencing is locked: **P2 via TASK-P1P2-002**.

---

## 11. Authorization gate

**Status: BUILD COMPLETE — awaiting FlightSim owner acceptance.**

Harness: `python -m memorybox prove-cross-provider-person` (green).  
Do **not** begin Increment 11 / TASK-P1P2-001 / TASK-P1P2-002 under this authorization.

---

## 12. Stop line

After I10 acceptance: **Increment 11** (Guided Capture) only with new authorization.  
Kinship inference remains **P2** ([TASK-P1P2-002](MBBS_P1_P2_BACKLOG.md)).

---

## Appendix A — I9A residual (not I10)

`son_of` → reciprocal `parent_of` (not `father_of`) is an I9A / kinship-inference limit. **Out of I10.** See TASK-P1P2-002 (P2).

---

*End of Increment 10 definition — BUILD COMPLETE; FlightSim owner gate pending.*
