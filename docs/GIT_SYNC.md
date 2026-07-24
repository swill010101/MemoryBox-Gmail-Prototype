# Git sync: FlightSim Takeout → Toms-Desktop

## Goal

Push immutable Gmail Takeout zips from **FlightSim** (`C:\memorybox`) to GitHub, then pull them onto **Toms-Desktop** (`C:\memorybox`).

Takeout zips use **Git LFS**. Derived data (`working/`, `database/`, `indexes/`, etc.) is **not** tracked.

## Canonical Takeout path

Prefer this folder name on both machines:

`archive/google-takeout-original/`

The earlier misspelling `archive/google-takout-original/` is also allowed in `.gitignore` / `.gitattributes` so nothing is lost if FlightSim still uses that name. **Do not delete or rename Takeout data** if zips already live under either path — keep the path that contains the files and document it here.

On Toms-Desktop today: `archive/google-takeout-original/` exists and is **empty** (no zips yet).

## What is tracked

| Path | Tracked? | Notes |
|------|----------|--------|
| `archive/google-takeout-original/**/*.zip` | Yes (LFS) | Original Takeout zips |
| `archive/google-takout-original/**/*.zip` | Yes (LFS) | Legacy misspelling support |
| `archive/checksums/` | Yes | Checksums if present |
| `working/`, `database/`, `indexes/`, `logs/`, `attachments/`, `exports/`, `backup/` | No | Local derived data |
| `application/`, `docs/`, `scripts/`, `tests/`, `config/*.example`, README | Yes | Code and docs |

## One-time: GitHub auth (both machines)

```powershell
gh auth login
# GitHub.com → HTTPS → login with browser
# Confirm repo access to MemoryBox-Gmail-Prototype
```

Or create a PAT with `repo` + `write:packages`/LFS access and:

```powershell
gh auth login --with-token
```

GitHub account (from your other repos): **swill010101**

Remote URL:

`https://github.com/swill010101/MemoryBox-Gmail-Prototype.git`

```powershell
cd C:\memorybox
git remote add origin https://github.com/swill010101/MemoryBox-Gmail-Prototype.git
# If remote already exists:
# git remote set-url origin https://github.com/swill010101/MemoryBox-Gmail-Prototype.git
```
## FlightSim — push Takeout (source of truth)

Prerequisites: `git`, `git-lfs`, `gh` authenticated, zips under the Takeout folder.

```powershell
cd C:\memorybox

# If repo not yet cloned/initialized on FlightSim:
# Recommended if C:\memorybox on FlightSim is NOT yet a git checkout of this repo:
#   1) Keep Takeout zips safe (do not delete).
#   2) git clone https://github.com/swill010101/MemoryBox-Gmail-Prototype.git into a temp folder
#      OR: git init + remote add + fetch + reset --hard origin/main inside C:\memorybox
#         ONLY if you understand that untracked local files are kept but tracked files match remote.
#   3) Place/copy the 8 zip files into archive\google-takeout-original\ (immutable originals).

git lfs install
git fetch origin
git checkout main
git pull origin main
# Ensure zips are present (read-only OK):
#   C:\memorybox\archive\google-takeout-original\*.zip

git add .gitattributes .gitignore
git add archive/google-takeout-original/
# If using misspelled folder instead:
# git add archive/google-takout-original/

git lfs status
git commit -m "Add Gmail Takeout archives via Git LFS"
git pull --rebase origin main   # if remote has commits
git push -u origin main
```

**Do not force-push.** **Do not modify zip contents.** Marking files read-only in NTFS is fine; git still reads them.

Verify LFS uploaded pointers + objects:

```powershell
git lfs ls-files
```

## Toms-Desktop — pull Takeout

```powershell
cd C:\memorybox
gh auth login          # if not already
git lfs install
git remote -v          # must point at MemoryBox-Gmail-Prototype
git pull origin main
git lfs pull
dir archive\google-takeout-original
```

After a successful pull you should see the 8 Takeout zip files locally. Leave them immutable; processing must copy into `working/` only.

## LFS size notes

Large Takeout sets need GitHub LFS quota (free tier is limited). If push fails on LFS storage, either buy LFS data pack or sync zips via a private file share instead — keep this git layout either way.

## Immutable archive rule

- Never extract/overwrite inside `archive/google-takeout-original/`
- Import pipeline copies into `working/`
- Original zips remain the snapshot in time
