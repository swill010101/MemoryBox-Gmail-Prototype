# P2-I10A — Stories

**Status:** **BUILD AUTHORIZED** 2026-08-21 (Tom: “Name PRD i10A - Stories…. it goes next and you are approved to build i10A - Stories”)  
**PRD:** [MBPRD-P2-I10A_STORIES.md](MBPRD-P2-I10A_STORIES.md)  
**Visuals:** `docs/source/Screens/MBUX Story Screens/`  
**Depends:** I10 **ACCEPTED** 2026-08-21 · I1–I8A **ACCEPTED** · I9 on this tree · MBQL-001 **ACCEPTED**  
**Does not start:** **I11** narrative generation · compose-from-memories · Story dictation · multi-user ACL · Story-as-evidence-for-Story · in-rail authoring

## Intent

A Story is a durable, human-authored MemoryBox knowledge object. Drafts are never Ask-visible. Ask retrieves only the current saved version. Supporting memories are mixed-type links on that version. Originals are never copied or altered.

I10A is **not** I11. I11 remains evidence-backed narrative synthesis.

## Build locks (from PRD)

1. Working draft vs `current_saved_version_id` UUID pointer.
2. Save draft / Save Story / Save revision are explicit.
3. Status filters: All / Drafts / Saved. Visibility is separate (Private / Shared with family).
4. Full name + preferred Immich portrait.
5. Ordered blocks: heading | paragraph | memory_ref. Plain text this increment.
6. Versioned mixed supporting memories; Stories cannot support Stories.
7. Photo/video rail: list / add-to-existing / new / open — not an editor.
8. Placeholder: “Start writing your story…”

## Locked implementation choices (were Open in the PRD)

- Save Story requires a **title**. Body or memories may be empty (owner can publish a titled stub).
- Editor field is the owner Person, **display-only** (single-user).
- Place is `place_label` plus optional `places.id`.
- Picker reports honest `total` / `truncated` rather than Explore gallery caps as “complete.”
- Email/SMS grain: `evidence` row id; `source_kind` email_thread | sms_conversation.
- No restore-from-history in this increment.
- Library does not list `draft_only` Stories.

## Prove

`python -m memorybox prove-story` (I10A checks). FlightSim: `/story/ui` after `migrate`.
