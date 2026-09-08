# P2-I13 Stage A authorization

Assessment bc2b967274d51ffce356a12895df2cd8f77d73b0 accepted by Tom.

Confirmed: I13 source seek and natural continuous playback supersede ACR-P2-001 stop-at-end. Machine transcripts remain immutable; owner corrections are additive auditable overlays for display/search/learning. Retirement stops future exemplar use, preserves history, marks dependent suggestions stale, and reprocesses only affected bounded scope.

Stage A only: identify authoritative runtime and consistent read-only inventory; submit exact versioned 22-video manifest with owner truth; centralized scope admission, preview/cardinality limits, off-manifest rejection and archive lock across API/CLI/Learn/queue/retry/drain/worker; separate unlock/start; remove forced playback end while retaining seek/context; automated tests; detailed step-by-step deployment plan. Migrations may be authored, never applied to runtime.

Forbidden in this authorization: recognition, transcription, cleanup, remediation, corpus/archive processing, legacy quarantine/deletion, derivative deletion, and I12 Historian Capture changes. Commit/push artifacts and stop for founder review before migration or processing. Runtime/corpus truth cannot be invented.

## Sequencing correction authorized 2026-09-05

Tom confirmed membership of the 22 proposed sources, then clarified that owner annotations must be made inside MB by selecting transcript text/face evidence and assigning a Person; MB retains the evidence timestamps. Manual filename/time/name worksheets are not a prerequisite. Tom authorized correcting the gate and deployment plan.

Separate bounded evidence generation from owner-confirmed acceptance/learning. Membership approval is not processing approval. No migration, runtime processing, deployment, or later annotation implementation is authorized by this correction. Existing immutable transcript/overlay and retirement decisions remain in force.

## Corrected Stage A approved - 2026-09-05

Tom approved correction commit `1ecad04e8bf8f798181bbce4447b4941d1df8947` and directed proceeding to the next step with voice recognition explicitly included in acceptance. This records approval of the correction, not successful full I13 voice acceptance. Next is preparing the corrected FlightSim checkout and verifying its offline tests and read-only preview. Tom remains the deploy operator. Separate migration/processing gates remain; no runtime action was performed by this documentation update.

## Fragment correction implementation authorized - 2026-09-05

After source-specific Gallery correlation at 014684e6d1eb48248735e5e0dff6efe5984ebda8, the assistant stated: "Next: implement the reviewed grouping and Gallery presentation correction before considering another Learn run." Tom replied "proceed." This authorizes the bounded application-code correction and offline tests in the isolated worktree, superseding the original assessment-only code restriction for this change.

Scope: recorded-cadence grouping for future admitted scans; non-destructive Gallery presentation for the traced source/run; retain evidence-backed navigation, original records, uncertainty and query context. Commit/push code, tests and deployment instructions for Tom's review. No recognition or Learn execution, runtime-data remediation, deletion, migration application, archive processing or I12 changes. The Gallery projection must preserve only the current query's evidence, without expanding a filtered result to all historical source moments.

## Second-source extension approved

Following lookup result 46089221bbb6e48c9c0a95412a8fbb94f492d132 and the explicit recommendation to extend only the verified 1530 source/run, Tom replied "approved." Authorize that bounded code/test extension and commit/push for deployment review. No processing, migration, conversion or data deletion.

## Video modal fit correction authorized

Tom reports both source videos work, but the enlarged player clips the transcript. He explicitly requests removing the evidence-description line, moving the transcript up and fitting everything inside the modal. Authorize the scoped UI correction, responsive browser verification and commit/push. Preserve playback, jump navigation, source grouping, evidence and runtime locks; no processing or runtime data changes.


## Modal acceptance and next-step preparation

Tom accepted correction 33eff43d34ecf1d4314509519bd4549a66f1befe and requested the next step. Recorded owner acceptance and prepared ANNOTATION-IMPLEMENTATION-PLAN.md after inspecting existing persistence. No approval for a new recognition/transcription run, deletion or archive start is inferred.


## Annotation-only slice approved

Tom approved ANNOTATION-IMPLEMENTATION-PLAN.md at 25290136b60653c2423c37b21c5e4b38203b9b11. Authorize implementation steps 1-6, offline/disposable database tests, code/test/documentation commit and push, and an unapplied migration. No runtime migration, recognition, transcription, deletion, deployment or archive processing. Preserve I12 and the original C:\MemoryBox working tree.


