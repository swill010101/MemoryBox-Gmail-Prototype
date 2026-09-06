# FlightSim bounded voice-pilot production readiness

## Decision required

This is the single consolidated approval package for the bounded TitaNet-Large voice pilot. It authorizes the exact release, the fresh backup, migration 032, isolated model installation, four selected private-audio spans, and the verification and rollback actions below. It does **not** authorize Learn, a queue drain, transcript generation, full-corpus processing, model tuning, archive processing, or any further recognition work.

The guarded script is [deploy-voice-pilot.ps1](deploy-voice-pilot.ps1). Without `-Execute` it performs no write and starts no model. With `-Execute`, it requires an explicit approval reference and follows this document in order.

## Exact release and target

- Release commit: `6d56da596b55260832ec6f5b302f06437ebd510b` on `codex/p2-i13-stage-a`.
- Target: FlightSim Windows host; production database `memorybox` in Docker container `memorybox-pg`, PostgreSQL 16.14.
- New isolated release: `C:\MemoryBox-releases\p2-i13-voice-pilot-6d56da5`.
- Existing runtime checkout `C:\MemoryBox` is not modified. The current locked app and worker may remain running; this release uses a separate, one-shot CLI.
- Media root: `P:\Photos\Home Videos`.

## Proven prerequisites

The FlightSim PostgreSQL 16 clone rehearsal passed at commit `43a4a38181b13e95899b364954694e10ad931a09`:

| Check | Result |
| --- | --- |
| Live DB before rehearsal | 2,244,869,143 bytes; latest migration `031`; annotation tables present; pilot tables absent |
| Rehearsal backup | `C:\MemoryBox-backups\i13-pre032-b4d1c80b487e4d1383af6b80ed67be65\memorybox.dump` |
| Backup proof | 433,074,031 bytes; SHA-256 `31c3fb1c78cb4e2dd28876a13acfd6c0b85a62804a7d23c30c9a4e4d9e27ad4e`; container hash matched |
| Clone | `mb_i13_pre032_restore_b4d1c80b487e4d1383af6b80ed67be65` |
| Migration result on clone | `032_p2_i13_voice_pilot.sql`; 0 runs, attempts, events, and retirements |
| Existing data protection | fingerprints unchanged; rollback verified; live production still had no pilot schema |
| Duration | 29.81 seconds for clone migration rehearsal, excluding backup/restore transfer |

A new, current backup is still mandatory immediately before the live schema change. The rehearsal backup is evidence only and is not a recovery point for later live writes.

## Model and frozen scoring policy

- Model: NVIDIA NeMo TitaNet-Large v1 (`titanet-l.nemo`), 101,621,760 bytes.
- Official download endpoint: `https://api.ngc.nvidia.com/v2/models/nvidia/nemo/titanet_large/versions/v1/files/titanet-l.nemo?redirect=true`.
- Required SHA-256: `e838520693f269e7984f55bc8eb3c2d60ccf246bf4b896d4be9bcabe3e4b0fe3`.
- Isolated environment: a new Python 3.12 virtual environment inside the new release. Direct pins are in `titanet-requirements.in`.
- Model smoke test uses generated audio only. It must produce a finite, repeatable 192-element embedding before any private-audio work.
- Frozen score policy: below `0.30` = no match; `0.30` through below `0.45` = uncertain; `0.45` or greater = match. The policy was calibrated once on separate public LibriSpeech speech, then frozen. It will not be adjusted using the pilot outcomes.

The model package install and the model download have not yet been tested on FlightSim. Family-video accuracy is unknown; the tightly bounded pilot measures it and cannot establish generalized recognition accuracy.

## Exact private pilot scope

| Key | Role | Source | Range | Expected result |
| --- | --- | --- | --- | --- |
| T1 | sole training reference | `vid-da41273dbd9ac4bb` | 02:18.720ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“02:24.660 | Eugene Will reference only |
| H1 | held out | `vid-c57dbd21f993f6d1` | 05:25.220ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“05:45.560 | Eugene Will |
| O1 | held out negative | `vid-c57dbd21f993f6d1` | 02:32.240ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“02:38.340 | Tom Will off camera; must not be a Eugene match |
| U1-clear | held out | `vid-c57dbd21f993f6d1` | 02:09.640ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“02:18.720 | Eugene Will |

Limits are enforced in code and in the reviewed plan: two source files, four extractions, four embeddings, three comparisons, one attempt per span, no automatic retry, 41.46 seconds of selected audio, 120 seconds per extraction, 120 seconds per embedding, and 20 minutes overall. Source and model SHA-256 values must match the reviewed plan before and after extraction. Temporary WAV files are deleted by the runner; originals and derived media are not written.

## Production write set

The deployment can write only these items:

