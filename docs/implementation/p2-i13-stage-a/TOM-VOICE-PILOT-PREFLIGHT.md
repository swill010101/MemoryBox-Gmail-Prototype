# Tom voice-pilot read-only preflight

This script prepares and validates the exact second pilot without creating an admission, invoking the model, extracting private audio, or writing to the production database. It verifies the detached release, local TitaNet artifact, and current active annotations before calling the existing plan builder in a read-only transaction. The default mode writes the generated plan only to a temporary file and removes it after preview.

## Inputs fixed by the reviewed proposal

- Training: T2, Tom Will, `vid-da41273dbd9ac4bb`, 00:37.120–00:42.400.
- Positive held-out: O1, Tom Will off camera, `vid-c57dbd21f993f6d1`, 02:32.240–02:38.340.
- Negative controls: H1 and U1-clear, Eugene Will.
- Bounds: four spans, four attempts, 40.80 seconds, frozen thresholds 0.30 / 0.45.

H1 and U1-clear were scored in the first Eugene pilot. They are therefore Tom-specific negative controls, not a fresh benchmark.

## Check-only command

From a configured FlightSim PowerShell shell, after creating a clean detached release at the stated commit:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File 'C:\MemoryBox-releases\<tom-release>\docs\implementation\p2-i13-stage-a\prepare-tom-voice-pilot.ps1' -ExpectedReleaseSha '<commit>'
```

Expected output has `mode: check_only`, exactly four work items, `private_audio_processed: false`, `database_writes: false`, and `admission_created: false`.

## Reviewed-plan file mode

Only after the check-only output is reviewed, add `-WritePlan`. This writes the prepared immutable plan into the detached release, still without an admission, model invocation, private-audio extraction, or database write. It refuses to overwrite an existing plan file.

A production readiness report and a separate founder approval remain required before any admission or private-audio run.