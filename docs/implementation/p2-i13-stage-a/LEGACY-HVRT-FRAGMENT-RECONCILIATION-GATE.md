# Legacy HVRT Fragment Reconciliation — I13 completion gate

**Status:** **Required before final I13 acceptance** (not satisfied by the two-source pilot alone)  
**Policy:** `i13-legacy-hvrt-fragment-v1`  
**Corpus:** **22-video manifest only** — not archive-wide Learn or recognition

---

## Why this gate exists

The one-source correction (nine Gallery results → two valid moments across two reviewed sources) proved the **presentation grouping** works. That pilot is **not** completion. I13 must not close on FR-005 playback alone or that partial pilot.

---

## Scope boundary

| In | Out |
|---|---|
| Legacy HVRT `mb_native_i8b` half-second (0.5–2 s) moments on **manifest sources** | Archive Outcomes C/D/E |
| Gallery/retrieval **presentation** dedupe via source cards | DB deletion of `face_appearance_moments` or observations |
| Preserved provenance (moment IDs, observation IDs, authority) | Archive-wide or off-manifest sources |
| Cadence-aware grouping for **future** scans (`group_assigned_into_ranges`) | New recognition drains or Learn reruns |

---

## Eight completion requirements

| # | Requirement | Tool / implementation |
|---|-------------|----------------------|
| 1 | Inventory all remaining legacy HVRT 0.5–2 s observations with source, Person, timing, Gallery/retrieval lineage | [inventory-legacy-hvrt-fragments.py](inventory-legacy-hvrt-fragments.py) |
| 2 | Read-only preview: proposed grouping, retained moments, suppressed duplicate presentations, before/after counts | [preview-fragment-reconciliation.py](preview-fragment-reconciliation.py) |
| 3 | Apply proven grouping rules across manifest population **after founder preview review** | [publish-fragment-allowlist.py](publish-fragment-allowlist.py) → `memorybox/recognition/data/legacy_hvrt_fragment_allowlist.json` |
| 4 | Preserve immutable source videos, observations, provenance, auditability | Presentation-only `project_source_cards`; no migration |
| 5 | Remove obsolete duplicate **presentations**; do not delete source evidence | Source card collapses N moment rows → 1 card with `source_moments[]` |
| 6 | Preserve genuinely separate appearances (meaningful timing gaps) | No interval union; gap at 40.5–60.5 s preserved in pilot |
| 7 | Verify repaired pipeline cannot recreate half-second fragment cards | `tests/test_i13_fragment_correction.py` cadence + Gallery tests; future scans use recorded cadence |
| 8 | Post-correction counts + representative live Gallery/retrieval proof | [verify-fragment-reconciliation.py](verify-fragment-reconciliation.py) + owner FlightSim notes |

---

## Founder workflow

```powershell
# 1. Inventory (FlightSim, read-only)
$env:MEMORYBOX_I13_FRAGMENT_INVENTORY_OUTPUT = 'E:\MemoryBox-dev\p2-i13-stage-a\docs\test-output\legacy-hvrt-fragment-inventory.json'
& $python -B docs\implementation\p2-i13-stage-a\inventory-legacy-hvrt-fragments.py

# 2. Preview for review
$env:MEMORYBOX_I13_FRAGMENT_INVENTORY_JSON = 'E:\MemoryBox-dev\p2-i13-stage-a\docs\test-output\legacy-hvrt-fragment-inventory.json'
$env:MEMORYBOX_I13_FRAGMENT_PREVIEW_OUTPUT = 'E:\MemoryBox-dev\p2-i13-stage-a\docs\test-output\legacy-hvrt-fragment-preview.json'
& $python -B docs\implementation\p2-i13-stage-a\preview-fragment-reconciliation.py

# 3. After founder sign-off — publish allowlist (no DB writes)
& $python -B docs\implementation\p2-i13-stage-a\publish-fragment-allowlist.py `
  --inventory E:\MemoryBox-dev\p2-i13-stage-a\docs\test-output\legacy-hvrt-fragment-inventory.json `
  --reference Tom-legacy-hvrt-fragment-reconciliation-<date>

# 4. Deploy code + restart serve; verify Gallery/retrieval live

# 5. Post-correction verification
& $python -B docs\implementation\p2-i13-stage-a\verify-fragment-reconciliation.py
```

---

## Future archive admission (documented only)

When a founder later approves a **separate** archive admission (Outcomes C/D/E):

- This manifest-scoped fragment reconciliation **remains unchanged** until a new reviewed allowlist or admission explicitly supersedes it.
- Archive processing does **not** automatically extend fragment reconciliation to new sources.
- A wider corpus requires a **new** inventory → preview → allowlist publish cycle under archive scope.
- I13 does **not** implement or authorize archive register/unlock/start.

---

## Acceptance classification

| Checkpoint | Until gate complete |
|---|---|
| Legacy HVRT fragment reconciliation (PRD gate) | **pending** |
| I13-FR-021 Fragment inventory | **pending** (inventory script satisfies when run) |
| I13-FR-020 Legacy moment presentation | **pending** (live Gallery proof required) |

Do **not** mark I13 **accepted** until this gate, interactive Learn steady state, and Admin proof are all signed.
