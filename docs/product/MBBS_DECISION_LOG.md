# MBBS Decision / Deviation Log

**Status:** Living · **Owner:** Tom  
**Governed by:** [MB_P1_ENGINEERING_RULES.md](../source/MB_P1_ENGINEERING_RULES.md)

Record one section per increment. Do not wait until end of P1.

---

## Increment 5 — Story service + first-class Ask modality

**Date:** 2026-08-09  
**Authorization:** Build Increment 5 only (locked definition)  
**Acceptance:** [MBBS-001_INCREMENT_5_ACCEPTANCE.md](MBBS-001_INCREMENT_5_ACCEPTANCE.md) — **ACCEPTED** (FlightSim `prove-story --flightsim` + owner Story UX)  
**Next:** [MBBS-001_INCREMENT_6_DEFINITION.md](MBBS-001_INCREMENT_6_DEFINITION.md) — **REVIEW ONLY**; do not begin I6 / Guided Capture / Inc 7 without authorization.

### Build-lock decisions

| Decision | Rationale |
|----------|-----------|
| Story is first-class Ask modality (direct PG query) | No silo; no required story_passage materialization for I5 |
| Ask blend = all applicable modalities + provenance labels | Matches I4 multimodal presentation |
| STT / Journal out | Capture later; Journal = 5A |
| I1 relationships for associations | No ad-hoc Story columns; domain gap none for I5 minimum |
| Owner Story = provenance-bearing recollection | May save/retrieve without independent corroboration; Ask must attribute |

---

## Increment 5A — Journal + Capture/STT + Ask Journal

**Date:** 2026-08-09  
**Authorization:** Build Increment 5A only  
**Definition:** [MBBS-001_INCREMENT_5A_DEFINITION.md](MBBS-001_INCREMENT_5A_DEFINITION.md)  
**Acceptance:** [MBBS-001_INCREMENT_5A_ACCEPTANCE.md](MBBS-001_INCREMENT_5A_ACCEPTANCE.md) — **ACCEPTED** (`prove-journal --flightsim` + owner typed/voice UX)  
**Owner gate:** Typed + spoken Journal via `/journal/ui` without developer intervention; retrieve both via Ask — **PASSED**  
**Next:** [MBBS-001_INCREMENT_6_DEFINITION.md](MBBS-001_INCREMENT_6_DEFINITION.md) — **FINAL REVIEW ONLY**; do not begin I6 without authorization.  
**Ops note (5A discovery, not I6):** [P1_REMOTE_BROWSER_MIC_HTTPS.md](../ops/P1_REMOTE_BROWSER_MIC_HTTPS.md) — remote-browser mic requires trusted HTTPS.

### Build-lock decisions

| Decision | Rationale |
|----------|-----------|
| Journal ≠ Story | MBDM; separate tables/services/provenance |
| `author_person_id` SoT only | No authored_by dual-write |
| Immutable `journal_versions` | Parallel to Story versions |
| Capture ≠ described temporal | `captured_at` + described dates + precision vocab |
| Capture/STT reusable; Whisper behind provider | Journal must not import Whisper |
| Ask = direct PG Journal query | No required journal_passage Evidence |
| EVS-136 without fake Place links | Text/context/real relationships only |
| Remote mic HTTPS | Browser secure-context; ops/deploy — not product I6 |

---

## Increment 6 — Person & Identity + teach

**Date:** 2026-08-10  
**Authorization:** **ACCEPTED**  
**Definition:** [MBBS-001_INCREMENT_6_DEFINITION.md](MBBS-001_INCREMENT_6_DEFINITION.md)  
**Acceptance:** [MBBS-001_INCREMENT_6_ACCEPTANCE.md](MBBS-001_INCREMENT_6_ACCEPTANCE.md) — **ACCEPTED**  
**Owner gate:** Thin Person UI on FlightSim — teach one real Immich identity → Ask photos via confirmed mapping — **PASSED** (`4d1e8857-40f1-4d7a-b3db-20aae5e4f0fe`)

### Locked decisions (as built)

