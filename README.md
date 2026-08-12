# Memory Box Prototype

## Purpose

Memory Box reconstructs personal memories using locally controlled,
source-grounded evidence including:

- Email
- Calendar
- Contacts
- Photographs
- Video
- Music history and playlists

## Evidence Principles

1. Answers must be grounded in retrieved evidence.
2. Supporting sources must be identifiable.
3. Confidence must be stated.
4. Assumptions and inferences must be labeled.
5. Missing and contradictory evidence must be disclosed.
6. Original source archives must remain unchanged.
7. Human identity confirmation overrides automated matching.

## Initial Prototype

MBX-P-001 — Gmail Memory Prototype

Host:
FlightSim / AI computer

Root:
C:\MemoryBox

## Git / Takeout sync

Takeout zips sync FlightSim → GitHub → Toms-Desktop via **Git LFS**.

See [docs/GIT_SYNC.md](docs/GIT_SYNC.md) and [docs/ARCHIVE_LAYOUT.md](docs/ARCHIVE_LAYOUT.md).

## P2 planning (no build)

- Locked specs: [docs/source/README.md](docs/source/README.md)
- Approved planning direction: [docs/product/MBRM-001A_P2_IMPLEMENTATION_PLAN_PROPOSAL.md](docs/product/MBRM-001A_P2_IMPLEMENTATION_PLAN_PROPOSAL.md)
- **P2-I1 definition (LOCKED, build authorized):** [docs/product/MBBS-P2_INCREMENT_1_DEFINITION.md](docs/product/MBBS-P2_INCREMENT_1_DEFINITION.md)
- Approved roadmap: [docs/product/MBRM-001A_P2_IMPLEMENTATION_PLAN_PROPOSAL.md](docs/product/MBRM-001A_P2_IMPLEMENTATION_PLAN_PROPOSAL.md)

**Prove harness:** `python -m memorybox migrate && python -m memorybox prove-p2-i1`  
**FlightSim:** `prove-p2-i1 --flightsim` with `MEMORYBOX_P1_RUNTIME_HOST=1` + real Immich/HVRT.

## UI mockups

Experience / walkthrough / prototype screens from earlier agent work live in [`mockups/`](mockups/README.md) (start at [`mockups/index.html`](mockups/index.html)).
