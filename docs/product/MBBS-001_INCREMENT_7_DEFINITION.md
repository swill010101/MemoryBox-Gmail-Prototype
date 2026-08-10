# MBBS-001 Increment 7 — Definition (build authorized)

**Status:** **ACCEPTED** — see [MBBS-001_INCREMENT_7_ACCEPTANCE.md](MBBS-001_INCREMENT_7_ACCEPTANCE.md)  
**Date:** 2026-08-10  
**Owner acceptance gate (locked):** On FlightSim, Tom can open the thin **Review** client **without developer intervention**, open/play/scrub **at least one real family video**, Teach / Confirm a **face** candidate as an Immich-**named** person who was **not** first created in `/people/ui` — MemoryBox **lazily materializes/reuses** the canonical MB Person from the trusted Immich identity via the **shared I6 Person & Identity** service — and then use Ask to retrieve a **person-linked video segment**. Provenance must distinguish trusted-provider seed from owner-confirmed identity. When the Video Intelligence worker is down, Ask/monolith remains up with **visible degradation**. Synthetic harnesses prove provider/worker/review/Ask/bootstrap subchecks (including presence-span merging, identity survival, and no silent same-name merge). A **second real family person is not required** on the owner gate.  
**Charter source:** [MBBS-001](MBBS-001_MEMORYBOX_BUILD_SPECIFICATION.md) § Increment 7  
**Governed by:** [MB_P1_ENGINEERING_RULES.md](../source/MB_P1_ENGINEERING_RULES.md) · [MB_LOCKED_DECISIONS_P1.md](../source/MB_LOCKED_DECISIONS_P1.md)  
**EVS catalog (authoritative):** [MBEVS-001_EVS_Catalog_v0.8.xlsx](../source/MBEVS-001_EVS_Catalog_v0.8.xlsx)  
**Depends on:** Increment 2 (provider patterns) · Increment 4 Ask visual contract (`want_video` / `visual_scope`) · **Increment 6 Person & Identity (accepted)** · **D4** (HVRT sibling worker) · **D7** (media on media-server; config-driven hosts)  
**Prior:** [MBBS-001_INCREMENT_6_ACCEPTANCE.md](MBBS-001_INCREMENT_6_ACCEPTANCE.md) — **ACCEPTED**  
**Related ops (not I7):** [P1_REMOTE_BROWSER_MIC_HTTPS.md](../ops/P1_REMOTE_BROWSER_MIC_HTTPS.md) — remote-browser mic requires trusted HTTPS; deployment/ops workstream  
**Authorization:** *Build Increment 7 only* — authorized.

---

## 0. Locked decisions (final)

