# Retirement lifecycle review plan

## Purpose

This is the next narrow I13 acceptance gap after the N1 Unknown no-match pilot. It first identifies one older, stopped, non-stale pilot admission and its active training reference. It does not retire any current Tom/N1 evidence, change annotations, start reprocessing, process audio, or touch queues.

## Read-only inspection

From a configured FlightSim release shell with drains off and no admission ID, run:

```powershell
python -B docs/implementation/p2-i13-stage-a/inspect-voice-retirement-candidates.py
```

Choose only a row marked `eligible_for_separate_retirement_proposal: true`. The preferred candidate is an older stopped admission whose result may become stale without invalidating the current Tom/N1 no-match acceptance.

## Later bounded lifecycle proof

After Tom selects an exact candidate, a separate readiness package must state the annotation ID, admission ID, retirement reason, expected stale-result observation, backup procedure, and rollback. Retirement preserves the annotation and history, prevents its future pilot reuse, marks dependent results stale, and creates no reprocessing. A separate reviewed proposal is required for any reprocessing.
