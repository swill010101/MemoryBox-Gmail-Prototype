# MBAS-P2-I11 — Narrative Evidence Preparation (final pre-build lock)

**Status:** Planning **LOCKED** 2026-08-24 · **BUILD AUTHORIZED** 2026-08-24  
**Does not start:** prep/LLM implementation · persisted authored-body column · I12 web retrieval · I13 Save View UI · `/narration/ui`  
**Depends on:** [MBAS-P2-I11](MBAS-P2-I11_NARRATION_LIVING_VIEW_ASSESSMENT.md) · I10C **ACCEPTED**

Parent MBAS remains directionally correct. This note is the **final pack contract** before build authorization. I11 must not become “retrieve some chunks and send them to the model.”

---

## Pipeline (locked)

```
Raw archive
  → deterministic retrieve / eligibility / filters
  → Narrative Evidence Preparation (question-specific pack)
  → optional hierarchical derived summaries (I7A; not family truth)
  → LLM synthesis for tell only (provider-neutral; I7A)
```

If the model is unavailable: **fail closed** for generated prose. Show evidence + coverage + “narration unavailable.” Do **not** substitute deterministic stitch that looks like the essay.

---

## 1. Final evidence-pack schema

```json
{
  "schema_version": 1,
  "ask": {
    "original_ask": "",
    "output_mode": "tell",
    "plan": {}
  },
  "scope": {
    "breadth": "narrow | broad",
    "owner_person_id": null,
    "people": [],
    "time": { "windows": [], "label": null },
    "places": [],
    "events_trips": [],
    "topic": null,
    "modalities": []
  },
  "units": [],
  "derived_summaries": [],
  "coverage": {
    "summary": "",
    "missing": [],
    "conflicts": [],
    "excluded": ["spam", "trash"],
    "truncated": false,
    "truncation_disclosure": null
  },
  "volume": {
    "retrieved_n": 0,
    "eligible_n": 0,
    "prepared_n": 0,
    "supplied_to_model_n": 0,
    "reduction": "rank | organize | hierarchical_summary"
  },
  "evidence_used": {
    "photos": 0,
    "video_moments": 0,
    "calendar_events": 0,
    "emails": 0,
    "sms": 0,
    "journal_entries": 0,
    "stories": 0,
    "artifacts": 0,
    "travel": 0,
    "spoken_moments": 0,
    "place_event": 0,
    "external_historical": 0
  }
}
```

`evidence_used` counts **normalized units supplied for synthesis**, not raw mailbox hits or quoted duplicates. `external_historical` stays **0** in I11; reserved for I12.

Saved View emit (unchanged, I13 stores):

```json
{ "schema_version", "original_ask", "output_mode", "plan", "presentation" }
```

`plan` must carry **general resolved semantic constraints** (not phrase-specific fields). Use the **generalized semantic resolver** already designed — do **not** hard-code a universal phrase rule such as `young = 10–25`.

Conceptually:

```
“when Dad was young”
  → resolved age band
  → interpretation / version metadata
  → birth fact converts the age band into actual dates
```

Stored generically (not a `when_he_was_young` field):

- Person
- age band
- interpretation / version

If Dad’s **birth year is known**, convert the band to dates. If birth is missing, MemoryBox may use **other reliable age/date evidence** when enough exists. If not, **ask rather than guess**. The pack must say when the band is unresolved to dates.

---

## 2. Evidence unit types (`units[].kind`)

Family evidence (I11):

| `kind` | Class |
|---|---|
| `communication` | Email + SMS/iMessage/MMS — one shape |
| `media_observation` | Photo or video observation (not raw EXIF dump) |
| `travel` | **Derived** structured itinerary/lodging/rental/reservation facts. Provenance **must** point at the original `communication` (or calendar/document). Never replaces that original. |
| `calendar` | Scheduled/recorded events |
| `journal` | Current saved Journal |
| `story` | Current saved Story recollection |
| `artifact` | Object identity + why-it-matters |
| `place_event` | Place / Event / Trip objects |
| `spoken_moment` | Audio / video spoken timeslot |

Reserved (I12, not implemented in I11):

| `kind` | Class |
|---|---|
| `external_historical` | World/context sources. **Never** family evidence. Separate “external sources used” list later. |

Common unit fields: `unit_id`, `kind`, `time` (+ precision/confidence), `people[]` with `role`, `place`, `content` (human-relevant only), `claims[]` (see §3), `provenance`, `rank`, `normalization`.

**Communication** fields: `source_type`, `source_id` / `evidence_id`, `thread_id`, `speaker_person_id`, `participants`, `group_thread`, `timestamp`, `authored_text`, `subject`, `attachments[]`, `location_assertions[]` (see SMS rule), provenance, flags.

