# P2-I10C — Journal

**Status:** **ACCEPTED** 2026-08-24 (Tom: “i10C - journal is accepted”) · Definition **LOCKED** 2026-08-24  
**Increment ID:** **P2-I10C Journal.** I10B is Artifacts (**ACCEPTED**).  
**Assessment / field map:** [MBAS-P2-I10C_ASSESSMENT_RECONCILIATION.md](MBAS-P2-I10C_ASSESSMENT_RECONCILIATION.md)  
**Visuals:** [MBUX Journal Screens](../source/Screens/MBUX%20Journal%20Screens/) (`01` panel, `02` new, `03` detail) from `fe913a4`  
**POC:** Increment 5A — `/journal/ui`, `journal_entries` / `journal_versions`, `prove-journal`  
**Depends:** I10A Stories **ACCEPTED** · I10A.1 **ACCEPTED** · I10A.2 speech **ACCEPTED** · I10B Artifacts **ACCEPTED** · I5A Journal store  
**Does not start:** I11 · I10A.2 polish · guided-capture campaigns (I15) · HVRT journal ingest · family multi-user ACL · Face SoT · Mine / Family contributions filters

A PRD is [MBPRD-P2-I10C_JOURNAL.md](MBPRD-P2-I10C_JOURNAL.md). **ACCEPTED** 2026-08-24.

---

## Intent

A Journal entry is the owner’s **own words** about a day, a feeling, or a memory — distinct from a **Story** (shaped family recollection) and from an **Artifact** (object). Capture is easier than organization: type or speak (I10A.2), review, **Save draft** or **Save journal**. Ask sees only the **current saved** version, subject to visibility — never an unfinished draft. Supporting memories are links; originals are never copied. Versions are retained. STT/AI is never Journal truth.

I10C replaces the 5A developer form with I10A-family chrome (panel, new, detail, edit). It **reuses** I10A.2 speech. It **does not** create Stories. It **productizes the existing Journal store**; it does not ingest HVRT journals.

I10C is **not** I11. I10C is **not** a second Story product. I10C is **not** guided email capture.

---

## Founder locks (2026-08-24)

These **supersede** the prior draft Opens O1–O6 and the “All + Mine” panel recommendation.

### Working drafts — IN

- **Save draft** keeps the entry **out of Ask**.
- **Save journal** creates or advances the **saved** version and makes **that** version Ask-eligible, subject to visibility.
- When editing an already-saved entry, the user may work on a **draft** while Ask continues using the **last saved version** until **Save journal**.
- An unfinished edit must **not** immediately change MemoryBox answers.

### One Entry date + optional time — IN

- I10C UI does **not** expose start/end date **ranges**.
- Keep the underlying range-capable schema (`described_start_date` / `described_end_date`) for **imports/future** use.
- **Preserve date precision.** Do not manufacture a fake day when only month or year is known (I10A.1 pattern).
- `captured_at` is the system capture/save timestamp. It is **not** the Entry date.
- Optional **described time** is likewise **separate** from `captured_at`.

### New-entry default date — IN

- New Journal entry: **Entry date defaults to today**, and stays **editable**.
- Recording an older memory: the user changes Entry date.
- Actual capture timestamp remains separately preserved (`captured_at`).

### Calendar + On this day — IN

- Calendar **dots** = **saved** Journal **Entry dates** (described Entry date, not `captured_at`).
- **On this day** = **saved** entries from **prior years** matching the viewed calendar date’s month/day (default today).
- **Drafts do not appear** on the calendar or On this day.

### HVRT Journal ingest — OUT

- I10C productizes the existing Journal store.
- Import/ingest later.

### Title — OPTIONAL

- **Body required** to **Save journal**.
- **Save draft** may keep in-progress text so work is not lost; it still stays out of Ask.
- Untitled **saved** entries display the first **meaningful** body line/excerpt.
- Do **not** invent “Untitled Journal” as though it were authored text.

### No tag taxonomy

- **People pills** are fine (real Person links).
- Artifact or other **real linked-object** indicators may appear where useful.
- Do **not** manufacture concepts like “Christmas” as a Journal tag without an actual tagging model.

### Panel filters

- **All entries only.**
- Do **not** show **Mine** or **Family contributions** until multiple authors/users actually exist.
- Mine has no filtering value today and would promise functionality we do not have.

