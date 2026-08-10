# MBBS-001 Increment 8 — Definition (final review — decisions locked)

**Status:** **ACCEPTED** — see [MBBS-001_INCREMENT_8_ACCEPTANCE.md](MBBS-001_INCREMENT_8_ACCEPTANCE.md)  
**Date:** 2026-08-10  
**Owner acceptance gate (locked):** On FlightSim, Tom can open the thin **Library** client **without developer intervention**, use **Timeline-first** browse (Gallery as alternate view of the **same** cards), apply a **required Person filter** resolved via the I6/I7 Person service, browse across **≥3 real modalities** meeting the locked mix rules (§3), open thin evidence-first card detail (including **date provenance**), use **Open in Review** on video cards when available, and keep undated items in an explicit **Undated** state — without inventing dates or re-implementing Teach inside Library. Synthetic harnesses prove unified API, pagination/bounds, date semantics, person filter, provider-down degrade, and undated behavior.  
**Charter source:** [MBBS-001](MBBS-001_MEMORYBOX_BUILD_SPECIFICATION.md) § Increment 8  
**Governed by:** [MB_P1_ENGINEERING_RULES.md](../source/MB_P1_ENGINEERING_RULES.md) · [MB_LOCKED_DECISIONS_P1.md](../source/MB_LOCKED_DECISIONS_P1.md)  
**EVS catalog (authoritative):** [MBEVS-001_EVS_Catalog_v0.8.xlsx](../source/MBEVS-001_EVS_Catalog_v0.8.xlsx)  
**Depends on:** Increment 3 (email/calendar Evidence) · Increment 4 Ask · Increment 5 / 5A (Story / Journal temporal) · Increment 6 Person · **Increment 7 Video / Review (ACCEPTED)** · D7  
**Prior:** [MBBS-001_INCREMENT_7_ACCEPTANCE.md](MBBS-001_INCREMENT_7_ACCEPTANCE.md) — **ACCEPTED**  
**Authorization:** *Build Increment 8 only* — **ACCEPTED**.

---

## 0. Locked decisions (final)

| Topic | Decision |
|-------|----------|
| Product slice | **Library / Gallery / Timeline** as **one** browse surface over a **unified Library card/read API** — browse family life **without** requiring an Ask question (EF-03) |
| Default experience | **Timeline-first** is the default Library view |
| Gallery | Alternate **visual** view over the **same** unified Library card/read API. **Not** a separate photo-first product. **Not** a second evidence model |
| Primary EVS | **EVS-015** thin |
| Person filter | **REQUIRED** in I8. Resolves through the **canonical I6/I7 Person service**. Browse/filter cards associated with an MB Person **without** re-implementing Person teaching in Library. Deep teach/edit remains in **People / Review** |
| Date semantics | Do **not** flatten modalities into one naive `occurred_at`. Normalize a **defensible browse/display date (or range)** while retaining **date provenance/source**, precision/approximation when known, and explicit **undated**. **Do not invent dates** to force timeline placement |
| Journal temporal | Reuse **I5A**: prefer **described/effective** date/range for Library ordering when defensible; keep **capture/creation** time separate in card detail/provenance |
| Story temporal | Described/event date when available; otherwise explicit fallback / undated — never silent invent |
| Performance | Paginated, **bounded** reads. **No** first-page fetch of entire Immich/HVRT/provider corpora. Pagination/cursoring; bounded date windows where appropriate; modality + person filters; provider calls limited to requested page/filter scope when the provider allows. **No full provider mirror** |
| Card detail | Thin evidence-first detail: what it is, modality, provenance/source/provider, **why/where displayed date came from**, associated MB Person(s), identity trust, deep-link to the appropriate existing surface. **No** full inspector / knowledge-graph editor |
| Video deep-link | Video cards: **Open in Review** when Video Intelligence / Review is available. **Do not** duplicate Review inside Library |
| Owner modalities (≥3) | At least one **visual** (photo **or** video); at least one **narrative/communication** (email, Story, **or** Journal); plus **≥1 additional distinct** modality. **Calendar** first-class when available — **not** specifically required for owner gate |
| Undated | Explicit **Undated** bucket/state. Undated stays undated. Full Review & Learn for fixing missing dates = **later** work |
| Identity trust | Reuse I6/I7: owner-confirmed vs trusted-provider vs candidate — never silently promote |
| Unified model | One Library read model; **PG authoritative domain** + providers; **no** second evidence database |
| SMS | Earn-in only if Evidence exists; **no SMS ingest requirement** for I8 |
| Immich write-back | **OUT** |
| EVS-014 / Artifacts / Guided Capture / Export | **OUT** → Inc 10 / 9 / 11 / 12 |
| Settings / multi-user / polish | **OUT** |
| Hosts (D7) | FlightSim app + PG; media on media-server via existing providers; config-only paths (`\\media-server\photos\home videos` for video worker) |
| Prove | **`prove-library`** primary; I1–I7 proves remain runnable; FlightSim owner acceptance |

---

## 1. Problem / why now

Ask, Story/Journal, People, and Review are **directed** surfaces. The family still cannot **browse** life across modalities without inventing a question.

