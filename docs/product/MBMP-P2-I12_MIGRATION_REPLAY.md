# MBMP-P2-I12 — Migration and Replay Proposal

**Status:** **ACCEPTED** 2026-09-04 (Tom: “i12 is accepted”) · Definition **LOCKED** 2026-09-03 · **BUILD AUTHORIZED S1–S5** 2026-09-03  
**Domain:** [MBDC-P2-I12_DOMAIN_MODEL.md](MBDC-P2-I12_DOMAIN_MODEL.md)  
**PoC matrix:** [MBAS-P2-I12_POC_REUSE_MATRIX.md](MBAS-P2-I12_POC_REUSE_MATRIX.md)

---

## 1. Principles

1. **Preserve old data** — never destroy or rewrite PoC SQLite, raw `.eml` files, or existing `guided_capture_*` rows.  
2. **No second source of truth** — after cutover, only Postgres historian model is authoritative for campaigns/capture/review.  
3. **Idempotent import** — replay keyed on `inbound_message_id`, `outbound_message_id`, `correlation_token`.  
4. **Provenance mapping** — every imported row records `import_source`, `imported_at`, original ids.  
5. **Rollback** — import is additive; rollback = disable imported rows via flag, not delete raw evidence.

---

## 2. Sources

| Source | Location | Records |
|--------|----------|---------|
| Marvin PoC SQLite | FlightSim/desktop PoC `marvin_capture.db` | `prompt`, `response`, `attachment` |
| I11 guided capture | MemoryBox Postgres `guided_capture_*` | Campaigns, deliveries, responses |
| Raw mail archive | PoC mail dirs, `.memorybox_gc_mail` | `.eml` files |

---

## 3. Target mapping

### 3.1 PoC SQLite → historian model

| SQLite | Historian entity | Rules |
|--------|------------------|-------|
| `prompt` (MEM) | Not auto-imported as campaign | MEM/JRN prompts are different product; **manual review** |
| `response` | `historian_capture_items` | Map if `gmail_message_id` present; link to synthetic delivery if needed |
| `response.response_text` | `extracted_text` | Immutable |
| `response.raw_email_path` | `preserved_raw_uri` | Copy to MB archive if path still valid |
| `attachment` | `historian_capture_attachments` | Copy binaries + sha256 |
| `reviewed` flag | `verdict` = `retained` if reviewed | Assessment = `not_rated` unless manually set |

### 3.2 `guided_capture_*` → historian model

| Current | Target | Rules |
|---------|--------|-------|
| `guided_capture_campaigns` | `historian_capture_campaigns` | 1:1 id preserve optional |
| `guided_capture_contacts` | `campaign_respondents` | Require `people_id`; skip if null with quarantine report |
| `guided_capture_deliveries` | `historian_capture_deliveries` | Add `question_snapshot_text` from question at import time |
| `guided_capture_responses` | `capture_items` + `review_drafts` v1 | Split `extracted_text`/`transcript_text` |
| `credibility` | `owner_assessments` initial row | |
| `resulting_knowledge_json` | `promotions` | Parse if Story ids present |

---

## 4. Import procedure (when authorized)

```text
1. Freeze PoC writes (read-only SQLite)
2. Run `memorybox import-historian-capture --dry-run`
   → report: would_import, skipped, unmatched, conflicts
3. Tom approves report
4. Run `memorybox import-historian-capture --apply`
   → transactional batches per campaign
5. Verify: prove-historian-capture --slice s1 on imported fixture
6. Mark PoC DB read-only archive (file note, not delete)
```

**Idempotency:** second run skips rows where `inbound_message_id` or `correlation_token` already exists.

---

## 5. Rollback and recovery

| Scenario | Recovery |
|----------|----------|
| Bad import batch | Set `provenance_json.import_revoked=true` on affected rows; exclude from UI/Ask |
| Wrong person link | Owner re-links in HC-11; audit log |
| Missing raw file | Keep DB row; flag `raw_missing`; do not fabricate body |
| Schema migration failure | Restore PG backup; PoC data untouched |

---

## 6. Is PoC data required for V1 acceptance?

**No.**

FlightSim acceptance ([MBAT-P2-I12](MBAT-P2-I12_ACCEPTANCE.md)) uses a **fresh campaign** with real mailbox send/receive. PoC replay is **optional** for migration confidence and historical continuity, not a gate.

**Recommendation:** Schedule replay as post-S4 housekeeping if Tom wants Peggy/MEM historical rows in MB; otherwise archive PoC as read-only reference.

---

## 7. `guided_capture` deprecation path

| Phase | Action |
|-------|--------|
| I12-S1 | New tables alongside existing; feature flag `HISTORIAN_CAPTURE_V1` |
| I12-S4 | UI reads new model only; migrate in-flight GC campaigns or freeze |
| Post-accept | One-way import script; deprecate `prove-guided-capture` → alias `prove-historian-capture` |
| Later | Drop `guided_capture_*` tables only after Tom confirms empty + backup |

---

## 8. What this planning commit does not do

- No migration scripts executed  
- No PoC data modified  
- No SQLite files touched  

---

**PLANNING LOCKED 2026-09-03.**
