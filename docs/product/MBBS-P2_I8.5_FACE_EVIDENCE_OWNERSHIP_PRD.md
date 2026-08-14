# P2-I8.5 — MemoryBox Face Evidence Ownership & Immich Decoupling

**Status:** Approved for insertion into the P2 roadmap · **Not authorized to build** until P2-I8 is ACCEPTED and Tom explicitly authorizes this increment  
**ID:** **P2-I8.5** (not I7.5 — executes after P2-I8 ACCEPTED)  
**Date:** 2026-08-14  
**Owner:** Tom  
**Execution order:** After **P2-I8 Richer Email** and before **P2-I9 Spoken Moments**  
**Purpose:** Establish MemoryBox as the durable owner of active face observations before implementing the Shared Evidence Viewer Learn rail and broader face-learning workflows.

**Numbering lock:** Early drafts used “I7.5” as an inserted increment. That ID is **retired**. Every living reference is **P2-I8.5** so sequence matches execution (after I8).

---

## 1. Why this increment exists

MemoryBox currently relies on Immich as the practical Photo / Face provider.

That is useful for discovering faces and named People, but MemoryBox must not make its own identity learning, face corrections, recognition evidence, or future recognition pipeline dependent upon Immich’s internal database, face clusters, or bounding-box state.

The current product principles already establish:

* canonical Person identity belongs to MemoryBox;
* provider identities such as Immich People remain mapped provider records;
* face evidence may come from Immich, manually boxed photo/video faces, and confirmed recognition results;
* provenance must be preserved;
* no individual provider becomes the sole authority;
* original media remains immutable.

P2-I8.5 makes those principles operational for face observations.

FlightSim already showed the cost of skipping this: photo Learn, Immich “ownership,” and video Learn still treat provider face state as the working authority. Those UI issues are **symptoms**. This increment is the correction. The Learn rail itself is **not** in this increment.

---

## 2. Product decision

### MemoryBox owns active face evidence

MemoryBox will maintain its own durable face-observation records.

Immich remains:

* a source/provider of media;
* a source/provider of face detections and identity evidence;
* a source of provider provenance;
* read-only from MemoryBox.

Immich is **not** the working authority for face coordinates, owner corrections, face assignment state, or MemoryBox recognition evidence.

Once a provider face observation has been imported into MemoryBox, normal MemoryBox behavior operates on the **MB-owned observation**.

---

## 3. Core invariant

> Provider face evidence may enter MemoryBox. Once imported, MemoryBox owns the durable working observation. Provider changes cannot silently erase, overwrite, or resurrect family-confirmed MemoryBox knowledge.

This is a product and architecture rule, not merely an implementation convenience.

It exists so that:

* an Immich upgrade cannot wipe out MemoryBox face learning;
* an Immich database reset cannot wipe out MemoryBox face learning;
* an Immich re-index cannot silently reverse MemoryBox corrections;
* replacement of Immich with another photo provider does not erase MemoryBox identity knowledge;
* future provider migrations remain feasible.

---

## 4. Relationship to existing P2 requirements

This increment implements/refines:

### MBPS-002

* P2-ID-01 — Canonical MemoryBox Person
* P2-ID-02 — Known Immich people require no redundant enrollment
* P2-ID-03 — Continuous provider identity synchronization
* P2-ID-04 — Face evidence ownership and provenance
* P2-ID-05 — Cross-modal identity

### MBCAP

* CAP-P2-003 — Face Identity & Appearance Learning
* CAP-P2-004 — Photo Face Identification & Face-Evidence Capture
* CAP-P2-005 — Video Face Identification & Learning
* CAP-P2-006 — Video Person Recognition & Appearance Timeslotting
* CAP-P2-010 — Cross-Modal Person Identity Learning
* CAP-P2-016 — Correction / withdrawal lifecycle
* CAP-P2-017 — Trust / provenance

### EVS

* EVS-250 — user boxes a face in a photo and links it to an existing or new canonical MB Person
* EVS-252 — known Immich People flow into canonical MB People while retaining provider mapping

P2-I8.5 does not replace those requirements. It creates the durable face-evidence foundation needed to implement them safely.

EVS-250 remains an I1 earn-in for Person-in-media proof. I8.5 is the increment that makes photo/video face observations **MB-owned working records** so later Learn-rail completion of EVS-250 does not depend on Immich mutation.

EVS-252 remains P1/I1 Person mapping. I8.5 imports **face observations**, not named People. Unknown Immich clusters still must not silently mint canonical MB People.

