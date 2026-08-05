# MBD-001 — MemoryBox Demonstrator PRD

**Status:** Approved (Tom) — implement · 2026-08-05  
**ID:** MBD-001  
**Owner:** Tom Will (sole demonstrator user; multi-user deferred)  
**Charter:** Integrate the existing HVRT POC and email/text search POC into a single coherent application. Add only the minimum new capabilities required to demonstrate the MemoryBox experience. Goal = **validation of the product experience**, not completion of the product. Host on **Media-Server**, reachable outside the LAN via **Tailscale** (Tom only).

**Depends on / imports:**
- HVRT R2 review + Learn (`hvrt/` — faces, speech, places, OCR, video transcripts)
- Email/text Ask historian POC (Desktop `application/api`, retrieve/Qdrant/Ollama — to be brought into git as part of this entity)
- Parked [MEMORYBOX_VOICE_ANNOTATE_PRD.md](../../hvrt/docs/MEMORYBOX_VOICE_ANNOTATE_PRD.md) — adopted **and extended** here with **Edit Memory / versioning**
- Evidence Principles in root [README.md](../../README.md)

**Related product hierarchy (when present):** sits under MB experience validation; does not replace MBAR / full product constitution.

---

## 1. Problem being solved (and why now)

Two working POCs prove pieces of Memory Box:

| POC | Proves | Feels like |
|-----|--------|------------|
| Email/text Ask (~8787) | Hybrid retrieve + narrative answer + citations over mail/SMS/calendar/Immich | Separate “historian” app |
| HVRT review (~8788) | Teach-while-watching video: faces, voice spans, places, OCR, Learn | Separate “operator console” |

Investors and family cannot experience **one product**. Teaching a face in video does not connect to people in email/Immich. Voice stories are not first-class. There is no shared library/timeline. Demo access is LAN-only.

Teaching today also fails a memory product promise: if Tom records the **pocket watch story** tonight, he must be able to **improve it tomorrow**—edit and **version**, never silently overwrite. And when he teaches, the archive should acknowledge quietly: **Archive Updated**.

**Why now:** Validate the Memory Box *experience* with a coherent demonstrator on Media-Server + Tailscale, before investing in full product completion.

---

## 2. Success criteria

Tom runs a live demo; investors/family watch. Unassisted use by guests is **out**. Success when:

1. **One app URL** on Media-Server (via Tailscale IP + port) opens a **dual-console** Memory Box: **Ask** | **Review** (and Library/Timeline), with **shared curator chrome** (Option B).
2. **Ask works** as today for email/text (and Immich photos): question → narrative → supporting evidence.
3. **Review works** as today for HVRT video teach/learn (faces, speech, places, OCR, Learn), restyled into curator patterns—not a bolted-on teal operator skin.
4. **Unified evidence** appears under Ask answers **and** in a **browseable timeline/library** (email, SMS, photo, video hit, voice note, artifact).
5. **Voice annotate:** Record → Stop → transcript → Save → searchable/citable; then **Edit Memory** later without destroying the prior version.
6. **Boxing:** (a) face → shared person + face-learning path; (b) artifact/keepsake/object → box → optional voice transcript → **label as identifier** (also editable/versioned when the label/story is owner text).
7. **Teach feedback:** after any successful owner teach action, MemoryBox **quietly** shows **Archive Updated** (no modal, no celebration spam).
8. **One shared person identity** across Ask hubs, Immich faces, and HVRT gallery for the demonstrator.
9. **Related memories** = soft “also related” from hybrid retrieve (no manual KnowledgeLinks graph).
10. **Immich** is live in-demo for photos/faces.
11. **Always-on** on Media-Server: demonstrator app, HVRT/video path, Ask path, Ollama (via FlightSim), Qdrant, Immich, Whisper—as needed for the demo without a manual “start everything” ritual during the pitch.
12. **Tailscale:** Tom only; access by Tailscale IP + port (no MagicDNS/HTTPS requirement for v1); LAN not exposed to the public internet.

---

## 3. Teach loop — Archive Updated + Edit Memory

### 3.1 Archive Updated (quiet confirmation)

**When:** After any successful **owner teach** that commits evidence to the archive, including at least:
- Save voice note
- Edit / save a new version of a memory
- Face enroll / person link
- Artifact box + label (and label edit)
- Place / date / OCR confirm in Review (owner marks)