| Decision | Rationale |
|----------|-----------|
| MB Person + owner teaching durable; Immich external_id not promised immortal | Remap new cluster ids; keep prior mapping provenance |
| Confirmed mapping authoritative; Immich name match = candidate only | Never silent confirm; unmapped confirmed Person → candidates disclosed |
| Negatives = X is not Y; consulted by map + Ask candidate resolution; X may map to Z | Prevent silent re-bind |
| Merge non-destructive + history for future reversal | `merged_away` + `merged_into_id`; `person_merges.snapshot_json`; no Unmerge UX in I6 |
| Central Person resolver; Story/Journal `ensure_person` delegates | Stop duplicate minting |
| Basic display-name correction IN; rich Person UX OUT | Thin slice |
| Email/phone, Immich write-back, HVRT, EVS-014, auto-merge OUT | Scope lock |
| `prove-person` + `/people/ui` | Opaque harness + owner teach path |
| Lowercase Ask person-of extraction | Owner typing; Title Case not required after pictures/photos of |

### Next

[MBBS-001_INCREMENT_7_DEFINITION.md](MBBS-001_INCREMENT_7_DEFINITION.md) — **REVIEW ONLY**; build requires explicit authorization.

---

## Increment 7 — Video Intelligence + Review & Learn

**Date:** 2026-08-10  
**Authorization:** **AUTHORIZED** (*Build Increment 7 only*) — **ACCEPTED**  
**Definition:** [MBBS-001_INCREMENT_7_DEFINITION.md](MBBS-001_INCREMENT_7_DEFINITION.md)  
**Acceptance:** [MBBS-001_INCREMENT_7_ACCEPTANCE.md](MBBS-001_INCREMENT_7_ACCEPTANCE.md) — **ACCEPTED**  
**Owner gate:** FlightSim thin Review — Immich-named person **not** pre-created in `/people/ui` → face Teach (Diane Scollay) → Ask **2** video hits; media root `\\media-server\photos\home videos`; second real person not required (harness)

### Locked decisions (build)

| Decision | Rationale |
|----------|-----------|
| HVRT sibling worker behind VideoIntelligenceProvider (D4) | Monolith never embeds HVRT schemas/process |
| P1 default worker host = FlightSim; location config-driven/portable | No FlightSim hard-code in product logic |
| Authoritative video = media-server family-video filesystem; Plex/Immich not video SoT | LAN configured path; originals untouched |
| Originals vs derived HVRT evidence vs MB owner teaching (PG) | Rebuildable detections; durable identity |
| Face teach required for owner path; voice teach not blocker | Scope lock |
| Presence span merging with configurable gap tolerance | Avoid one-second span flood; Settings UI later |
| EVS-003/007 = person-linked retrieve/play; laughter deferred unless free earn-in | Thin acceptance |
| `prove-video` single command with named subchecks | Operator simplicity |
| Owner gate: real family video; second person harness-only | Practical FlightSim gate |
| Remote mic HTTPS = ops, not I7 | Separate deploy requirement |
| EVS-014, Gallery, Immich write-back, auto-confirm, Guided Capture, SMS, multi-user, polish OUT | Scope lock |
| Trusted-provider Immich lazy Person bootstrap (I7 correction) | No dual People universes; no bulk Immich import |

**Next:** [MBBS-001_INCREMENT_8_DEFINITION.md](MBBS-001_INCREMENT_8_DEFINITION.md) — **REVIEW ONLY**; do not begin I8 / Gallery build without authorization.

---

## Increment 8 — Library / Gallery / Timeline (EF-03)

**Date:** 2026-08-10  
**Authorization:** **AUTHORIZED** (*Build Increment 8 only*) — **ACCEPTED**  
**Definition:** [MBBS-001_INCREMENT_8_DEFINITION.md](MBBS-001_INCREMENT_8_DEFINITION.md)  
**Acceptance:** [MBBS-001_INCREMENT_8_ACCEPTANCE.md](MBBS-001_INCREMENT_8_ACCEPTANCE.md) — **ACCEPTED**  
**Owner gate (locked):** FlightSim Timeline-first Library + required Person filter (I6) + multi-modality browse; undated explicit; video Open in Review; proxied visual thumbs; no invented dates; bounded/paginated reads

### Locked decisions (build)

