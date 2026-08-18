# MBBS-P2 Increment MBQL-001 — Ask, Query & Command Language

**Status:** **ACCEPTED** (2026-08-18 — Tom: “MBQL is accepted”) · definition **LOCKED** · PRD **ACCEPTED**  
**Date:** 2026-08-15 (build) · 2026-08-18 (accepted)  
**PRD:** [MBPRD-P2-MBQL-001_ASK_QUERY_COMMAND_LANGUAGE.md](MBPRD-P2-MBQL-001_ASK_QUERY_COMMAND_LANGUAGE.md)  
**Authority:** Tom lock 2026-08-15 · owner pass 2026-08-18 · [MBRM-001A](MBRM-001A_P2_IMPLEMENTATION_PLAN_PROPOSAL.md) · [MBRM-001 v0.2](MBRM-001_v0.2_AI_TRACE_INSERTION.md) · I7A **ACCEPTED**  
**Roadmap:** After **P2-I7A ACCEPTED** and **before P2-I8**  
**Depends:** I7A **ACCEPTED** 2026-08-15 · I1–I7 **ACCEPTED** · I4 build authorized / not ACCEPTED  
**Does not reopen / does not absorb:** I7 SMS · **P2-BL-I7-01** · I8 email / **P2-BL-I8-01** · I8.5 · **I9 spoken product** (stays after I8.5) · I10 · I11 · I13/I14 · family nav · multi-user · Explore redesign

**MBQL-001 is ACCEPTED.** Q1 residual · Q2 shared Explore contract. Do not start I8 until Tom authorizes that increment. I4 §8 + §8.1 remains the Explore owner pass.

---

## 0. Product intent

> **One typed intent for every Ask, refine, and (later) spoken command — so MemoryBox, Explore, and a model (when used) argue about the same slots, and I7A can tell a compile bug from a retrieve bug from a model bug.**

MBQL-001 is a **foundational language increment**, not a new family screen and not “turn Ask into ChatGPT.”

The family still types English in the existing Ask box. MBQL is the **internal record**:

- who / where / when / what kind of memory  
- new find vs refine vs navigate vs clarify  
- which slots were inherited vs said now  
- compile provenance: deterministic, residual model fill, or mixed  

I8 **reuses** this contract for communication semantics. I9 STT **calls** it when I9 is built (I9 stays in its roadmap position after I8.5). I10/I11 must not invent a third planner.

---

## 1. Why now (sequence lock)

| Order | Artifact | Role |
|-------|----------|------|
| 1 | **P2-I7** SMS/Text | **ACCEPTED** 2026-08-15 |
| 2 | **P2-I7A** AI Model Trace | **ACCEPTED** 2026-08-15 — observe before models do more |
| 3 | **MBQL-001** | **ACCEPTED** 2026-08-18. Shared compile **before** I8 |
| 4 | **P2-I8** Richer Email | Shared MBQL communication semantics + **P2-BL-I8-01** |
| 5 | **P2-I8.5** Face Evidence | Unchanged |
| 6 | **P2-I9** Spoken Moments | **Stays here.** STT-ready contract only in MBQL-001; no I9 product |
| 7+ | I10 / I11 | Same contract; do not pull them into MBQL-001 |

**Build rule:** Definition locked. Build authorized 2026-08-15. Increment **ACCEPTED** 2026-08-18. Do not start I8.

---

## 2. Locked decisions (Tom, 2026-08-15)

| # | Topic | Locked answer |
|---|--------|---------------|
| **Q1** | Model use | **Residual.** Deterministic compile first. Model fills missing or ambiguous slots on the **same schema**. Not every Ask to Ollama. Complete deterministic compiles stay **zero-model** (I7A T3). |
| **Q2** | Explore commands | **Confirm.** Same contract in MBQL-001. No private Explore language. Client may keep instant UI; it must emit/consume the same record. “Only photos.” ≡ Photos filter (I4 E). |
| **Q3** | Answers | **Confirm.** Normalize intent only. Retrieve and curator stay as they are unless a compile bug is proven. No narrative (not I11). |
| **Q4** | Failure | **Confirm.** Fail back to deterministic `plan_ask` or clarification. Never fail the Ask because MBQL, model, or trace-store failed. |
| **Q5** | Speech | **Confirm.** STT-ready contract. **I9 stays in its position** (after I8.5). Do not build spoken moments in MBQL-001. Later STT must call the same compile. |
| **Q6** | Sequence | **Confirm.** I7A ACCEPTED → MBQL-001 → I8. I8.5 remains after I8. |
| **Q7** | Explore UX | **Confirm.** Do not redesign I4. MBQL sits under the current Explore Ask row. |
| **Q8** | Build gate | **Confirm, then authorized.** Tom 2026-08-15: “approved to build.” |

### Additional locked rules (same day)

1. Extend today’s `QueryPlan`. Do not fork a second intent object.  
2. Keep planner rules A–H (current utterance > inherit; typed slots; disclose ambiguity; displayed context = retrieval context).  
3. I7 gallery default-hide SMS on broad asks is unchanged. Visibility ≠ exclusion.  
4. Empty Explore boot stays orchestrator-free.  
5. Any residual model fill is traced on I7A (assembled context vs exact payload vs parsed vs disposition).  
6. Bare holiday “Christmas” still expands across all years (I4 lock).  
7. Person Explorer refinements inherit the locked person unless the act is navigate/switch.

---

## 3. Current code (build authorized)

