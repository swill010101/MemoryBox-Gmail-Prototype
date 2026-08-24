# P2-I10A.2 — Narrative field and speech surface map

**Status:** **LOCKED** 2026-08-24 · **BUILD AUTHORIZED**  
**Assessment:** [MBAS-P2-I10A2_ASSESSMENT_RECONCILIATION.md](MBAS-P2-I10A2_ASSESSMENT_RECONCILIATION.md)

| Screen | Control today | Shared field | Speech semantics | Notes |
|---|---|---|---|---|
| Story editor | `#ed-body` | **Yes** | **Authored-memory** | I10A forbade dictation; I10A.2 reopens it here. Honor `?capture=1`. |
| Story editor | `#ed-title`, `#ed-desc` inputs | No | Off | Short |
| Artifact editor | `#ed-desc` | **Yes** | **Convenience** | Object description. I10B “forbidden” **superseded**. Audio transient. |
| Artifact editor | `#ed-label`, dates, pickers | No | Off | |
| Artifact `#rep-cap` | caption textarea | No | Off v1 | Short |
| Artifact Tell its story | `/story/ui?...&capture=1` | Story body | **Authored-memory** | No Artifact `MediaRecorder`. Story must honor `capture=1`. |
| Journal 5A | `#body`, `#editBody` | **Yes** | **Authored-memory** | Replace private Record/Stop. Not I10C done. |
| Journal | title, dates, author | No | Off | |
| Person Edit | `#mb-edit-notes` | **Yes** | **Convenience** | Durable text; no automatic voice memory. |
| Person Edit | name, nick, email, phone, dates | No | Off | A-20 |
| Ask / pickers / I9 | — | No | Off | Out |

**Required:** one narrative control + one speech module; semantics from the column above, not per-page forks.