| Topic | Decision |
|-------|----------|
| Product slice | **VideoIntelligenceProvider** + **HVRT sibling worker** + thin **Review & Learn** UX + Ask **video modality earn-in** + **presence span merging** |
| Flows | **EF-15** (Review & Learn) + **EF-04 video** thin — not Library/Gallery (Inc 8), not Guided Capture (Inc 11) |
| Process boundary (**D4**) | HVRT runs as a **sibling background worker** behind a stable **Video Intelligence Provider** API. Monolith **must not** embed HVRT schemas, engines, or native tables as domain SoT |
| Worker host (P1 default) | **FlightSim** is the **default** P1 host for the HVRT / Video Intelligence worker. Location remains **configuration-driven and portable** — **do not** hard-code FlightSim (or any host) into product logic |
| Authoritative video source | **Preserved family-video filesystem/library on media-server**. **Plex and Immich are not** SoT for video originals. Worker reads the **configured media-server video path** across the LAN. **Original video files remain untouched** |
| Data authority layers | See §5.0 — original media vs derived/provider evidence vs MB owner teaching |
| Teach durability | Review Teach / Confirm / Reject writes **MB assertions** and uses **I6** teach/map/reject rules. Worker reprocessing **must not** silently overwrite owner-confirmed identity knowledge |
| Owner identity path | **Face teaching** is the **required** I7 owner identity path. Speaker/voice identity teaching is **not** a blocker unless existing HVRT capability is already mature and can earn in **without** scope expansion |
| Ask video | When planner `want_video` (or broad visual includes video), Ask queries VideoIntelligenceProvider. Hits cite video/segment provenance. Still PhotoProvider path unchanged |
| Worker down | Monolith **degraded, not dead**. Visible provider status (Immich-down ≠ “no photos” rule applies to video). Video asks disclose unavailability |
| Presence span merging | **IN** — worker/provider must merge nearby same-candidate detections into continuous presence spans via **configurable gap tolerance** (sensible P1 default; no Settings UI in I7; designed for later Settings exposure). See §5.5 |
| Person identity | Review teach **reuses I6** resolver/teach/map. Do **not** mint a second Person path inside HVRT. **Trusted Immich named identities may lazily seed a provisional MB Person** when needed (not bulk import; not owner-confirmed until owner confirms) |
| Identity authority | **Owner-confirmed** > **trusted-provider** (e.g. named Immich) > **AI/inferred candidate**. Do not flatten. Owner correction overrides provider identity; rejected pairings retain I6 negatives |
| Trusted-provider bootstrap | When Ask / Review teach needs a named Immich person and no clean MB mapping exists: resolve or **lazy-materialize** one canonical MB Person + `provider_identities`; never use Immich UUID as `people.id`; no silent same-name merge |
| EVS-003 / 007 | **Person-linked video segment retrieve/play** is the I7 acceptance bar. **Laughing / speech-emotion detection is not required** for I7 unless existing HVRT reuse already provides it without research or material scope expansion — otherwise **explicitly deferred** |
| Owner gate media | **At least one real family video** through FlightSim Review UI. Synthetic media for deterministic harness only |
| Second person | **Not required** on FlightSim owner gate. Generalized second-person behavior proven in **synthetic harness** |
| Prove command | Primary: **`prove-video`** with named provider / worker / review / Ask **subchecks** (not multiple operator commands) |
| EVS-014 | **OUT** — full cross-provider face enroll loop is **Increment 10** (D5) |
| Immich write-back | **OUT** — MB owns Person; Immich remains photo provider |
| Library / Gallery / Timeline | **OUT** → Increment 8 |
| Multi-span timeline polish/chrome | **OUT** of thin Review |
| MemoryBox Settings UI | **OUT** of I7 (presence-gap threshold is config-only in I7) |
| Auto-learn without owner | **OUT** — no silent promotion of HVRT face/voice guesses to confirmed MB Person |
| Multi-user, polish, Guided Capture, SMS | **OUT** |
| Remote-browser mic HTTPS | **OUT of I7** — separate P1 ops/deploy requirement ([ops note](../ops/P1_REMOTE_BROWSER_MIC_HTTPS.md)) |
| Acceptance | Synthetic harness + real FlightSim owner path; opaque IDs/counts/status only |

---

## 1. Problem / why now

Ask already plans for video (`want_video`, broad visual) but I4–I6 only execute **stills**. Owner face teaching exists for Immich (I6) but **not** for video Review. HVRT POC exists as engines to mine, but D4 forbids embedding it inside the monolith.

Without I7:

- “Show me videos of Dan” cannot be honest product behavior.  
- Review & Learn (EF-15) and EVS-003/007 stay blocked.  
- Risk of bolting HVRT into the monolith, treating detections as Person SoT, or flooding UX with one-second spans.

I7 productizes the **provider + sibling worker + thin Review** path so face teaching lands in MB domain, presence spans are usable, and Ask can use video when the worker is healthy.

---

## 2. Objective

1. **VideoIntelligenceProvider** interface (health, search/list presence spans/segments, get hit, face teach hooks as needed).  
2. **HVRT sibling worker** (default host FlightSim; config-portable) reading **media-server** family-video library; **presence span merging**; originals untouched.  
3. **Thin Review UX** — open/play/scrub; see face candidate; Teach / Confirm / Reject via I6.  
4. **Ask earn-in** — video modality returns person-linked segment hits with provenance; worker-down visible.  
5. Prove via **`prove-video`** (synthetic subchecks + FlightSim owner path).

| Field | Content |
|-------|---------|
| **Modules** | VideoIntelligenceProvider (+ fake/unavailable adapters); HVRT worker process; thin Review UX; Ask video retrieval; presence-span merge config |
| **Flows** | **EF-15**; **EF-04 video** thin |
| **EVSs in** | **EVS-003**, **EVS-007** thin person-linked segment (see §8) |

---

## 3. Success criteria (acceptance)

