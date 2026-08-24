# MBAS-P2-I11 — Narrative Evidence Preparation (founder lock)

**Status:** Planning assessment **LOCKED** 2026-08-24 (founder direction on I11 narration prep)  
**Does not start:** LLM synthesis implementation · Email authored-body persist · I13 Save View UI · `/narration/ui`  
**Depends on:** [MBAS-P2-I11](MBAS-P2-I11_NARRATION_LIVING_VIEW_ASSESSMENT.md) · I10C Journal **ACCEPTED**  
**Build:** I10C wait is **cleared**. **Do not implement** this preparation/synthesis layer until Tom gives explicit build authorization on **this** contract (not the earlier deterministic-stitch default).

Parent MBAS direction remains correct: Narration is Ask `output_mode`, not a new app. This note **supersedes** the earlier default “v1 = deterministic stitch, no tell-model.”

---

## Pipeline (locked)

```
Raw archive evidence
  → deterministic retrieval / eligibility / filters
  → Narrative Evidence Preparation (normalized pack)
  → LLM synthesis (tell only; I7A-traced)
```

The model receives the **smallest complete evidence representation** needed for that Ask. It does **not** clean the archive, elect Spam/Trash, or decide trust.

---

## 1. Proposed normalized evidence-pack structure

One pack per `tell` Ask. Same schema for Explore and Person Explorer.

```json
{
  "schema_version": 1,
  "ask": {
    "original_ask": "…",
    "output_mode": "tell",
    "plan": { }
  },
  "scope": {
    "breadth": "narrow | broad",
    "owner_person_id": null,
    "people": [],
    "time": { "windows": [], "label": null },
    "places": [],
    "events_trips": [],
    "topic": null,
    "modalities": ["communication", "calendar", "journal"]
  },
  "units": [],
  "coverage": {
    "summary": "",
    "missing": [],
    "conflicts": [],
    "excluded": ["spam", "trash"]
  },
  "volume": {
    "retrieved_n": 0,
    "prepared_n": 0,
    "truncated": false,
    "reduction": "rank | chunk | hierarchical_summary"
  }
}
```

### Unit (all types)

| Field | Role |
|---|---|
| `unit_id` | Stable in this pack |
| `kind` | `communication` \| `calendar` \| `photo` \| `video_moment` \| `journal` \| `story` \| `artifact` \| `spoken` \| `document` |
| `time` | ISO timestamp or described date + precision |
| `people` | `{ person_id, display_name, role }` — speaker / participant / attendee / depicted / author |
| `place` | Label + id when known |
| `content` | Human-relevant text only (authored body, caption, transcript **excerpt**, notes) |
| `provenance` | `{ source_kind, source_id, evidence_id, original_ref }` — never drop |
| `rank` | Deterministic relevance |
| `normalization` | `{ confidence, flags }` e.g. `quote_uncertain`, `group_thread` |

### Communication unit (Email + SMS — one shape)

| Field | Role |
|---|---|
| `source_type` | `email` \| `sms` \| `imessage` \| `mms` |
| `thread_id` | Conversation / RFC-ish thread |
| `subject` | Email subject / SMS group name when useful |
| `speaker_person_id` | Canonical author when known |
| `participants` | Full participant set (group threads keep extras in metadata) |
| `group_thread` | True when more than owner + named people |
| `authored_text` | Derived; not the quoted dump |
| `attachments` | References only |
| `authored_by_focus` | True if speaker is in the Ask’s people (e.g. Peggy or owner) |

Photos: date, people, place, caption, visual observations, provenance — not Immich internal IDs.  
Video: timeslot + spoken excerpt for that moment — not a two-hour transcript.  
Journal/Story: **current saved** body, author, described date, links — not obsolete versions unless the Ask is about history.  
Calendar: title, when, place, attendees, notes, provenance. Scheduled ≠ occurred unless corroborated.

Saved View persistable JSON (I11 emit, I13 store) stays:

```json
{ "schema_version", "original_ask", "output_mode", "plan", "presentation" }
```

Do not persist the LLM essay as the Saved View. User-facing I13 names: **Save View** / **Saved View** (live recompute). Not **Living Album**. Keep Curated Collection and Snapshot distinct.

---

## 2. Email parsing / dedup — current vs gap

**Have**

- Ingest stores `body_text` / `body_html`, headers, `thread_id`, `in_reply_to` / `references`, `from_owner`, `identity_resolution.mapped`, attachments, `gmail_labels`, `mailbox_skip`.
- Viewer helper `split_quoted_email` (`memorybox/explore/email_attach.py`) splits on `On … wrote:` and `-----Original Message-----` for the rail. I8 prove covers quoted **turns**, not authored-only persistence.
- Ask retrieve (`search_email_messages`) matches person ids, confirmed addresses, display names, windows, keywords. Hit `excerpt` is `_excerpt(..., limit=800)` of stored body — typically the **raw** MIME text including quotes.

**Gaps (block safe model input)**

- No persisted **authored-message** row. Quotes, signatures, confidentiality, HTML, tracking, forward headers stay in `body_text`.
- No `>`-prefix quote strip; no signature heuristic; no duplicate-authored-sentence collapse across a thread.
- Speaker on a quoted turn is a display string from a header regex, not canonical Person.
- Participant filter for “Peggy and I” does not drop Rick/Sue **authored** lines while keeping group-thread metadata.
- If quote removal is uncertain, there is no `quote_uncertain` flag — nothing conservative to send.

---

## 3. SMS representation — current vs gap

**Have**

