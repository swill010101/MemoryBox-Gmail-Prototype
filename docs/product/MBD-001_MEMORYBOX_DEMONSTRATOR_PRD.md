# MBD-001 — MemoryBox Demonstrator PRD

**Status:** Draft — awaiting Tom sign-off (do not build until Approved)  
**ID:** MBD-001  
**Owner:** Tom Will (sole demonstrator user; multi-user deferred)  
**Charter:** Integrate the existing HVRT POC and email/text search POC into a single coherent application. Add only the minimum new capabilities required to demonstrate the MemoryBox experience. Goal = **validation of the product experience**, not completion of the product. Host on **Media-Server**, reachable outside the LAN via **Tailscale** (Tom only).

**Depends on / imports:**
- HVRT R2 review + Learn (`hvrt/` — faces, speech, places, OCR, video transcripts)
- Email/text Ask historian POC (Desktop `application/api`, retrieve/Qdrant/Ollama — to be brought into git as part of this entity)
- Parked [MEMORYBOX_VOICE_ANNOTATE_PRD.md](../../hvrt/docs/MEMORYBOX_VOICE_ANNOTATE_PRD.md) (adopt as-is for MBD-001)
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

**Why now:** Validate the Memory Box *experience* with a coherent demonstrator on Media-Server + Tailscale, before investing in full product completion.

---

## 2. Success criteria

Tom runs a live demo; investors/family watch. Unassisted use by guests is **out**. Success when:

1. **One app URL** on Media-Server (via Tailscale IP + port) opens a **dual-console** Memory Box: **Ask** | **Review** (and Library/Timeline), with **shared curator chrome** (Option B).
2. **Ask works** as today for email/text (and Immich photos): question → narrative → supporting evidence.
3. **Review works** as today for HVRT video teach/learn (faces, speech, places, OCR, Learn), restyled into curator patterns—not a bolted-on teal operator skin.
4. **Unified evidence** appears under Ask answers **and** in a **browseable timeline/library** (email, SMS, photo, video hit, voice note).
5. **Voice annotate** (parked PRD): Record → Stop → transcript → Save → searchable/citable like other modalities.
6. **Boxing:** (a) face → shared person + face-learning path; (b) artifact/keepsake/object → box → optional voice transcript → **label as identifier**.
7. **One shared person identity** across Ask hubs, Immich faces, and HVRT gallery for the demonstrator.
8. **Related memories** = soft “also related” from hybrid retrieve (no manual KnowledgeLinks graph).
9. **Immich** is live in-demo for photos/faces.
10. **Always-on** on Media-Server: demonstrator app, HVRT/video path, Ask path, Ollama (via FlightSim), Qdrant, Immich, Whisper—as needed for the demo without a manual “start everything” ritual during the pitch.
11. **Tailscale:** Tom only; access by Tailscale IP + port (no MagicDNS/HTTPS requirement for v1); LAN not exposed to the public internet.

---

## 3. Scope

### 3.1 In

| Area | Demonstrator commitment |
|------|-------------------------|
| **Entity** | New git-rooted demonstrator (cohesive app). **Import** HVRT + Ask codebases; do not leave Ask as Desktop-only untracked code. |
| **Shell** | Curator visual system; dual console **Ask** \| **Review**; Library/Timeline browse. Option B: shared nav, fonts, colors, panels, evidence cards, person chips, teach affordances. |
| **Ask** | Existing email/SMS/calendar/Immich retrieve + answer + citations, served inside the shell. |
| **Review** | Existing HVRT review capabilities inside the shell (modes, hits, player, enroll, Learn, process). |
| **Databases** | **Keep** existing POC databases (`memorybox.db`, `hvrt.sqlite`, Qdrant collection). Add thin **gateway / identity / voice / artifact** tables as needed—no forced mega-migration for v1. |
| **Unified evidence API** | Read-model that normalizes citations/cards from both stores for Ask filmstrip + Library/Timeline. |
| **Shared people** | Single demonstrator person registry (aliases → email/phone/Immich id/HVRT person id). |
| **Voice annotate** | As parked PRD: browser mic, local faster-whisper, Save, owner provenance, searchable. |
| **Artifact boxing** | Box region on photo/video frame; optional voice→transcript; store label as identifier; cite in Ask/Library. |
| **Face boxing** | Existing HVRT path, wired to **shared person** + Learn/face recognition tools. |
| **Related memories** | Soft retrieve neighbors on an evidence card / Ask follow-up. |
| **Immich** | In-demo photos/faces (API key / env on Media-Server). |
| **Hosting** | App on **Media-Server**; LLM on **FlightSim** (network path required); Tailscale for Tom’s remote access. |

### 3.2 Out (explicit)

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

