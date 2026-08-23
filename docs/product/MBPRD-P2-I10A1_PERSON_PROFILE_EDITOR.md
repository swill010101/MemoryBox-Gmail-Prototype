# MBPRD-P2-I10A.1 — Person Profile and Editor

**Status:** PRD **revised after repository assessment** · **not accepted** · increment **not build-authorized**  
**Date:** 2026-08-23  
**Increment definition:** [MBBS-P2_INCREMENT_10A1_DEFINITION.md](MBBS-P2_INCREMENT_10A1_DEFINITION.md)  
**Assessment:** [MBAS-P2-I10A1_ASSESSMENT_RECONCILIATION.md](MBAS-P2-I10A1_ASSESSMENT_RECONCILIATION.md)

**Visual baseline:** `MBUX-Person-Edit-v1.png` on `fe913a4` (`cursor/marvin-capture-v01-3344`) in `docs/source/Screens/MBUX Story Screens/`. Copy to `docs/source/Screens/MBUX Person Screens/` before implementation. Pixels lose to Frozen rows.

**Depends:** I1–I8A **ACCEPTED** · I5 **ACCEPTED** · I6 **ACCEPTED** · I10A **ACCEPTED** · I10B **ACCEPTED** 2026-08-23 · profile APIs in `memorybox/app.py` / `memorybox/profile/` / `memorybox/person/`

**Does not start:** I10A.2 · I10C · I11 · I8.5 · Immich write-back · I5 timeline/gallery rebuild

**Increment ID:** **P2-I10A.1 — Person Profile and Editor.** Not I5. Does not reopen I5.

**Legend:** **Frozen** · **Existing** · **Required** · **Recommendation** · **Open**

---

## Frozen product decisions

Owner 2026-08-23.

1. Person Explorer remains **concise and memory-focused**. Do not put the entire person record on it.
2. **About / Details** may open the **existing informational panel**.
3. That panel is **read-only** and is **not** the editor.
4. The action at the **bottom of the panel** opens the **full Person Profile/Editor** for the **currently selected** person.
5. Any Explorer control **labeled Edit** **bypasses** the panel and opens the **same** full editor.
6. **No additional person-selection step.** Person and current data are already loaded.
7. The full profile/editor is **authoritative** for viewing and editing the complete person record.
8. MemoryBox corrections **must not silently write changes back to Immich**.
9. MemoryBox Person is canonical. Immich / HVRT people are **provider identities**.
10. Taught vs Derived kinship stays I6: editor writes taught assertions only; Derived is read-only and labeled.
11. Advanced identity tools (reject, merge, teach, repair, “I am this person”) live on the full editor in a **separated** section. They must not visually compete with ordinary profile editing.
12. No Person working draft. Save writes. Cancel/Back without Save writes nothing.

---

## Problem and success

**Problem:** Explorer is the family home. The complete record and all admin repairs live on `/people/ui?admin=1`, or are misrouted (header **Edit** opens the About drawer). Families cannot see or correct the full person without leaving the product path.

**Success**

- About/Details → read-only panel only.
- Panel footer → full editor, same `person` id, no picker.
- **Edit** → full editor directly.
- Full screen shows Profile, Relationships (grouped), Identity and Sources, Advanced.
- Rename, facts, contacts, relationships do not call Immich update APIs.
- FlightSim: open a person, Edit, change display name, reload Explorer header — MB name changed; Immich person name unchanged.

---

## A. Surfaces and navigation

### Person Explorer — **Existing**, stay concise

**Required** header/curator only: portrait, `display_name`, owner-relative kinship, life years, memory summary, gallery (I5).

| Control | Today | I10A.1 |
|---|---|---|
| **About** / **Details** / **View / Edit details** | Opens `#mb-person-drawer` | **Keep panel.** Relabel if needed so it is not “Edit”. |
| Drawer body | Read-only from cached `/people/{id}/profile` | **Keep read-only.** Do not add the full record. |
| Drawer footer | “Open full profile editor” → `?admin=1` | **Required:** same label or “Open full profile” → **new editor**, current person. |
| Header **Edit** (`#mb-person-edit`) | `preventDefault` + About drawer | **Required:** navigate to full editor. **Do not** open the panel. |