**How it feels:** A quiet, non-blocking notice—e.g. soft toast or status line—copy exactly or near: **Archive Updated**. No success modal. No confetti. Disappears on its own. If the write fails, show a clear error instead (never a false Archive Updated).

**Why:** Teaching should feel like adding to a lasting archive, not submitting a form.

### 3.2 Edit Memory (version, do not overwrite)

**Problem:** The pocket watch story recorded tonight will be wrong or incomplete tomorrow. Overwrite destroys provenance and trust.

**Behavior:**
- Owner-authored **memories** (voice notes and their transcripts; artifact **labels/stories**) support **Edit Memory**.
- Edit creates a **new version**; prior version remains stored and auditable.
- **Ask and Library cite the current (latest) version by default.**
- UI can open **version history** (v1, v2, …) with timestamps; older versions are read-only unless explicitly restored (restore = new current version, still keeping history).
- Original **audio blob** for a voice note is not deleted when the transcript/story text is edited; if Tom re-records audio, that is a new version that references new audio + new transcript—old audio kept with old version.
- Provenance: each version is **owner**, with `edited_at` / `version_n`; Evidence Principles—human confirmation still overrides AI; originals of source media (email, video files, Immich assets) remain immutable.

**Demo beat:** Record pocket watch story → Archive Updated → next day Edit Memory → improve transcript/story → Archive Updated → Ask still finds it; history shows both versions.

### 3.3 Relationship to parked Voice Annotate PRD

Capture UX from the parked PRD stays (mic tap start/stop, max 10 min, Whisper, Save).  
**MBD-001 adds:** Archive Updated + Edit Memory / versioning. The parked PRD alone is not sufficient for the demonstrator.

---

## 4. Scope

### 4.1 In

| Area | Demonstrator commitment |
|------|-------------------------|
| **Entity** | New git-rooted demonstrator (cohesive app). **Import** HVRT + Ask codebases; do not leave Ask as Desktop-only untracked code. |
| **Shell** | Curator visual system; dual console **Ask** \| **Review**; Library/Timeline browse. Option B: shared nav, fonts, colors, panels, evidence cards, person chips, teach affordances. |
| **Ask** | Existing email/SMS/calendar/Immich retrieve + answer + citations, served inside the shell. |
| **Review** | Existing HVRT review capabilities inside the shell (modes, hits, player, enroll, Learn, process). |
| **Databases** | **Keep** existing POC databases (`memorybox.db`, `hvrt.sqlite`, Qdrant collection). Add thin **gateway / identity / voice / artifact / memory_versions** tables as needed—no forced mega-migration for v1. |
| **Unified evidence API** | Read-model that normalizes citations/cards from both stores for Ask filmstrip + Library/Timeline (latest memory version). |
| **Shared people** | Single demonstrator person registry (aliases → email/phone/Immich id/HVRT person id). |
| **Voice annotate** | Parked PRD capture + **Edit Memory / versions** + Archive Updated. |
| **Artifact boxing** | Box region on photo/video frame; optional voice→transcript; store label as identifier; editable/versioned label/story; Archive Updated. |
| **Face boxing** | Existing HVRT path, wired to **shared person** + Learn/face recognition tools; Archive Updated on enroll. |
| **Archive Updated** | Shared quiet teach confirmation across Ask / Review / Library teach actions. |
| **Related memories** | Soft retrieve neighbors on an evidence card / Ask follow-up. |
| **Immich** | In-demo photos/faces (API key / env on Media-Server). |
| **Hosting** | App on **Media-Server**; LLM on **FlightSim** (network path required); Tailscale for Tom’s remote access. |

### 4.2 Out (explicit)

- Multi-user auth / family accounts (Tom is the only demonstrator user)
- Guests driving the UI unassisted
- Public internet exposure without Tailscale
- Cloud AI for email/private text
- Full KnowledgeLinks / manual related-memory graph
- Place recognition engine; settings/event engines
- Mobile native apps
- Completing the full Memory Box product / MBAR implementation
- Replacing or rewriting Phase-1 `process_videos` beyond what’s needed to run on Media-Server
- Merging `memorybox.db` + `hvrt.sqlite` into one physical DB (keep both; unify at API/UI)
- Collaborative editing / branching / rich diff UI beyond simple version list + restore
- Versioning of **immutable source archives** (Takeout mail, original video files)—only owner **memories/annotations**

