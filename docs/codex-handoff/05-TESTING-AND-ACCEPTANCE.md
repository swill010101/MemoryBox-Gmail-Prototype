# Testing and Acceptance

## I12 prove command

```bash
python -m memorybox migrate
MEMORYBOX_HC_EMAIL_PROVIDER=fake python -m memorybox prove-historian-capture [--slice s1|s2|s3|s4|s5] [--flightsim]
```

## Slice matrix

| Slice | Focus | Key criteria |
|-------|-------|--------------|
| **s1** | Campaign lifecycle, send, reminder → no_response | C-01..C-04, C-12, C-17..C-19 |
| **s2** | Inbound correlate, duplicate, quarantine, STOP | C-05, C-06, C-13, C-14, C-20 |
| **s3** | Review draft, assessment, verdict | C-07, C-08, C-09 |
| **s4** | Story promotion, Ask attribution, thank-you | C-10, C-11, C-21 |
| **s5** | Full harness + artifact + unmatched integration | A-01..A-12 mapping |

## Sanitized prove artifacts (committed)

Fake-adapter runs on integration commit `9f0d7dc`:

| File | Result |
|------|--------|
| `docs/test-output/historian-capture/prove-fake-s1-20260904.json` | `ok: true` |
| `docs/test-output/historian-capture/prove-fake-s2-20260904.json` | `ok: true` |
| `docs/test-output/historian-capture/prove-fake-s3-20260904.json` | `ok: true` |
| `docs/test-output/historian-capture/prove-fake-s4-20260904.json` | `ok: true` |
| `docs/test-output/historian-capture/prove-fake-s5-20260904.json` | `ok: true` |

These use synthetic `respondent-*@example.test` addresses — no PII.

## FlightSim live acceptance (Tom, 2026-09-04)

Tom accepted I12 on FlightSim with live Gmail channel. Material checks:

- Real campaign created for MB Person with multiple questions
- Outbound via `memorybox@marvinbot.net` channel / Gmail API transport
- Inbound reply correlated and visible in campaign after poll fix
- MB-dark UI reviewed and corrected per UX sign-off doc
- `prove-historian-capture --flightsim` exercised (Stage 2/3)

**Live prove JSON not committed** (would contain account metadata). Re-run on FlightSim to regenerate if needed.

## Regression suite (keep green)

Per [MBAT-P2-I12](../product/MBAT-P2-I12_ACCEPTANCE.md) §2.3:

- `prove-i10a`, `prove-i10b`, `prove-i10c`, `prove-journal`
- `prove-guided-capture` (until deprecated)
- `prove-i11` / `prove-i11a` smoke where applicable

## UI manual acceptance

See [I12_UX_SIGNOFF_20260904](../product/I12_UX_SIGNOFF_20260904.md) and screen refs in `docs/source/Screens/MBUX Historian Capture Screens/`.

## Environment for prove

| Variable | Fake prove | Live FlightSim |
|----------|------------|----------------|
| `MEMORYBOX_HC_EMAIL_PROVIDER` | `fake` | `auto` |
| `MEMORYBOX_DATABASE_URL` | required | required |
| `MEMORYBOX_HC_GMAIL_CREDENTIALS` | not needed | required (local file) |
| `MEMORYBOX_HC_GMAIL_TOKEN` | not needed | required (local file) |
| `application/marvin_capture/` | not needed | required on PYTHONPATH |
