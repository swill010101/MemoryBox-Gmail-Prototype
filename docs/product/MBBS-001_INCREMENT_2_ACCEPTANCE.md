# MBBS-001 Increment 2 — Acceptance report

**Date:** 2026-08-09  
**Status:** **ACCEPTED** (offline provider prove; live Immich/Ollama optional)  
**Charter:** [MBBS-001](MBBS-001_MEMORYBOX_BUILD_SPECIFICATION.md) Increment 2  
**Decision log:** [MBBS_DECISION_LOG.md](MBBS_DECISION_LOG.md) § Increment 2  
**Prior checkpoint:** tag `increment-1-accepted`

---

## Acceptance criteria (Increment 2)

| Criterion | Result | Evidence |
|-----------|--------|----------|
| Stable capability interfaces | **PASS** | `PhotoProvider`, `LlmProvider`, `EmailReadProvider` protocols under `memorybox/providers/` |
| Immich / LLM / Email → MemoryBox DTOs | **PASS** | `ImmichPhotoProvider`, `OllamaLlmProvider`, `MboxEmailReadProvider` + Fake photo/LLM for offline prove |
| Domain never uses Immich UUID as Person PK | **PASS** | `PhotoPersonRef.external_id` only; prove inserts `provider_identities` mapping where `people.id ≠ immich external_id` |
| All calls via interfaces | **PASS** | Acceptance exercises providers only; DTOs have no `person_id` / `immich_person_id` fields |

### Prove command

```powershell
$env:MEMORYBOX_DATABASE_URL = "postgresql://memorybox:memorybox@127.0.0.1:5432/memorybox"
python -m memorybox prove-providers
```

Result (2026-08-09): `"ok": true` — MB person UUID distinct from Immich-shaped external id.

---

## Delivered

| Path | Role |
|------|------|
| `memorybox/providers/photo/` | Protocol, DTOs, Fake, Immich adapter |
| `memorybox/providers/llm/` | Protocol, DTOs, Fake, Ollama adapter |
| `memorybox/providers/email_read/` | Protocol, DTOs, mbox reader (no SQLite write) |
| `memorybox/providers/acceptance.py` | `prove-providers` |
| `memorybox/providers/_fixtures/i2_synthetic.mbox` | Tiny email fixture |

Live Immich/Ollama require local config; acceptance does **not** require them.

---

## Stop

**Increment 2 accepted.** Do not begin Increment 3 without explicit authorization.
