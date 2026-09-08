# P2-I13 Cursor handoff

## Repository checkpoint

- Repository: `E:\MemoryBox-dev\p2-i13-stage-a`
- Branch: `codex/p2-i13-stage-a`
- Pre-handoff HEAD: `e3c98134cbf8f43635c313ba343e689a9a5978cf`
- Pre-handoff working tree: clean.
- Remote: `origin/codex/p2-i13-stage-a`.

This handoff contains source and documentation state only. Do not add database dumps, backup files or hashes, credentials, media, proxies, dependency environments, caches, generated copies, or storage-audit output to Git.

## Governing product decisions

- Product authority: `docs/product/MBPRD-P2-I13_Video_Face_Speech_Voice_Learning_v0.2.docx`, `docs/product/MBBS-P2_INCREMENT_13_DEFINITION_DRAFT_v0.2.docx`, and `docs/implementation/p2-i13-stage-a/FOUNDER-AUTHORIZATION.md`.
- Tom accepted assessment `bc2b967274d51ffce356a12895df2cd8f77d73b0` and later approved the Stage A correction `1ecad04e8bf8f798181bbce4447b4941d1df8947`.
- Playback seeks to evidence and continues naturally; it does not force-stop at the relevance interval end.
- Machine transcripts are immutable. Owner corrections are additive, auditable overlays.
- Retiring a reference preserves history, blocks its future use, stales dependent pilot results, and never starts reprocessing. Any reprocessing must be affected-only, bounded, separately reviewed, and separately approved.
- Learn, recognition/speech drains, archive processing, and legacy processing paths remain locked unless a distinct reviewed admission authorizes an exact run.

## Completed work and accepted deployments

- Migrations 030, 031, and 032 are already applied on FlightSim. Do not rerun them.
- The annotation-review workflow was accepted by Tom on FlightSim at `7bc47b5911caeb8ca256dcc260f17943d2fb777a`.
- The accepted playback/result-modal release is `d3785b93311920a3409961054368796ed7fa66b3`.
- Bounded real-audio pilots completed and stopped: the original Eugene pilot, Tom pilot, N1 Unknown no-match pilot, and Eugene Patio pilot. Each is provenance-backed pilot evidence, not archive acceptance or a generalized accuracy claim.
- The Eugene Patio pilot was corrected for PostgreSQL floating-point timestamp representation before its approved run. Its held-out Eugene case matched, while the Tom and Unknown controls were no-match. No automatic retry occurred.
- T1 lifecycle retirement was already completed before the current handoff. Read-only FlightSim verification confirmed only that older Eugene admission is stale; the Tom, N1, and Eugene Patio pilot admissions remain stopped and current.

## Current FlightSim state

- Known pilot states from the supplied read-only query: the retired T1 pilot is `stopped` and `stale`; the Tom, N1, and Eugene Patio pilots are `stopped` and current.
- The deployed annotation UI and results viewer have owner-reported acceptance. Independent process inspection, aggregate health evidence, and current queue counts were not supplied with this handoff.
- Keep `MEMORYBOX_RECOGNITION_DRAIN=0`, `MEMORYBOX_SPEECH_DRAIN=0`, and no `MEMORYBOX_I13_ADMISSION_ID` outside a separately approved bounded operation.
- No active admission, queue, or service state should be inferred beyond the supplied read-only evidence. Recheck it before any future proposal or run.

## Eight owner voice annotations and roles

The exact IDs, source hashes, transcript versions, and ranges remain in the versioned pilot proposals under `docs/implementation/p2-i13-stage-a/`; do not duplicate raw database exports in this handoff.