---

## 5. Scope

### In scope

1. Define/confirm MB-owned FaceObservation / FaceEvidence domain representation.
2. Import existing eligible Immich face observations into MemoryBox.
3. Preserve Immich provenance and source identifiers.
4. Preserve original provider bounding-box coordinates.
5. Establish MB-owned working bounding-box coordinates.
6. Establish MB-owned active Person assignment and state.
7. Change MemoryBox face rendering to use MB-owned observations.
8. Change recognition/training input selection to use MB-owned observations.
9. Implement override rules so owner corrections cannot be reversed by provider synchronization.
10. Continue read-only incremental Immich discovery for newly appearing provider face observations.
11. Add migration/reconciliation status and test coverage.
12. Ensure future provider replacement does not invalidate MB face evidence.

### Out of scope

* writing face changes back to Immich;
* modifying original photo/video files;
* Shared Evidence Viewer Learn rail UI actions themselves;
* full new photo-recognition engine;
* continuous face boxes during video playback;
* major Immich management features;
* editing Immich People from MemoryBox;
* replacing Immich in this increment.

The Learn rail is a **dependent follow-on** and must not be implemented until this increment is accepted. That follow-on is **after I8.5** (which itself is after I8). Do not proceed into Learn-rail implementation from this PRD unless Tom explicitly authorizes it.

---

## 6. Authoritative data model behavior

MemoryBox must maintain a durable face-observation record sufficient to function independently of Immich’s internal face records.

Exact schema is an engineering decision, but the conceptual record must support at least:

* MB face observation ID;
* canonical MB Person ID, when assigned;
* source asset reference;
* source provider;
* provider asset ID;
* provider face/person identity ID when applicable;
* media type;
* video frame/time when applicable;
* original provider bounding box;
* current MB working bounding box;
* origin/source type;
* confirmation state;
* active/withdrawn/superseded state;
* owner correction state;
* recognition eligibility;
* created/imported timestamp;
* updated timestamp;
* provenance;
* correction/revision history.

Do not require provider identity IDs for MB-created observations.

---

## 7. Initial Immich migration

P2-I8.5 must perform an initial import of existing eligible Immich face observations.

For each imported observation:

1. identify the Immich asset;
2. identify the Immich face/person observation;
3. map to the corresponding canonical MB Person when a valid mapping exists;
4. copy/store the face bounding coordinates into MB;
5. preserve the original Immich coordinates as provider provenance;
6. initialize the MB working coordinates from the provider coordinates;
7. preserve provider source IDs;
8. preserve enough provenance to explain where the observation originated;
9. mark the imported observation as provider-originated;
10. make the MB copy the active working observation for MemoryBox.

The migration must be idempotent.

Running it twice must not create duplicate MB face observations.

---

## 8. Which Immich observations should migrate

The objective is to take durable control of usable face evidence without turning every meaningless provider cluster into a canonical MB Person.

Use the existing Person/provider mapping rules.

### Known/mapped faces

If an Immich observation maps to a known canonical MB Person:

* migrate the observation;
* associate it with that Person;
* retain Immich provenance.

### Unknown/unmapped provider faces

Do not automatically create named MB People merely because Immich detected a face.

Unknown observations may be imported as unassigned MB face observations if useful to support later owner teaching, but they must remain unassigned and must not silently mint canonical People.

This preserves the existing rule that provider detections are evidence, not automatic family facts.

---

## 9. Working coordinate rule

After migration:

**MemoryBox screens use MB-owned working coordinates, not live Immich coordinates, for face overlays and face-related UX.**

This includes where applicable:

* photo face boxes;
* face selections;
* face icons/crops derived from coordinates;
* Person face evidence;
* Review & Learn;
* Shared Evidence Viewer;
* face exemplar selection;
* recognition input generation.

Provider coordinates remain available as provenance but cease being the runtime authority for MemoryBox face UX.

---

## 10. Original media rule

Original photos and videos remain untouched.

Changing an MB face observation changes only derived MemoryBox metadata.

Do not:

* edit the image;
* write pixels;
* overwrite EXIF;
* modify the source video;
* alter Immich’s copy of the media.

This follows **Original Evidence Is Sacred**.

---

## 11. Immich read-only rule

MemoryBox must not write the following back to Immich:

* face coordinates;
* Person assignments;
* face merges;
* face splits;
* owner corrections;
* face withdrawals;
* MB recognition results;
* MB Person creation;
* MB Person merges;
* recognition confidence;
* recognition training state.

