# P2-I10A.1 — Field and action mapping

**Status:** Planning only · repository traced **2026-08-23** on `cursor/p2-i10b-artifacts-49da` (I10B **ACCEPTED**)  
**Not build-authorized.** Does not implement code.  
**PRD:** [MBPRD-P2-I10A1_PERSON_PROFILE_EDITOR.md](MBPRD-P2-I10A1_PERSON_PROFILE_EDITOR.md)  
**Assessment:** [MBAS-P2-I10A1_ASSESSMENT_RECONCILIATION.md](MBAS-P2-I10A1_ASSESSMENT_RECONCILIATION.md)

Every displayed or editable field and every action for I10A.1. **Existing source** is the current repository, not a screenshot.

**Columns**

| Column | Meaning |
|---|---|
| Screen section | Explorer, Informational panel, Profile, Relationships, Identity and Sources, Advanced, or Out |
| UI label | Family-facing label to use (today’s admin/Explorer wording in parentheses when different) |
| Existing source | Route / service / table / column / UI file that already supplies or writes it |
| Write / action | How it changes, or Display only |
| Immich write | Whether today’s path writes Immich (must stay **No**) |
| I10A.1 | Required / Keep / Relabel / Open / Out |

---

## 0. Navigation (Frozen)

| Screen section | UI label | Existing source | Write / action | Immich write | I10A.1 |
|---|---|---|---|---|---|
| Explorer header | **About** | Missing as a labeled header action. Footer **View / Edit details** opens drawer | Open **complete** read-only About | No | **Required** `#mb-person-about` |
| Explorer header | **Edit** | `#mb-person-edit` · `adminHref()` then `preventDefault` + `renderAboutDrawer()` | `GET /people/{id}/edit`. **Bypass** About. | No | **Required** fix |
| Explorer footer About card | **View / Edit details** | `#mb-person-about-edit` → drawer | Remove this label. About lives on the header. | No | **Required** remove |
| About footer | **Edit** / Open full profile | `#mb-person-drawer-admin` · `adminHref()` | Same `/people/{id}/edit` | No | **Required** retarget |
| Explorer | Curator card below Ask | `#mb-explore-curator` (portrait, title, body — duplicates header) | Remove or hide on Person surface | No | **Required** |
| Explorer header | Relationships | `#mb-person-relationships` → `renderFamilyDrawer()` | Concise family drawer (not the editor) | No | Keep on Explorer |
| Explorer Family card | View relationships | `#mb-person-family-open` → `renderFamilyDrawer()` | Same drawer | No | Keep |
| Explorer Family card | + Add family | `#mb-person-family-add` → `adminHref()+'#relationships'` | Today leaves Explorer for admin | No | **Required:** stay on Explorer I6 modal **or** open full editor Relationships for current person — **not** admin picker. **Recommendation:** I6 modal on Explorer; full groups live on the editor |
| Explorer header / Learn card | Learn / Explore | `#mb-person-learn-link`, `#mb-person-learn-explore` → `renderLearnDrawer()` | Face/appearance summary drawer | No | Keep on Explorer. Teach/confirm face is **Advanced**, not this drawer |
| I6 modal | Add / withdraw / supersede relationship | `person-relationships.js` + `POST /people/relationships` (+ withdraw/supersede) | Taught assertion only | No | Keep on Explorer. Same APIs as editor Relationships |
| Full editor | Cancel / Back | None on `people.html` (admin is a long form) | Leave without write if nothing Saved | No | **Required** sticky chrome |
| Full editor | Save | Per-section buttons on `people.html` | Immediate writes; no Person draft | No | **Required** |

`GET /people/ui` (`people_ui()` in `memorybox/app.py`): Explorer when `person` / `person_id` set (or owner default). `pick=1` picker. `admin=1` → `people.html`. **Frozen:** family editor = `GET /people/{id}/edit`. `?admin=1` is not the family Edit URL.

---

## 1. Person Explorer — concise, memory-focused (do not expand)

How the Explorer **obtains** concise information: `loadProfile()` in `person-explore.js` parallel-fetches `GET /people/{id}`, `GET /people/{id}/profile` (`get_person_profile()` in `memorybox/profile/ask_resolve.py`), portrait URL, plus Learn extras (`face-evidence`, `appearances`, `learn-stats`). Gallery is `GET /explore/api/find` via `explore.js`.

