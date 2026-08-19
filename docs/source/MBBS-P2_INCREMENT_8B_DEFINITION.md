# MBBS-P2 Increment 8B — Person-Seeded Video Recognition & Learning

**Document:** MBBS-P2 Increment 8B Definition  
**Version:** v0.1  
**Status:** Approve — Definition locked; NOT build-authorized  
**Roadmap placement:** Immediately after P2-I8A Unified Communications Gallery & Timeline Precision and before P2-I9 Spoken Moments.

## 1. Purpose

P2-I8B turns the existing MemoryBox video-face recognition proof of concept into a repeatable operational capability.

The proof of concept established that MemoryBox can take a manually boxed and owner-identified face, learn from it, run recognition against a limited video set, find appearances of that person, and create time-bounded video slices. It did **not** establish either of the two production paths now required:

1. **Provider-seeded recognition:** start with a canonical MemoryBox Person already mapped to a known Immich Person, retrieve representative confirmed face evidence from Immich, generate MemoryBox recognition exemplars, scan video, and create Person-linked appearance observations/time slices.
2. **Owner-learned recognition:** from a paused video frame, allow the owner to box/band a face, identify the Person, press Learn, persist that confirmed exemplar, and use it for targeted recognition and reusable future processing.

I8B operationalizes both paths. It is a prerequisite for strong Person-level Spoken Moments in I9, but it does not itself perform speech transcription, diarization, speaker identification, or narrative synthesis.

## 2. Product Outcome

After I8B, MemoryBox can reliably answer the visual identity question:

> **Where does this known Person appear in my videos?**

For a supported known Person, MemoryBox can build a usable face exemplar set, scan configured video sources, record observed appearances, and expose trustworthy start/end appearance ranges that later capabilities can retrieve and correlate.

The user can also teach MemoryBox a Person directly from video and have that teaching reused.

## 3. Why I8B Exists Now

I9 Spoken Moments depends on time-addressable evidence and benefits materially from reliable Person identity in video. Today MemoryBox has demonstrated video-face recognition only as a proof of concept against a small set using a manually boxed face. MemoryBox has **not** yet built:

- the Immich-known-Person → face evidence → MemoryBox exemplar bridge;
- an archive-operational video scan pipeline;
- a durable owner Learn action;
- targeted rescanning after new learning or correction;
- an operational processing/status loop for this work.

These are infrastructure/capability prerequisites and should not be hidden inside I9.

## 4. Governing Architecture

### 4.1 Immich is a face-evidence provider, not the MemoryBox video-recognition engine

For I8B, Immich remains the operational provider of known still-photo People and confirmed face observations. MemoryBox uses supported Immich APIs to retrieve identity evidence.

MemoryBox does **not** depend on Immich face embeddings or direct Immich database access for I8B.

The preferred boundary is:

> **Immich tells MemoryBox which still-photo face observations belong to a known Person. MemoryBox crops representative faces, generates its own embeddings using the same recognition model used for video, and owns the resulting video observations/time slices.**

This preserves provider independence and avoids coupling MemoryBox to Immich embedding model versions, dimensions, or database internals.

### 4.2 Public API first

The supported Immich REST API is sufficient for the I8B bridge:

- resolve/read the Immich Person;
- enumerate assets associated with that Person;
- retrieve per-asset face records;
- retrieve bounding-box coordinates and image dimensions;
- retrieve source asset dates;
- retrieve preview/image bytes sufficient to crop the face.

Direct Immich DB access is **not required**. A future performance optimization may revisit bulk retrieval, but it is not an I8B capability requirement.

### 4.3 MemoryBox owns video recognition results

Video face observations and resulting appearance ranges used by MemoryBox are MemoryBox-derived evidence with provenance. Immich does not need to be written back to.

This does **not** pull forward the later full face-evidence ownership / Immich decoupling increment. I8B may consume provider-known still-face evidence while MemoryBox owns only the video-derived observations and learning needed for this capability.

## 5. In Scope

### 5.1 Provider-seeded exemplar retrieval

