# MBBS — P2-I6 Relationship Graph & Derived Kinship · Increment Definition / Acceptance

**Status:** **ACCEPTED** (2026-08-14 — Tom: “i6 passes”)  
**Authority:** [MBBS-P2_I6_RELATIONSHIP_KINSHIP_PRD.md](MBBS-P2_I6_RELATIONSHIP_KINSHIP_PRD.md) · Tom I6 directive · CAP-P2-011 · EVS-204–210  
**Branch:** `cursor/p2-i6-relationship-kinship-3061` (from I5 ACCEPTED)  
**Depends:** P2-I5 ACCEPTED

---

## What shipped (ACCEPTED)

- Relationships **modal** over Person Explorer (Direct / Extended tabs; dark I5 language)
- Direct CRUD: add / edit role / change person / remove (unlink) / history
- SoT remains `person_relationship_assertions`; reciprocal via inverse projection (no dual editable SoT)
- `profile/kinship.py` — nephew/niece, aunt/uncle, grand*, cousins, in-laws; explainable paths
- API: `GET /people/{id}/relationships`, `GET /people/relationships/how-related`
- Ask: EVS-204–210 relationship reasoning

## OUT (locked — do not reopen)

No family tree · no new nav · derived not directly editable · Immich portrait **P2-BL-I5-01** untouched

## Carry-forward / backlog (not ACCEPTED blockers)

| ID | Item | Notes |
|----|------|-------|
| **P2-BL-I6-01** | EVS-209 kinship-in-photo | Graph filter is ready; full pass needs an **open photo with recognized People**. Do not reopen I6. Not I7 SMS. |

Full parking: [MBBS_P2_BACKLOG_PLANNING.md](MBBS_P2_BACKLOG_PLANNING.md).

## Prove

```powershell
python -m memorybox prove-p2-i6
python -m memorybox prove-p2-i5
```

## Authorization stop-line

| Step | Status |
|------|--------|
| PRD + I6 directive | **LOCKED** |
| Build | **AUTHORIZED** (2026-08-14) |
| Implementation | **COMPLETE** on `cursor/p2-i6-relationship-kinship-3061` |
| Founder FlightSim acceptance | **ACCEPTED** (2026-08-14 — Tom: “i6 passes”) |
| EVS-209 kinship-in-photo | **BACKLOG** P2-BL-I6-01 (not a reopen) |

P2-I6 is **ACCEPTED**. Next increment is **P2-I7 SMS/Text Evidence** — [definition draft](MBBS-P2_INCREMENT_7_DEFINITION.md). **No I7 build** until Tom locks the open questions and authorizes.
