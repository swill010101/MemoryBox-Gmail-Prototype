# MBBS-001 Increment 7 — Definition (for review only)

**Status:** **DRAFT — REVIEW ONLY** (not locked for build)  
**Date:** 2026-08-10  
**Owner acceptance gate (proposed):** On FlightSim, Tom can open the thin **Review** client **without developer intervention**, teach/confirm **one** person on a real video segment via the **I6 Person & Identity** service, and then use Ask to retrieve a **video** hit for that MB Person when video modality is available. When the Video Intelligence worker is down, Ask/monolith remains up with **visible degradation** (not empty success, not process death). Synthetic harnesses prove provider contract, worker-down degrade, and assertion provenance.  
**Charter source:** [MBBS-001](MBBS-001_MEMORYBOX_BUILD_SPECIFICATION.md) § Increment 7  
**Governed by:** [MB_P1_ENGINEERING_RULES.md](../source/MB_P1_ENGINEERING_RULES.md) · [MB_LOCKED_DECISIONS_P1.md](../source/MB_LOCKED_DECISIONS_P1.md)  
**EVS catalog (authoritative):** [MBEVS-001_EVS_Catalog_v0.8.xlsx](../source/MBEVS-001_EVS_Catalog_v0.8.xlsx)  
**Depends on:** Increment 2 (provider patterns) · Increment 4 Ask visual contract (`want_video` / `visual_scope`) · **Increment 6 Person & Identity (accepted)** · **D4** (HVRT sibling worker) · **D7** (media on media-server)  
**Prior:** [MBBS-001_INCREMENT_6_ACCEPTANCE.md](MBBS-001_INCREMENT_6_ACCEPTANCE.md) — **ACCEPTED**  
**Authorization:** **NOT AUTHORIZED** — review and lock decisions only. Do **not** build until Tom says *Build Increment 7 only*.

---

## 0. Proposed locked decisions (needs Tom sign-off)

| Topic | Proposed decision |
|-------|-------------------|
| Product slice | **VideoIntelligenceProvider** + **HVRT sibling worker** + thin **Review & Learn** UX + Ask **video modality earn-in** |
| Flows | **EF-15** (Review & Learn) + **EF-04 video** thin — not Library/Gallery (Inc 8), not Guided Capture (Inc 11) |
| Process boundary (**D4**) | HVRT runs as a **sibling background worker** behind a stable **Video Intelligence Provider** API. Monolith **must not** embed HVRT schemas, engines, or native tables as domain SoT |
| Domain SoT | Owner teaching and person identity remain in **PostgreSQL** via I6 Person service + `assertions` / `provider_identities` / `media_refs` as needed. Worker annotations are **provider evidence**, not substitute for owner-confirmed MB Person |
| Teach durability | Review teach/confirm writes **MB assertions** and uses **I6** teach/map/reject rules. HVRT/AI reprocessing **must not** silently overwrite owner teaching |
| Ask video | When planner `want_video` (or broad visual includes video), Ask queries VideoIntelligenceProvider. Hits cite video/segment provenance. Still PhotoProvider path unchanged |
| Worker down | Monolith **degraded, not dead**. Visible provider status (same rule as Immich-down ≠ “no photos”). Video asks disclose unavailability |
| Media topology (**D7**) | Video libraries stay on **media-server**. Worker accesses media via **config-driven** paths/endpoints — no hard-coded hosts/drives in app logic |
| Person identity | Review teach **reuses I6** resolver/teach/map. Do **not** mint a second Person path inside HVRT |
| EVS-003 / 007 | **Thin:** person-linked video segment play/retrieve for a taught MB Person. Full emotional/laughter speech proof is **IN only if** existing HVRT reuse already supports it without expanding I7 into research — otherwise disclose as stretch / later refinement (open question §13) |
| EVS-014 | **OUT** of I7 — full “teach face in video → same Person in Immich photo Ask” cross-provider loop is **Increment 10** (D5 sequencing) |
| Immich write-back | **OUT** — MB owns Person; Immich remains photo provider |
| Library / Gallery / Timeline | **OUT** → Increment 8 |
| Auto-learn without owner | **OUT** — no silent promotion of HVRT face/voice guesses to confirmed MB Person |
| Multi-user, polish, Guided Capture, SMS | **OUT** |
| Acceptance | Synthetic + real FlightSim; opaque IDs/counts/status only |

---

## 1. Problem / why now

Ask already plans for video (`want_video`, broad visual) but I4–I6 only execute **stills**. Owner teaching for faces exists for Immich (I6) but **not** for video Review. HVRT POC exists as engines to mine, but D4 forbids embedding it inside the monolith.

Without I7:

