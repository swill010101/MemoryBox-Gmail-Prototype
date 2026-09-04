# P2-I13 assessment ? founder review

Date: 2026-09-04. Assessment-only authorization. **No implementation, remediation, recognition, transcription, migration, or archive unlock performed.**

Baseline: `12fe18305f81350f28f8bcc0851c8a1091103f91`.
Branch: `codex/p2-i13-assessment`.
Isolated worktree: `C:\MemoryBox-worktrees\p2-i13-assessment`.

## Recommendation

Review this assessment before authorizing any build. First resolve the authoritative runtime location and exact corpus membership; implement an enforced scope gate before exercising existing Learn or processing flows. Preserve the existing Gallery, source player, transcript selection, face learning, queues, and retrieval components. Extend them in small steps after approval.

Confirmed findings:

- Full reconciliation requests every eligible Person ? video pair even when those sources were already queued. The existing queue uniqueness does not bound this initial workload; this matches Tom's reported historical cause of the 155K expansion.

- The actual Gallery player binder seeks to a source moment but deliberately clamps playback to its end. A synthetic media-element check reproduces a forced pause at 14 seconds after attempting to play to 15 seconds. This follows historical ACR-P2-001 but conflicts with accepted I13 FR-005.
- Face and voice Learn can immediately process the current video and enqueue other eligible videos. No I13 manifest/accepted-gate enforcement was found in these APIs or workers.
- Native voice recognition reads turn embeddings only through `i9_voice_vec_for_turn`; only the fake provider implements it. Real exemplar extraction exists, but that does not prove real-video voice recognition.
- Legacy appearance persistence is an INSERT despite the name `upsert_appearance_moment`. Native rescans instead delete/rebuild records, without provider predicates in that cleanup. Neither is sufficient proof of the required versioned, concurrent-safe idempotency.
- Transcript reruns delete machine words/turns and replace moments. Existing original-text fields are not a versioned correction-overlay lifecycle.

Unresolved findings:

- Founder reports the approximately 155,000 work items came from full reconciliation of known People against the video repository and were subsequently processed. The baseline fan-out mechanism is reproduced in an isolated 3-People ? 4-videos planner check; the historical 155K count and resulting evidence are **not independently reconciled**. The documented local PostgreSQL endpoint is reachable but has no recognition/speech tables. Do not interpret that as zero events in the actual runtime.
- An immutable, checkpoint-only view of local HVRT SQLite contains 19 videos, 3,579 face rows, 3,557 ranges of at most two seconds, and 268 excess exact-key rows. Its existing WAL was deliberately excluded. These figures do not describe the live database or establish the cause of the reported 155K condition.
- No versioned 22-video manifest was found in the accepted tree. The proposal is intentionally non-runnable and has no invented source IDs or truth labels.
- Rendered live workflow, recognition accuracy, performance, physical-fragment lineage, and recovery remain unproven.

## Packet

- [Requirements matrix](completeness-matrix.md): all 26 FRs, architectural and non-functional requirements, and all acceptance gates.
- [Pipeline inventory](pipeline-inventory.md), plus [schema/API declarations](schema-api-inventory.md).
- [Causal analysis and runtime evidence](causal-analysis.md).
- [Bounded manifest proposal](bounded-corpus-proposal.json): review only; **not a runnable manifest**.
- [Implementation and proof plan](implementation-plan.md): future work, requiring separate authorization.
- [Reproducible isolated checks](verify_assessment.py) and [results](verification.json).

## Authority and preservation

The user accepted the exact baseline and authorized assessment, commit, and push. Its two controlling DOCX files retain draft wording; this packet records session authorization without editing those source documents. The PRD is `docs/product/MBPRD-P2-I13_Video_Face_Speech_Voice_Learning_v0.2.docx`; the definition is `docs/product/MBBS-P2_INCREMENT_13_DEFINITION_DRAFT_v0.2.docx`. Both were read in full, including acceptance gates. All five approved screen references were inspected as an in-memory contact sheet.

Target path and branch were verified absent before worktree creation; the new worktree was clean at the exact baseline. The original worktree's application, tracked and untracked files were not edited, copied, moved, staged, cleaned, or deleted. Git necessarily registered the linked worktree and new branch in shared repository metadata, as required by the approved worktree operation.

No application server was started: startup ensures schema and may start drains; opening a video can automatically queue transcription, and poster/proxy reads may create derivative caches. Existing I8B/I9 prove harnesses invoke migrations and writes and were therefore inspected but not executed. Isolated behavioral checks execute a pure grouping function, the baseline JavaScript binder with a synthetic player, and the enqueue planner with every external read/write replaced by in-memory stubs. Other checks inspect source. No queue writer or worker is invoked. Passing these checks confirms the assessment evidence, not product acceptance.

## Founder review needed

Provide the authoritative runtime database location and existing corpus manifest, or authorize finalizing a manifest with owner-confirmed membership/truth. Confirm the transcript-overlay and retirement-cascade policies and explicitly supersede historical stop-at-end playback before implementation. Numeric timing/accuracy policy remains open. Do not unlock or start archive processing on the strength of this packet.
