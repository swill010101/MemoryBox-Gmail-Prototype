# MBBS-001 Increment 12 — Minimum Viable Export (EF-16) — Final Definition

**Status:** **BUILT — READY FOR OWNER ACCEPTANCE** (FlightSim I12-OWNER)  
**Date:** 2026-08-11 (final definition locked; build authorized and shipped same day)  
**Roadmap placement:** **After Increment 11 Guided Capture (ACCEPTED)** · **Likely last P1 ownership/exit increment**  
**Owner acceptance gate (locked):** On FlightSim, **without SQL/dev intervention**, Tom starts export from the normal owner UI (`/export/ui`) and receives a **documented on-disk folder package** (`memorybox_export_format: 1`) containing: (1) MemoryBox-created knowledge including **retained version history** where the domain keeps it, (2) **first-class Guided Capture Responses** with enough campaign/question/respondent context to understand the testimony outside MemoryBox, (3) People/relationship/assertion tables (with retained history when available), (4) MemoryBox-**managed** original bytes MB stores, (5) human-readable **README**, (6) **MANIFEST** with **required SHA-256** integrity for packaged files, (7) **human-understandable external evidence references** (not opaque IDs alone) marked INCLUDED vs EXTERNALLY REFERENCED — **without** bulk-copying Immich/HVRT/Takeout libraries. Export of MB-local knowledge must succeed even if Immich/HVRT are unavailable. No subscription or vendor portal required.  
**Charter source:** [MBBS-001](MBBS-001_MEMORYBOX_BUILD_SPECIFICATION.md) § Increment 12  
**Governed by:** [MB_P1_ENGINEERING_RULES.md](../source/MB_P1_ENGINEERING_RULES.md) · [MB_LOCKED_DECISIONS_P1.md](../source/MB_LOCKED_DECISIONS_P1.md)  
**EVS catalog (authoritative):** [MBEVS-001_EVS_Catalog_v0.8.xlsx](../source/MBEVS-001_EVS_Catalog_v0.8.xlsx) (v0.8) — EF-16 / ownership exit (catalog bind at build)  
**Depends on:** Domain knowledge from I1–I11 (Stories, Journals, People/relationships, Artifacts, Guided Capture Responses, Evidence refs as metadata)  
**Prior:** [MBBS-001_INCREMENT_11_ACCEPTANCE.md](MBBS-001_INCREMENT_11_ACCEPTANCE.md) — **ACCEPTED**  
**Acceptance:** [MBBS-001_INCREMENT_12_ACCEPTANCE.md](MBBS-001_INCREMENT_12_ACCEPTANCE.md) — **READY FOR OWNER ACCEPTANCE**  
**Next (after 12):** P1 closeout / P2 backlog only with new authorization — **no silent expansion**  
**Later portability (parked):** Round-trip **import / restore** — [TASK-P1P2-003](MBBS_P1_P2_BACKLOG.md) — **OUT of I12/P1 acceptance**  
**Authorization:** Build authorized 2026-08-11 (*you're approved to build*). Shipped; awaiting FlightSim owner gate.

**Product intent:** Ship a real **way out** — family ownership / no vendor lock-in. MemoryBox must not trap the family’s MB-created knowledge, retained revision history, Guided Capture testimony-in-context, or MB-managed originals by withholding export. I12 proves **exit/export**, not full backup-and-restore.

**Parked / OUT elsewhere:** Full Immich/HVRT mirror · pretty publishing · cloud escrow/sync · multi-user share packages · round-trip import/restore · I11 polish · kinship TASK-P1P2-002 · universal lazy-teach TASK-P1P2-001 · EVS-140 · P2 Dashboard · SMS · P2 UX work

---

## 0. Locked decisions (final definition)

| Topic | Locked decision |
|-------|-----------------|
| Product slice | **Minimum viable Export (EF-16)** — documented package of MB-created knowledge + retained histories MB already keeps + MB-managed originals + manifest |
| Export format version | Explicit **`memorybox_export_format: 1`** in MANIFEST + README; future MB versions must distinguish layouts |
| Package shape | **Canonical = open folder structure.** Optional ZIP may be produced from that folder as transport convenience. Folder is source of truth; no proprietary archive format required |
| Destination | **Config/env only.** No hard-coded FlightSim path, media-server path, Windows drive letter, or hostname. Owner acceptance configures a real destination |
| **IN — versioned knowledge** | Stories/Journals: **current version clearly exposed** + **all retained historical versions** in machine-readable form (version id/number, timestamps, narrator/author, current vs superseded, provenance). Same principle for other correction/revision histories the domain retains (e.g. relationship/assertion history). **Do not invent history the domain does not retain** |
| **IN — Guided Capture** | **First-class.** Export Responses **whether or not** promoted to Story/Journal/Person Fact. Each Response carries **sufficient context** (campaign, question, delivery ref, respondent/contact, optional MB Person, timestamps, channel, typed/transcript + transcript provenance, credibility, review status, MB-managed audio, provenance). Not a second Gmail archive. If a Response also produced a Story (or other object), **preserve that relationship** without ambiguously duplicating testimony |
| **IN — People / graph** | People display + aliases/facts/relationships/assertions as tables; include retained history when available |
| **IN — originals MB stores** | Story/Journal/Guided Capture **audio** and other bytes whose authoritative file lives under MB-managed storage; Artifact **MB-managed** representation files |
| **IN — checksums** | **Required SHA-256.** At minimum every MB-managed original copied into the package; **preferably every packaged file** (JSON/JSONL/CSV/README included). MANIFEST entries: relative path, byte size, SHA-256, media/type, related MB entity id where appropriate |
| **IN — external refs** | Human-understandable reference metadata (provider/source type, external id, original filename, URI/path where appropriate, date/time metadata, related MB entities, **INCLUDED vs EXTERNALLY REFERENCED**). README explains externally managed originals may not be in the package. **No** bulk Immich/HVRT/Takeout copy. MB-local export must **not** fail solely because an external provider is unavailable |
| **OUT — media mirror** | Do **not** copy Immich originals, HVRT video libraries, or Takeout trees into the export |
| **OUT — pretty publishing** | No PDF coffee-table book, no multi-theme website publisher |
| **OUT — import-back** | Round-trip import/restore **OUT of I12/P1 acceptance**; parked as later portability ([TASK-P1P2-003](MBBS_P1_P2_BACKLOG.md)) |
| Owner UX | Thin UI **starts** export; export **may run asynchronously**; UI shows running/completed/failed + destination; disk-full/path/access failures visible. CLI may wait synchronously for prove/ops. **No** sophisticated job-management subsystem solely for I12 |
| Access | Owner produces export **locally**; **no subscription** required |
| Prove | `prove-export` (+ `--flightsim`) |
| Hosts | FlightSim = P1 runtime; desktop = edit/prove only |

---

## 1. Why 12 exists

P1 already creates durable family knowledge (Stories, Journals, People, Artifacts, Guided Capture). Without Export, that knowledge — including retained revisions and Guided Capture testimony-in-context — is trapped in MemoryBox’s runtime. MBBC / locked P1 decisions require a **minimum viable exit**: documented, open, owner-controlled, integrity-checked package of **what MB created and what MB manages** — not a full photo-library clone, and not a restore product.

---

## 2. EVS / charter binding

| Source | Role in I12 |
|--------|-------------|
| **EF-16** (MBBS Increment 12) | **Primary** — MV export |
| Ownership / no lock-in (MBBS §6.10, MB_LOCKED_DECISIONS) | **Governing** |
| Immich / HVRT / Takeout as **referenced** sources | Human-understandable pointers; must not require byte-for-byte mirror |
| Catalog rows for “export” if present in v0.8 | Bind exact EVS ids at build after sheet check — do not invent |

---

## 3. Domain / package model

### 3.0 Format identity

MANIFEST and README **must** identify:

| Field | Requirement |
|-------|-------------|
| `memorybox_export_format` | **`1`** (integer/string as documented; layout discriminator for future versions) |
| Export timestamp | Required |
| MemoryBox application/build version | Include **if available** |
| Package limitations | Honest: what is INCLUDED vs EXTERNALLY REFERENCED; no Immich/HVRT full library; no import-back claim |

### 3.1 Canonical layout (folder = source of truth)

```
export_root/
  README.md                 # human: format version, layout, limits, how to open; external originals may be absent
  MANIFEST.json             # machine: format version, created_at, app version, inventories, file integrity entries
  tables/                   # CSV and/or JSONL
    people.csv
    relationships.csv
    relationship_history.jsonl   # only if domain retains history
    assertions.csv               # + history if retained
    stories.jsonl                # current + retained versions (see §3.2)
    journals.jsonl               # current + retained versions (see §3.2)
    guided_capture_campaigns.jsonl
    guided_capture_questions.jsonl
    guided_capture_deliveries.jsonl   # references, not email archive
    guided_capture_responses.jsonl    # first-class + context (§3.3)
    artifacts.csv
    evidence_refs.jsonl          # human-understandable external refs (§3.5)
  originals/                # MB-managed bytes only
    audio/...
    artifacts/...
  provenance/               # optional deeper dumps if needed
```

Exact filenames finalized at build; README must match reality. Optional ZIP is a **derivative** of this folder, not a second layout.

### 3.2 Retained version history (Stories, Journals, and peers)

If MemoryBox retains immutable historical versions, export **must not** drop them in favor of “current body only.”

For versioned objects such as **Story** and **Journal**, machine-readable export must include, for each retained version:

| Field | Required |
|-------|----------|
| Version number / id | Yes |
| Body / content for that version | Yes |
| Created / changed timestamp | Yes (as domain stores) |
| Narrator / author | Yes (as domain stores) |
| Current vs superseded (or equivalent status) | Yes |
| Provenance | Yes (as domain stores) |

**Current version** must be **clearly exposed** (flag, pointer, or dedicated current record) so a human or tool can find “what is live now” without discarding history.

Apply the **same principle** to other correction/revision histories the existing domain retains (including relationship/assertion history **when available**).

**Do not invent** history the domain does not currently retain.

### 3.3 Guided Capture — context must survive; Response remains first-class

Guided Capture is **IN**.

Do **not** export only isolated response text.

**Guided Capture Responses remain first-class** whether or not they were promoted to Story / Journal / Person Fact. If a response also has a resulting Story (or other object), **preserve that relationship** without ambiguously duplicating testimony (e.g. link/ids + clear roles: source Response vs derived Story).

For each Response, export enough context to understand the testimony **outside MemoryBox**:

| Context | Required |
|---------|----------|
| Campaign | Yes |
| Question | Yes |
| Outbound delivery reference | Yes |
| Respondent / contact | Yes |
| Optional linked MB Person | Yes when present |
| Received timestamp | Yes |
| Channel | Yes |
| Typed response / transcript | Yes |
| Transcript provenance / version | Where applicable |
| Owner credibility assessment | Yes |
| Review status | Yes |
| Original audio reference/file when MB-managed | Yes when MB stores bytes |
| Provenance | Yes |

**Do not** create a second Gmail archive. Preserve transport/source references where useful; the purpose is to preserve **Guided Capture knowledge and why the person was answering**.

### 3.4 Inclusion rules (summary)

| Include | Rule |
|---------|------|
| Story / Journal | Current + **all retained** versions (§3.2) |
| Guided Capture | First-class Responses + campaign/question/delivery/respondent context (§3.3); not email-body dump |
| People / relationships / facts / assertions | Owner-visible graph as tables; retained history when domain keeps it |
| Artifact | Metadata + **MB-managed** representation files only |
| Audio / attachments | Only if MemoryBox **stores** the bytes |
| Evidence / Immich / HVRT / Takeout | **Human-understandable references** (§3.5) — **no** bulk media copy |

### 3.5 External evidence references (human-understandable)

Do **not** copy full Immich, HVRT, Takeout, or other externally managed libraries.

Where information exists, external references must include more than opaque provider IDs, for example:

| Metadata | When available |
|----------|----------------|
| Provider / source type | Yes |
| Provider external id | Yes |
| Original filename | Yes |
| Original URI / path / reference | Where appropriate |
| Relevant date/time metadata | Yes |
| Related MB entities | Yes |
| Bytes status | **`INCLUDED`** or **`EXTERNALLY_REFERENCED`** |

README **must** explain that externally managed originals may not be contained in the export.

MB-local knowledge export **must not fail** merely because an external provider is unavailable.

### 3.6 Checksums (required)

Require **SHA-256** integrity values.

| Rule | Requirement |
|------|-------------|
| Minimum | Checksum **every MB-managed original** copied into the package |
| Prefer | Checksum **every packaged file**, including JSON/JSONL/CSV/README |
| MANIFEST file entry | Relative path; byte size; SHA-256; media/type; related MemoryBox entity id where appropriate |

### 3.7 Explicit non-goals

- Reconstructing Immich or HVRT libraries  
- Guaranteeing offline playback of every Ask photo/video hit  
- Encrypted escrow / lawyer-held vault / continuous backup SaaS  
- Multi-user share packages  
- **Import-back / round-trip restore as I12 or P1 acceptance** (parked: TASK-P1P2-003)  
- Sophisticated job orchestration beyond thin async status for export  

---

## 4. Owner UX / job model (thin — no polish)

| Capability | Required |
|------------|----------|
| Thin UI starts export | Yes |
| Export may run asynchronously | Yes (preferred for UI) |
| UI shows running / completed / failed + destination | Yes |
| Disk-full / path missing / access failures visible | Yes |
| Land package on configured local/LAN path | Yes (config/env — D7; no hard-coded host paths) |
| Open README and verify contents without MemoryBox UI | Yes |
| CLI may wait synchronously for proving/ops | Allowed |
| Sophisticated job-management subsystem solely for I12 | **No** |

---

## 5. Success criteria

| ID | Criterion | Proof |
|----|-----------|-------|
| **I12-A** | Owner starts export from normal UI without SQL | Harness + FS |
| **I12-B** | README documents format version, layout, MV limits, external-ref policy | Harness + FS |
| **I12-C** | Stories + Journals export **current + retained versions** when domain has them | Harness + FS |
| **I12-D** | MB-managed originals present when they exist; SHA-256 in MANIFEST | Harness + FS |
| **I12-E** | People/relationships/assertions (+ retained history when available) | Harness |
| **I12-F** | Guided Capture Responses first-class with campaign/question/respondent context | Harness + FS |
| **I12-F2** | Response↔derived Story (or other) relationship preserved without ambiguous testimony duplication | Harness |
| **I12-G** | Export does **not** require Immich/HVRT for MB-local knowledge | Harness |
| **I12-H** | No Immich/HVRT/Takeout full-library copy; refs are human-understandable + INCLUDED vs EXTERNALLY_REFERENCED | Harness + docs |
| **I12-I** | `memorybox_export_format: 1` + export timestamp (+ app version if available) in MANIFEST/README | Harness |
| **I12-J** | SHA-256 required for packaged MB-managed originals; preferably all packaged files | Harness + FS |
| **I12-K** | Canonical output is folder; optional ZIP is derivative only | Harness |
| **I12-L** | Destination from config/env only — no hard-coded FS/media-server/drive/host | Harness + docs |
| **I12-M** | Async UI status (or equivalent visible completion) without heavy job platform | Harness + FS |
| **I12-N** | `prove-export` (+ `--flightsim`) | Harness |
| **I12-O** | I1–I11 remains runnable | Prior |
| **I12-OWNER** | §6 strengthened FlightSim gate | Tom |
| **I12-P** | Living docs; OUT list honest; import-back parked not forgotten | Docs |

---

## 6. FlightSim owner gate (strengthened)

1. Ensure Story / Journal / Guided Capture / People / relationship data exists.  
2. Ensure at least one **retained version history** exists where practical.  
3. Ensure at least one **MB-managed original** exists.  
4. Run export from **normal owner UI** without SQL.  
5. Open **README** outside MemoryBox.  
6. Inspect **machine-readable** data outside MemoryBox.  
7. Confirm **current + retained** version history where present.  
8. Confirm Guided Capture Response includes its **prompting question / respondent** context.  
9. Verify at least one packaged file against **MANIFEST SHA-256**.  
10. Confirm MB-managed originals are **included**.  
11. Confirm external Immich/HVRT media are **referenced** rather than bulk copied.  
12. Confirm export **succeeds without requiring active Immich/HVRT** for MB-local knowledge.  
13. Confirm **no subscription / vendor portal** is required.

---

## 7. Synthetic harness (`prove-export`)

Must prove: `memorybox_export_format: 1`; folder layout (+ optional zip derivative if implemented); README present with limitations; Story/Journal current + retained versions when seeded; Guided Capture Response with campaign/question/respondent context; promotion link without ambiguous duplication when seeded; MB-managed file copied + SHA-256; preferably checksums on table/README files; human-understandable external refs with EXTERNALLY_REFERENCED; Immich-unavailable does not block MB-local export; config/env destination (no hard-coded paths); thin async or visible completion path; `--flightsim` owner checks aligned to §6.

---

## 8. Out of I12 (scope locks)

Keep **OUT**:

- Full Immich / HVRT / Takeout media mirror  
- Pretty publishing (PDF / multi-theme site)  
- Cloud escrow / sync product  
- Multi-user share packages  
- Round-trip restore / import (P1 acceptance) — parked [TASK-P1P2-003](MBBS_P1_P2_BACKLOG.md)  
- P2 Dashboard  
- Kinship inference (TASK-P1P2-002)  
- Guided Capture polish  
- SMS  
- EVS-140  
- P2 UX work  
- Sophisticated job-management platform solely for export  

---

## 9. Resolved decisions (former open questions)

| Question | Resolution |
|----------|------------|
| Package shape | **Folder canonical**; optional ZIP from folder |
| Guided Capture + People | **IN** (with full Response context; first-class) |
| Export destination | **Config/env only**; owner configures real path at acceptance |
| Async vs sync | **Async UI preferred**; CLI may sync for prove/ops; no heavy job system |
| Import-back | **OUT of I12/P1**; parked TASK-P1P2-003 |
| Checksums | **Required SHA-256** (originals minimum; preferably all packaged files) |
| Version history | **Export retained versions** the domain keeps; do not invent |
| Format version | **`memorybox_export_format: 1`** |

---

## 10. Build plan (only after authorize)

1. Export format `1` + README template + MANIFEST schema (integrity entries).  
2. Serialize Stories/Journals with retained versions; People/relationships/assertions (+ history when retained).  
3. Serialize Guided Capture campaigns/questions/deliveries/responses with §3.3 context; preserve promotion links without ambiguous duplication.  
4. Copy MB-managed originals into `originals/`; compute SHA-256 (prefer all packaged files).  
5. Emit human-understandable evidence refs (INCLUDED vs EXTERNALLY_REFERENCED).  
6. Thin UI (async status) + config/env destination + CLI / `prove-export`.  
7. Optional ZIP from folder.  
8. FlightSim owner gate (§6).  
9. **Stop** — no import-back, no P2, no media mirror under this auth.

---

## 11. Authorization gate

**Status: BUILT — READY FOR OWNER ACCEPTANCE.**

Build was authorized 2026-08-11. Owner acceptance remains the FlightSim gate in [MBBS-001_INCREMENT_12_ACCEPTANCE.md](MBBS-001_INCREMENT_12_ACCEPTANCE.md).

---

## 12. Stop line

After I12 acceptance (when owner-accepted): treat P1 ownership/exit as satisfied for **MV Export**; further work (including import/restore portability) only with new authorization.

---

*End of MBBS-001 Increment 12 — Minimum Viable Export (EF-16) — Final Definition. Built; owner acceptance pending.*
