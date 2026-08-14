/**
 * MemoryBox P2-I4 — Mixed-Media Exploration
 *
 * INTERACTION REFERENCE (founder): the current Explore screen is the accepted
 * I4 interaction reference. Improve implementation underneath; do NOT redesign
 * the experience while wiring live data / providers.
 *
 * Separated state layers (MBUX-001 / locked I4 definition):
 *   domain  — query, chips, type filter, place filter, map refine → eligible set
 *   timeline — dated portion of eligible set; active range; playhead
 *   gallery  — density + viewMode (gallery|map presentation), scroll position
 *   modal    — open item; close restores explore snapshot (+ correction consequences)
 *
 * Typed Ask commands and future STT must manipulate the same domain/timeline state.
 * Map is a secondary result mode over the current result set — not a top-level app.
 */
(function () {
  "use strict";

  const FILTERS = [
    { id: "all", label: "All" },
    { id: "photo", label: "Photos" },
    { id: "video", label: "Video" },
    { id: "email", label: "Email/Text" },
    { id: "artifact", label: "Artifacts" },
    { id: "story", label: "Stories" },
  ];

  const TYPE_GLYPH = {
    photo: "▣",
    video: "▶",
    email: "✉",
    artifact: "◇",
    story: "❧",
    audio: "♫",
    sms: "💬",
    calendar: "▦",
    recipe: "♨",
    document: "▤",
  };

  const NAV = [
    { id: "ask", label: "Ask", href: "/ask/ui", ico: "?" },
    { id: "people", label: "People", href: "/people/ui", ico: "☺" },
    { id: "stories", label: "Stories", href: "/story/ui", ico: "❧" },
    { id: "journal", label: "Journal", href: "/journal/ui", ico: "✎" },
    { id: "artifacts", label: "Artifacts", href: "/artifact/ui", ico: "◇" },
    { id: "family-night", label: "Family Night", href: "/family-night/ui", ico: "✧" },
    { id: "teach", label: "Review & Learn", href: "/review/ui", ico: "✧" },
  ];

  const DENSITY_LABEL = { 1: "Small", 2: "Medium", 3: "Large" };

  const PERSON = window.MB_PERSON_SURFACE || null;
  const PERSON_MODE = Boolean(PERSON && PERSON.personId);
  if (PERSON_MODE) {
    // I5 visual lock order: All · Photos · Video · Audio · Email/Text · Artifacts · Stories · Location
    // Audio empty-OK; Location = has GPS/Place (locked option D); Map toggle stays separate.
    FILTERS.splice(3, 0, { id: "audio", label: "Audio" });
    FILTERS.push({ id: "location", label: "Location" });
    const teachNav = NAV.find((n) => n.id === "teach");
    if (teachNav) teachNav.label = "Teach";
  }

  // Ask command examples (typed today; STT later shares applyAskCommand):
  // "Only photos." "Add video." "Clear filters." "Show everything."
  // "Add texts." "Only texts." — I7: texts join / text-only; default Gallery hides SMS
  // "Show 2005 through 2011." "Only Oak Street." "Near Cascadia."
  // "Clear location." "Show map." "Show gallery."
  // "Clear context and go to People."

  /** @type {{
   *   domain: {
   *     askText: string,
   *     title: string,
   *     summary: string,
   *     chips: Array<{label:string,kind?:string}>,
   *     typeFilter: string,
   *     placeFilter: string|null,
   *     undatedFilter: boolean,
   *     mapRefineIds: string[]|null,
   *     items: Array<object>,
   *   },
   *   timeline: {
   *     extentStart: number,
   *     extentEnd: number,
   *     rangeStart: number,
   *     rangeEnd: number,
   *     playhead: number,
   *     precision: 'years'|'months'|'days',
   *   },
   *   gallery: { density: number, scrollTop: number, sort: 'newest'|'oldest', viewMode: 'gallery'|'map' },
   *   modal: { openId: string|null, snapshot: object|null, pendingCorrection: object|null },
   * }} */
  let state = null;
  let rawItems = [];
  let peopleOptions = [];
  let liveMode = true;
  let sessionId = null;
  let bandDrag = null;
  let handleDrag = null;
  let handleDragMeta = null;
  let scrubDrag = null;
  let mapInstance = null;
  let mapClusterLayer = null;
  let mapReady = false;

  function dayMs(y, m, d) {
    return Date.UTC(y, m - 1, d);
  }

  function parseISO(s) {
    if (!s) return NaN;
    const p = String(s || "").slice(0, 10).split("-");
    if (p.length < 3 || !p[0]) return NaN;
    return dayMs(+p[0], +p[1], +p[2]);
  }

  function isUndated(item) {
    return Boolean(item && (item.undated || !item.date || !Number.isFinite(parseISO(item.date))));
  }

  function isDated(item) {
    return !isUndated(item);
  }

  function itemPlaceBlob(item) {
    if (!item) return "";
    return [
      item.place,
      item.location,
      item.city,
      item.state,
      item.country,
      item.title,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
  }

  function matchesPlace(item, placeFilter) {
    if (!placeFilter) return true;
    const needle = String(placeFilter).trim().toLowerCase();
    if (!needle) return true;
    return itemPlaceBlob(item).includes(needle);
  }

  function itemLatLng(item) {
    if (!item) return null;
    const lat = item.lat != null ? item.lat : item.latitude;
    const lng = item.lng != null ? item.lng : item.longitude;
    const la = Number(lat);
    const lo = Number(lng);
    if (!Number.isFinite(la) || !Number.isFinite(lo)) return null;
    if (la < -90 || la > 90 || lo < -180 || lo > 180) return null;
    return { lat: la, lng: lo };
  }

  /** Eligible = corpus ∩ type ∩ place (map refine applies at visible layer). */
  function eligibleItems() {
    return rawItems.filter(
      (it) =>
        matchesType(it, state.domain.typeFilter) &&
        matchesPlace(it, state.domain.placeFilter)
    );
  }

  function datedEligible() {
    return eligibleItems().filter(isDated);
  }

  function undatedEligible() {
    return eligibleItems().filter(isUndated);
  }

  /** True when active range is narrower than full dated extent of eligible set. */
  function isDateBounded() {
    if (!hasDatedExtent()) return false;
    const span = state.timeline.extentEnd - state.timeline.extentStart;
    const eps = Math.max(span * 0.004, 86400000 * 0.5);
    return (
      state.timeline.rangeStart > state.timeline.extentStart + eps ||
      state.timeline.rangeEnd < state.timeline.extentEnd - eps
    );
  }

  function fmtDay(ms) {
    const d = new Date(ms);
    const y = d.getUTCFullYear();
    const m = String(d.getUTCMonth() + 1).padStart(2, "0");
    const day = String(d.getUTCDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
  }

  function fmtRangeLabel(a, b, precision) {
    const da = new Date(a);
    const db = new Date(b);
    if (precision === "days") {
      return `${fmtDay(a)} → ${fmtDay(b)}`;
    }
    if (precision === "months") {
      const ma = `${da.getUTCFullYear()}-${String(da.getUTCMonth() + 1).padStart(2, "0")}`;
      const mb = `${db.getUTCFullYear()}-${String(db.getUTCMonth() + 1).padStart(2, "0")}`;
      return `${ma} → ${mb}`;
    }
    return `${da.getUTCFullYear()}–${db.getUTCFullYear()}`;
  }

  function computePrecision(rangeStart, rangeEnd) {
    const days = (rangeEnd - rangeStart) / 86400000;
    if (days <= 62) return "days";
    if (days <= 900) return "months";
    return "years";
  }

  function extentOf(items) {
    const dated = items.filter(isDated);
    if (!dated.length) {
      // Honest empty extent — do not invent "today" (that fake-bounded the gallery
      // and showed 2026-08-13 → 2026-08-13 for all-undated result sets).
      return { start: NaN, end: NaN, empty: true };
    }
    let lo = Infinity;
    let hi = -Infinity;
    for (const it of dated) {
      const t = parseISO(it.date);
      if (!Number.isFinite(t)) continue;
      lo = Math.min(lo, t);
      hi = Math.max(hi, t);
    }
    if (!Number.isFinite(lo)) {
      return { start: NaN, end: NaN, empty: true };
    }
    const pad = Math.max((hi - lo) * 0.02, 86400000);
    return { start: lo - pad, end: hi + pad, empty: false };
  }

  function hasDatedExtent() {
    return (
      state &&
      state.timeline &&
      Number.isFinite(state.timeline.extentStart) &&
      Number.isFinite(state.timeline.extentEnd) &&
      state.timeline.extentEnd > state.timeline.extentStart
    );
  }

  function isSmsTextItem(item) {
    const t = String((item && item.type) || "").toLowerCase();
    return t === "sms" || t === "text" || t === "imessage" || t === "mms" || t === "rcs";
  }

  function matchesType(item, filter, opts) {
    const d = (opts && opts.domain) || (state && state.domain) || {};
    const includeTexts = Boolean(
      (opts && opts.includeTexts) ||
        d.includeTexts ||
        d.galleryShowSms ||
        filter === "email"
    );
    if (isSmsTextItem(item)) {
      if (!includeTexts) return false;
      if (!filter || filter === "all" || filter === "email") return true;
      // "Add texts" joins the current Gallery (e.g. photos + texts) without
      // clearing person/event/trip context or flipping to a full All mix.
      return true;
    }
    if (!filter || filter === "all") return true;
    if (filter === "location") {
      // Option D: Location pill = has GPS/Place evidence (Map toggle is separate).
      if (itemLatLng(item)) return true;
      return Boolean(itemPlaceBlob(item).trim());
    }
    const t = String(item.type || "").toLowerCase();
    if (filter === "email") return t === "email" || t === "sms" || t === "text";
    if (filter === "audio") return t === "audio" || t === "voice";
    return t === filter;
  }

  /**
   * Result set before map-marker refine (type ∩ place ∩ timeline ∩ undated filter).
   *
   * Undated sit OFF the Timeline axis (control to the left). They always remain
   * in the Gallery unless the Undated filter is on (then Gallery = undated only).
   * Sort undated to the oldest end of the group when mixed with dated items.
   */
  function resultSetItems() {
    const eligible = eligibleItems();
    const { rangeStart, rangeEnd } = state.timeline;
    const sort = (state.gallery && state.gallery.sort) || "newest";
    const hasRange =
      Number.isFinite(rangeStart) && Number.isFinite(rangeEnd);
    const undatedOnly = Boolean(state.domain.undatedFilter);
    const windows = state.domain.temporalWindows || null;
    const list = eligible.filter((it) => {
      if (undatedOnly) return isUndated(it);
      if (isUndated(it)) return true; // never exclude undated from gallery
      const t = parseISO(it.date);
      if (!Number.isFinite(t)) return true;
      if (windows && windows.length) {
        return windows.some(([a, b]) => t >= a && t <= b);
      }
      if (!hasRange) return true;
      return t >= rangeStart && t <= rangeEnd;
    });
    list.sort((a, b) => {
      if (isUndated(a) && isUndated(b)) return 0;
      if (isUndated(a)) return sort === "oldest" ? -1 : 1;
      if (isUndated(b)) return sort === "oldest" ? 1 : -1;
      const d = parseISO(a.date) - parseISO(b.date);
      return sort === "oldest" ? d : -d;
    });
    if (PERSON_MODE && (PERSON.memoryMode || "highlights") === "highlights") {
      if (state && state.domain) state.domain._eligibleBeforeHighlights = list.length;
      return rankHighlights(list);
    }
    if (state && state.domain) state.domain._eligibleBeforeHighlights = list.length;
    return list;
  }

  /**
   * I5 Highlights ranking (Person surface) — quality first, then year shape:
   * 1) Clear, focused, face-forward pics (large/centered face, high identity score)
   * 2) Bulk from recent years; still reach back ~10–20 years with best-per-era picks
   * Not random / not “first 36”. All Memories shows the full set.
   */
  function highlightScore(it) {
    if (!it) return -1e9;
    let s = 0;
    const t = String(it.type || "").toLowerCase();
    // Photos dominate — Highlights are a visual best-of for the person
    if (t === "photo") s += 25;
    else if (t === "video") s += 8;
    else if (t === "story") s += 5;
    else if (t === "artifact") s += 3;
    else if (t === "email" || t === "sms") s += 1;

    const box = it.face_box;
    if (
      box &&
      Number(box.w) > 0 &&
      Number(box.h) > 0 &&
      Number.isFinite(Number(box.x)) &&
      Number.isFinite(Number(box.y))
    ) {
      const w = Number(box.w);
      const h = Number(box.h);
      const x = Number(box.x);
      const y = Number(box.y);
      const area = w * h; // Immich boxes normalized 0–1
      // Large face ≈ clear full face / good framing (quality signal #1)
      s += Math.min(90, area * 140);
      if (area >= 0.08) s += 18; // close / portrait-scale
      else if (area >= 0.04) s += 10;
      else if (area < 0.012) s -= 28; // tiny distant face
      const cx = x + w / 2;
      const cy = y + h / 2;
      const centerDist = Math.hypot(cx - 0.5, cy - 0.5);
      s += Math.max(0, 22 - centerDist * 44);
      // Face fully in frame (not clipped) — proxy for cleaner crop / lighting room
      if (x > 0.02 && y > 0.02 && x + w < 0.98 && y + h < 0.98) s += 10;
      const aspect = w / h;
      if (aspect > 0.55 && aspect < 1.75) s += 6;
    } else if (t === "photo") {
      s -= 12; // person photo without a face box is a weak Highlight
    } else if (it.thumb_url || it.media_url) {
      s += 1;
    }

    // Identity probability / retrieval confidence when present
    if (typeof it.score === "number" && Number.isFinite(it.score)) {
      let conf = Number(it.score);
      if (conf > 1.5) conf = conf / 100; // allow 0–100 provider scales
      s += Math.min(28, Math.max(0, conf * 28));
    }
    if (it.face_identity || it.mb_person_name) s += 8;
    if (isDated(it)) s += 2;
    return s;
  }

  function itemYear(it) {
    if (!isDated(it)) return null;
    const y = parseInt(String(it.date).slice(0, 4), 10);
    return Number.isFinite(y) ? y : null;
  }

  function rankHighlights(items) {
    const MAX = 36;
    if (!items || items.length <= MAX) return items;
    const scored = items
      .map((it) => ({ it, s: highlightScore(it), y: itemYear(it) }))
      .sort((a, b) => b.s - a.s || (b.y || 0) - (a.y || 0));

    const years = scored.map((r) => r.y).filter((y) => y != null);
    const maxY = years.length ? Math.max.apply(null, years) : new Date().getUTCFullYear();
    const recentFloor = maxY - 10; // bulk = last ~10 years
    const archiveFloor = maxY - 20; // reach back 10–20 years

    const BULK = 24; // quality-first recent majority
    const REACH = 10; // best picks spanning the prior decade
    const out = [];
    const seen = new Set();
    function take(it) {
      if (!it || seen.has(it.id) || out.length >= MAX) return false;
      seen.add(it.id);
      out.push(it);
      return true;
    }

    // 1) Bulk: highest-quality from recent years (current era)
    for (const row of scored) {
      if (out.length >= BULK) break;
      if (row.y != null && row.y < recentFloor) continue;
      take(row.it);
    }

    // 2) Reach-back: best face/quality per year for ~10–20 years ago
    const bestArchiveByYear = new Map();
    for (const row of scored) {
      if (row.y == null) continue;
      if (row.y < archiveFloor || row.y >= recentFloor) continue;
      if (!bestArchiveByYear.has(row.y)) bestArchiveByYear.set(row.y, row);
    }
    const archiveYears = Array.from(bestArchiveByYear.keys()).sort((a, b) => b - a);
    let reachTaken = 0;
    for (const y of archiveYears) {
      if (reachTaken >= REACH || out.length >= MAX) break;
      if (take(bestArchiveByYear.get(y).it)) reachTaken += 1;
    }

    // 3) Fill remainder with next-best quality overall (still face/quality ranked)
    for (const row of scored) {
      if (out.length >= MAX) break;
      take(row.it);
    }

    out.sort((a, b) => {
      if (isUndated(a) && !isUndated(b)) return 1;
      if (!isUndated(a) && isUndated(b)) return -1;
      return parseISO(b.date) - parseISO(a.date);
    });
    return out;
  }

  /**
   * Gallery membership:
   * - dated items in active Timeline range (unless Undated filter is on)
   * - undated always included when filter off; only undated when filter on
   * - optional mapRefineIds from marker/cluster selection
   */
  function visibleItems() {
    const base = resultSetItems();
    const refine = state.domain.mapRefineIds;
    if (!refine || !refine.length) return base;
    const allow = new Set(refine.map(String));
    return base.filter((it) => allow.has(String(it.id)));
  }

  /** After type-filter change: Timeline = dated portion of new eligible set (full extent). */
  function syncTimelineToEligibleDatedExtent() {
    const ext = extentOf(datedEligible());
    if (ext.empty) {
      state.timeline.fullExtentStart = NaN;
      state.timeline.fullExtentEnd = NaN;
      state.timeline.extentStart = NaN;
      state.timeline.extentEnd = NaN;
      state.timeline.rangeStart = NaN;
      state.timeline.rangeEnd = NaN;
      state.timeline.playhead = NaN;
      state.timeline.precision = "years";
      state.timeline.empty = true;
      return;
    }
    state.timeline.empty = false;
    state.timeline.fullExtentStart = ext.start;
    state.timeline.fullExtentEnd = ext.end;
    state.timeline.extentStart = ext.start;
    state.timeline.extentEnd = ext.end;
    state.timeline.rangeStart = ext.start;
    state.timeline.rangeEnd = ext.end;
    state.timeline.precision = computePrecision(ext.start, ext.end);
    state.timeline.playhead = ext.start;
  }

  /** Zoom axis so the current range fills the track (higher precision). */
  function zoomTimelineToRange() {
    if (!hasDatedExtent()) return;
    const fullA = Number.isFinite(state.timeline.fullExtentStart)
      ? state.timeline.fullExtentStart
      : state.timeline.extentStart;
    const fullB = Number.isFinite(state.timeline.fullExtentEnd)
      ? state.timeline.fullExtentEnd
      : state.timeline.extentEnd;
    let a = state.timeline.rangeStart;
    let b = state.timeline.rangeEnd;
    if (!Number.isFinite(a) || !Number.isFinite(b) || b <= a) return;
    a = Math.max(a, fullA);
    b = Math.min(b, fullB);
    const pad = Math.max((b - a) * 0.02, 86400000);
    let viewA = Math.max(fullA, a - pad);
    let viewB = Math.min(fullB, b + pad);
    if (viewB <= viewA) {
      viewA = fullA;
      viewB = fullB;
    }
    state.timeline.extentStart = viewA;
    state.timeline.extentEnd = viewB;
    state.timeline.rangeStart = Math.max(a, viewA);
    state.timeline.rangeEnd = Math.min(b, viewB);
    state.timeline.precision = computePrecision(
      state.timeline.rangeStart,
      state.timeline.rangeEnd
    );
  }

  function setTypeFilter(id) {
    state.domain.typeFilter = id || "all";
    state.domain.mapRefineIds = null;
    syncTimelineToEligibleDatedExtent();
  }

  function setUndatedFilter(on) {
    state.domain.undatedFilter = Boolean(on);
    state.domain.mapRefineIds = null;
  }

  function setPlaceFilter(label) {
    const next = label ? String(label).trim() : "";
    state.domain.placeFilter = next || null;
    state.domain.mapRefineIds = null;
    syncTimelineToEligibleDatedExtent();
  }

  function clearPlaceFilter() {
    state.domain.placeFilter = null;
    state.domain.mapRefineIds = null;
    syncTimelineToEligibleDatedExtent();
  }

  function setViewMode(mode) {
    const m = mode === "map" ? "map" : "gallery";
    state.gallery.viewMode = m;
  }

  function syncPersonChrome() {
    if (!PERSON_MODE) return;
    const mode = PERSON.memoryMode === "all" ? "all" : "highlights";
    PERSON.memoryMode = mode;
    document.querySelectorAll(".mb-person-mode").forEach((b) => {
      const on = (b.getAttribute("data-mode") || "") === mode;
      b.classList.toggle("is-active", on);
      b.setAttribute("aria-selected", on ? "true" : "false");
    });
    const view = (state.gallery && state.gallery.viewMode) || "gallery";
    document.querySelectorAll(".mb-person-view").forEach((b) => {
      const on = (b.getAttribute("data-view") || "") === view;
      b.classList.toggle("is-active", on);
    });
  }

  function setMapRefine(ids) {
    if (!ids || !ids.length) {
      state.domain.mapRefineIds = null;
      return;
    }
    state.domain.mapRefineIds = ids.map(String);
  }

  function placeFilterFromChips(chips) {
    const places = (chips || []).filter((c) => c && c.kind === "place" && c.label);
    if (places.length === 1) return String(places[0].label);
    return null;
  }

  function snapshotExplore() {
    return {
      domain: JSON.parse(JSON.stringify(state.domain)),
      timeline: { ...state.timeline },
      gallery: { ...state.gallery },
    };
  }

  function restoreExplore(snap) {
    if (!snap) return;
    state.domain = JSON.parse(JSON.stringify(snap.domain));
    state.timeline = { ...snap.timeline };
    state.gallery = { ...snap.gallery };
  }

  function countByType(items) {
    const c = { photo: 0, video: 0, email: 0, artifact: 0, story: 0, other: 0 };
    for (const it of items) {
      const t = String(it.type || "").toLowerCase();
      if (t in c) c[t] += 1;
      else if (t === "sms" || t === "text") c.email += 1;
      else c.other += 1;
    }
    return c;
  }

  function refreshCuratorFromVisible() {
    // Keep fixture curator copy when on demo All+full range; else summarize live set.
    const vis = visibleItems();
    const atFull =
      !hasDatedExtent() ||
      (state.timeline.rangeStart <= state.timeline.extentStart + 1 &&
        state.timeline.rangeEnd >= state.timeline.extentEnd - 1);
    if (state.domain.typeFilter === "all" && atFull && state.domain._fixtureSummary) {
      state.domain.summary = state.domain._fixtureSummary;
      return;
    }
    // Prefer Ask clarification / curator answer over empty "0 memories" noise.
    if (
      state.domain._askSummary &&
      (state.domain._askKind === "clarification" || vis.length === 0)
    ) {
      state.domain.summary = state.domain._askSummary;
      return;
    }
    const c = countByType(vis);
    const parts = [];
    if (c.photo) parts.push(`${c.photo} photo${c.photo === 1 ? "" : "s"}`);
    if (c.video) parts.push(`${c.video} video moment${c.video === 1 ? "" : "s"}`);
    if (c.email) parts.push(`${c.email} email${c.email === 1 ? "" : "s"}`);
    if (c.artifact) parts.push(`${c.artifact} artifact${c.artifact === 1 ? "" : "s"}`);
    if (c.story) parts.push(`${c.story} stor${c.story === 1 ? "y" : "ies"}`);
    const filterLabel =
      FILTERS.find((f) => f.id === state.domain.typeFilter)?.label || "All";
    const undatedOnly = !hasDatedExtent() && vis.some(isUndated);
    const range = undatedOnly
      ? "undated"
      : hasDatedExtent()
        ? fmtRangeLabel(
            state.timeline.rangeStart,
            state.timeline.rangeEnd,
            state.timeline.precision
          )
        : "all dates";
    if (
      PERSON_MODE &&
      (PERSON.memoryMode || "highlights") === "highlights" &&
      Number(state.domain._eligibleBeforeHighlights || 0) > vis.length
    ) {
      const total = state.domain._eligibleBeforeHighlights;
      state.domain.summary =
        `Highlights · ${vis.length} of ${total} memories (${filterLabel}) for ${range}` +
        (parts.length ? ": " + parts.join(", ") + "." : ".") +
        " Ranked by picture quality first (clear full face, focused, high identity confidence), with most from recent years and a reach-back across the prior 10–20 years. Switch to All Memories for the full set.";
      return;
    }
    if (state.domain.undatedFilter) {
      state.domain.summary = `Showing ${vis.length} undated memories (${filterLabel})${
        parts.length ? ": " + parts.join(", ") + "." : "."
      }`;
      return;
    }
    state.domain.summary = `Showing ${vis.length} memories (${filterLabel}) for ${range}${
      parts.length ? ": " + parts.join(", ") + "." : "."
    }`;
  }

  // ——— Ask command architecture (typed today; STT later shares this) ———

  function personScopedAsk(askText) {
    let q = String(askText || "").trim();
    if (!PERSON_MODE) return q;
    const name = (PERSON.displayName || "").trim();
    if (!name) return q;
    const lower = q.toLowerCase();
    const nameL = name.toLowerCase();
    const first = nameL.split(/\s+/)[0];
    if (!q) return "Show " + name;
    if (/^go to\b/.test(lower)) return q;
    if (lower.includes(nameL) || (first && /\b/.test(first) && lower.includes(first))) {
      // Already mentions locked person — don't double-prefix
      if (/^show\b/.test(lower)) return q;
      return q;
    }
    if (/^show\b/.test(lower)) {
      // "Show Christmas" / "Show only video" → keep locked person in the query
      const rest = q.replace(/^show\s+(?:me\s+)?/i, "").trim();
      return "Show " + name + " " + rest;
    }
    // Bare refinements inherit Person ("Christmas." → "Show Peggy Christmas")
    return "Show " + name + " " + q;
  }

  /** Resolve a person option carefully — avoid "Tom" → first Tom* in the list. */
  function resolvePersonOption(who) {
    const whoL = String(who || "")
      .trim()
      .toLowerCase();
    if (!whoL) return null;
    const opts = peopleOptions || [];
    const exact = opts.filter(
      (p) => String(p.label || "").toLowerCase() === whoL
    );
    if (exact.length === 1) return exact[0];
    if (exact.length > 1) return exact[0];
    const tokens = whoL.split(/\s+/).filter(Boolean);
    if (tokens.length > 1) {
      const multi = opts.filter((p) => {
        const lab = String(p.label || "").toLowerCase();
        const parts = lab.split(/\s+/);
        return tokens.every((t) => parts.some((part) => part === t || part.startsWith(t)));
      });
      if (multi.length === 1) return multi[0];
      if (multi.length > 1) {
        // Prefer exact token-count / shortest full name
        multi.sort(
          (a, b) =>
            String(a.label || "").length - String(b.label || "").length
        );
        return multi[0];
      }
    }
    // Single token: unique first-name only
    const firstHits = opts.filter(
      (p) => String(p.label || "").toLowerCase().split(/\s+/)[0] === whoL
    );
    if (firstHits.length === 1) return firstHits[0];
    // Ambiguous "Tom" with multiple people — do not guess
    return null;
  }

  /** Person surface: "Show me Tom" / "Go to Tom instead" → open that Person Explorer. */
  function trySwitchPersonFromAsk(raw) {
    if (!PERSON_MODE) return false;
    const text = String(raw || "").trim();
    const lower = text.toLowerCase();
    let who = "";
    const go = lower.match(/^go to\s+(.+?)\s+instead\.?$/);
    const show = text.match(/^show\s+(?:me\s+)?(.+?)\.?$/i);
    if (go) who = go[1].replace(/\.$/, "").trim();
    else if (show) {
      who = show[1].trim();
      who = who
        .replace(
          /\s+(at|in|during|from|between|only|through|near|around)\b[\s\S]*$/i,
          ""
        )
        .trim();
    } else {
      return false;
    }
    if (!who) return false;
    const whoL = who.toLowerCase();
    const locked = (PERSON.displayName || "").toLowerCase();
    const lockedFirst = locked.split(/\s+/)[0] || "";
    if (
      whoL === locked ||
      whoL === lockedFirst ||
      (lockedFirst && whoL.startsWith(lockedFirst + " "))
    ) {
      return false;
    }
    if (
      /^(christmas|easter|thanksgiving|halloween|summer|winter|spring|fall|labor|memorial|nye|nyd|new year|photos?|videos?|audio|everything|map|gallery|undated|highlights|all memories|\d{4})/.test(
        whoL
      )
    ) {
      return false;
    }
    const hit = resolvePersonOption(who);
    if (hit && hit.id) {
      if (window.mbShell && window.mbShell.setActivePerson) {
        window.mbShell.setActivePerson({ id: hit.id, name: hit.label || who });
      }
      window.location.replace(
        "/people/ui?person=" +
          encodeURIComponent(hit.id) +
          "&person_name=" +
          encodeURIComponent(hit.label || who)
      );
      return true;
    }
    // Ambiguous or unknown — let Ask clarify (do not navigate to a wrong Tom)
    if (whoL.split(/\s+/).length === 1) {
      const firstHits = (peopleOptions || []).filter(
        (p) => String(p.label || "").toLowerCase().split(/\s+/)[0] === whoL
      );
      if (firstHits.length > 1) {
        state.domain.summary =
          "Which " +
          who +
          "? " +
          firstHits
            .slice(0, 6)
            .map((p) => p.label)
            .join(", ") +
          (firstHits.length > 6 ? "…" : "") +
          ". Try “Show " +
          (firstHits[0].label || who) +
          "” or “Go to … instead”.";
        renderCurator();
        return true;
      }
    }
    if (window.mbShell && window.mbShell.setActivePerson) {
      window.mbShell.setActivePerson({ id: "", name: who });
    }
    window.location.replace(
      "/people/ui?person_name=" + encodeURIComponent(who)
    );
    return true;
  }

  async function liveFind(askText) {
    const q = personScopedAsk(askText);
    const url =
      "/explore/api/find?q=" +
      encodeURIComponent(q) +
      (sessionId ? "&session_id=" + encodeURIComponent(sessionId) : "");
    const res = await fetch(url);
    if (!res.ok) throw new Error("find " + res.status);
    return res.json();
  }

  function applyPayloadToState(payload, { keepPresentation } = {}) {
    rawItems = Array.isArray(payload.items)
      ? payload.items.map((x) => Object.assign({}, x))
      : [];
    if (payload.session_id) sessionId = payload.session_id;
    const dens = keepPresentation && state ? state.gallery.density : 2;
    const sort = keepPresentation && state ? state.gallery.sort : "newest";
    const scrollTop = keepPresentation && state ? state.gallery.scrollTop : 0;
    // Map is opt-in only — never carry map mode across a new find payload
    const viewMode = "gallery";
    const typeFilter =
      keepPresentation && state ? state.domain.typeFilter : "all";
    const undatedFilter =
      keepPresentation && state ? Boolean(state.domain.undatedFilter) : false;
    const chips = payload.chips || [];
    const exploreHint = payload.explore_state || {};
    const plan = payload.plan || {};
    // Shared Ask → Explore state: place + media + temporal windows from plan.
    // Place comes from Ask plan only — never keep a stale pin from a prior
    // mis-parse (e.g. "Show me Peggy" → place "Me Peggy George").
    let placeFilter = null;
    const planPlaces = exploreHint.place_names || plan.place_names || [];
    if (Array.isArray(planPlaces) && planPlaces.length === 1) {
      placeFilter = planPlaces[0];
    } else if (Array.isArray(planPlaces) && planPlaces.length > 1) {
      placeFilter = null;
    }
    let nextType = typeFilter;
    const galleryShowSms = Boolean(exploreHint.gallery_show_sms);
    const includeTexts = keepPresentation && state
      ? Boolean(state.domain.includeTexts || galleryShowSms)
      : galleryShowSms;
    if (!keepPresentation) {
      const vs = exploreHint.visual_scope || plan.visual_scope || "";
      if (vs === "still_only") nextType = "photo";
      else if (vs === "video_only") nextType = "video";
      else if (galleryShowSms) nextType = "all";
      else nextType = "all";
    }
    let temporalWindows = null;
    const rawWindows =
      exploreHint.temporal_windows || plan.temporal_windows || [];
    if (Array.isArray(rawWindows) && rawWindows.length) {
      temporalWindows = rawWindows
        .map((w) => {
          if (!Array.isArray(w) || w.length < 2) return null;
          const a = parseISO(String(w[0]).slice(0, 10));
          const b = parseISO(String(w[1]).slice(0, 10));
          if (!Number.isFinite(a) || !Number.isFinite(b)) return null;
          return [Math.min(a, b), Math.max(a, b)];
        })
        .filter(Boolean);
      if (!temporalWindows.length) temporalWindows = null;
    }
    const ext = extentOf(
      rawItems.filter(
        (it) =>
          isDated(it) &&
          matchesType(it, nextType, {
            includeTexts,
            domain: { includeTexts, galleryShowSms, typeFilter: nextType },
          }) &&
          matchesPlace(it, placeFilter)
      )
    );
    const emptyTl = Boolean(ext.empty);
    let rangeStart = emptyTl ? NaN : ext.start;
    let rangeEnd = emptyTl ? NaN : ext.end;
    // Band timeline to plan union (or single year/season/holiday span).
    const t0 = exploreHint.time_start || plan.time_start;
    const t1 = exploreHint.time_end || plan.time_end;
    if (!emptyTl && t0 && t1) {
      const a = parseISO(String(t0).slice(0, 10));
      const b = parseISO(String(t1).slice(0, 10));
      if (Number.isFinite(a) && Number.isFinite(b)) {
        rangeStart = Math.max(ext.start, Math.min(a, b));
        rangeEnd = Math.min(ext.end, Math.max(a, b));
        if (rangeEnd < rangeStart) {
          rangeStart = ext.start;
          rangeEnd = ext.end;
        }
      }
    }
    state = {
      domain: {
        askText: payload.ask_text || "",
        title: payload.title || "Memories",
        summary: payload.summary || "",
        _fixtureSummary: payload.demo ? payload.summary || "" : "",
        _askSummary: payload.summary || "",
        _askKind: payload.answer_kind || "",
        chips: chips,
        typeFilter: nextType,
        includeTexts: includeTexts,
        galleryShowSms: galleryShowSms,
        placeFilter: placeFilter,
        undatedFilter: undatedFilter,
        mapRefineIds: null,
        temporalWindows: temporalWindows,
        items: [],
      },
      timeline: {
        fullExtentStart: emptyTl ? NaN : ext.start,
        fullExtentEnd: emptyTl ? NaN : ext.end,
        extentStart: emptyTl ? NaN : ext.start,
        extentEnd: emptyTl ? NaN : ext.end,
        rangeStart: rangeStart,
        rangeEnd: rangeEnd,
        playhead: emptyTl ? NaN : rangeStart,
        precision: emptyTl ? "years" : computePrecision(rangeStart, rangeEnd),
        empty: emptyTl,
      },
      gallery: {
        density: dens,
        scrollTop: scrollTop,
        sort: sort,
        viewMode: viewMode,
      },
      modal: {
        openId: null,
        snapshot: null,
        pendingCorrection: null,
        railTab: "people",
        transcriptOn: false,
        zoom: 1,
      },
      preview: {
        timer: null,
        itemId: null,
        x: 0,
        y: 0,
        visible: false,
      },
    };
    if (typeFilter && typeFilter !== "all") {
      syncTimelineToEligibleDatedExtent();
    } else if (placeFilter) {
      syncTimelineToEligibleDatedExtent();
    }
  }

  function applyAskCommand(raw) {
    const text = String(raw || "").trim();
    if (!text) return;
    state.domain.askText = text;
    const lower = text.toLowerCase();

    // Navigation / clear context — bare People picker (drop active person)
    if (/clear context.*people|go to people/.test(lower)) {
      if (window.mbShell && window.mbShell.setActivePerson) {
        window.mbShell.setActivePerson(null);
      }
      window.location.href = "/people/ui";
      return;
    }

    if (trySwitchPersonFromAsk(text)) return;

    if (
      PERSON_MODE &&
      (/^clear everything except\b/.test(lower) ||
        /^reset to person\.?$/.test(lower) ||
        /^clear all but person\.?$/.test(lower))
    ) {
      setTypeFilter("all");
      clearPlaceFilter();
      setUndatedFilter(false);
      state.domain.temporalWindows = null;
      resetTimelineExtent(false);
      setViewMode("gallery");
      if (PERSON.memoryMode) PERSON.memoryMode = PERSON.memoryMode;
      liveFind("Show " + (PERSON.displayName || "person"))
        .then((payload) => {
          applyPayloadToState(payload, { keepPresentation: true });
          // Re-assert locked person chip
          ensureLockedPersonChip();
          render();
        })
        .catch((err) => {
          state.domain.summary = "Find failed: " + err;
          renderCurator();
        });
      return;
    }

    if (PERSON_MODE && /^go to\s+(.+?)\s+instead\.?$/.test(lower)) {
      const m = lower.match(/^go to\s+(.+?)\s+instead\.?$/);
      const who = (m && m[1] ? m[1] : "").replace(/\.$/, "").trim();
      if (who) {
        const whoL = who.toLowerCase();
        const hit = (peopleOptions || []).find((p) => {
          const lab = String(p.label || "").toLowerCase();
          const first = lab.split(/\s+/)[0];
          return lab === whoL || first === whoL || lab.includes(whoL);
        });
        if (hit && hit.id) {
          window.location.href =
            "/people/ui?person=" + encodeURIComponent(hit.id);
        } else {
          // Server resolves display name → MB Person id (same Person continuum)
          window.location.href =
            "/people/ui?person_name=" + encodeURIComponent(who);
        }
        return;
      }
    }

    if (/^clear filters\.?$/.test(lower)) {
      setTypeFilter("all");
      clearPlaceFilter();
      setUndatedFilter(false);
      setViewMode("gallery");
      state.domain.includeTexts = Boolean(state.domain.galleryShowSms);
      render();
      return;
    }
    if (/^show everything\.?$/.test(lower)) {
      setTypeFilter("all");
      clearPlaceFilter();
      setUndatedFilter(false);
      setViewMode("gallery");
      state.domain.includeTexts = true;
      render();
      return;
    }

    if (/^only undated\.?$|^undated\.?$|^show undated\.?$/.test(lower)) {
      setUndatedFilter(true);
      render();
      return;
    }
    if (/^clear undated\.?$|^include dated\.?$/.test(lower)) {
      setUndatedFilter(false);
      render();
      return;
    }

    if (/^show map\.?$|^map view\.?$|^on the map\.?$/.test(lower)) {
      setViewMode("map");
      render();
      return;
    }
    if (/^show gallery\.?$|^gallery view\.?$|^list view\.?$/.test(lower)) {
      setViewMode("gallery");
      render();
      return;
    }

    if (
      /^clear location\.?$/.test(lower) ||
      /^clear place\.?$/.test(lower) ||
      /^clear map selection\.?$/.test(lower)
    ) {
      clearPlaceFilter();
      render();
      return;
    }

    if (/^clear date\.?$|^clear time\.?$|^clear timeline\.?$/.test(lower)) {
      state.domain.temporalWindows = null;
      resetTimelineExtent(true);
      render();
      return;
    }

    if (/^reset\.?$/.test(lower)) {
      setTypeFilter("all");
      clearPlaceFilter();
      setUndatedFilter(false);
      state.domain.includeTexts = Boolean(state.domain.galleryShowSms);
      state.domain.temporalWindows = null;
      resetTimelineExtent(false);
      setViewMode("gallery");
      render();
      return;
    }

    const removePlace = lower.match(
      /^remove\s+([a-z0-9][a-z0-9'’.\-\s]{1,40})\.?$/i
    );
    if (removePlace) {
      const drop = removePlace[1].replace(/\.$/, "").trim().toLowerCase();
      const cur = (state.domain.placeFilter || "").toLowerCase();
      if (cur && (cur === drop || cur.includes(drop) || drop.includes(cur))) {
        clearPlaceFilter();
        render();
        return;
      }
    }

    // Single year refinement on current result set: "Only 2024." / "2024 only."
    const onlyYear = lower.match(/^(?:only\s+)?((?:19|20)\d{2})(?:\s+only)?\.?$/);
    if (onlyYear) {
      const y = +onlyYear[1];
      setActiveRange(dayMs(y, 1, 1), dayMs(y, 12, 31));
      render();
      return;
    }

    // Location refine on *current* result set only — never "Show me <Person>".
    // "Show …" must fall through to liveFind / Ask (person + time + place compose).
    const placeOnly = lower.match(
      /^(?:only|near|around|at)\s+([a-z0-9][a-z0-9'’.\-\s]{1,40})\.?$/i
    );
    if (placeOnly) {
      const candidate = placeOnly[1].replace(/\.$/, "").trim();
      const blocked =
        /^(me|myself|photos?|videos?|emails?|texts?|artifacts?|stories?|everything|map|gallery|undated)$/i;
      // Reject person-like / year-bearing phrases so Ask owns those.
      const looksLikeAsk =
        /\b((?:19|20)\d{2}|christmas|easter|thanksgiving|summer|winter|spring|fall)\b/i.test(
          candidate
        ) || /^me\b/i.test(candidate);
      if (candidate && !blocked.test(candidate) && !looksLikeAsk) {
        setPlaceFilter(candidate.replace(/\b\w/g, (c) => c.toUpperCase()));
        render();
        return;
      }
    }

    if (/only photos?\.?/.test(lower) || /^photos?\.?$/.test(lower)) {
      setTypeFilter("photo");
      render();
      return;
    }
    if (/only videos?\.?/.test(lower) || /add video/.test(lower)) {
      if (/add video/.test(lower) && state.domain.typeFilter === "photo") {
        setTypeFilter("all");
      } else if (/only videos?/.test(lower)) {
        setTypeFilter("video");
      } else {
        setTypeFilter("all");
      }
      render();
      return;
    }
    if (
      /^(add|include)\s+(texts?|sms|imessage|i-?message)s?\.?$/.test(lower) ||
      /^add texts?\.?$/.test(lower)
    ) {
      state.domain.includeTexts = true;
      syncTimelineToEligibleDatedExtent();
      render();
      return;
    }
    if (/only (email|emails|texts?|sms|imessage)\b/.test(lower)) {
      state.domain.includeTexts = true;
      setTypeFilter("email");
      render();
      return;
    }
    if (/only artifacts?/.test(lower)) {
      setTypeFilter("artifact");
      render();
      return;
    }
    if (/only stories?/.test(lower)) {
      setTypeFilter("story");
      render();
      return;
    }

    // Date range: "Show 2005 through 2011" / "2005–2011" / "from 2005 to 2011"
    const rangeMatch = lower.match(
      /(?:show\s+)?(\d{4})\s*(?:through|thru|to|–|-|—)\s*(\d{4})/
    );
    if (rangeMatch) {
      const y0 = +rangeMatch[1];
      const y1 = +rangeMatch[2];
      const start = dayMs(Math.min(y0, y1), 1, 1);
      const end = dayMs(Math.max(y0, y1), 12, 31);
      setActiveRange(start, end);
      render();
      return;
    }

    if (/reset timeline|full result range|reset range/.test(lower)) {
      resetTimelineExtent(true);
      render();
      return;
    }

    if (PERSON_MODE && /^remove\s+([a-z0-9][a-z0-9'’.\-\s]{1,40})\.?$/i.test(lower)) {
      const m = lower.match(/^remove\s+([a-z0-9][a-z0-9'’.\-\s]{1,40})\.?$/i);
      const token = (m && m[1] ? m[1] : "").replace(/\.$/, "").trim().toLowerCase();
      const personL = (PERSON.displayName || "").toLowerCase();
      const personFirst = personL.split(/\s+/)[0] || "";
      // Locked Person cannot be removed via Ask — ignore attempts to strip them
      if (
        token &&
        token !== personL &&
        token !== personFirst &&
        !personL.includes(token)
      ) {
        // Drop matching event/time chips by re-asking without that token — clear temporal if holiday/season-like
        if (
          /christmas|easter|thanksgiving|halloween|summer|winter|spring|fall|labor|memorial|nye|nyd|new year/.test(
            token
          )
        ) {
          state.domain.temporalWindows = null;
          resetTimelineExtent(false);
          const chips = (state.domain.chips || []).filter(
            (c) =>
              !(c.kind === "event" || c.kind === "time") ||
              !String(c.label || "")
                .toLowerCase()
                .includes(token.split(/\s+/)[0])
          );
          state.domain.chips = chips;
          ensureLockedPersonChip();
          liveFind("Show " + (PERSON.displayName || ""))
            .then((payload) => {
              applyPayloadToState(payload, { keepPresentation: true });
              ensureLockedPersonChip();
              render();
            });
          return;
        }
      } else if (token && (token === personL || token === personFirst)) {
        state.domain.summary =
          (PERSON.displayName || "Person") +
          " stays locked on this surface. Use “Go to … instead” to switch people, or People to leave.";
        renderCurator();
        return;
      }
    }

    // New find query — live path re-runs Ask; demo path keeps fixture membership
    if (liveMode) {
      liveFind(text)
        .then((payload) => {
          applyPayloadToState(payload, { keepPresentation: true });
          ensureLockedPersonChip();
          setTypeFilter("all");
          render();
        })
        .catch((err) => {
          state.domain.summary = "Find failed: " + err;
          renderCurator();
        });
      return;
    }

    state.domain.title = text.length > 48 ? text.slice(0, 45) + "…" : text;
    refreshCuratorFromVisible();
    render();
  }

  function setActiveRange(start, end) {
    if (!hasDatedExtent()) return;
    const fullA = Number.isFinite(state.timeline.fullExtentStart)
      ? state.timeline.fullExtentStart
      : state.timeline.extentStart;
    const fullB = Number.isFinite(state.timeline.fullExtentEnd)
      ? state.timeline.fullExtentEnd
      : state.timeline.extentEnd;
    let a = Math.min(start, end);
    let b = Math.max(start, end);
    // Handles may move within the full data extent (zoom out by expanding)
    a = Math.max(a, fullA);
    b = Math.min(b, fullB);
    if (b - a < 86400000) b = Math.min(fullB, a + 86400000);
    state.timeline.rangeStart = a;
    state.timeline.rangeEnd = b;
    state.timeline.precision = computePrecision(a, b);
    state.timeline.playhead = a;
    state.domain.mapRefineIds = null;
    state.domain.temporalWindows = null;
  }

  function resetTimelineExtent(andRender) {
    // Reset = full temporal extent of current eligible set. Does NOT clear query/filters.
    if (!hasDatedExtent()) {
      if (andRender) render();
      return;
    }
    const fullA = Number.isFinite(state.timeline.fullExtentStart)
      ? state.timeline.fullExtentStart
      : state.timeline.extentStart;
    const fullB = Number.isFinite(state.timeline.fullExtentEnd)
      ? state.timeline.fullExtentEnd
      : state.timeline.extentEnd;
    state.timeline.extentStart = fullA;
    state.timeline.extentEnd = fullB;
    state.timeline.rangeStart = fullA;
    state.timeline.rangeEnd = fullB;
    state.timeline.precision = computePrecision(
      state.timeline.rangeStart,
      state.timeline.rangeEnd
    );
    state.timeline.playhead = fullA;
    if (andRender) render();
  }

  // ——— Render ———

  function ensureLockedPersonChip() {
    if (!PERSON_MODE) return;
    const name = (PERSON.displayName || "").trim();
    if (!name || !state) return;
    const chips = Array.isArray(state.domain.chips) ? state.domain.chips.slice() : [];
    const without = chips.filter((c) => c.kind !== "person");
    without.unshift({ kind: "person", label: name, locked: true, personId: PERSON.personId });
    state.domain.chips = without;
  }

  /** Persist Explore person chip so shell People nav continues into Person Explorer. */
  function syncActivePersonContext() {
    if (!state || !state.domain) return;
    const chip = (state.domain.chips || []).find((c) => c && c.kind === "person");
    if (!chip || !chip.label) {
      if (window.mbShell && window.mbShell.setActivePerson) {
        window.mbShell.setActivePerson(null);
        window.mbShell.refreshPeopleNavLinks();
      }
      return;
    }
    let id =
      chip.personId ||
      (PERSON && PERSON.personId) ||
      "";
    const name = String(chip.label || "").trim();
    if (!id && name && peopleOptions && peopleOptions.length) {
      const nameL = name.toLowerCase();
      const hit = peopleOptions.find((p) => {
        const lab = String(p.label || "").toLowerCase();
        return (
          lab === nameL ||
          lab.startsWith(nameL) ||
          nameL.startsWith(lab.split(/\s+/)[0])
        );
      });
      if (hit) id = hit.id;
    }
    if (window.mbShell && window.mbShell.setActivePerson) {
      window.mbShell.setActivePerson({ id: id || "", name: name });
      window.mbShell.refreshPeopleNavLinks();
    }
  }

  function peopleNavHref() {
    if (window.mbShell && typeof window.mbShell.peopleHref === "function") {
      return window.mbShell.peopleHref();
    }
    const chip =
      state &&
      state.domain &&
      (state.domain.chips || []).find((c) => c && c.kind === "person");
    if (PERSON_MODE && PERSON && PERSON.personId) {
      return (
        "/people/ui?person=" +
        encodeURIComponent(PERSON.personId) +
        (PERSON.displayName
          ? "&person_name=" + encodeURIComponent(PERSON.displayName)
          : "")
      );
    }
    if (chip && chip.label) {
      return "/people/ui?person_name=" + encodeURIComponent(chip.label);
    }
    return "/people/ui";
  }

  function renderNav() {
    const el = document.getElementById("mb-explore-nav");
    if (!el) return;
    el.innerHTML = NAV.map((n) => {
      const href = n.id === "people" ? peopleNavHref() : n.href;
      return `<a href="${href}" data-nav="${n.id}"${
        (PERSON_MODE ? n.id === "people" : n.id === "ask")
          ? ' aria-current="page"'
          : ""
      }><span class="mb-nav-ico" aria-hidden="true">${n.ico}</span>${n.label}</a>`;
    }).join("");
  }

  // Expose for shell Global Ask + future STT — same applyAskCommand path.
  window.mbExploreApplyAsk = applyAskCommand;
  window.mbExploreSetViewMode = function (mode) {
    setViewMode(mode === "map" ? "map" : "gallery");
    render();
  };
  window.mbPersonSetMemoryMode = function (mode) {
    if (!PERSON_MODE || !PERSON) return;
    PERSON.memoryMode = mode === "all" ? "all" : "highlights";
    if (window.MB_PERSON_SURFACE) {
      window.MB_PERSON_SURFACE.memoryMode = PERSON.memoryMode;
    }
    syncPersonChrome();
    render();
  };
  window.addEventListener("mb-person-ready", (ev) => {
    if (!PERSON_MODE) return;
    const d = (ev && ev.detail) || {};
    if (d.displayName) PERSON.displayName = d.displayName;
    ensureLockedPersonChip();
    renderCurator();
  });

  function renderCurator() {
    refreshCuratorFromVisible();
    document.getElementById("mb-explore-curator-title").textContent =
      state.domain.title || "Memories";
    document.getElementById("mb-explore-curator-body").textContent =
      state.domain.summary || "";
    const chips = document.getElementById("mb-explore-chips");
    const activePlace = (state.domain.placeFilter || "").toLowerCase();
    chips.innerHTML = (state.domain.chips || [])
      .map((c) => {
        const kind = c.kind || "";
        const label = c.label || "";
        const isPlace = kind === "place";
        const active =
          isPlace && activePlace && String(label).toLowerCase() === activePlace;
        const cls = `mb-chip${isPlace ? " mb-chip-place" : ""}${
          active ? " is-active" : ""
        }`;
        if (isPlace) {
          return `<button type="button" class="${cls}" data-kind="place" data-place="${escapeAttr(
            label
          )}" aria-pressed="${active ? "true" : "false"}">${escapeHtml(
            label
          )}</button>`;
        }
        const locked = Boolean(c.locked) || (PERSON_MODE && kind === "person");
        return `<span class="${cls}${locked ? " is-locked" : ""}" data-kind="${escapeAttr(
          kind
        )}">${escapeHtml(label)}</span>`;
      })
      .join("");
    chips.querySelectorAll(".mb-chip-place").forEach((btn) => {
      btn.addEventListener("click", () => {
        const place = btn.getAttribute("data-place") || "";
        if (
          state.domain.placeFilter &&
          String(state.domain.placeFilter).toLowerCase() === place.toLowerCase()
        ) {
          clearPlaceFilter();
        } else {
          setPlaceFilter(place);
        }
        render();
      });
    });
    const av = document.getElementById("mb-explore-curator-avatar");
    if (av) {
      const portraitUrl =
        (PERSON && PERSON.portraitUrl) ||
        (window.MB_PERSON_SURFACE && window.MB_PERSON_SURFACE.portraitUrl) ||
        "";
      if (portraitUrl && av.classList.contains("has-photo")) {
        // Keep Immich preferred portrait; do not wipe to letter
      } else if (portraitUrl) {
        av.textContent = "";
        av.style.backgroundImage = "url(" + JSON.stringify(portraitUrl) + ")";
        av.classList.add("has-photo");
      } else if (!av.classList.contains("has-photo")) {
        const person = (state.domain.chips || []).find((c) => c.kind === "person");
        const label = (person && person.label) || state.domain.title || "M";
        av.textContent = String(label).trim().charAt(0).toUpperCase() || "M";
      }
    }
  }

  function renderFilters() {
    const el = document.getElementById("mb-explore-filters");
    el.innerHTML = FILTERS.map((f) => {
      const on = state.domain.typeFilter === f.id;
      return `<button type="button" data-filter="${f.id}" aria-pressed="${on}">${f.label}</button>`;
    }).join("");
    const uCount = undatedEligible().length;
    // Undated filter always offered next to type filters (mirrors timeline-left control)
    {
      const on = Boolean(state.domain.undatedFilter);
      el.insertAdjacentHTML(
        "beforeend",
        `<button type="button" class="mb-filter-undated${on ? " is-active" : ""}" data-undated-filter="1" aria-pressed="${
          on ? "true" : "false"
        }" title="${on ? "Clear undated filter" : "Show only undated"}">Undated${
          uCount ? ` · ${uCount}` : " · 0"
        }${on ? " ×" : ""}</button>`
      );
    }
    // Map is opt-in via filter bar on Explore. Person surface uses Gallery|Map toggle only.
    if (!PERSON_MODE) {
      const on = (state.gallery && state.gallery.viewMode) === "map";
      el.insertAdjacentHTML(
        "beforeend",
        `<button type="button" class="mb-filter-map${on ? " is-active" : ""}" data-map-filter="1" aria-pressed="${
          on ? "true" : "false"
        }" title="${on ? "Back to gallery" : "Show result set on map"}">Map${
          on ? " ×" : ""
        }</button>`
      );
    }
    if (state.domain.placeFilter) {
      el.insertAdjacentHTML(
        "beforeend",
        `<button type="button" class="mb-filter-place is-active" data-place-clear="1" aria-pressed="true" title="Clear location filter">📍 ${escapeHtml(
          state.domain.placeFilter
        )} ×</button>`
      );
    }
    el.querySelectorAll("[data-filter]").forEach((btn) => {
      btn.addEventListener("click", () => {
        setTypeFilter(btn.getAttribute("data-filter"));
        render();
      });
    });
    const undatedBtn = el.querySelector("[data-undated-filter]");
    if (undatedBtn) {
      undatedBtn.addEventListener("click", () => {
        setUndatedFilter(!state.domain.undatedFilter);
        render();
      });
    }
    const mapBtn = el.querySelector("[data-map-filter]");
    if (mapBtn) {
      mapBtn.addEventListener("click", () => {
        const on = (state.gallery && state.gallery.viewMode) === "map";
        setViewMode(on ? "gallery" : "map");
        render();
      });
    }
    const clearPlace = el.querySelector("[data-place-clear]");
    if (clearPlace) {
      clearPlace.addEventListener("click", () => {
        clearPlaceFilter();
        render();
      });
    }
  }

  function renderViewMode() {
    const mode = (state.gallery && state.gallery.viewMode) || "gallery";
    const gallery = document.getElementById("mb-explore-gallery");
    const mapPane = document.getElementById("mb-explore-map-pane");
    if (gallery) gallery.hidden = mode === "map";
    if (mapPane) mapPane.hidden = mode !== "map";
    syncPersonChrome();
  }

  function densityLabel() {
    return DENSITY_LABEL[state.gallery.density] || "Medium";
  }

  function fmtCardDate(iso) {
    if (!iso) return "Undated";
    const t = parseISO(iso);
    if (!Number.isFinite(t)) return "Undated";
    const d = new Date(t);
    const months = [
      "Jan",
      "Feb",
      "Mar",
      "Apr",
      "May",
      "Jun",
      "Jul",
      "Aug",
      "Sep",
      "Oct",
      "Nov",
      "Dec",
    ];
    return `${months[d.getUTCMonth()]} ${d.getUTCDate()}, ${d.getUTCFullYear()}`;
  }

  function cardMediaInner(it) {
    const t = String(it.type || "").toLowerCase();
    const prev = escapeHtml(it.preview || "");
    const media = it.thumb_url || it.media_url || "";
    if (t === "email" || t === "sms" || t === "text") {
      const from = escapeHtml(it.from || "Message");
      return `<div class="mb-card-textbody"><strong>${from}</strong>${prev || escapeHtml(it.title || "")}</div><span class="mb-card-preview">${prev}</span>`;
    }
    if (t === "story") {
      return `<div class="mb-card-textbody"><strong>Story</strong>${prev || escapeHtml(it.title || "")}</div><span class="mb-card-preview">${prev}</span>`;
    }
    if (t === "video") {
      const dur = it.duration_sec
        ? `${Math.floor(it.duration_sec / 60)}:${String(Math.floor(it.duration_sec % 60)).padStart(2, "0")}`
        : it.t != null
          ? `@ ${Number(it.t).toFixed(0)}s`
          : "";
      const bg = media
        ? `<img class="mb-card-thumb" src="${escapeAttr(media)}" alt="" loading="lazy" />`
        : "";
      return `${bg}<span class="mb-card-play" aria-hidden="true">▶</span>${
        dur ? `<span class="mb-card-dur">${dur}</span>` : ""
      }<span class="mb-card-preview">${prev}</span>`;
    }
    if (t === "audio" || t === "voice") {
      const dur = it.duration_sec
        ? `${Math.floor(it.duration_sec / 60)}:${String(
            Math.floor(it.duration_sec % 60)
          ).padStart(2, "0")}`
        : "";
      return `<div class="mb-card-textbody"><strong>Audio</strong>${
        prev || escapeHtml(it.title || "Voice")
      }</div>${
        dur ? `<span class="mb-card-dur">${dur}</span>` : ""
      }<span class="mb-card-preview">${prev}</span>`;
    }
    if (t === "photo" && media) {
      return `<img class="mb-card-thumb" src="${escapeAttr(media)}" alt="" loading="lazy" /><span class="mb-card-preview">${prev || escapeHtml(it.title || "")}</span>`;
    }
    return `<span class="mb-card-preview">${prev || escapeHtml(it.title || "")}</span>`;
  }

  function renderGallery() {
    const gallery = document.getElementById("mb-explore-gallery");
    const items = visibleItems();
    state.domain.items = items;
    gallery.dataset.density = String(state.gallery.density);
    const densLabel = document.getElementById("mb-density-label");
    if (densLabel) densLabel.textContent = densityLabel();
    const sortEl = document.getElementById("mb-explore-sort");
    if (sortEl) sortEl.value = state.gallery.sort || "newest";

    gallery.innerHTML = items
      .map((it) => {
        const glyph = TYPE_GLYPH[it.type] || "•";
        const title = escapeHtml(it.title || it.type);
        const date = escapeHtml(fmtCardDate(it.date));
        const undatedBadge = isUndated(it)
          ? `<span class="mb-card-undated-badge">Undated</span>`
          : "";
        return `<button type="button" class="mb-card" data-id="${escapeAttr(
          it.id
        )}" data-type="${escapeAttr(it.type)}">
          ${undatedBadge}
          <div class="mb-card-media" data-type="${escapeAttr(it.type)}">${cardMediaInner(
            it
          )}</div>
          <div class="mb-card-meta">
            <span class="mb-card-type" aria-hidden="true">${glyph}</span>
            <div>
              <div class="mb-card-title">${title}</div>
              <div class="mb-card-sub">${date}${
          it.face_identity ? " · " + escapeHtml(it.face_identity) : ""
        }</div>
            </div>
          </div>
        </button>`;
      })
      .join("");

    gallery.querySelectorAll(".mb-card").forEach((card) => {
      const id = card.getAttribute("data-id");
      card.addEventListener("click", () => openModal(id));
      bindCardPreview(card, id);
    });

    requestAnimationFrame(() => {
      gallery.scrollTop = state.gallery.scrollTop || 0;
    });

    const meta = document.getElementById("mb-explore-meta");
    const placeBit = state.domain.placeFilter
      ? ` · place ${state.domain.placeFilter}`
      : "";
    const undatedBit = state.domain.undatedFilter ? " · undated only" : "";
    const refineBit =
      state.domain.mapRefineIds && state.domain.mapRefineIds.length
        ? ` · map selection ${state.domain.mapRefineIds.length}`
        : "";
    const viewBit =
      (state.gallery.viewMode || "gallery") === "map" ? " · map" : "";
    meta.textContent = `${items.length} visible · ${densityLabel()} · filter ${
      state.domain.typeFilter
    }${placeBit}${undatedBit}${refineBit}${viewBit}`;
  }

  function ensureMap() {
    if (mapInstance || typeof L === "undefined") return mapInstance;
    const el = document.getElementById("mb-explore-map");
    if (!el) return null;
    mapInstance = L.map(el, {
      scrollWheelZoom: true,
      attributionControl: true,
    }).setView([39.5, -98.35], 4);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap",
    }).addTo(mapInstance);
    if (typeof L.markerClusterGroup === "function") {
      mapClusterLayer = L.markerClusterGroup({
        showCoverageOnHover: false,
        maxClusterRadius: 48,
        zoomToBoundsOnClick: false,
      });
      mapInstance.addLayer(mapClusterLayer);
    }
    mapReady = true;
    return mapInstance;
  }

  function renderMap() {
    const hint = document.getElementById("mb-map-hint");
    const clearBtn = document.getElementById("mb-map-clear-refine");
    const mode = (state.gallery && state.gallery.viewMode) || "gallery";
    if (clearBtn) {
      const hasRefine =
        state.domain.mapRefineIds && state.domain.mapRefineIds.length;
      clearBtn.hidden = !hasRefine;
    }
    if (mode !== "map") return;

    if (typeof L === "undefined") {
      if (hint)
        hint.textContent =
          "Map library unavailable offline — Gallery still works. Location filter remains active.";
      return;
    }

    const map = ensureMap();
    if (!map) return;

    // Markers from current result set (before refine) so selection can refine gallery.
    const base = resultSetItems();
    const withGeo = base.filter((it) => itemLatLng(it));
    const selected = new Set(
      (state.domain.mapRefineIds || []).map(String)
    );

    const layerParent = mapClusterLayer || map;
    if (mapClusterLayer) mapClusterLayer.clearLayers();
    else {
      map.eachLayer((ly) => {
        if (ly instanceof L.Marker) map.removeLayer(ly);
      });
    }

    const bounds = [];
    withGeo.forEach((it) => {
      const ll = itemLatLng(it);
      const marker = L.marker([ll.lat, ll.lng], {
        title: it.title || it.place || it.id,
      });
      marker._mbItemId = String(it.id);
      marker.bindPopup(
        `<strong>${escapeHtml(it.title || "Memory")}</strong><br/>${escapeHtml(
          it.place || it.location || "Located"
        )}`
      );
      marker.on("click", () => {
        setMapRefine([it.id]);
        setViewMode("gallery");
        render();
        openModal(it.id);
      });
      if (selected.size && selected.has(String(it.id))) {
        marker.setOpacity(1);
      } else if (selected.size) {
        marker.setOpacity(0.45);
      }
      if (mapClusterLayer) mapClusterLayer.addLayer(marker);
      else marker.addTo(map);
      bounds.push([ll.lat, ll.lng]);
    });

    if (mapClusterLayer) {
      mapClusterLayer.off("clusterclick");
      mapClusterLayer.on("clusterclick", (e) => {
        const childMarkers = e.layer.getAllChildMarkers
          ? e.layer.getAllChildMarkers()
          : [];
        const ids = childMarkers
          .map((m) => m._mbItemId)
          .filter(Boolean);
        if (!ids.length) return;
        // Prevent zoom-through; refine gallery to cluster members
        L.DomEvent.stopPropagation(e);
        setMapRefine(ids);
        setViewMode("gallery");
        render();
      });
    }

    requestAnimationFrame(() => {
      map.invalidateSize();
      if (bounds.length === 1) {
        map.setView(bounds[0], 13);
      } else if (bounds.length > 1) {
        map.fitBounds(bounds, { padding: [28, 28], maxZoom: 14 });
      }
    });

    if (hint) {
      const nGeo = withGeo.length;
      const nAll = base.length;
      const missing = nAll - nGeo;
      hint.textContent =
        nGeo === 0
          ? nAll === 0
            ? "No memories in the current result set."
            : `No coordinates on the current ${nAll} result${nAll === 1 ? "" : "s"} — location text filter still works; Map stays honest.`
          : `Showing ${nGeo} located of ${nAll} in the current result set${
              missing ? ` (${missing} without coordinates)` : ""
            }. Select a marker or cluster to refine the gallery.`;
    }
  }

  function renderTimeline() {
    const { extentStart, extentEnd, rangeStart, rangeEnd, playhead, precision } =
      state.timeline;
    const band = document.getElementById("mb-tl-band");
    const ph = document.getElementById("mb-tl-playhead");
    const hl = document.getElementById("mb-tl-handle-l");
    const hr = document.getElementById("mb-tl-handle-r");
    const empty = !hasDatedExtent();

    if (empty) {
      band.style.left = "0%";
      band.style.width = "100%";
      hl.style.left = "0%";
      hr.style.left = "100%";
      ph.style.left = "0%";
      document.getElementById("mb-tl-range-label").textContent =
        "No dated memories on the Timeline";
    } else {
      const span = Math.max(extentEnd - extentStart, 1);
      // Clamp chrome to the track — indicators/handles never paint outside the timeline
      const left = Math.min(100, Math.max(0, ((rangeStart - extentStart) / span) * 100));
      const right = Math.min(100, Math.max(0, ((rangeEnd - extentStart) / span) * 100));
      const width = Math.max(right - left, 0.5);
      band.style.left = `${left}%`;
      band.style.width = `${width}%`;
      hl.style.left = `${left}%`;
      hr.style.left = `${right}%`;
      const p = ((playhead - extentStart) / span) * 100;
      ph.style.left = `${Math.min(100, Math.max(0, p))}%`;
      document.getElementById("mb-tl-range-label").textContent = fmtRangeLabel(
        rangeStart,
        rangeEnd,
        precision
      );
    }

    const undatedEl = document.getElementById("mb-tl-undated");
    const uCount = undatedEligible().length;
    if (undatedEl) {
      // Always visible left of the Timeline axis (founder: undated filter next to timeline)
      undatedEl.hidden = false;
      undatedEl.textContent = `Undated: ${uCount}`;
      undatedEl.classList.toggle("is-active", Boolean(state.domain.undatedFilter));
      undatedEl.setAttribute(
        "aria-pressed",
        state.domain.undatedFilter ? "true" : "false"
      );
      undatedEl.disabled = uCount === 0 && !state.domain.undatedFilter;
      undatedEl.title =
        uCount === 0 && !state.domain.undatedFilter
          ? "No undated memories in the current result set"
          : state.domain.undatedFilter
            ? "Clear undated filter"
            : "Filter gallery to undated memories (off Timeline axis)";
    }

    const dotsEl = document.getElementById("mb-tl-dots");
    const typedDated = datedEligible();
    // Always clear first — prevents leftover dots after zoom
    if (dotsEl) dotsEl.innerHTML = "";
    if (!empty && dotsEl) {
      const span = Math.max(extentEnd - extentStart, 1);
      const parts = [];
      for (const it of typedDated) {
        const t = parseISO(it.date);
        if (!Number.isFinite(t)) continue;
        // Rule: timeline indicators never exceed the timeline track
        if (t < extentStart || t > extentEnd) continue;
        let x = ((t - extentStart) / span) * 100;
        if (x < 0 || x > 100) continue;
        // Keep dot centers inside the rail (avoid margin bleed past edges)
        x = Math.min(99.2, Math.max(0.8, x));
        parts.push(
          `<span class="mb-tl-dot" style="left:${x}%" title="${escapeAttr(
            it.date
          )}"></span>`
        );
      }
      dotsEl.innerHTML = parts.join("");
    }

    const ticks = document.getElementById("mb-tl-ticks");
    if (empty) {
      ticks.innerHTML = "";
    } else {
      const span = Math.max(extentEnd - extentStart, 1);
      const years = [];
      const y0 = new Date(extentStart).getUTCFullYear();
      const y1 = new Date(extentEnd).getUTCFullYear();
      for (let y = y0; y <= y1; y++) years.push(y);
      const step = years.length > 16 ? 4 : years.length > 10 ? 2 : 1;
      ticks.innerHTML = years
        .filter((y, i) => i === 0 || i === years.length - 1 || y % step === 0)
        .map((y) => {
          const t = dayMs(y, 1, 1);
          const x = ((t - extentStart) / span) * 100;
          return `<span style="left:${Math.min(98, Math.max(0, x))}%">${y}</span>`;
        })
        .join("");
    }
  }

  function render() {
    document.getElementById("mb-explore-ask").value = state.domain.askText || "";
    ensureLockedPersonChip();
    syncActivePersonContext();
    syncPersonChrome();
    renderNav();
    renderCurator();
    renderFilters();
    renderViewMode();
    renderGallery();
    renderMap();
    renderTimeline();
  }

  // ——— Shared Evidence Viewer + quick preview (MBUX §22.4–22.6) ———

  function visibleIds() {
    return visibleItems().map((x) => x.id);
  }

  function openModal(id) {
    const item = rawItems.find((x) => x.id === id);
    if (!item) return;
    hideQuickPreview();
    state.gallery.scrollTop =
      document.getElementById("mb-explore-gallery").scrollTop || 0;
    if (!state.modal.snapshot) state.modal.snapshot = snapshotExplore();
    state.modal.openId = id;
    state.modal.pendingCorrection = null;
    if (!state.modal.railTab) state.modal.railTab = "people";
    state.modal.transcriptOn = false;
    state.modal.zoom = 1;
    renderViewer(item);
    document.getElementById("mb-modal").hidden = false;
    document.getElementById("mb-modal-close").focus();
  }

  function renderViewer(item) {
    const ids = visibleIds();
    const idx = ids.indexOf(item.id);
    document.getElementById("mb-modal-kicker").textContent = String(
      item.type || "Evidence"
    ).toUpperCase();
    document.getElementById("mb-modal-title").textContent = item.title || item.id;
    const count = document.getElementById("mb-viewer-count");
    if (count) {
      count.textContent =
        idx >= 0 ? `${idx + 1} of ${ids.length}` : `— of ${ids.length}`;
    }
    const prevBtn = document.getElementById("mb-viewer-prev");
    const nextBtn = document.getElementById("mb-viewer-next");
    if (prevBtn) prevBtn.disabled = idx <= 0;
    if (nextBtn) nextBtn.disabled = idx < 0 || idx >= ids.length - 1;
    document.getElementById("mb-modal-body").innerHTML = renderEvidenceBody(item);
    renderViewerFooter(item);
    syncRailTabs();
    renderRailPanel(item);
    renderRailTools(item);
    renderTeachSlot(item);
    bindPhotoPan();
    enrichPhotoPeople(item);
  }

  function stepViewer(delta) {
    const ids = visibleIds();
    const idx = ids.indexOf(state.modal.openId);
    if (idx < 0) return;
    const next = ids[idx + delta];
    if (!next) return;
    const item = rawItems.find((x) => x.id === next);
    if (!item) return;
    state.modal.openId = next;
    state.modal.pendingCorrection = null;
    state.modal.transcriptOn = false;
    state.modal.zoom = 1;
    renderViewer(item);
  }

  function closeModal() {
    hideQuickPreview();
    const snap = state.modal.snapshot;
    const pending = state.modal.pendingCorrection;
    state.modal.openId = null;
    state.modal.zoom = 1;
    state.modal.snapshot = null;
    state.modal.pendingCorrection = null;
    state.modal.transcriptOn = false;
    document.getElementById("mb-modal-body").innerHTML = "";
    const teach = document.getElementById("mb-modal-teach");
    if (teach) {
      teach.innerHTML = "";
      teach.hidden = true;
    }
    const foot = document.getElementById("mb-viewer-footer");
    if (foot) foot.innerHTML = "";
    const rail = document.getElementById("mb-rail-panel");
    if (rail) rail.innerHTML = "";
    document.getElementById("mb-modal").hidden = true;
    if (snap) restoreExplore(snap);
    if (pending) applyCorrectionConsequences(pending);
    render();
    requestAnimationFrame(() => {
      const g = document.getElementById("mb-explore-gallery");
      g.scrollTop = state.gallery.scrollTop || 0;
    });
  }

  function applyCorrectionConsequences(pending) {
    const item = rawItems.find((x) => x.id === pending.itemId);
    if (!item) return;
    item.face_identity = pending.personLabel;
    item.people = Array.isArray(item.people) ? item.people.slice() : [];
    if (pending.personLabel && !item.people.includes(pending.personLabel)) {
      item.people.push(pending.personLabel);
    }
    const note = `Identity updated: ${pending.personLabel}`;
    if (state.domain.summary && !state.domain.summary.includes(note)) {
      state.domain.summary = `${state.domain.summary} (${note})`;
    }
  }

  function faceBoxStyle(box) {
    const b = box;
    if (
      !b ||
      typeof b.x !== "number" ||
      typeof b.y !== "number" ||
      typeof b.w !== "number" ||
      typeof b.h !== "number"
    ) {
      return "";
    }
    return `left:${b.x * 100}%;top:${b.y * 100}%;width:${b.w * 100}%;height:${b.h * 100}%`;
  }

  function faceBoxesForItem(item) {
    const out = [];
    const faces = Array.isArray(item.faces) ? item.faces : [];
    faces.forEach((f) => {
      if (!f || typeof f !== "object") return;
      const box = f.face_box || f.box;
      const style = faceBoxStyle(box);
      if (!style) return;
      out.push({ style, name: f.name || f.display_name || "" });
    });
    if (!out.length && item.face_box) {
      const style = faceBoxStyle(item.face_box);
      if (style) {
        out.push({
          style,
          name: item.face_identity || item.mb_person_name || "",
        });
      }
    }
    return out;
  }

  function faceBoxHtml(item) {
    return faceBoxesForItem(item)
      .map((f) => {
        const label = escapeHtml(f.name || "");
        return `<div class="mb-face-box" style="${f.style}" title="${label || "Face"}">${
          label ? `<span class="mb-face-label">${label}</span>` : ""
        }</div>`;
      })
      .join("");
  }

  function peopleList(item) {
    const seen = [];
    const push = (n) => {
      const s = String(n || "").trim();
      if (!s) return;
      if (s.toLowerCase() === "unknown") return;
      if (s.toLowerCase() === "photo") return;
      if (!seen.includes(s)) seen.push(s);
    };
    if (Array.isArray(item.people)) item.people.forEach(push);
    push(item.face_identity);
    push(item.mb_person_name);
    // Ask-scoped person chips — why this result set exists (e.g. Show me Peggy).
    (state.domain.chips || []).forEach((c) => {
      if (c && c.kind === "person") push(c.label);
    });
    // Title often begins with the person name before " · place".
    const titleHead = String(item.title || "").split(" · ")[0].trim();
    push(titleHead);
    return seen;
  }

  function syncRailTabs() {
    const tab = state.modal.railTab || "people";
    document.querySelectorAll(".mb-rail-tab").forEach((btn) => {
      const on = btn.getAttribute("data-rail") === tab;
      btn.setAttribute("aria-selected", on ? "true" : "false");
    });
  }

  function sourceDetailsHtml(item) {
    const rows = [
      ["Type", String(item.type || "—").toUpperCase()],
      ["Date", fmtCardDate(item.date)],
      ["Location", item.place || item.location || item.city || "—"],
      ["Provider", item.provider_key || item.source || "—"],
      ["Original preserved", item.original_preserved === false ? "No" : "Yes"],
      ["File / id", item.original_filename || item.external_id || item.id || "—"],
    ];
    const exif =
      item.exif && typeof item.exif === "object" && !Array.isArray(item.exif)
        ? item.exif
        : null;
    const exifKeys = exif ? Object.keys(exif) : [];
    let exifBlock = "";
    if (exifKeys.length) {
      exifBlock =
        `<h3 id="mb-rail-exif" style="margin-top:1rem">Camera / EXIF</h3>` +
        exifKeys
          .map(
            (k) =>
              `<div class="mb-rail-meta-row"><dt>${escapeHtml(k)}</dt><dd>${escapeHtml(
                String(exif[k])
              )}</dd></div>`
          )
          .join("");
    } else {
      exifBlock =
        `<p id="mb-rail-exif" class="mb-rail-empty" style="margin-top:0.75rem">No camera EXIF on this asset. Shown when Immich/provider returns it.</p>`;
    }
    return (
      `<h3>Source details</h3>` +
      rows
        .map(
          ([k, v]) =>
            `<div class="mb-rail-meta-row"><dt>${escapeHtml(k)}</dt><dd>${escapeHtml(
              String(v)
            )}</dd></div>`
        )
        .join("") +
      exifBlock
    );
  }

  function renderRailTools(item) {
    const tools = document.getElementById("mb-rail-tools");
    if (!tools) return;
    const t = String(item.type || "").toLowerCase();
    if (t !== "photo") {
      tools.hidden = true;
      tools.innerHTML = "";
      return;
    }
    const zPct = Math.round((Number(state.modal.zoom) || 1) * 100);
    tools.hidden = false;
    tools.innerHTML = `
      <div class="mb-rail-tools-row" role="group" aria-label="Photo tools">
        <div class="mb-viewer-zoom" role="group" aria-label="Zoom">
          <button type="button" class="mb-viewer-footbtn" id="mb-zoom-out" aria-label="Zoom out">−</button>
          <span class="mb-viewer-zoom-label" id="mb-zoom-label">${zPct}%</span>
          <button type="button" class="mb-viewer-footbtn" id="mb-zoom-in" aria-label="Zoom in">+</button>
        </div>
        <button type="button" class="mb-viewer-footbtn" id="mb-rail-exif-btn">Exif</button>
        <button type="button" class="mb-viewer-footbtn" id="mb-viewer-share" title="Coming soon">Share</button>
        <button type="button" class="mb-viewer-footbtn" id="mb-rail-add-story">Add story</button>
      </div>`;
    const zin = document.getElementById("mb-zoom-in");
    const zout = document.getElementById("mb-zoom-out");
    if (zin) {
      zin.addEventListener("click", () => {
        state.modal.zoom = Math.min(
          3,
          Math.round(((Number(state.modal.zoom) || 1) + 0.05) * 100) / 100
        );
        const cur = rawItems.find((x) => x.id === state.modal.openId);
        if (cur) renderViewer(cur);
      });
    }
    if (zout) {
      zout.addEventListener("click", () => {
        state.modal.zoom = Math.max(
          0.5,
          Math.round(((Number(state.modal.zoom) || 1) - 0.05) * 100) / 100
        );
        const cur = rawItems.find((x) => x.id === state.modal.openId);
        if (cur) renderViewer(cur);
      });
    }
    const exifBtn = document.getElementById("mb-rail-exif-btn");
    if (exifBtn) {
      exifBtn.addEventListener("click", () => {
        state.modal.railTab = "people";
        syncRailTabs();
        const cur = rawItems.find((x) => x.id === state.modal.openId);
        if (cur) renderRailPanel(cur);
        requestAnimationFrame(() => {
          const el = document.getElementById("mb-rail-exif");
          if (el) el.scrollIntoView({ behavior: "smooth", block: "nearest" });
        });
      });
    }
    const shareBtn = document.getElementById("mb-viewer-share");
    if (shareBtn) {
      shareBtn.addEventListener("click", () => {
        window.alert("Share is coming soon — button stays; wiring is a later slice.");
      });
    }
    const addStory = document.getElementById("mb-rail-add-story");
    if (addStory) {
      addStory.addEventListener("click", () => {
        window.location.href = "/story/ui";
      });
    }
  }

  function renderRailPanel(item) {
    const panel = document.getElementById("mb-rail-panel");
    const teach = document.getElementById("mb-modal-teach");
    if (!panel) return;
    const tab = state.modal.railTab || "people";
    if (teach) teach.hidden = tab !== "learn";

    if (tab === "people") {
      const peeps = peopleList(item);
      let peopleHtml = "";
      if (!peeps.length) {
        peopleHtml =
          `<h3>People</h3><p class="mb-rail-empty">No people identified on this evidence yet. Use Learn to teach a face.</p>`;
      } else {
        peopleHtml =
          `<h3>People in this ${escapeHtml(item.type || "memory")}</h3>` +
          peeps
            .map((n) => {
              const initial = escapeHtml((n[0] || "?").toUpperCase());
              return `<div class="mb-rail-person"><span class="mb-rail-avatar" aria-hidden="true">${initial}</span><div><strong>${escapeHtml(
                n
              )}</strong><div style="font-size:0.72rem;color:#94a3b8">Confirmed / known</div></div></div>`;
            })
            .join("");
      }
      panel.innerHTML = peopleHtml + `<div class="mb-rail-source-block">${sourceDetailsHtml(item)}</div>`;
      return;
    }

    if (tab === "story") {
      const storyTitle = item.story_title || item.linked_story_title;
      const storyBody = item.story_excerpt || item.linked_story_excerpt;
      if (storyTitle || String(item.type || "").toLowerCase() === "story") {
        panel.innerHTML = `<h3>Story</h3>
          <p><strong>${escapeHtml(storyTitle || item.title || "Story")}</strong></p>
          <p class="mb-rail-empty">${escapeHtml(
            storyBody || item.detail || item.preview || ""
          )}</p>
          <p><a class="mb-viewer-footbtn" href="/story/ui">Read story</a></p>`;
        return;
      }
      panel.innerHTML = `<h3>Story</h3>
        <p class="mb-rail-empty">No story yet. Would you like to add one?</p>
        <p><a class="mb-viewer-footbtn" href="/story/ui">Add story</a></p>`;
      return;
    }

    if (tab === "artifact") {
      const art = item.artifact_title || item.linked_artifact_title;
      if (art || String(item.type || "").toLowerCase() === "artifact") {
        panel.innerHTML = `<h3>Artifact</h3>
          <p><strong>${escapeHtml(art || item.title || "Artifact")}</strong></p>
          <p class="mb-rail-empty">${escapeHtml(item.detail || item.preview || "")}</p>
          <p><a class="mb-viewer-footbtn" href="/artifact/ui">View artifact</a></p>`;
        return;
      }
      panel.innerHTML = `<h3>Artifact</h3>
        <p class="mb-rail-empty">No linked artifact on this evidence.</p>
        <p><a class="mb-viewer-footbtn" href="/artifact/ui">Browse artifacts</a></p>`;
      return;
    }

    if (tab === "source") {
      panel.innerHTML = sourceDetailsHtml(item);
      return;
    }


    if (tab === "learn") {
      panel.innerHTML = `<h3>Learn</h3>
        <p class="mb-rail-empty">Teach / correct identity from this evidence. Actions appear below when this item is teachable.</p>`;
    }
  }

  function renderViewerFooter(item) {
    const foot = document.getElementById("mb-viewer-footer");
    if (!foot) return;
    const t = String(item.type || "").toLowerCase();
    const bits = [];
    if (t === "photo") {
      // Photo tools live in the right rail (zoom / exif / share / add story).
    } else if (t === "video") {
      const t0 = item.t != null ? Number(item.t).toFixed(1) + "s" : "—";
      bits.push(`<span class="mb-ev-meta">Moment @ ${escapeHtml(t0)}</span>`);
      bits.push(
        `<button type="button" class="mb-viewer-footbtn" id="mb-transcript-toggle" aria-pressed="${
          state.modal.transcriptOn ? "true" : "false"
        }">Transcript ${state.modal.transcriptOn ? "on" : "off"}</button>`
      );
      if (item.play_url) {
        bits.push(
          `<a class="mb-viewer-footbtn" href="${escapeAttr(item.play_url)}">Open in Review</a>`
        );
      }
    } else {
      bits.push(
        `<span class="mb-ev-meta">${escapeHtml(fmtCardDate(item.date))} · ${escapeHtml(
          t || "evidence"
        )}</span>`
      );
    }
    foot.innerHTML = bits.join("");
    const tr = document.getElementById("mb-transcript-toggle");
    if (tr) {
      tr.addEventListener("click", () => {
        state.modal.transcriptOn = !state.modal.transcriptOn;
        const box = document.getElementById("mb-ev-transcript");
        if (box) box.classList.toggle("is-on", state.modal.transcriptOn);
        tr.setAttribute("aria-pressed", state.modal.transcriptOn ? "true" : "false");
        tr.textContent = `Transcript ${state.modal.transcriptOn ? "on" : "off"}`;
      });
    }
  }


  function renderTeachSlot(item) {
    const slot = document.getElementById("mb-modal-teach");
    if (!slot) return;
    const t = String(item.type || "").toLowerCase();
    const teachable =
      item.teachable ||
      t === "photo" ||
      (t === "video" && item.paused_frame !== false);
    if (!teachable) {
      slot.innerHTML =
        "Contextual Review &amp; Learn attaches here for photos, paused video frames, and future voice/transcript teaching — same viewer shell.";
      return;
    }
    const opts = (peopleOptions.length
      ? peopleOptions
      : [
          { id: "demo:peggy", label: "Peggy" },
          { id: "demo:rick", label: "Rick" },
          { id: "demo:tom", label: "Tom Will" },
        ]
    )
      .map(
        (p) =>
          `<option value="${escapeAttr(p.id)}" data-label="${escapeAttr(
            p.label
          )}">${escapeHtml(p.label)}</option>`
      )
      .join("");
    slot.innerHTML = `
      <div><strong>Selected face:</strong> <span id="mb-teach-current">${escapeHtml(
        item.face_identity || "Unknown"
      )}</span></div>
      <label style="display:block;margin:0.4rem 0 0.25rem">Assign / reassign
        <select id="mb-teach-person">${opts}</select>
      </label>
      <button type="button" class="mb-viewer-footbtn" id="mb-teach-confirm">Learn from this face</button>
      <div id="mb-teach-status" style="margin-top:0.35rem"></div>`;
    const btn = document.getElementById("mb-teach-confirm");
    if (btn) btn.addEventListener("click", () => confirmIdentityCorrection(item));
  }

  async function confirmIdentityCorrection(item) {
    const sel = document.getElementById("mb-teach-person");
    if (!sel) return;
    const opt = sel.options[sel.selectedIndex];
    const personId = sel.value;
    const personLabel = opt.getAttribute("data-label") || opt.textContent || "Person";
    const status = document.getElementById("mb-teach-status");
    const current = document.getElementById("mb-teach-current");

    state.modal.pendingCorrection = {
      itemId: item.id,
      personId,
      personLabel,
      at: Date.now(),
    };
    item.face_identity = personLabel;

    const livePerson = personId && !String(personId).startsWith("demo:");
    const vid = item.video_external_id;
    if (livePerson && vid) {
      try {
        const res = await fetch("/recognition/appearances/correct", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            person_id: personId,
            video_provider_key: item.video_provider_key || "hvrt",
            video_external_id: vid,
            start_sec: Number(item.t != null ? item.t : 0),
            end_sec: null,
            face_external_id: item.face_external_id || null,
          }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.detail || res.statusText);
        if (status) status.textContent = "Identity corrected via I1 owner path. Close to return.";
      } catch (err) {
        if (status)
          status.textContent =
            "Local correction recorded; live I1 call: " + err + " — close still restores context.";
      }
    } else if (status) {
      status.textContent =
        "Identity correction recorded (demo / photo path). Close returns to the same exploration context.";
    }
    if (current) current.textContent = personLabel;
  }

  function renderEvidenceBody(item) {
    const t = String(item.type || "").toLowerCase();
    const media = item.media_url || item.thumb_url || "";
    if (t === "photo") {
      const zoom = Number(state.modal.zoom) || 1;
      // Width-based zoom (not transform) so overflow scrolls inside the stage
      // and never paints over the footer controls.
      const zoomStyle =
        zoom === 1
          ? ""
          : ` style="width:${(zoom * 100).toFixed(2)}%;max-width:none;max-height:none;height:auto"`;
      const img = media
        ? `<img src="${escapeAttr(media)}" alt="${escapeAttr(
            item.title || "Photo"
          )}"${zoomStyle} />`
        : escapeHtml(item.preview || item.title || "Photo");
      return `<div class="mb-ev-photo${zoom !== 1 ? " is-zoomed" : ""}" aria-label="Photo workspace">
        <div class="mb-ev-photo-frame">${img}${faceBoxHtml(item)}</div>
      </div>`;
    }
    if (t === "video") {
      const poster = media
        ? `<img src="${escapeAttr(media)}" alt="" />`
        : "Paused frame · face teach applies here only (not during playback)";
      const t0 = item.t != null ? Number(item.t) : 0;
      return `<div class="mb-ev-video-shell">
        <div class="mb-ev-video-frame" id="mb-ev-video-frame">
          ${poster}
          ${faceBoxHtml(item)}
        </div>
        <div class="mb-ev-video-transport" aria-label="Video transport">
          <span>▶︎</span>
          <span>${t0.toFixed(1)}s · paused frame</span>
        </div>
        <div class="mb-ev-transcript" id="mb-ev-transcript" aria-label="Optional transcript (off by default)">
          <div class="is-active">[${String(Math.max(0, Math.floor(t0 - 2))).padStart(2, "0")}] …selectable speech span for speaker Learn…</div>
          <div>[${t0.toFixed(0)}] ${escapeHtml(
        item.detail || "Video moment ready for time-aligned teaching."
      )}</div>
        </div>
      </div>`;
    }
    if (t === "email" || t === "sms" || t === "text") {
      return `<div class="mb-ev-email">${escapeHtml(item.detail || item.preview || "")}</div>
        <p class="mb-ev-meta">${escapeHtml(fmtCardDate(item.date))} · Email / text</p>`;
    }
    if (t === "story") {
      return `<p class="mb-ev-meta">${escapeHtml(fmtCardDate(item.date))} · Story (contextual meaning)</p>
        <p>${escapeHtml(item.detail || "")}</p>`;
    }
    const img = media
      ? `<img src="${escapeAttr(media)}" alt="" style="max-width:100%;border-radius:10px" />`
      : `${escapeHtml(TYPE_GLYPH[t] || "•")} ${escapeHtml(item.preview || t)}`;
    return `<div class="mb-ev-photo">${img}</div>
      <p class="mb-ev-meta">${escapeHtml(fmtCardDate(item.date))}</p>
      <p>${escapeHtml(item.detail || "")}</p>`;
  }

  function quickPreviewHtml(item) {
    const t = String(item.type || "memory");
    const media = item.thumb_url || item.media_url || "";
    const peeps = peopleList(item).slice(0, 4).join(", ");
    const place = item.place || item.location || item.city || "";
    const dur =
      item.duration_sec != null
        ? `${Math.floor(item.duration_sec / 60)}:${String(
            Math.floor(item.duration_sec % 60)
          ).padStart(2, "0")}`
        : item.t != null
          ? `@ ${Number(item.t).toFixed(0)}s`
          : "";
    const mediaBlock = media
      ? `<div class="mb-qp-media"><img src="${escapeAttr(media)}" alt="" /></div>`
      : `<div class="mb-qp-media"><span>${escapeHtml(TYPE_GLYPH[t] || "•")}</span></div>`;
    return `${mediaBlock}<div class="mb-qp-body">
      <div class="mb-qp-type">${escapeHtml(t)}</div>
      <div class="mb-qp-title">${escapeHtml(item.title || t)}</div>
      <div class="mb-qp-line">${escapeHtml(fmtCardDate(item.date))}${
      place ? " · " + escapeHtml(place) : ""
    }</div>
      ${peeps ? `<div class="mb-qp-line">${escapeHtml(peeps)}</div>` : ""}
      ${
        item.preview
          ? `<div class="mb-qp-line">${escapeHtml(String(item.preview).slice(0, 120))}</div>`
          : ""
      }
      ${dur ? `<div class="mb-qp-line">${escapeHtml(dur)}</div>` : ""}
      ${
        item.provider_key
          ? `<div class="mb-qp-line">${escapeHtml(item.provider_key)}</div>`
          : ""
      }
    </div>`;
  }


  async function enrichPhotoPeople(item) {
    if (!item || String(item.type || "").toLowerCase() !== "photo") return;
    const eid = item.external_id;
    if (!eid || item._facesLoaded) return;
    try {
      const res = await fetch(
        `/explore/api/photo/${encodeURIComponent(eid)}/people`
      );
      if (!res.ok) return;
      const data = await res.json();
      const faces = Array.isArray(data.faces) ? data.faces : [];
      const names = Array.isArray(data.people) ? data.people : [];
      item._facesLoaded = true;
      if (faces.length) item.faces = faces;
      item.people = Array.isArray(item.people) ? item.people.slice() : [];
      names.forEach((n) => {
        const s = String(n || "").trim();
        if (s && s.toLowerCase() !== "unknown" && !item.people.includes(s)) {
          item.people.push(s);
        }
      });
      if (item.id !== state.modal.openId) return;
      document.getElementById("mb-modal-body").innerHTML = renderEvidenceBody(item);
      renderRailPanel(item);
      renderRailTools(item);
      bindPhotoPan();
    } catch (_err) {
      /* keep ask-scoped people */
    }
  }

  function bindPhotoPan() {
    if (state.modal._panCleanup) {
      state.modal._panCleanup();
      state.modal._panCleanup = null;
    }
    const stage = document.querySelector(".mb-ev-photo.is-zoomed");
    if (!stage) return;
    let dragging = false;
    let sx = 0;
    let sy = 0;
    let sl = 0;
    let st = 0;
    const onDown = (ev) => {
      if (ev.button !== 0) return;
      dragging = true;
      stage.classList.add("is-panning");
      sx = ev.clientX;
      sy = ev.clientY;
      sl = stage.scrollLeft;
      st = stage.scrollTop;
      ev.preventDefault();
    };
    const onMove = (ev) => {
      if (!dragging) return;
      stage.scrollLeft = sl - (ev.clientX - sx);
      stage.scrollTop = st - (ev.clientY - sy);
    };
    const onUp = () => {
      dragging = false;
      stage.classList.remove("is-panning");
    };
    stage.addEventListener("mousedown", onDown);
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    state.modal._panCleanup = () => {
      stage.removeEventListener("mousedown", onDown);
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }

  const QUICK_PREVIEW_DELAY_MS = 2500;

  function clearPreviewTimer() {
    if (state.preview && state.preview.timer) {
      clearTimeout(state.preview.timer);
      state.preview.timer = null;
    }
  }

  function hideQuickPreview() {
    clearPreviewTimer();
    if (state.preview) {
      state.preview.visible = false;
      state.preview.itemId = null;
    }
    const el = document.getElementById("mb-quick-preview");
    if (el) {
      el.hidden = true;
      el.innerHTML = "";
    }
  }

  function positionQuickPreviewAtPointer() {
    const el = document.getElementById("mb-quick-preview");
    if (!el || el.hidden || !state.preview) return;
    const pad = 8;
    const w = el.offsetWidth || 280;
    const h = el.offsetHeight || 200;
    let left = state.preview.x;
    let top = state.preview.y;
    // Upper-left of preview sits at pointer; nudge into viewport only.
    if (left + w > window.innerWidth - pad) left = Math.max(pad, window.innerWidth - w - pad);
    if (top + h > window.innerHeight - pad) top = Math.max(pad, window.innerHeight - h - pad);
    if (left < pad) left = pad;
    if (top < pad) top = pad;
    el.style.left = `${Math.round(left)}px`;
    el.style.top = `${Math.round(top)}px`;
  }

  function renderQuickPreview(item) {
    const el = document.getElementById("mb-quick-preview");
    if (!el || !item || !state.preview) return;
    el.innerHTML = quickPreviewHtml(item);
    el.hidden = false;
    state.preview.visible = true;
    state.preview.itemId = item.id;
    positionQuickPreviewAtPointer();
  }

  function scheduleQuickPreview(item, clientX, clientY) {
    if (!state.preview) {
      state.preview = { timer: null, itemId: null, x: 0, y: 0, visible: false };
    }
    clearPreviewTimer();
    state.preview.x = clientX;
    state.preview.y = clientY;
    state.preview.timer = setTimeout(() => {
      state.preview.timer = null;
      if (state.modal.openId) return;
      renderQuickPreview(item);
    }, QUICK_PREVIEW_DELAY_MS);
  }

  function bindCardPreview(card, id) {
    card.addEventListener("mouseenter", (ev) => {
      if (state.modal.openId) return;
      const it = rawItems.find((x) => x.id === id);
      if (it) scheduleQuickPreview(it, ev.clientX, ev.clientY);
    });
    card.addEventListener("mousemove", (ev) => {
      if (!state.preview || state.preview.visible) return;
      state.preview.x = ev.clientX;
      state.preview.y = ev.clientY;
    });
    card.addEventListener("mouseleave", hideQuickPreview);
    card.addEventListener("focus", () => {
      if (state.modal.openId) return;
      const it = rawItems.find((x) => x.id === id);
      if (!it) return;
      const r = card.getBoundingClientRect();
      scheduleQuickPreview(it, r.left, r.top);
    });
    card.addEventListener("blur", hideQuickPreview);
  }

  // ——— Timeline interaction ———

  function trackFrac(clientX) {
    if (!hasDatedExtent()) return NaN;
    const track = document.getElementById("mb-tl-track");
    const r = track.getBoundingClientRect();
    const x = Math.min(1, Math.max(0, (clientX - r.left) / r.width));
    return state.timeline.extentStart + x * (state.timeline.extentEnd - state.timeline.extentStart);
  }

  /** Handle drag may move past the visible axis toward the full archive span. */
  function trackFracHandle(clientX) {
    if (!hasDatedExtent()) return NaN;
    const track = document.getElementById("mb-tl-track");
    const r = track.getBoundingClientRect();
    const fullA = Number.isFinite(state.timeline.fullExtentStart)
      ? state.timeline.fullExtentStart
      : state.timeline.extentStart;
    const fullB = Number.isFinite(state.timeline.fullExtentEnd)
      ? state.timeline.fullExtentEnd
      : state.timeline.extentEnd;
    const extA = state.timeline.extentStart;
    const extB = state.timeline.extentEnd;
    const span = Math.max(extB - extA, 1);
    // Allow overshoot past track edges so range can expand toward fullExtent
    const x = (clientX - r.left) / r.width;
    const t = extA + x * span;
    return Math.min(fullB, Math.max(fullA, t));
  }

  /** Proportional scrub: playhead → chronological neighborhood without huge jumps. */
  function scrollGalleryToward(ms, opts) {
    opts = opts || {};
    const items = visibleItems();
    if (!items.length) return;
    const gallery = document.getElementById("mb-explore-gallery");
    const datedIdx = [];
    items.forEach((it, i) => {
      if (isDated(it)) datedIdx.push({ i, t: parseISO(it.date) });
    });
    if (!datedIdx.length) return;
    datedIdx.sort((a, b) => a.t - b.t);

    let best = datedIdx[0];
    for (let k = 0; k < datedIdx.length; k++) {
      if (datedIdx[k].t <= ms) best = datedIdx[k];
      else break;
    }
    // If closer to next neighbor, ease toward it (continuous neighborhood)
    const next = datedIdx.find((d) => d.t > best.t);
    let cardIndex = best.i;
    if (next && next.t !== best.t) {
      const frac = (ms - best.t) / (next.t - best.t);
      if (frac > 0.55) cardIndex = next.i;
    }

    const cards = gallery.querySelectorAll(".mb-card");
    const card = cards[cardIndex];
    if (!card) return;
    const behavior = opts.smooth ? "smooth" : "auto";
    const target =
      card.offsetTop - Math.max(0, (gallery.clientHeight - card.offsetHeight) / 3);
    if (opts.smooth) {
      card.scrollIntoView({ inline: "nearest", block: "nearest", behavior });
    } else {
      gallery.scrollTop = Math.max(0, target);
    }
    state.gallery.scrollTop = gallery.scrollTop;
  }

  function bindTimeline() {
    const track = document.getElementById("mb-tl-track");
    const hl = document.getElementById("mb-tl-handle-l");
    const hr = document.getElementById("mb-tl-handle-r");

    document.getElementById("mb-tl-reset").addEventListener("click", () => {
      resetTimelineExtent(true);
    });

    const nudge = (dir) => {
      if (!hasDatedExtent()) return;
      const span = state.timeline.extentEnd - state.timeline.extentStart;
      const step = span * 0.04 * dir;
      let next = state.timeline.playhead + step;
      next = Math.min(state.timeline.extentEnd, Math.max(state.timeline.extentStart, next));
      state.timeline.playhead = next;
      scrollGalleryToward(next);
      renderTimeline();
    };
    document.getElementById("mb-tl-nudge-l").addEventListener("click", () => nudge(-1));
    document.getElementById("mb-tl-nudge-r").addEventListener("click", () => nudge(1));

    // Band drag = redefine active range (explore period)
    track.addEventListener("pointerdown", (e) => {
      if (!hasDatedExtent()) return;
      if (e.target.classList.contains("mb-tl-handle")) return;
      const t = trackFrac(e.clientX);
      // Click near playhead → scrub; elsewhere start band
      const nearPlay =
        Math.abs(t - state.timeline.playhead) <
        (state.timeline.extentEnd - state.timeline.extentStart) * 0.03;
      if (nearPlay || e.shiftKey) {
        scrubDrag = { last: t };
        track.setPointerCapture(e.pointerId);
        state.timeline.playhead = t;
        scrollGalleryToward(t);
        renderTimeline();
        return;
      }
      bandDrag = { a: t, b: t };
      track.setPointerCapture(e.pointerId);
    });

    track.addEventListener("pointermove", (e) => {
      if (handleDrag) {
        const t = trackFracHandle(e.clientX);
        if (handleDrag === "l") {
          setActiveRange(t, state.timeline.rangeEnd);
        } else {
          setActiveRange(state.timeline.rangeStart, t);
        }
        render();
        return;
      }
      if (scrubDrag) {
        const t = trackFrac(e.clientX);
        scrubDrag.last = t;
        state.timeline.playhead = t;
        // Continuous proportional neighborhood sync (no huge jumps / no drift)
        scrollGalleryToward(t, { smooth: false });
        renderTimeline();
        return;
      }
      if (bandDrag) {
        bandDrag.b = trackFrac(e.clientX);
        // live preview band
        const a = Math.min(bandDrag.a, bandDrag.b);
        const b = Math.max(bandDrag.a, bandDrag.b);
        const span = state.timeline.extentEnd - state.timeline.extentStart;
        const band = document.getElementById("mb-tl-band");
        band.style.left = `${((a - state.timeline.extentStart) / span) * 100}%`;
        band.style.width = `${((b - a) / span) * 100}%`;
      }
    });

    track.addEventListener("pointerup", (e) => {
      if (handleDrag) {
        endHandle();
        return;
      }
      if (bandDrag) {
        const a = Math.min(bandDrag.a, bandDrag.b);
        const b = Math.max(bandDrag.a, bandDrag.b);
        bandDrag = null;
        if (b - a > (state.timeline.extentEnd - state.timeline.extentStart) * 0.01) {
          setActiveRange(a, b);
          zoomTimelineToRange();
          render();
        } else {
          // tap: move playhead + scrub gallery
          state.timeline.playhead = a;
          scrollGalleryToward(a);
          renderTimeline();
        }
        return;
      }
      scrubDrag = null;
    });

    hl.addEventListener("pointerdown", (e) => {
      if (!hasDatedExtent()) return;
      e.stopPropagation();
      handleDrag = "l";
      handleDragMeta = {
        side: "l",
        startA: state.timeline.rangeStart,
        startB: state.timeline.rangeEnd,
      };
      hl.setPointerCapture(e.pointerId);
    });
    hr.addEventListener("pointerdown", (e) => {
      if (!hasDatedExtent()) return;
      e.stopPropagation();
      handleDrag = "r";
      handleDragMeta = {
        side: "r",
        startA: state.timeline.rangeStart,
        startB: state.timeline.rangeEnd,
      };
      hr.setPointerCapture(e.pointerId);
    });
    // Slight outward pull while zoomed → restore full archive span
    function endHandle() {
      if (!handleDrag) return;
      const side = handleDrag;
      const origin = handleDragMeta;
      handleDrag = null;
      handleDragMeta = null;
      if (!hasDatedExtent()) {
        render();
        return;
      }
      const fullA = Number.isFinite(state.timeline.fullExtentStart)
        ? state.timeline.fullExtentStart
        : state.timeline.extentStart;
      const fullB = Number.isFinite(state.timeline.fullExtentEnd)
        ? state.timeline.fullExtentEnd
        : state.timeline.extentEnd;
      const extA = state.timeline.extentStart;
      const extB = state.timeline.extentEnd;
      const rA = state.timeline.rangeStart;
      const rB = state.timeline.rangeEnd;
      const viewSpan = Math.max(extB - extA, 1);
      const zoomed =
        extA > fullA + viewSpan * 0.005 || extB < fullB - viewSpan * 0.005;
      const pulledLeftOut =
        side === "l" &&
        origin &&
        Number.isFinite(origin.startA) &&
        rA < origin.startA - 1;
      const pulledRightOut =
        side === "r" &&
        origin &&
        Number.isFinite(origin.startB) &&
        rB > origin.startB + 1;
      const pastViewEdge =
        (side === "l" && rA < extA - 1) || (side === "r" && rB > extB + 1);
      if (zoomed && (pulledLeftOut || pulledRightOut || pastViewEdge)) {
        resetTimelineExtent(true);
        return;
      }
      zoomTimelineToRange();
      render();
    }
    hl.addEventListener("pointerup", endHandle);
    hr.addEventListener("pointerup", endHandle);
    hl.addEventListener("pointercancel", endHandle);
    hr.addEventListener("pointercancel", endHandle);
  }

  function bindChrome() {
    document.getElementById("mb-explore-ask-go").addEventListener("click", () => {
      applyAskCommand(document.getElementById("mb-explore-ask").value);
    });
    document.getElementById("mb-explore-ask").addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        applyAskCommand(e.target.value);
      }
    });
    document.getElementById("mb-density-minus").addEventListener("click", () => {
      state.gallery.density = Math.max(1, state.gallery.density - 1);
      renderGallery();
    });
    document.getElementById("mb-density-plus").addEventListener("click", () => {
      state.gallery.density = Math.min(3, state.gallery.density + 1);
      renderGallery();
    });
    const sortEl = document.getElementById("mb-explore-sort");
    if (sortEl) {
      sortEl.addEventListener("change", () => {
        state.gallery.sort = sortEl.value === "oldest" ? "oldest" : "newest";
        renderGallery();
      });
    }
    const gBtn = document.getElementById("mb-view-gallery");
    const mBtn = document.getElementById("mb-view-map");
    if (gBtn) {
      gBtn.addEventListener("click", () => {
        setViewMode("gallery");
        render();
      });
    }
    if (mBtn) {
      mBtn.addEventListener("click", () => {
        setViewMode("map");
        render();
      });
    }
    const clearRefine = document.getElementById("mb-map-clear-refine");
    if (clearRefine) {
      clearRefine.addEventListener("click", () => {
        setMapRefine(null);
        render();
      });
    }
    const undatedTl = document.getElementById("mb-tl-undated");
    if (undatedTl) {
      undatedTl.addEventListener("click", () => {
        setUndatedFilter(!state.domain.undatedFilter);
        render();
      });
    }
    document.getElementById("mb-modal-close").addEventListener("click", closeModal);
    document.getElementById("mb-modal").addEventListener("click", (e) => {
      if (e.target.id === "mb-modal") closeModal();
    });
    const prevBtn = document.getElementById("mb-viewer-prev");
    const nextBtn = document.getElementById("mb-viewer-next");
    if (prevBtn) prevBtn.addEventListener("click", () => stepViewer(-1));
    if (nextBtn) nextBtn.addEventListener("click", () => stepViewer(1));
    document.querySelectorAll(".mb-rail-tab").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.modal.railTab = btn.getAttribute("data-rail") || "people";
        const item = rawItems.find((x) => x.id === state.modal.openId);
        if (!item) return;
        syncRailTabs();
        renderRailPanel(item);
        renderTeachSlot(item);
      });
    });
    document.addEventListener("keydown", (e) => {
      if (!state.modal.openId) return;
      if (e.key === "Escape") closeModal();
      if (e.key === "ArrowLeft") stepViewer(-1);
      if (e.key === "ArrowRight") stepViewer(1);
    });
    const gallery = document.getElementById("mb-explore-gallery");
    gallery.addEventListener("scroll", () => {
      state.gallery.scrollTop = gallery.scrollTop;
      hideQuickPreview();
    });
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
  function escapeAttr(s) {
    return escapeHtml(s).replace(/'/g, "&#39;");
  }

  function bootFromPayload(payload) {
    liveMode = !payload.demo;
    applyPayloadToState(payload, { keepPresentation: false });
    ensureLockedPersonChip();
    syncActivePersonContext();
    renderNav();
    bindChrome();
    bindTimeline();
    render();
    loadPeopleOptions().then(() => {
      syncActivePersonContext();
      renderNav();
    });
  }

  async function loadPeopleOptions() {
    const fallback = [
      { id: "demo:peggy", label: "Peggy" },
      { id: "demo:rick", label: "Rick" },
      { id: "demo:tom", label: "Tom Will" },
    ];
    try {
      const res = await fetch("/people/picker-options");
      if (!res.ok) throw new Error(String(res.status));
      const data = await res.json();
      const opts = (data.options || data.people || []).map((p) => ({
        id: String(p.id || p.person_id || ""),
        label: String(p.display_name || p.name || p.label || "Person"),
      })).filter((p) => p.id);
      peopleOptions = opts.length ? opts : fallback;
    } catch (_) {
      peopleOptions = fallback;
    }
    return peopleOptions;
  }

  async function main() {
    const params = new URLSearchParams(location.search);
    const demo = params.get("demo");
    const q = params.get("q") || "";
    sessionId =
      params.get("session_id") ||
      localStorage.getItem("mb_ask_session") ||
      null;
    try {
      let payload;
      if (demo) {
        // Explicit demo/prove path only — not required for real experience
        const res = await fetch(`/explore/api/demo/${encodeURIComponent(demo)}`);
        if (!res.ok) throw new Error(`demo ${res.status}`);
        payload = await res.json();
      } else if (PERSON_MODE) {
        const seed = q || ("Show " + (PERSON.displayName || "person"));
        payload = await liveFind(seed);
        if (payload.session_id) {
          localStorage.setItem("mb_ask_session", payload.session_id);
        }
      } else {
        payload = await liveFind(q);
        if (payload.session_id) {
          localStorage.setItem("mb_ask_session", payload.session_id);
        }
      }
      bootFromPayload(payload);
    } catch (err) {
      document.getElementById("mb-explore-curator-body").textContent =
        "Could not load exploration: " + err;
    }
  }

  main();
})();