Final acceptance on **FlightSim** for I7-OWNER; harness for the rest via **`prove-video`**.

| ID | Criterion | Proof |
|----|-----------|-------|
| **I7-A** | VideoIntelligenceProvider contract + Fake adapter | `prove-video` provider subcheck |
| **I7-B** | HVRT sibling worker (separate process); monolith talks only via provider API; worker location config-driven (no FlightSim hard-code) | `prove-video` worker subcheck |
| **I7-C** | Worker down → monolith healthy; Ask video path shows **visible degradation** | `prove-video` |
| **I7-D** | Face Review teach writes **MB assertions** / I6 Person mapping — durable across derived reprocess | `prove-video` review + identity-survival subcheck |
| **I7-E** | Review Reject respects I6 “X is not Y” for video provider identities | `prove-video` |
| **I7-F** | Ask `want_video` / video_only retrieves **person-linked** video segment hits when healthy | `prove-video` Ask subcheck + FlightSim |
| **I7-G** | Video citations/attribution distinct from still PhotoProvider; provenance honest | `prove-video` |
| **I7-H** | No HVRT/Immich native schemas as MB domain tables; originals not mutated | Health / inventory / policy check |
| **I7-I** | Person teach from Review uses **shared I6 Person service** (no second mint path) | `prove-video` integration subcheck |
| **I7-N** | **Presence span merging:** adjacent/nearby same-candidate detections merge within configured gap tolerance; a gap **exceeding** tolerance yields a **separate** span; changing/reprocessing derived spans **does not** overwrite owner-confirmed identity knowledge | `prove-video` span-merge + identity-survival subchecks |
| **I7-BOOTSTRAP** | **Trusted-provider lazy Person bootstrap:** named Immich identity exists, no MB Person initially → resolve/seed provisional MB Person (provider provenance, not owner-confirmed) → Immich + HVRT map to same `people.id` (never provider UUID as PK) → Ask retrieves video; owner correction + negatives; no silent same-name merge | `prove-video` bootstrap subchecks + FlightSim |
| **I7-OWNER** | FlightSim thin Review: Immich-**named** family person **not** pre-created in `/people/ui` → face Teach in real video → MB lazily materializes/reuses Person from trusted Immich → Ask retrieves video — **no developer intervention / SQL / API patching**. Second real person **not** required | Tom on FlightSim |
| **I7-J** | Generalized synthetic subjects + **second-person** behavior in harness (opaque) | `prove-video` |
| **I7-K** | I1–I6 proves remain runnable | health + prior prove commands |
| **I7-L** | Living specs | Decision log + acceptance report |
| **I7-M** | Laughing / speech-emotion: **earn-in only** if already in HVRT without research/scope expansion; else **deferred** (document in acceptance) | Note / optional subcheck |

---

## 4. Scope

### In

- VideoIntelligenceProvider interface + config-driven client in monolith  
- Unavailable / Fake adapters (parallel to photo)  
- HVRT sibling worker: health, segment/presence-span search, face-candidate surface behind worker API  
- Worker reads **configured media-server family-video path** over LAN; **does not** treat Plex/Immich as video-original SoT; **does not** modify originals  
- **Presence span merging** with configurable gap tolerance + sensible P1 default (later Settings-ready; **no** Settings UI in I7)  
- Thin `/review/ui`: open/play/scrub video or segment; see **face** candidate; Teach / Confirm / Reject via I6  
- Persist owner teaching as MB assertions + `provider_identities` (video provider_key, e.g. `hvrt`)  
- Ask retrieval for video hits when `want_video` / broad visual includes video  
- **`prove-video`** primary command with named provider/worker/review/Ask/span-merge subchecks + `--flightsim` owner path  
- Quiet “Archive Updated” (or equivalent) after successful teach

### Out