---

## Build locks

1. Surfaces: **Panel**, **New entry**, **Detail**, **Edit** (Edit = New layout on an existing id; no Edit PNG yet).
2. I10A/I10B **family shell**. Journal active. Review & Learn present (panel PNG is incomplete).
3. Speech = existing I10A.2 `authored-memory` on the Entry body only. No mic on title, dates, place, people, search.
4. Body required. Title optional. Untitled display = first meaningful body line, never invented title copy.
5. Author = owner Person, display-only. SoT `author_person_id`. No free-text author as SoT.
6. Visibility `private` \| `shared_with_family`, default private. Owner Ask sees private. Do not leak.
7. Place = `places.id` when set. No Place string as SoT.
8. People via Person picker; persist `about_person` (or equivalent). Full names + portraits as I10A.
9. Supporting memories: photo, video, communications, calendar, artifact, audio. **Not** Journal→Journal. Unique active link per source. Remove link ≠ delete source. Soft-remove Journal.
10. Ask: **current saved version only**, subject to visibility. Drafts never Ask-visible. Saved answers do not change until **Save journal**.
11. Integer `journal_versions` retained for **saved** versions. View history. Restore-from-history **out**.
12. Channel: `voice` if audio present on Save journal, else `ui`. Email/import channels **out**.
13. STT cannot persist (`actor_key` rule stays).
14. Entry is one narrative body (I10A.2 textarea), not Story heading/paragraph/memory_ref blocks.
15. Panel list filter: **All entries** only. People and time filters may still narrow that list. No Mine. No Family contributions.
16. Calendar + On this day as founder-locked above.
17. New Entry date defaults to **today**, editable; precision UI must not fake a day.

---

## Locked implementation choices

- Routes **Recommendation:** `/journal/ui` panel; `/journal/ui?new=1` New; `/journal/ui?id=` Detail; Edit `?id=&edit=1` (names may change in PRD; one HTML app like Story/Artifact).
- Working draft needs a Stories-like **working vs saved pointer** (or equivalent). Ask reads saved only.
- List API must grow excerpt, author display name, memory count, visibility, described Entry date — today’s `GET /journal` is insufficient for cards. List **saved** entries on the panel; drafts belong on the editor, not On this day/calendar.
- Memory links: new `journal_version_memories` (or equivalent) mirroring I10A `story_version_memories`. Do not overload `cites_evidence` for photos. Attach memories to the **working** draft; Ask/detail-for-Ask use the **saved** version’s links until Save journal.
- Soft-remove `status=removed`; hide from panel, calendar, On this day, and Ask.
- I10A.2 unchanged as a consumer. Dark theme. Pixels lose to Frozen rows.
- Date precision vocabulary stays (`day` \| `month` \| `year` \| `approximate` \| `unknown`). Do not use `range` in I10C UI. Schema may still hold start≠end for future import.

---

## POC → product (what I10C replaces)

| Goes away | Becomes |
|---|---|
| Three numbered developer sections + JSON `<pre>` | Panel / New / Detail / Edit |
| Paste Journal UUID to edit | Open from panel / Edit entry |
| Author text field default “Tom” | Owner Person |
| Start+end+precision range widgets | One Entry date + optional time + precision (no range UI) |
| Immediate Ask on Save | Save draft vs Save journal; Ask = last saved |
| List-all JSON | Searchable **All entries** feed + People/time filters |
| Mine / Family contributions (PNG) | **Out** until multiple authors exist |

---

## Prove (when authorized)

Add `python -m memorybox prove-i10c`. Keep `prove-journal` (5A) green. FlightSim: `/journal/ui` after migrate.

Must cover: new (Entry date defaults today) → Save draft (not in Ask, not on calendar/On this day) → Save journal (Ask-eligible per visibility, calendar dot) → edit saved while Ask still serves previous saved → Save journal advances Ask; history; memories add/remove on draft vs saved; private visibility; soft-remove; untitled excerpt; month/year precision without a fake day; speech Save journal still preserves `audio_uri`; cancel/discard writes no Ask row.

---

## After I10C

**I11 Narrative & Summaries** is next (Ask output mode). Do not reopen Journal chrome.

---

**ACCEPTED 2026-08-24.**
