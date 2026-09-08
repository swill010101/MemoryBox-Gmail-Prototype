# Overlap and poor-audio voice gap plan

**Status:** design only — no run authorized  
**Purpose:** smallest next owner-review path for the largest remaining voice acceptance gap

## Why this is next

Lifecycle reprocessing, Tom off-camera positive evidence, N1 Unknown no-match, and retirement stale cascade are now bounded and recorded. The remaining checklist gap that still requires **new owner truth** before any pilot is overlap or poor/mumbled audio on `20111105_1532.MP4`.

## Owner exclusions already fixed

- `vid-c57dbd21f993f6d1` is excluded from **Eugene training and held-out voice evidence** because TV/background audio overlaps Eugene throughout Tom's listening review.
- N1 on `vid-c015e0fe07414fcc` is narrow Unknown TV-announcer evidence only; it does not generalize to overlap on 1532.

## Tom-reported owner evidence (2026-09-08)

FlightSim inspector captured active annotations. Unused prior to this proposal:

- Eugene `bbceb696…` on 1532 (09:02.82–09:12.78) — candidate overlap/poor-audio **held-out**  
- Tom `2b013ef8…` on 1532 (15:48.30–15:55.50) — candidate off-camera **negative control**  
- Tom `d890e55e…` on 1532 (10:20.14–10:22.04) — too short; not selected  

Design-only proposal: [OVERLAP-POOR-AUDIO-VOICE-PILOT-PROPOSAL.md](OVERLAP-POOR-AUDIO-VOICE-PILOT-PROPOSAL.md). **Requires founder waiver** for interval-specific use of `bbceb696` on excluded 1532 before any run.

## Candidate owner work (no pilot until saved)

| Key | Range | Current state | Needed |
|---|---|---|---|
| Q1 | 02:18.72–02:23.18 on 1532 | Listening only; TV + Eugene together | Save exact truthful sub-spans or mark Unknown; never use whole interval |
| U1 remainder | 1532 outside U1-clear | Unreviewed | Owner listening; save only clear single-speaker intervals if any |

Do not repurpose H1, U1-clear, O1, N1, or excluded-source annotations (`bbceb696…` on 1532).

## Future bounded pilot shape (template only)

Only after Tom saves at least one new overlap or poor-audio annotation on an **approved** source:

- One training reference already current elsewhere (for example T2 or a fresh Eugene reference not on 1532).
- One held-out overlap/poor-audio case with owner-confirmed truth.
- Known negative controls reused from prior pilots (for example N1 or T2).
- Same four-span, one-attempt, no-retry budget as prior voice pilots.

## Explicit prohibitions

- No pilot on `vid-c57dbd21f993f6d1` for Eugene match evidence.
- No Learn, drains, archive processing, or Gate 4 unlock inferred from this plan.
- No automatic retry or broadened corpus run.

## FlightSim read-only recheck before any future proposal

```powershell
$python = 'C:\MemoryBox-releases\p2-i13-voice-pilot-6d56da5\.titanet-venv\Scripts\python.exe'
cd C:\MemoryBox
& $python -B docs\implementation\p2-i13-stage-a\inspect-voice-pilot-status.py
```
