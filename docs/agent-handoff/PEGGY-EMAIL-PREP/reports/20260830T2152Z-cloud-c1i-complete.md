MB_REVIEW_READY
task: PEGGY-EMAIL-PREP
handoff: R1
correction_pass: C1i
run_id: 20260830T2152Z-cloud-c1i-complete
code_commit: a52eb1ad8c72ec99e897b95449528267de82e859
prior_report_superseded_metadata_only: docs/agent-handoff/PEGGY-EMAIL-PREP/reports/20260830T2147Z-cloud-c1i.md
stage: preparation-only
scope: paged-multi-hop-rfc-neighbor-fetch
status: READY_FOR_REVIEW

## Metadata correction (does not change code)

The prior C1i report `20260830T2147Z-cloud-c1i` shipped with `code_commit: PLACEHOLDER`. This new immutable report binds the same C1i implementation to its full SHA. It does not overwrite prior reports and does not authorize new code work.

## Lightweight PRD (C1i)

Problem: C1h neighbor fetch used one targeted query with a 500-row page cap treated as fatal saturation. FlightSim prepare returned `ok:false` / `rfc_neighbor_query_saturated:500` and wrote no packet. One-hop fetch also could not reach grandparent messages in a chain.

Success: deterministic keyset paging (no OFFSET), multi-hop expansion with visited RFC/row tracking, DB errors fail closed, attach/hop caps return a reviewable packet with honest incomplete metadata.

In: neighbor fetch/attach only; synthetic proves; PREPARATION_REPORT + SOURCE_MAP inventory fields.
Out: thank-you template attribution, bound prompt_tokens/usable budget (deferred, not waived), chunking, Gemma/Sol, merge, identity widening.

## What changed (C1i code at bound SHA)

1. **Keyset paging.** Targeted `ANY(%s)` query uses `ORDER BY id` + `AND id > %s` + `LIMIT page_size`. No unordered scan. No OFFSET.
2. **Multi-hop.** Newly discovered RFC ids from attached rows drive further targeted pages until the frontier is empty or hop cap.
3. **Cycle/duplicate safety.** Visited evidence ids and queried RFC ids prevent re-fetch loops.
4. **References match.** `regexp_split_to_array` token match replaces substring `position()` matching.
5. **Caps vs errors.** Real DB errors → `ok:false`. Attach cap or hop cap → `ok:true` with `neighbor_context_complete:false`, `stopping_reason`, and `unresolved_rfc_ids`.
6. **Reporting.** inventory / PREPARATION_REPORT include neighbor_* metadata fields.

Deferred before Gemma (not waived): service-template thank-you attribution; immutable/recomputed replay budget oversize check.

## Tests actually run

Host: Cursor cloud agent, not FlightSim. Synthetic only.

`MEMORYBOX_ALLOW_DEV_DEFAULTS=1 python3 -m memorybox prove-trusted-identity-retrieval`

Results at `a52eb1ad8c72ec99e897b95449528267de82e859`: `problems: []`. Proves include three-hop chain, multiple filled keyset pages, cycle termination, attach-cap incomplete metadata, DB error propagation.

Not run: FlightSim `prepare-trusted-email-review --flightsim`.

## FlightSim / human / model

- Code-complete (C1i unit checks): **YES**
- FlightSim-prepared after C1i: **NO** (Tom to rerun)
- Human-approved hash: **NO**
- Inference: **NONE**

## How to regenerate (FlightSim)

```
cd C:\memorybox
git fetch origin cursor/p2-i11a-trusted-identity-retrieve-49da
git -c core.editor=true pull --rebase --no-edit origin cursor/p2-i11a-trusted-identity-retrieve-49da
git rev-parse HEAD

$env:MEMORYBOX_P1_RUNTIME_HOST = "1"
Remove-Item Env:MEMORYBOX_ALLOW_DEV_DEFAULTS -ErrorAction SilentlyContinue
if (-not $env:MEMORYBOX_DATABASE_URL) {
  if (Test-Path config\memorybox_app.env) {
    Get-Content config\memorybox_app.env | ForEach-Object {
      if ($_ -match '^\s*MEMORYBOX_DATABASE_URL\s*=\s*(.*)$') {
        $env:MEMORYBOX_DATABASE_URL = $Matches[1].Trim().Trim('"').Trim("'")
      }
    }
  }
}
if (-not $env:MEMORYBOX_DATABASE_URL) {
  $env:MEMORYBOX_DATABASE_URL = "postgresql://memorybox:memorybox@127.0.0.1:5432/memorybox"
}
python -m memorybox prepare-trusted-email-review --person "Peggy George" --flightsim
```

Do not git-add MODEL_PASTE. Do not run Gemma.

WAITING FOR TOM — NO MODEL EXECUTION AUTHORIZED.