- A detached release directory, an isolated Python virtual environment, the public model file, and backup files under `C:\MemoryBox-backups`.
- Migration ledger row `032` and the additive pilot tables, triggers, and view defined by `032_p2_i13_voice_pilot.sql`.
- One I13 admission and its audit events; one pilot run; four attempt records; reference/result events or one failure event.

It does not alter machine transcripts, owner overlays, legacy recognition/speech queues, legacy exemplars, original media, derivative files, Historian Capture, or app/worker drain settings.

## Deployment sequence and smoke tests

After approval, Tom runs one command from a configured FlightSim PowerShell session. The script first verifies the commit and a clean release directory, installs the isolated dependencies, downloads the redirected model artifact into a temporary file, requires its exact byte count and SHA-256, preserves any invalid response as a rejected file, runs generated-audio smoke, and then creates and verifies a fresh custom-format backup. It refuses any live state other than migration `031` with absent pilot tables.

It applies **only** migration 032 inside a transaction and writes the `032` ledger row. It then verifies the ledger and all four pilot tables. It creates the reviewed plan from the pinned selection, registers and starts one bounded admission, runs the CLI, records the result, and stops the admission. The final read-only report verifies there is one run, four attempts, and the expected event records. It also reports legacy queue counts and transcript/annotation counts before and after; they must be equal.

The acceptance result is a report of all three held-out scores and decisions. H1 and U1 are expected to score Eugene; O1 must never score `match` for Eugene. `uncertain` is an allowed abstention rather than a positive recognition claim. Any failure, source/model mismatch, stale annotation, quality failure, budget violation, or unexpected legacy count change stops the script. There is no automatic retry.

## Availability and rollback

No application or worker replacement is required, so no planned user-interface outage is expected. The SQL migration requests a five-second lock timeout. Reserve a 30ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“45 minute maintenance window because the one-time Python package installation/download may take time and the backup transfers roughly 433 MB; existing services can remain locked and available while that occurs. The private run itself is capped at 20 minutes.

If preparation fails before migration, no database state changed. If migration or run fails, the script stops the new admission where possible, preserves all additive pilot evidence and failure output, and leaves the existing app/worker locks intact. Do not rerun automatically, drop pilot tables, delete records, restore the database, or alter the original checkout. Normal operational rollback is to stop using this detached release and retain the existing locked release. A full database restore is an exceptional recovery action because it would remove later legitimate writes; it requires a separate founder decision.

## Command to execute after approval

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File 'C:\MemoryBox-releases\p2-i13-voice-pilot-6d56da5\docs\implementation\p2-i13-stage-a\deploy-voice-pilot.ps1' -ExpectedReleaseSha '6d56da596b55260832ec6f5b302f06437ebd510b' -Execute -ApprovalReference 'founder-approved-voice-pilot-2026-09-06'
```

Before that command can work, create the detached release exactly once:

```powershell
& {
  $ErrorActionPreference = 'Stop'
  $root = 'C:\MemoryBox'
  $release = 'C:\MemoryBox-releases\p2-i13-voice-pilot-6d56da5'
  $sha = '6d56da596b55260832ec6f5b302f06437ebd510b'
  if (Test-Path -LiteralPath $release) { throw 'Release path already exists; preserve it and stop.' }
  git -C $root fetch origin codex/p2-i13-stage-a
  if ($LASTEXITCODE -ne 0) { throw 'Fetch failed.' }
  git -C $root worktree add --detach $release $sha
  if ($LASTEXITCODE -ne 0) { throw 'Worktree creation failed.' }
  if ((git -C $release rev-parse HEAD) -ne $sha) { throw 'Release SHA mismatch.' }
  if (git -C $release status --porcelain) { throw 'Release is not clean.' }
}
```

The detached-release creation changes Git metadata only; it does not clean, move, stage, or modify the existing `C:\MemoryBox` working files.

## Approval request

Approve this entire FlightSim production deployment: the exact commit and detached release, fresh verified backup, one additive migration 032, isolated TitaNet-Large install/download and generated-audio smoke, the four-span private bounded run, and the stated verification/rollback procedure.

## Download correction recorded

The earlier release d587199 stopped before database backup, schema migration, admission creation, or private-media processing because the bare NGC URL saved a 73-byte request receipt. Release a52ecf uses NVIDIA's file-artifact redirect form and rejects a non-101,621,760-byte payload before model loading. The prior response is preserved in the earlier isolated release; do not reuse that release.

The intermediate `356e10d` route returned public model metadata (783 bytes), also before any database or private-media operation. It is preserved for diagnosis and must not be reused.

The final downloader requests the official file endpoint, requires its HTTPS redirect target to be `xfiles.ngc.nvidia.com`, and downloads that target directly. The time-limited redirect URL is never logged or persisted. The intermediate `fa52ecf` release stopped before database or private-media processing and must not be reused.
