# I13 voice pilot evidence inventory

Read-only status as of 2026-09-08 after the Eugene reprocessing lifecycle run. Recheck on FlightSim with [inspect-voice-pilot-status.py](inspect-voice-pilot-status.py).

## Stopped admissions

| Admission | Training key | Stale | Role |
|---|---|---|---|
| `1039c733-2149-40b2-b027-97058e032af3` | T1 | **yes** | Original Eugene pilot (retired reference) |
| `9e0a2605-8bfc-4ec7-aa6e-501f9bca7cea` | T2 | no | Tom off-camera positive pilot |
| `46cb1d21-b464-4bc4-bf7c-7d0de0202ca6` | T2 | no | N1 Unknown no-match pilot |
| `f59050d5-cb4b-4ff7-beee-609b28f7af61` | T3-patio | no | Eugene Patio held-out pilot |
| `66fb93af-92a9-4ef1-b3e6-c0f700e89276` | R1-gs2-fresh | no | Eugene reprocessing lifecycle pilot |
| `f9aa45bc-d5b1-4608-bca1-61cfe9993aeb` | T3-patio | no | Stopped Patio failure admission (do not retry) |

## Owner annotations added this session

| Key | Annotation | Source | Interval | Role |
|---|---|---|---|---|
| R1-gs2-fresh | `3eb88a19…` | `vid-34df63e61b949890` | 00:26.30–00:34.78 | Lifecycle training |
| H1-gs2-held-out | `5d87a6ac…` | `vid-34df63e61b949890` | 01:26.42–01:45.44 | Lifecycle held-out |

Playable copy for `vid-34df63e61b949890` published to `browser_proxies/7cb205f4b99419be11e3d3f5.mp4`.

## Remaining voice gaps (no run authorized)

1. **Overlap / poor-audio** — Q1 listening-only; U1 remainder unreviewed; `vid-c57dbd21f993f6d1` excluded from Eugene evidence.
2. **Face/voice corroboration** — separate acceptance matrix.
3. **Generalized accuracy** — not claimed by any pilot.
4. **Gate 3 bounded processing** — founder decision pending; see [GATE-3-DECISION-PRD.md](GATE-3-DECISION-PRD.md).
5. **Gate 4 archive unlock** — separate founder decision.

See [POST-PILOT-VOICE-GAP-PLAN.md](POST-PILOT-VOICE-GAP-PLAN.md).
