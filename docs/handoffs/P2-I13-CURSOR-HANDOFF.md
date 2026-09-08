# P2-I13 Cursor handoff

## Repository checkpoint

- Repository: `E:\MemoryBox-dev\p2-i13-stage-a`
- Branch: `codex/p2-i13-stage-a`
- Handoff HEAD: `de9cc72`+ (after overlap voice pilot recorded)
- Remote: `origin/codex/p2-i13-stage-a`
- Working tree: clean unless noted below.

This handoff contains source and documentation state only. Do not add database dumps, backup files or hashes, credentials, media, proxies, dependency environments, caches, generated copies, or storage-audit output to Git.

## Governing product decisions

- Product authority: `docs/product/MBPRD-P2-I13_Video_Face_Speech_Voice_Learning_v0.2.docx`, `docs/product/MBBS-P2_INCREMENT_13_DEFINITION_DRAFT_v0.2.docx`, and `docs/implementation/p2-i13-stage-a/FOUNDER-AUTHORIZATION.md`.
- Tom accepted assessment `bc2b967274d51ffce356a12895df2cd8f77d73b0` and later approved the Stage A correction `1ecad04e8bf8f798181bbce4447b4941d1df8947`.
- Playback seeks to evidence and continues naturally; it does not force-stop at the relevance interval end.
- Machine transcripts are immutable. Owner corrections are additive, auditable overlays.
- Retiring a reference preserves history, blocks its future use, stales dependent pilot results, and never starts reprocessing. Any reprocessing must be affected-only, bounded, separately reviewed, and separately approved.
- Learn, recognition/speech drains, archive processing, and legacy processing paths remain locked unless a distinct reviewed admission authorizes an exact run.

## Completed work and accepted deployments

- Migrations 030, 031, and 032 applied on FlightSim. Do not rerun them.
- Annotation-review workflow accepted at `7bc47b5911caeb8ca256dcc260f17943d2fb777a`.
- Playback/result-modal release accepted at `d3785b93311920a3409961054368796ed7fa66b3`.
- **Gate 3 evidence-generation completed** 2026-09-08 — admission `458d1a76-4ecb-4722-bd76-20125b14c1d3` (stopped); 22/22 transcribe noops; see [gate-3-evidence-generation-report.json](docs/implementation/p2-i13-stage-a/gate-3-evidence-generation-report.json).
- Bounded voice pilots completed and stopped:
  - Original Eugene (T1) — admission `1039c733…` now **stale** after T1 retirement
  - Tom off-camera — `9e0a2605…` **current**
  - N1 Unknown — `46cb1d21…` **current**
  - Eugene Patio — `f59050d5…` **current**
  - Eugene reprocessing lifecycle — `66fb93af…` **current**
  - Overlap / poor-audio Eugene — `339b3a14…` **current**
- T1 lifecycle retirement completed; stale cascade verified.
- Playable copy published for `vid-34df63e61b949890` (`grandpa sessions 2 002.MP4`).

## Owner voice annotations (ten reviewed + overlap track complete)

| Key | Person | Status |
|---|---|---|
| T1 | Eugene | Retired training reference |
| H1 | Eugene | Prior pilot held-out; Tom control |
| O1 | Tom off-camera | Tom pilot held-out match |
| U1-clear | Eugene | Prior pilot held-out; Tom control |
| T2 | Tom | Training reference (Tom/N1/Patio/reprocessing controls) |
| N1 | Unknown TV | Held-out no-match only |
| T3-patio | Eugene | Patio training |
| E3-patio-held-out | Eugene | Patio held-out |
| R1-gs2-fresh | Eugene | Lifecycle training |
| H1-gs2-held-out | Eugene | Lifecycle held-out |
| E2-1532-overlap | Eugene | Overlap/poor-audio held-out match (`339b3a14…`) |
| O2-tom-offcamera | Tom off-camera | Overlap pilot Eugene negative control |

Q1 on 1532 remains listening-only. `vid-c57dbd21f993f6d1` remains excluded from generalized Eugene voice evidence; E2 used interval-specific waiver for `bbceb696` only.

## Gate position and locks

**Gate 4 deferred (Outcome A, 2026-09-08).** Gate 3 and overlap voice pilot are **complete**. Archive unlock/start is **not** authorized. See [GATE-4-DECISION-PRD.md](docs/implementation/p2-i13-stage-a/GATE-4-DECISION-PRD.md). **P2-I14** remains blocked until full I13 acceptance. Learn and recognition drains stay locked.

Keep `MEMORYBOX_RECOGNITION_DRAIN=0`, `MEMORYBOX_SPEECH_DRAIN=0`, and no `MEMORYBOX_I13_ADMISSION_ID` outside a separately approved bounded operation.

## Exact next action

1. **Gate 4 Outcome B** — Run plan preview on FlightSim: [DEPLOYMENT-READINESS-GATE-4-ARCHIVE-PLAN-PREVIEW.md](docs/implementation/p2-i13-stage-a/DEPLOYMENT-READINESS-GATE-4-ARCHIVE-PLAN-PREVIEW.md). Narrow acceptance waiver recorded: [NARROW-ACCEPTANCE-WAIVER.md](docs/implementation/p2-i13-stage-a/NARROW-ACCEPTANCE-WAIVER.md).

2. **Separate track:** face/voice corroboration; full I13 acceptance; P2-I14 only after I13 closeout.

## Actions that must not be repeated

- Migrations 030–032, T1 retirement, completed voice pilot reruns, Patio failure admission retry, grandpa 002 playable-copy staging, Eugene reprocessing lifecycle (`66fb93af…`), **Gate 3 evidence-generation run (`458d1a76…`)**, **overlap/poor-audio voice pilot (`339b3a14…`)**.
- Bare `python` on FlightSim for I13 helpers; use `.titanet-venv` under `p2-i13-voice-pilot-6d56da5`.

## Known paths

- Development worktree: `E:\MemoryBox-dev\p2-i13-stage-a`
- FlightSim checkout: `C:\MemoryBox`
- Verified TitaNet tool release: `C:\MemoryBox-releases\p2-i13-voice-pilot-6d56da5`
- Gate 3 backup: `C:\MemoryBox-backups\i13-final-pre-gate-3-evidence-2bc4a542025249d2ab62886aa84cf4a5\memorybox.dump`
- Overlap pilot backup: `C:\MemoryBox-backups\i13-final-pre-overlap-poor-audio-2498b6a8ce1241ecbc5dad9993ce1733\memorybox.dump`

## Key evidence files

- [gate-3-evidence-generation-report.json](docs/implementation/p2-i13-stage-a/gate-3-evidence-generation-report.json)
- [overlap-poor-audio-voice-pilot-report.json](docs/implementation/p2-i13-stage-a/overlap-poor-audio-voice-pilot-report.json)
- [GATE-4-DECISION-PRD.md](docs/implementation/p2-i13-stage-a/GATE-4-DECISION-PRD.md)
- [I13-VOICE-PILOT-STATUS.md](docs/implementation/p2-i13-stage-a/I13-VOICE-PILOT-STATUS.md)
- [OVERLAP-POOR-AUDIO-VOICE-GAP-PLAN.md](docs/implementation/p2-i13-stage-a/OVERLAP-POOR-AUDIO-VOICE-GAP-PLAN.md)