---

## 5. Experience decisions (locked from discovery)

| # | Decision |
|---|----------|
| 1 | No single scripted story required—**both** Ask and Review must work in the demo. Tailscale = secure remote access to Media-Server. |
| 2 | **Dual console** (Ask \| Review), not Ask-only. |
| 3 | Audience = investors + family; **Tom runs**, they watch. |
| 4 | Unified evidence under Ask **and** browseable **timeline/library**. |
| 5 | Voice annotate capture per parked PRD; **plus** Edit Memory / versioning (this v2). |
| 6 | Face box → face learning; artifact/object box → voice (optional) + **label identifier**. |
| 7 | **One shared person identity** across the demonstrator. |
| 8 | Related memories = **soft** retrieve. |
| 9 | Demonstrator is its **own git entity**; import both codebases. |
| 10 | **Keep** existing POC databases. |
| 11 | Immich **in-demo**. |
| 12 | Visual system = **curator**. |
| 13 | UI integration = **Option B** (shared shell + shared patterns; Review restyled, not rewritten into Ask-only). |
| 14 | Host app on **Media-Server**; LLM on **FlightSim**. |
| 15 | Tailscale **Tom only**; IP + port. |
| 16 | Services **stay up**. |
| 17 | Multi-user deferred; demonstrator is single-operator. |
| 18 | Teach confirmation = quiet **Archive Updated**. |
| 19 | Owner memories are **edited and versioned**, never silently overwritten. |

---

## 6. Constraints & dependencies

### Constraints
- Evidence Principles unchanged (grounding, citations, confidence, labeled inference, missing/conflict disclosure, originals immutable, human identity overrides AI).
- Owner > User > AI ranking preserved for HVRT marks; voice notes / artifact labels are **owner** evidence.
- **Versioned memories:** latest is current truth for Ask; history retained; no silent overwrite.
- Local-first custody; no cloud LLM for private mail/SMS.
- Frontend design rules: curator composition, brand-forward, expressive fonts (not Inter/Roboto), atmospheric backgrounds, no generic AI-purple dashboard, no card soup in heroes; Review tools may use interaction cards where needed.
- Do not overwrite Desktop Phase-1 `process_videos.py` with stubs.

### Dependencies
| Dependency | Role |
|------------|------|
| Media-Server | Runs demonstrator UI/API, Immich access, Whisper, DB files, Tailscale serve |
| FlightSim | Ollama (and existing Qdrant if that remains the vector host—confirm in build plan) |
| Tailscale | Tom ↔ Media-Server |
| Immich | Photos/faces API |
| Desktop Ask tree | Source to import into git |
| HVRT branch/`hvrt/` | Source already in repo |
| faster-whisper | Voice annotate + (existing) video ASR family |

### Edge cases
- FlightSim LLM unreachable → Ask degrades with clear “model offline” (Review/Library still usable).
- Immich down → photo evidence omitted with disclosure; face alias from cache if available.
- Person alias conflicts → owner confirmation wins; never silent merge.
- Long video face samples → keep HVRT presence-span merge behavior in Review.
- Tailscale disconnect → LAN access on Media-Server still works for local demo.
- Edit Memory with empty transcript → block save; keep prior version current.
- Re-index after edit → search/Qdrant must point at **latest** text; stale vectors for old versions optional/out of default Ask path.

---

## 7. Architecture sketch (demonstrator, not full MBAR)

```
                    Tailscale (Tom)
                          │
                    Media-Server
            ┌─────────────┴─────────────┐
            │   MemoryBox Demonstrator  │
            │   (one origin / one shell)│
            │  Ask │ Review │ Library   │
            │  + Archive Updated toast  │
            │  + Edit Memory (versions) │
            └─────────────┬─────────────┘
         ┌────────────────┼────────────────┐
         ▼                ▼                ▼
   memorybox.db      hvrt.sqlite      voice/artifact
   (Ask/SMS/…)       (video/faces)   + people registry
                                      + memory_versions
         │                │
         └────────┬───────┘
                  ▼
         Unified evidence read API
         (cite latest memory version)
                  │
         ┌────────┴────────┐
         ▼                 ▼
   Qdrant (vectors)   Immich API
         │
         ▼
   Ollama on FlightSim
```

