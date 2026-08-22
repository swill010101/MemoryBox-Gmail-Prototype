# MBBS-001 Increment 6 — Acceptance

**Status:** **ACCEPTED** (FlightSim owner gate + teach → Ask confirmed mapping)  
**Date:** 2026-08-10  
**Definition:** [MBBS-001_INCREMENT_6_DEFINITION.md](MBBS-001_INCREMENT_6_DEFINITION.md)  
**Decision log:** [MBBS_DECISION_LOG.md](MBBS_DECISION_LOG.md) § Increment 6

## Owner gate (I6-OWNER) — PASSED

Tom used FlightSim `/people/ui` without developer intervention to teach a real Immich identity and retrieve photos via Ask with **confirmed** MB mapping.

| Item | Opaque id |
|------|-----------|
| Owner taught Person (Dan Will) | `4d1e8857-40f1-4d7a-b3db-20aae5e4f0fe` |
| Immich provider external id | `0a74834b-4859-4525-8cfb-54ada3957368` |

Post-teach Ask defect (lowercase `dan will` → empty planner `person`) fixed in `4c8cba4`; re-Ask confirmed mapping path.

## Harness

```text
python -m memorybox prove-person
# ok: true — teach, mapping PK, bulk, negatives, merge, rename, remap, shared resolver, Ask trust
```

## Shipped surface

| Surface | Path |
|---------|------|
| People UI | `/people/ui` |
| People API | `/people`, `/people/teach`, `/people/reject`, `/people/merge`, … |
| Person service | `memorybox.person` (central resolver) |
| Migration | `003_person_i6.sql` |
| Ask photo trust | confirmed mapping vs candidate disclosure |
| Prove | `prove-person [--flightsim]` |

## Stop

Do **not** begin Increment 7 / Guided Capture / EF-11 without explicit authorization. Immich write-back, email/phone identity productization, auto-merge, full EVS-014, and remote HTTPS remain out of I6.
