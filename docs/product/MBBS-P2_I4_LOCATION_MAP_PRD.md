# PRD — P2-I4 Location filter + Map result mode

**Status:** BUILD AUTHORIZED by founder “Implement now” scope (2026-08-13)  
**Surface:** Mixed-Media Explore (accepted interaction reference — do not redesign)  
**Branch:** `cursor/p2-i4-mixed-media-explore-3061`

## Problem
Explore can show people/time/type, but **place is only a chip string**. Immich GPS exists on assets but is dropped before the gallery. Owners cannot filter by location or see where the current result set sits on a map — while typed Ask / future STT must share one state model.

## Success criteria
1. **Location is a first-class filter** on the current Explore result corpus (alongside type), including from chips and Ask commands.
2. **Map is opt-in only** — lives in the **filter bar** (with Undated / type filters). Default remains Gallery. Map must not appear as an empty pane unless the owner asked for Map (`Map` filter or Ask `Show map.`).
3. **Map markers/clusters** come from the **same current result set** (type ∩ place ∩ timeline).
4. **Marker/cluster selection refines the gallery** (shared underlying state).
5. **Ask/STT** can set/clear location and switch Gallery/Map via `applyAskCommand`.
6. Items without coordinates stay in the gallery when place-text matches; they simply omit map markers (honest).

## In scope (implement now)
- Preserve `place` / `location` / `lat` / `lng` on Explore items from Ask/Immich (+ demo fixture coords for Oak Street).
- `domain.placeFilter` intersecting eligible set; place chips activate/clear filter.
- `gallery.viewMode`: `gallery` | `map` (presentation mode; membership stays domain+timeline). Activated from filter-bar **Map** control or Ask — not a standing Gallery|Map toolbar takeover.
- Lightweight OSM/Leaflet map + simple clustering over current result set.
- Marker/cluster → `domain.mapRefineIds` → gallery refined; clearable.
- Ask: `Only <Place>.` / `Near <Place>.` / `Clear location.` / `Show map.` / `Show gallery.` / clear filters clears place+map refine + returns to gallery.

## Founder correction (2026-08-13)
Map should **only show when requested**, and the control belongs **with filters** (not a default dual canvas that can leave an empty gray map).

## Out of scope (do not implement now)
- Full GIS tools, route/history reconstruction, complicated layers
- Settings-based place search
- Map as its own top-level destination
- Durable Place SoT / aliases (EVS backlog)

## Constraints
- Preserve I1–I3 and locked Explore UX hierarchy.
- No invented coordinates for undated/unlocated items.
- Reset timeline does **not** clear place filter (same rule as type filter); explicit clear does.

## Build sequence
1. Pipe lat/lng/place through PhotoHit → Explore find (+ fixture).
2. Domain place filter + Ask commands + chips.
3. Map mode UI + sync to result set + refine gallery.
4. Prove harness markers; commit/push; FlightSim notes.
