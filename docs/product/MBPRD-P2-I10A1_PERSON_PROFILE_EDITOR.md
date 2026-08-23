# MBPRD-P2-I10A.1 — Person Profile Editor

**Status:** PRD **for owner review** · increment **not build-authorized**  
**Date:** 2026-08-23  
**Increment definition:** [MBBS-P2_INCREMENT_10A1_DEFINITION.md](MBBS-P2_INCREMENT_10A1_DEFINITION.md)

**Visual baseline:** Person Edit PNG(s) on commit `fe913a4` (`cursor/marvin-capture-v01-3344`) under `docs/source/Screens/MBUX Story Screens/` (same drop as Artifact/Journal). Copy into `docs/source/Screens/MBUX Person Screens/` before build. Screenshot text is not proof of a backend field.

**Depends:** I1–I8A **ACCEPTED** · I5 Person Explorer **ACCEPTED** · I6 kinship **ACCEPTED** · I10A Stories **ACCEPTED** · I10B Artifacts **ACCEPTED** 2026-08-23 · `memorybox/profile` + `/people/{id}/profile` · owner Person

**Does not start:** I10A.2 voice · I10C Journal · I11 · I8.5 Face SoT · new Person identity model · family multi-user ACL

**Increment ID:** **P2-I10A.1 — Person Profile Editor.** This is **not** I5 and does **not** reopen I5.

**Legend**

| Label | Meaning |
|---|---|
| **Frozen** | Owner decision. Do not reopen without a new decision. |
| **Existing** | Confirmed in the repository. |
| **Required** | Must be built for this slice. |
| **Recommendation** | Implementation choice. Change only with a recorded reason. |
| **Open** | Question for Tom. Does not invent a second product. |

---

## Problem being solved

Person Explorer (`/people/ui?person=`) is the accepted family gallery. Editing a person still lives on `/people/ui?admin=1`: a long operational form (facts, aliases, contacts, relationships, marriage, rename, reject face, merge, teach Immich). Families will not find that path. I10A.1 converts the **family edit** into the same chrome as Stories/Artifacts.

It matters now because I10B is ACCEPTED and the frozen sequence’s next slice is this editor — before I10A.2 voice and I10C Journal.

## Success criteria

- From Person Explorer, Edit opens the Person Profile Editor for that person without `?admin=1`.
- Owner can correct display name, birth/death/note facts, nicknames, email/phone, taught family roles, and a shared marriage/anniversary date.
- People pickers are search-while-type (I10A pattern), full name + portrait — not a dump of every person.
- Derived kinship remains visible as Derived and is not edited as if it were taught.
- Dark theme; cards/fields readable (same shell-token lock as I10A/I10B).
- `?admin=1` is no longer the product path for those family edits.
- FlightSim: open Peggy/Sue/Tom, change a fact, reload Explorer About — the change is there. Cancel does not write.

## Scope

### In

| Capability | Notes |
|---|---|
| Editor chrome | I10A Explore nav + Ask band; dark surface `people` / `person-edit` |
| Entry | Person Explorer header/drawer **Edit person** / **Open full profile editor** → `/people/ui?person={id}&edit=1` (**Recommendation**) |
| Display name | Existing rename API |
| Facts | `birth_date`, `death_date`, `note` — Existing `POST /people/{id}/facts` |
| Aliases | nickname / other name — Existing |
| Contacts | email / phone (10-digit rule stays) — Existing add + in-place correct |
| Taught relationships | Existing role set; typeahead both sides |
| Marriage / anniversary | One shared date for two people — Existing |
| About read-back | Editor shows current profile from `GET /people/{id}/profile` |
| Sticky save/cancel | Footer stays on screen (I10B lesson) |

### Out

- I5 gallery, Highlights, Timeline, Map, Learn boxing
- I6 derived-edge editing or new inference
- I10A.2 MediaRecorder / STT on Person
- I10C Journal
- I11 narrative
- I8.5 Face SoT
- New Person enroll as a first-class “New person” product (Open: see below)
- File GC, public people routes, multi-user ACL
- Reopening I10B

### Existing APIs to reuse (do not fork)

`GET /people/{id}`, `GET /people/{id}/profile`, `GET /people/{id}/portrait`, `GET /library/person-options`, `POST /people/{id}/facts`, aliases, contacts, relationships, marriage, rename. Merge / reject-face / teach-Immich remain **Existing** on `?admin=1` until an Open below pulls them in.

## Frozen product decisions (proposed)

Confirm or rewrite before build.

1. Explorer stays the home. Editor is a second surface for one person, not a replacement gallery.
2. One MB Person. No per-evidence Person IDs.
3. Taught vs Derived stays I6: editor writes taught assertions only.
4. Visibility/sharing of a Person is **not** this increment (People are not Stories).
5. Portrait display uses `GET /people/{id}/portrait`. **P2-BL-I5-01** (preferred Immich face) is **Open** — absorb only if it is a thin reuse; do not build a new face stack.
6. Merge duplicate people, reject wrong Immich link, and teach-Immich-face stay off the family editor unless the approved PNG shows them.
7. No working draft for Person. Save writes immediately (same spirit as I10B Artifact — no Person draft lifecycle).
8. Cancel / Back with no Save writes nothing.

## Constraints and edge cases

- Phone: digits-only persist (Existing). Show a readable formatted value.
- Birth date replace-in-place (Existing).
- Owner Person badge remains honest (`is_canonical_owner`).
- Ambiguous Immich→MB map: fail closed with a resolve message; do not silently create a second person.
- Soft-removed / `merged_away` people are not editable.
- Dark theme: lock `html[data-mb-surface=…]` tokens so shell paper cannot paint light cards (I10B defect).

## Build plan (after sign-off)

1. Copy Person Edit PNG(s) into `docs/source/Screens/MBUX Person Screens/`.
2. Editor route + I10A chrome; load profile; sticky footer.
3. Name, facts, aliases, contacts.
4. Relationship + marriage with I10A typeahead.
5. Wire Explorer Edit; stop sending families to `?admin=1` for those fields.
6. Prove: save fact/name/relationship; cancel no-write; derived not writable; theme tokens.

## Open questions for Tom

1. **Route:** `/people/ui?person=&edit=1` on the same page vs a dedicated `/people/ui/edit`? **Recommendation:** query on the existing People URL.
2. **P2-BL-I5-01** preferred Immich portrait: in I10A.1 or stay parked?
3. **New person:** editor-only for existing people, or a New person path that enrolls by exact display name (Stories already enroll narrators)?
4. **Merge / reject face / teach:** stay `?admin=1` (Recommendation) or appear on the family editor?
5. **PNG lock:** treat `fe913a4` Person Edit as visual baseline, with these Frozen rows winning over pixels?

## Sign-off

This PRD is **not** build-authorized. Reply **Approved to build** (and answers to Open items) before implementation. Do not start I10A.2 in this increment.
