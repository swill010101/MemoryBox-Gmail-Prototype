# Eugene reprocessing candidate review

The retired T1 annotation cannot be reused. This read-only inspector lists every active Eugene assignment and its prior voice-pilot use. A candidate is eligible only if it is active, unretired, and has never appeared in any prior voice-pilot plan.

Run it on FlightSim from the canonical checkout in the configured application shell. It reads PostgreSQL under repeatable-read, read-only isolation; it does not access audio, invoke a model, modify annotations, register an admission, or start reprocessing.

## FlightSim command

Load the established deployment environment first. Keep drains off and do not set `MEMORYBOX_I13_ADMISSION_ID`. Use the verified TitaNet tool release Python (`.titanet-venv`, not `.venv`):

```powershell
$env:MEMORYBOX_RECOGNITION_DRAIN = '0'
$env:MEMORYBOX_SPEECH_DRAIN = '0'
Remove-Item Env:MEMORYBOX_I13_ADMISSION_ID -ErrorAction SilentlyContinue
if (-not $env:MEMORYBOX_DATABASE_URL) { throw 'Load the deployment env first.' }

$python = 'C:\MemoryBox-releases\p2-i13-voice-pilot-6d56da5\.titanet-venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Verified TitaNet tool release is unavailable.' }

cd C:\MemoryBox
& $python -B docs\implementation\p2-i13-stage-a\inspect-eugene-reprocessing-candidates.py
```

If `fresh_reference_count` is `0`, Tom must save one new clear Eugene assignment in MemoryBox and rerun this inspector before any affected-only reprocessing proposal is finalized.

If the report has no eligible reference, Tom must save one new, clear Eugene assignment in MemoryBox. The next proposal will pin that assignment and define fresh held-out passages; it will not reuse T1 or silently convert prior held-out evidence into training.

## Owner audio-quality exclusion

Tom’s listening review excludes vid-c57dbd21f993f6d1 (20111105_1532.MP4) from Eugene training and held-out voice acceptance: TV/background audio overlaps Eugene throughout the reviewed material. Accurate STT does not establish clean source audio. The inspector reports this exclusion and will not select a newly saved annotation from that source.
