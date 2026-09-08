# FlightSim readiness: Eugene reprocessing lifecycle voice pilot

## Founder authorization

Tom approved the design proposal and authorized one bounded lifecycle run on 2026-09-08. Approval reference: `Tom-approved-eugene-reprocessing-lifecycle-run-2026-09-08`.

## Exact scope

| Key | Role | Evidence | Expected |
|---|---|---|---|
| R1-gs2-fresh | training | Eugene, grandpa sessions 2 002, 00:26.30–00:34.78 | reference only |
| H1-gs2-held-out | held-out | Eugene, same source, 01:26.42–01:45.44 | match |
| T2-as-Eugene-negative | held-out | Tom Will, 20111105_1530, 00:37.12–00:42.40 | no-match |
| N1-TV-announcer-unknown | held-out | Unknown TV announcer, 00:00.00–00:06.74 | no-match |

Budget: four extracts, four embeddings, three comparisons, 39.52 seconds, one attempt per span, no automatic retry.

## FlightSim execution sequence

Use a new detached release at `7629c18a57804a3c29521bda5c90c1f12a4622a7` and verified tool release `C:\MemoryBox-releases\p2-i13-voice-pilot-6d56da5`.

```powershell
$root = 'C:\MemoryBox'
$release = 'C:\MemoryBox-releases\p2-i13-eugene-reprocessing-7629c18'
$sha = '7629c18a57804a3c29521bda5c90c1f12a4622a7'
$tool = 'C:\MemoryBox-releases\p2-i13-voice-pilot-6d56da5'
$approval = 'Tom-approved-eugene-reprocessing-lifecycle-run-2026-09-08'

git -C $root fetch origin codex/p2-i13-stage-a
if (-not (Test-Path -LiteralPath $release)) {
  git -C $root worktree add --detach $release $sha
}

$env:MEMORYBOX_RECOGNITION_DRAIN = '0'
$env:MEMORYBOX_SPEECH_DRAIN = '0'
Remove-Item Env:MEMORYBOX_I13_ADMISSION_ID -ErrorAction SilentlyContinue
# Load established deployment env for MEMORYBOX_DATABASE_URL

cd $release

# 1. Check-only prepare (no writes)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\docs\implementation\p2-i13-stage-a\prepare-eugene-reprocessing-voice-pilot.ps1 `
  -ExpectedReleaseSha $sha -ToolRelease $tool

# 2. Write reviewed plan file (creates i13-reviewed-eugene-reprocessing-voice-pilot-plan.json)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\docs\implementation\p2-i13-stage-a\prepare-eugene-reprocessing-voice-pilot.ps1 `
  -ExpectedReleaseSha $sha -ToolRelease $tool -WritePlan

# Copy plan_sha256 from step 2 output into $planSha below, then:
$planSha = '<plan_sha256_from_step_2>'

# 3. Deploy check-only
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\docs\implementation\p2-i13-stage-a\deploy-eugene-reprocessing-voice-pilot.ps1 `
  -ExpectedReleaseSha $sha -ExpectedPlanSha $planSha -ApprovalReference $approval -ToolRelease $tool

# 4. Execute once (backup + run + stop)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\docs\implementation\p2-i13-stage-a\deploy-eugene-reprocessing-voice-pilot.ps1 `
  -ExpectedReleaseSha $sha -ExpectedPlanSha $planSha -ApprovalReference $approval -ToolRelease $tool -Execute
```

Reserve up to 25 minutes. Expected held-out outcomes: H1-gs2-held-out `match`; T2 and N1 `no_match`. Tom, N1, and Patio prior results must remain current. Legacy queue and transcript counts must remain unchanged.

## Rollback

Preserve admission output and backup. Do not restore the database or retry automatically on failure.
