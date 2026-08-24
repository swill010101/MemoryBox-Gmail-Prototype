# P2-I10C — Journal screens vs I5A POC (field verification)

**Status:** Assessment **LOCKED** with I10C definition 2026-08-24 (Tom lock list)  
**Increment ID:** **P2-I10C Journal** (I10B is Artifacts, **ACCEPTED**. Tom said “i10B journal”; product sequence names this **I10C**.)  
**Visuals:** `fe913a4` → `docs/source/Screens/MBUX Journal Screens/`  
**POC:** `memorybox/journal/static/journal.html` + `memorybox/journal/__init__.py` + `002_journal_i5a.sql` + `GET/POST /journal`  
**Speech:** I10A.2 **ACCEPTED** — Journal body already mounts `MBNarrativeField` `authored-memory`. Do not reopen I10A.2.

Screenshot text is **not** proof of a backend field. This table is the verification.

---

## 1. What the POC is

Increment **5A** Journal: typed/spoken owner notes, **integer versions**, author Person FK, described date range + precision, `audio_uri` on save, Ask retrieve of **current** version. UI is a developer form: Capture / paste Journal ID / Get / List, JSON in a `<pre>`. No panel, no detail, no I10A chrome, no place, no visibility, no supporting-memory picker, no draft vs Ask.

Speech on `#body` / `#editBody` is already I10A.2. Private Record/Stop is gone. I10C is **family Journal product**, not a second mic.

---

## 2. Screens present

| PNG | Product surface |
|---|---|
| `01_MBUX_Journal_Panel_Draft_v1.png` | List/feed, calendar, On this day, New entry |
| `02_MBUX_Journal_New_Entry_Draft_v1.png` | Create (draft chrome + ENTRY DETAILS) |
| `03_MBUX_Journal_Detail_Draft_v1.png` | Read one saved entry + connections |

No Journal **Edit** PNG. Treat Edit as New-entry layout on an existing id (same pattern as Stories revision), unless a later PNG arrives.

Panel nav omits **Review & Learn**; New and Detail include it. **I10C chrome = I10A/I10B family shell** (Ask, People, Stories, Journal, Artifacts, Family Night, Review & Learn). Do not fork Ask copy per Journal page.

---

## 3. Field-by-field: New entry (`02`) vs POC

| Screen control | POC UI | Schema / service today | Verification | I10C stance |
|---|---|---|---|---|
| Title (optional) “Give this entry a title.” | `#title` optional | `journal_entries.title` nullable | **Match.** | **Frozen.** Title optional. Body required. Untitled = first meaningful body line, never invented “Untitled Journal”. |
| Entry textarea + “Write directly or dictate…” | `#body` + I10A.2 | `journal_versions.body_text` NOT NULL | **Match** (speech already shared). | Reuse `MBNarrativeField` authored-memory. No Journal-private recorder. |
| Start dictation / Upload audio | I10A.2 Tell this story / file fallback | `audio_uri` on entry + version | **Match in capability, not chrome.** POC has no “Start dictation” label. | I10A.2 family wording. Preserve audio on Save journal. |
| Supporting memories + Add memories | **Missing.** API `evidence_ids` unused in HTML | `relationships` `cites_evidence` only; no mixed photo/video/artifact/calendar/journal-audio picker | **Screen ahead of POC.** | **Required.** Mixed links like I10A (`photo` \| `video` \| `email_thread` \| `sms_conversation` \| `calendar_event` \| `artifact` \| `audio`). Journal→Journal **out**. Originals unchanged. |
| Author “Tom Will” | `#author` free text default “Tom” | `author_person_id` NOT NULL; `ensure_person(display_name)` | **Partial.** Screen is a Person; POC mints/resolves by typed name. | **Required.** Owner Person display-only (I10A editor pattern). Do not keep a free-text author box as SoT. |
| Entry date “August 22, 2026” | `#dStart` + `#dEnd` YYYY-MM-DD | `described_start_date`, `described_end_date`; both set or both NULL | **Conflict.** Screen = **one** date. POC = **range**. | **Frozen.** One Entry date + optional described time. No range UI. Schema start/end kept for import/future. Precision preserved; no fake day. New entry **defaults to today**, editable. `captured_at` ≠ Entry date. |
| Time (optional) “2:15 PM” | **Missing** | `captured_at` is save timestamp, not described time | **Missing in POC.** | **Frozen.** Optional described time, separate from `captured_at`. |
| Place (optional) | **Missing** | no `place_id` on `journal_entries` | **Missing in POC.** | **Required** like I10B: `places.id` SoT. No free-text-only Place. |
| Visibility Private | **Missing** | no visibility column; Ask indexes all `status=active` | **Missing in POC. Risk:** every Save is Ask-visible. | **Required** `private` \| `shared_with_family` (I10A). Owner Ask sees private. Unauthorized must not. |
| People + Add people | API `person_ids` unused in HTML | `relationships` `about_person` | **API exists, no family UI.** | **Required** Person picker (I10A/I10B). |
| Draft / Not available to Ask | **Missing.** Save = `active` v1 immediately | `status` active\|removed only | **Conflict.** Screens = Stories draft. I5A = no working draft. | **Frozen — drafts IN.** Save draft out of Ask. Save journal creates/advances saved version; Ask-eligible subject to visibility. |
| Save draft / Save journal | Save Journal / Save new version | `create_journal` / `save_new_version` | **Conflict** vs I5A immediate save. | **Frozen.** Edit-saved: work on draft; Ask keeps last saved until Save journal. |
| Footer copy about Ask | POC tells you to Save | Ask `search_journals` current version only | Screens match once **saved**. | **Frozen.** Draft never in Ask. Ask = last saved version. |