Given a canonical MemoryBox Person mapped to a known Immich Person, I8B shall:

1. resolve the Immich Person ID;
2. enumerate associated Immich assets using supported API paths;
3. retrieve face records for those assets;
4. retain only face observations assigned to the target Immich Person;
5. retrieve the corresponding preview/image bytes;
6. crop face regions using the returned bounding boxes and image dimensions;
7. preserve source asset, face ID, capture date, box coordinates, and provider provenance for every candidate exemplar.

No assumption may be made that `GET /people/{id}` returns the complete face catalog. I8B must use the supported asset/face enumeration path required by the current Immich API.

### 5.2 Exemplar curation

I8B shall not treat one feature photo as sufficient recognition training for a Person.

MemoryBox shall select a representative exemplar set from the available confirmed face observations. Selection must favor both **quality and diversity**, including where available:

- age/time-period coverage;
- frontal, three-quarter, and useful profile variation;
- expression variation;
- glasses/no-glasses or other material appearance variation;
- lighting/background variation;
- image sharpness and usable crop size;
- avoidance of excessive near-duplicates.

The exact number of exemplars is an implementation/tuning decision and shall not be hard-coded by this definition. The system should select enough representative evidence to improve robustness without unnecessarily processing hundreds of redundant faces.

Where source dates are available, they should be retained so future recognition may prefer age-appropriate exemplars without losing cross-age evidence.

### 5.3 MemoryBox embeddings

Selected face crops shall be embedded by MemoryBox using the same compatible face-embedding model used to evaluate video frames.

Immich embeddings are not required and shall not be read directly from the Immich database in I8B.

Each generated exemplar shall preserve provenance back to the provider face observation or owner-learned video frame from which it was created.

### 5.4 Video recognition pipeline

I8B shall operationalize the proven video-recognition path across configured video-bearing sources/libraries.

The pipeline shall support:

1. discover eligible video;
2. sample/process frames using the established recognition approach;
3. detect candidate faces;
4. compare candidate face embeddings against the Person exemplar set;
5. record positive/uncertain observations with confidence/provenance;
6. group sufficiently continuous observations into Person appearance ranges/time slices;
7. persist those observations/ranges for retrieval;
8. expose processing status and failure information.

A source video remains immutable original evidence. Face observations and appearance ranges are derived, rebuildable evidence.

### 5.5 Appearance time slices

For a recognized Person, MemoryBox shall create time-addressable appearance ranges of the form:

- source media asset;
- Person;
- start offset;
- end offset;
- supporting face observations;
- recognition confidence/state;
- exemplar/model/provider provenance;
- processing version/time.

Opening a recognized appearance must be capable of returning to the source video at or near the relevant start offset.

### 5.6 Owner Learn path

I8B shall turn the existing POC interaction into an operational reusable learning path:

1. owner pauses a video on a useful frame;
2. owner boxes/bands a visible face;
3. owner assigns an existing canonical MemoryBox Person;
4. owner invokes **Learn**;
5. MemoryBox stores the confirmed face observation/exemplar with owner-confirmed provenance;
6. MemoryBox generates its own embedding;
7. the new learning becomes available for recognition;
8. MemoryBox can trigger a targeted rescan of appropriate video rather than requiring a full archive rerun;
9. newly found observations/time slices become normal MemoryBox recognition evidence.

Owner-confirmed exemplars and provider-seeded exemplars are peers in the MemoryBox recognition set, with distinct provenance.

### 5.7 Corrections and withdrawal

I8B shall support enough correction behavior to make learning safe operationally:

- a false Person assignment can be corrected or removed;
- owner-confirmed negative/corrective evidence is preserved;
- removed/corrected observations are not silently recreated merely because the same provider evidence is seen again;
- targeted reprocessing can update affected video recognition results;
- uncertain identity remains uncertain rather than being forced to a Person.

Full provider decoupling, global face merge/review UX, and complete still-photo face ownership remain later work unless strictly required to satisfy this increment's acceptance gate.

### 5.8 Incremental and targeted processing

I8B must not remain a one-time script.

