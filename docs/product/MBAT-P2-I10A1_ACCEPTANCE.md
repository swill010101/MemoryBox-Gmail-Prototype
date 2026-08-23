# MBAT-P2-I10A.1 — Person Profile / Explorer acceptance

**Increment:** P2-I10A.1  
**Prove:** `python -m memorybox prove-person-i10a1`  
**FlightSim:** `MEMORYBOX_P1_RUNTIME_HOST=1 python -m memorybox prove-person-i10a1 --flightsim`  
**Contracts:** [MBSC-P2-I10A1_PERSON_SCREEN_CONTRACT.md](MBSC-P2-I10A1_PERSON_SCREEN_CONTRACT.md) · [MBPRD-P2-I10A1_PERSON_PROFILE_EDITOR.md](MBPRD-P2-I10A1_PERSON_PROFILE_EDITOR.md)

These cases must pass **before** I10A.1 is accepted. The prove harness encodes chrome and route contracts as static checks; service checks reuse existing profile/person APIs. Implementation is what turns failing chrome checks green.

---

## A. Explorer header (one card above Ask)

| ID | Criterion |
|---|---|
| A1 | Person Explorer has **one** identity header above Ask (`#mb-person-header`). |
| A2 | `#mb-explore-curator` is **absent or hidden** on the Person surface (no second portrait/name card below Ask). |
| A3 | Header actions are labeled **About**, **Edit**, **Relationships**, **Learn** (`#mb-person-about`, `#mb-person-edit`, `#mb-person-relationships`, `#mb-person-learn-link`). |
| A4 | No control labeled **View / Edit details**. |
| A5 | Header includes labeled slots for life dates (`data-mb-life-dates` or equivalent) and does not present an unlabeled date range as lifespan. |
| A6 | Header includes labeled memory totals by kind and a total (`data-mb-memory-totals`). |
| A7 | Always-visible header HTML does not render email or phone values (no contact dump). |
| A8 | Also-known-as slot exists (`data-mb-also-known-as`); may be empty when no alias. |
| A9 | Place slot exists (`data-mb-important-place`); omitted or empty when no SoT. |
| A10 | Result / media date range, if shown, is labeled as results/view (`data-mb-result-range` or copy containing “result” / “in this view”), not as Born/Died. |

## B. About versus Edit

| ID | Criterion |
|---|---|
| B1 | **About** navigates to `/people/{id}/edit?view=1` (header `#mb-person-about` and footer Open profile). JS must not open the text drawer as About. |
| B2 | **Edit** `href` is `/people/{id}/edit` without `view=1`. Click does **not** open About. |
| B3 | About view-mode screen has an **Edit** control to `/people/{id}/edit`. |
| B4 | About/view uses `person-edit.html` cards: identity, aliases, life facts, notes, family, contacts, places, provenance/confirmation. |
| B5 | About view-mode is read-only (`mb-edit-readonly` / disabled fields). No Advanced writes. |
| B6 | `GET /people/{person_id}/edit` is registered and serves the family editor (not `people.html` admin). |
| B7 | Family Edit is **not** `?admin=1`. |

## C. Shared SoT / no Immich write-back

| ID | Criterion |
|---|---|
| C1 | `rename_person` updates only `people.display_name` (source still contains no Immich person PATCH). |
| C2 | `reject_mapping` / `teach_provider_person` / `merge_people` remain MB-only (existing I6/I9A; re-asserted). |
| C3 | Header, About, and Edit consume the same profile bundle (`GET /people/{id}/profile`) for name, facts, aliases, contacts, relationships. |
| C4 | Date precision: birth/death display path honors precision (year/month/day/unknown) — service + UI contract once implemented. Until then the prove records the schema gap as a required I10A.1 build item. |

## D. FlightSim (`--flightsim`)

| ID | Criterion |
|---|---|
| D1 | `MEMORYBOX_P1_RUNTIME_HOST=1`. |
| D2 | Open a Person Explorer URL: one header, no curator identity card, About lands on `/people/{id}/edit?view=1`, Edit lands on `/people/{id}/edit` populated for that person. Family chips show preferred portraits and kinship labels. |
| D3 | Change display name on Edit, return to Explorer: header name updated; Immich person name unchanged. |

---

**Do not treat I9A `prove-person-profile` as I10A.1 chrome acceptance.** That harness stays for I9A services.
