# MBBS-P2 Increment MBQL-001 — Ask, Query & Command Language

**Status:** **DRAFT FOR REVIEW** · **NO BUILD** · wait for Tom lock + explicit build authorization  
**Date:** 2026-08-15  
**PRD:** [MBPRD-P2-MBQL-001_ASK_QUERY_COMMAND_LANGUAGE.md](MBPRD-P2-MBQL-001_ASK_QUERY_COMMAND_LANGUAGE.md)  
**Authority:** [MBRM-001A](MBRM-001A_P2_IMPLEMENTATION_PLAN_PROPOSAL.md) · [MBRM-001 v0.2](MBRM-001_v0.2_AI_TRACE_INSERTION.md) · I7A ACCEPTED (trace before model workload grows)  
**Roadmap:** After **P2-I7A ACCEPTED** and **before P2-I8**  
**Depends:** I7A **ACCEPTED** 2026-08-15 · I1–I7 **ACCEPTED** · I4 build authorized / not ACCEPTED  
**Does not reopen / does not absorb:** I7 SMS · **P2-BL-I7-01** · I8 email / **P2-BL-I8-01** · I8.5 · I9 spoken product · I10 · I11 · I13/I14 · family nav · multi-user · Explore redesign

**Planning only.** Do not implement `plan_ask` rewrites, model-assisted compile, or Explore command moves until Tom locks Q1–Q8 **and** authorizes build.

---

## 0. Product intent

> **One typed intent for every Ask, refine, and (later) spoken command — so MemoryBox, Explore, and a model (when used) argue about the same slots, and I7A can tell a compile bug from a retrieve bug from a model bug.**

MBQL-001 is a **foundational language increment**, not a new family screen and not “turn Ask into ChatGPT.”

The family still types English in the existing Ask box. MBQL is the **internal record**:

- who / where / when / what kind of memory  
- new find vs refine vs navigate vs clarify  
- which slots were inherited vs said now  
- whether a model was allowed to fill anything  

I8 is supposed to **reuse** this contract for communication semantics. I9 STT must call it. I10/I11 must not invent a third planner.

---

## 1. Why now (sequence lock)

| Order | Artifact | Role |
|-------|----------|------|
| 1 | **P2-I7** SMS/Text | **ACCEPTED** 2026-08-15 |
| 2 | **P2-I7A** AI Model Trace | **ACCEPTED** 2026-08-15 — observe before we ask models to do more |
| 3 | **MBQL-001** | This draft. Shared compile **before** I8 |
| 4 | **P2-I8** Richer Email | Apply shared MBQL communication semantics + **P2-BL-I8-01** |
| 5 | **P2-I8.5** Face Evidence | Unchanged |
| 6+ | I9 / I10 / I11 | Same contract; do not pull them into MBQL-001 |

**Build rule:** Definition may be locked from this draft. **No runtime** until explicit MBQL-001 build authorization.

---

## 2. Open questions (Tom — lock before build)

Recommended answers are in the [PRD §6](MBPRD-P2-MBQL-001_ASK_QUERY_COMMAND_LANGUAGE.md). Short form:

| # | Topic | Recommended |
|---|--------|-------------|
| **Q1** | Model use | Deterministic first. Model fills **residual** slots only. Not every Ask. |
| **Q2** | Explore commands | Same contract in this increment. No private Explore language. |
| **Q3** | Answers | Normalize intent only. No narrative. |
| **Q4** | Failure | Fail back to deterministic plan or clarification. |
| **Q5** | Speech | STT-ready. Do not build I9. |
| **Q6** | Sequence | I7A → MBQL-001 → I8. I8.5 after I8. |
| **Q7** | Explore UX | Do not redesign I4. |
| **Q8** | Gate | No build until you say so. |

Until Q1–Q8 are confirmed or replaced, this document is **not locked**.

---

## 3. Current code (inspect only)