| Decision | Rationale |
|----------|-----------|
| Timeline-first default; Gallery = same-API alternate view | Browse without Ask; no photo-first second product |
| Required Person filter via I6/I7; no Library teach | Canonical identity; teach stays People/Review |
| Defensible browse date + provenance + undated; no invented dates | Honest chronology across modalities |
| Journal: I5A described/effective preferred; capture separate | Temporal earn-in |
| Paginated/bounded; no full Immich/HVRT corpus fetch | Performance; no provider mirror |
| Thin card detail + date source + trust + deep-links | Evidence First without inspector/graph |
| Video → Open in Review when available | No Review duplication |
| Visual thumbs via MB media proxies (not raw Immich URLs) | Browser cannot use Immich API keys |
| Video segments undated (Bucket Undated/All) | In-video time ≠ calendar date |
| Narrator ≠ About subject (Story associations) | Library Person filter is subject-about |
| Owner ≥3 modalities: visual + narrative/comms + other; calendar optional | Practical FlightSim gate |
| SMS ingest / EVS-014 / Artifacts / Guided Capture / Export / Settings / Immich write-back OUT | Scope lock |
| `prove-library` + I1–I7 proves remain runnable | Operator simplicity |

### Shipped surface

| Surface | Path |
|---------|------|
| Library UI | `/library/ui` |
| API | `GET /library/cards` |
| Media | `/library/media/photo/...`, `/library/media/video-poster` |
| Prove | `prove-library [--flightsim]` |

**Next:** [MBBS-001_INCREMENT_9_DEFINITION.md](MBBS-001_INCREMENT_9_DEFINITION.md) — **REVIEW ONLY**; do not begin I9 / Artifact build without authorization.

---

## Increment 9 — Artifact thin + import jobs (EF-05/06)