- “Show me videos of Dan” cannot be honest product behavior.  
- Review & Learn (EF-15) and EVS-003/007 stay blocked.  
- Risk of bolting HVRT into the monolith or treating worker annotations as Person SoT.

I7 productizes the **provider + sibling worker + thin Review** path so video teaching lands in MB domain and Ask can use video when the worker is healthy.

---

## 2. Objective

1. **VideoIntelligenceProvider** interface (health, search/list segments, get hit, teach/learn hooks as needed).  
2. **HVRT sibling worker** process implementing that API; contract versioned; replaceable.  
3. **Thin Review UX** — open a video/segment, see candidates, **owner teach/confirm/reject** via I6.  
4. **Ask earn-in** — video modality returns provider hits with provenance; worker-down visible.  
5. Prove on **FlightSim** (synthetic + real owner Review teach).

| Field | Content |
|-------|---------|
| **Modules** | VideoIntelligenceProvider (+ fake/unavailable adapters); HVRT worker process; thin Review UX; Ask video retrieval path |
| **Flows** | **EF-15**; **EF-04 video** thin |
| **EVSs in** | **EVS-003**, **EVS-007** thin (see §9) |

---

## 3. Success criteria (acceptance)

Final acceptance on **FlightSim** for I7-OWNER; harness for the rest.

| ID | Criterion | Proof |
|----|-----------|-------|
| **I7-A** | VideoIntelligenceProvider contract + Fake adapter for harness | Harness |
| **I7-B** | HVRT runs as sibling worker (separate process); monolith talks only via provider API | Harness / process check |
| **I7-C** | Worker down → monolith healthy; Ask video path shows **visible degradation** (not empty success, not crash) | Harness |
| **I7-D** | Review teach writes **MB assertions** / I6 Person mapping — durable; AI rerun does not silently overwrite | Harness |
| **I7-E** | Review reject / negative respects I6 “X is not Y” semantics for video provider identities | Harness |
| **I7-F** | Ask `want_video` / video_only retrieves video hits via provider when healthy | Harness + FlightSim |
| **I7-G** | Video citations/attribution distinct from still PhotoProvider; provenance honest | Harness |
| **I7-H** | No HVRT/Immich native schemas as MB domain tables | Health / inventory |
| **I7-I** | Person teach from Review uses **shared I6 Person service** (no second mint path) | Harness / integration check |
| **I7-OWNER** | FlightSim thin Review: one real video teach → Ask video hit for that MB Person — **no developer intervention** | Tom on FlightSim |
| **I7-J** | Generalized synthetic subjects (opaque in reports) | Harness |
| **I7-K** | I1–I6 proves remain runnable | health + prior prove commands |
| **I7-L** | Living specs | Decision log + acceptance report |
| **I7-M** (optional stretch) | Laughing / speech-emotion span for EVS-003/007 if HVRT reuse already provides it | Harness or deferred note |

---

## 4. Scope

### In

- VideoIntelligenceProvider interface + config-driven client in monolith  
- Unavailable / Fake adapters (parallel to photo)  
- HVRT sibling worker packaging: health, segment/search, teach surface behind worker API  
- Thin `/review/ui` (or equivalent): pick/open one video or segment; show face/voice/span candidates; Teach / Confirm / Reject via I6  
- Persist owner teaching as MB assertions + provider_identities (video provider_key, e.g. `hvrt`)  
- Ask retrieval path for video hits when `want_video` / broad visual includes video  
- `prove-video` / `prove-review` harness + `--flightsim` owner path  
- Quiet “Archive Updated” (or equivalent) after successful teach

### Out

| Out | Notes |
|-----|--------|
| Full EVS-014 cross-provider face enroll loop | **Increment 10** |
| Library / Gallery / Timeline | **Increment 8** |
| Immich write-back of identity | Locked OUT |
| Embedding HVRT inside monolith process / domain schema | Violates D4 |
| Auto-confirm HVRT guesses as MB Person | Forbidden |
| Moving video libraries onto FlightSim | Violates D7 |
| Guided Capture, SMS, multi-user, polish | Out |
| Full speech-search product / editor suite | Out of thin Review |
| Replacing Immich still path | Unchanged |

---

## 5. Domain / provider intent

### 5.1 VideoIntelligenceProvider (proposed)

Minimum surface (names illustrative):

- `health()` → ok / detail  
- `search_segments(query)` → hits with opaque `external_id`, optional person refs, time span, media ref  
- `get_segment(external_id)`  
- Teach/learn operations either on provider **or** via MB Review service that calls worker then writes PG — **MB domain remains SoT for confirmed Person**

Provider IDs are **external_id only** (same rule as Immich). Never use HVRT UUIDs as `people.id`.

### 5.2 Worker (proposed)