Without I8, EVS-015 stays unmet and risk rises of a photo-only Gallery or a second evidence store that ignores Person trust and I5A date semantics.

I8 productizes **one** Timeline-first Library over the **same** MB domain + providers, with honest dates and bounded reads.

---

## 2. Objective

1. **Unified Library read API** — paginated/bounded cards; modality + **required Person** filters; defensible date model + undated.  
2. **Thin Library UX** — Timeline default; Gallery alternate over same API; thin card detail; video → Open in Review.  
3. **I6 Person filter** — no teach path inside Library.  
4. Prove via **`prove-library`** + FlightSim owner gate.

| Field | Content |
|-------|---------|
| **Modules** | Library read API + card DTO; Timeline/Gallery thin UX; Person filter via I6; date/provenance read-model |
| **Flows** | **EF-03**; **EF-04** thin (browse visual refs — not a new Ask rewrite) |
| **EVSs in** | **EVS-015** thin |

---

## 3. Success criteria (acceptance)

Final acceptance on **FlightSim** for **I8-OWNER**; harness via **`prove-library`**.

| ID | Criterion | Proof |
|----|-----------|-------|
| **I8-A** | Unified Library API returns mixed-modality cards (synthetic ≥3 modalities) | `prove-library` |
| **I8-B** | Timeline-first default; Gallery is same-API alternate view | Harness + UX |
| **I8-C** | Modality filter works; product still supports multi-modality | Harness |
| **I8-D** | **Person filter required** — resolves via I6/I7 Person service; filters cards for an MB Person without Library teach UX | Harness + FlightSim |
| **I8-E** | Date model: browse date/range + date provenance + precision/approx when known + explicit undated; **no invented dates** | Harness |
| **I8-F** | Journal prefers described/effective date/range when defensible; capture time preserved in detail | Harness |
| **I8-G** | Paginated/bounded; no full Immich/HVRT corpus pull for first page; filters constrain provider scope where allowed | Harness |
| **I8-H** | Thin card detail: what / modality / provenance / date source / Person(s) / trust / deep-link | Harness + FlightSim |
| **I8-I** | Video card **Open in Review** when provider/Review available; no Review duplication | Harness / FlightSim |
| **I8-J** | Undated bucket/state; undated not silently chronologized | Harness |
| **I8-K** | Photo/video provider down → Library up; affected modalities **visible degrade** | Harness |
| **I8-L** | I6/I7 trust labels honored — no silent candidate→confirmed | Harness |
| **I8-OWNER** | FlightSim: Timeline browse with Person filter; **≥3** real modalities with locked mix (§0); card detail + date provenance; no developer intervention / SQL | Tom on FlightSim |
| **I8-M** | Owner modality mix: ≥1 visual (photo\|video) + ≥1 narrative/comms (email\|Story\|Journal) + ≥1 other distinct modality; calendar optional | FlightSim |
| **I8-N** | No Immich/HVRT native schemas as MB domain; originals untouched; no provider mirror | Health / policy |
| **I8-O** | I1–I7 proves remain runnable | Prior prove commands |
| **I8-P** | Living specs | Decision log + acceptance report |
| **I8-Q** | SMS: disclose if absent; not owner blocker | Note |

---

## 4. Scope

### In

- Unified Library card/read API (one evidence read model)  
- Timeline-first UX + Gallery alternate over **same** API  
- **Required** Person filter via I6/I7 Person service (link-only to People/Review for teach)  
- Modality filters; pagination/cursoring; bounded date windows  
- Date read-model: browse date/range, provenance, precision/approx, undated  
- Journal I5A effective vs capture temporal earn-in  
- Thin card detail + deep-links (Ask / People / **Open in Review** for video)  
- Explicit Undated state  
- Provider-down degrade per modality  
- **`prove-library`** + FlightSim owner path  

### Out

| Out | Notes |
|-----|--------|
| Separate photo-first Gallery product / second evidence model | Forbidden |
| Full Immich/HVRT mirror or unbounded provider fetch | Forbidden |
| Inventing dates to force timeline placement | Forbidden |
| Full date-repair Review & Learn | Later |
| Full inspector / knowledge-graph editor | Out |
| Person teach/edit inside Library | People / Review only |
| Immich write-back | Locked OUT |
| EVS-014 full cross-provider loop | **Increment 10** |
| Artifact work | **Increment 9** |
| Guided Capture | **Increment 11** |
| Export | **Increment 12** |
| SMS ingest as I8 requirement | Earn-in only |
| Settings / multi-user / polish | Out |
| Duplicating Review inside Library | Open in Review only |
| Auto-curated highlights / invented narrative | Create No False Memories |

---

## 5. Domain / provider intent

### 5.0 Library card read model (locked concepts)

Each card is a **read model**, not a new SoT. Illustrative fields/concepts:

