# P2-I10A.1 — Person Profile and Editor

**Status:** Definition **revised after repository assessment** · **not accepted** · **not build-authorized**  
**PR base:** `cursor/p2-i10b-artifacts-49da` (I10B **ACCEPTED**).  
**PRD:** [MBPRD-P2-I10A1_PERSON_PROFILE_EDITOR.md](MBPRD-P2-I10A1_PERSON_PROFILE_EDITOR.md)  
**Assessment:** [MBAS-P2-I10A1_ASSESSMENT_RECONCILIATION.md](MBAS-P2-I10A1_ASSESSMENT_RECONCILIATION.md)  
**Visuals:** `MBUX-Person-Edit-v1.png` on `fe913a4` — copy to `docs/source/Screens/MBUX Person Screens/` before build.  
**Depends:** I5 Explorer **ACCEPTED** · I6 kinship **ACCEPTED** · I10A **ACCEPTED** · I10B **ACCEPTED** · `memorybox/profile` + `people` / `provider_identities`  
**Does not start:** I10A.2 voice · I10C · I11 · I8.5 Face SoT · Immich write-back · I5 gallery reopen

## Intent

Person Explorer stays a **memory-focused** screen. A concise **read-only** About/Details panel may summarize the person. The **full Person Profile/Editor** is the only authoritative place to see and change the complete MemoryBox person record. MemoryBox Person is canonical. Immich people are linked provider identities. Corrections stay in MemoryBox and **do not silently write Immich**.

## Build locks (from owner + PRD)

1. Explorer does not gain the entire person record.
2. About/Details → existing informational panel; **read-only**; **not** the editor.
3. Panel footer opens the full editor for the **already selected** person.
4. Explorer **Edit** skips the panel and opens the same editor.
5. No second person picker on that path.
6. Full editor = Profile + Relationships + Identity and Sources + Advanced (specialist tools visually separated).
7. Taught relationships: user enters one side; service keeps inverses. Derived stays labeled Derived.
8. No Immich person/face write-back from rename, facts, reject, teach, merge, or owner.
9. No Person working draft. Save writes. Cancel without Save writes nothing.
10. Dark I10A/I10B chrome. Shell paper must not paint light cards.

## Locked implementation choices

- **Recommendation:** `/people/ui?person={id}&edit=1`. Reuse `GET /people/{id}/profile` and existing write routes.
- `?admin=1` is not the family Edit destination.
- Header Edit today opens the About drawer — **defect**; fix in this increment.
- Important places: no person-place SoT today — honest empty unless a later decision adds I10 `places` links.
- Birth/death: `DATE` or absent (unknown). Partial dates are not in schema.

## Does not start

I10A.2 · I10C · I11 · Face SoT · deleting a Person row · new Person identity model
