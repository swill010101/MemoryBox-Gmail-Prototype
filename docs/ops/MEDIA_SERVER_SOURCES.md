# MemoryBox Sources on media-server

Canonical share root (photos volume):

`\\media-server\photos\MemoryBox\Sources`

Also available as mapped `P:\MemoryBox\Sources` on machines that map `\\media-server\photos`.

## Layout

```text
MemoryBox/Sources/
  email/       Gmail mbox export (immutable copy)
  calendar/    Takeout calendar zip + extracted ics/
  sms/         iMessage/SMS CSV export (immutable copy)
  MANIFEST.json
```

## Rules

- These are **authoritative originals for ingest** (referenced mode). Do not edit in place.
- MemoryBox / FlightSim must **read** via UNC or mapped drive; never rewrite these files.
- Working slices (optional) may live under FlightSim `working/smoke/` — never commit family content to Git.
- SMS is stored here for P1 readiness; **SMS ingest remains deferred** (Increment 3 deferred scope).

## FlightSim configuration

```powershell
$env:MEMORYBOX_SMOKE_MBOX_URI = "\\media-server\photos\MemoryBox\Sources\email\All mail Including Spam and Trash-002.mbox"
$env:MEMORYBOX_SMOKE_ICS_URI = "\\media-server\photos\MemoryBox\Sources\calendar\ics\swill01@gmail.com.ics"
$env:MEMORYBOX_SMOKE_LIMIT = "5"
```

Use `prepare_smoke_slices.py` only if you need a local working copy; prefer reading Sources with `--limit` / smoke limit.

Env template: [`config/memorybox_sources.env.example`](../../config/memorybox_sources.env.example)  
Checkpoint: [`MBBS-001_MEDIA_SERVER_SOURCES_CHECKPOINT.md`](../product/MBBS-001_MEDIA_SERVER_SOURCES_CHECKPOINT.md)
