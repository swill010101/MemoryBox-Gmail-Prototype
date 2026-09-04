# MBUX Historian Capture Screens (Accepted Implementation)

**Status:** **ACCEPTED** 2026-09-04 — shipped product UI  
**Implementation:** `memorybox/historian_capture/static/historian_capture.html`  
**Route:** `/historian-capture/ui`  
**UX sign-off:** [I12_UX_SIGNOFF_20260904.md](../../../product/I12_UX_SIGNOFF_20260904.md)

---

## Important distinction

| Source | Authority | Notes |
|--------|-----------|-------|
| **This folder** | **Accepted implemented screens** | Sanitized static references of the shipped MB-dark UI |
| `codex/historian-capture-reference-screens-20260829` @ `fe913a4` | **Reference only** | August 22 layout mockups; **not** product spec |
| `memorybox/historian_capture/static/historian_capture.html` | **Live implementation** | Authoritative behavior; these HTML refs are snapshots |

All names, emails, and story text in this folder are **synthetic** (fake data).

---

## Screen inventory

| File | Screen | Contract |
|------|--------|----------|
| [01_hc_dashboard_needs_review.html](01_hc_dashboard_needs_review.html) | Dashboard — Needs review tab | HC-01, HC-06 |
| [02_hc_campaign_detail.html](02_hc_campaign_detail.html) | Campaign detail dashboard | HC-05 |
| [03_hc_review_screen.html](03_hc_review_screen.html) | Capture item review | HC-07, HC-08, HC-09 |
| [04_hc_new_campaign.html](04_hc_new_campaign.html) | New campaign form | HC-02, HC-03, HC-04 |

Open any `.html` file in a browser to view the sanitized layout reference (self-contained; no server required).

---

## Accepted visual rules

- Dark page background `#0f141c`
- Card/panel background `#1a2230`
- Primary text `#e8edf5`; muted `#9aa3b5`
- Primary action blue `#3b82f6`
- Status badges: Draft (orange), In progress (blue), Saved (green)
- Canonical MemoryBox header with Review & Learn active
- No engineering/admin controls visible

---

## Live UI vs static reference

Static HTML files preserve **layout and copy patterns** at acceptance time. For interactive behavior (poll, verdict save, promotion), use the running app:

```bash
MEMORYBOX_HC_EMAIL_PROVIDER=fake python -m memorybox serve
# http://127.0.0.1:8790/historian-capture/ui
```
