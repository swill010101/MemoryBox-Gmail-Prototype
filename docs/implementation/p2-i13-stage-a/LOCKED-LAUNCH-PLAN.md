# Locked launch arrangement - pending configuration review

Tom starts FlightSim through startmb.cmd. The checked-in CMD changes to its own directory and invokes startmb.ps1. That script loads three optional .env files, then inherited settings/defaults. Tom confirmed those three files absent; immich.env, historian_capture.json, Gmail credential/token files and four Capture transport modules are present under C:/MemoryBox.

## Confirmed startup hazards

- startmb.ps1 defaults recognition drain to on and derives runtime/config paths from its script directory.
- Its serve child invokes python -m memorybox serve. That command auto-runs migrations, ensures AI trace schema, abandons stale trace records and bootstraps an owner session before serving. It is not a read-only check or an appropriate migration-free launcher.
- Moving the startmb invocation to a new release loses the old script-relative configuration and Capture package unless explicitly handled. Existing workers listening on ports can also cause the script to retain old code rather than switch releases.

## Proposed deployment arrangement

Use a separate reviewed launcher, leaving C:/MemoryBox/startmb.cmd and startmb.ps1 untouched. Keep runtime working directory C:/MemoryBox so existing relative runtime paths retain meaning. Put the approved release first for the regular memorybox package and retain the original runtime root only for the external application.marvin_capture dependency; verify both module origins without running Gmail clients before start. This temporary external code dependency must remain explicit and pinned by file hashes in the release record; it is not a fully self-contained clone. Do not copy/commit credential or runtime files or vendor unreviewed Capture modules.

Resolve Immich, Capture configuration, Gmail credentials/token and mail preservation paths explicitly to existing runtime paths. Respect reviewed overrides and any relative paths inside historian_capture.json. Preserve source/derived locations. Do not silently introduce an empty new derivative tree. The configured source and derivative roots need confirmation because the three optional env files are absent and the current terminal may not reflect startmb's inherited environment.

After environment loading, force both native drains off and remove the admission ID. Verify only the reviewed 030 schema is applied through a separate approved migration step. Start through a migration-free app entry (not memorybox serve), with separate confirmed worker/app process management and explicit release-origin proof. Existing startup hooks must be reviewed for writes; locked launch is not read-only runtime access. Preserve the accepted owner session and I12 dependencies rather than rerunning startup cleanup/bootstrap as a shortcut. No launcher execution is authorized by preparing this plan.

## Next read-only check

Run preflight-launch.py --runtime-root C:/MemoryBox from the release containing this documentation. It only reads optional environment files and checks file paths. It never imports MB/Capture, reads OAuth content, opens a database, starts services or writes environment/files. Output contains path metadata and presence flags, not database URLs or credentials. Missing inherited settings are not proof the currently running app lacks them; reconcile them against startmb defaults and the actual deployment before completing the launcher.

Status: arrangement prepared; executable start path intentionally not supplied until effective source/derived/config paths are resolved. No service switch, migration or processing occurred. Existing I12 code remains unchanged.

## Recovery verification received

Tom reported a 424764650-byte full dump, SHA256 B879D850D0A84B4B6E682C9A63673A7D312A9126A311969D2CEB223920075FCE, independently restored into mb_i13_restore_947883684e4a4cab9e63daf2ab499844. Ledger 001-029, recognition queue 155854, speech queue 2011, transcript words 140441, one Capture campaign and five Capture items were present. Tom reported all four source/restore metadata comparisons true (tables, columns, constraints, indexes). This verifies the inspected database recovery artifact, not a live application workflow or a quiescent final maintenance snapshot.
