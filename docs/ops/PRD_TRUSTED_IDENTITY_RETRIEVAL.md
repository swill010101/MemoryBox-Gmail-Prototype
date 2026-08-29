# PRD — Trusted-identity retrieval (Phase 1)

**Branch:** `cursor/p2-i11a-trusted-identity-retrieve-49da`  
**Parent:** `cursor/p2-i11a-address-centric-email-49da` (PR #74 — do not merge)  
**Do not merge:** PR #76 (gate artifacts)

**Stop this slice at Phase 1.** Phase 2 (Gemma/Sol fixture) and Phase 3 (chunking)
start only after Phase 1 product acceptance.

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

The gate runs `run-trusted-evidence-pipeline` (Phase 1 report → freeze → Gemma → Sol).
It stops on Phase 1 failure and does not widen matching.

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

Phase 2 is included in the pipeline when Ollama / cloud Sol env is present.
Manual equivalent after Phase 1 is green:

```
python -m memorybox freeze-trusted-full-evidence-v2 --person "Peggy George" --out-dir docs/test-output/trusted-full-evidence-v2
python -m memorybox run-trusted-full-evidence-v2 --fixture <FEV2.json> --provider ollama --model gemma4:26b
python -m memorybox run-trusted-full-evidence-v2 --fixture <same file> --provider cloud --model <sol-model>
```

Cloud Sol is opt-in and stateless: `MEMORYBOX_CLOUD_LLM_BASE_URL` + `MEMORYBOX_CLOUD_LLM_API_KEY`.
No chunking on these two runs. Phase 3 starts only after both reports are comparable.

Phase 3 structure-only (after both single-pass reports exist):

```
python -m memorybox compare-trusted-fev2-chunks --fixture <same FEV2.json>
```
