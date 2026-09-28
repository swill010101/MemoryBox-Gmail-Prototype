# v5 live ladder (founder-authorized autonomous continuation)

A2 through 22K on `gate3-b-i14-full-prompt-v5` are **immutable** and are not rerun.

Founder authorized the validated controller to finish the remaining Qwen B full-prompt ladder autonomously. `founder_review_23k` and per-rung founder gates are bypassed for this continuation.

Resume the same series, start at **23K**, then continue in 1,000-token nested complete-message steps with valid-run VRAM preflight, `num_ctx <= 40960`, and peak VRAM `< 22.5 GB`. After the coarse stop, run 250-token refinement where distinct packets exist, then authorized repeats at the proposed point and next-larger safe point. Assemble the review package and stop. Do not start the Peggy scenario.

Historical sidecars `v5_22k_decision.json`, `v5_23k_decision.json`, and `v5_a2_through_22k_review.json` are preserved in place.
