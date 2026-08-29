# MBPS-002 — MemoryBox Product Specification — P2 Iteration

**Status:** Locked for P2 iteration (founder 2026-08-12)
**Source:** `docs/source/MBPS-002_MemoryBox_Product_Specification_P2_Iteration_v0.1.docx`
**Authority:** Product WHAT for P2. EVSs remain validation authority.

---

MBPS-002
MemoryBox Product Specification — P2 Iteration
Review Draft v0.1
Prepared August 12, 2026
Document Purpose & Status
MBPS-002 defines WHAT MemoryBox must become during the P2 iteration. It builds on the P1 product baseline and translates the completed Experience Validation Scenario catalog and the accumulated P1/P2 backlog into a coherent P2 product scope. It intentionally does not prescribe implementation details, service internals, database schemas, model choices, or Cursor task decomposition.
Status: Review Draft. This document is intended for founder review before it becomes the product specification supplied to Cursor for P2 implementation planning. EVSs remain the validation authority for user outcomes; MBCAP remains the reusable capability layer; MBUX governs interaction and design behavior; implementation increments must preserve traceability back to these sources.
1. P2 Product Objective
P1 proved a foundational set of MemoryBox capabilities and architecture. P2 must do two things at the same time: turn those capabilities into one coherent MemoryBox product, and materially expand the underlying archive-understanding capabilities required to work across a real family’s photos, video, audio, communications, stories, people, events, places, and artifacts.
P2 is therefore both product maturation and capability expansion. It is not simply a UX pass, and it is not a technology-gap phase.
Product maturation: coherent navigation, high-volume exploration, Archive Health, Settings, saved/dynamic views, summaries/highlights, consistent correction, and a mature family-facing experience.
Capability expansion: SMS/text, richer email, face and voice learning, video timeslots/searchable moments, audio/video transcription, speaker/person linking, cross-source correlation, relationship inference, and evidence-backed narrative generation.
Experience completion: EVSs are complete only when the user’s intended outcome is complete, including drill-down, correction, provenance, and return to context where required.
2. P2 Planning Basis
The P2 scope is grounded in MBEVS-001 v1.0, MBRM-001 MemoryBox Roadmap & P2 Backlog Notes, MBCAP-001 P2 Initial Capability Catalog, and the accepted P1 product baseline. The current EVS catalog contains 260 scenarios across all phases. Of these, 89 are P2, 48 span P1–P2, and one spans P2–P3; these 138 scenarios form the principal P2 validation pool while already-supported P1 scenarios remain regression requirements.
The product specification groups those scenarios into reusable product requirements. It does not create one feature or implementation increment per EVS.
3. Product Principles That Do Not Change in P2
People are anchors; Stories connect people, places, moments, artifacts and evidence.
Evidence First. A fluent answer never outranks the evidence supporting it.
Create No False Memories. Uncertainty, inference and external context must be visible and distinguishable from authentic family evidence.
Original Evidence Is Sacred. Derived transcripts, recognition results, annotations and generated summaries are additive layers.
Import, Don’t Replace. Existing family systems and prior owner work are inputs, not chores to repeat.
Capture should be easier than organization. The family teaches through natural actions and MemoryBox remembers.
AI is the engine, not the product. The family outcome remains primary.
Local First, Cloud Optional; family ownership, exportability and provenance remain product requirements.
4. P2 Product Scope
P2 is organized below as product requirement areas. Each area may be implemented through several capabilities and increments, and each must ultimately trace to the EVSs it enables.
4.1 Product Shell, Navigation & High-Volume Exploration
P2-UX-01 — Coherent product shell. Ask, Library/Timeline, People, Stories, Journal, Artifacts, Review & Learn, Settings and Archive Health must feel like parts of one product. Open → inspect → act → return must preserve meaningful context.
P2-UX-02 — Timeline-first high-volume media exploration. Large photo/video result sets must support timeline-centered navigation, adaptive time zoom, clustering, banding, preview, filters, drill-down and return without forcing confidence scores or provider structure to become the primary interface.
P2-UX-03 — Natural and structured refinement. Natural-language/voice refinement must work alongside People, Event, Trip, Place, modality and other useful structured filters.
P2-UX-04 — Progressive disclosure. Family-facing exploration remains simple; technical provider, processing and confidence details appear only when useful for an owner decision or advanced workflow.
4.2 Archive Health, Dashboard & Guided Work
P2-AH-01 — Archive Health. Evolve P1 Status into an owner-facing view of archive coverage, provider/processing health, source counts, searchable moments, People, Stories, Artifacts, Journal, communications and meaningful gaps.
P2-AH-02 — Small actionable queues. Do not present thousands of deficiencies. Surface a small number of high-value “Work on these now” actions such as unknown people, missing dates, missing locations, unlinked artifacts, incomplete relationships or unreviewed identity candidates.
P2-AH-03 — High-leverage cleanup. Prioritize corrections whose value propagates broadly, such as dating one source video so its derived moments can be positioned correctly on the timeline.
4.3 Canonical People, Provider Identity & Continuous Learning
P2-ID-01 — Canonical MemoryBox Person. MemoryBox continues to own canonical Person identity. Provider identities such as Immich People remain mapped provider records with provenance rather than becoming the canonical object themselves.
P2-ID-02 — Known Immich people require no redundant enrollment. A named/confirmed Immich Person should automatically create or map to a canonical MB Person when no conflicting identity exists. The owner should not have to re-create a person already identified in Immich.
P2-ID-03 — Continuous provider identity synchronization. This is not a one-time seed. If the owner later names, merges, splits or corrects a Person in Immich, MemoryBox must detect and reconcile the provider change. Ambiguous conflicts route to review rather than silent destructive updates.
P2-ID-04 — Face evidence ownership and provenance. MemoryBox may use confirmed Immich face assets, manually boxed photo/video faces and confirmed recognition results as reusable recognition evidence while preserving source, bounding box, confidence, confirmation and provenance.
P2-ID-05 — Cross-modal identity. A Person may accumulate independently traceable identity evidence from face, voice, communications, owner confirmations, relationships, stories and other sources. No individual provider becomes the sole authority.
4.4 Video Understanding & Searchable Moments
P2-VID-01 — Source video versus derived moment. The source video remains immutable evidence. Derived face, speaker, transcript, scene and other time-based observations are rebuildable evidence layers.
P2-VID-02 — HVRT-style timeslotting. Recognition must identify where a person appears, not merely that the person occurs somewhere in a video. Person appearances must support start/end time, representative frame, confidence, method, correction state and provenance.
P2-VID-03 — Searchable video moments. Video portions must be searchable by people, speech/transcript, events, places, scenes/objects where supported, stories and other linked evidence. Results should open at the relevant moment.
P2-VID-04 — Face teach/correct in video. The owner must be able to identify or correct a face in a video frame and associate it with a canonical MB Person; confirmed observations may become new recognition evidence.
P2-VID-05 — Reuse proven HVRT learning. P2 should adapt proven HVRT timeslice, face and media-analysis concepts where they remain suitable rather than rediscovering them as greenfield research.
4.5 Audio, Speech, Speaker Identity & Spoken-Moment Retrieval
P2-AUD-01 — Audio/video STT. Speech in audio and video must be transcribed into time-aligned searchable text while the authentic source recording remains preserved.
P2-AUD-02 — Speaker/person association. Diarized speakers and confirmed voice exemplars may be associated with canonical MB People. Owner corrections and voice exemplars must be reusable and provenance-preserved.
P2-AUD-03 — Spoken-moment retrieval. Queries such as “Play Peggy talking about Alaska,” “Find every recording where Dad talks about the war,” or “Let me hear Grandpa’s voice” return relevant passages/time ranges, not merely containing files.
P2-AUD-04 — Search by person across authentic voice. Once speaker identity is sufficiently known, MemoryBox can retrieve all relevant authentic audio/video moments associated with that Person, subject to confidence and review rules.
4.6 Communications: SMS/Text & Richer Email
P2-COM-01 — SMS/text as first-class evidence. P2 adds legitimate SMS/text ingestion, original preservation where available, participant association, timestamp, search, Person/event/trip correlation and use as narrative evidence.
P2-COM-02 — Richer email understanding. Expand P1 email beyond basic retrieval to thread awareness, participant identity, attachments, dates/events, places, relationships, significant exchanges, artifact/story links and cross-source correlation.
P2-COM-03 — Communication provenance. Message source, participants, timestamps, thread/context and import provenance must remain accessible behind conclusions.
4.7 Relationships, Places, Events & Cross-Source Correlation
P2-GRAPH-01 — Derived kinship and relationship reasoning. MemoryBox may derive relationships from the canonical relationship graph, but derived kinship remains distinguishable from directly asserted facts and must expose the path used.
P2-GRAPH-02 — Cross-source correlation. People, Places, Events, Trips, Stories and evidence must correlate across photos, video, audio, communications, calendars, documents, Stories, Journal and Artifacts when the evidence supports a connection.
P2-GRAPH-03 — Correction propagates safely. Corrections to People, relationships, dates, Places or Events must update dependent discovery behavior without erasing the historical provenance of prior assertions.
4.8 Evidence-Backed Narrative, Summary & Historical Context
P2-NAR-01 — Evidence-backed narrative generation. MemoryBox may synthesize multiple evidence sources into a coherent narrative while distinguishing known facts, human recollections, inference, uncertainty, disagreement and missing evidence. Generated narrative is not itself authoritative evidence.
P2-NAR-02 — Owner review for saved narratives. Substantial AI-composed narratives require review/edit/save before becoming a persistent Story or narrative object attributed to the owner.
P2-NAR-03 — Trip, year and Person summaries. Large result sets may produce concise summaries and representative highlights with full drill-down to underlying evidence. Technical image quality and family significance are separate concepts.
P2-NAR-04 — External historical context. P2 may answer questions about U.S. or world events surrounding a family photo/video date and may weave selected external facts into a year summary. External facts require source citation and must be visually/semantically distinguishable from family evidence. MemoryBox must not imply that an external event affected the family without family evidence supporting that connection.
4.9 Dynamic Views, Collections & Result Persistence
P2-VIEW-01 — Save intent, not only IDs. Generated views should preserve the original query plus normalized intent such as date band, People, Place/Trip/Event, modalities, trust/highlight refinements, sort and view state.
P2-VIEW-02 — Live view. A live saved view re-runs against the current archive and models so newly added evidence or improved processing can improve the result.
P2-VIEW-03 — Curated and frozen modes. Curated mode preserves owner selections/order while retaining underlying intent; Snapshot/Frozen mode preserves an exact result set/version for reproducibility or sharing.
4.10 Capture, Guided Capture & Family Contribution
P2-CAP-01 — Proactive memory capture. MemoryBox may prompt the owner from gaps or meaningful evidence—unidentified people, artifacts, incomplete Stories, unexplained events or Personal Profile questions—and preserve answers as provenance-backed evidence.
P2-CAP-02 — Low-friction channels. Capture should continue to support typed, voice, email and other configured channels using the same domain and provenance model.
P2-CAP-03 — Controlled family contribution. P2 may deepen owner-mediated family contribution with contributor identity, provenance, review, ownership and correction controls. Full independent multi-user participation remains late-P2/P2.5 unless explicitly promoted during roadmap review.
4.11 Correction, Trust, Authority & Provenance
P2-TRUST-01 — Consistent correction lifecycle. Major domain objects must support appropriate combinations of correct, merge, split, unlink, supersede, withdraw and restore/reconsider rather than destructive overwrite.
P2-TRUST-02 — Contributor and assertion authority. MemoryBox must preserve who supplied evidence, who made an assertion, who corrected it, when, and with what authority/confidence. An original Story/recollection remains distinguishable from another person’s assessment of it.
P2-TRUST-03 — Identity uncertainty. Face, voice and relationship inferences must not silently become confirmed facts. Human confirmation has high authority but still retains provenance and revision history.
P2-TRUST-04 — Authentic versus generated media boundary. Synthetic or imagined media is not authentic family evidence. P2 must preserve this boundary even if future generations of MemoryBox support explicitly requested illustrative media.
4.12 Settings, Providers & Processing Controls
P2-SET-01 — Mature Settings area. Settings must cover providers/connections, storage/archive locations, processing state, recognition services, archive configuration and owner-appropriate controls without leaking this complexity into everyday exploration.
P2-SET-02 — Provider health. Provider/source health and ingest state should be visible and actionable for the owner, including degraded processing and reprocessing where appropriate.
4.13 Late P2 / P2.5 Multi-User Identity & Context
P2-MU-01 — One shared archive. Multiple authorized users operate against one canonical People/evidence graph, not separate family archives per person.
P2-MU-02 — Account versus Person. Each account maps to a canonical MB Person but retains an archive-level role and permissions. Relationship context such as “my father” depends on the active user.
P2-MU-03 — User-specific context. Preferences, Journal/Profile data, permissions, contribution history and relationship-relative queries become user-specific while evidence remains shared according to authorization.
P2-MU-04 — Voice convenience, not sole authentication. Voice recognition may select user context for convenience, with explicit switching as fallback; voice alone must not authorize sensitive actions.
5. Core P2 Experience Patterns
Ask → Narrative → Evidence → Drill-down → Correction/Feedback → Learning — A broad family question can cross sources, return a concise human answer, expose supporting evidence and permit useful corrections without losing context.
Explore → Filter/Timeline → Open Moment → Act → Return — High-volume discovery preserves result set, filters, timeline position and exploration context.
Capture → Transcribe/Understand → Link → Review → Save — Voice/text/email capture is easy; significant authored content is reviewed before durable save.
Recognize → Confirm/Correct → Reuse Evidence — A face or voice confirmation improves later recognition while preserving provenance.
Gap → Work on this now → Resolve → Propagate — Archive Health turns a useful gap into a direct correction experience whose benefit propagates across related evidence.
Saved intent → Reopen → Refresh/Curate/Freeze — Saved exploration can remain live, become curated, or be frozen intentionally.
6. P2 Scope Boundaries
The following boundaries protect P2 from becoming an unlimited technology program and preserve the product’s trust model.
Do not turn every EVS or every MBCAP capability into its own implementation increment. Roadmap increments should cluster coherent user outcomes and reusable machinery.
Do not replace canonical MemoryBox People with provider-specific identity records; improve synchronization and mapping instead.
Do not make confidence-first or provider-first UX the default family experience.
Do not treat AI-generated narrative, recognition, summaries or external web context as original family evidence.
Do not silently create relationships, identities, dates or stories when evidence is uncertain.
Do not require full multi-user family account architecture before the primary P2 owner experience is mature.
Do not include imagined/synthetic family images, videos or speech as active P2 evidence features. EVS-253 and EVS-257 through EVS-260 remain P3/future unless explicitly reconsidered with a separate synthetic-media policy.
7. P2 EVS Validation Framework
P2 acceptance is scenario-driven. The product is not complete because a service endpoint exists or a screen renders. A mapped EVS passes only when the intended user outcome can be completed with appropriate evidence, trust behavior, correction path and context continuity.
P2-EVS-01 — Traceability. Every active P2 EVS must map to at least one P2 roadmap increment before implementation begins. Multi-step EVSs may also map to an Experience Flow and multiple reusable capabilities.
P2-EVS-02 — Regression. P1 EVSs that represent foundational behavior remain regression requirements; P2 cannot gain richness by breaking accepted P1 trust or evidence behavior.
P2-EVS-03 — Partial versus complete. A scenario that returns an initial result but cannot perform required drill-down, jump-to-moment, review, correction, save or evidence inspection is only partially met.
P2-EVS-04 — Real family evidence. Acceptance should continue using real-family material where legitimate and practical, because ambiguity, missing dates, duplicate identities and imperfect media are part of the product problem.
8. P2 Completion Criteria
A new or returning owner can navigate MemoryBox as one coherent product rather than a set of P1 tools.
High-volume photo/video exploration is practical at real archive scale.
Known provider identities, especially Immich People, flow into canonical MB People continuously without redundant owner enrollment while retaining provider separation/provenance.
Video can be searched at the meaningful moment/timeslot level using Person appearance and other supported time-based evidence.
Authentic audio/video speech is transcribed, time-aligned, searchable, and can be linked to canonical People with correction/reuse loops.
SMS/text and richer email participate in the same evidence and cross-source correlation model.
Cross-source summaries and narratives are evidence-backed, reviewable and transparent about gaps/inference.
Dynamic views and summaries make large archives usable without hiding underlying media.
Archive Health guides useful work without turning MemoryBox into an administrative cleanup product.
Correction, provenance and authority behavior are consistent across major domain objects.
Settings/provider health are mature enough to operate P2 without exposing technical complexity in normal family exploration.
Every active P2 EVS has an implementation/acceptance home and the EVS traceability review identifies no unexplained unmapped scenarios.
9. P2 EVS Coverage Snapshot
Current catalog phase counts: 115 P1; 48 P1–P2; 89 P2; 1 P2–P3; 7 P3. The 138 P2-relevant scenarios (P1–P2 + P2 + P2–P3) span the product broadly; the largest taxonomy groups overall include People & Identity, Stories & Narrative, Artifacts, Communications, Photos, Places, Guided & Journal Capture, Corrections & Learning, Video and Trust & Evidence.
The roadmap phase following approval of MBPS-002 should map each active P2 EVS to a coherent implementation increment and identify its supporting capabilities. This specification should remain the product-level authority for what P2 must deliver; the roadmap determines sequence.
10. Open Review Questions Before Cursor Handoff
Should controlled family contribution remain owner-mediated through most of P2, with independent accounts held for late P2/P2.5?
Which external historical-context experiences (EVS-254 through EVS-256) belong in the first P2 roadmap versus a later P2 increment?
What minimum provider synchronization cadence/trigger constitutes acceptable continuous Immich Person synchronization?
Which recognition confidence thresholds are product defaults versus owner-adjustable advanced settings?
Which P2 multi-step EVSs should be formalized first in MBEF-001 Experience Flow Catalog before implementation?
What exact P2 acceptance set will be used for the first real-family demonstration after the product-shell/high-volume UX work?
Do any P2 EVSs need to be intentionally deferred because they are product-maturity or legal/privacy risks rather than technical gaps?
11. Next Planning Step
After founder review and approval of MBPS-002, create one authoritative Cursor-ready P2 roadmap. The roadmap should cluster EVSs and capabilities into coherent increments, state dependencies and acceptance intent, and maintain EVS → Experience Flow (where needed) → Capability → Increment traceability. Cursor should receive the approved specification and roadmap rather than a sequence of disconnected feature requests.
