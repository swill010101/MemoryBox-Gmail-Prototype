# I13 voice pilot evidence inventory

Read-only status as of 2026-09-08 after the overlap / poor-audio voice pilot. Recheck on FlightSim with [inspect-voice-pilot-status.py](inspect-voice-pilot-status.py).

## Stopped admissions

| Admission | Training key | Stale | Role |
|---|---|---|---|
| `1039c733-2149-40b2-b027-97058e032af3` | T1 | **yes** | Original Eugene pilot (retired reference) |
| `9e0a2605-8bfc-4ec7-aa6e-501f9bca7cea` | T2 | no | Tom off-camera positive pilot |
| `46cb1d21-b464-4bc4-bf7c-7d0de0202ca6` | T2 | no | N1 Unknown no-match pilot |
| `f59050d5-cb4b-4ff7-beee-609b28f7af61` | T3-patio | no | Eugene Patio held-out pilot |
| `66fb93af-92a9-4ef1-b3e6-c0f700e89276` | R1-gs2-fresh | no | Eugene reprocessing lifecycle pilot |
| `339b3a14-5069-4554-846f-dc84d6745c00` | T-gs2-reuse | no | Overlap / poor-audio Eugene pilot |
| `f9aa45bc-d5b1-4608-bca1-61cfe9993aeb` | T3-patio | no | Stopped Patio failure admission (do not retry) |

## Owner annotations added this session

| Key | Annotation | Source | Interval | Role |
|---|---|---|---|---|
| R1-gs2-fresh | `3eb88a19…` | `vid-34df63e61b949890` | 00:26.30–00:34.78 | Lifecycle training |
| H1-gs2-held-out | `5d87a6ac…` | `vid-34df63e61b949890` | 01:26.42–01:45.44 | Lifecycle held-out |

Playable copy for `vid-34df63e61b949890` published to `browser_proxies/7cb205f4b99419be11e3d3f5.mp4`.

## Overlap / poor-audio pilot (completed 2026-09-08)

Admission `339b3a14-5069-4554-846f-dc84d6745c00` used T-gs2-reuse training and three held-outs. E2 overlap Eugene match `0.584`; O2 off-camera Tom no-match `0.093`; N1 TV announcer no-match `-0.020`. See [overlap-poor-audio-voice-pilot-report.json](overlap-poor-audio-voice-pilot-report.json). Do not retry.

## Remaining voice gaps (no run authorized)

1. **Q1 listening-only** — no saved annotation; excluded from evidence.
2. **U1 remainder** — unreviewed portion of prior Eugene interval.
3. **Face/voice corroboration** — separate acceptance matrix.
4. **Generalized accuracy** — not claimed by any pilot (E2 is interval-specific on 1532 only).
5. **Gate 4 archive unlock** — **deferred** 2026-09-08 (Outcome A); resume after acceptance prerequisites — see [GATE-4-DECISION-PRD.md](GATE-4-DECISION-PRD.md).

See [POST-PILOT-VOICE-GAP-PLAN.md](POST-PILOT-VOICE-GAP-PLAN.md).
