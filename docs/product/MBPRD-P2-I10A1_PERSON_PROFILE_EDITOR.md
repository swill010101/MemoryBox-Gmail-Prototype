# MBPRD-P2-I10A.1 — Person Profile and Editor

**Status:** PRD **ACCEPTED** (owner) · **amended 2026-08-23** (Person Explorer header / About vs Edit) · implementation **must follow this contract**; chrome prove is red until built  
**Date:** 2026-08-23  
**Increment definition:** [MBBS-P2_INCREMENT_10A1_DEFINITION.md](MBBS-P2_INCREMENT_10A1_DEFINITION.md)  
**Assessment:** [MBAS-P2-I10A1_ASSESSMENT_RECONCILIATION.md](MBAS-P2-I10A1_ASSESSMENT_RECONCILIATION.md)  
**Field / action map:** [MBAS-P2-I10A1_FIELD_ACTION_MAP.md](MBAS-P2-I10A1_FIELD_ACTION_MAP.md)  
**Screen contract:** [MBSC-P2-I10A1_PERSON_SCREEN_CONTRACT.md](MBSC-P2-I10A1_PERSON_SCREEN_CONTRACT.md)  
**Acceptance:** [MBAT-P2-I10A1_ACCEPTANCE.md](MBAT-P2-I10A1_ACCEPTANCE.md) · `python -m memorybox prove-person-i10a1`

**Visual baseline:** `MBUX-Person-Edit-v1.png` on `fe913a4` (`cursor/marvin-capture-v01-3344`) in `docs/source/Screens/MBUX Story Screens/`. Copy to `docs/source/Screens/MBUX Person Screens/` before implementation. Pixels lose to Frozen rows.

**Depends:** I1–I8A **ACCEPTED** · I5 **ACCEPTED** · I6 **ACCEPTED** · I10A **ACCEPTED** · I10B **ACCEPTED** 2026-08-23 · profile APIs in `memorybox/app.py` / `memorybox/profile/` / `memorybox/person/`

**Does not start:** I10A.2 · I10C · I11 · I8.5 · Immich write-back · I5 timeline/gallery rebuild

**Increment ID:** **P2-I10A.1 — Person Profile and Editor.** Not I5. Does not reopen I5.

**Legend:** **Frozen** · **Existing** · **Required** · **Recommendation** · **Open**

---

## Frozen product decisions

Owner 2026-08-23, including Explorer amendment.

1. Person Explorer remains **memory-focused**. Do **not** place every profile field permanently on it. The **header is a summary**; **About** is the complete read-only record; **Edit** is the writable record.
2. **One** enriched Person header **above** Ask. Remove the second portrait/name identity card below Ask (`#mb-explore-curator` on this surface).
3. Header shows: preferred provider portrait; full/display name; alternate/known-as when present; birth/death **with date precision**; relationship to the MemoryBox owner when known; primary/important place when available; **labeled** memory totals by supported kind; actions **About · Edit · Relationships · Learn**.
4. **Do not** show an unlabeled media/result date range that can be mistaken for lifespan. Distinguish person life dates, current result/media range, total memories, and counts by kind.
5. **Do not** expose full contact information in always-visible chrome (header or footer About card). Contacts belong in About (read) and Edit (write).
6. **About** opens a **complete read-only** view of the supported person record (identity, aliases, life facts and notes, family, confirmed contacts, important places, relevant provenance/confirmation). It is **not** the editor. This is how the family inspects the record and decides whether to correct it.
7. **Edit** **bypasses** About and opens **`/people/{id}/edit`**, already populated for the selected person. No extra picker.
8. The bottom action in About opens the **same** editor.
9. About, header, and Edit **share** field mapping, SoT, date precision, provenance, and relationship interpretation (this increment — not a later polish).
10. MemoryBox corrections **must not silently write changes back to Immich**.
11. MemoryBox Person is canonical. Immich / HVRT people are **provider identities**.
12. Taught vs Derived kinship stays I6: editor writes taught assertions only; Derived is read-only and labeled.
13. Advanced identity tools (reject, merge, teach, repair, “I am this person”) live on Edit in a **separated** section. They must not visually compete with ordinary profile editing. They are **not** on About.
14. No Person working draft. Save writes. Cancel/Back without Save writes nothing.
15. Preferred provider portrait on the Explorer header is **in scope** (absorbs **P2-BL-I5-01**).

