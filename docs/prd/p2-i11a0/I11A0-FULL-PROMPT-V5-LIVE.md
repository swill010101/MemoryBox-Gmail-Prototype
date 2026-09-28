# v5 live ladder (founder-authorized)

A2 `292642bad1a27cb4…` is the first valid full-prompt hardware rung and is **not rerun**. Completed 19K/20K/21K artifacts on `gate3-b-i14-full-prompt-v5` are **immutable**.

One FlightSim `i11a0-gate3` invocation with `docs/ops/i11a0_gate3.b.full-prompt-v5.json` (`authorized_22k=true`) resumes that series, skips completed A2/19K/20K/21K packets, runs **only the 22K** nested I14 packet, then stops.

It does **not** run 23K, refinement, or repeats. A founder-review, VRAM, or model-context stop is not a performance knee.

The 22K packet must match packed 22,547 estimated evidence tokens, 90,186 bytes, 51 messages / 33 threads, predicted complete prompt 29,508, `num_ctx=33536`.
