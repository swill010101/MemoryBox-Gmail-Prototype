# MBAS-P2-I12 — PoC Retain / Adapt / Replace Matrix

**Status:** **ACCEPTED** 2026-09-04 (Tom: “i12 is accepted”) · Definition **LOCKED** 2026-09-03 · **BUILD AUTHORIZED S1–S5** 2026-09-03  
**PoC branch (read-only):** `origin/cursor/marvin-capture-v01-3344`  
**Current repo partial integration:** `memorybox/guided_capture/` + `007_guided_capture_i11.sql`  
**PRD:** [MBPRD-P2-I12_HISTORIAN_COLLECTION_CAMPAIGNS.md](MBPRD-P2-I12_HISTORIAN_COLLECTION_CAMPAIGNS.md)

---

## Summary

The MarvinCapture PoC (~95% working **email loop** on personal Gmail plus-address) validated transport, correlation, reply extraction, and review UX patterns. **MB integration is far less complete** — I11 `guided_capture` added Postgres campaigns but lacks immutable Capture Items, Review Drafts, verdicts, promotion chain, and dedicated mailbox.

**Strategy:** Selectively reuse proven transport and extraction code behind MB-native interfaces; **replace** PoC SQLite as SoT; **adapt** I11 schema toward [MBDC-P2-I12](MBDC-P2-I12_DOMAIN_MODEL.md).

---

## Matrix

| Area | PoC / current (`marvin_capture` + `guided_capture`) | Decision | Notes |
|------|-----------------------------------------------------|----------|-------|
| **Outbound email transport** | `gmail_client.send_message`, Marvin adapter in `email_adapter.py` | **ADAPT** | Wrap in `HistorianEmailAdapter`; send from `memorybox@marvinbot.net`; preserve outbound raw |
| **Inbound polling/receipt** | Gmail API list queries, `poll_inbound`, label `MemoryBox/GC-Processed` | **ADAPT** | Point at Capture account inbox; update queries for `[MB-HC-` tokens; label name TBD |
| **Correlation** | `[MB-GC-token]` subject + `gc-` plus-address Reply-To | **ADAPT** | MB-native: delivery `correlation_token` + subject tag `[MB-HC-…]`; plus-address **optional**, not required |
| **Attachment preservation** | `mail_store.save_attachments`, multipart walk | **RETAIN** | Move under MemoryBox archive paths; SHA-256 on insert |
| **Raw email preservation** | `save_raw_email`, `.eml` paths in PoC | **RETAIN** | Authoritative `preserved_raw_uri` on Capture Item |
| **Reply-text extraction** | `reply_extract.extract_reply_text`, `refine_gc_reply_text` | **RETAIN** | Derived `extracted_text` only; never overwrite raw |
| **Idempotency** | `gmail_message_id UNIQUE` in SQLite; `inbound_message_id` unique in PG | **RETAIN** | Enforce on `historian_capture_items` |
| **Unmatched holding** | Quarantine list in `poll_and_ingest` return | **ADAPT** | First-class unmatched queue + HC-11 UI |
| **SQLite PoC schema** | `prompt` / `response` / `attachment` | **REPLACE** | Postgres historian model; SQLite read-only for replay import only |
| **Scheduler** | `mem_bank.py` daily send, `tick_scheduler` in guided_capture | **ADAPT** | Per-respondent cadence; running/paused guards |
| **Review UI** | PoC `static/review.html` separate app | **REPLACE** | MB shell HC-* screens; dark theme I10A family |
| **Transcription hooks** | `whisper_client`, voice attachments in PoC/GC | **DEFER** | V1 email-text only; preserve hooks for V2 |
| **Plus-address behavior** | `+MEM`, `+JRN`, `+gc-` routing | **REPLACE** | Not production architecture for I12; reference only |
| **Message deletion/Trash** | PoC `_verify_and_trash` after DB verify | **REPLACE** | Do not Trash inbound; label processed only |
| **Tests and fixtures** | PoC manual; `prove-guided-capture` harness | **ADAPT** | New `prove-historian-capture`; fake adapter pattern retained |
| **Runtime configuration** | `marvin_capture.json`, env examples | **ADAPT** | New `historian_capture` env block; secrets outside Git |
| **Campaign model** | I11 `guided_capture_campaigns` (single respondent) | **ADAPT** | Multi-respondent; question snapshots on delivery |
| **Response model** | `guided_capture_responses` merges source+review | **REPLACE** | Split: Capture Item + Review Draft + Verdict |
| **Credibility** | `set_credibility` on response row | **ADAPT** | Move to `owner_assessments` history table |
| **Promotion** | `resulting_knowledge_json` informal | **REPLACE** | Explicit `promotions` table + Story/Artifact FKs |
| **Ask search** | `search_responses_for_ask` | **ADAPT** | Search promoted/retained per verdict rules |
| **People integration** | `respondent_options` + optional `people_id` on contact | **ADAPT** | Require Person + confirmed route before send |
| **STT / voice channel** | Supported in guided_capture responses | **DEFER** | Out of V1 contributor workflow |
| **Fake adapter** | `FakeGuidedEmailAdapter` | **RETAIN** | Rename to `FakeHistorianEmailAdapter` |
| **Unavailable adapter** | `UnavailableGuidedEmailAdapter` | **RETAIN** | Visible degrade pattern |
| **MEM/JRN daily journal sends** | PoC `send_daily_journal_if_due` | **OUT OF SCOPE** | Not part of I12 historian campaigns |

---

## Code reuse map (files)

| Source (PoC branch) | Target | Action |
|---------------------|--------|--------|
| `application/marvin_capture/gmail_client.py` | `memorybox/historian_capture/gmail_transport.py` (proposed) | Copy/adapt behind interface |
| `application/marvin_capture/reply_extract.py` | `memorybox/historian_capture/reply_extract.py` | Retain logic |
| `application/marvin_capture/mail_store.py` | `memorybox/historian_capture/mail_store.py` | Retain attachment/raw helpers |
| `application/marvin_capture/plus_address.py` | Optional util only | Do not require for V1 send path |
| `application/marvin_capture/db.py` | — | **Do not port** as SoT |
| `application/marvin_capture/static/review.*` | — | **Replace** with MB UI |
| `memorybox/guided_capture/__init__.py` | `memorybox/historian_capture/` | Refactor/evolve |
| `memorybox/guided_capture/email_adapter.py` | `memorybox/historian_capture/email_adapter.py` | Adapt mailbox + token prefix |
| `memorybox/migrations/007_*.sql` | New `008_historian_capture_i12.sql` (proposed) | Additive migration |

---

## Risk notes

1. **“95% working”** = PoC loop on Tom’s Gmail — not MB integration completeness.  
2. **Dual SoT:** Running PoC SQLite alongside Postgres during transition is **forbidden** after I12-S1.  
3. **Credential split:** Capture mailbox ≠ owner personal Gmail — adapter must not default to `MEMORYBOX_GC_USER_EMAIL` owner address for production send.  
4. **Correlation regression:** Changing token prefix requires migration of in-flight deliveries or acceptance-only fresh campaigns.

---

**PLANNING LOCKED 2026-09-03.**