| Screen section | UI label | Existing source | Write / action | Immich write | I10A.1 |
|---|---|---|---|---|---|
| Explorer header | Preferred provider portrait | `GET /people/{id}/portrait` | Display. Letter if none | No | **Required** (absorbs P2-BL-I5-01) |
| Explorer header | Full / display name | `people.display_name` via `GET /people/{id}` | Display | No | **Required** |
| Explorer header | Also known as | `person_aliases` (omit if none) | Display | No | **Required** when present |
| Explorer header | Born / Died (precision) | `person_facts` + **Required** precision | Display, labeled life dates | No | **Required**. Not a result range |
| Explorer header | Relationship to owner | Derived edges vs `owner_person_id` | Display when known | No | **Required** when known |
| Explorer header | Primary / important place | **No person–place SoT today** | Display when available | No | Omit if none |
| Explorer header | Memory totals by kind | Explore find / meta (today a prose `#mb-person-summary`) | Labeled kind counts + total | No | **Required** |
| Explorer header | Result / media range | Timeline / find span (today can look like years in curator) | Labeled “In this view” / Results | No | **Required** if shown |
| Explorer About card | Contacts | `#mb-person-about-dl` + JS `Confirmed phone/email` | Must **leave** always-visible chrome | No | **Required** remove from card |
| Explorer Family strip | First name + role (max 8) | `assertions_sot` + `derived_edges`; other party id/name | Navigate to that person’s Explorer | No | Keep strip |
| Explorer | Highlights / All Memories / Gallery / Map / Timeline / Ask | I5 Explore | Memory find | No | **Out** of I10A.1 (do not reopen I5) |
| Explorer | People (picker) | `/people/ui?pick=1` | Change person | No | Keep. **Not** used when opening the editor from a selected person |

---

## 2. About panel — complete read-only, not the editor

Today `renderAboutDrawer()` is a **subset** from cached `GET /people/{id}/profile`. I10A.1 **Required:** expand to the **complete supported record** (same fields as Edit Profile + Relationships + Identity read). Still no POST. Not Advanced writes.

| Screen section | UI label | Existing source | Write / action | Immich write | I10A.1 |
|---|---|---|---|---|---|
| Panel · Identity | Full name | Cached `cfg.displayName` | Read-only | No | Keep |
| Panel · Identity | Also known as | `profile.aliases` (`alias_text`) | Read-only | No | Keep |
| Panel · Life | Born | `facts` `birth_date.value_date` or “Not recorded” | Read-only | No | Keep |
| Panel · Life | Died | `facts` `death_date.value_date` or “Not recorded” | Read-only | No | Keep |
| Panel · Family | Name — role | `cached.family` | Read-only | No | Keep concise |
| Panel · Confirmed contacts | kind: **value** (confirmed) | `profile.contacts` | Read-only | No | Keep |
| Panel · Places | Important Places… (placeholder) | **Hard-coded string.** No `person_places` table. `people.notes` unused. | None | No | Honest empty or same disclaimer. **Open** SoT |
| Panel · Notes | Note lines | `facts` where `fact_kind=note` (`value_text` or `note`) | Read-only | No | Keep |
| About | Provenance / confirmation | `people.status`, `provider_identities.confirmed_*`, `provenance_json` | Read-only | No | **Required** (inspect before Edit) |
| About | Advanced writes | reject / merge / teach / owner | — | — | **Must not** appear here |

---

## 3. Profile (full editor)

Admin today: `people.html` “Add or update details” + “Fix a name” + profile preview blocks.

| Screen section | UI label | Existing source | Write / action | Immich write | I10A.1 |
|---|---|---|---|---|---|
| Profile | Profile image | Same `GET /people/{id}/portrait` | Display this increment | No | **Required** display |
| Profile | Full name / Display name (admin **Correct spelling**) | `people.display_name` · `POST /people/{id}/name` → `rename_person()` in `memorybox/person/__init__.py` — `UPDATE people SET display_name` only | Save name | **No** (inspected) | **Required** |
| Profile | Preferred / display name | **No preferred-name column.** Same as `display_name` | — | No | **Recommendation:** do not add a column; nicknames = “also called”. **Open** |
| Profile | Nickname (admin **Nickname**) | `person_aliases.alias_kind='nickname'` · `POST /people/{id}/aliases` → `add_alias()` | Add confirmed alias | No | **Required** |
| Profile | Other name (admin **Other name** / alternate) | `person_aliases.alias_kind='alternate_name'` | Same POST | No | **Required** |
| Profile | Alias note | `person_aliases.note` (API accepts `note`) | Optional | No | Keep if shown |
| Profile | Withdraw alias | `person_aliases.status` supports `withdrawn` | **No withdraw API** | No | **Out** unless Open |
| Profile | Birth (admin **Birth date**) | `person_facts` `fact_kind='birth_date'` · `value_date DATE NOT NULL` · CHECK in `005_person_profile_i9a.sql` · `POST /people/{id}/facts` → `add_fact()` supersedes prior confirmed birth | Replace-in-place | No | **Required**. Unknown = no confirmed row |
| Profile | Death | `fact_kind='death_date'` · same | Same | No | **Required** |
| Profile | Partial / unknown date | `parse_date()` requires `YYYY-MM-DD`. Admin UI accepts `mm-dd-yyyy` then sends ISO day | Year-only **not stored** | No | **Open** (precision vs day-or-unknown) |
| Profile | Note on a birth/death fact | `person_facts.note` (column) via POST `note` | Optional on fact | No | **Required** if we keep “notes attached to facts” |
| Profile | Notes (free-form) | `person_facts` `fact_kind='note'` · `value_text` required · admin **Note text (for notes)** | Add note fact | No | **Required** |
| Profile | `people.notes` | Column on `people` in `001_domain_v0.sql` | **No API read/write found** | No | **Out** — do not surface as a second notes field |
| Profile | Email | `person_contact_points` `email` · `POST /people/{id}/contacts` | Add | No | **Required** |
| Profile | Phone | `phone` · persist 10 digits | Add | No | **Required**. Display readable format |
| Profile | Correct contact | `POST /people/contacts/{id}/supersede` | Supersede; no hard-delete | No | **Required** |
| Profile | Important places | **No person↔place table.** I10 `places` exist for other objects. Drawer placeholder only | — | No | **Open**. If in: I10 `places` + new link table. Do not invent lat/long |

