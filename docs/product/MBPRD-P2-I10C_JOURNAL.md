# MBPRD-P2-I10C — Journal

**Status:** **ACCEPTED** 2026-08-24 (Tom: “i10C - journal is accepted”) · PRD **LOCKED** · built 2026-08-24  
**Definition:** [MBBS-P2_INCREMENT_10C_DEFINITION.md](MBBS-P2_INCREMENT_10C_DEFINITION.md)  
**Field map:** [MBAS-P2-I10C_ASSESSMENT_RECONCILIATION.md](MBAS-P2-I10C_ASSESSMENT_RECONCILIATION.md)  
**Acceptance:** [MBAT-P2-I10C_ACCEPTANCE.md](MBAT-P2-I10C_ACCEPTANCE.md) · `python -m memorybox prove-i10c`  
**Visuals:** `docs/source/Screens/MBUX Journal Screens/`  
**Does not start:** I11 · HVRT journal ingest · Mine / Family contributions · I10A.2 reopen · guided capture (I15)

Pixels lose to Frozen rows. Journal screens are complete; do not redesign unless a contract defect appears.

---

## Frozen (from founder lock)

1. Working drafts **IN**. Save draft out of Ask. Save journal creates/advances the saved version; Ask-eligible subject to visibility. Edit-saved uses a draft; Ask keeps last saved until Save journal.
2. One Entry date + optional described time. No range UI. Keep start/end columns for import/future. Preserve precision; no fake day. `captured_at` ≠ Entry date ≠ described time. New Entry date defaults to **today**, editable.
3. Calendar + On this day **IN** for **saved** Entry dates only. Drafts excluded.
4. HVRT ingest **OUT**.
5. Title optional. Body required to Save journal. Untitled = first meaningful body line, never “Untitled Journal.”
6. No tag taxonomy. People pills and real linked-object indicators only.
7. Panel: **All entries only.** People/time may filter that list. No Mine. No Family contributions.
8. Speech = I10A.2 authored-memory on Entry body only.
9. Author = owner Person. Visibility private | shared_with_family. Place = places.id. Soft-remove. History read-only. Journal→Journal memories out.

---

## Success

Panel / New / Detail / Edit on `/journal/ui`. Continue writing for never-saved drafts (no Drafts tab). Ask + calendar + On this day see saved only. `prove-journal` (5A) stays green. `prove-i10c` covers the definition prove list.

---

**ACCEPTED 2026-08-24.** Do not reopen Journal screens unless a contract defect appears. Next is I11.