### Informational panel — **Existing** read-only

Shows a **subset**: name, aliases, birth/death, family names+roles, contacts, places **placeholder**, notes. Not authoritative. Not editable.

### Full Person Profile/Editor — **Required** new surface

**Recommendation:** `GET /people/ui?person={id}&edit=1` (reuse `people_ui()`). I10A/I10B dark chrome, sticky Cancel / Save.

Boot: use `person` from the URL (already selected). `GET /people/{id}` + `GET /people/{id}/profile` + `GET /people/{id}/portrait` + `GET /people/{id}/provider-projection`. No `picker-options` / `ensure` step on this path.

`?admin=1` is **not** the family Edit URL.

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

Every displayed or editable field and every action. **Existing source** is the repository as of I10B ACCEPTED.

| Screen section | UI label | Existing source | Write / action | I10A.1 |
|---|---|---|---|---|
| Explorer header | Portrait | `GET /people/{id}/portrait` · Immich preferred thumb when mapped (`fetch_person_portrait_bytes`) | None (display) | Keep on Explorer |
| Explorer header | Name | `people.display_name` via `GET /people/{id}` | None | Keep |
| Explorer header | Subline | Derived kinship to owner + birth/death years from facts | None | Keep |
| Explorer header | Memory summary | Explore find meta | None | Keep |
| Explorer | **Edit** | `#mb-person-edit` → **wrongly** About drawer | Navigate to full editor | **Required** fix |
| Explorer footer | View / Edit details | `#mb-person-about-edit` → About drawer | Open **panel** | Relabel to About/Details if it still says Edit |
| Panel | Full name | Cached profile / `display_name` | Read-only | Keep concise |
| Panel | Also known as | `person_aliases` | Read-only | Keep |
| Panel | Born / Died | `person_facts` `value_date` | Read-only | Keep; “Not recorded” if absent |
| Panel | Family | Cached family name + role | Read-only | Keep concise |
| Panel | Confirmed contacts | `person_contact_points` | Read-only | Keep |
| Panel | Places | **Hard-coded placeholder** — no table | None | Honest empty or same placeholder |
| Panel | Notes | `person_facts` `note` kind | Read-only | Keep |
| Panel footer | Open full profile / editor | Today `adminHref()` `?admin=1` | Open full editor, same id | **Required** |
| Profile | Profile image | Same portrait endpoint | Display only this increment unless Open portrait absorb | **Required** display |
| Profile | Full name / Display name | `people.display_name` | `POST /people/{id}/name` → `rename_person` (**MB `people` only**) | **Required** |
| Profile | Preferred name | **No column** — same as display name | — | **Recommendation:** do not add a column; nicknames cover “also called” |
| Profile | Nickname | `person_aliases` `nickname` | `POST /people/{id}/aliases` | **Required** |
| Profile | Other name | `person_aliases` `alternate_name` | Same | **Required** |
| Profile | Birth | `person_facts` `birth_date` + `value_date` | `POST /people/{id}/facts` (replaces prior birth) | **Required**. Unknown = no row |
| Profile | Death | `person_facts` `death_date` | Same | **Required** |
| Profile | Partial date | **Not in schema** (`DATE` + `parse_date` ISO day) | — | **Open** (see below) |
| Profile | Fact note | `person_facts.note` and/or `fact_kind=note` `value_text` | `POST /people/{id}/facts` | **Required** (notes as today) |
| Profile | Email | `person_contact_points` `email` | POST contacts; correct via `POST /people/contacts/{id}/supersede` | **Required** |
| Profile | Phone | `phone` · 10-digit persist | Same | **Required** |
| Profile | Important places | **None** | — | **Open**. Do not invent lat/long. If in, reuse I10 `places` + new link table |
| Relationships | Parents / Siblings / Spouse or partner / Children / Other | `get_person_profile().relationships` assertions + kinship `direct` / `extended` | Add: `POST /people/relationships`. Change: `…/supersede`. Remove: `…/withdraw` | **Required** taught; Derived read-only |
| Relationships | Inverse | `INVERSE_ROLE` in `memorybox/profile/owner.py`; projection in `relationships.py` | Service-maintained | **Required** — one user entry |
| Relationships | Wedding / anniversary | `shared_life_events` + participants | `POST /people/life-events/marriage` | **Required** |
| Identity | MB Person id | `people.id` | None | **Required** read |
| Identity | Person status | `people.status` | None (except merge) | **Required** read |
| Identity | Identity authority | `people.attributes_json.identity_authority` | Set by teach/map | **Required** read |
| Identity | Linked Immich / provider | `provider_identities` · `GET /people/{id}/provider-projection` | None here | **Required** read |
| Identity | Confirmation | `confirmed_at`, `confirmed_by` | Teach/map | **Required** read |
| Identity | Provenance | `provenance_json`, `assertions` | Written by existing services | **Required** disclose; no history browser |
| Advanced | Reject incorrect mapping | `POST /people/reject` → `reject_mapping` (detach + `identity_negatives`) | MB only | **Required** |
| Advanced | Merge duplicates | `POST /people/merge` → `merge_people` | Survivor kept; loser `merged_away` | **Required** |
| Advanced | Teach / confirm face | `POST /people/teach` · Learn/Review recognition | Maps provider → MB | **Required** in Advanced |
| Advanced | Repair mapping | `POST /people/{id}/map`, `POST /people/{id}/reconcile` | MB only | **Required** |
| Advanced | I am this person | `GET/POST /people/owner` · setting `owner_person_id` | MB runtime (+ env override) | **Required** |
| — | Immich person name / faces | Immich API | **Forbidden silent write** | **Frozen** |
| — | Delete Person | **No API** | — | **Out** |
| — | Delete fact/alias | **No API** (supersede/replace only) | — | **Out** unless Open later |
| — | Immich sync run | `POST /people/sync/immich` | Operator | **Out** of family editor |
| — | I5 Highlights / Timeline / Map / Learn boxing | Explorer | — | **Out** |
| — | I10A.2 recorder | — | — | **Out** |