**Media observation** fields: asset ref, source type photo|video, capture time + precision, people **visibly identified**, place from GPS/confirmed place (how established), observable setting/activity/object, caption/annotation, event association, provenance, flags. **Do not** treat filename, folder, camera owner, or archive owner as photographer or purpose.

**Travel** fields: `travel_kind` (flight|lodging|car|reservation|other), parties/passengers, origin/destination or property, start/end, confirmation reference if present, `derived_from` → original communication `evidence_id` / `unit_id`. Extract **only when reliable**. Keep the original airline/hotel/rental email as a **communication** unit. Never replace the original with the derived travel record.

**Calendar:** title, start/end/duration, location, attendees, notes, provenance. Scheduled ≠ occurred unless corroborated.

---

## 3. Claim-specific confidence / provenance (trust rule)

A source supports **only the factual claim it can establish**. Items are not globally “proof” or “not proof.”

**Locked example:** Person Tom visible + reliable EXIF/GPS Maui + supported capture date may support:

> Tom was photographed in Maui on or around 2017-03-14.

It may support physical presence there at that time **depending on identity and place/time confidence**.

It does **not** automatically support: who took the photo; companions; vacation vs other purpose; enjoyment; first trip; why.

**General rule:** Person identity + reliable place/time can support **presence**. It does not establish photographer, purpose, motive, emotion, causation, or significance.

Each unit may list:

```
claims: [
  { "type": "presence", "person_id", "place", "time", "confidence", "basis": ["face","exif_gps"] }
]
```

Unsupported inferences are **omitted**, not guessed. Corroboration **raises** confidence; one strong source can suffice.

SMS/iMessage: **timestamp is not location.** Location assertions must record `basis`: `authored_text` | `shared_location_payload` | `attachment_exif` | `corroborated_other_source`. No undifferentiated “message GPS.”

Calendar: establishes **scheduled/recorded**. Do not overstate occurrence without corroboration.

---

## 4. Email normalization plan (Ask-time, not persist)

Derive authored-only text **conservatively at pack time**. Do **not** gate I11 on a new persisted authored-body column. Raw Email remains source of truth. Later cache may store derived body with parser version, source ref, provenance, confidence, rebuildability — never silent replace of raw.

Ask-time steps:

1. Exclude Spam/Trash/`mailbox_skip` before pack/model.  
2. Canonical speaker + participants; `group_thread`.  
3. Extract authored body; remove repeated quotes when prior messages exist independently; suppress obvious duplicates; strip signatures/boilerplate **when reliable**.  
4. Keep date/time/thread subject.  
5. Provenance to original message.  
6. Flag `quote_uncertain` / `boilerplate_uncertain` rather than destroy possible authored text.

Viewer `split_quoted_email` is a starting heuristic only (On…wrote / Original Message). Need `>`-quote handling, signature detection, thread-level authored-sentence dedupe, Person mapping for speaker.

---

## 5. SMS normalization plan

Same **communication** unit as Email.

Map: channel → `source_type`; `from_owner` / `person_ids` / `sender_name` → `speaker_person_id`; `participants` + thread → `group_thread`; `body_text` → `authored_text` (little quote cleanup).

Location: scan body for place language and maps links; attachments for EXIF; structured shared-location if present. Each location assertion carries `basis`. Timestamp-only → no place claim.

“Peggy and I discussed…”: include Peggy/owner authored units; keep other participants in metadata; do not include Rick/Sue authored text unless the Ask requires it. Existing retrieve “and I” sender filter is a starting point, not the pack.

---

## 6. Media observation extraction plan

Build `media_observation` from photo/video hits without dumping provider IDs, raw EXIF blobs, or Immich internals into the model.

Populate: capture time + precision; depicted people (confirmed vs candidate — disclose); place from GPS/confirmed place **with basis**; caption; observable setting only when already extracted or conservatively labeled unknown; timeslot + spoken **excerpt** for video moments (not whole-tape transcript).

Claims: presence when identity + place/time support it. Never photographer from filename/folder/camera owner/archive owner.

---

## 7. Travel evidence correlation plan

**Both units when extraction is reliable.**

The original airline / hotel / rental / reservation **email remains a `communication` unit** — that is the authentic evidence.

When structured travel facts can be extracted **reliably**, also emit a **derived `travel` unit**. Example:

- Communication: Delta itinerary confirmation (raw authored/email evidence).  
- Derived travel: `flight`, STL → OGG, 2017-03-12, passengers, confirmation reference, provenance → that Delta email.

Same pattern for hotels, cars, reservations.

