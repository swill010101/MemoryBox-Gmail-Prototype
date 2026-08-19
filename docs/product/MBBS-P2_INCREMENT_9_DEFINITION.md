# P2-I9 Spoken Moments — definition pointer

**Status:** **HOLD FOR APPROVAL** (2026-08-19) · **not locked** · **not build-authorized**  
**Authority:** [docs/source/MBBS-P2_INCREMENT_9_DEFINITION.md](../source/MBBS-P2_INCREMENT_9_DEFINITION.md) (v1.1)

**Sequence:** P2-I8A **ACCEPTED** (2026-08-19) → P2-I8B (runtime in flight; I9 wait until **I8B founder ACCEPTED**) → I9 Spoken Moments (video speech only).

Do not start I9 schema, queue, STT, diarization, or Text-pane work until Tom approves v1.1 **and** I8B is ACCEPTED **and** I9 build is explicitly authorized.

Founder locks (also in the source file): local diarization with anonymous speakers; no standalone audio; Choose Person + Learn on a transcript span (no new speaker product); evidence-first semantic retrieval (transcript embeddings/Qdrant + MBQL; residual chat does not replace evidence); word timing / diarized turns / Spoken Moments kept distinct; I8B videos as the controlled acceptance subset; face ranges optional context only.
