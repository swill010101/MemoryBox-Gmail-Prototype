# MBPRD-P2-MBQL-001 — Ask, Query & Command Language

**Status:** **DRAFT FOR REVIEW** · **NO BUILD** · wait for Tom lock + explicit build authorization  
**Date:** 2026-08-15  
**Increment definition:** [MBBS-P2_INCREMENT_MBQL_001_DEFINITION.md](MBBS-P2_INCREMENT_MBQL_001_DEFINITION.md)  
**Depends:** P2-I7A **ACCEPTED** (2026-08-15) · I1–I7 **ACCEPTED** · I4 build authorized / not ACCEPTED  
**Does not start:** I8 email · I8.5 face SoT · I9 spoken product · I10 correlation · I11 narrative · Settings · multi-user

This is a planning PRD. It does **not** authorize implementation.

---

## 1. Problem being solved (and why it matters now)

Family historians type (and will later speak) one Ask box. MemoryBox must turn that utterance into a **typed intent** the rest of the product can retrieve, filter, and explain.

Today that job is split and brittle:

1. **Server `plan_ask`** (`memorybox/planner`) is a large regex / rule compiler. It already does a lot: person, place, time/holiday windows, SMS vs email vs photo vs video, kinship cues, follow-ups, clarification. Most production Asks **never call a model** (I7A T3 path). Tom’s “show me text messages from Peggy George” worked on that path.
2. **Explore `applyAskCommand`** (`explore.js`) is a **second** command language: “Only photos.”, “Add texts.”, “Show map.”, “Clear filters.”, person-switch phrases. Some of those never hit `plan_ask`. Clicking a type filter must match typing the same command (I4 §2.2 / §8.1 E).
3. The two compilers **drift**. A phrase that is a refine on Explore can be a new find on Ask, or the reverse. Person + time + place + modality + SMS compose only when both sides happen to agree.
4. I8 / I9 / I10 / I11 will make interpretation harder (richer email, speech, correlation, narrative). I7A exists so we can see whether a bad result is **Python/orchestrator** or **model/provider**. That only helps if there is a **single contract** the model is allowed to fill.

**Why now:** I7A is ACCEPTED. The roadmap lock is I7 → I7A → **MBQL-001** → I8. Doing I8 (or “just send every Ask to Ollama”) without a shared language would multiply untraceable intent bugs.

**What MBQL is not:** a family-facing query syntax (not SQL, not a new box). The family still types English. MBQL is the **internal semantic contract** between utterance, planner, orchestrator, Explore/Person chrome, and (later) STT.

---

## 2. Success criteria (how we’ll know it works)

After a future authorized build (not this draft):

1. **One contract.** Ask, Explore refine, Person-scoped Ask, and filter chips describe the same typed intent (person / place / time / modality / communication / navigation).
2. **One compiler entry.** Typed Ask and the equivalent click produce the same plan fields and the same visible filter/result interpretation (I4 equivalence preserved).
3. **Deterministic first.** Utterances that `plan_ask` already handles well stay **zero-model** unless Tom locks otherwise. I7A still shows a complete T3 trace.
4. **Model only for residual work.** If a model fills slots, I7A shows assembled MB context vs exact provider payload, parse/validate, and disposition. A bad fill is `PARSE_SCHEMA` / `TRUST_VALIDATION` / `MODEL_OUTPUT`, not “AI error.”
5. **Fail back.** Model/planner failure must not fail the user request. Fall back to today’s deterministic plan (or clarification). Trace-store failure still never fails Ask (I7A lock).
6. **No answer invention.** MBQL names intent. Retrieve and curator remain evidence-backed. MBQL-001 does not become I11 narrative.
7. **FlightSim owner pass** on a short locked phrase list (below) with `/dev/ai-trace` available. `prove-mbql-001` is a harness, not ACCEPTED.

---

## 3. Scope

### IN (this increment, if later authorized)

- Name and freeze the **MBQL intent record** (extend today’s `QueryPlan`, do not invent a parallel object).
- Classify every current Ask/Explore phrase as: **new find** · **refine current set** · **navigate** · **clarify**.
- Route Explore refine commands through the same contract (server or shared module — lock in Q2).
- Keep planner rules A–H (current utterance > inherit; typed slots; disclose ambiguity; displayed context = retrieval context).
- Optional **model-assisted slot fill** only when deterministic compile is incomplete or ambiguous — **Q1**.
- I7A spans on any model fill (planner / prompt_build / provider_call / parse_validate).
- A thin prove list + FlightSim phrase list. No new family surface.

### OUT (explicit)