**UI Option B:** one curator shell; Ask and Review are consoles that share components (evidence card, person chip, teach sheet, Archive Updated, Edit Memory, typography, color tokens).

---

## 8. Build plan (sequencing)

Rough order—no calendar estimates; each step is a vertical that keeps the demo runnable.

1. **Repo entity** — Scaffold demonstrator package; import Ask API/UI from Desktop into git; integrate HVRT module; single process or reverse-proxy one port.
2. **Curator shell + Option B** — Shared layout, tokens, Ask + Review routes; restyle Review; shared **Archive Updated** affordance.
3. **Always-on Media-Server** — Service install/scripts; bind for Tailscale IP; config for FlightSim Ollama (+ Qdrant host decision); health endpoints.
4. **Unified evidence read API** — Normalize cards from both DBs for Ask citations + Library/Timeline browse.
5. **Shared people registry** — Link HVRT people ↔ Immich people ↔ email/SMS hubs; use in face enroll + Ask.
6. **Voice annotate + Edit Memory** — Capture per parked PRD; versioned store; latest indexed; history + restore; Archive Updated on save/edit.
7. **Artifact boxing** — Box + optional voice + label; versioned label/story; Archive Updated.
8. **Soft related memories** — “Also related” on evidence cards via hybrid retrieve.
9. **Demo hardening** — Offline disclosures, sample path checklist, one-page runbook for Tom (include pocket-watch edit beat).

---

## 9. Validation script (Tom-operated)

Not a fixed narrative—checklist that both consoles work:

1. Open demonstrator over Tailscale; show Ask + Review + Library in one chrome.
2. Ask a question that returns email/SMS (+ Immich photo if relevant); open citations.
3. Open Library/Timeline; browse across modalities.
4. In Review: load a Grandpa Sessions face span; show shared person; note quiet **Archive Updated** on enroll.
5. Box a keepsake/object; voice-label; **Archive Updated**; find it again via Ask or Library.
6. Record the **pocket watch** (or any) voice note → **Archive Updated** → Ask cites it.
7. **Edit Memory** on that note → improve text → **Archive Updated** → history shows v1 + v2; Ask uses v2.
8. Show soft “related” on one evidence card.
9. Point out always-on: no restart mid-demo; if FlightSim LLM blips, disclosure is calm and honest.

---

## 10. Open questions

### Resolved in v2 (with recommended defaults)
| Topic | Default locked unless Tom overrides |
|-------|-------------------------------------|
| Archive Updated copy | Exact phrase **Archive Updated** |
| Archive Updated scope | All successful owner teach commits listed in §3.1 |
| Edit Memory scope (v1) | Voice notes + artifact labels/stories (not full HVRT span surgery UI) |
| Ask cites | **Latest** version only by default |
| History | List versions + open prior + **restore** (restore writes a new current version) |

### Still open (non-blocking for sign-off; resolve in build)
1. **Qdrant location** — Remain on FlightSim, or move/replicate beside the app on Media-Server?
2. **Single port** — One listen port (e.g. 8780) vs two internal ports behind one shell origin.
3. **People / versions storage** — New SQLite on Media-Server vs tables inside `memorybox.db`.
4. **Artifact media** — Box on Immich stills only for v1, or also HVRT video frames?
5. **Tailscale port** — Preferred listen port.
6. **Import path** — Exact Desktop Ask folders to copy into git.

### Confirm A (locked 2026-08-05)
**Edit Memory (voice) v1 = edit transcript/story text only.** Saving creates a **new version**; that version is what Ask/Library **search**. Prior versions retained in history. Re-record audio deferred. Never silent overwrite.

### Still open (non-blocking; resolve during import/hosting)
1. **Qdrant location** — Remain on FlightSim, or move/replicate beside the app on Media-Server?
2. **Single port** — One listen port (e.g. 8780) vs two internal ports behind one shell origin.
3. **People / versions storage** — New SQLite on Media-Server vs tables inside `memorybox.db`. *(Demonstrator v1 uses `database/mbd_demonstrator.sqlite` for memories/versions.)*
4. **Artifact media** — Box on Immich stills only for v1, or also HVRT video frames?
5. **Tailscale port** — Preferred listen port (default **8780**).
6. **Import path** — Exact Desktop Ask folders to copy into git *(required for full email/text Ask inside the shell)*.