---

## 4. Relationships

Taught SoT: `person_relationship_assertions` (`from_person_id` has `role_kind` toward `to_person_id`). Inverse is **derived** (`INVERSE_ROLE` in `memorybox/profile/owner.py`; projection in `relationships.py`). User enters **one** side.

Kinship groups already in `DIRECT_GROUP_ORDER` (`memorybox/profile/kinship.py`): `parents`, `siblings`, `spouse_partner`, `children`. Extended → **Other family**.

| Screen section | UI label | Existing source | Write / action | Immich write | I10A.1 |
|---|---|---|---|---|---|
| Relationships | Parents | Kinship `direct.parents` + taught `father_of` / `mother_of` / `parent_of` / biological / adoptive / step | Add: `POST /people/relationships`. Change: `POST /people/relationships/{id}/supersede`. Remove: `…/withdraw` | No | **Required** taught editable; Derived labeled **Derived** |
| Relationships | Siblings | `direct.siblings` + `sibling_of` + shared-parent derivation | Same writes for taught only | No | **Required** |
| Relationships | Spouse or partner | `direct.spouse_partner` + `spouse_of` / `partner_of` | Same | No | **Required** |
| Relationships | Children | `direct.children` + `child_of` / `son_of` / `daughter_of` (or inverse of parent_of) | Same | No | **Required** |
| Relationships | Other family | `extended` + taught `grandparent_of` / `grandchild_of` / `uncle_of` / `aunt_of` / `nephew_of` / `niece_of` | Taught writable; cousins etc. Derived | No | **Required** |
| Relationships | Inverse (automatic) | `INVERSE_ROLE`: father/mother/parent* → `child_of`; child/son/daughter → `parent_of`; spouse↔spouse; partner↔partner; sibling↔sibling; grandparent↔grandchild; uncle↔nephew; aunt↔niece | Service-maintained. **Do not** ask the user to enter both sides | No | **Required** |
| Relationships | Wedding / anniversary (admin **Wedding / anniversary date**) | `shared_life_events` `event_kind='marriage'` + `shared_life_event_participants` · `POST /people/life-events/marriage` · `event_date DATE` | One shared date, two people | No | **Required** |
| Relationships | How related | `GET /people/relationships/how-related` | Read / Ask | No | **Out** of editor chrome (Ask stays on Explorer) |
| Relationships | Typeahead target | Admin uses `<select>` of every person; I10A Story uses `person-typeahead` | Pick related person | No | **Required** typeahead — not a chip dump |

Admin role list also includes nephew/niece missing from the `<select>` (uncle/aunt present). Editor should use full `ALLOWED_ROLES`.

---

## 5. Identity and Sources (read; Immich is not SoT)

| Screen section | UI label | Existing source | Write / action | Immich write | I10A.1 |
|---|---|---|---|---|---|
| Identity | Canonical MemoryBox Person | `people.id` · `GET /people/{id}` / `profile.identity` | Display | No | **Required** read |
| Identity | Display name (canonical) | `people.display_name` | Edit lives in Profile | No | Show here as identity, edit in Profile |
| Identity | Person status | `people.status` `unresolved` \| `confirmed` \| `merged_away` | Display. Merge changes loser | No | **Required** read. `merged_away` not editable |
| Identity | Merged into | `people.merged_into_id` · `person_merges` | Follow survivor | No | **Required** if merged |
| Identity | Identity authority | `people.attributes_json.identity_authority` (set by teach/map) | Display | No | **Required** read |
| Identity | Is owner | `profile.is_canonical_owner` · `GET /people/owner` | Change is Advanced | No | **Required** read |
| Identity | Linked Immich / provider identities | `provider_identities` (`provider_key`, `identity_kind`, `external_id`, `label`) · `GET /people/{id}/provider-projection` · admin **Photo-library links** | Display as **links**, not the person | No | **Required** read |
| Identity | Mapping confirmation | `provider_identities.confirmed_at`, `confirmed_by` (`003_person_i6.sql`) | Written by teach/map | No | **Required** read |
| Identity | Provenance | `provenance_json` / `actor_key` on facts, aliases, contacts, assertions, events; `assertions` table | Display relevant rows | No | **Required** disclose. No family history browser |
| Identity | HVRT / other provider | Same `provider_identities` rows when present | Display | No | **Required** if linked |