Immich remains an input/provider, not a bidirectional identity store.

---

## 12. Continuous provider synchronization after migration

This increment does **not** eliminate ongoing provider synchronization.

Immich may later contain:

* newly detected faces;
* new assets;
* new provider identity observations;
* changed provider metadata.

MemoryBox should continue to detect newly available provider evidence.

However, ongoing provider synchronization is subordinate to the MemoryBox authority rules below.

---

## 13. Owner-override rule

This rule is mandatory.

If an imported Immich observation has subsequently been corrected in MemoryBox, later Immich synchronization must not silently undo the MemoryBox decision.

Examples:

### Reassigned in MB

Immich:
`Face 123 → Peggy`

Owner changes in MB:
`Face 123 → Rick`

Later provider sync still says:
`Face 123 → Peggy`

Result:

**MB remains Rick.**

The provider value may remain visible in provenance/history, but it does not overwrite the active MB assignment.

### Adjusted box in MB

Immich coordinates:
`X1/Y1/X2/Y2 = provider box`

Owner adjusts MB coordinates.

Later Immich sync returns the original provider coordinates.

Result:

**MB working coordinates remain the owner-adjusted coordinates.**

### Unassigned in MB

Immich still associates the provider observation with Peggy.

Owner has intentionally unassigned/withdrawn the MB association.

Later Immich sync runs.

Result:

**The MB face remains unassigned/withdrawn.**

Provider synchronization must not resurrect it.

---

## 14. Override / tombstone semantics

Implement an explicit mechanism sufficient to distinguish:

* untouched provider-derived observation;
* owner-confirmed observation;
* owner-reassigned observation;
* owner-adjusted geometry;
* owner-withdrawn assignment;
* superseded observation;
* provider update awaiting reconciliation if necessary.

Do not rely on fragile inference such as comparing timestamps alone.

The system must know when MB has intentionally overridden provider state.

---

## 15. Provider-change conflict rule

MBPS-002 requires continued awareness of Immich changes.

This remains true.

However, P2-I8.5 refines how those changes are applied:

### Provider changes with no MB override

MemoryBox may safely update/reconcile provider-derived evidence.

### Provider changes after MB owner correction

Do not overwrite the MB working state.

Record/update the provider evidence separately.

### Ambiguous conflict

Route to review or preserve both states with clear provenance.

Never silently choose provider state over confirmed MB owner knowledge.

---

## 16. Provider replacement resilience

MemoryBox face evidence must survive:

* Immich being disconnected;
* Immich being rebuilt;
* Immich changing internal face IDs;
* Immich face re-indexing;
* Immich version upgrades;
* migration to another photo provider.

If Immich is unavailable, MB should still retain:

* canonical Person identity;
* imported/confirmed face observation records;
* MB bounding coordinates;
* owner corrections;
* recognition exemplars;
* correction history;
* provenance stating the original provider.

The system may temporarily lose access to the original image if the provider/source itself is unavailable, but it must not lose the MemoryBox knowledge layer.

---

## 17. Face crops / embeddings

The PRD requires MemoryBox to own sufficient durable face evidence for provider-independent operation.

Whether this means:

* storing source asset + MB coordinates;
* storing derived face crops;
* storing embeddings;
* storing both crops and embeddings;

is an engineering choice to be determined after inspection of the current recognition pipeline.

The implementation must satisfy this outcome:

> MemoryBox can continue using its confirmed face evidence for supported recognition workflows without depending on Immich’s internal face cluster database.

Any derivative needed for recognition must be reproducible or durably stored according to the existing architecture.

---

## 18. Recognition input authority

After P2-I8.5, face recognition/training inputs must originate from **MB-owned active face evidence**.

Eligible evidence may include:

* imported Immich-origin observations now owned by MB;
* manually boxed MB photo observations;
* manually boxed paused-video observations;
* confirmed recognition observations.

The recognition layer should not query Immich’s current face boxes as its sole working training source.

---

## 19. Shared Evidence Viewer dependency

The Learn rail implementation is intentionally deferred until this increment is accepted.

After P2-I8.5, the Learn rail will support:

* Assign to someone
* Reassign face
* Adjust face box
* Unassign face
* Learn from this face

All of those operations must operate on MB-owned face observations.

They must not require Immich mutation.

---

## 20. Future Assign flow requirement

P2-I8.5 should support the data/service foundation required for the following UX:

**Assign to someone**

