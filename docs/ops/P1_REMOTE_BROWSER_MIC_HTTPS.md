# P1 operational requirement — remote-browser microphone HTTPS

**Status:** Recorded · **Date:** 2026-08-10  
**Discovered during:** Increment 5A Journal voice acceptance (FlightSim)  
**Workstream:** Deployment / ops (D7 topology) — **not** Increment 6 Person & Identity; **not** Increment 7 Video / Review

## Requirement

Remote-browser microphone capture (getUserMedia / MediaRecorder) for MemoryBox thin clients **must** be served from a **trusted secure context** — typically **HTTPS** with a certificate the browser trusts — when the page is **not** `http://127.0.0.1` / `http://localhost`.

Browsers block or restrict mic access on plain `http://<hostname>` from another machine. This blocked FlightSim Journal spoken capture when opened from a non-localhost URL (e.g. `http://flightsim:8790/...`), even when Windows default mic was correct.

## Implications

- Localhost on the FlightSim host remains a valid P1 acceptance path for voice capture.  
- LAN/remote operator browsers need HTTPS (or equivalent trusted secure context) for mic — configure at reverse-proxy / TLS termination, not inside Person & Identity product code.  
- Do **not** expand Increment 6 or Increment 7 to implement TLS unless Tom assigns that work to the ops/deploy track explicitly.

## Related

- [MBBS-001_INCREMENT_5A_ACCEPTANCE.md](../product/MBBS-001_INCREMENT_5A_ACCEPTANCE.md)  
- [MBBS-001_INCREMENT_6_DEFINITION.md](../product/MBBS-001_INCREMENT_6_DEFINITION.md) (explicitly out of I6)  
- [MBBS-001_INCREMENT_7_DEFINITION.md](../product/MBBS-001_INCREMENT_7_DEFINITION.md) (explicitly out of I7)  
- Locked decision **D7** (config-driven hosts; FlightSim runtime)