---

## 6. Advanced identity tools (separated; confirm destructive)

Admin today: “Who am I?”, “Reject a wrong photo match”, “Merge duplicate people”, “Teach a photo face”. Map/reconcile are APIs without family UI.

| Screen section | UI label | Existing source | Write / action | Immich write | I10A.1 |
|---|---|---|---|---|---|
| Advanced | I am this person (admin **Save as me**) | `GET/POST /people/owner` → `set_owner_person_id()` · `memorybox_runtime_settings.owner_person_id` | Set owner. **Env `MEMORYBOX_OWNER_PERSON_ID` overrides UI** — disclose | **No** | **Required** + confirm |
| Advanced | Reject incorrect photo/person mapping (admin **Reject this match**) | `POST /people/reject` → `reject_mapping()`: detach `provider_identities.person_id`, insert `identity_negatives` | MB negative + unlink | **No** (does not unassign Immich faces) | **Required** + confirm |
| Advanced | Merge duplicate people (admin **Keep** / **Merge this duplicate away**) | `POST /people/merge` → `merge_people()` · loser `merged_away` · `person_merges` | Destructive | **No** (MB people only) | **Required** + confirm. Typeahead for loser |
| Advanced | Teach or confirm a face (admin **Teach / confirm**) | `POST /people/teach` → `teach_provider_person()`; also `POST /people/bulk-teach`; Learn/Review recognition | Map Immich person → MB Person | **No** (no Immich PATCH name) | **Required** in Advanced, not Profile |
| Advanced | Repair mapping | `POST /people/{id}/map`, `POST /people/{id}/reconcile` | MB mapping only | **No** | **Required** (no admin UI today) |
| Advanced | Open / ensure person from Immich picker | `POST /people/ensure` · `GET /people/picker-options` | Creates/binds MB person | No | **Out** of this editor path (no extra selection). Keep for picker / operator |
| Advanced | Immich sync | `POST /people/sync/immich` | Operator ingest | Talks to Immich **read/sync**, not a silent person-name write from Profile | **Out** of family editor |

Ambiguous Immich→MB teach: existing 409 / owner resolve. Do not silently create a second person.

---

## 7. Capability checklist (old admin → I10A.1)

| Asked capability | Mapped section | Gap |
|---|---|---|
| Full / display name | Profile | None |
| Alternate names / nicknames | Profile | No withdraw API |
| Birth / death including unknown or partial | Profile | Unknown = no row. Partial dates **not** in schema |
| Notes attached to facts | Profile (`person_facts.note` + `fact_kind=note`) | Admin UI mostly uses note-kind `value_text` |
| Email / phone | Profile | Supersede only |
| Important places | Profile | **No SoT** |
| Family + inverse | Relationships | Groups exist in kinship; admin is a flat role select |
| Marriage / anniversary | Relationships | One shared event |
| I am this person | Advanced | Env override |
| Correct displayed name | Profile | MB only |
| MB↔Immich mappings | Identity (read) | — |
| Reject incorrect match | Advanced | MB only |
| Teach / confirm face | Advanced | MB only |
| Merge duplicates | Advanced | Confirm |
| Provenance / confirmation / source identity | Identity | Disclose, no history product |
| Delete / unlink / archive / repair | No person-delete. Unlink = reject. Archive loser = merge. Repair = map/reconcile | No GC |

---

## 8. Inverse role table (do not make the user enter both)

From `INVERSE_ROLE` in `memorybox/profile/owner.py`:

| User teaches | MemoryBox understands |
|---|---|
| father_of / mother_of / parent_of / biological_parent_of / adoptive_parent_of / step_parent_of | child_of |
| child_of / son_of / daughter_of | parent_of |
| spouse_of | spouse_of |
| partner_of | partner_of |
| sibling_of | sibling_of |
| grandparent_of | grandchild_of |
| grandchild_of | grandparent_of |
| uncle_of | nephew_of |
| aunt_of | niece_of |
| nephew_of | uncle_of |
| niece_of | aunt_of |

---

**This map is for product-owner review. It does not authorize implementation.**