| Key | Person / truth | Intended role and current status |
|---|---|---|
| T1 | Eugene | Original Eugene training reference; now retired and must never be reused. |
| H1 | Eugene | Held-out Eugene evidence; later reused only as a Tom no-match control. |
| O1 | Tom, off-camera | Held-out positive Tom evidence; confirmed by the Tom pilot. |
| U1-clear | Eugene | Clear held-out Eugene evidence; later reused only as a Tom no-match control. |
| T2 | Tom | Tom training reference; current and shared by the Tom/N1 pilot evidence. |
| N1 | Unknown TV announcer | Held-out no-match evidence only; never training and never a basis to create or infer a Person. |
| T3-patio | Eugene | Eugene Patio training reference for the completed Patio pilot. |
| E3-patio-held-out | Eugene | Distinct held-out Eugene Patio positive evidence for the completed Patio pilot. |

Q1 remains excluded: it has background/TV overlap and no exact saved truthful annotation.

## Gate position and locks

Treat the project as **between Gate 2 and Gate 3** for future work: locked deployment and bounded pilot evidence exist, but no broadened Gate 3 processing or Gate 4 archive unlock/start is authorized. The completed pilots do not open Learn or any drain.

Do not run `startmb.ps1`, `startmb.cmd`, legacy prove commands, Learn, an archive pass, a bulk retry, or an unrestricted worker as a shortcut. Do not restart a stopped admission. Do not retry the failed Patio admission; its successful replacement is already recorded.

## Remaining evidence and defects

- Full I13 acceptance remains open: poor or mumbled audio, overlap/multiple speakers, broader unknown/no-match behavior, face/voice corroboration, generalized accuracy, and archive acceptance are not established.
- The original T1 retirement backup and legacy-count proof was not supplied in this conversation. Do not invent it.
- A lifecycle stale cascade is confirmed, but no affected-only reprocessing has been proposed or run.
- The initial Patio run failed before private audio processing because PostgreSQL floating-point display noise triggered exact timestamp comparison. The precision fix is implemented and the successful replacement pilot is recorded.
- The earlier retired-T1 execution package is obsolete; do not invoke it with `-Execute`.

## Exact next action

Run the existing read-only `docs/implementation/p2-i13-stage-a/inspect-eugene-reprocessing-candidates.py` from an exact FlightSim release using the verified TitaNet Python environment and the configured database environment. It must identify an active, unretired Eugene annotation that has never appeared in a voice-pilot plan. Then prepare, but do not run, one affected-only reprocessing proposal with exact source/annotation IDs, bounds, expected evidence, backup and rollback steps.

If there is no eligible reference, Tom must save one new clear Eugene assignment in MemoryBox. Do not repurpose T1, a prior held-out span, N1, Q1, or TV-overlapped material as a new reference.

## Actions that must not be repeated

- Do not apply migrations 030, 031, or 032 again.
- Do not duplicate the already completed T1 retirement.
- Do not recreate or rerun the stopped Eugene Patio failure admission.
- Do not use bare `python` on FlightSim for I13 pilot helpers; use the verified TitaNet tool release environment.
- Do not use literal placeholder paths in PowerShell commands.
- Do not create or assume an `E:` drive on FlightSim. FlightSim has C: only; the development desktop has C: and E:.
- Do not move storage, Git metadata, databases, Docker data, models, media, or backups. The H: storage migration remains planning-only.
- Do not commit runtime data or generated artifacts listed at the start of this handoff.

## Known paths and worktrees

- Development worktree: `E:\MemoryBox-dev\p2-i13-stage-a`.
- Canonical FlightSim Git checkout: `C:\MemoryBox`.
- Current FlightSim diagnostic release: `C:\MemoryBox-releases\p2-i13-eugene-t1-retirement-da43db7`.
- Prior corrected Patio release: `C:\MemoryBox-releases\p2-i13-eugene-patio-precision-32c0136`.
- Verified TitaNet tool release: `C:\MemoryBox-releases\p2-i13-voice-pilot-6d56da5` (Python at `.titanet-venv\Scripts\python.exe`, not `.venv`).
- Storage constraint: FlightSim uses C: and has no E:. The development desktop’s E: is separate. Do not infer capacity problems on FlightSim C:, and do not perform any storage move under this handoff.