# MBBS-001 Increment 12 — Minimum Viable Export (EF-16) — Definition

**Status:** **REVIEW ONLY — NOT AUTHORIZED TO BUILD**  
**Date:** 2026-08-11  
**Roadmap placement:** **After Increment 11 Guided Capture (ACCEPTED)** · **Likely last P1 ownership/exit increment**  
**Owner acceptance gate (proposed for review):** On FlightSim, **without SQL/dev intervention**, Tom runs a MemoryBox export and receives a **documented on-disk package** containing: (1) MemoryBox-created knowledge (at least Stories, Journals, and related text/manifests), (2) MemoryBox-**managed** original files MB stores (e.g. Story/Journal/Guided Capture audio, Artifact bytes MB holds), (3) a **human-readable README**, (4) a **manifest** (JSON and/or CSV) covering people/relationships/assertions/provenance pointers sufficient to understand what was exported — **without** reconstructing Immich or copying every externally referenced original. No subscription or vendor portal required to obtain this package of the family’s own MB data.  
**Charter source:** [MBBS-001](MBBS-001_MEMORYBOX_BUILD_SPECIFICATION.md) § Increment 12  
**Governed by:** [MB_P1_ENGINEERING_RULES.md](../source/MB_P1_ENGINEERING_RULES.md) · [MB_LOCKED_DECISIONS_P1.md](../source/MB_LOCKED_DECISIONS_P1.md)  
**EVS catalog (authoritative):** [MBEVS-001_EVS_Catalog_v0.8.xlsx](../source/MBEVS-001_EVS_Catalog_v0.8.xlsx) (v0.8) — EF-16 / ownership exit (catalog bind at build)  
**Depends on:** Domain knowledge from I1–I11 (Stories, Journals, People/relationships, Artifacts, Guided Capture Responses, Evidence refs as metadata)  
**Prior:** [MBBS-001_INCREMENT_11_ACCEPTANCE.md](MBBS-001_INCREMENT_11_ACCEPTANCE.md) — **ACCEPTED**  
**Acceptance:** *(write `MBBS-001_INCREMENT_12_ACCEPTANCE.md` only after *Build Increment 12 only*)*  
**Next (after 12):** P1 closeout / P2 backlog only with new authorization — **no silent expansion**  
**Authorization:** **Not authorized.** Do not implement until Tom says *Build Increment 12 only*.

**Product intent:** Ship a real **way out** — family ownership / no vendor lock-in. MemoryBox must not retain the family’s MB-created knowledge or MB-managed originals by withholding export.

**Parked / OUT elsewhere:** Full Immich mirror · pretty multi-format publishing · encrypted cloud sync product · multi-user share packages · I11 polish · kinship TASK-P1P2-002 · universal lazy-teach TASK-P1P2-001 · EVS-140 · P2 Dashboard

---

## 0. Proposed locked decisions (for Tom review)

| Topic | Proposed decision |
|-------|-------------------|
| Product slice | **Minimum viable Export (EF-16)** — documented package of MB-created knowledge + MB-managed originals + manifest |
| Package form | Single **export root folder** (optionally zip) on a configured path; open formats only |
| **IN — knowledge** | Current Story versions; current Journal versions; **Guided Capture Responses** (testimony + credibility metadata); People display + aliases/facts/relationships/assertions as exported tables; Artifact metadata (+ MB-managed representation bytes) |
| **IN — originals MB stores** | Story/Journal/Guided Capture **audio** (and other bytes) whose authoritative file lives under MemoryBox-managed storage; Artifact **MB-managed** representation files |
| **IN — manifest** | README + JSON and/or CSV: package version, export timestamp, entity inventories, provenance pointers (Evidence/Source ids, provider keys, external ids **as references**, not Immich file copies) |
| **OUT — media mirror** | Do **not** copy Immich originals, HVRT video libraries, or Takeout trees into the export |
| **OUT — pretty publishing** | No PDF coffee-table book, no multi-theme website publisher |
| Access | Owner can produce export **locally** on FlightSim; **no subscription** required for this exit package |
| Prove | `prove-export` (+ `--flightsim`) |
| Hosts | FlightSim = P1 runtime; desktop = edit/prove only |

---

## 1. Why 12 exists

P1 already creates durable family knowledge (Stories, Journals, People, Artifacts, Guided Capture). Without Export, that knowledge is trapped in MemoryBox’s runtime. MBBC / locked P1 decisions require a **minimum viable exit**: documented, open, owner-controlled package of **what MB created and what MB manages** — not a full photo-library clone.

---

## 2. EVS / charter binding

| Source | Role in I12 |
|--------|-------------|
| **EF-16** (MBBS Increment 12) | **Primary** — MV export |
| Ownership / no lock-in (MBBS §6.10, MB_LOCKED_DECISIONS) | **Governing** |
| Immich / HVRT / Takeout as **referenced** sources | Manifest may **point**; must not require byte-for-byte mirror |
| Catalog rows for “export” if present in v0.8 | Bind exact EVS ids at build after sheet check — do not invent |

---

## 3. Domain / package model (proposed)