- Separate process; start/stop independent of `memorybox serve`  
- Owns HVRT engines/pipeline/annotations **internally**  
- Exposes versioned HTTP (or equivalent) API consumed only through VideoIntelligenceProvider  
- Config: base URL, credentials, media root/endpoints — env only  

### 5.3 Review teach (proposed)

1. Owner views candidate (face/voice/span) on a video.  
2. Teach “this is \<Name\>” → I6 `teach_provider_person` / map with `provider_key` for video (e.g. `hvrt`).  
3. Reject → I6 negative semantics.  
4. Assertions record owner authority + provenance JSON (segment id, time range, provider).

### 5.4 Ask (proposed)

- Still path: unchanged I6 trust rules.  
- Video path: resolve confirmed MB Person → list video provider_identities → search segments by those ids; else candidates only with disclosure.  
- Broad visual: may return stills + video; each citation labeled by modality + trust.

---

## 6. UX (thin)

- `/review/ui` (name flexible): functional Review only — no Gallery chrome, no polish.  
- Owner FlightSim gate uses this UI (or minimal equivalent) without SQL/API babysitting.  
- Link from Ask/People as needed; taxonomy navigation not required.

---

## 7. Architecture notes

```
memorybox serve (monolith)
    │  VideoIntelligenceProvider
    ▼
HVRT sibling worker  ←→  media-server video libraries (config)
    │
    ▼
PostgreSQL: people / provider_identities / assertions (I6 SoT)
```

- POC HVRT under `hvrt/` (if present) = **mine for adapters**, not package layout (D2).  
- Contract versioning is an acceptance risk — pin and prove compatibility in harness.  
- Do not require Immich or HVRT schemas in domain tests (Fake provider).

---

## 8. EVS scope (MBEVS-001 v0.8)

### 8.1 In (thin)

| EVS ID | Role in I7 |
|--------|------------|
| **EVS-003** | Thin: retrieve/play a video segment linked to a taught person (Dad-class subject via opaque synthetic or owner-taught). Full “laughing” speech-emotion = stretch if already in HVRT reuse |
| **EVS-007** | Thin: same pattern for a second person (Peggy-class) on FlightSim owner path as practical — or harness if second real video unavailable |

### 8.2 Out (later)

| Slice | Increment |
|-------|-----------|
| EVS-014 full cross-provider | 10 |
| EVS-015 Library/timeline | 8 |
| Guided Capture | 11 |

---

## 9. Build plan (only after *Build Increment 7 only*)

1. Provider interface + Fake/Unavailable adapters.  
2. Sibling worker skeleton + health + segment search (wrap HVRT engines as needed).  
3. Review service + thin `/review/ui` wired to I6 Person.  
4. Ask video retrieval + citations + degrade path.  
5. `prove-video` / `prove-review` + FlightSim I7-OWNER.  
6. Confirm I1–I6 proves.  
7. Acceptance report; **stop**.

---

## 10. Risks

| Risk | Mitigation |
|------|------------|
| Process boundary / API drift | Versioned contract; harness against Fake + live worker |
| Media access from FlightSim worker | D7 config; clarify worker host in §13 |
| EVS-003/007 laughter bar too high | Thin person-linked segment as acceptance; emotion as stretch |
| Scope creep into Gallery / EVS-014 | Hard OUT table |
| Dual Person minting in HVRT | Mandatory I6 reuse; gap-fail if not wired |

---

## 11. Authorization gate

**Status: REVIEW ONLY — NOT BUILD AUTHORIZED.**

Do **not** implement worker, Review UX, or Ask video retrieval until Tom explicitly authorizes *Build Increment 7 only*.

---

## 12. Stop line

After any future I7 acceptance: do **not** begin Increment 8 / 10 / Guided Capture without new authorization.

---

## 13. Open questions for Tom (required before lock / build)

1. **Worker host:** Does the HVRT sibling worker run on **FlightSim**, **media-server**, or either (config)? (Affects media path and ops.)  
2. **Video source of truth for P1:** Which library/path is authoritative for Review (filesystem under media-server, Plex, Immich video, other)?  
3. **Owner gate media:** Must I7-OWNER use a **real family video** on FlightSim, or is a **checked-in synthetic clip + one real teach** acceptable?  
4. **EVS-003/007 laughter:** Is **person-linked segment retrieve/play** sufficient for I7 acceptance, with laughing/speech-emotion deferred if not already cheap in HVRT reuse?  
5. **Review UX depth:** Is scrub + one-candidate teach enough, or must I7 include multi-span timeline chrome?  
6. **Prove command name:** Prefer `prove-video`, `prove-review`, or both?  
7. **Second person (EVS-007):** Required on FlightSim owner gate, or harness-only if only one convenient real video?

---

*End of Increment 7 definition draft — awaiting Tom review / lock decisions. No build.*
