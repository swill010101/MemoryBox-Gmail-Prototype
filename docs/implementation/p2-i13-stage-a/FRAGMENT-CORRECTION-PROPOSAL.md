# Bounded fragment correction proposal

Status: prepared for founder review, 2026-09-05. Tom approved preparing the correction and asked to consider restarting Learn and wiping fragments. That alternative is evaluated here; no deletion, Learn run or runtime publication has been performed or authorized by this proposal.

## Problem and scope

For source vid-c57dbd21f993f6d1, offline replay exactly matches 79 persisted half-second appearance moments to their observations. Samples are normally ten seconds apart while grouping permits eight seconds. The 15 owner-observed Gallery cards still need correlation to actual response membership. The original and its published full-source playable copy remain intact.

Initial scope is this source and the one traced Person/run. Use existing observations only. Preserve original moments, observation IDs, confidence, authority, withdrawals, owner annotations, machine transcripts and playback files. Other sources, people, Historian Capture and archive state remain unchanged. Do not elevate AI association to owner-confirmed identity.

## Recommended design

1. Capture or inspect the existing Gallery response read-only and match source/start/evidence IDs to the 79 stored moments. Explain the displayed subset before claiming a corrected card count.
2. Prepare a deterministic offline projection grouped by source, canonical Person, compatible run/model and evidence authority. Record policy version and all contributing observation/moment IDs. Separate presentation grouping from claims of continuous frame-level presence.
3. Use recorded sampling cadence when available. Legacy cadence inferred from timestamps must be explicitly labeled inferred; unknown cadence remains unmerged. Ten-second adjacent positive samples may be presented together under the reviewed policy, unless existing negative, ambiguous, withdrawn or scene-boundary evidence contradicts joining them. Never merge merely by display name or candidate label.
4. Keep the twenty-second gap unresolved initially. It could reflect a missed sample or a real identity gap; the supplied positives alone cannot decide. Tom's continuous-shot report is relevant owner evidence, but must be attached explicitly if used to bridge this gap. Do not silently assume missing observations mean continuous presence.
5. Display one source card with evidence-backed seek points or reviewed grouped moments, rather than treating every positive sample as a separate video. This is a proposed Gallery behavior requiring review against the accepted screen contract before implementation. Preserve access to original evidence details. Do not promise one continuous confirmed appearance over the entire source.
6. Do not extend presence beyond the last observation at 790.5 seconds to the source end at 1,105.104 seconds. Playback can still continue naturally to the source end, because playback duration and identity evidence are separate.
7. Publish only a reviewed, versioned projection or explicit non-destructive supersession after a source-specific before/after preview. Keep prior evidence recoverable. The exact storage mechanism and any migration require code/schema review before implementation. Rollback selects the previous presentation version; it does not delete evidence.

## Alternative: restart Learn and wipe fragments

Not recommended as the first correction. Rerunning the current grouping code can recreate the same short intervals. Deleting moments first removes useful lineage and could leave dependent suggestions or owner annotations inconsistent. Restarting Learn may also enqueue broader work unless admission pins its exact source/Person scope. The traced run was provider_seeded/newly_known_person; the trace does not prove that the Learn button directly created these moments.

If existing face assignments or coverage prove inadequate after grouping is corrected, propose a separate bounded Learn/re-recognition attempt: exact source/Person manifest, workload preview, retry budget, preserved history, and before/after review. Supersede affected results only after validation; do not wipe them. Retiring an exemplar remains a distinct action with stale-dependent-suggestion handling. A face regrouping does not satisfy voice-recognition acceptance or authorize new transcription.

## Acceptance and deployment sequence

- Offline tests: ten-second positives do not become one half-second card per sample; twenty-second/unknown gaps remain explicit; different people/sources/authority and genuine contradictory boundaries remain separate; deterministic replay preserves all lineage and respects withdrawals/owner overlays.
- Prepare a source-only dry-run preview showing old moments, proposed groups/card count, uncertainty, and every contributing ID. No DB writes or models are needed to prepare it.
- Review the preview and Gallery contract before implementing/publishing. Automated checks alone cannot prove the user-facing workflow.
- Tom deploys an exact reviewed commit using the locked launcher. Keep recognition/speech drains off and admission unset. Do not apply migrations or start Learn as part of startup.
- Verify the one source in Gallery: no repeated sample-only video cards, correct Person association, source seek, natural continuation, and return to the same Gallery context. Verify evidence details and owner annotations remain accessible.
- Stop for founder review before any broader projection, runtime supersession, migration or processing. Voice recognition, remaining unplayable sources and overall I13 acceptance remain open.

This proposal changes documentation only. No cleanup, record deletion, recognition, transcription, additional conversion or archive processing occurred.
