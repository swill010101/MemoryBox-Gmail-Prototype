# P2-I4 DEMO → REAL gap assessment (concise)

**Date:** 2026-08-13 · **Before live wiring** · Interaction reference unchanged  
**Full inventory:** [MBBS-P2_I4_DEMO_ELEMENT_INVENTORY.md](MBBS-P2_I4_DEMO_ELEMENT_INVENTORY.md)

| Element | Class |
|---------|-------|
| Shared Explore client state (filters, range, playhead, density, modal restore) | **1 already real** (client) |
| Ask/query/context → Explore membership | **2 backend exists; not connected** (`POST /ask`) |
| Curator summary | **2** (Ask answer_text/counts) / fixture today |
| Mixed-media Gallery membership | **2** (Ask+Library) / fixture today |
| Filters / density / scrub / Reset / undated rules | **1** client; need live dated membership |
| Timeline extent from real dates | **2** |
| Photo evidence + thumbs | **2** (`/library/media/photo/...`) |
| I1 video appearance moments + jump `t=` | **2** / **3** (Ask video_hits + Review) |
| Email/text when ingested | **2** (Ask evidence) |
| Artifacts / Stories | **2** |
| Evidence modal real media | **3** shell real; content fixture |
| Teach/Learn I1 correct | **3** API real; demo ids/fixture videos |
| Typed Ask ≡ UI controls | **1** client commands |
| Explore live find API | **4 missing** (this wiring) |
| Family Night / full Teach / STT / Health redesign | **5 deferred** |

**Wiring plan:** Add `/explore/api/find` via AskOrchestrator → Explore items; default UI to live path; keep `?demo=` for prove; no UX redesign.
