# v5 live ladder (founder-authorized)

A2 `292642bad1a27cb4…` is the first valid full-prompt hardware rung and is **not rerun**.

One FlightSim `i11a0-gate3` invocation with `docs/ops/i11a0_gate3.b.full-prompt-v5.json` runs 19K → 20K → (21K if valid-run VRAM projection stays under 22.5 GB). It does **not** run 22K.

After 21K (or a 21K skip), the controller writes `v5_22k_decision.json` and stops. A VRAM boundary is not a performance knee.
