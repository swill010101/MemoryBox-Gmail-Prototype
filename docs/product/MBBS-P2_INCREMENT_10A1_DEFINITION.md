# P2-I10A.1 — Person Profile Editor

**Status:** Definition **ready for PRD review** · **not build-authorized** until Tom signs the PRD  
**Date:** 2026-08-23  
**PRD:** [MBPRD-P2-I10A1_PERSON_PROFILE_EDITOR.md](MBPRD-P2-I10A1_PERSON_PROFILE_EDITOR.md)  
**Depends:** I5 Person Explorer **ACCEPTED** · I6 kinship **ACCEPTED** · I10A Stories **ACCEPTED** · I10B Artifacts **ACCEPTED** 2026-08-23 (chrome/typeahead reuse) · existing `/people/{id}/profile` APIs  
**Does not start:** I10A.2 Unified Voice · I10C Journal · I11 · I8.5 Face SoT · Artifact or Story rebuilds

## Intent

The family-facing way to **correct a person’s name, facts, contacts, and taught relationships** is a MemoryBox Person Profile Editor on I10A chrome — not the hidden `?admin=1` form. Person Explorer (I5) stays the gallery/timeline home. Derived kinship stays I6 (labeled Derived).

## Build locks (proposed — confirm in PRD)

1. One editor for an existing MB Person. Entry from Person Explorer (Edit / Open full profile editor).
2. Reuse I10A typeahead for picking people (relationships, marriage). Full `display_name` + portrait.
3. Reuse existing profile write APIs. Do not invent a second Person identity.
4. Taught relationships remain SoT; derived edges stay read-only and labeled Derived.
5. Dark theme. Do not reopen I5 gallery/timeline.
6. Merge, reject-wrong-face, and teach-Immich-face stay **out** unless the approved Person Edit PNG requires them on this screen.
7. No Artifact MediaRecorder. No I10A.2 mic on Person.

## Next after this increment

**I10A.2** Unified Voice Capture (Stories first). Then **I10C** Journal. I11 stays closed.
