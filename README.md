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
- **P2-I1 definition (ACCEPTED 2026-08-13):** [docs/product/MBBS-P2_INCREMENT_1_DEFINITION.md](docs/product/MBBS-P2_INCREMENT_1_DEFINITION.md)
- **P2-I2 definition (ACCEPTED 2026-08-13):** [docs/product/MBBS-P2_INCREMENT_2_DEFINITION.md](docs/product/MBBS-P2_INCREMENT_2_DEFINITION.md)
- **P2-I3 definition (ACCEPTED 2026-08-13):** [docs/product/MBBS-P2_INCREMENT_3_DEFINITION.md](docs/product/MBBS-P2_INCREMENT_3_DEFINITION.md)
- **P2-I4 definition (DRAFT — awaiting approval; governed by MBUX-001 v0.4):** [docs/product/MBBS-P2_INCREMENT_4_DEFINITION.md](docs/product/MBBS-P2_INCREMENT_4_DEFINITION.md)
- **MBUX-001 v0.4 I4 addendum:** [docs/product/MBUX-001_v0.4_I4_MIXED_MEDIA_EXPLORATION_ADDENDUM.md](docs/product/MBUX-001_v0.4_I4_MIXED_MEDIA_EXPLORATION_ADDENDUM.md)
- Approved roadmap: [docs/product/MBRM-001A_P2_IMPLEMENTATION_PLAN_PROPOSAL.md](docs/product/MBRM-001A_P2_IMPLEMENTATION_PLAN_PROPOSAL.md)

**Prove harness:** `python -m memorybox migrate && python -m memorybox prove-p2-i1` · `prove-p2-i2` · `prove-p2-i3`  
**FlightSim ACCEPTED (I1):** real Immich + real HVRT only (fakes fail):

```powershell
$env:MEMORYBOX_P1_RUNTIME_HOST = "1"
$env:MEMORYBOX_PHOTO_PROVIDER = "immich"
$env:MEMORYBOX_VIDEO_PROVIDER = "hvrt"
# MEMORYBOX_VIDEO_WORKER_URL + immich.env already configured on FlightSim
$env:MEMORYBOX_P2_I1_PERSON_NAME = "Peggy"   # optional; default Peggy
$env:MEMORYBOX_P2_I1_POSITIVE_VIDEO_ID = "<hvrt-video-id-with-peggy>"
$env:MEMORYBOX_P2_I1_NEGATIVE_VIDEO_ID = "<hvrt-video-id-without-peggy>"
$env:MEMORYBOX_P2_I1_HVRT_FACE_ID = "<hvrt-face-id>"  # or teach via Review first
python -m memorybox prove-p2-i1 --flightsim
```

**FlightSim ACCEPTED (I2):** serve on `:8790` (or `MEMORYBOX_BASE_URL`), then:

```powershell
$env:MEMORYBOX_P1_RUNTIME_HOST = "1"
python -m memorybox prove-p2-i2 --flightsim
```

## UI mockups

Experience / walkthrough / prototype screens from earlier agent work live in [`mockups/`](mockups/README.md) (start at [`mockups/index.html`](mockups/index.html)).
