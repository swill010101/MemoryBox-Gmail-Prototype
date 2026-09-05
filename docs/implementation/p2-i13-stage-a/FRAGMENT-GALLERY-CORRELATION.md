# Gallery correlation and source-only preview - 2026-09-05

Tom supplied rendered card IDs following the read-only trace. Seven IDs match source vid-c57dbd21f993f6d1 appearance moments exactly, including their start times: 0.5, 10.5, 20.5, 30.5, 40.5, 60.5 and 70.5 seconds. Each persisted range lasts 0.5 seconds and has the verified native grouping lineage. Raw Gallery IDs and unrelated media identifiers are not copied into Git.

This proves the known native fragmentation is represented in the current Gallery. It does not establish that the earlier 15 owner-observed entries all belong to this source. Other supplied HVRT IDs are outside the source-scoped trace and must not be assigned to files by thumbnail resemblance or neighboring order.

Code inspection: explore/find.py builds video card IDs from provider, hit external_id and start time. Native retrieval sets external_id to the appearance moment ID, while video_external_id remains the actual source ID. Thus different card UUIDs do not demonstrate separate video files. Retrieval deduplicates source/start slots of 2.5 seconds, then merges overlaps and applies a result limit (default 48). This can select a subset of source evidence, but the current request's effective limit, ranking and filtering are not proven by the DOM capture alone. No claim is made that the default limit explains exactly seven or the earlier fifteen.

## Offline before/after proposal

The full source trace has 79 half-second moments. Grouping consecutive positive samples at the source-specific inferred ten-second cadence produces:

| Sample group | First sample (seconds) | Last sample (seconds) | Original moments |
|---|---:|---:|---:|
| A | 0.5 | 40.5 | 5 |
| B | 60.5 | 790.5 | 74 |

Verification against the supplied trace: all 79 unique moment IDs are retained exactly once across these two proposed sample groups. These are not confirmed continuous-presence intervals. The twenty-second gap remains unresolved and presence is not extended beyond the last observation. No persistent projection or runtime changes were made.

A proposed one-source Gallery card can expose these two evidence groups and original seek points, retaining record details. This requires screen-contract review and implementation approval; the preview is not a claim that the Gallery is already corrected. Correcting future interval construction and changing existing Gallery presentation are separate code paths; rerunning Learn with the current grouper would not fix the defect.

## Next step

The source-specific Gallery linkage is now sufficient to prepare a concrete implementation design against the accepted Gallery contract. Preserve all original observations/moments, confidence and authority, owner corrections and withdrawals. Do not infer continuous identity from sparse samples or globally collapse unrelated sources/people. Keep source playback and Gallery return context. No deletion, migration, recognition, transcription, Learn, conversion or archive operation is part of this diagnostic result. The exact earlier fifteen-card count remains an observation not reconstructed by this later snapshot.