At minimum, the operational engine must distinguish:

- initial processing of an eligible video set;
- processing of newly discovered/changed videos;
- targeted reprocessing caused by new Person exemplars;
- targeted reprocessing caused by correction/withdrawal;
- no-op when nothing relevant has changed.

Implementation may choose queues/jobs/batches, but work state must be durable enough to resume/retry rather than requiring manual one-off reruns.

### 5.9 Processing visibility

The owner/developer path shall expose enough status to answer:

- which Person is being processed;
- which videos are pending/processing/complete/failed;
- why an item failed;
- whether a run was provider-seeded, owner-learned, incremental, or correction-triggered;
- counts of candidate/accepted/uncertain observations and resulting appearance ranges where practical.

This may use existing developer/Archive Health patterns; I8B does not require a new family-facing operations product.

## 6. Explicitly Out of Scope

I8B does **not** include:

- replacing Immich as the still-photo face recognition provider;
- full Immich removal or appliance migration work;
- direct use of Immich database embeddings;
- writing MemoryBox corrections back to Immich;
- complete migration of all still-photo face observations into MemoryBox ownership;
- family-tree or relationship changes;
- speech-to-text transcription;
- speaker diarization;
- voice-print enrollment or speaker recognition;
- Spoken Moments retrieval (I9);
- cross-modal event correlation (I10);
- evidence-backed narrative generation (I11);
- broad new face-clustering science beyond what is required to operationalize the proven recognition approach.

## 7. Trust and Provenance Rules

1. A provider-known face is evidence, not infallible truth.
2. Owner-confirmed identity outranks provider inference for MemoryBox learning/correction purposes.
3. Unknown or uncertain faces remain unknown/uncertain.
4. Every exemplar must preserve its origin.
5. Every video observation must preserve the model/version and evidence used to produce it.
6. Original video is never altered.
7. Derived observations/time slices may be rebuilt as models improve, while corrections/withdrawals must be preserved and respected.
8. MemoryBox must not imply that a Person is present in a video when recognition confidence does not meet the product threshold.

## 8. Required Data/Service Concepts

The exact schema is implementation-owned, but I8B requires durable concepts equivalent to:

### Person Face Exemplar
- canonical Person ID;
- exemplar source type: Immich provider face / owner-confirmed video face;
- provider/source IDs;
- source asset/frame/time;
- crop/box metadata;
- capture date when available;
- MemoryBox embedding/model version;
- quality/diversity metadata as needed;
- active/withdrawn state;
- provenance.

### Video Face Observation
- video asset ID;
- frame/time offset;
- face box;
- candidate/assigned Person;
- confidence;
- supporting exemplar/model information;
- review/correction state;
- provenance.

### Video Person Appearance Range
- video asset ID;
- Person ID;
- start/end offsets;
- supporting observation IDs;
- confidence/status;
- processing/model version;
- provenance.

The implementation may normalize or combine these concepts, but it must preserve the semantics above.

## 9. Operational Flow

### 9.1 Provider-seeded path

Canonical MB Person  
→ mapped Immich Person  
→ enumerate Person assets  
→ retrieve target face boxes  
→ retrieve preview bytes  
→ crop confirmed faces  
→ quality/diversity selection  
→ generate MB embeddings  
→ scan eligible video  
→ record observations  
→ form appearance ranges  
→ index/retrieve

### 9.2 Owner-learned path

Video frame  
→ owner boxes face  
→ owner selects Person  
→ Learn  
→ persist confirmed exemplar  
→ generate MB embedding  
→ targeted rescan  
→ observations  
→ appearance ranges  
→ reuse in future processing

## 10. Acceptance Gate

I8B is accepted only when the following are demonstrated on real FlightSim data.

### A. Immich-seeded Person recognition

For at least one canonical MemoryBox Person with a mapped known Immich Person:

1. MemoryBox retrieves that Person's face evidence through supported Immich APIs without direct DB access.
2. MemoryBox constructs a representative exemplar set from multiple confirmed faces rather than relying only on the feature photo.
3. Exemplar provenance can be traced to the source Immich face/asset.
4. MemoryBox scans a meaningful video corpus using its own embeddings/model.
5. Recognized appearances are stored as time-bounded Person appearance ranges.
6. Opening a result can jump into the source video at the relevant range.