---

## D. Constraints and honesty

- **Dates:** birth/death need a full calendar day or be absent. Admin `mm-dd-yyyy` still becomes `DATE`. “Unknown” is no fact. Year-only is **not Existing**.
- **Phone:** digits-only store; show a readable format.
- **Owner:** if `MEMORYBOX_OWNER_PERSON_ID` is set, UI cannot override env — say so.
- **Merged_away:** not editable; follow survivor.
- **Ambiguous Immich→MB teach:** 409 / owner resolve; do not silently create a second person.
- **Theme:** lock `html[data-mb-surface]` tokens (I10B card-paper defect).
- **Typeahead:** I10A `person-typeahead` for relationship/marriage/merge targets — not a dump of every name.

---

## E. Build plan (after sign-off only)

1. Copy Person Edit PNG into `MBUX Person Screens/`.
2. Editor route + chrome; load current person; sticky footer.
3. Fix Explorer **Edit** vs About/Details vs panel footer (Frozen navigation).
4. Profile writes (name, facts, aliases, contacts).
5. Relationships groups + marriage; inverses via Existing service.
6. Identity read + Advanced actions with confirm.
7. Prove: nav paths; no Immich write on rename; merge/reject stay MB-only; cancel no-write.

---

## F. Open questions

1. Partial dates this increment (precision like I10B) or keep day-or-unknown?  
2. Important places: honest empty, or I10 `places` link table now?  
3. Preferred name as its own field?  
4. Absorb **P2-BL-I5-01** (preferred Immich portrait) in this increment?  
5. Confirm `edit=1` on `/people/ui` vs a dedicated path.

---

**This PRD is for product-owner review. It is not accepted and not build-authorized. Do not implement until Tom says Approved to build.**
