# MBBS — P2-I6 Relationship Graph & Derived Kinship · Increment Definition

**Status:** BUILD IN PROGRESS · harness green (`prove-p2-i6`) · FlightSim manual review pending  
**Date:** 2026-08-14  
**Authority:** [MBBS-P2_I6_RELATIONSHIP_KINSHIP_PRD.md](MBBS-P2_I6_RELATIONSHIP_KINSHIP_PRD.md) · Tom I6 directive · CAP-P2-011 · EVS-204–210  
**Branch:** `cursor/p2-i6-relationship-kinship-3061` (from I5 ACCEPTED)  
**Depends:** P2-I5 ACCEPTED

## Delivered

- Relationships **modal** over Person Explorer (Direct / Extended tabs; dark I5 language)
- Direct CRUD: add / edit role / change person / remove (unlink) / history
- SoT remains `person_relationship_assertions`; reciprocal via inverse projection (no dual editable SoT)
- `profile/kinship.py` — nephew/niece, aunt/uncle, grand*, cousins, in-laws; explainable paths
- API: `GET /people/{id}/relationships`, `GET /people/relationships/how-related`
- Ask: EVS-204–210 relationship reasoning (EVS-209 partial — needs open photo faces)

## OUT (locked)

No family tree · no new nav · derived not directly editable · Immich portrait P2-BL-I5-01 untouched

## Prove

```powershell
python -m memorybox prove-p2-i6
python -m memorybox prove-p2-i5
```