### B. Owner Learn

1. From a paused video, the owner can box/band a face and assign a canonical Person.
2. Learn persists a confirmed MemoryBox exemplar.
3. The exemplar is reusable outside that single frame/video.
4. A targeted recognition run finds at least one additional valid appearance when appropriate test evidence exists.
5. The resulting observations/ranges preserve owner-confirmed provenance.

### C. Correction safety

1. A deliberately incorrect match can be corrected/removed.
2. Reprocessing respects that correction rather than silently restoring the rejected identity.
3. Uncertain matches can remain unassigned.

### D. Operational behavior

1. Processing is not dependent on a one-off developer script.
2. Failed work is visible and retryable.
3. Newly added eligible video can be processed incrementally.
4. New learning can trigger targeted work without requiring an unconditional full-library rerun.
5. The system can report enough status/counts to diagnose whether recognition is actually operating.

### E. Scale proof

Acceptance must use a **meaningful FlightSim subset beyond the original POC sample** and include enough variation to test:

- more than one video;
- more than one appearance range;
- multiple Immich exemplars;
- age/pose/image-quality variation where the available archive permits;
- at least one owner-learned exemplar;
- at least one correction/withdrawal path.

Exact corpus size is determined during implementation planning, but acceptance may not be satisfied by rerunning only the original small POC dataset.

## 11. Critical Success Factors

1. **The Immich bridge is real.** A known provider Person can seed MemoryBox video recognition without manual face boxing.
2. **Exemplars are representative, not merely convenient.** Selection considers quality plus age/pose/diversity rather than one feature image.
3. **MemoryBox controls its recognition space.** Face crops are re-embedded by MemoryBox; I8B is not coupled to Immich's internal vectors.
4. **The POC becomes an engine.** Processing is durable, repeatable, incremental, and diagnosable.
5. **Learn changes future behavior.** Owner teaching is persisted and reused rather than being a UI-only annotation.
6. **Time slices are trustworthy.** Recognition creates real Person appearance ranges that point back to original video.
7. **Corrections stick.** User rejection/correction is not silently undone by provider sync or reprocessing.
8. **Unknown remains safe.** The system favors unassigned/uncertain over a confident-looking wrong identity.
9. **No strategic overreach.** Immich remains the still-photo provider for now; I8B does not become the later decoupling project.
10. **I9 is unblocked.** At acceptance, Spoken Moments can rely on an operational source of visual Person-in-video evidence rather than a POC-only path.

## 12. Open Implementation Questions for Cursor Planning

These are implementation questions, not product decisions, and should be resolved during planning without changing the scope above:

1. What exact existing POC code can be promoted versus rewritten?
2. Which supported Immich asset enumeration path is most stable on FlightSim given prior metadata-search resets: timeline first, metadata search fallback, or another supported combination?
3. Should exemplar selection initially use deterministic heuristics only, or embedding clustering/diversity scoring as well?
4. What initial quality thresholds should reject unusable crops?
5. What sampling interval/frame strategy from the POC should be retained for operational scanning?
6. What temporal-gap rule groups face observations into one appearance range?
7. What targeted-rescan scope is appropriate after new learning: same video, recent/unprocessed video, all configured video for that Person, or queued priority tiers?
8. Which existing job/status/Archive Health mechanism should own processing visibility?
9. What minimum FlightSim corpus is large/diverse enough for acceptance while keeping I8B bounded?

## 13. Build Authorization

This document is a **definition draft only**.

Cursor may inspect existing code, validate assumptions, and return an implementation plan after founder approval of the definition. Runtime implementation does **not** begin until explicit founder build authorization.

---

**Roadmap sequence after this draft is approved:**  
P2-I8A Unified Communications Gallery & Timeline Precision → **P2-I8B Person-Seeded Video Recognition & Learning** → P2-I9 Spoken Moments.