## Explicit annotation publication approval

After automatic approval review rejected publication, the assistant asked: "May I commit these changes and push them to origin/codex/p2-i13-stage-a?" Tom replied "approved." This explicitly authorizes committing and pushing the reviewed annotation implementation, tests, synthetic proof and unapplied migration. Runtime migration and deployment remain separate.


## Explicit annotation performance publication approval

Tom replied "approved" to the explicit request to commit and push the tested annotation query performance correction to origin/codex/p2-i13-stage-a. This covers the revised unapplied 031 view, tests, synthetic performance proof, rollback-only clone rehearsal helper and review documents. It does not authorize runtime migration or deployment.


## Gate 3 Outcome A authorized — 2026-09-08

Tom chose **Outcome A** (full bounded evidence-generation run) in [GATE-3-DECISION-PRD.md](GATE-3-DECISION-PRD.md).

| Field | Value |
|---|---|
| Outcome | A — register, start, enqueue 22 transcribe units, process, stop |
| Review reference | `Tom-approved-gate-3-evidence-generation-outcome-a-2026-09-08` |
| Start reference | `Tom-approved-gate-3-bounded-start-2026-09-08` |
| Plan | `bounded-manifest-proposal.json` SHA `330c2f90fa0de3b319097d17f31ca5dfabe6bd57b469a1a033a79e3851259b35` |

This authorizes **transcription-only** admission on the 22-source manifest. It does **not** authorize Learn, recognition drain, face/voice matching, or Gate 4. Existing stored words are expected to produce noop completions.

Tom also reported new owner evidence for the **parallel overlap/poor-audio voice track**: Eugene Will assignments plus an off-camera Tom Will reference. That work is **not** part of Gate 3; start overlap pilot planning with Eugene Will after Gate 3 execution. Run [inspect-overlap-voice-annotations.py](inspect-overlap-voice-annotations.py) on FlightSim to capture annotation IDs before proposing the next voice pilot.

Execution: [DEPLOYMENT-READINESS-GATE-3-EVIDENCE-GENERATION.md](DEPLOYMENT-READINESS-GATE-3-EVIDENCE-GENERATION.md) and [deploy-gate-3-evidence-generation.ps1](deploy-gate-3-evidence-generation.ps1).


## Gate 3 Outcome A completed — 2026-09-08

FlightSim execution completed on release `1b60e798f69c4d17ab71f9bffc35e6912fdbde70`. Admission `458d1a76-4ecb-4722-bd76-20125b14c1d3` registered, started, enqueued 22 transcribe units, processed to completion, and stopped. All 22 queue items completed (expected noop for existing words). Legacy word/annotation counts unchanged; automatic retry false.

| Field | Value |
|---|---|
| Backup | `C:\MemoryBox-backups\i13-final-pre-gate-3-evidence-2bc4a542025249d2ab62886aa84cf4a5\memorybox.dump` |
| Backup SHA-256 | `284d06b88d6e4fe90f19ef9397adf8f589e51fc2935d66f0f5335f6e3e84f909` |

Recorded in [gate-3-evidence-generation-report.json](gate-3-evidence-generation-report.json). Gate 3 transcription evidence-generation is **complete**. Gate 4 archive unlock/start remains a separate founder decision. Learn and recognition drains remain locked unless separately authorized.


## Overlap / poor-audio pilot intervals confirmed — 2026-09-08

Tom confirmed after in-browser review on `20111105_1532.MP4`:

| Key | Confirmation |
|---|---|
| E2-1532-overlap-held-out (`bbceb696…`, 09:02–09:12) | Eugene speaking; TV on in background; mixed attribution in STT |
| O2-tom-offcamera-negative (`2b013ef8…`, 15:48–15:55) | Tom Will off-camera |

Reference: `Tom-confirmed-overlap-pilot-intervals-2026-09-08`. Interval-specific waiver for `bbceb696` on excluded 1532 is **approved** for this bounded pilot only.

Execution package: [DEPLOYMENT-READINESS-OVERLAP-POOR-AUDIO-VOICE-PILOT.md](DEPLOYMENT-READINESS-OVERLAP-POOR-AUDIO-VOICE-PILOT.md). Run approval: `Tom-approved-overlap-poor-audio-voice-pilot-run-2026-09-08` (Tom chat 2026-09-08).


