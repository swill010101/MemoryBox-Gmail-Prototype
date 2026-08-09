# Media-Server Sources checkpoint

**Date:** 2026-08-09  
**Status:** **PASSED**  
**Scope:** Establish `MemoryBox\Sources` on media-server; copy/verify email, calendar, SMS exports; configure FlightSim paths; small email/calendar ingest from those paths; confirm originals unchanged.  
**Not in scope:** Increment 4, Ask/UX, SMS ingest, photo library moves.

---

## Verdict

**PASSED.** Sources tree is on media-server; copies hash-verified; small email + calendar ingest from Sources paths succeeded; Source files unchanged after ingest. SMS is staged only (ingest still deferred).

---

## Layout created

Root: `\\media-server\photos\MemoryBox\Sources` (also `P:\MemoryBox\Sources` where `P:` maps to that share)

| Relative path | Role | Verify |
|---------------|------|--------|
| `email/All mail Including Spam and Trash-002.mbox` | Gmail export | SHA256 match desktop archive; 19,716,121,563 bytes |
| `calendar/takeout-20260724T122934Z-2-001.zip` | Calendar Takeout zip | SHA256 match |
| `calendar/ics/*.ics` (5 files) | Extracted from zip | Present; primary ICS used for smoke |
| `sms/Messages - 1085 chat sessions.csv` | iMessage/SMS export | SHA256 match |
| `MANIFEST.json` | Sizes/hashes/rules | Written |

Email mbox SHA256: `6B0F009CB1C63CB203D483F0B93506656DA131D225D1F5E79F0B59EFD4A299BB`  
(Desktop archive re-hashed after robocopy: **UNCHANGED=True**.)

---

## FlightSim configuration

Template: [`config/memorybox_sources.env.example`](../../config/memorybox_sources.env.example)  
Ops notes: [`docs/ops/MEDIA_SERVER_SOURCES.md`](../ops/MEDIA_SERVER_SOURCES.md)

On FlightSim (session env):

```powershell
$env:MEMORYBOX_SMOKE_MBOX_URI = "\\media-server\photos\MemoryBox\Sources\email\All mail Including Spam and Trash-002.mbox"
$env:MEMORYBOX_SMOKE_ICS_URI = "\\media-server\photos\MemoryBox\Sources\calendar\ics\swill01@gmail.com.ics"
$env:MEMORYBOX_SMOKE_LIMIT = "5"
```

Ensure FlightSim can resolve/reach `\\media-server\photos` (same share as photos). Do not copy media libraries onto FlightSim.

---

## Ingest from Sources (proved)

Ran `ingest-email` / `ingest-calendar` with `--limit 5` against **P:\MemoryBox\Sources\...** (media-server paths).

| Channel | Result | Notes |
|---------|--------|-------|
| Email | ok; 5 evidence ids (0 inserted / 5 skipped idempotent) | Length + LastWriteTimeUtc **unchanged** |
| Calendar | ok; 5 evidence ids (0 inserted / 5 skipped idempotent) | Length + LastWriteTimeUtc **unchanged** |

Idempotent skips expected after prior FlightSim smoke of the same content hashes.

---

## Stop

Checkpoint complete. **Do not begin Increment 4** without authorization. SMS remains deferred for ingest.
