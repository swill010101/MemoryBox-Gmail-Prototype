# FlightSim migration history reconciliation

Evidence supplied by Tom on 2026-09-05 from database memorybox: runtime versions 001 through 029 are recorded. Filename conflicts with the original Stage A checkout are 009 (person_fact_residence versus ai_trace), 025 (trusted_retrieval_identity versus historian_capture_i12), and 026 (backfill_email_retrieval_trust versus scope_admission). No I13 tables exist. AI trace tables and all 12 expected historian_capture tables do exist. This is owner-supplied read-only output, not a claim that the agent ran a new runtime inspection.

The repository migrator compares numeric versions only. Therefore an empty pending list did not mean the I13 schema was installed. Migration 010 explicitly documents the historical 009 collision; Capture table presence indicates 025's numeric ledger does not fully describe the deployed schema. No provenance for that separate Capture installation is inferred.

Correction: rename unapplied I13 026 to 030, the next number after the supplied runtime history, with SQL bytes unchanged. Do not renumber/replay I12, change existing ledger rows, merge unrelated communications migrations, or remove runtime schema. A fresh read-only preflight is still required because runtime history may change. The new script reports historical conflicts rather than claiming number-only comparison proves compatibility.

Deployment remains gated on correction review, refreshed schema metadata review, backup/restore verification, preservation of FlightSim's staged live Capture dependency, and explicit migration/locked-deployment approval. No runtime migration, processing, service change, or cleanup occurred in this correction. Table presence is not full schema or workflow compatibility proof.
