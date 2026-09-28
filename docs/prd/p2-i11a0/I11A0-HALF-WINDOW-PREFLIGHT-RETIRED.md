# Half-window preflight retired

The v4 admission rule `predicted <= keep + (num_ctx-keep)//2` is **disproven** for Ollama 0.34.1 Qwen B chat when `truncate=false` and `shift=false`.

Evidence:

- A2 `292642bad1a27cb4…` evaluated **24,174** tokens at `num_ctx=28416` (half-window 14,210) with no truncation log and `truncated = 0`.
- Diagnostic B rejected overflow with HTTP 400 instead of a truncated HTTP 200.

The applicable planning equation is again `predicted_complete_prompt_tokens + 2500 + 1500 <= num_ctx`, with log verification, GPU residency, VRAM `<22.5 GB`, and fail-closed overflow. See `I11A0-FULL-PROMPT-V5-PLAN.md`.
