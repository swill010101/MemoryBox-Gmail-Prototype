# I13 → I14 scoped cleanup inventory (prepared, not executed)

**Status:** Inventory only. I13 is **accepted 2026-09-11**. **Do not delete, restore, or move anything** until Tom separately authorizes cleanup execution.

**Purpose:** Remove Codex/Cursor **temporary** working material before I14 without touching FlightSim product data, media, or the accepted I13 SHA.

## In scope (candidates)

| Location | Why it is temporary | Risk if deleted early |
|---|---|---|
| `C:\MemoryBox-backups\i13-interactive-learn-20260910-105354\` proof `*.txt`/`*.json` | Session proof copies | Lose I13 close evidence; **archive this folder** before delete |
| Extra `C:\MemoryBox-backups\*` dumps from I13 deploy experiments | Operator backups | Confirm dump is not the only restore point |
| Desktop untracked `docs/test-output/inventory-stdout.txt`, `phase1-3-deployment-result.json` | Local probe output | None if committed evidence already exists elsewhere |
| Cursor agent transcripts under `%USERPROFILE%\.cursor\projects\...\agent-transcripts` | Chat logs | History only; not runtime |
| Hand-patched FlightSim copies already superseded by `b2dd4a2` (if any leftover under `C:\MemoryBox-backups\` audit trees) | Pre-deploy patches | Confirm they are not the live `C:\MemoryBox` tree |

## Out of scope (never this cleanup)

- `C:\MemoryBox` git worktree at SHA `b2dd4a2c4cfd613b0d7cd32d9a4426b25be3ebcb`
- Postgres `memorybox` / Docker `memorybox-pg`, Qdrant, media / HVRT files
- Gmail OAuth, `.env`, tokens
- `speech_voice_exemplars`, `face_evidence`, queue rows, transcripts
- `memorybox/recognition/data/legacy_hvrt_fragment_allowlist.json` in git
- Archive lock / drain env
- I14 product work

## Proposed sequence (after explicit authorization)

1. Copy the `i13-interactive-learn-20260910-105354` proof folder to a dated archive Tom names.  
2. List leftover backup dumps; Tom ticks which may be deleted.  
3. Delete only ticked temp dirs.  
4. Leave FlightSim runtime and DB untouched.

**Not authorized now.**
