# I11A.0 Phase 1 — accepted I14 source freeze (counts only)

Email-only. No SMS. No Ollama. I11A.1 not started. I14 database not modified.

## Accepted I14 identity

| Item | Value |
|------|--------|
| Accepted I14 code SHA | `b54be38ade9f378f1e25e0738bb9e9963f7dcd88` |
| Active generation | `i14-prepared-email-v3` |
| Generation id | `a3ec3877-f91d-49a0-8201-267b383c69ce` |
| Generation checksum | `cf12a9206b04abe697e20e90e9f336b8855476c94266506957aa7a934ae89785` |
| Scope | `household_email` / `source_kind=email` |
| Tables | `comms_prepared_generations`, `comms_prepared_threads`, `comms_prepared_messages`, `comms_prepared_participants`, `comms_prepared_attachments`, view `comms_prepared_active_generations` |
| Ledger | 035–040 (`036` schema, `037` T/M scale, `038` voice without recipient identity, `039` voice requires prepared text, `040` disposition) |
| Cleaned authored field | `comms_prepared_messages.cleaned_authored_text` (full body; not Gallery `left(..., N)` preview) |
| Immutable original | `evidence.id` + `evidence.payload_json` (not copied into the benchmark prompt) |
| Peggy | `Peggy George` / `cc6eb438-86a9-405c-89aa-6c6fc43de076` |
| Tom | `Tom Will` / `33509a4c-0869-458a-b0b9-35a669aace16` |
| Author identification | `comms_prepared_participants.role='from'` → `people.id`. `authorship=authenticated_focal` means any authenticated From person. |
| Voice | `voice_corpus` requires authenticated From + `quote_quality=clean` + resolved identity + `authored_displayable` |

v1 superseded; v2 validated unpublished; v3 sole published/active. SMS tables: none. SMS evidence rows: 0. HTTP in cleaned text: 0. Max cleaned chars: 109983 (not a 240-char display excerpt).

## Frozen export (FlightSim)

Directory: `docs/test-output/i11a0-benchmark/i14-cleaned-export` (gitignored family text).

Exported at `2026-09-27T15:43:44Z`.

| File | SHA-256 |
|------|---------|
| `i11a0_prompt_messages.jsonl` | `fa870c80c758c6bfea0b7c29a8b58fe127db88a9c9cb7d994e2f074eae73ca30` |
| `peggy_related_email.jsonl` | `2e49831a379efb8b29d8782d9549d2e421ce8446e1add5641a468ea949719452` |
| `peggy_only_inventory.jsonl` | `de2f8b176fed2fdd24311ff23c7a51297fe1e91b43e5542cc70995df89e046c0` |
| `peggy_voice_corpus_inventory.jsonl` | `835011eb0d5f93eb3859c8d06bf5b2f8c7e60dda808af6c281c3d7c8c20d3e13` |
| `SOURCE_INSPECTION.json` | `e879b06c695979cbc6bfe594ef4409e33afd514e135d1a6d0809f25ebdf6a327` |

I11A.0 prompt set: 6680 authored_displayable messages in 1655 Peggy-related threads, 2005-12-10 through 2025-11-12, **1,510,894 estimated** evidence tokens (`utf8_bytes_plus_3_div_4`). Peggy-only authored_displayable: 2674 / **815,792 estimated**. Peggy `voice_corpus`: 1345 / **505,756 estimated**. Original bodies were not copied into the prompt files.

Cleaning indicators in the Peggy-related freeze: URLs stripped on 1514 rows; quote contamination flagged 3804; commercial suppress_default 650; forward duplicate omitted 329; commercial body omitted 124; non-displayable 126.

## Founder review items

- Four UUIDs appear in the legacy seven-chunk paste and not as evidence IDs in this Peggy-related I14 freeze: `412635f6-e4d9-5246-8bbe-87b2d99f5615`, `4c50ce28-73f5-446a-919a-5337c477aafb`, `5252bc6e-ccaf-11df-898b-0017a4a78c22`, `5e258d1f-1638-5516-9a2c-f875df741d2e`. Cite-as overlap with evidence UUIDs is otherwise ~0 because legacy labels are not I14 evidence IDs.
- `voice_corpus` (1345) is stricter than all Peggy From `authored_displayable` rows (2674). I11A.0 uses both speakers; I11A.1 later chooses the Peggy subset.
- `quote_contamination_flagged` remains on some stored cleaned rows; I14 still stores `cleaned_authored_text` separately from immutable originals.