---

## 4. Experience decisions (locked from discovery)

| # | Decision |
|---|----------|
| 1 | No single scripted story required—**both** Ask and Review must work in the demo. Tailscale = secure remote access to Media-Server. |
| 2 | **Dual console** (Ask \| Review), not Ask-only. |
| 3 | Audience = investors + family; **Tom runs**, they watch. |
| 4 | Unified evidence under Ask **and** browseable **timeline/library**. |
| 5 | Voice annotate PRD **as-is**. |
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

---

## 5. Constraints & dependencies

### Constraints
- Evidence Principles unchanged (grounding, citations, confidence, labeled inference, missing/conflict disclosure, originals immutable, human identity overrides AI).
- Owner > User > AI ranking preserved for HVRT marks; voice notes / artifact labels are **owner** evidence.
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

---

## 6. Architecture sketch (demonstrator, not full MBAR)

```
                    Tailscale (Tom)
                          │
                    Media-Server
            ┌─────────────┴─────────────┐
            │   MemoryBox Demonstrator  │
            │   (one origin / one shell)│
            │  Ask │ Review │ Library   │
            └─────────────┬─────────────┘
         ┌────────────────┼────────────────┐
         ▼                ▼                ▼
   memorybox.db      hvrt.sqlite      voice/artifact
   (Ask/SMS/…)       (video/faces)   + people registry
         │                │
         └────────┬───────┘
                  ▼
         Unified evidence read API
                  │
         ┌────────┴────────┐
         ▼                 ▼
   Qdrant (vectors)   Immich API
         │
         ▼
   Ollama on FlightSim
```

**UI Option B:** one curator shell; Ask and Review are consoles that share components (evidence card, person chip, teach sheet, typography, color tokens).

---

## 7. Build plan (sequencing)

Rough order—no calendar estimates; each step is a vertical that keeps the demo runnable.

1. **Repo entity** — Scaffold `application/` (or `mbd/`) demonstrator package; import Ask API/UI from Desktop into git; park HVRT as integrated module; single process or reverse-proxy one port.
2. **Curator shell + Option B** — Shared layout, tokens, Ask + Review routes; restyle Review controls to curator patterns without dropping HVRT capabilities.
3. **Always-on Media-Server** — Service install/scripts; bind for Tailscale IP; config for FlightSim Ollama (+ Qdrant host decision); health endpoints.
4. **Unified evidence read API** — Normalize cards from both DBs for Ask citations + Library/Timeline browse.
5. **Shared people registry** — Link HVRT people ↔ Immich people ↔ email/SMS hubs; use in face enroll + Ask.
6. **Voice annotate** — Implement parked PRD against demonstrator search index.
7. **Artifact boxing** — Box + optional voice transcript + label identifier; show in Library and Ask.
8. **Soft related memories** — “Also related” on evidence cards via hybrid retrieve.
9. **Demo hardening** — Offline disclosures, sample path checklist, one-page runbook for Tom.

---

## 8. Validation script (Tom-operated)

Not a fixed narrative—checklist that both consoles work:

1. Open demonstrator over Tailscale; show Ask + Review + Library in one chrome.
2. Ask a question that returns email/SMS (+ Immich photo if relevant); open citations.
3. Open Library/Timeline; browse across modalities.
4. In Review: load a Grandpa Sessions face span; show shared person; optional Learn status.
5. Box a keepsake/object; voice-label; find it again via Ask or Library.
6. Record a voice note; Ask a question that cites it.
7. Show soft “related” on one evidence card.
8. Point out always-on: no restart mid-demo; if FlightSim LLM blips, disclosure is calm and honest.

---

## 9. Open questions (non-blocking for sign-off; resolve in build)

1. **Qdrant location** — Remain on FlightSim, or move/replicate beside the app on Media-Server for fewer moving parts?
2. **Single port** — Prefer one HTTPS/HTTP port (e.g. 8780) reverse-proxying Ask+Review vs two internal ports behind one shell origin.
3. **People registry storage** — New SQLite on Media-Server vs tables inside `memorybox.db`.
4. **Artifact media** — Box on Immich stills only for v1, or also HVRT video frames?
5. **Tailscale port** — Confirm preferred listen port and whether MagicDNS name is optional later.
6. **Import path** — Exact Desktop folders/files Tom will provide or sync for the Ask tree (agent cannot see untracked Desktop code until copied into git).

---

## 10. Sign-off

| Role | Decision |
|------|----------|
| Tom | Approve / request changes / defer |

**Approval means:** implement MBD-001 per this PRD (build plan order), creating implementation branches as needed; no silent scope expansion into Out list.

**Status after approval:** change header to `Approved (Tom) — implement` and date it.
