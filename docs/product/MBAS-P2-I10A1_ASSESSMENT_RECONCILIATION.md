# P2-I10A.1 — Assessment reconciliation

**Status:** Repository assessment **2026-08-23** · PRD **ACCEPTED** (Explorer amendment) · chrome not yet implemented  
**Does not implement** code, migrations, routes, templates, APIs, or tests  
**Definition / PRD / map / contract:** [MBBS-P2_INCREMENT_10A1_DEFINITION.md](MBBS-P2_INCREMENT_10A1_DEFINITION.md) · [MBPRD-P2-I10A1_PERSON_PROFILE_EDITOR.md](MBPRD-P2-I10A1_PERSON_PROFILE_EDITOR.md) · [MBAS-P2-I10A1_FIELD_ACTION_MAP.md](MBAS-P2-I10A1_FIELD_ACTION_MAP.md) · [MBSC-P2-I10A1_PERSON_SCREEN_CONTRACT.md](MBSC-P2-I10A1_PERSON_SCREEN_CONTRACT.md) · [MBAT-P2-I10A1_ACCEPTANCE.md](MBAT-P2-I10A1_ACCEPTANCE.md)  
**Base:** `cursor/p2-i10b-artifacts-49da` (I10B **ACCEPTED** 2026-08-23)

This revises the first I10A.1 PRD after owner navigation lock. Screenshot text is still not proof of a backend field. Immich people are provider identities, not MemoryBox SoT.

**Visuals cited:** Person Edit PNG on `fe913a4` (`cursor/marvin-capture-v01-3344`) under `docs/source/Screens/MBUX Story Screens/` (`MBUX-Person-Edit-v1.png`). **Not present** on this checkout. Copy into `docs/source/Screens/MBUX Person Screens/` before build.

---

## Frozen navigation (owner 2026-08-23)

Person Explorer stays a **concise, memory-focused** screen. Do not add the entire person record to it.

| # | Rule |
|---|---|
| 1 | `About` / `Details` may open the **existing concise informational panel**. |
| 2 | That panel is **read-only** and is **not** the editor. |
| 3 | The action at the **bottom of that panel** opens the **full Person Profile/Editor** for the **currently selected** person. |
| 4 | Any Explorer control **explicitly labeled Edit** **bypasses** the informational panel and opens the same full editor. |
| 5 | **No extra person-selection step.** Selected person and current data are already loaded. |
| 6 | The full profile/editor is the **authoritative** place to view and edit the complete person record. |
| 7 | MemoryBox corrections **must not silently write back to Immich**. |

**Amended:** the informational panel is no longer a short teaser. **About** is the complete **read-only** supported record (inspect, then decide). It still **must not sit in the Edit path**. The Explorer **header** stays a summary and must not duplicate a second identity card below Ask.

---

## 1. What the repository actually is

### Person Explorer (I5) — stay concise

| Item | Evidence |
|---|---|
| Route | `GET /people/ui` → `people_ui()` in `memorybox/app.py`. Serves `person-explore.html` when `person` / `person_id` is set (or owner default). `pick=1` → picker. `admin=1` → `people.html`. |
| Selection | Query `person` / `person_id` / `person_name`. Boot: `window.MB_PERSON_SURFACE` in `person-explore.html`. Shell `mb_active_person`. |
| Header | Portrait (`GET /people/{id}/portrait`), `display_name`, kinship-to-owner + life span, memory count. `person-explore.js` `loadProfile()`. |
| Memories | Shared Explore find: `GET /explore/api/find` via `explore.js`. |
| About / Details | Drawer `#mb-person-drawer`. `renderAboutDrawer()` reads **cached** `GET /people/{id}/profile` plus family list. **Read-only HTML.** |
| Drawer contents | Identity (name, aliases), Life (birth/death dates), Family (name + role), Confirmed contacts, **Places placeholder** (no data), Notes. |
| Footer today | “Open full profile editor” → `/people/ui?admin=1&person={id}` (`adminHref()`). |
| **Edit today (bug vs lock)** | Header `#mb-person-edit` is labeled **Edit** but `onclick` **opens the About drawer** and `preventDefault`s the admin href. That **violates** Frozen #4. |