| Concept | Rule |
|---------|------|
| `modality` | email \| calendar \| photo \| video \| story \| journal \| (sms if present) |
| Domain / provider ids | MB UUIDs for Story/Journal/Evidence/Person; provider IDs remain `external_id` only |
| `browse_date` / `browse_date_end` | Normalized defensible display date or range for Timeline ordering — **not** a flattened fake `occurred_at` for all types |
| `date_provenance` | Source/meaning of the browse date (examples below) |
| `date_precision` / approximation | When already available from domain/provider |
| `undated` | Explicit true when no defensible date — item goes to **Undated**, not invented chronology |
| `capture_at` (when applicable) | Separate from described/effective (esp. Journal I5A) |
| `identity_trust` | confirmed \| trusted_provider \| candidate \| n/a |
| Persons | Associated MB Person id(s)/names via I6 mappings — not raw Immich-as-PK |
| Deep-links | Ask / People / Review as appropriate |

### 5.1 Date provenance examples (normative intent)

| Modality | Prefer for browse date | Provenance note |
|----------|------------------------|-----------------|
| email | sent/received | Email temporal SoT |
| calendar | event start/date | Event temporal |
| photo | capture/EXIF when available | Else undated or explicit provider fallback — never invent |
| video | media date / segment context when known | Else undated/fallback disclosed |
| Journal | **described/effective** date/range (I5A) | Capture/creation retained separately in detail |
| Story | described/event date when available | Else explicit fallback / undated |
| unknown | — | **undated** |

### 5.2 Bounded reads (locked)

- Pagination / cursoring required.  
- First page must **not** pull entire Immich or HVRT corpora.  
- Person + modality + optional date window constrain the query.  
- Provider calls scoped to the requested page/filter when the provider allows.  
- No full provider mirror for I8.

### 5.3 Surfaces

```
Ask     = question → retrieve
Review  = teach video faces (+ Open in Review from Library video cards)
People  = teach / map identity
Library = browse / filter without a question (Timeline default; Gallery alternate)
```

---

## 6. UX (thin)

Locked thin Library surface:

- **Timeline** default  
- **Gallery** alternate visual layout over **same** cards/API  
- **Person filter required** (I6 resolution)  
- Modality filters  
- Explicit **Undated** bucket/state  
- Open card → thin evidence-first detail (incl. date provenance)  
- Video → **Open in Review** when available  
- Nav: Ask · Review · People · Library  

No dashboard chrome, no graph editor, no Settings, no Library teach.

---

## 7. Architecture notes

```
memorybox serve (FlightSim)
    ├─ /ask/ui
    ├─ /review/ui
    ├─ /people/ui
    └─ /library/ui  ← I8 (Timeline default / Gallery alternate)
         │
         ▼
    Library read API (paginated, bounded, person+modality filters)
         ├─ PG Evidence / Story / Journal / People (I6)
         ├─ PhotoProvider (Immich — scoped calls)
         └─ VideoIntelligenceProvider (worker → \\media-server\photos\home videos)
```

Demonstrator Library = mine for UX ideas only — not P1 SoT.

---

## 8. EVS scope (MBEVS-001 v0.8)

### 8.1 In (thin)

| EVS ID | Role in I8 |
|--------|------------|
| **EVS-015** | Browse timeline/library across modalities — **not Ask-only** |

### 8.2 Out (later)

| Slice | Increment / track |
|-------|-------------------|
| EVS-014 | 10 |
| EVS-013 Artifact | 9 |
| Guided Capture | 11 |
| Export | 12 |
| Soft related suggestions (EVS-016) | Out unless free earn-in |
| Date-repair Review & Learn | Later |

---

## 9. Build plan (only after *Build Increment 8 only*)

1. Library card DTO with date/provenance/undated + Person refs.  
2. Paginated/bounded read API + modality + **Person** filters.  
3. Wire PG modalities + scoped photo/video provider refs.  
4. Thin `/library/ui`: Timeline default, Gallery alternate, Undated, card detail, Open in Review.  
5. Provider-down degrade.  
6. **`prove-library`** + `--flightsim`.  
7. Confirm I1–I7 proves.  
8. Acceptance report; **stop**.

---

## 10. Risks

| Risk | Mitigation |
|------|------------|
| Photo-first second product | Gallery = same API view only |
| Naive single timestamp | Locked date provenance model + undated |
| Unbounded Immich/HVRT fetch | Pagination + scoped provider calls; harness |
| Trust dilution | I6/I7 labels; no Library teach |
| Journal wrong order | I5A effective vs capture earn-in |
| Scope into Review/date repair | Open in Review + Undated only |

---

## 11. Authorization gate

**Status: ACCEPTED** — see [acceptance](MBBS-001_INCREMENT_8_ACCEPTANCE.md).

Do **not** begin Increment 9 / 10 / Guided Capture / Export without new authorization.
Next: [MBBS-001_INCREMENT_9_DEFINITION.md](MBBS-001_INCREMENT_9_DEFINITION.md) — **REVIEW ONLY**.

---

## 12. Stop line

After owner acceptance: do **not** begin Increment 9 / 10 / Guided Capture / Export without new authorization.

---

## 13. Residual open items (non-blocking)

Optional later: exact cursor pagination scheme polish; P1 default page size; Gallery density; fuller about-graph (Story about Evidence auto-in Library).

---

*End of Increment 8 definition — ACCEPTED.*
