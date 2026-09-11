# H: storage migration plan

## Hold status

On 2026-09-07, Tom deferred this migration to continue I13 work. No preflight, copy, cutover, or cleanup is authorized while this hold remains in effect.

## Status and authorization boundary

This is a planning document only. As of 2026-09-07, no MemoryBox path, service, virtual environment, model, worktree, backup, derivative, Docker volume, original media file, database, or Git metadata has been moved, copied, deleted, linked, renamed, or reconfigured under this plan.

Tom requested a safe plan before any storage cutover. Execution needs one later approval after a concrete preflight inventory and cutover-readiness report. The plan is deliberately independent of I13 feature acceptance: moving storage is an operations change, not a reason to unlock processing or advance a Gate.

## Confirmed capacity

Read-only volume inspection on 2026-09-07 reported:

| Volume | Free space |
|---|---:|
| C: | 98,174,296,064 bytes (about 91.4 GiB) |
| E: | 603,823,828,992 bytes (about 562.4 GiB) |
| H: | 2,000,185,262,080 bytes (about 1.82 TiB) |

H: has sufficient capacity for a staged migration. Capacity alone does not prove a safe cutover.

## Scope

| Category | Current role | Planned H: destination | Cutover treatment |
|---|---|---|---|
| Runtime repository and release source | `C:\MemoryBox` and release worktrees | `H:\MemoryBox\runtime` and `H:\MemoryBox\releases` | Create a new H:-native clone/worktree set; do not move `.git` or existing worktrees in place. |
| Development worktrees | `E:\MemoryBox-worktrees` | `H:\MemoryBox\worktrees` | Recreate from Git after source integrity checks; preserve E: until rollback close. |
| Backups | `C:\MemoryBox-backups` | `H:\MemoryBox\backups` | Copy then hash-verify; retain original copies during the rollback window. |
| Rebuildable video derivatives | current configured `MEMORYBOX_VIDEO_DERIVED_DIR` | `H:\MemoryBox\derived\video` | Configure only after service stop and preflight. Copy existing validated proxies; do not regenerate or delete any. |
| TitaNet model and its environment | pilot release/virtual environment locations | `H:\MemoryBox\voice-model` and `H:\MemoryBox\voice-venv` | Hash-copy the model; recreate the virtual environment on H: because Python virtual environments contain absolute paths. |
| Original family media | `P:\Photos\Home Videos` | unchanged | Never move under this plan. |
| PostgreSQL/Docker data | Docker-managed storage | unchanged | Not part of this cutover. Inventory separately before any database-storage work. |

## Phased cutover

### 1. Read-only preflight

Before any copy, capture an inventory of exact source paths, directory sizes, free space, filesystem types, reparse points, active MemoryBox process paths, active service configuration paths, Git remotes/heads, backup hashes, derivative/proxy status, model hash, and current app/worker health. Do not print credentials, command-line secrets, database URLs, or tokens.

The preflight must also confirm that H: is writable, its destinations are new/empty, and the target filesystem supports the required operations. It must flag a path that is in use, missing, redirected, or outside the approved roots. It must not create destination directories.

### 2. Build H: copies without a service switch

Create a new clone on H: from the reviewed remote/commit and create new detached H: release worktrees. Copy backups, approved model bytes, and static/rebuildable artifacts with source and destination SHA-256 verification. Use copy-only operations, never a move or overwrite. Preserve C:/E: originals and record each copied path and hash.

Do not copy a Python virtual environment as a portable runtime. Create a new H:-resident environment using the reviewed Python and locked package requirements, then revalidate the model hash and generated-audio smoke proof. Do not run recognition or private-media processing.

### 3. Cutover readiness review

Prepare one report stating the exact new release SHA, target paths, copy hashes, environment/model verification, service configuration changes, expected downtime, smoke tests, old paths retained for rollback, and a rollback command path. Obtain one approval before stopping services or changing any live configuration.

### 4. Approved maintenance cutover

Stop the MemoryBox app and video worker through their established operator method. Keep both drains off and the admission ID unset. Perform a final copy-only synchronization for runtime files/configuration that are safe to copy, verify hashes, update only the reviewed service path/configuration values, and start the H:-resident app and worker.

Run locked-mode smoke tests: app and worker bind only to the expected ports; Explore/Ask/Review load; the existing voice-results endpoint is read-only; the validated playable source still plays; N1 remains unavailable unless separately authorized; queue/admission state and drains remain unchanged. Do not start Learn, recognition, transcription, migration, archive work, or proxy generation.

### 5. Rollback window and later reclamation

Retain the old C:/E: runtime/release, backup, model, and derivative copies unchanged for a proposed **30-day rollback window** after successful H: cutover. The window is a proposal, not an automatic deletion schedule.

At the end of the window, run a read-only reconciliation of old/new hashes, service paths, backup retention needs, active release references, and rollback evidence. Present a file-by-file reclamation list for Tom's approval. Only then can old C:/E: copies be removed. Full I13 acceptance is neither required nor sufficient for automatic deletion.

## Explicit exclusions

- No move, deletion, cleanup, or overwrite.
- No alteration of `P:` original media.
- No relocation of PostgreSQL/Docker volumes.
- No Git `.git` directory or existing worktree metadata move.
- No service restart, port change, migration, admission, drain change, recognition, transcription, Learn action, proxy generation, or archive action.
- No release of C:/E: space until the separately approved reclamation list.

## Next decision

Approve **only the read-only H: migration preflight** when ready. It will produce the exact source/target inventory and cutover readiness report, then stop for a separate approval before any copy or service change.