- Family-facing query language, DSL, or “power user” syntax.
- Sending **every** Ask to a model by default.
- I8 richer email ingest or **P2-BL-I8-01** attachment files.
- I8.5 face evidence ownership.
- I9 STT product (contract must be **STT-ready**; do not build speech).
- I10 correlation, I11 narrative, I13 Living Album / views, I14 Settings.
- SMS attachment bytes **P2-BL-I7-01**. Reopen I7 / I7A.
- Explore visual redesign (I4 interaction reference stays).
- Family nav change. `/dev/ai-trace` stays developer-only.
- Multi-user. Confidence dials. Asking the model to explain hidden reasoning.

---

## 4. Constraints, dependencies, edge cases

**Dependencies**

- I7A ACCEPTED — traces must stay on for any model-assisted compile.
- Current `QueryPlan` + Explore domain state (type filter, place, undated, timeline, `includeTexts` / gallery SMS hide).
- Person lock on Person Explorer (I5): refinements inherit the locked person unless the owner switches.

**Constraints**

- Evidence first. MBQL must not invent people, dates, or messages.
- Ambiguity is disclosed, not guessed (planner rule F).
- Default Gallery still hides SMS on broad memory asks (I7). “Add texts” / “Only texts” / explicit text asks override. Visibility ≠ exclusion.
- Warm Ask cost today is ~6 s retrieve for Peggy texts; Trace persist is ~80 ms. MBQL must not put a model call on the common path without Tom locking that cost.
- Cold orchestrator (~60 s first Ask) is provider init, not MBQL. Do not “fix” it by skipping I7A.

**Edge cases the definition must cover**

| Case | Today | MBQL must |
|------|--------|-----------|
| “Only photos.” after a find | Explore local refine | Same contract as Photos filter; not a new person-less photo search unless owner asked that |
| “Show me text messages from Peggy George” | Deterministic SMS retrieve | Stay zero-model if compile is complete |
| “Show me Peggy” vs “Show me Peggy in 2021” | Person vs person+time | Slots compose; do not drop time |
| “Go to Tom instead.” on Person | Client navigate | Navigate, not a find for “Tom instead” |
| “What did she say about Alaska?” | Weak / regex | Clarify or model-fill **referent** + place; do not invent speech (I9) |
| Bare holiday “Christmas” | I4: all years | Keep I4 lock |
| Empty Explore boot | No orchestrator | Unchanged |
| Model returns extra person | — | Reject / clarify; do not retrieve the extra person |

---

## 5. Build plan (sequencing only — not authorized)

Do **not** execute until Tom locks Q1–Q8 and says to build.

1. Freeze the intent record (fields, enums, refine vs find vs navigate).
2. Inventory every `plan_ask` path and every `applyAskCommand` phrase; map each to the record.
3. Single compile function used by Ask + Explore (+ Person scope).
4. If Q1 = model residual only: traced fill + schema validate + fail back.
5. Prove harness + FlightSim phrase list.
6. **Stop.** Do not start I8.

---

## 6. Open questions for Tom

| # | Topic | Recommended answer (for you to confirm or replace) |
|---|--------|-----------------------------------------------------|
| **Q1** | How much model? | **Residual only.** Deterministic compile first. Model fills missing/ambiguous slots on the **same schema**. Not “every Ask goes to Ollama.” |
| **Q2** | Explore commands | **Same contract in MBQL-001.** Prefer one server/shared compile. Client may keep instant UI, but must not keep a private language. |
| **Q3** | Change answers? | **Normalize intent only.** Retrieve/curator stay as they are unless a compile bug is proven. No narrative. |
| **Q4** | Fail path | **Fail back** to deterministic `plan_ask` or clarification. Never fail the Ask because MBQL/model/store failed. |
| **Q5** | Speech | **STT-ready contract.** Do not build I9. Later STT must call the same compile. |
| **Q6** | Sequence | **Confirm.** I7A ACCEPTED → MBQL-001 → I8. I8.5 remains after I8. |
| **Q7** | I4 Explore | **Do not redesign.** MBQL sits under the current Explore Ask row. |
| **Q8** | Build gate | **Confirm.** This draft may be locked as definition. **No runtime** until you explicitly authorize MBQL-001 build. |

Push back once if you want to skip this PRD: locking Q1–Q8 is cheaper than a planner rewrite that sends every Ask to the model.

---

## 7. Decision this PRD is asking for

1. Is the problem statement right?  
2. Is Q1 (deterministic first, model residual only) the product you want?  
3. Any IN/OUT row you want flipped before lock?  
4. **Do not authorize build** until the increment definition is locked.

Reply with confirms / replacements on Q1–Q8. Planning only until then.
