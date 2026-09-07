# Eugene reprocessing candidate review

The retired T1 annotation cannot be reused. This read-only inspector lists every active Eugene assignment and its prior voice-pilot use. A candidate is eligible only if it is active, unretired, and has never appeared in any prior voice-pilot plan.

Run it on FlightSim from an exact release in the configured application shell. It reads PostgreSQL under repeatable-read, read-only isolation; it does not access audio, invoke a model, modify annotations, register an admission, or start reprocessing.

If the report has no eligible reference, Tom must save one new, clear Eugene assignment in MemoryBox. The next proposal will pin that assignment and define fresh held-out passages; it will not reuse T1 or silently convert prior held-out evidence into training.