### Informational panel vs editor (today)

| Surface | Role today | I10A.1 required |
|---|---|---|
| About drawer | Read-only summary; Edit incorrectly opens it | Keep read-only. Bottom action → **new editor**, not `?admin=1`. |
| Header **Edit** | Opens drawer | Must **skip drawer** → full editor, same person. |
| Footer **View / Edit details** | Opens drawer | Treat as **About/Details** (panel), not Edit. |
| `?admin=1` `people.html` | Full operational form + owner/merge/reject/teach | **Not** the family product path. Capability moves into the new full screen (Profile / Relationships / Identity / Advanced). |

### Admin editor (`people.html` + `?admin=1`)

All of these exist as UI + API except as noted in §3.

Who am I (owner picker), Open a person (MB + Immich picker via `POST /people/ensure`), facts, aliases, contacts (+ supersede), taught relationships, marriage, rename, reject Immich match, merge people, teach Immich face.

**Not on admin page but APIs exist:** withdraw/supersede relationship (Explorer I6 modal), `POST /people/{id}/map`, `POST /people/{id}/reconcile`, Immich sync.

**No API:** delete/withdraw fact or alias (birth/death **replace** by adding a new fact; contacts **supersede**).

### Canonical identity

- **SoT person:** `people.id`. Status `unresolved` \| `confirmed` \| `merged_away`.
- **Display name:** `people.display_name` via `rename_person()` — **MB only**.
- **Provider:** `provider_identities` (`provider_key`, `external_id`, `confirmed_at` / `confirmed_by`).
- **Reject:** `identity_negatives` + detach mapping. **Does not call Immich to rename or unassign faces.**
- **Teach:** `teach_provider_person()` maps Immich → MB. Does not PATCH Immich person name.
- **Owner:** `memorybox_runtime_settings.owner_person_id` and/or `MEMORYBOX_OWNER_PERSON_ID` (env **wins**).

**Frozen #7 is already true for existing write paths inspected** (`rename_person`, facts/aliases/contacts, relationships, marriage, reject, merge, set owner). I10A.1 must **keep** that: no Immich person-update, no silent face rewrite.

---

## 2. Capability reconciliation (admin → I10A.1)

| Admin / asked capability | Existing source | I10A.1 home | Gap |
|---|---|---|---|
| Full / display name | `people.display_name` · `POST /people/{id}/name` | Profile | None |
| Preferred / display name | **Same column** — no separate preferred-name field | Profile | **Open:** nickname as “preferred” vs one name |
| Alternate names / nicknames | `person_aliases` `nickname` \| `alternate_name` · `POST /people/{id}/aliases` | Profile | No withdraw API |
| Birth / death | `person_facts` `birth_date` / `death_date` · `value_date DATE` required · `POST /people/{id}/facts` | Profile | **Unknown** = no row. **Partial dates not stored** (`parse_date` requires `YYYY-MM-DD`) |
| Notes on facts | `person_facts.note` + `fact_kind=note` `value_text` | Profile | Admin “note text” is `value_text` for notes, not `note` on birth |
| Email / phone | `person_contact_points` · add + `POST /people/contacts/{id}/supersede` | Profile | No hard-delete |
| Important places | About drawer **placeholder only**. No `person_places` table | Profile (display) | **No SoT.** Do not invent GIS. **Open** whether to add I10 `places` links |
| Taught family + inverse | `person_relationship_assertions` · `INVERSE_ROLE` in `profile/owner.py` · `POST /people/relationships` | Relationships | User enters **one** side; projection shows inverse. Withdraw/supersede exist |
| Marriage / anniversary | `shared_life_events` `marriage` · `POST /people/life-events/marriage` | Relationships | One date, two participants |
| Owner “I am this person” | `GET/POST /people/owner` | **Advanced** | Env override if `MEMORYBOX_OWNER_PERSON_ID` set |
| Correct displayed name | Same as rename | Profile | MB only |
| MB ↔ Immich mapping | `provider_identities` · profile + `GET /people/{id}/provider-projection` | Identity and Sources | Read |
| Reject wrong photo/person | `POST /people/reject` | Advanced | MB negative only |
| Teach / confirm face | `POST /people/teach` (+ Learn/Review recognition) | Advanced | Do not write Immich |
| Merge duplicate MB people | `POST /people/merge` · loser `merged_away` | Advanced | Destructive; confirm |
| Provenance / confirmation | `status`, `actor_key`, `provenance_json`, `confirmed_at`, `assertions` | Identity (read) · writes keep provenance | No family “history browser” required |
| Delete / unlink / archive person | No person-delete API. Mapping unlink = reject. Merge = archive loser | Advanced (reject/merge only) | No GC |
| Repair mapping | `POST /people/{id}/map`, `reconcile` | Advanced | No admin UI today |

