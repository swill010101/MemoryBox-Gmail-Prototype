# MBBS-001 Increment 9A — Person Profile acceptance

**Status:** READY FOR FLIGHTSIM OWNER ACCEPTANCE  
**Date:** 2026-08-11  
**Definition:** [MBBS-001_INCREMENT_9A_DEFINITION.md](MBBS-001_INCREMENT_9A_DEFINITION.md)

## Harness

```powershell
cd C:\memorybox
git fetch
git checkout cursor/marvin-capture-v01-3344
git pull
python -m memorybox migrate
$env:MEMORYBOX_ALLOW_DEV_DEFAULTS = "1"   # desktop only if needed
python -m memorybox prove-person-profile
```

FlightSim final:

```powershell
$env:MEMORYBOX_P1_RUNTIME_HOST = "1"
$env:MEMORYBOX_OWNER_PERSON_ID = "<Tom Will people.id>"
python -m memorybox prove-person-profile --flightsim
```

## Owner gate (FlightSim)

1. Set `MEMORYBOX_OWNER_PERSON_ID` to the canonical Tom Will `people.id` (I6-merge duplicates first if needed).
2. Restart serve with that env.
3. Open `/people/ui` — Profile section: load Eugene Will; add birth_date `1927-06-11`; assert Eugene `father_of` owner; record Eugene↔Anne marriage `1947-09-25`.
4. Ask: “Who is my father?” → Eugene; “When was my father born?” → 1927-06-11; “Show me pictures of my father.” → resolves to Eugene then existing media path.

## Out of scope (do not claim)

EVS-014 · genealogy tree viz · auto-inferred family · Immich write-back · multi-user · Places/Event platform · universal lazy-teach · polish