```
export_root/
  README.md                 # human: what this is, layout, limits, how to open files
  MANIFEST.json             # machine: version, created_at, counts, checksums
  tables/                   # CSV and/or JSONL
    people.csv
    relationships.csv
    stories.jsonl
    journals.jsonl
    guided_capture_responses.jsonl
    artifacts.csv
    evidence_refs.csv       # pointers only where useful
  originals/                # MB-managed bytes only
    audio/...
    artifacts/...
  provenance/               # optional deeper dumps
```

Exact filenames/layout finalized at build; README must match reality.

### 3.1 Inclusion rules

| Include | Rule |
|---------|------|
| Story / Journal **text** | Current version bodies (+ version metadata) |
| Guided Capture Response | Testimony text/transcript; credibility; campaign/question refs; **not** a second email archive |
| People / relationships / facts | Owner-visible graph knowledge as tables |
| Artifact | Metadata + **MB-managed** representation files only |
| Audio / attachments | Only if MemoryBox **stores** the bytes (not Immich proxy URLs alone) |
| Evidence / Immich / HVRT | **References** in manifest (ids, URIs, provider keys) — **no** bulk media copy |

### 3.2 Explicit non-goals

- Reconstructing Immich or HVRT libraries  
- Guaranteeing offline playback of every Ask photo/video hit  
- Encrypted escrow / lawyer-held vault product  
- Continuous backup SaaS  
- Import-back / round-trip restore as I12 acceptance (nice later; not required for MV exit)

---

## 4. Owner UX (thin — no polish)

| Capability | Required |
|------------|----------|
| Trigger export from thin UI and/or CLI | Yes |
| See job/progress or clear completion path | Yes (async OK) |
| Land package on configured local/LAN path | Yes (D7 — no hard-coded host paths) |
| Open README and verify contents without MemoryBox UI | Yes |
| Failures visible (disk full, path missing) | Yes |

---

## 5. Success criteria (proposed)

| ID | Criterion | Proof |
|----|-----------|-------|
| **I12-A** | Owner can start export without SQL | Harness + FS |
| **I12-B** | Package contains README documenting layout + MV limits | Harness + FS |
| **I12-C** | Stories + Journals present (text) when they exist in DB | Harness + FS |
| **I12-D** | MB-managed originals present when they exist (e.g. audio) | Harness + FS |
| **I12-E** | Manifest lists people/relationships/assertions or equivalent provenance tables | Harness |
| **I12-F** | Guided Capture Responses included when present | Harness + FS |
| **I12-G** | Export does **not** require Immich/HVRT to succeed for MB-local knowledge | Harness |
| **I12-H** | No Immich full-library copy claimed or performed | Harness + docs |
| **I12-I** | `prove-export` (+ `--flightsim`) | Harness |
| **I12-J** | I1–I11 remains runnable | Prior |
| **I12-OWNER** | §6 real package on FlightSim | Tom |
| **I12-K** | Living docs; OUT list honest | Docs |

---

## 6. FlightSim owner gate (proposed)

1. Ensure some MB-created knowledge exists (Story and/or Journal and/or Guided Capture Response).  
2. Ensure at least one MB-managed original exists if available (audio or artifact bytes).  
3. Tom runs export from UI or CLI.  
4. Opens package on disk; reads README.  
5. Confirms knowledge files + managed originals (if any) + manifest.  
6. Confirms package was obtained **locally** without a vendor subscription step.  
7. Confirms Immich library was **not** mirrored as a requirement.

---

## 7. Synthetic harness (`prove-export`)

Must prove: package layout; README present; story/journal (and GC when seeded) serialized; MB-managed file copied when present; manifest inventories; Immich-unavailable does not block MB-local export; `--flightsim` owner checks.

---

## 8. Out of I12

Full Immich/HVRT media mirror · pretty publishing · encrypted cloud escrow product · multi-user shared export portals · round-trip import/restore as acceptance · Settings polish · kinship inference · Guided Capture polish · P2 Dashboard · SMS · EVS-140

---

## 9. Open questions for Tom (sign-off blockers)

1. **Package shape:** folder on disk vs zip-primary — preference?  
2. **Guided Capture + People graph in MV:** proposed **IN** — confirm or trim?  
3. **Default export path:** env/config only (proposed) — any FlightSim convention to document?  
4. **Async job vs sync CLI** for acceptance — either OK if visible; prefer one?  
5. **Import-back:** explicitly **OUT** of I12 acceptance — confirm?  
6. **Checksums:** SHA256 of packaged originals in MANIFEST — required or optional?

---

## 10. Build plan (only after authorize)

1. Export service + documented layout + README template.  
2. Serialize Stories/Journals/People/relationships (+ GC Responses, Artifacts per lock).  
3. Copy MB-managed originals into `originals/`.  
4. Manifest JSON/CSV + optional checksums.  
5. Thin UI + CLI (`export` / `prove-export`).  
6. FlightSim owner gate.  
7. **Stop** — no P2 scope under this auth.

---

## 11. Authorization gate

**Status: REVIEW ONLY — NOT AUTHORIZED TO BUILD.**

Do **not** begin Increment 12 until Tom explicitly authorizes *Build Increment 12 only* after reviewing this definition (and answering §9 as needed).

---

## 12. Stop line

After I12 acceptance (when built): treat P1 ownership/exit as satisfied for MV Export; further work only with new authorization.

---

*End of MBBS-001 Increment 12 — Minimum Viable Export (EF-16) — Definition. REVIEW ONLY — do not build.*