| Boundary | Path | MBQL-001 role (if built) |
|----------|------|---------------------------|
| Planner | `memorybox/planner/__init__.py` `QueryPlan` + `plan_ask` | **Today’s de facto MBQL.** Extend; do not fork a second dataclass. |
| Temporal | `memorybox/planner/temporal.py` | Keep holiday / season / year windows (I4 all-years Christmas lock). |
| Orchestrator | `memorybox/ask/orchestrator.py` | Consumes the plan; person resolve; retrieve. Must not re-parse English ad hoc. |
| Explore commands | `explore/static/explore.js` `applyAskCommand` | Second language today. Must compile to the same record (Q2). |
| Explore find | `explore/find.py` `build_explore_find` | Empty q stays orchestrator-free. Non-empty q uses Ask. |
| Person scope | `personScopedAsk` + I5 locked person | Inherit locked person unless navigate/switch. |
| I7A | `ai_trace` + `/dev/ai-trace` | Required around any model-assisted compile. T3 remains the common path if Q1 holds. |

`QueryPlan` already has the slots MBQL needs: `person_names` / `person_ids`, `place_names`, `event_labels`, `trip_labels`, `time_start` / `time_end` / `temporal_windows`, `visual_scope`, `want_communication`, story/journal/artifact flags, follow-up / clarification / inheritance notes.

What it **lacks** (draft — lock in build, not now):

- Explicit **act**: `find` · `refine` · `navigate` · `clarify`
- Explicit **modality visibility** (I7 gallery-hide SMS vs retrieve)
- A single **compile provenance**: `deterministic` · `model_fill` · `mixed`
- Shared refine verbs (`only_photos`, `add_texts`, `show_map`, `clear_filters`, `go_to_person`)

---

## 4. Scope

### IN

- Freeze the intent record and act enum.
- One compile entry for Ask + Explore (+ Person inherit).
- Inventory and map existing phrases (server + client).
- If Q1 residual-model: traced, schema-validated slot fill + fail back.
- Prove / FlightSim phrase list.
- Keep planner rules A–H.

### OUT

- Family DSL or extra Ask box.
- Default model-on-every-Ask.
- I8 / I8.5 / I9 product / I10 / I11 / Settings / multi-user.
- I7 attachment bytes. I4 visual redesign.
- New family nav item. Changing I7A retention or putting Trace in family chrome.

---

## 5. Acceptance intent (after a future build — not now)

Pass **all** on FlightSim. Harness ≠ ACCEPTED.

| # | Gate |
|---|------|
| A | Phrase list below: correct act + slots; curator/gallery match today’s good results where the phrase already works |
| B | “Only photos.” ≡ Photos filter (I4 E) |
| C | “show me text messages from Peggy George” stays **zero-model** if Q1 holds; I7A T3-shaped |
| D | Ambiguous referent → clarification, not a silent wrong person |
| E | Model fill (if Q1 allows) visible on `/dev/ai-trace`: context vs payload vs parsed vs disposition |
| F | Forced model/store failure does not 500 the Ask |
| G | No MBQL in family nav; I7A still developer-only |
| H | I7 SMS default-hide on broad asks unchanged |

**Draft FlightSim phrases** (adjust at lock):

1. `show me text messages from Peggy George`  
2. `Show me Peggy`  
3. `Show me Peggy Christmas`  
4. `Only photos.`  
5. `Add texts.`  
6. `Clear filters.`  
7. `Go to Tom instead.` (on a Person surface)  
8. One ambiguous follow-up (`what did she say` / `the other trip`) → clarify  

`prove-mbql-001` (when it exists) is a harness, not ACCEPTED.

---

## 6. Privacy and trace

MBQL plans may name people and quote Ask text. They are **intent**, not Evidence. Any model fill uses I7A redaction-before-write. Do not persist hidden chain-of-thought.

---

## 7. Authorization stop-line

| Step | Status |
|------|--------|
| I7A ACCEPTED | **Yes** 2026-08-15 |
| MBQL-001 PRD + definition draft | **THIS REVISION** — review only |
| Q1–Q8 locked | **OPEN** |
| MBQL-001 build | **NOT AUTHORIZED** |
| I8 / MBQL runtime | **NOT STARTED** |

**Stop.** Reply on Q1–Q8. Do not implement until you lock the definition and explicitly authorize build.