| Boundary | Path | Locked role when built |
|----------|------|------------------------|
| Planner | `memorybox/planner/__init__.py` `QueryPlan` + `plan_ask` | **Today’s de facto MBQL.** Extend this record. Deterministic first (Q1). |
| Temporal | `memorybox/planner/temporal.py` | Keep holiday / season / year windows. |
| Orchestrator | `memorybox/ask/orchestrator.py` | Consumes the plan. Must not re-parse English ad hoc. |
| Explore commands | `explore/static/explore.js` `applyAskCommand` | Must compile to the same record (Q2). |
| Explore find | `explore/find.py` `build_explore_find` | Empty q: no orchestrator. Non-empty q: Ask. |
| Person scope | `personScopedAsk` + I5 locked person | Inherit locked person unless navigate/switch. |
| I7A | `ai_trace` + `/dev/ai-trace` | Required on residual model fill. Zero-model Asks still get an end-to-end T3 trace. |

`QueryPlan` already has: `person_names` / `person_ids`, `place_names`, `event_labels`, `trip_labels`, `time_start` / `time_end` / `temporal_windows`, `visual_scope`, `want_communication`, story/journal/artifact flags, follow-up / clarification / inheritance.

**Added this build:**

- **act:** `find` · `refine` · `navigate` · `clarify`  
- **compile_provenance:** `deterministic` · `model_fill` · `mixed`  
- Shared refine verbs: `only_photos`, `add_texts`, `show_map`, `clear_filters`, `go_to_person`, …  
- I7 **visibility** vs retrieve (gallery-hide SMS)

---

## 4. Compile path (locked)

```text
utterance
  → deterministic plan_ask / shared refine map
      → complete?  → QueryPlan (provenance=deterministic) → retrieve as today
      → residual missing/ambiguous slots?
            → traced model fill of those slots only (same schema)
            → parse + trust validate
            → ok → QueryPlan (provenance=mixed|model_fill) → retrieve
            → fail → Q4 fail back to deterministic plan or clarification
```

Residual means: a slot the deterministic compiler could not fill, or an ambiguity it already marks for clarification. The model must **not** invent extra people, dates, or modalities. Extra slots in the model return are rejected or clarified (not retrieved).

---

## 5. Scope

### IN (this authorized build)

- Freeze the intent record and act enum on `QueryPlan`.  
- One compile entry for Ask + Explore + Person inherit.  
- Inventory and map every `plan_ask` path and every `applyAskCommand` phrase.  
- Residual model fill: traced, schema-validated, fail back (Q1 + Q4).  
- Prove harness + FlightSim phrase list.  
- Keep planner rules A–H.

### OUT

- Family DSL or extra Ask box.  
- Default model-on-every-Ask.  
- I8 richer email / **P2-BL-I8-01**.  
- I8.5 face SoT.  
- **I9 spoken product** (position unchanged; contract only).  
- I10 correlation · I11 narrative · I13 views · I14 Settings · multi-user.  
- **P2-BL-I7-01** SMS attachment bytes. Reopen I7 / I7A.  
- I4 Explore visual redesign.  
- Family nav item. Putting `/dev/ai-trace` in family chrome.

---

## 6. Acceptance intent (FlightSim owner pass)

Pass **all** on FlightSim. `prove-mbql-001` is a harness (structural assist). Increment **ACCEPTED** 2026-08-18 (Tom: “MBQL is accepted”).

| # | Gate |
|---|------|
| A | Phrase list: correct act + slots; curator/gallery match today’s good results where the phrase already works |
| B | “Only photos.” ≡ Photos filter (I4 E) |
| C | `show me text messages from Peggy George` stays **zero-model**; I7A T3-shaped |
| D | Ambiguous referent → clarification, not a silent wrong person |
| E | A residual model-fill phrase is visible on `/dev/ai-trace`: context vs payload vs parsed vs disposition |
| F | Forced model/store failure does not 500 the Ask (Q4) |
| G | No MBQL in family nav; I7A still developer-only |
| H | I7 SMS default-hide on broad asks unchanged |

**FlightSim phrases**

1. `show me text messages from Peggy George` — find, SMS, Peggy George, zero-model  
2. `Show me Peggy` — find, person, zero-model  
3. `Show me Peggy Christmas` — find, person + holiday-all-years, zero-model  
4. `Only photos.` — refine ≡ Photos filter  
5. `Add texts.` — refine; gallery shows SMS  
6. `Clear filters.` — refine reset  
7. `Go to Tom instead.` on a Person surface — navigate, not a find  
8. One residual/ambiguous follow-up (`what did she say` / `the other trip`) — clarify or traced residual fill  

`prove-mbql-001` is a harness (structural assist). Increment **ACCEPTED** 2026-08-18 (Tom: “MBQL is accepted”).

---

## 7. Privacy and trace

MBQL plans may name people and quote Ask text. They are **intent**, not Evidence. Residual model fill uses I7A redaction-before-write. Do not persist hidden chain-of-thought.

---

## 8. Authorization stop-line

| Step | Status |
|------|--------|
| I7A ACCEPTED | **Yes** 2026-08-15 |
| MBQL-001 PRD | **ACCEPTED** 2026-08-15 (Tom Q1–Q8) |
| MBQL-001 definition | **LOCKED** |
| MBQL-001 build | **AUTHORIZED** 2026-08-15 |
| MBQL-001 ACCEPTED | **Yes** (2026-08-18 — Tom: “MBQL is accepted”) |
| I8 / I9 runtime | **NOT STARTED** |

**Stop.** Do not start I8 until Tom authorizes I8. **I4 §8 + §8.1** is still the Explore owner pass and must actually work. Do not reopen MBQL-001.