## Overlap / poor-audio voice pilot completed — 2026-09-08

FlightSim execution completed on release `de9cc726f713da9fc1405c13f1aa68fedc8c8b44`. Admission `339b3a14-5069-4554-846f-dc84d6745c00` registered, ran four spans (T-gs2-reuse training plus three held-outs), and stopped. All held-outs matched expected decisions: E2 Eugene overlap match `0.584`, O2 off-camera Tom no-match `0.093`, N1 TV announcer no-match `-0.020`. Prior Tom, N1, Patio, and reprocessing pilot results remained **current**; legacy counts unchanged; automatic retry false.

| Field | Value |
|---|---|
| Backup | `C:\MemoryBox-backups\i13-final-pre-overlap-poor-audio-2498b6a8ce1241ecbc5dad9993ce1733\memorybox.dump` |
| Backup SHA-256 | `c5fd749b0a5987d16211c70f50ff6f94cf9380a11fc665538d1a1fedcafc9f3f` |
| Plan SHA-256 | `42a3ffcc303fe9bfe23c7bdf6d133e5b634ff902d7de0d3b4f4d6f4983ba7d4c` |

Recorded in [overlap-poor-audio-voice-pilot-report.json](overlap-poor-audio-voice-pilot-report.json). E2 is narrow overlap/poor-audio evidence for interval `bbceb696` only — not approval of Eugene matching across all of 1532. Gate 4, Learn, recognition drains, face/voice corroboration, and full I13 acceptance remain separate founder decisions. **Do not retry** admission `339b3a14-5069-4554-846f-dc84d6745c00`.


## Gate 4 Outcome A — defer — 2026-09-08

Tom chose **Outcome A** in [GATE-4-DECISION-PRD.md](GATE-4-DECISION-PRD.md): defer archive register/unlock/start until bounded acceptance prerequisites are clearer.

| Field | Value |
|---|---|
| Decision | A — defer Gate 4 execution |
| Review reference | `Tom-deferred-gate-4-archive-until-acceptance-prerequisites-2026-09-08` |

**Not authorized:** archive plan register, `unlock`, `start`, drains, or P2-I14 product build.

**Resume Gate 4 when:** face/voice corroboration scope is decided; owner truth is exported/reviewed for an `acceptance_learning` or archive plan; or Tom issues an explicit narrow acceptance waiver with a defined `--acceptance-ref`. Next step is then Outcome **B** (plan-only preview) at minimum, with fresh sign-off before any register/unlock/start.


## Narrow bounded voice acceptance waiver — 2026-09-08

Tom chose option **2**: narrow acceptance waiver plus Gate 4 Outcome **B** (archive plan preview only).

| Field | Value |
|---|---|
| Waiver reference (`--acceptance-ref` when unlock is authorized) | `Tom-narrow-bounded-voice-acceptance-waiver-2026-09-08` |
| Owner-truth export reference | `Tom-owner-truth-export-flightsim-2026-09-08` |
| Archive plan | [archive-manifest-proposal.json](archive-manifest-proposal.json) — 5 sources, 10 face work units |
| Plan SHA-256 | `f36cdb19c51abe13234b80c08b746901d5d195c5e8be621e10e5f2a85f46316c` |

See [NARROW-ACCEPTANCE-WAIVER.md](NARROW-ACCEPTANCE-WAIVER.md) and [DEPLOYMENT-READINESS-GATE-4-ARCHIVE-PLAN-PREVIEW.md](DEPLOYMENT-READINESS-GATE-4-ARCHIVE-PLAN-PREVIEW.md).

**Not authorized:** `register`, `unlock`, `start`, drains, full 22-source acceptance, full I13 sign-off, or P2-I14.


## Gate 4 Outcome B plan preview completed — 2026-09-08

FlightSim preview on release at or after `ebd04f1` matched the reviewed plan:

| Field | Value |
|---|---|
| `source_count` | 5 |
| `person_count` | 2 |
| `work_items` | 10 |
| `max_attempts` | 20 |
| `plan_sha256` | `f36cdb19c51abe13234b80c08b746901d5d195c5e8be621e10e5f2a85f46316c` |

Tom reported all checks pass. Archive register/unlock/start remain separate founder decisions.
