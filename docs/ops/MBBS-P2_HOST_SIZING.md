# MBBS-P2 — Combined host sizing (floor vs buy)

**Status:** Owner recommendation · **Date:** 2026-08-17  
**Owner:** Tom  
**Scope:** One Windows box running MemoryBox + Immich + Docker (Postgres, Qdrant) + Ollama + video worker  
**Not:** I14 Settings · not a product increment · not an ACCEPTED gate  

**Archive guide (this recommendation):** ~51k photos · ~1k videos · ~94k email · ~90k SMS  

**Related:** Immich lives on **local disk** on this host (not UNC `\\media-server\…`). After the box is up: point `config/immich.env` at localhost, then **I4 §8.1 is the first owner pass** ([I4 definition](../product/MBBS-P2_INCREMENT_4_DEFINITION.md)).

---

## Verdict

Buy a **2023–2025 8+ core** machine with **64 GB RAM** and a **1 TB NVMe** for the running stack. Put **source archives and video originals** on the **10 TB USB**. Do not size this like the i7-6700 media-server.

| | **Floor (will run)** | **Buy / run this** | **Skip** |
|---|---|---|---|
| **CPU** | 8 cores / 16 threads, **Intel 12th gen or AMD 5000** or newer | **AMD Ryzen 7 7700 / 8700G** or **Intel Core Ultra 7 / 14th-gen i7 (14700-class)** | 4-core Skylake/Kaby (6700, 7700K) |
| **Chip generation** | 2022+ | **2023–2025** Zen 4 / Raptor Lake Refresh / Core Ultra | Pre-11th Intel as the Immich+Docker host |
| **RAM** | **32 GB** DDR5 | **64 GB** | 16 GB |
| **GPU** | iGPU only (CPU faces + small LLM) | **RTX 4060 8 GB** (4070 12 GB if you want headroom) | No need for a 4090 |
| **Main disk** | 1 TB NVMe | **1 TB NVMe Gen4** | SATA SSD as the Docker/Immich disk |
| **10 TB USB** | Sources only | Powered USB 3.2 (or Thunderbolt enclosure). HDD is fine for archives | Immich library, Postgres, Qdrant, or models on that stick |

**llama3.2 + nomic-embed-text** (current MemoryBox wiring) is a small local model. **32 GB** is enough for that. **64 GB** is so Immich ML + Docker Desktop + Chrome Explore + Windows are not fighting. Residual MBQL does not need a 70B box.

---

## Why this size

Steady state on one Windows host:

- Docker Desktop + Postgres + Qdrant: a few GB; hates a starving machine  
- Immich (API, Postgres, Redis, ML): another few GB; **face jobs** want CPU cores or CUDA  
- MemoryBox + video worker: ~1–2 GB  
- Ollama 8B Q4: ~5–8 GB when chat/embed actually runs  
- Explore in Chrome: not free  

**32 GB** = comfortable for *this* model set and archive. **64 GB** = stop thinking about RAM. **16 GB** = media-server failure mode (thrash, then “Immich died”).

CPU: Immich machine-learning and HVRT/video are **core-count** problems. **8c/16t is the floor**; 12c (14700 / 7700) is the sweet spot. Generation matters for iGPU, USB, and not repeating ACPI/XTU-era boards.

GPU: optional. It is the upgrade that makes the **first Immich face pass** and **local chat** stop feeling like a batch job. **8 GB VRAM** is enough for Immich CUDA + llama 8B. Without a GPU, still viable; budget an overnight face run on CPU.

---

## 1 TB SSD vs 10 TB USB

### On the 1 TB NVMe (hot)

- Windows  
- Docker volumes (MemoryBox Postgres, Qdrant, Immich’s **own** DB/Redis)  
- Immich **thumbs** + (if it fits) **photo** library  
- Ollama models  
- `C:\memorybox`

Rough photo math: 51k × ~5 MB JPEG ≈ **250 GB**. Add thumbs, databases, Docker images, Windows, models → **~500–700 GB**. 1 TB works for **photos + stack**. It does **not** also hold **1k videos** if those are 1–2 GB each.

### On the 10 TB USB (cold)

- mbox / SMS exports / attachment dumps  
- Original photo ingest bags  
- **Video masters**  
- Anything you can lose for a day if the cable wiggles  

**Do not** put Immich’s live library, Postgres, or Qdrant on USB. Disconnects and 100–200 MB/s HDDs look like “Immich died.” If videos must be in Immich, prefer an **internal** second disk (even a cheap 4–8 TB SATA) over USB. An Immich **external library** pointed at USB is the least-bad USB option. Running the whole Immich data directory from USB is the worst.

Config split (already the product model):

- Hot paths: `config/immich.env`, `config/memorybox_app.env`, Docker volumes on NVMe  
- Cold paths: `config/memorybox_sources.env` → 10 TB USB  

---

## One box vs two boxes

For this product, **one solid host** with Immich on **local NVMe** is the target. The old split (MemoryBox on FlightSim, Immich on media-server) was a reliability tax, not an architecture win.

Keep the 10 TB as **Sources**, not as the database disk.

---

## Short buy line

**Ryzen 7 7700 or Intel 14700-class, 64 GB DDR5, 1 TB NVMe Gen4, optional RTX 4060 8 GB, 10 TB USB for sources/video originals only.**

32 GB / no GPU still works if you stay on llama3.2 and accept slow Immich ML. Do not go below **8 cores** or **32 GB** if Immich lives on this box.

---

## After the machine is up

1. Immich app + library on **local NVMe** (not UNC).  
2. `config/immich.env`: `IMMICH_BASE_URL` → localhost; thumbs path local; thumbs API off unless needed.  
3. Restart Ask/serve.  
4. **I4 §8 + §8.1 owner pass** — must actually work. **MBQL-001 is ACCEPTED** (2026-08-18). Do not skip I4 for I8.