- Per-message Evidence: `body_text`, `sent_at`, `thread_id`, `participants`, `sender_name`, `from_owner`, `person_ids`, attachments, channel.
- Duplicate signature skip (thread + time + normalized body).
- “Peggy and I” style asks already restrict to owner- or Peggy-authored senders in groups (`retrieve.py`).

**Gaps**

- No shared Communication Evidence type with Email (two retrieve functions, two hit builders).
- Speaker is `from_owner` / name / person_ids — not a single `speaker_person_id` on a normalized unit.
- Group-thread **metadata** is not a first-class `group_thread` flag on Ask statements.
- Bodies are already “authored” more often than email; still no pack-time participant filter unified with email.

---

## 4. Spam / Trash eligibility — current vs gap

**Have**

- Gmail Takeout labels → `mailbox_skip` `spam` | `trash` (`mbox_parse.gmail_mailbox_skip`).
- Default **ingest** skips Spam/Trash (`--include-spam-trash` to keep rows). Originals are never rewritten.
- Story evidence search **excludes** `mailbox_skip` / labels spam|trash|junk (`story/search.py` `_is_spam_or_trash`).

**Gap**

- `search_email_messages` / Ask retrieve **do not** filter `mailbox_skip`. If spam/trash was ingested, it can enter Ask and would enter a tell pack.
- No Ask-time eligibility layer that excludes before any model call.
- No user intent path to search Spam/Trash (correctly out of I11).

---

## 5. Calendar normalization — current vs gap

**Have**

- `calendar_event` Evidence: title, start, location, organizer, attendees, description, `person_ids`, `event_uid`.
- `search_calendar_events`: temporal windows + person id / name / confirmed email in blob. Cap then chronological slice.

**Gaps**

- Narrow discussion Asks still pull any in-window event that mentions the person — not “materially related to the thread / place / topic.”
- Broad year Asks can dump a huge attendee/title list with no significance ranking.
- No “scheduled vs corroborated occurred” disclosure in a pack unit.
- Same 25k retrieve cap family as SMS (`SMS_RETRIEVE_CAP`) — volume, not relevance.

---

## 6. Broad pack reduction without losing provenance

**Today:** retrieve-all-matching then `limit` / `truncated` / first-N excerpts. I10 `coverage` counts gaps. No staged “organize → dedupe → significance → compact units.”

**I11 must (when built)**

1. Retrieve eligible evidence (spam/trash already out).  
2. Organize by time / thread / event.  
3. Dedupe (message ids, SMS sig, quoted copies).  
4. Rank for **this Ask** (narrow vs broad).  
5. Emit compact units with `provenance` always pointing at originals.  
6. If still huge: chunk / hierarchical summary **as derived units**, I7A-traced; summaries are **not** Ask-current fact.

Do not solve volume by stuffing every calendar row and every message into the model.

---

## 7. Do raw provider dumps reach the model today?

**Tell path (current tree):** `synthesize_tell` is a **deterministic stitch** of Ask `statements[]` (short excerpts). **No LLM** on the tell pack.

**Other model use:** `compile_ask` residual fill (I7A `trace_llm`) for leftover slots / clarification — Ask **text**, not mailbox dumps. Photo/video providers are not an LLM dump of email.

**Risk if tell-LLM is wired naively:** `_email_hit.excerpt` and statement `text` can still carry quoted threads; calendar `excerpt` is description/location; journal/story excerpts are current saved. Spam ingested rows could be included.

---

## 8. Changes needed before I11 can safely synthesize

Must land with (or immediately before) tell-LLM — not as afterthoughts:

1. Ask eligibility: exclude Spam/Trash **before** pack and model (same predicate as Story search).  
2. Narrative Evidence Preparation module: query-dependent scope (examples A/B in the founder note).  
3. Email authored-body derivation + thread-level dedupe; conservative `quote_uncertain`; provenance to original message.  
4. Shared Communication Evidence units for Email and SMS; participant filter + `group_thread`.  
5. Calendar selection: narrow = people + comms-linked; broad = year-significant, not every row.  
6. Volume staging + provenance-preserving compression.  
7. `tell` LLM call through I7A; pack JSON in assembled context; fail closed (no invent).  
8. Shared long-form curator on **Explore and Person Explorer** (Person currently **hides** `#mb-explore-curator`).  
9. Keep Copy / Save as Story / persistable Saved View JSON; **no** Save View control.  
10. Replace deterministic stitch as the **product** synthesizer (scaffold may remain only as fail-closed fallback if Tom authorizes).

Do **not** block on Face-SoT or unrelated recognition. Disclose missing coverage.

---

## 9. Unresolved product decisions (founder)

1. **Authorize this contract to build?** Definition is locked; synthesis/prep is **not** started until explicit approval.  
2. **Tell model:** which `LlmProvider` / host (existing Ollama vs other)? Max tokens?  
3. **Hierarchical summarization:** allowed in I11 when volume requires a second traced model pass, or I11 stays single-pass + hard cap + disclosure?  
4. **Persist authored_text** on Evidence vs derive only in the pack?  
5. **Age-relative Saved View** (“when he was young”): add a durable interpreted slot now, or I13?  
6. **Person Explorer pixels:** unhide Explore curator vs reuse `#mb-person-summary` as the same component?  
7. **Fail-closed stitch:** keep deterministic stitch if the model is unavailable, or show insufficient + disclosure only?

---

## Explicitly out

I13 Save View UI (including disabled Save View). `/narration/ui`. Journal redesign. I12. Face SoT. Physically deleting Spam/Trash originals. Sending spam to the model with “ignore this.”