**Never replace** the original communication with the derived travel record. The communication preserves what the source was; the travel unit gives chronology a clean structure.

For trip Asks (“Tell me about my Hawaii trip in 2017”), **correlate before synthesis**:

Derived travel units + original comms, calendar span, GPS/EXIF media, people in media, comms during/about the trip, Journal, Stories, Place/Event/Trip objects, artifacts/documents.

Do not hand the model an unsorted pile and ask it to invent the trip.

Corroboration example: STL→OGG 2017-03-12 + Maui lodging 12–18 + photos 14–16 + calendar Maui 12–18 → chronology “traveled to Maui in March 2017” is allowed. One strong source can suffice; more sources increase confidence.

---

## 8. Calendar relevance plan

Narrow: only events **materially related** to the people/topic/trip/window (attendees, place, title/notes linked to qualifying threads — not every 2017 event).

Broad year: calendar may reconstruct the year; still rank/prepare; do not dump every row.

Trust: scheduled/recorded ≠ occurred-as-planned.

---

## 9. Hierarchical volume-management plan

**IN.** Do not use arbitrary first-N / hard cap as the **primary** broad-narrative solution.

1. retrieve → 2. filter (eligibility, Ask constraints, spam/trash) → 3. normalize → 4. dedupe → 5. organize chronology/event/topic → 6. rank for Ask → 7. summarize chunks/groups if needed → 8. keep provenance to underlying units → 9. synthesize.

Configured model context window is an **implementation** constraint (reserve pack, trust instructions, output, coverage). It is not a reason to silently omit relevant evidence. Intermediate model summaries: derived, regenerable, I7A-traced, **not** durable family truth. If still omitted: disclose truncation.

Provider-neutral `LlmProvider`. Do not hard-code a host or model name in the PRD. I7A records provider, model, prepared context (per trace policy), response, latency/errors, orchestration state.

---

## 10. Shared Curator component plan

Do **not** merely unhide Person Explorer’s `#mb-explore-curator` (divergent CSS/behavior).

One shared long-form Narrative/Curator module used by Explore and Person Explorer: same semantics, rendering, Copy, Save as Story, evidence/coverage, evidence-used footer. Ask must not change because the surface is People.

---

## 11. Model invocation boundary

Deterministic: resolve, retrieve, eligibility, prep, claims, coverage, ranking, chunking. Model: **synthesize readable prose from the prepared pack** for `output_mode=tell` only.

Model must not: elect Spam/Trash, invent photographer/purpose/emotion, treat filename as meaning, treat SMS time as GPS, promote intermediate summaries to truth, or run I12 web retrieval.

Unavailable model: fail closed (see pipeline). Gallery/results remain.

Copy / Save as Story / Saved View JSON: unchanged from prior lock.

---

## 12. Acceptance additions (prove when built)

| ID | Case |
|---|---|
| C-17 | Photo + identity + EXIF/GPS: presence/photographed-there OK; no photographer/purpose/emotion/companions without evidence. |
| C-18 | Hawaii trip: original itinerary/lodging **communication** units remain; derived `travel` units when extraction is reliable; plus calendar + GPS/photos may synthesize supported chronology. Original is never replaced. |
| C-19 | SMS timestamp alone ≠ location; authored/shared-location/attachment EXIF may, with `basis`. |
| C-20 | Peggy/Tom Christmas 2017 discussion: authored units, no quote dupes, no unrelated 2017 calendar dump. |
| C-21 | “Tell me about my 2017”: broad family evidence; staged volume, not first-N dump. |
| C-22 | Evidence-used counts = normalized Email/SMS units included, not raw hits/quotes. |
| C-23 | Model down: evidence visible; narration unavailable; no stitch-as-narrative. |
| C-24 | Dual travel: confirmation email is a communication unit; structured flight/hotel facts are a derived travel unit with provenance to that email. |
| C-25 | “When Dad was young”: generic Person + age_band + interpretation/version; dates from birth (or other sufficient age/date evidence); **ask rather than guess** if insufficient. Not a phrase-specific field. Not a hard-coded 10–25 rule. |

Keep C-01–C-16. Shared curator (C-05) means **one component**, not unhide.

---

## 13. Remaining founder input

None. **Build authorized** 2026-08-24.

Not open: model host name; product token cap; persist authored email as I11 gate; stitch fallback; Living Album; Save View UI; I12 inside I11.

---

## Explicitly out

I12 implementation. I13 UI. `/narration/ui`. Journal redesign. Face SoT. Persist-authored-body as a gate. Silent stitch fallback. First-N as primary volume strategy. Filename-as-photographer. SMS-time-as-GPS.
