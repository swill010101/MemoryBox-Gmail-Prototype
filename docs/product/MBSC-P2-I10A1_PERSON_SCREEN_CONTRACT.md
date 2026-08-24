# MBSC-P2-I10A.1 — Person Explorer, About, and Editor screen contract

**Status:** **LOCKED** with implementation **ACCEPTED** 2026-08-24. Do not reopen I10A.1 for polish.  
**PRD:** [MBPRD-P2-I10A1_PERSON_PROFILE_EDITOR.md](MBPRD-P2-I10A1_PERSON_PROFILE_EDITOR.md)  
**Field map:** [MBAS-P2-I10A1_FIELD_ACTION_MAP.md](MBAS-P2-I10A1_FIELD_ACTION_MAP.md)  
**Acceptance:** [MBAT-P2-I10A1_ACCEPTANCE.md](MBAT-P2-I10A1_ACCEPTANCE.md) · `python -m memorybox prove-person-i10a1`

About, Explorer header, and Edit **share** the same field mapping, SoT, date precision, provenance, and relationship interpretation. They differ only in **how much is always visible** and **whether the user can write**.

---

## Three layers (Frozen)

| Layer | Role | Always on Explorer? | Writable? |
|---|---|---|---|
| **Enriched Person header** | Useful summary | Yes, **one** card **above** Ask | No |
| **About** | Complete **read-only** supported person record | No — opens on **About** | No |
| **Edit** | Complete **writable** record | No — `/people/{id}/edit` | Yes |

Do **not** put every profile field permanently on the Explorer. Do **not** show full contact values in always-visible chrome (header **or** the footer About summary card).

---

## S.1 Person Explorer

**Keep** I5 gallery, Ask, filters, timeline, map. **Do not** rebuild those. **Do** remove identity duplication.

### S.1.1 One header above Ask

Remove the second portrait/name identity card below Ask (`#mb-explore-curator` on the Person surface). Move any useful result counts from it into the enriched header **or** a compact result summary **above the filters**.

The single header **must** show:

| Slot | Rule | Source |
|---|---|---|
| Preferred provider portrait | Immich/provider preferred face when mapped; letter if none. Do not race a random face crop. | `GET /people/{id}/portrait` (P2-BL-I5-01 absorbed) |
| Full / display name | Canonical `people.display_name` | `GET /people/{id}` |
| Also known as | First nickname or alternate **when present**; omit if none | `person_aliases` via profile |
| Life dates | Labeled **Born** / **Died** (or Life). Honor date **precision** (year / month / day / unknown). Omit a side that is unknown. | `person_facts` birth/death + precision |
| Relationship to owner | When known; omit if unknown | Derived kinship vs owner |
| Primary / important place | When available; omit if none. No invented lat/long. | Person–place SoT when it exists |
| Memory totals by kind | **Labeled** counts for supported kinds (photos, video, stories, communications, artifacts, …) plus a **Total memories** figure | Explore find / current person corpus |
| Actions | **About** · **Edit** · **Relationships** · **Learn** | See S.1.3 |

### S.1.2 Date and count honesty (Frozen)

Never show an **unlabeled** media or result date range where it can be read as the person’s lifespan.

Each visible date or count must be distinguishable:

| Kind | Label example | Must not look like |
|---|---|---|
| Person life dates | Born 1927 · Died 2004, or Born Jun 1927 | A gallery span |
| Current result / media date range | Results 1998–2010, or In this view: 1998–2010 | Born/Died |
| Total memories | 142 memories (person corpus or current Ask, labeled) | A year span |
| Counts by kind | 80 photos · 12 videos · 4 stories · … | An unlabeled pile of numbers |

Life dates live only in the life-date slot. Result range lives in the compact result summary (header or above filters), **labeled**.

### S.1.3 Actions

| Control | Target |
|---|---|
| **About** | `/people/{id}/edit?view=1` — same structured Person Profile, **read-only**, with an **Edit** button. Not a text-string drawer. |
| **Edit** | `/people/{id}/edit` for the **already selected** person. **Bypasses** view mode. No picker. |
| **Relationships** | Existing I6 relationships modal / family drawer on Explorer (taught add stays here). Not the admin form. |
| **Learn** | Existing Learn drawer. Teach/confirm face remains **Advanced** on Edit. |

Do not label About as View / Edit details. Do not open About from a control labeled **Edit**.

### S.1.4 Always-visible chrome must not include

- Full email / phone list (About only)
- Provider mapping table, merge, reject, owner setter (Identity / Advanced on Edit; About may **read** confirmation/provenance)
- Second portrait + name block below Ask

Footer Family strip and Learn stats may remain as I5 context. Family chips show the **preferred provider portrait** and the **kinship label** (Father, Spouse, Son — not the word “family”). The footer About **card** is a structured card (relationship, born, died) — not a sentence — and opens the Profile in view mode. No contacts on the card.

---

## S.2 About (complete read-only)

Opens from header **About** as **`/people/{id}/edit?view=1`**. Same I10A/I10B structured screen as Edit (cards, not a drawer paragraph). Fields are read-only. An **Edit** button on that screen drops `view=1` and enters edit mode. Explorer **Edit** still goes straight to `/people/{id}/edit`.

**Must include** the supported person record so the family can inspect and decide whether to correct:

- Identity: full/display name, alternate names / nicknames
- Life facts (birth/death with precision) and notes
- Family relationships (same grouping and Taught vs Derived rules as Edit)
- Confirmed contacts (email / phone)
- Important places (honest empty if no SoT)
- Relevant provenance and confirmation status (MB Person status, mapping confirmation — **read**)

Footer action: **Edit** / Open full profile → `/people/{id}/edit` for the same person.

About does **not** run reject, merge, teach, map, reconcile, or “I am this person”. Those stay on Edit → Advanced.

---

## S.3 Edit — `/people/{id}/edit`

Authoritative writable record. I10A/I10B dark chrome. Sticky Cancel / Save. No Person draft. No second person-selection step. Boot from `{id}` already on the Explorer.

Regions: **Profile · Relationships · Identity and Sources · Advanced** (see PRD). `?admin=1` `people.html` is not the family Edit URL.

**Keep Relationships on Edit.** Explorer **Relationships** is the I6 gallery modal (quick teach over memories). Edit **Relationships** is the full grouped record (Parents / Siblings / Spouse / Children / Other + marriage). They are different jobs — do not remove the Edit section.

MemoryBox writes stay in MemoryBox. No silent Immich person or face write-back.

---

## S.4 Shared interpretation (Frozen)

| Topic | Rule |
|---|---|
| Canonical person | `people.id`. Immich rows are provider identities. |
| Display name | `people.display_name`. Header, About, and Edit show the same value. |
| Date precision | Header, About, and Edit format the same fact the same way. Unknown is absent, not a fake day. |
| Relationships | One taught assertion; `INVERSE_ROLE` maintains the inverse. Derived labeled Derived. |
| Provenance | Same `provenance_json` / confirmation fields. About discloses; Edit writes through existing services. |
| Places | Same SoT (or honest empty) in header (when present), About, and Edit. |
| Contacts | Same `person_contact_points`. Header omits values. About reads. Edit writes. |