### Explorer concise info (must stay on Explorer)

`loadProfile()` in `person-explore.js` loads `GET /people/{id}` + `GET /people/{id}/profile` (+ portrait, Learn extras). Header: portrait, `display_name`, owner-relative derived role + birth/death years. About **card** (`#mb-person-about-dl`): name, relationship, born/died, confirmed phone/email only. Family **strip**: up to eight names from assertions + derived. Gallery via Explore find.

**Not** on Explorer: full aliases list, mappings, merge, owner, places SoT, complete contact editor.

**Also today (defects vs lock, besides header Edit):** footer **View / Edit details** is About/Details but labeled Edit. **+ Add family** jumps to `?admin=1#relationships` instead of the I6 modal or the new editor. Header **Relationships** opens the concise family drawer, not the admin form.

The I6 relationships modal (`person-relationships.js`) already teaches one side and withdraws/supersedes. Keep it on Explorer. The full editor Relationships section is the authoritative grouped view.

---

## 3. UX structure (assessed)

Follow I10A/I10B dark chrome (`data-mb-surface` token lock so shell paper cannot paint light cards).

**Frozen:** `/people/{id}/edit`. Server already has the person. **No picker.** Load `GET /people/{id}/profile` (+ provider projection). Same mapping as About and the Explorer header summary.

| Region | Purpose |
|---|---|
| **Profile** | Image (display), full/display name, aliases, birth/death, notes, contacts, important places (honest empty if no SoT) |
| **Relationships** | Groups: Parents, Siblings, Spouse/partner, Children, Other. Taught editable; Derived read-only. Inverse maintained in service |
| **Identity and Sources** | Canonical MB Person id/status; linked Immich/provider rows; confirmation; provenance. Not editable as if Immich were SoT |
| **Advanced identity tools** | Visually separated: reject mapping, merge, teach/confirm face, repair map/reconcile, “I am this person”. Must not compete with Profile |

Save writes immediately (no Person working draft). Cancel/Back with no save writes nothing.

---

## 4. Prior PRD corrections

The 2026-08-23 first PRD parked merge/reject/teach/owner on `?admin=1`. **Superseded:** those belong on the **full editor Advanced** section. `?admin=1` is no longer the family destination.

Header Edit opening the About drawer is a **defect to fix in I10A.1**, not a product pattern to keep.

---

## 5. Boundary

### Required for I10A.1

Navigation lock; full editor chrome; Profile + Relationships + Identity + Advanced; reuse existing APIs; no Immich write-back; Explorer stays memory-first; panel stays read-only.

### Out

I5 gallery/timeline reopen · I6 new inference · I10A.2 mic · I10C · I11 · I8.5 Face SoT · person file GC · inventing person GIS · silent Immich PATCH

---

## Open (do not block writing the definition)

1. **Closed:** persist and display date precision (not a fake day).  
2. Important places: leave honest-omit, or add `person_id`↔`places.id` this increment?  
3. Preferred name: alias only, or new column? **Recommendation:** one `display_name` + nicknames.  
4. **Closed:** `/people/{id}/edit`. Preferred portrait in scope.
