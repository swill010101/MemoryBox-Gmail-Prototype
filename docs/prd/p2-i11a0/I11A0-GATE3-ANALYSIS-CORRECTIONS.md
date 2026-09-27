# I11A.0 Gate 3 analysis corrections (sidecar)

**Kind:** derived analysis. Existing `gate3-b` run directories, CSV, JSONL, and narrations are preserved unchanged.  
**Experiment phase:** `legacy_reviewed_chunks` only. Not a cleaned-I14 operating-point recommendation.

## Defects and corrections

1. **`33229` estimated-evidence run / `fddc024a9d47526050898336cfdb508df292409c5a337e94c4b4a38c60066635`.** Peak VRAM `22.62109375` GB exceeded the 22.5 GB ceiling. Original classification `infrastructure_failure` (elapsed ~994 s, empty actual prompt tokens, planned `num_ctx=41472`). Corrected stop: **`vram_ceiling`**. VRAM ceiling now outranks infrastructure_failure when the peak is at or above 22.5 GB.

2. **Planned `num_ctx=41472` exceeded verified Qwen B context `40960`.** Future planning must set `exceeds_verified_model_context` and **reject before inference**. Classification: `planned_ctx_exceeds_model_limit`. That run remains stored; it must not be treated as a valid ladder measurement.

3. **`knee_range.first_regression_or_stop=2000` was wrong.** It used the first row’s `requested_evidence_tokens`, including calibration/placement rows at the 2,000 request / 3,048 packed packet. Corrected field uses **estimated evidence tokens of the first non-calibration capacity stop**. For this series that is **33229** (`vram_ceiling`), not 2000.

4. **Packet progression skipped intermediate conversation-sized packets.** The conversation-intact packer jumped (e.g. 3,048 → 4,372 → 6,889 → 9,314 → 21,704). That is preserved as historical packet behavior. The I14 cleaned ladder uses **message-boundary** nested packets targeting ~1,000 additional estimated evidence tokens per achievable rung.

5. **RAM series mixing.** Early high-RAM observations and later clean-session RAM must not be averaged into one knee. `ram_pressure_report` is labeled by `experiment_phase`. Do not mix `legacy_reviewed_chunks` with `i14_cleaned`.

6. **`successful_stable` vs `stable_ladder_rung=false`.** `successful_stable` means the pipeline completed with a passing safety margin. `stable_ladder_rung` is true only for coarse/refinement/calibrated_rerun rows that also pass placement/VRAM/regression gates. Repeat-validation rows may be `successful_stable` while `stable_ladder_rung` is false because they are copies, not new rungs.

7. **VRAM release.** Release is measured after an unload settling interval (`VRAM_RELEASE_SETTLE_SECONDS=8`). A sample taken while the model is still loaded is not a release claim.

8. **`cpu_spill`.** A fully GPU-resident `/api/ps` placement (`placement_status=gpu_resident`) must not be labeled `cpu_spill=true` without affirmative offload evidence (`size` vs `size_vram` while loaded).

9. **False `evidence_exhausted` and same-packet repeats.** Preserved on disk. Excluded from knee determination. Covered targets skip to the next achievable grid; exhaustion requires no remaining eligible messages.

10. **~22.6K estimated evidence tokens (`d73edda3…`, 22602 estimated / 24594 actual / `num_ctx=29952`).** Historical/provisional on the **legacy noisy** source only. **Not** the final cleaned-source recommendation.

No new knee, winner, or production chunk size is declared from this sidecar.