---

## Problem and success

**Problem:** Explorer is the family home. The complete record and all admin repairs live on `/people/ui?admin=1`, or are misrouted (header **Edit** opens the About drawer). Families cannot see or correct the full person without leaving the product path.

**Success**

- One header above Ask; no curator identity duplicate; life dates ≠ result range.
- Header: portrait, name, aka, life dates with precision, owner kinship, place when known, labeled kind totals, About/Edit/Relationships/Learn.
- About → complete read-only supported record. Footer → `/people/{id}/edit`.
- **Edit** → `/people/{id}/edit` directly, same id, no picker.
- Edit screen: Profile, Relationships (grouped), Identity and Sources, Advanced.
- Header / About / Edit show the same name, facts, precision, and kinship rules.
- Rename, facts, contacts, relationships do not call Immich update APIs.
- FlightSim: open a person, Edit, change display name, reload Explorer header — MB name changed; Immich person name unchanged.
- `python -m memorybox prove-person-i10a1` is green.

---

## A. Surfaces and navigation

Canonical chrome: [MBSC-P2-I10A1_PERSON_SCREEN_CONTRACT.md](MBSC-P2-I10A1_PERSON_SCREEN_CONTRACT.md).

### Person Explorer — **Existing** gallery, **Required** header rewrite

I5 Ask / gallery / filters / timeline / map stay. Identity chrome is **one** enriched header above Ask.

| Control | Today | I10A.1 |
|---|---|---|
| Header | Portrait, name, kinship+years; **Edit** opens About | Enriched summary (contract S.1.1). **Edit** → `/people/{id}/edit`. |
| `#mb-explore-curator` | Second portrait/name + result copy below Ask | **Remove / hide** on Person surface. |
| **View / Edit details** | Opens About | **Remove.** Header **About** opens About. |
| About card `#mb-person-about-dl` | Always-visible contacts | Teaser only — **no** emails/phones. |
| **+ Add family** | Jumps to `?admin=1#relationships` | I6 modal or Edit Relationships — **not** admin. |

### About — **Required** complete read-only

Not a short teaser. Same supported fields as Edit Profile + Relationships + Identity **read** (not Advanced writes). Footer → `/people/{id}/edit`.

### Full Person Profile/Editor — **Required**

**Frozen path:** `GET /people/{id}/edit`. I10A/I10B dark chrome, sticky Cancel / Save.

Boot: `{id}` from the path (already selected). `GET /people/{id}` + `GET /people/{id}/profile` + `GET /people/{id}/portrait` + `GET /people/{id}/provider-projection`. No `picker-options` / `ensure` on this path.

`?admin=1` / `people.html` is **not** the family Edit URL.

---

## B. Full-editor regions

### Profile

Portrait (display; `GET /people/{id}/portrait`). Full/display name. Nicknames / alternate names. Birth and death. Notes. Email/phone. Important places (honest empty until a place SoT exists).

### Relationships

Groups: **Parents · Siblings · Spouse or partner · Children · Other family**.

User adds **one** taught assertion (`POST /people/relationships`). Service `INVERSE_ROLE` / derived projection maintains the other side. Do not require the user to enter both directions.

Withdraw / change use Existing supersede/withdraw routes (already on the I6 modal).

Marriage/anniversary: Existing shared life event (one date, two people).

Derived kinship: read-only, labeled **Derived**.

### Identity and Sources

Show without mixing SoT:

- Canonical MemoryBox Person (`people.id`, `status`, `display_name`)
- Linked `provider_identities` (Immich `external_id`, label, `confirmed_at` / `confirmed_by`)
- Mapping / confirmation / relevant `provenance_json` / assertions

Immich rows are **links**, not the person.

### Advanced identity tools

Separated (disclosure / “Advanced” block):

- Reject incorrect photo/person mapping
- Merge duplicate MB people
- Teach or confirm a face
- Repair provider mappings (`map` / `reconcile`)
- Set or change “I am this person”

Confirm before merge / reject / owner change.

---

## C. Field and action mapping

The complete table (screen section, UI label, existing source, write/action, Immich write, disposition) is [MBAS-P2-I10A1_FIELD_ACTION_MAP.md](MBAS-P2-I10A1_FIELD_ACTION_MAP.md). Summary:

| Screen section | What lives there |
|---|---|
| Explorer header | Summary only: portrait, name, aka, life dates (precision), owner kinship, place if known, labeled kind totals. About / Edit / Relationships / Learn. **No** full contacts. |
| About | Complete **read-only** supported record (same mapping as Edit, minus Advanced writes). Footer → `/people/{id}/edit`. |
| Profile (Edit) | Image, full/display name, nicknames, birth/death + precision, notes, email/phone, important places. |
| Relationships | Parents, Siblings, Spouse or partner, Children, Other family. One taught side; `INVERSE_ROLE` maintains the other. Marriage shared event. |
| Identity and Sources | Canonical MB Person vs linked Immich/provider rows, confirmation, provenance. Immich is not SoT. |
| Advanced | Reject mapping, merge, teach/confirm face, repair map/reconcile, “I am this person”. Confirm destructive. |
| Out | Delete Person, Immich silent write, Immich sync UI, I5 gallery reopen, I10A.2 recorder, `people.notes` unused column, curator identity card |

Reuse Existing APIs. Do not fork a second person model.

---

## D. Constraints and honesty

- **Dates:** Header, About, and Edit must honor **precision** (year / month / day / unknown). Schema today is a required `DATE` — I10A.1 **Required** to persist precision (I10B-style) so a year-only fact is not stored or shown as a fake day. Unknown remains no fact (or an explicit unknown), never a silent `YYYY-01-01`.
- **Phone:** digits-only store; show a readable format.
- **Owner:** if `MEMORYBOX_OWNER_PERSON_ID` is set, UI cannot override env — say so.
- **Merged_away:** not editable; follow survivor.
- **Ambiguous Immich→MB teach:** 409 / owner resolve; do not silently create a second person.
- **Theme:** lock `html[data-mb-surface]` tokens (I10B card-paper defect).
- **Typeahead:** I10A `person-typeahead` for relationship/marriage/merge targets — not a dump of every name.

---

## E. Build plan (implementation next; contract and prove already updated)

1. Copy Person Edit PNG into `MBUX Person Screens/`.
2. Explorer: one enriched header; hide curator; labeled life vs result range vs kind totals; About / Edit / Relationships / Learn.
3. `GET /people/{id}/edit` + chrome; load current person; sticky footer.
4. About = complete read-only; footer and **Edit** → same path.
5. Profile writes (name, facts + precision, aliases, contacts).
6. Relationships groups + marriage; inverses via Existing service.
7. Identity read + Advanced actions with confirm.
8. Green `prove-person-i10a1` (+ FlightSim D2/D3).

---

## F. Open questions (remaining)

1. **Closed:** Date precision is **Required** (display + persist).  
2. Important places: honest omit until a person↔`places` link exists, or add that link table in this increment?  
3. Preferred name as its own field? **Recommendation:** one `display_name` + nicknames.  
4. **Closed:** Preferred provider portrait is **in scope**.  
5. **Closed:** Family Edit path is `/people/{id}/edit`.

---

**PRD ACCEPTED and amended. Implement against the screen contract. Do not ship Explorer chrome that still duplicates the curator card or routes Edit through About.**
