# FlightSim Immich cutover — leave media-server

**Status:** Ops runbook · **Date:** 2026-08-17  
**Owner:** Tom  
**Scope:** Point MemoryBox **photo/Immich** config at Immich running **on FlightSim**.  
**Not this cutover:** SMS / mbox / ICS / video library / artifacts still on `\\media-server\photos\…` until those move.

Immich is up on FlightSim. MemoryBox still reads `config/immich.env` (gitignored). If that file still has a media-server URL or `\\media-server\immich\thumbs`, Ask/Explore will talk to the old box or miss thumbs.

After this works: **I4 §8.1 is the first owner pass.**

---

## What MemoryBox actually reads

| Setting | File / env | Must be on FlightSim |
|---|---|---|
| API URL | `config/immich.env` → `IMMICH_BASE_URL` | `http://127.0.0.1:2283/api` (or `http://localhost:2283/api`) |
| API key | same file → `IMMICH_API_KEY` | Key created **on FlightSim Immich** |
| Thumbs | same file → `IMMICH_THUMBS_PATH` | Local folder, e.g. `C:\immich\library\thumbs` — **not** UNC |
| Thumbs HTTP | `IMMICH_THUMBS_API` | **Off** (unset) unless local thumbs are missing |
| Provider | `MEMORYBOX_PHOTO_PROVIDER` | `immich` (`startmb.ps1` already sets this) |
| Env path | `MEMORYBOX_IMMICH_ENV` | `C:\memorybox\config\immich.env` (`startmb.ps1` sets this when the file exists) |

Person rows in PostgreSQL (`provider_identities.external_id`) stay valid **if** this Immich is the **same library** (same person UUIDs). A **fresh** Immich install needs `POST /people/sync/immich` and a Peggy/Tom identity check.

---

## 1. Confirm Immich on FlightSim

In a browser on FlightSim:

`http://127.0.0.1:2283`

You should see **this** Immich (library, People), not a dead media-server.

PowerShell:

```bat
curl -s -o NUL -w "%{http_code}" http://127.0.0.1:2283/api/server/ping
```

Expect `200` (some builds return a small JSON body).

Find the thumbs directory (Docker):

```bat
docker ps --format "{{.Names}}"
docker inspect immich_server --format "{{range .Mounts}}{{.Source}} -> {{.Destination}}{{println}}{{end}}"
```

Use the host path that maps to Immich upload/library, then the `thumbs` folder under it. Typical: `C:\immich\library\thumbs` or `D:\immich\library\thumbs`.

---

## 2. Write `C:\memorybox\config\immich.env`

Do **not** commit this file. Create/replace it on FlightSim only.

Immich UI → Account → API Keys → create a key (read is enough for Ask/Explore; `asset.view` if you later turn on API thumbs).

```bat
cd C:\memorybox
copy /Y config\immich.env.example config\immich.env
notepad config\immich.env
```

Set:

```
IMMICH_BASE_URL=http://127.0.0.1:2283/api
IMMICH_API_KEY=<paste FlightSim key>
IMMICH_THUMBS_PATH=C:\immich\library\thumbs
```

Adjust `IMMICH_THUMBS_PATH` to the folder from step 1. **Delete** any `\\media-server\…` line.

Leave `IMMICH_THUMBS_API` unset.

---

## 3. Restart MemoryBox serve

The Immich client is a **process singleton**. Editing the file does nothing until serve restarts.

```bat
cd C:\memorybox
git fetch origin
git checkout cursor/p2-immich-flightsim-cutover-3061
git pull origin cursor/p2-immich-flightsim-cutover-3061
```

Then restart Ask/serve. Prefer **`startmb.cmd`** (not `.\startmb.ps1` — Restricted policy blocks `.ps1` files):

```powershell
cd C:\memorybox
.\startmb.cmd
```

Or Bypass once:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\memorybox\startmb.ps1
```

Confirm the serve window prints `IMMICH_ENV=C:\memorybox\config\immich.env` and does **not** warn about media-server.

---

## 4. Prove the mapping (FlightSim)

```bat
cd C:\memorybox
python -c "from pathlib import Path; p=Path('config/immich.env'); t=p.read_text(encoding='utf-8-sig'); assert 'media-server' not in t.lower(), t; assert '127.0.0.1:2283' in t or 'localhost:2283' in t; print('immich.env host OK')"
```

```bat
python -c "from memorybox.ask.deps import build_photo; p=build_photo(); h=p.health(); print(h.ok, h.provider_key, getattr(h,'detail',h))"
```

Expect `True immich`.

Hard-reload Explore. One **named person** ask (Peggy). Confirm photos are hers, not Tom’s library. If faces look wrong after a **new** Immich install:

```bat
curl -X POST "http://127.0.0.1:8790/people/sync/immich?trigger=sync_now"
```

Then re-ask Peggy. Stale `provider_identities` are dropped when the Immich person name does not match the Ask (existing verify).

Activity (optional): `http://127.0.0.1:8790/dev/api/immich-activity`

---

## 5. What we are not remapping here

| Still on media-server (leave UNC) | Env / code |
|---|---|
| SMS / mbox / ICS Sources | `config/memorybox_sources.env` |
| Family videos | `MEMORYBOX_VIDEO_MEDIA_ROOT` |
| Artifact binaries | `MEMORYBOX_ARTIFACT_MEDIA_ROOT` |

Those are not Immich. Do not point them at `127.0.0.1:2283`.

---

## Failure checklist

| Symptom | Likely cause |
|---|---|
| Health fake/unavailable | `immich.env` missing, placeholder key, or serve not restarted |
| Photos still from old NAS | `IMMICH_BASE_URL` still media-server IP |
| Gallery 204 / no thumbs | Wrong `IMMICH_THUMBS_PATH` (must reach Immich `thumbs/`, not UNC). Current Immich stores `{owner}/{aa}/{bb}/{id}-thumbnail.webp`. Do not enable API thumbs to fix it first. |
| Peggy shows Tom’s photos | Fresh Immich UUIDs; sync + name verify; do not skip I4 case D |
| Immich dies after gallery | `IMMICH_THUMBS_API=1` or UNC thumbs — turn API off, use local disk |
