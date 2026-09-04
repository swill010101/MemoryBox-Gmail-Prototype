# Decision Log (Codex Handoff)

## 2026-09-04 — P2-I12 ACCEPTED

- **Decision:** Tom accepted Historian Collection & Campaigns V1 on FlightSim.
- **Tag:** `increment-12-accepted` on `9f0d7dc`
- **Authority:** [MBBS-P2_INCREMENT_12](../product/MBBS-P2_INCREMENT_12_DEFINITION.md), [MBRM-001B](../product/MBRM-001B_P2_HISTORIAN_COLLECTION_AND_CAMPAIGNS.md)

## 2026-09-04 — Cursor → Codex transition

- **Decision:** End Cursor development; preserve product knowledge in Git for OpenAI Codex in VS Code.
- **Branch:** `transition/p2-i12-codex-handoff` (docs only; no app behavior changes)
- **Constraint:** Do not merge to `main`.

## 2026-09-03 — I12 build authorized S1–S5

- **Decision:** Founder authorized full slice build after planning package review.
- **Prove:** `python -m memorybox prove-historian-capture`

## Email architecture (locked)

| Decision | Detail |
|----------|--------|
| Capture channel | `memorybox@marvinbot.net` |
| Transport | Gmail API via OAuth (often personal Gmail hosting the channel) |
| Correlation | `[MB-HC-token]` + `+hc-token` plus-address |
| Inbound handling | Label `MemoryBox/HC-Processed`; never Trash |
| UI disclosure | Banner shows capture channel vs transport when different |

## UX decisions (2026-09-04 acceptance review)

Full detail: [I12_UX_SIGNOFF_20260904](../product/I12_UX_SIGNOFF_20260904.md)

Summary:

- MB-dark surfaces only — no white admin panels
- Canonical MB header/navigation; no HC-## IDs in product UI
- Person dropdown with search; starter questions button
- Follow-up in **days** (default 7), not hours
- Campaign dashboard with metrics, settings, question progress, replies
- Safe "Send next question now" (blocked while waiting for reply)
- Inline messages beside action buttons
- Thank-you modal with optional personal note
- Download original email as `.txt` not `.eml`
- Auto inbound poll on dashboard/campaign open

## Inbound poll fix (2026-09-04)

- **Problem:** Replies sat in Gmail; UI never called `poll_and_ingest`.
- **Fix:** `tick_scheduler` polls at start; UI `syncInbox()` on boot and campaign open.
- **Commit:** `85baea2` (included in integration line via merge)

## `application/marvin_capture/` (deferred decision)

- **Fact:** I12 imports `plus_address`, `reply_extract`, `gmail_client` from PoC package.
- **Fact:** Package exists on `cursor/marvin-capture-v01-3344` @ `fe913a4`, not on I12 integration line.
- **Fact:** Fake adapter + inline fallbacks allow prove/CI without PoC package.
- **Fact:** Live FlightSim requires PoC checkout or PYTHONPATH addition.
- **Decision:** Document only in this transition; **no vendor/merge yet**.

## Post-I12 sequence (2026-09-03)

- **Authority:** [MBRM-001C](../product/MBRM-001C_P2_POST_I12_ROADMAP.md)
- **Next:** P2-I13 Video/Face/STT/Voice revalidation (not authorized to build)

## Reference mockups vs accepted UI

- **Reference:** `codex/historian-capture-reference-screens-20260829` @ `fe913a4` — layout inspiration only
- **Accepted:** Shipped `historian_capture.html` with MBUX-001 dark theme — see `docs/source/Screens/MBUX Historian Capture Screens/`
