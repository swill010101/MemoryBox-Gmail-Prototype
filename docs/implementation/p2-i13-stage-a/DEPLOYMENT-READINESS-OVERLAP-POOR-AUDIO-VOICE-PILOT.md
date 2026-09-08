# FlightSim readiness: overlap / poor-audio Eugene voice pilot

## Founder authorization

Tom confirmed both pilot intervals on 2026-09-08 after in-browser review:

| Key | Owner confirmation |
|---|---|
| E2-1532-overlap-held-out | Eugene speaking with mixed TV background on 1532; interval-specific waiver approved |
| O2-tom-offcamera-negative | Tom Will off-camera confirmed |

Confirmation reference: `Tom-confirmed-overlap-pilot-intervals-2026-09-08`

**Execution** requires a separate run approval reference: `Tom-approved-overlap-poor-audio-voice-pilot-run-2026-09-08` (or Tom’s explicit “approved run” in chat).

## Exact scope

| Key | Role | Evidence | Expected |
|---|---|---|---|
| T-gs2-reuse | training | Eugene, grandpa 002, 00:26.30–00:34.78 | reference only |
| E2-1532-overlap-held-out | held-out | Eugene, 1532, 09:02.82–09:12.78 | match (narrow overlap evidence) |
| O2-tom-offcamera-negative | held-out | Tom off-camera, 1532, 15:48.30–15:55.50 | no-match |
| N1-TV-announcer-unknown | held-out | Unknown TV, meals on wheels | no-match |

Budget: four extracts, four embeddings, three comparisons, 32.38 seconds, one attempt per span, no automatic retry.

## FlightSim execution sequence

Use checkout `C:\MemoryBox` at the pushed commit. Live-checkout WIP (marvin_capture, config, runtime dirs) is expected; helpers pin **code identity by SHA only**, not a clean git tree.

```powershell
cd C:\MemoryBox
git pull --ff-only origin codex/p2-i13-stage-a
$sha = (git rev-parse HEAD).Trim()
$tool = 'C:\MemoryBox-releases\p2-i13-voice-pilot-6d56da5'
$approval = 'Tom-approved-overlap-poor-audio-voice-pilot-run-2026-09-08'

$env:MEMORYBOX_RECOGNITION_DRAIN = '0'
$env:MEMORYBOX_SPEECH_DRAIN = '0'
Remove-Item Env:MEMORYBOX_I13_ADMISSION_ID -ErrorAction SilentlyContinue

# 1. Check-only prepare
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\docs\implementation\p2-i13-stage-a\prepare-overlap-poor-audio-voice-pilot.ps1 `
  -ExpectedReleaseSha $sha -ToolRelease $tool

# 2. Write reviewed plan (creates i13-reviewed-overlap-poor-audio-voice-pilot-plan.json)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\docs\implementation\p2-i13-stage-a\prepare-overlap-poor-audio-voice-pilot.ps1 `
  -ExpectedReleaseSha $sha -ToolRelease $tool -WritePlan

# Copy plan_sha256 from step 2 into $planSha, then:
$planSha = '<plan_sha256_from_step_2>'

# 3. Deploy check-only
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\docs\implementation\p2-i13-stage-a\deploy-overlap-poor-audio-voice-pilot.ps1 `
  -ExpectedReleaseSha $sha -ExpectedPlanSha $planSha -ApprovalReference $approval -ToolRelease $tool

# 4. Execute once (backup + run + stop)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\docs\implementation\p2-i13-stage-a\deploy-overlap-poor-audio-voice-pilot.ps1 `
  -ExpectedReleaseSha $sha -ExpectedPlanSha $planSha -ApprovalReference $approval -ToolRelease $tool -Execute
```

Reserve up to 25 minutes. Prior Tom, N1, Patio, and reprocessing pilot results must remain **current**. Legacy queue and transcript counts must remain unchanged.

## Rollback

Preserve admission output and backup. Do not restore the database or retry automatically on failure.
