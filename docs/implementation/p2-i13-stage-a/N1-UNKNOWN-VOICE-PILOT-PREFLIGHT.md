# N1 Unknown no-match pilot: read-only preflight

This preflight prepares the exact four-span Tom acceptance plan without creating an admission, invoking the model, extracting audio, or writing to FlightSim. It uses the already verified local TitaNet environment and model.

## Fixed evidence

| Key | Role | Bound | Truth |
|---|---|---|---|
| T2 | training | `vid-da41273dbd9ac4bb`, 00:37.120?00:42.400 | Tom Will |
| O1 | held-out | `vid-c57dbd21f993f6d1`, 02:32.240?02:38.340 | Tom Will; expected match |
| H1-as-Tom-negative | held-out | `vid-c57dbd21f993f6d1`, 05:25.220?05:45.560 | Eugene Will; expected no match |
| N1-TV-announcer-unknown | held-out | `vid-c015e0fe07414fcc`, 00:00.000?00:06.740 | Unknown TV announcer; expected no match |

N1 remains annotation `74cc9646-82db-4899-960d-f795f691c524`, transcript version `8f879c74-ceb9-4f2c-b464-4f494ca66c25`, `speaker_state=unknown`, `person_id=NULL`. Any revision, retirement, source hash change, or bound change causes preflight to stop.

## Check-only command

After a clean detached release at the stated commit is created, run one line in the configured FlightSim PowerShell shell:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File 'C:\MemoryBox-releases\<n1-unknown-release>\docs\implementation\p2-i13-stage-a\prepare-n1-unknown-voice-pilot.ps1' -ExpectedReleaseSha '<commit>' -ToolRelease 'C:\MemoryBox-releases\p2-i13-voice-pilot-6d56da5'
```

Expected output: `mode: check_only`, four work items, 38.46 selected seconds, `private_audio_processed: false`, `database_writes: false`, and `admission_created: false`.

`-WritePlan` may be used only after review of that check-only result. It writes one immutable plan into the detached release and still does not create an admission or process private audio. A separate consolidated deployment-readiness review is required before execution.
