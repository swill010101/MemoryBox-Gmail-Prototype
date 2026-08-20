# P2-I10 implementation note (definition is not rewritten)

**Status:** Build authorized 2026-08-20 (Tom: “I10 is approved to build”). Definition remains `docs/source/MBBS-P2_INCREMENT_10_DEFINITION.md`.

**Locks honored:**
- I9 speech modules are unchanged. Cross-source Ask may *include* spoken moments; it does not replace I9 Learn/transcribe.
- I8A Q3 hide-comms remains for ordinary Show-me. Everything-about sets presentation on.
- Correlation links never rewrite source files.
- Rejected links stay in `correlation_links` with status=rejected.
- Pack answer is coverage + citations, not a saved Story.
- Owner unlink: Learn rail **Not this event** or `POST /correlate/unlink` — rejected row is kept.
- FlightSim compose (2026-08-20): `in florida` (any case) is a Place filter on photos, not the full person library. `Tom Will and Florida` after an Eugene session must not keep Eugene’s library.

**Ops:** `python -m memorybox migrate` then Ask *Show me everything I have about …* on Explore.

**Prove:** `python -m memorybox prove-p2-i10`
