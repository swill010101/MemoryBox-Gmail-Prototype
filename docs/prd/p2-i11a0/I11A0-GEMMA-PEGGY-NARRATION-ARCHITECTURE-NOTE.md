# I11A.0 note: cleaned-email freeze vs Peggy / production narration

Inference-free planning only. This file does not authorize Words of Life, Peggy's complete narrative, SMS ingestion, or production narration.

## Current freeze

The accepted I14 freeze is **cleaned household email only**. SMS is not in this experiment. Do not invent or estimate an SMS count from Gemma ladder packets.

## Peggy later

Peggy's eventual source will also include SMS and will be materially larger than any single Gemma full-prompt rung measured here.

## Production cannot be one prompt

Production narration cannot depend on placing the entire archive in one model context window. FlightSim VRAM and Gemma context are practical limits, not a design that the whole corpus fits in one request.

## Proposed future architecture

1. Source-grounded extraction of dated events, relationships, recurring language, direct quotes, themes, and citations.
2. Deterministic deduplication and consolidation.
3. Chronological and thematic outline construction.
4. Retrieval of the strongest primary evidence for each section.
5. Final narration from the outline plus selected primary evidence.
6. Sentence-level claim and citation audit.

Do not implement those stages in this ladder increment.