**Date:** 2026-08-10 · **Accepted:** 2026-08-11  
**Authorization:** **AUTHORIZED / SHIPPED / ACCEPTED** (*Build Increment 9 only*)  
**Definition:** [MBBS-001_INCREMENT_9_DEFINITION.md](MBBS-001_INCREMENT_9_DEFINITION.md)  
**Acceptance:** [MBBS-001_INCREMENT_9_ACCEPTANCE.md](MBBS-001_INCREMENT_9_ACCEPTANCE.md) — **ACCEPTED**  
**Owner gate:** Real keepsake (**Dad's Picture of Mom**); MB-managed upload to `MemoryBox\Artifacts`; Library without Person; Immich lazy Person; in-app STT→Story; Ask/provenance

### Locked decisions (final review)

| Decision | Rationale |
|----------|-----------|
| Artifact ≠ Representation; 1 Artifact → N representations | EVS-013 / cigar-box; no per-file Artifact |
| Small kind set (keepsake, letter, document, recipe card, clipping, photograph-of-object, other) | Browse/Ask without taxonomy project |
| Owner gate = MB-managed upload; Evidence-ref also supported | Prove preserve, not only pointer |
| Durable media-server storage + content hash; FlightSim ≠ archive SoT | D7; originals sacred |
| P1 Artifact original-media root = `\\media-server\photos\MemoryBox\Artifacts` via `MEMORYBOX_ARTIFACT_MEDIA_ROOT` only (no UNC in app code; ops may create folder) | Same MemoryBox durable tree as Sources; do not invent folder names |
| PG on FlightSim = domain knowledge; binaries on media-server; no Artifact blobs in PG | Topology lock 2026-08-11 |
| Immutable representation bytes; immutable metadata revisions; no byte dup on edit | Parallel Story/Journal; inspect at build |
| Library first-class `artifact` modality; Person **not** required for visibility | Fix Person-only about collapse |
| Person filter narrows when associated | Keep I8 Person browse; one card model |
| Optional voice → I5A Capture/STT → explicit Story Save → link | EVS-013; no Artifact-specific STT |
| Ask by Artifact identity/metadata/relationships | Filename ≠ meaning |
| SMS OUT (stay on P1 backlog); EVS-014 / Guided Capture / Export / recipe ontology OUT | Scope lock |

### Shipped (code)

- Migration `004_artifact_i9.sql`; Artifact service + `/artifact/ui` + APIs  
- `MEMORYBOX_ARTIFACT_MEDIA_ROOT` (ops: `\\media-server\photos\MemoryBox\Artifacts`); integrity hash; no silent overwrite; no PG blobs  
- Library Person-optional `modalities=artifact`; Ask `artifact_hits`  
- Immich lazy-teach on Artifact Person/Narrator (local); linked Stories display; Story `?id=` deep-link  
- `prove-artifact`; health `increment: 9`  
- Ops: [FLIGHTSIM_I9_ARTIFACT_RUNBOOK.md](../ops/FLIGHTSIM_I9_ARTIFACT_RUNBOOK.md) · `config/artifact.env.example`

**Deferred (not I9):** Universal Immich lazy-teach — [TASK-P1P2-001](MBBS_P1_P2_BACKLOG.md).

**Next:** [MBBS-001_INCREMENT_9A_DEFINITION.md](MBBS-001_INCREMENT_9A_DEFINITION.md) — Person Profile (**FINAL REVIEW** — decisions locked; no build until authorized).

---

## Increment 9A — Person Profile, Facts & Relationships

**Date:** 2026-08-11  
**Authorization:** **ACCEPTED** (FlightSim owner 2026-08-11)  
**Definition:** [MBBS-001_INCREMENT_9A_DEFINITION.md](MBBS-001_INCREMENT_9A_DEFINITION.md)  
**Acceptance:** [MBBS-001_INCREMENT_9A_ACCEPTANCE.md](MBBS-001_INCREMENT_9A_ACCEPTANCE.md)  
**Roadmap:** After **I9 Artifact (ACCEPTED)** · Before **I10 EVS-014**  
**Owner gate:** Owner Person (`MEMORYBOX_OWNER_PERSON_ID` and/or People “I am this person”); Eugene father + birthdate; shared marriage; Ask relational resolve; `/people/ui` Profile  

**Deferred:** Full kinship inference (cousins, gendered resolve from `son_of`, etc.) — [TASK-P1P2-002](MBBS_P1_P2_BACKLOG.md).  

**Next:** [MBBS-001_INCREMENT_10_DEFINITION.md](MBBS-001_INCREMENT_10_DEFINITION.md) — EVS-014 (**REVIEW ONLY**; no build until authorized).

### Locked decisions (shipped)

| Decision | Rationale |
|----------|-----------|
| Explicit owner Person for “my/me” relativity; never infer via display_name | Single-owner P1 |
| One relationship assertion SoT; derive inverses in service | Prevent dual-row drift |
| Multiple qualified parents/roles thin P1; disclose ambiguity | No one-father schema |
| Marriage/anniversary = shared life event both participants | EVS-086 |
| Layered facts / aliases / contacts / relationships / life events | Not junk drawer |
| Extend `/people/ui` Profile | Coherent owner surface |
| Ask: owner → Relationship service → Person → existing retrieve | No string hacks |
| Correction supersedes; prior provenance retained | Trust |
| Thin mother/father via spouse of opposite gendered parent only | Avoid Anne-as-father from generic parent_of |
| EVS-014 / tree viz / auto-genealogy / Immich write-back / multi-user / Places / universal lazy-teach / polish OUT | Scope lock |

**Stop:** Do not begin Increment 10 until Tom authorizes.

---

## Increment 10 — Cross-provider Person in Ask (EVS-014)

**Date:** 2026-08-11  
**Authorization:** **BUILD COMPLETE** — harness green; FlightSim owner acceptance pending  
**Definition:** [MBBS-001_INCREMENT_10_DEFINITION.md](MBBS-001_INCREMENT_10_DEFINITION.md)  
**Acceptance:** [MBBS-001_INCREMENT_10_ACCEPTANCE.md](MBBS-001_INCREMENT_10_ACCEPTANCE.md)  
**Roadmap:** After **I9A (ACCEPTED)** · Before **I11 Guided Capture**  
**Owner gate:** One real family Person in Immich + ≥1 HVRT-processed video; Review attach/teach onto one `people.id`; Ask + Library same Person; **HVRT worker required**

### Locked decisions (shipped)

| Decision | Rationale |
|----------|-----------|
| Cross-provider teach via I6/I7 onto one `people.id`; no per-provider Person recreation | EVS-014 |
| No display-name-only join; ambiguity → owner map (`/people/{id}/map`) | Create No False Memories |
| Reprocess reconcile: Person + owner assertions + mapping provenance survive; external IDs not stable; no silent duplicate Person | Durability |
| Ask + existing Library Person filter share mappings | Consistency; no new Library UX |
| Photo-only interim invalid; HVRT worker required for I10-OWNER | EVS-014 |
| EVS-009 shared-identity-across-sources portion only | Catalog bound |
| Kinship / lazy-teach / write-back / tree / multi-user / Capture / Export / polish OUT | Scope |

**Prove:** `python -m memorybox prove-cross-provider-person` (+ `--flightsim`)  
**Stop:** Do not begin Increment 11 until Tom authorizes.

---

## Increment 4 — Ask + Query Planner + basic contextual follow-up

**Date:** 2026-08-09  
**Authorization:** Build Increment 4 only (locked definition); corrective reopen for planner/context + exploratory multimodal  
**Acceptance:** [MBBS-001_INCREMENT_4_ACCEPTANCE.md](MBBS-001_INCREMENT_4_ACCEPTANCE.md) · [MBBS-001_INCREMENT_4_CORRECTIVE_ACCEPTANCE.md](MBBS-001_INCREMENT_4_CORRECTIVE_ACCEPTANCE.md) — **ACCEPTED** (corrective + owner manual validation)  
**Next increment:** [MBBS-001_INCREMENT_5_DEFINITION.md](MBBS-001_INCREMENT_5_DEFINITION.md) — **REVIEW ONLY** (locked review decisions: Story + first-class Ask modality; STT/Journal out; I1 relationships for associations); build requires explicit authorization  
**Post-acceptance policy:** Further Ask-language edge cases → defects/EVS refinements in future increments unless fundamental trust/architecture failure. **No I4 polish.**

### Corrective decisions (same day, post manual test)

| Decision | Rationale |
|----------|-----------|
| Reopen I4 for planner/context only | Manual defects A–H; not a new increment |
| Typed slots + supersede + reference resolution + ambiguity | Prevent person→place contamination and silent wrong retrieval |
| `i4_context_semantics_AH` regression | Catch failure pattern + unseen variation without demo hardcoding |
| In-package Immich HTTP client | FlightSim had no `application/api`; earn-in under `memorybox/providers/photo/` |
| Immich env URL hardening | Mangled `IMMICH_BASE_URL=` pastes caused urllib scheme errors on FlightSim |
| Exploratory / know-about = always multimodal (I4 modalities) | “Know about / tell me about / what do I have about” explores subject across Immich stills + email/calendar — not comms-only and not photo-fallback; explicit narrowing still wins |
| `i4_exploratory_multimodal` regression | Photo-only / evidence-only / both / neither / narrowed communication with unseen subjects |

### Decisions discovered during build

| Decision | Rationale |
|----------|-----------|
| Template/structured answers from Evidence + provider hits (no free-form invention) | Evidence First / No False Memories; LLM optional via LlmProvider only |
| In-memory `ContextStore` protocol | I4 session; clean contract for later persistence |
| `MEMORYBOX_PHOTO_PROVIDER=unavailable` + harness `UnavailablePhotoProvider` for I4-G | Deliberate degradation without taking family Immich offline |
| `MEMORYBOX_P1_RUNTIME_HOST=1` required with `--flightsim` | Prevents desktop from claiming P1-runtime final acceptance |
| Proper-noun lexical constraints on Evidence retrieval | Stops weak keyword/semantic hits from “answering” nonsense asks |
| Thin static Ask shell | Locked: functional only, no polish |
| **Intent-oriented visual semantics** | Broad “show me / pictures / images” → `visual_scope=broad` (stills+video intent); “photos” may narrow to stills; “videos” → video only; “show me” ≠ media type. I4 executes available stills only; **no HVRT/video build**. Contract fields enable later video without NL/architecture change |

### Change-impact check

| Layer | Impact? |
|-------|---------|
| EVS | 005/006 exercised (shaped asks) |
| UX | Thin Ask shell + breadcrumb / clear-change |
| Domain | Session context contract only (no new SoT tables) |
| Experience Flow | EF-01, EF-02 basic, EF-04 thin |
| Architecture | Planner + orchestrator + providers |
| Build Spec | Inc 4 **accepted** on FlightSim |
| Locked decisions | D2/D3/D6/D7 aligned |
| In-package Immich HTTP client | FlightSim had no `application/api`; earn-in under `memorybox/providers/photo/` |
| Immich env URL hardening | Mangled `IMMICH_BASE_URL=` pastes caused urllib scheme errors on FlightSim |

### Specs changed

| Spec | Change |
|------|--------|
| I4 definition | Status → built / awaiting FlightSim final; **§0.1 intent-oriented visual semantics locked** |
| This log | Inc 4 section + visual semantic rule |
| MBBS-001 | Inc 4 status |
| Ops | FlightSim I4 acceptance runbook |
| Planner | `visual_scope` / want_still / want_video contract |

### Intentional tech debt

| Item | Why acceptable |
|------|----------------|
| Process-session context only | Locked for I4; protocol ready for persistence |
| Heuristic planner (regex) v0 | Sufficient for EF-02 basic; not multi-agent |
| POC Immich client earn-in behind PhotoProvider | Matches Inc 2 pattern |

---

## Increment 3 — Email + Calendar → Evidence + derived Qdrant

**Date:** 2026-08-09  
**Authorization:** Build Increment 3 only (final scope: email + calendar; SMS deferred)  
**Acceptance:** [MBBS-001_INCREMENT_3_ACCEPTANCE.md](MBBS-001_INCREMENT_3_ACCEPTANCE.md) — **ACCEPTED**  
**Next increment:** Not started (requires explicit authorization)

### Decisions discovered during build

| Decision | Rationale |
|----------|-----------|
| `evidence_kind=communication` for email; `calendar_event` for calendar | Owner lock — event-oriented kind ≠ communication |
| No `communications` table | Locked; Source + Evidence + payload contracts |
| SMS deferred with Inc 9 / later comms anchor | Final I3 scope |
| Qdrant `:memory:` allowed for desktop prove via config | D7 — network URL on P1 runtime host |
| Fake token-hash embeddings when Ollama unset | Deterministic I3-D retrieval without requiring live LLM |
| Real smoke optional via `MEMORYBOX_SMOKE_*_URI` | Where practical; none available on this host at acceptance |
| `MEMORYBOX_ALLOW_DEV_DEFAULTS` for desktop only | FlightSim must set explicit URLs |

### Change-impact check

| Layer | Impact? |
|-------|---------|
| EVS | No Ask yet |
| UX | No |
| Domain | Email/calendar Evidence payload conventions |
| Experience Flow | EF-05/14 thin |
| Architecture | Ingest + derived Qdrant; D7 |
| Build Spec | Inc 3 accepted; SMS deferred noted |
| Locked decisions | D2/D3/D7 aligned |

### Specs changed

| Spec | Change |
|------|--------|
| I3 definition | Final email+calendar scope |
| MBBS-001 | Inc 3 accepted; SMS deferred |
| This log | Inc 3 section |

---

## Cross-cutting — Media-Server Sources checkpoint (2026-08-09)

**Authorization:** Establish `\\media-server\photos\MemoryBox\Sources`; copy/verify email/calendar/SMS; FlightSim path config; small ingest; originals unchanged  
**Status:** **PASSED** — [MBBS-001_MEDIA_SERVER_SOURCES_CHECKPOINT.md](MBBS-001_MEDIA_SERVER_SOURCES_CHECKPOINT.md)

| Item | Outcome |
|------|---------|
| Sources tree | email / calendar(+ics) / sms + MANIFEST |
| Copy verify | SHA256 match for mbox, calendar zip, SMS CSV |
| Archive mbox after robocopy | UNCHANGED |
| Ingest from Sources | email+calendar limit 5 ok; files unchanged |
| SMS | Staged only — ingest still deferred |
| Next | Increment 4 **not** authorized |

---

## Cross-cutting — FlightSim I1–I3 deployment checkpoint (2026-08-09)

**Authorization:** Deploy accepted I1–I3 to P1 runtime host; real-data smoke; no Increment 4  
**Status:** **PASSED** — [MBBS-001_FLIGHTSIM_I1_I3_CHECKPOINT.md](MBBS-001_FLIGHTSIM_I1_I3_CHECKPOINT.md)

| Item | Outcome |
|------|---------|
| Host | FlightSim (`tomwi`); Docker PG + Qdrant; Ollama local |
| Synthetic proves | PASS |
| Real email + calendar smoke | PASS (5+5 Evidence rows; IDs only in report) |
| Qdrant | Derived; network URL; rebuild/retrieval PASS |
| Next | Increment 4 **not** authorized |

---

## Cross-cutting — D7 P1 deployment (2026-08-09; updated same day)

**Authorization:** Owner lock (not tied to a single increment build)  
**Status:** **LOCKED** as [D7](../source/MB_LOCKED_DECISIONS_P1.md)

| Decision | Detail |
|----------|--------|
| P1 runtime host | **FlightSim** — MemoryBox **application** + MemoryBox-owned services |
| MB-owned on FlightSim | PostgreSQL, Qdrant, local Ollama/model service **where practical** |
| Media host | **media-server** — Immich, Plex, photos, videos, related media storage/libraries |
| Media access | Remote via **provider interfaces** + configured network endpoints |
| P1 non-goal | Do **not** move or duplicate media libraries onto FlightSim |
| Development | May continue on **dev box**; **Increment 3+** must deploy to FlightSim **without source-code changes** |
| Config rule | No hard-coded FlightSim, media-server, localhost, drive letters, IPs, credentials, or dev-machine paths in application logic |
| Git | Deployable app code only; exclude secrets, runtime data, DBs, caches, machine-specific config |

**Specs updated:** Locked decisions, P1 engineering rules, MBBS §2.2 / non-goals, I3 definition §0/§8.  
**Code debt noted:** Inc 1/2 localhost **dev defaults** remain; must not be required for FlightSim — clear for I3-G.  
**Increment 3:** Still **awaiting authorization** after definition review.  

---

## Increment 2 — Provider interfaces + first adapters

**Date:** 2026-08-09  
**Authorization:** Contingent on I1 synthetic gate (owner authorized I2 after Grandpa fixture passed)  
**Acceptance:** [MBBS-001_INCREMENT_2_ACCEPTANCE.md](MBBS-001_INCREMENT_2_ACCEPTANCE.md) — **ACCEPTED**  
**Next increment:** Increment 3 authorized and accepted (2026-08-09)

### Decisions discovered during build

| Decision | Rationale |
|----------|-----------|
| Providers live under `memorybox/providers/` | Matches monolith package; Inc 1 package root |
| Photo/LLM/Email protocols + frozen DTOs | Prevent Immich/Ollama shapes leaking into domain |
| `PhotoPersonRef.external_id` only — no `person_id` field | Hardens “never Immich UUID as Person PK” |
| Immich/Ollama adapters import POC clients via path earn-in | Reuse without promoting POC as architecture |
| Mbox reader reimplemented in-package (no SQLite write) | Email-read → DTO only; ingest dual-write deferred to Inc 3 |
| Offline Fake photo/LLM for `prove-providers` | Acceptance without requiring live Immich/Ollama |

### Change-impact check (this increment)

| Layer | Impact? |
|-------|---------|
| EVS | No |
| UX | No |
| Domain | Mapping pattern exercised via `provider_identities` only |
| Experience Flow | No |
| Architecture | Provider adapter layer realized per MBAA/MBBS |
| Build Spec | Yes — Inc 2 status |
| Locked decisions | Aligns with D2 POC-as-adapter |

---

## Increment 1 — Monolith + PostgreSQL domain v0

**Date:** 2026-08-09  
**Authorization:** Build Increment 1 only (MBBS-001 v0.2 charter)  
**Acceptance:** [MBBS-001_INCREMENT_1_ACCEPTANCE.md](MBBS-001_INCREMENT_1_ACCEPTANCE.md) — **ACCEPTED** (incl. synthetic persistence after PG restart)  
**Checkpoint tag:** `increment-1-accepted`  
**Next increment:** Increment 2 authorized after synthetic gate (2026-08-09)

### Decisions discovered during build

| Decision | Rationale |
|----------|-----------|
| Package root = `memorybox/` | Matches MBBS preference for production package name |
| SQL file migrations + `schema_migrations` table | Thin, explicit, no premature migration framework |
| Default DB URL `postgresql://memorybox:memorybox@127.0.0.1:5432/memorybox` | Local single-owner P1; credentials via env |
| Default API port **8790** (demo used **8791** when Marvin held 8790) | Avoid silent collision; document port conflict |
| Local PostgreSQL 17 Windows service used when Docker Hub pull failed | Still PostgreSQL authoritative store (D3); Compose remains optional path |
| Bootstrap superuser password for local install was installer default `postgres`/`postgres` | Dev-only; not for production secrets |
| Synthetic I1 fixture (Grandpa / christmas.jpg) with stable UUIDs + `seed-synthetic` / `prove-synthetic` | Prove domain FKs survive PG restart without real archive ingest |

### Specifications changed this increment

| Spec | Change |
|------|--------|
| [MB_P1_ENGINEERING_RULES.md](../source/MB_P1_ENGINEERING_RULES.md) | **Added** — founder P1 standing rules (Living Spec, process, trust) |
| [MBBS-001](MBBS-001_MEMORYBOX_BUILD_SPECIFICATION.md) | **v0.3** — embed standing rules; Inc 1 complete; keep runnable |
| [MB_LOCKED_DECISIONS_P1.md](../source/MB_LOCKED_DECISIONS_P1.md) | Pointer to engineering rules |
| [DOCUMENT_HIERARCHY.md](../DOCUMENT_HIERARCHY.md) | Index rules + decision log |
| MBPS / MBEVS / MBUX / MBDM / MBEF / MBAA DOCX | **No product content change** — rules reinforce existing Evidence First, provenance, provider, rebuildability positions (change-impact: process layer only) |

### Intentional deviations

| Item | Notes |
|------|--------|
| `media_refs`, `assertion_evidence` tables | Supporting physical tables not named as top-level MBBS list items; align with MediaRef + Evidence↔Assertion without provider schemas |
| Place / Event / Artifact tables absent | Per MBBS Inc 1 scope list — deferred |

### Technical debt accepted

| Debt | Why acceptable in Inc 1 |
|------|-------------------------|
| No auth on `/health` | Single-owner local; auth later |
| Docker Compose path unproven on this machine (Hub EOF) | Local PG 17 demonstrated acceptance |
| Possible lingering elevated Postgres installer process | Ops hygiene; does not affect schema |

### Unresolved questions

| Question | Impact if deferred |
|----------|--------------------|
| Canonical app listen port vs Marvin (8790) | Low — env-configurable; resolve before multi-service demos |
| When to check in Founder's Book DOCX | Docs completeness; extract remains interim |

### Change-impact check (this increment)

| Layer | Impact? |
|-------|---------|
| EVS | No |
| UX | No |
| Domain | Physical schema v0 introduced under MBDM concepts — documented in migration; conceptual MBDM DOCX unchanged |
| Experience Flow | No |
| Architecture | Monolith + PG path realized per MBAA/D2/D3 |
| Build Spec | Yes — rules + Inc 1 status |
| Locked decisions | No conflict |

### Rules compliance (Inc 1)

| Rule | Status |
|------|--------|
| One increment at a time | Met — only Inc 1 |
| Acceptance before advancement | Met — health/migrate demonstrated |
| Living specs / no silent supersede | Met — rules written into controlled docs this increment |
| No provider schemas as domain | Met |
| No false memories / teaching / provider failure UX | N/A this increment (no Ask yet) — schema supports future provenance |
| Rebuildable derived data | N/A — no derived indexes yet |
| Keep runnable | Met — `python -m memorybox serve` |
| POC earn its way in | Met — no POC code promoted as domain model |
| No migration-debt shortcuts on IDs/provenance/PG | Met — UUID domain PKs; provider IDs only in mapping tables |