| Out | Notes |
|-----|--------|
| Bulk Immich Person import | OUT — lazy materialization only |
| Full EVS-014 cross-provider face enroll loop | **Increment 10** |
| Library / Gallery / Timeline | **Increment 8** |
| Immich write-back of identity | Locked OUT |
| Plex / Immich as authoritative video originals | Locked OUT for I7 video SoT |
| Embedding HVRT inside monolith process / domain schema | Violates D4 |
| Auto-confirm HVRT guesses as MB Person | Forbidden |
| Moving/copying family video library onto FlightSim as SoT | Violates D7; worker reads media-server path |
| Mutating original video files | Forbidden |
| Multi-span timeline polish / chrome | OUT of thin Review |
| MemoryBox Settings UI (incl. presence-gap editor) | OUT of I7 — config only |
| Speaker/voice identity teach as acceptance blocker | OUT unless mature HVRT earn-in |
| Laughing / speech-emotion as hard acceptance bar | Deferred unless free earn-in |
| Guided Capture, SMS, multi-user, polish | Out |
| Full speech-search product / editor suite | Out |
| Remote-browser mic HTTPS / TLS product work | **Ops/deploy** — not I7 |
| Replacing Immich still path | Unchanged |

---

## 5. Domain / provider intent

### 5.0 Authoritative vs derived (locked)

| Layer | What | Authority |
|-------|------|-----------|
| **Original video file** | Preserved source media on media-server family-video library | **Preserved source** — untouched by I7 |
| **HVRT detections, spans, transcripts, recognition candidates, etc.** | Derived / provider evidence | **Rebuildable**; may change on reprocess; **not** Person SoT |
| **Trusted-provider identity** (e.g. named Immich person) | Evidence that may **lazy-seed** a provisional MB Person + `provider_identities` | Usable for resolution/retrieval; **must not** be presented as owner-confirmed |
| **Owner-confirmed Person identity / teaching** | MB `people` / `provider_identities` / owner `assertions` in PostgreSQL | **Strongest** — **must survive** worker reprocessing; overrides provider identity |

AI/inferred candidates remain unconfirmed and must not silently become confirmed Person knowledge.

### 5.0.1 Trusted-provider bootstrap (locked)

Do **not** bulk-import Immich people. When Ask / Review teach / association needs a named Immich person:

1. Resolve whether a matching canonical MB Person already exists (clean provider mapping preferred).  
2. If none and a **unique exact-name** Immich identity exists → lazily create **provisional** MB Person (`status=unresolved`, `identity_authority=trusted_provider`) + Immich `provider_identities`.  
3. Never use Immich UUID as `people.id`.  
4. Display-name string match alone must **not** silently merge Persons; ambiguous cases require owner resolution.  
5. Owner correction wins; I6 negatives prevent rejected pairings from silently reappearing.  
6. All of the above via the **shared I6 Person service** — no second bootstrap path inside HVRT/I7.

### 5.1 VideoIntelligenceProvider

Minimum surface (names illustrative):

- `health()` → ok / detail  
- `search_segments` / presence-span query → hits with opaque `external_id`, optional person refs, **merged** time span, media ref  
- `get_segment(external_id)`  
- Face teach/learn operations via MB Review service that may call worker then writes **PG** — **MB domain remains SoT for confirmed Person**

Provider IDs are **external_id only** (same rule as Immich). Never use HVRT UUIDs as `people.id`.

### 5.2 Worker

- Separate process; start/stop independent of `memorybox serve`  
- **P1 default host: FlightSim**; endpoint/media path **config-driven** (portable; no FlightSim hard-code in logic)  
- Reads **configured media-server family-video path** across LAN  
- Owns HVRT engines/pipeline/annotations **internally** (derived store)  
- Exposes versioned HTTP (or equivalent) API consumed only through VideoIntelligenceProvider  
- Implements **presence span merging** (§5.5)

### 5.3 Review teach (face-required)

1. Owner opens/plays/scrubs a video or segment; views a **face** candidate.  
2. Teach / Confirm “this is \<Name\>” → I6 `teach_provider_person` / map with video `provider_key` (e.g. `hvrt`), **after** trusted-provider resolve/seed when Immich already has that named identity. Owner does **not** need to pre-create the Person in `/people/ui`.  
3. Reject → I6 negative semantics.  
4. Assertions record authority + provenance JSON (segment/span id, time range, provider); Immich seed remains provider-originated even when video mapping is owner-taught.  
5. Speaker/voice teach may earn in later only if already mature — **not** I7-OWNER blocker.

### 5.4 Ask

- Still path: I6/I7 trust rules — owner-confirmed vs trusted-provider-seeded vs candidate attribution.  
- Video path: resolve Ask Person (confirmed or trusted-provider, with lazy Immich seed when needed) → video `provider_identities` → search **merged** presence spans/segments; else candidates only with disclosure.  
- Broad visual: may return stills + video; each citation labeled by modality + trust.  
- Do **not** present provider-seeded identity as if the owner personally confirmed it.

