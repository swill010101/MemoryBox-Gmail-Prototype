# P2-I10C — Journal

**Status:** Definition **DRAFT** 2026-08-24 · **not locked** · **not build-authorized**  
**Increment ID:** **P2-I10C Journal.** I10B is Artifacts (**ACCEPTED**). This is the Journal increment even if spoken as “i10B journal.”  
**Assessment / field map:** [MBAS-P2-I10C_ASSESSMENT_RECONCILIATION.md](MBAS-P2-I10C_ASSESSMENT_RECONCILIATION.md)  
**Visuals:** [MBUX Journal Screens](../source/Screens/MBUX%20Journal%20Screens/) (`01` panel, `02` new, `03` detail) from `fe913a4`  
**POC:** Increment 5A — `/journal/ui`, `journal_entries` / `journal_versions`, `prove-journal`  
**Depends:** I10A Stories **ACCEPTED** · I10A.1 **ACCEPTED** · I10A.2 speech **ACCEPTED** · I10B Artifacts **ACCEPTED** · I5A Journal store  
**Does not start:** I11 · I10A.2 polish · guided-capture campaigns (I15) · HVRT journal ingest unless locked below · family multi-user ACL · Face SoT

I10C **does not build** until Tom locks this definition and explicitly authorizes build. A PRD follows lock (same gate as I10A.1 / I10B).

---

## Intent

A Journal entry is the owner’s **own words** about a day, a feeling, or a memory — distinct from a **Story** (shaped family recollection) and from an **Artifact** (object). Capture is easier than organization: type or speak (I10A.2), review, **explicit Save journal**. Ask sees only the **current saved** version, with visibility. Supporting memories are links; originals are never copied. Versions are retained. STT/AI is never Journal truth.

I10C replaces the 5A developer form with I10A-family chrome (panel, new, detail, edit). It **reuses** I10A.2 speech. It **does not** create Stories.

I10C is **not** I11. I10C is **not** a second Story product. I10C is **not** guided email capture.

---

## Build locks (from screens + I5A, pending founder lock of Opens)

1. Surfaces: **Panel**, **New entry**, **Detail**, **Edit** (Edit = New layout on an existing id; no Edit PNG yet).
2. I10A/I10B **family shell**. Journal active. Review & Learn present (panel PNG is incomplete).
3. Speech = existing I10A.2 `authored-memory` on the Entry body only. No mic on title, dates, place, people, search.
4. Body required to **Save journal**. Title optional.
5. Author = owner Person, display-only. SoT `author_person_id`. No free-text author as SoT.
6. Visibility `private` \| `shared_with_family`, default private. Owner Ask sees private. Do not leak.
7. Place = `places.id` when set. No Place string as SoT.
8. People via Person picker; persist `about_person` (or equivalent). Full names + portraits as I10A.
9. Supporting memories: photo, video, communications, calendar, artifact, audio. **Not** Journal→Journal. Unique active link per source. Remove link ≠ delete source. Soft-remove Journal.
10. Ask: current **saved** version only. Draft (if locked in) never Ask-visible. `prove-journal` remains the 5A regression; add `prove-i10c` when built.
11. Integer `journal_versions` retained. View history. Restore-from-history **out**.
12. Channel: `voice` if audio present on save, else `ui`. Email/import channels **out**.
13. STT cannot persist (`actor_key` rule stays).
14. Distinct from Story: no Story blocks model required; Entry is one narrative body (I10A.2 textarea), not heading/paragraph/memory_ref blocks unless a later PRD says otherwise.

---

## Open — Tom must answer before lock

| # | Question | Recommendation |
|---|---|---|
| **O1** | Working **draft** (PNG: Draft, Save draft, Not available to Ask) vs I5A **Save = version 1** (no draft, like I10B Artifacts)? | **Follow the Journal PNGs:** Save draft keeps it out of Ask; Save journal creates/advances a saved version and is Ask-current. Need a working row (Stories-style) **or** `status=draft`. Do not Ask-index drafts. |
| **O2** | One **Entry date** + optional **Time** (PNG) vs POC **start/end + precision** including `range`? | **One Entry date** in New/Detail. Persist start=end, `precision=day`. Blank → unknown. Optional time is described time, not `captured_at`. Month/year/approximate on Edit if we refuse fake days. Range UI **out** unless you want Stories-style range. |
| **O3** | Panel **calendar** + **On this day** in I10C? | **In.** Calendar dots = described Entry dates. On this day = prior-year saved entries (EVS-072 still works via Ask if you cut the widget). |
| **O4** | **HVRT journal ingest** this increment? Roadmap said HVRT→MB Journal. I5A already stores journals. | **Out of I10C.** Family chrome on the existing store. Ingest later. |
| **O5** | Save journal **without a title**? PNG says optional; I10A Stories require a title. | **Optional title.** Untitled cards use first body line, not a fake title. |
| **O6** | People pills like “Family” / “Christmas” / “Artifacts” on panel cards? | **People only** (and maybe Artifact when linked). No tag taxonomy. “Christmas” is not a field. |

Until O1–O2 are answered, do not treat draft or date-range as Frozen.

---

## Locked implementation choices (safe now)

- Routes **Recommendation:** `/journal/ui` panel; `/journal/ui?new=1` New; `/journal/ui?id=` Detail; Edit `?id=&edit=1` (names may change in PRD; one HTML app like Story/Artifact).
- List API must grow excerpt, author display name, memory count, visibility, described date — today’s `GET /journal` is insufficient for cards.
- Memory links: new `journal_version_memories` (or equivalent) mirroring I10A `story_version_memories`. Do not overload `cites_evidence` for photos.
- Soft-remove `status=removed`; hide from panel and Ask.
- I10A.2 cache/query unchanged; Journal page stays a consumer.
- Dark theme. Pixels lose to Frozen rows.

---

## POC → product (what I10C replaces)

| Goes away | Becomes |
|---|---|
| Three numbered developer sections + JSON `<pre>` | Panel / New / Detail / Edit |
| Paste Journal UUID to edit | Open from panel / Edit entry |
| Author text field default “Tom” | Owner Person |
| Start+end+precision widgets on the capture form | O2 |
| List-all JSON | Searchable feed + filters (All, Mine, People, time) |
| Family contributions tab | **Out** (no second user) |

---

## Prove (when authorized)

Extend or add `python -m memorybox prove-i10c`. Keep `prove-journal` (5A) green. FlightSim: `/journal/ui` after migrate. Cover: new → draft (if O1) → save journal → Ask current → edit version N+1 → history → memories add/remove → visibility private → soft-remove; speech Save still preserves `audio_uri`; cancel/discard writes no orphan Ask row.

---

## After I10C

**I11** remains closed until I10A + I10A.1 + I10A.2 + I10B + I10C and required recognition/transcription work.

---

**Not locked. Not authorized to build.** Sign this definition, then PRD, then build.