---

## 4. Field-by-field: Detail (`03`) vs POC

| Screen control | POC | Verification | I10C stance |
|---|---|---|---|
| Title heading | `title` or empty | POC list shows title; no family detail page | **Frozen.** If title empty: first meaningful body line. Never invent “Untitled Journal”. |
| Delete entry | `status='removed'` unused in UI | **Missing UI** | **Required** soft-remove. Keep bytes and versions. No GC. |
| Edit entry | paste UUID + `#editBody` | **Not a product path** | **Required** editor on that id. |
| Saved / Available to Ask | derived nowhere | **Missing** | **Required** badges from persist + visibility (I10A pattern). |
| AUGUST 17, 2026 • Written by Tom Will | described dates + author name | **Match if Entry date = described start** | Show described Entry date, not `created_at`, unless date unknown. |
| Body card | `body_text` | **Match** | Current version body. |
| Supporting memories photo/video cards | unused `evidence_ids` | **Missing** | Same memory model as New. |
| ABOUT: Author, Entry date, Current version, Last saved, Visibility | version int, `updated_at`, no visibility | **Partial** | **Required** panel. Last saved = `updated_at` / version `created_at`. |
| View revision history | `GET /journal/{id}?version=` | **API exists, no UI** | **Required** read-only history. Restore-from-history **out** (same as I10A). |
| ENTRY CONNECTIONS person · memories | `person_ids` + evidence | **Partial** | Counts from live links. |
| Ask about this entry | Ask shell | **Missing Journal-scoped Ask** | Reuse product Ask; optional prefill. Do not invent a second Ask engine. |

---

## 5. Field-by-field: Panel (`01`) vs POC

| Screen control | POC | Verification | I10C stance |
|---|---|---|---|
| Journal heading + “Your memories and reflections…” | “MemoryBox Journal” + JSON | Chrome only | Family copy OK. |
| Private by default | none | **Missing** | Matches Visibility default `private`. |
| + New entry / Start an entry | always-on capture form | **Missing navigation** | Both go to New entry. |
| Search journal | `GET /journal` unfiltered list | **Missing search** | **Required** title/body search of **saved** entries (drafts are not the panel feed). |
| All entries / Mine / Family contributions | none | PNG shows three tabs | **Frozen.** **All entries only.** Do not show Mine or Family contributions until multiple authors/users exist. |
| People filter / All time | none | **Missing** | **Required** Person + time filters **within All entries**. |
| Card: thumbnail, date, Saved, ⋮, title, preview, author, pills, linked memories | list API too thin | **POC list is too thin** | **Required** card: described Entry date, title or first meaningful body line, author, memory count. Thumbnail = first photo memory or honest empty. Pills = real Person links; optional real linked-object indicators. **No tag taxonomy** (no “Christmas”). |
| Calendar with dots | none | **Missing** | **Frozen IN.** Dots = **saved** Entry dates. Drafts do not appear. |
| On this day | none (EVS-072 is Ask-shaped) | **Missing** | **Frozen IN.** Saved entries from prior years matching the viewed calendar date’s month/day. Drafts do not appear. |
| Journal principles widget | none | Decorative | Optional copy; not a data object. |
| ⋮ on card | none | **Missing** | Open, Edit, Remove (soft). |

---

## 6. POC fields **not** on screens

| POC / schema | Screens | Stance |
|---|---|---|
| `#precision` day/month/year/range/approximate/unknown | Hidden; Entry date looks like a calendar day | **Frozen.** Preserve precision. No fake day for month/year. No range UI. `range` not in I10C UI; schema may still hold start≠end for future import. |
| `channel` ui \| email \| voice \| import | Dictation implies voice | Set `voice` when `audio_uri` present on Save journal, else `ui`. Email/import **out**. |
| `captured_at` | Last saved vs Entry date | **Frozen.** System capture/save clock. Not Entry date. Not described time. |
| `source_id` | none | Leave unused. |
| Paste Journal ID / List / JSON result | none | **Replace.** Family routes, not UUID paste. |
| `actor_key` must not be stt/ai | none | Keep: STT cannot Save. |
| Dual `body_text` on entry **and** version | one body | Keep version as SoT for Ask; entry row may mirror current body (existing I5A). |

---

## 7. Founder locks (closed)

O1–O6 are **closed** 2026-08-24. See [MBBS-P2_INCREMENT_10C_DEFINITION.md](MBBS-P2_INCREMENT_10C_DEFINITION.md) Founder locks: drafts IN; one Entry date + optional time IN (default today on new); calendar + On this day IN (saved only); HVRT ingest OUT; title optional; no tag taxonomy; **All entries only** (no Mine / Family contributions).

---

## 8. Do not start in I10C

I11 narrative · I10A.2 reopen · Artifact recorder · guided-capture email journals (EVS-131–140 / I15) · Mine / Family contributions · multi-user ACL · tag taxonomy · Journal→Journal memories · restore-from-history · file GC · Face SoT · HVRT journal ingest
