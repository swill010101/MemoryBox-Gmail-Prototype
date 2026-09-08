# I13 acceptance checklist - voice remains required

## Authority and scope

Confirmed against `docs/product/MBPRD-P2-I13_Video_Face_Speech_Voice_Learning_v0.2.docx`, section 8 (Voice), and `docs/product/MBBS-P2_INCREMENT_13_DEFINITION_DRAFT_v0.2.docx`, section 8 (Voice). Both require confirmed samples to produce reviewable suggestions including off-camera speech, without requiring face presence. Tom reaffirmed this requirement on 2026-09-05 when approving Stage A correction 1ecad04e8bf8f798181bbce4447b4941d1df8947.

This checklist makes existing requirements explicit; it does not replace the accepted definition or authorize later implementation/processing. The roadmap amendment open in Tom's IDE preserves the accepted I13 definition and requires independent face/voice evidence. Its demo journey allowing face OR voice is not a waiver of full I13 voice acceptance.

## Required bounded voice proof - pending

- [ ] In MB, select timestamp-backed speech, assign a Person, and confirm sample quality. Assignment for learning must not be presented as already-proven recognition.
- [x] Use confirmed source-audio samples to produce reviewable voice suggestions in separately authorized bounded recognition. Two bounded real-audio pilots produced Eugene and Tom results with immutable admission provenance; transcript text alone was not used as recognition proof.
- [x] Demonstrate correct off-camera speaker suggestions without requiring a visible face for one bounded case: Tom pilot held-out O1 matched at `0.487` with T2 training; this is not generalized off-camera accuracy.
- [ ] Preserve independent face and voice evidence and show corroboration transparently when both exist.
- [ ] Review poor-audio, multiple-person and no-match cases against owner-confirmed annotations; uncertain output must not masquerade as confirmed identity.
- [ ] Record source/interval provenance, model and threshold versions, measured results and errors. Threshold policy remains for founder review after bounded measurement; no numeric accuracy target is invented here.
- [x] Preserve immutable machine transcripts and additive audited owner overlays. Retirement and lifecycle reprocessing verified: T1 retirement stale cascade and fresh-reference pilot `66fb93af…` completed without altering legacy queues or current Tom/N1/Patio evidence.
- [ ] Prove scope/cardinality limits, queue/retry/worker gates and locked archive behavior throughout. Founder acceptance, archive unlock and archive start remain separate decisions.

## Completed bounded pilot evidence

- [x] One bounded real-audio pilot recorded two Eugene Will matches (H1 `0.633`, U1-clear `0.570`) against T1 and rejected off-camera Tom Will as Eugene (O1 `0.105`).
- [x] Results are additive, read-only review evidence with source/time, model-threshold, admission and stopped-state provenance; no legacy queue or transcript-overlay writes occurred.
- [x] A separate bounded Tom pilot used T2 training and held-out off-camera O1: Tom matched O1 at `0.487`; the H1 and U1-clear Eugene controls were Tom `no_match` at `0.122` and `0.066`. The result endpoint showed both admissions stopped and current.
- [x] A separate bounded N1 Unknown no-match pilot rejected TV announcer speech as Tom at `0.112`; narrow evidence only.
- [x] Exemplar retirement stale cascade and bounded lifecycle reprocessing: T1 retirement made admission `1039c733…` stale; fresh `R1-gs2-fresh` pilot `66fb93af…` completed with expected held-out outcomes while Tom, N1, and Patio results remained current.
- [ ] Overlap/poor-audio handling, face/voice corroboration, and generalized accuracy remain unproven.
## Current evidence

Stage A correction: 26 offline tests pass on the dev machine; FlightSim passed the earlier 22-test commit. Source membership of the exact 22 videos is confirmed. Corrected preview is transcription-only (22 items, zero Person targets), so it cannot satisfy the voice recognition checks above. No voice recognition run, migration, or runtime processing was performed for this update. Full annotation-only overlays and the remaining voice lifecycle proof are pending later implementation/authorization.

Do not mark full I13 accepted based on transcription success, the Stage A tests, existing combined Learn code, or the synthetic playback proof.