1. user chooses Assign;
2. user draws a face box;
3. compact canonical MB Person picker opens;
4. user searches/selects an existing Person;
5. or chooses **Create new Person**;
6. minimal new Person is created if needed;
7. face observation is linked to that Person;
8. user commits;
9. MB saves the face observation and provenance.

Do not require a full Person profile form during face teaching.

The same canonical Person picker should later be reused for **Reassign face**.

---

## 21. Background recognition processing

P2-I8.5 should prepare or use the existing background-job mechanism for later Learn behavior.

The architecture should support:

`face evidence added/changed/withdrawn`
→ affected canonical Person marked recognition-dirty
→ background recognition job queued
→ eligible video recognition performed
→ derived Appearance results updated
→ dirty state cleared only on successful completion

Long-running recognition must remain asynchronous.

Do not block the evidence viewer while recognition runs.

The actual Learn rail trigger may be implemented in the follow-on Learn increment.

---

## 22. Processing location

Where current architecture applies, computational face/video recognition continues on the configured backend machine/service used for that work, including the existing HP/HVRT path.

P2-I8.5 should not relocate heavy recognition into the UI machine merely because MB now owns the face evidence.

Data ownership and compute location are separate concerns.

---

## 23. UX impact during I8.5

This is primarily an architecture/data-ownership increment.

Do not redesign the product.

Visible behavior should remain consistent with the accepted MBUX and current P2 screens.

If face overlays are already shown, they should transition to MB-owned data without changing the user’s mental model.

Provider terminology should remain progressively disclosed rather than becoming normal family-facing UI.

---

## 24. Provenance behavior

An MB face observation may retain origin such as:

* imported from Immich;
* manually added by owner;
* confirmed from video recognition;
* confirmed from photo recognition;
* other future provider.

The user should not need to see provider details constantly.

However, evidence/provenance inspection must be able to answer:

* where did this face observation come from?
* who assigned this Person?
* was it imported or owner-created?
* has it been corrected?
* what was the previous state?

---

## 25. Migration safety

Before migration:

* inspect current Immich mapping tables;
* inspect existing provider identity records;
* inspect current face box APIs;
* inspect any existing MB face evidence schema;
* inspect current photo and video face rendering paths.

Migration must:

* be repeatable;
* be resumable where practical;
* avoid duplicate observations;
* not delete Immich records;
* not delete existing MB identity data;
* preserve existing canonical Person mappings;
* expose migration counts/status for verification.

---

## 26. Required migration reporting

At completion, provide counts including at minimum:

* total Immich face observations inspected;
* observations imported;
* observations linked to canonical MB People;
* observations imported as unassigned;
* observations skipped and reason;
* conflicts requiring review;
* duplicate observations avoided;
* failures.

These are engineering/owner verification outputs, not necessarily permanent family-facing UI.

---

## 27. Acceptance tests

P2-I8.5 is accepted only when all applicable items pass.

### Ownership

1. Existing Immich face observations have corresponding durable MB face-evidence records.
2. MB face overlays can render from MB-owned coordinates.
3. MB does not require live Immich face coordinates to display previously imported face boxes.
4. canonical MB Person remains the identity authority.

### Provenance

5. Imported face evidence retains Immich source/provider provenance.
6. Original Immich coordinates remain inspectable where relevant.
7. MB working coordinates are distinct from provider provenance coordinates when corrected.

### Override protection

8. Adjust an MB working box, run provider sync, and prove the adjustment remains.
9. Reassign an MB face to another Person, run provider sync, and prove the reassignment remains.
10. Unassign/withdraw an MB face, run provider sync, and prove it is not resurrected.
11. Provider state remains available as provenance rather than being destroyed.

### Provider independence

12. Disable Immich after migration and prove MB retains face observations and Person assignments.
13. MB-owned face evidence remains queryable without access to Immich’s face tables.
14. no MemoryBox face correction writes to Immich.

### Migration

15. Running migration twice does not duplicate observations.
16. migration is safe against partial completion/retry.
17. unknown provider faces do not silently create named canonical People.

### Recognition readiness

18. recognition exemplar selection can read MB-owned face evidence.
19. changed/withdrawn evidence can mark appropriate recognition state dirty or enqueue future work.
20. existing HVRT/video pathways are not broken.

### Regression

21. current I5/I6 Person identity behavior remains intact.
22. I7 SMS and I8 Email behavior remains intact.
23. existing Ask/photo/video retrieval does not regress.
24. original media remains unchanged.

