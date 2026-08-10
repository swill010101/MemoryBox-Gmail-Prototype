# MBBS-001 Increment 6 — Acceptance

**Status:** **BUILD SHIPPED — AWAITING FLIGHTSIM OWNER GATE**  
**Date:** 2026-08-10  
**Definition:** [MBBS-001_INCREMENT_6_DEFINITION.md](MBBS-001_INCREMENT_6_DEFINITION.md)  
**Decision log:** [MBBS_DECISION_LOG.md](MBBS_DECISION_LOG.md) § Increment 6

## Owner gate (I6-OWNER) — PENDING

On FlightSim, Tom uses `/people/ui` without developer intervention to:

1. Refresh Immich people and select **one real** Immich provider identity  
2. Teach / confirm MB Person display name → durable `provider_identities` mapping  
3. Ask for photos of that MB Person and receive hits via **confirmed** mapping (`identity_trust=confirmed`)

After Teach, record opaque Person id:

| Item | Opaque id |
|------|-----------|
| Owner taught Person | *(set after UX)* |

```powershell
$env:MEMORYBOX_P1_RUNTIME_HOST = "1"
$env:MEMORYBOX_I6_OWNER_PERSON_ID = "<opaque-person-uuid>"
# optional: $env:MEMORYBOX_I6_OWNER_IMMICH_EXTERNAL_ID = "<immich-external-id>"
python -m memorybox prove-person --flightsim
```

## Harness (desktop / FlightSim)

```text
python -m memorybox migrate
python -m memorybox prove-person
# ok: true covers I6-A..K synthetic (teach, mapping PK, bulk, negatives, merge, rename, remap, shared resolver, Ask trust)
```

## Shipped surface

| Surface | Path |
|---------|------|
| People UI | `/people/ui` |
| People API | `/people`, `/people/teach`, `/people/reject`, `/people/merge`, … |
| Person service | `memorybox.person` (central resolver) |
| Migration | `003_person_i6.sql` (`identity_negatives`, `person_merges`) |
| Ask photo trust | confirmed mapping vs candidate disclosure |
| Prove | `prove-person [--flightsim]` |

## Stop

Do **not** begin Increment 7 / Guided Capture / EF-11 without explicit authorization. Immich write-back, email/phone identity productization, auto-merge, HVRT, EVS-014, and remote HTTPS remain out of I6.
