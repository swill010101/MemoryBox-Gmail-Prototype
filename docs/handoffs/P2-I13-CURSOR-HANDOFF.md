# P2-I13 Cursor handoff

## Repository checkpoint

- Repository: `E:\MemoryBox-dev\p2-i13-stage-a`
- Branch: `codex/p2-i13-stage-a`
- Handoff HEAD: `ef12cb3` (after Eugene reprocessing lifecycle pilot recorded)
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
- Bounded voice pilots completed and stopped:
  - Original Eugene (T1) — admission `1039c733…` now **stale** after T1 retirement
  - Tom off-camera — `9e0a2605…` **current**
  - N1 Unknown — `46cb1d21…` **current**
  - Eugene Patio — `f59050d5…` **current**
  - Eugene reprocessing lifecycle — `66fb93af…` **current** (2026-09-08)
- T1 lifecycle retirement completed; stale cascade verified.
- Playable copy published for `vid-34df63e61b949890` (`grandpa sessions 2 002.MP4`).
- Two new Eugene assignments on that source enabled the lifecycle pilot.

## Owner voice annotations (ten reviewed)

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
| R1-gs2-fresh | Eugene | Lifecycle training (`3eb88a19…`) |
| H1-gs2-held-out | Eugene | Lifecycle held-out (`5d87a6ac…`) |

Q1 remains excluded (listening only, no saved annotation). `vid-c57dbd21f993f6d1` is excluded from Eugene voice evidence.

## Gate position and locks

Still **between Gate 2 and Gate 3**. Bounded voice evidence is substantial, but Gate 3 broadened processing and Gate 4 archive unlock/start are **not** authorized. Completed pilots do not open Learn or drains.

Keep `MEMORYBOX_RECOGNITION_DRAIN=0`, `MEMORYBOX_SPEECH_DRAIN=0`, and no `MEMORYBOX_I13_ADMISSION_ID` outside a separately approved bounded operation.

## Exact next action

1. **Optional read-only verify** on FlightSim:

```powershell
$python = 'C:\MemoryBox-releases\p2-i13-voice-pilot-6d56da5\.titanet-venv\Scripts\python.exe'
cd C:\MemoryBox
git pull --ff-only origin codex/p2-i13-stage-a
& $python -B docs\implementation\p2-i13-stage-a\inspect-voice-pilot-status.py
```

2. **Next voice gap** requiring owner input before any run: overlap/poor-audio per [OVERLAP-POOR-AUDIO-VOICE-GAP-PLAN.md](docs/implementation/p2-i13-stage-a/OVERLAP-POOR-AUDIO-VOICE-GAP-PLAN.md) (Q1 sub-spans or new clear intervals; not on excluded 1532 Eugene evidence).

3. **Separate track:** face/voice corroboration and Gate 3/Gate 4 authorization remain distinct founder decisions.

## Actions that must not be repeated

- Migrations 030–032, T1 retirement, completed pilot reruns, Patio failure admission retry, playable-copy staging for `vid-34df63e61b949890` (already published), Eugene reprocessing lifecycle run (`66fb93af…`).
- Bare `python` on FlightSim for I13 pilot helpers; use `.titanet-venv` under `p2-i13-voice-pilot-6d56da5`.
- Do not create or assume an `E:` drive on FlightSim.

## Known paths

- Development worktree: `E:\MemoryBox-dev\p2-i13-stage-a`
- FlightSim checkout: `C:\MemoryBox`
- Verified TitaNet tool release: `C:\MemoryBox-releases\p2-i13-voice-pilot-6d56da5` (`.titanet-venv\Scripts\python.exe`)
- Reprocessing release used: `C:\MemoryBox-releases\p2-i13-eugene-reprocessing-7629c18`
- Grandpa playback release used: `C:\MemoryBox-releases\p2-i13-grandpa-sessions-2-002-playback-032a113`

## Key evidence files

- [I13-VOICE-PILOT-STATUS.md](docs/implementation/p2-i13-stage-a/I13-VOICE-PILOT-STATUS.md)
- [eugene-reprocessing-voice-pilot-report.json](docs/implementation/p2-i13-stage-a/eugene-reprocessing-voice-pilot-report.json)
- [POST-PILOT-VOICE-GAP-PLAN.md](docs/implementation/p2-i13-stage-a/POST-PILOT-VOICE-GAP-PLAN.md)
