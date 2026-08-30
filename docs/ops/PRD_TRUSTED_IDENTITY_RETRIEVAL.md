# PRD — Trusted-identity retrieval (Phase 1)

**Branch:** `cursor/p2-i11a-trusted-identity-retrieve-49da`  
**Parent:** `cursor/p2-i11a-address-centric-email-49da` (PR #74 — do not merge)  
**Do not merge:** PR #76 (gate artifacts)

Phase 1 product acceptance is **done on FlightSim** (trusted `peggo417`,
retrieve/Gallery 5716, unsupported 0). This branch now continues Phase 2
(year-fair frozen Gemma+Sol Full-Evidence V2) then Phase 3 (L1 chunk models).
Do not treat the 1-email `3cf95fa4` freeze as Phase 2 complete.

## Problem

Address-centric prove showed `peggo417@hotmail.com` on Peggy George (~5,716
structured messages) but Explore/Gallery retrieved ~42,554 messages because
~700 auto-confirmed addresses were treated as retrieve keys. That scope is
not acceptable for the I11A model benchmark.

## Governing rules (general — no Peggy hardcode)

1. An address is trusted for retrieval only when it is an explicit canonical
   Person-profile contact, a direct owner/operator confirmation, or another
   already-approved deterministic trusted source.
2. `people[]` must never establish identity ownership or supply a display name
   used to confirm ownership.
3. Quoted/body headers may be diagnostic or candidate-discovery only — never
   independently promote an address to confirmed or trusted.
4. Structured From/To/CC/BCC proves participation, not Person ownership.
5. Fuzzy name / nickname / display-name matching may create a **candidate** only.
6. Preserve all observed identity evidence and provenance. Demote unsupported
   auto-confirmed identities to candidate/observed — do not delete.
7. Gallery and Ask/Full-Evidence V2 use the same trusted-identity resolver.

## Success (Phase 1)

- Retrieve/Gallery/Ask use **only** `retrieval_trust = trusted` emails.
- Unsupported addresses in Person retrieval = **0**.
- Report: every trusted identity + why; counts by observed/candidate/confirmed/
  trusted-for-retrieval; unique emails via each trusted address; Gallery count.
- Product: Peggy Explore/Gallery shows Peg Legg / Peggy George mail through
  trusted `peggo417` without unrelated mail.

## Out of scope (this slice)

- Historian / I11B expansion
- Gemma/Sol benchmark (Phase 2)
- Chunking (Phase 3)
- Merging PR #74 / #76

## FlightSim (after pull)

```
cd C:\memorybox
git fetch origin cursor/p2-i11a-trusted-identity-retrieve-49da
git checkout cursor/p2-i11a-trusted-identity-retrieve-49da
git pull origin cursor/p2-i11a-trusted-identity-retrieve-49da
python -m memorybox migrate
tools\flightsim-trusted-identity-gate.cmd
```

The gate sets `MEMORYBOX_P1_RUNTIME_HOST=1`, clears
`MEMORYBOX_ALLOW_DEV_DEFAULTS`, and defaults `MEMORYBOX_QDRANT_URL` to
`http://127.0.0.1:6333` (same as address-centric prove.ps1). Clearing ALLOW_DEV
drops the `:memory:` Qdrant fallback; without the URL, migrate/prove crash
before the trusted report. Then: if `TRUSTED_IDENTITY_GATE.json` already verifies, skip archive prove
and start year-fair freeze. Otherwise Phase 1 prove,
`tools/verify-trusted-identity-gate.py` (rejects ALLOW_DEV / cloud hostname
fakes), then `freeze-trusted-full-evidence-v2` (year-fair 200 emails after a sent_at-only
scan — does not load every trusted HTML body; committed before models), then
`run-trusted-evidence-pipeline` (reuses the green Phase 1 gate and that
year-fair freeze — no second Takeout identity scan). Freeze uses
`--reuse-if-coverage-ok` so a later gate retry does not rebuild a good
year-fair fixture. The frozen paste puts trusted email blocks before the
full ALLOWED_EVIDENCE_IDS roster so a short Ollama context still sees
mail (not just a 100k-token id list). Pipeline
skip/fail is `errorlevel 1`. Then `tools/verify-trusted-fev2-reports.py`
requires both Gemma (`gemma4:26b`) and Sol reports: same freeze hash, email
grounded, selected emails ≥ 8 (rejects `3cf95fa4`). After that verifier the
gate runs `run-trusted-fev2-chunked-models`. It stops on Phase 1 failure and
does not widen matching.

A green product report (`trusted=peggo417`, retrieve/Gallery > 0, unsupported=0)
with `C2`/`C2a` fail is a false fail: ALLOW_DEV leftover demoted the FlightSim
stamp. A later `MEMORYBOX_QDRANT_URL is required` fail is the same gate
missing the startmb Qdrant default. Re-run the gate after pull — do not
re-attest or widen matching.

If `peggo417@hotmail.com` is on the Person profile but classify is untrusted
(auto-expand actor), the owner profile add was overwritten or never stamped.
Re-add the address on the People card (now promotes the existing row to
`person_profile` / trusted) **or** attest, then re-run prove — not the pipeline
— until Phase 1 is green:

```
python -m memorybox attest-trusted-identity --person "Peggy George" --email peggo417@hotmail.com
python -m memorybox prove-trusted-identity-retrieval --flightsim
```

Auto-expand must not clobber an owner/operator profile contact. People UI
`add_contact` upserts and promotes an existing auto-expand row.

Phase 2 is included in the pipeline when Ollama has `gemma4:26b` and cloud Sol
env is set. The gate and the Python pipeline both load `MEMORYBOX_CLOUD_LLM_*`
and `MEMORYBOX_OLLAMA_BASE_URL` from repo `config\memorybox_app.env` (startmb-only
vars are otherwise invisible to cmd; `for /f` set lines can miss). A skipped
Gemma/Sol run is a hard gate fail. Paste `PHASE2_SUMMARY`.
If `ollama_model_missing`: `ollama pull gemma4:26b`. If `cloud_sol_not_configured`:
put `MEMORYBOX_CLOUD_LLM_BASE_URL`, `MEMORYBOX_CLOUD_LLM_API_KEY`, and
`MEMORYBOX_CLOUD_LLM_MODEL` in `config\memorybox_app.env`.

Manual equivalent after Phase 1 is green:

```
python -m memorybox freeze-trusted-full-evidence-v2 --person "Peggy George" --out-dir docs/test-output/trusted-full-evidence-v2
python -m memorybox run-trusted-full-evidence-v2 --fixture <FEV2.json> --provider ollama --model gemma4:26b
python -m memorybox run-trusted-full-evidence-v2 --fixture <same file> --provider cloud --model <sol-model>
```

Cloud Sol is opt-in and stateless: `MEMORYBOX_CLOUD_LLM_BASE_URL` + `MEMORYBOX_CLOUD_LLM_API_KEY`.
No chunking on the two single-pass runs. After both reports verify, run:

```
python -m memorybox run-trusted-fev2-chunked-models --from-dir docs/test-output/trusted-full-evidence-v2
```
