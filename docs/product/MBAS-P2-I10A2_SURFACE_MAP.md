# P2-I10A.2 — Narrative field and speech surface map

**Status:** Planning only **2026-08-24** · not build-authorized  
**Assessment:** [MBAS-P2-I10A2_ASSESSMENT_RECONCILIATION.md](MBAS-P2-I10A2_ASSESSMENT_RECONCILIATION.md)

| Screen | Control today | Kind | Speech in I10A.2 | Notes |
|---|---|---|---|---|
| Story editor | `#ed-body` textarea | Narrative | **Yes** — shared field | Primary. I10A forbade dictation; I10A.2 reopens it here. |
| Story editor | `#ed-title` input | Short | **No** | Title |
| Story editor | `#ed-desc` input | Short | **No** | Optional one-line description, not a textarea |
| Artifact editor | `#ed-desc` textarea | Narrative | **Yes** — shared field | Object description. Testimony belongs on Stories. |
| Artifact editor | `#ed-label` input | Short | **No** | Name |
| Artifact editor | `#rep-cap` textarea | Short caption | **No** v1 | Representation caption |
| Artifact **Tell its story** | (intended) Story `#ed-body` | Narrative | **Yes** via Story | I10B consumes Story dictation; no Artifact `MediaRecorder` |
| Journal 5A | `#body` textarea | Narrative | **Yes** — shared field | Replace whole-field STT overwrite and screen-local recorder |
| Journal 5A | `#editBody` textarea | Narrative | **Yes** — same control | Version body |
| Journal 5A | `#title`, dates, author | Short / structured | **No** | |
| Person Edit | `#mb-edit-notes` textarea | Narrative | **Yes** — shared field | `person_facts` notes, not `people.notes` |
| Person Edit | name, nick, email, phone, dates | Short / structured | **No** | AT-11 |
| Person Explorer Ask | Ask input | Query | **No** | Spoken Ask is out |
| Explore / pickers | typeahead, dates | Short | **No** | |
| Guided Capture | various textareas | Campaign / admin | **Out** | Not I10A.2 |

**Shared control (Required):** one narrative field used by every **Yes** row. Speech is an option on that control, not a per-page feature.