---

## 28. Failure behavior

If provider sync or migration fails:

* do not destroy previously imported MB face evidence;
* preserve retry state;
* report failure clearly to owner/system health;
* do not falsely mark migration complete;
* do not fall back to silently treating Immich as the active authority.

---

## 29. Implementation sequence

Cursor should execute in this order **only after I8 is ACCEPTED and Tom authorizes build**:

### Step 1 — Inspect

Report current:

* Immich face APIs/data being used;
* provider identity schema;
* canonical Person mappings;
* face coordinate storage;
* photo face rendering path;
* video face rendering path;
* recognition exemplar source;
* provider synchronization behavior;
* correction/provenance schema;
* background job support.

### Step 2 — Plan

Produce the smallest migration/architecture plan satisfying this PRD.

Call out any conflict with:

* current MBPS-002 behavior;
* current schemas;
* existing P2-I5/I6 People implementation;
* I7/I8 work.

Do not implement until those conflicts are understood.

### Step 3 — Add MB-owned face evidence model

Extend existing domain structures where sound.

Do not duplicate canonical People.

### Step 4 — Migrate Immich observations

Perform idempotent import and verification.

### Step 5 — Switch read paths

Move MemoryBox face UX and recognition evidence reads to MB-owned observations.

### Step 6 — Add override-safe provider sync

New provider evidence may arrive; owner overrides remain authoritative.

### Step 7 — Regression and provider-loss tests

Prove independence.

### Step 8 — Update living specs

Record the new authority rule and roadmap insertion.

---

## 30. Required documentation updates

Cursor must update the living documentation/decision log so this rule cannot be lost later.

Document:

## Face evidence authority

MemoryBox owns active face observations used by MemoryBox.

## Provider role

Immich is a read-only provider of source media and face/identity evidence.

## Initial migration

Existing Immich observations are imported into MB-owned records.

## Ongoing sync

New provider observations may continue to enter MB through read-only synchronization.

## Owner authority

Owner-confirmed MB corrections override provider state.

## No resurrection

Provider sync must never silently restore an assignment or coordinates that the owner has changed or withdrawn in MB.

## Provider replacement

Replacing, upgrading, rebuilding, or removing Immich must not erase MB-owned face evidence.

## Original evidence

Source photos/videos are never altered.

## Write-back

MemoryBox does not write identity/face learning changes back to Immich.

---

## 31. Roadmap update

Insert:

**P2-I8.5 — MemoryBox Face Evidence Ownership & Immich Decoupling**

Execution sequence:

**P2-I6 → P2-I7 → P2-I8 → P2-I8.5 → P2-I9**

Numbered **I8.5** because it executes after **P2-I8 Richer Email** acceptance and before **P2-I9 Spoken Moments**. Do not use I7.5.

### Primary outcome

MemoryBox becomes the durable owner of the face evidence required for its own learning and recognition, while Immich remains a replaceable read-only provider.

### Prerequisites

* canonical Person mapping stable;
* I6 complete;
* I7 and I8 accepted before scheduled implementation.

### Blocks

The final Shared Evidence Viewer Learn rail face-editing implementation should not be considered complete until I8.5 is accepted.

---

## 32. Non-negotiable rules

1. **MemoryBox owns canonical Person identity.**
2. **MemoryBox owns active face-observation state used by MemoryBox.**
3. **Immich remains read-only.**
4. **Original media is never altered.**
5. **Provider provenance is preserved.**
6. **Owner corrections outrank provider state.**
7. **Provider sync cannot silently resurrect withdrawn/corrected MB state.**
8. **Immich replacement cannot wipe out MemoryBox face learning.**
9. **Unknown provider faces do not silently create named MB People.**
10. **Recognition outputs remain derived evidence, not original evidence.**
11. **Long-running recognition work remains asynchronous.**
12. **The UX continues to follow MBUX and existing accepted screen patterns.**

---

## 33. Completion report required from Cursor

When complete, report:

* files changed;
* schema/domain changes;
* migration mechanism;
* migration counts;
* provider-sync changes;
* face-read paths changed from Immich to MB;
* recognition-input changes;
* override/tombstone implementation;
* tests and results;
* regression results;
* behavior with Immich unavailable;
* documentation/roadmap files updated;
* any remaining dependency before implementing the Learn rail.

Do not proceed directly into the Learn rail implementation unless explicitly instructed. Learn-rail face editing is future work **after I8.5** (and I8.5 itself is **after I8**).