### 5.5 Presence span merging (locked)

Raw frame / short-interval detections **must not** force the product to expose large numbers of one-second Person spans.

- Worker/provider supports a **configurable presence-gap tolerance**.  
- Nearby detections of the **same** candidate/person within the tolerance **merge** into one continuous presence span.  
- Gaps **larger than** the threshold start a **new** span.  
- Sensible **P1 default** in config; **no** Settings UI in I7; design for later Settings exposure.  
- Rebuilding/changing derived spans **must not** overwrite owner-confirmed identity knowledge (§5.0).

---

## 6. UX (thin)

Locked thin Review surface:

- Open / play / scrub video or segment  
- See candidate (face for owner path)  
- Teach / Confirm / Reject through shared I6 Person service  

No Gallery chrome, no multi-span timeline polish, no taxonomy navigation, no Settings UI.

Owner FlightSim gate uses this UI without SQL/API babysitting.

---

## 7. Architecture notes

```
memorybox serve (monolith on FlightSim)
    │  VideoIntelligenceProvider (config URL)
    ▼
HVRT sibling worker (P1 default: FlightSim; portable config)
    │  read-only LAN path (config)
    ▼
media-server: preserved family-video library (originals untouched)

PostgreSQL (FlightSim): people / provider_identities / assertions
    = owner-confirmed identity SoT (survives worker reprocess)
```

- POC HVRT under `hvrt/` (if present) = **mine for adapters**, not package layout (D2).  
- Contract versioning pinned and proven in `prove-video`.  
- Domain tests use Fake provider — no Immich/HVRT schemas required.

---

## 8. EVS scope (MBEVS-001 v0.8)

### 8.1 In (thin)

| EVS ID | Role in I7 |
|--------|------------|
| **EVS-003** | Person-linked video segment **retrieve/play** for a taught person (synthetic and/or owner-taught). Laughing/speech-emotion **not required** unless free HVRT earn-in |
| **EVS-007** | Same person-linked retrieve/play pattern; **second real family person not required** on owner gate — generalized second-person behavior in **synthetic harness** |

### 8.2 Out (later)

| Slice | Increment / track |
|-------|-------------------|
| EVS-014 full cross-provider | 10 |
| EVS-015 Library/timeline | 8 |
| Guided Capture | 11 |
| Remote mic HTTPS | Ops/deploy |

---

## 9. Build plan (only after *Build Increment 7 only*)

1. Provider interface + Fake/Unavailable adapters.  
2. Sibling worker skeleton + health + media-server path config + presence span merging.  
3. Review service + thin `/review/ui` wired to I6 (face Teach / Confirm / Reject).  
4. Ask video retrieval + citations + degrade path.  
5. **`prove-video`** with named subchecks (provider, worker, review, Ask, span-merge, identity-survival) + `--flightsim` owner path.  
6. Confirm I1–I6 proves.  
7. Acceptance report; **stop**.

---

## 10. Risks

| Risk | Mitigation |
|------|------------|
| Process boundary / API drift | Versioned contract; Fake + live worker in `prove-video` |
| LAN media path / permissions | Config-driven media-server path; ops checklist; originals read-only |
| Span-merge defaults wrong | Config threshold + harness merge/split cases; later Settings |
| Scope creep into Gallery / EVS-014 / voice teach | Hard OUT table; face-required owner path |
| Dual Person minting in HVRT | Mandatory I6 reuse; gap-fail if not wired |
| Treating derived detections as identity SoT | §5.0 layers + I7-N identity-survival prove |

---

## 11. Authorization gate

**Status: ACCEPTED** — see [MBBS-001_INCREMENT_7_ACCEPTANCE.md](MBBS-001_INCREMENT_7_ACCEPTANCE.md).

Do **not** begin Increment 8 / Guided Capture / polish beyond locked I7 scope without explicit authorization.

---

## 12. Stop line

Do **not** begin Increment 8 / 10 / Guided Capture without new authorization. Do **not** fold remote HTTPS into I7.

---

## 13. Residual open items (non-blocking for definition lock)

None required for I7 acceptance. Laughing/speech-emotion remains deferred.

---

*End of Increment 7 definition — ACCEPTED.*
