# P2-I10A.1 — Person Profile and Editor

**Status:** **ACCEPTED** 2026-08-24 (Tom: “i10a.1 is accepted”) · implementation `cursor/p2-i10a1-person-build-49da` · `prove-person-i10a1`  
**PR base:** `cursor/p2-i10b-artifacts-49da` (I10B **ACCEPTED**).  
**PRD:** [MBPRD-P2-I10A1_PERSON_PROFILE_EDITOR.md](MBPRD-P2-I10A1_PERSON_PROFILE_EDITOR.md)  
**Screen contract:** [MBSC-P2-I10A1_PERSON_SCREEN_CONTRACT.md](MBSC-P2-I10A1_PERSON_SCREEN_CONTRACT.md)  
**Assessment:** [MBAS-P2-I10A1_ASSESSMENT_RECONCILIATION.md](MBAS-P2-I10A1_ASSESSMENT_RECONCILIATION.md)  
**Field / action map:** [MBAS-P2-I10A1_FIELD_ACTION_MAP.md](MBAS-P2-I10A1_FIELD_ACTION_MAP.md)  
**Acceptance:** [MBAT-P2-I10A1_ACCEPTANCE.md](MBAT-P2-I10A1_ACCEPTANCE.md) · `prove-person-i10a1`  
**Visuals:** `MBUX-Person-Edit-v1.png` on `fe913a4` — copy to `docs/source/Screens/MBUX Person Screens/` before build.  
**Depends:** I5 Explorer **ACCEPTED** · I6 kinship **ACCEPTED** · I10A **ACCEPTED** · I10B **ACCEPTED** · `memorybox/profile` + `people` / `provider_identities`  
**Does not start:** I10A.2 voice · I10C · I11 · I8.5 Face SoT · Immich write-back · I5 gallery reopen

## Intent

Person Explorer stays **memory-focused** with **one** enriched header. **About** is the complete read-only supported record. **Edit** at `/people/{id}/edit` is the writable record. Header, About, and Edit share mapping, SoT, date precision, provenance, and kinship rules. MemoryBox Person is canonical. Immich people are linked provider identities. Corrections **do not silently write Immich**.

## Build locks

1. One header above Ask. No second portrait/name card below Ask.
2. Header is a **summary** (no full contacts). About is complete **read-only**. Edit is **writable**.
3. Header: preferred portrait, display name, aka when present, life dates with precision, owner kinship, place when available, labeled kind totals, About / Edit / Relationships / Learn.
4. Life dates ≠ unlabeled result/media range. Label totals vs kind counts.
5. **Edit** → `/people/{id}/edit` for the selected person. Bypasses About. No picker.
6. About footer opens the same editor.
7. Edit = Profile + Relationships + Identity and Sources + Advanced (specialist tools separated).
8. Taught relationships: one side; service inverses. Derived labeled Derived.
9. Date precision persisted and displayed (not a fake calendar day).
10. No Immich person/face write-back from rename, facts, reject, teach, merge, or owner.
11. No Person working draft. Save writes. Cancel without Save writes nothing.
12. Dark I10A/I10B chrome. Shell paper must not paint light cards.

## Locked implementation choices

- Family Edit: `GET /people/{id}/edit`.
- `?admin=1` is not the family Edit destination.
- Header Edit today opens About — **defect**.
- `+ Add family` today jumps to admin — **defect**.
- Important places: omit when no SoT; do not invent GIS.
- Preferred provider portrait is in scope.

## Does not start

I10A.2 · I10C · I11 · Face SoT · deleting a Person row · new Person identity model
