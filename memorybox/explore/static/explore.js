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

  // Ask command examples (typed today; STT later shares applyAskCommand):
  // "Only photos." "Add video." "Clear filters." "Show everything."
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

  function matchesType(item, filter) {
    if (!filter || filter === "all") return true;
    const t = String(item.type || "").toLowerCase();
    if (filter === "email") return t === "email" || t === "sms" || t === "text";
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
    const list = eligible.filter((it) => {
      if (undatedOnly) return isUndated(it);
      if (isUndated(it)) return true; // never exclude undated from gallery
      if (!hasRange) return true;
      const t = parseISO(it.date);
      return Number.isFinite(t) && t >= rangeStart && t <= rangeEnd;
    });
    list.sort((a, b) => {
      if (isUndated(a) && isUndated(b)) return 0;
      if (isUndated(a)) return sort === "oldest" ? -1 : 1;
      if (isUndated(b)) return sort === "oldest" ? 1 : -1;
      const d = parseISO(a.date) - parseISO(b.date);
      return sort === "oldest" ? d : -d;
    });
    return list;
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
    state.timeline.extentStart = ext.start;
    state.timeline.extentEnd = ext.end;
    state.timeline.rangeStart = ext.start;
    state.timeline.rangeEnd = ext.end;
    state.timeline.precision = computePrecision(ext.start, ext.end);
    state.timeline.playhead = ext.start;
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
      ? "undated memories (off Timeline axis — use Undated filter)"
      : hasDatedExtent()
        ? fmtRangeLabel(
            state.timeline.rangeStart,
            state.timeline.rangeEnd,
            state.timeline.precision
          )
        : "no dated memories";
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

  async function liveFind(askText) {
    const q = String(askText || "").trim();
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
    const viewMode =
      keepPresentation && state ? state.gallery.viewMode || "gallery" : "gallery";
    const typeFilter =
      keepPresentation && state ? state.domain.typeFilter : "all";
    const undatedFilter =
      keepPresentation && state ? Boolean(state.domain.undatedFilter) : false;
    const chips = payload.chips || [];
    // Keep prior place filter across re-find; chips are activatable (not auto-forced).
    let placeFilter = null;
    if (keepPresentation && state && state.domain.placeFilter) {
      placeFilter = state.domain.placeFilter;
    }
    const ext = extentOf(
      rawItems.filter(
        (it) =>
          isDated(it) &&
          matchesType(it, typeFilter) &&
          matchesPlace(it, placeFilter)
      )
    );
    const emptyTl = Boolean(ext.empty);
    state = {
      domain: {
        askText: payload.ask_text || "",
        title: payload.title || "Memories",
        summary: payload.summary || "",
        _fixtureSummary: payload.demo ? payload.summary || "" : "",
        chips: chips,
        typeFilter: typeFilter,
        placeFilter: placeFilter,
        undatedFilter: undatedFilter,
        mapRefineIds: null,
        items: [],
      },
      timeline: {
        extentStart: emptyTl ? NaN : ext.start,
        extentEnd: emptyTl ? NaN : ext.end,
        rangeStart: emptyTl ? NaN : ext.start,
        rangeEnd: emptyTl ? NaN : ext.end,
        playhead: emptyTl ? NaN : ext.start,
        precision: emptyTl ? "years" : computePrecision(ext.start, ext.end),
        empty: emptyTl,
      },
      gallery: {
        density: dens,
        scrollTop: scrollTop,
        sort: sort,
        viewMode: viewMode,
      },
      modal: { openId: null, snapshot: null, pendingCorrection: null },
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

    // Navigation / clear context
    if (/clear context.*people|go to people/.test(lower)) {
      window.location.href = "/people/ui";
      return;
    }

    if (/^clear filters\.?$/.test(lower) || /^show everything\.?$/.test(lower)) {
      setTypeFilter("all");
      clearPlaceFilter();
      setUndatedFilter(false);
      setViewMode("gallery");
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

    // Location filter on current result set (Ask/STT same path)
    const placeOnly = lower.match(
      /^(?:only|near|around|at)\s+([a-z0-9][a-z0-9'’.\-\s]{1,40})\.?$/i
    );
    if (placeOnly) {
      const candidate = placeOnly[1].replace(/\.$/, "").trim();
      const blocked = /^(photos?|videos?|emails?|texts?|artifacts?|stories?|everything|map|gallery)$/i;
      if (candidate && !blocked.test(candidate)) {
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
    if (/only (email|emails|text)/.test(lower)) {
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

    // New find query — live path re-runs Ask; demo path keeps fixture membership
    if (liveMode) {
      liveFind(text)
        .then((payload) => {
          applyPayloadToState(payload, { keepPresentation: true });
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
    let a = Math.min(start, end);
    let b = Math.max(start, end);
    a = Math.max(a, state.timeline.extentStart);
    b = Math.min(b, state.timeline.extentEnd);
    if (b - a < 86400000) b = a + 86400000;
    state.timeline.rangeStart = a;
    state.timeline.rangeEnd = b;
    state.timeline.precision = computePrecision(a, b);
    state.timeline.playhead = a;
    state.domain.mapRefineIds = null;
  }

  function resetTimelineExtent(andRender) {
    // Reset = full temporal extent of current eligible set. Does NOT clear query/filters.
    if (!hasDatedExtent()) {
      if (andRender) render();
      return;
    }
    state.timeline.rangeStart = state.timeline.extentStart;
    state.timeline.rangeEnd = state.timeline.extentEnd;
    state.timeline.precision = computePrecision(
      state.timeline.rangeStart,
      state.timeline.rangeEnd
    );
    state.timeline.playhead = state.timeline.extentStart;
    if (andRender) render();
  }

  // ——— Render ———

  function renderNav() {
    const el = document.getElementById("mb-explore-nav");
    if (!el) return;
    el.innerHTML = NAV.map(
      (n) =>
        `<a href="${n.href}" data-nav="${n.id}"${
          n.id === "ask" ? ' aria-current="page"' : ""
        }><span class="mb-nav-ico" aria-hidden="true">${n.ico}</span>${n.label}</a>`
    ).join("");
  }

  // Expose for shell Global Ask + future STT — same applyAskCommand path.
  window.mbExploreApplyAsk = applyAskCommand;

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
        return `<span class="${cls}" data-kind="${escapeAttr(kind)}">${escapeHtml(
          label
        )}</span>`;
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
      const person = (state.domain.chips || []).find((c) => c.kind === "person");
      const label = (person && person.label) || state.domain.title || "M";
      av.textContent = String(label).trim().charAt(0).toUpperCase() || "M";
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
    // Map is opt-in via filter bar (not a default Gallery|Map takeover)
    {
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
      card.addEventListener("click", () => openModal(card.getAttribute("data-id")));
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
      const left = ((rangeStart - extentStart) / span) * 100;
      const right = ((rangeEnd - extentStart) / span) * 100;
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
    if (empty) {
      dotsEl.innerHTML = "";
    } else {
      const span = Math.max(extentEnd - extentStart, 1);
      dotsEl.innerHTML = typedDated
        .map((it) => {
          const t = parseISO(it.date);
          if (!Number.isFinite(t)) return "";
          const x = ((t - extentStart) / span) * 100;
          return `<span class="mb-tl-dot" style="left:${x}%" title="${escapeAttr(it.date)}"></span>`;
        })
        .join("");
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
    renderCurator();
    renderFilters();
    renderViewMode();
    renderGallery();
    renderMap();
    renderTimeline();
  }

  // ——— Modal ———

  function openModal(id) {
    const item = rawItems.find((x) => x.id === id);
    if (!item) return;
    state.gallery.scrollTop =
      document.getElementById("mb-explore-gallery").scrollTop || 0;
    state.modal.snapshot = snapshotExplore();
    state.modal.openId = id;
    state.modal.pendingCorrection = null;

    const modal = document.getElementById("mb-modal");
    document.getElementById("mb-modal-kicker").textContent = String(
      item.type || "Evidence"
    ).toUpperCase();
    document.getElementById("mb-modal-title").textContent = item.title || item.id;
    const body = document.getElementById("mb-modal-body");
    body.innerHTML = renderEvidenceBody(item);
    renderTeachSlot(item);
    modal.hidden = false;
    document.getElementById("mb-modal-close").focus();
  }

  function closeModal() {
    const snap = state.modal.snapshot;
    const pending = state.modal.pendingCorrection;
    state.modal.openId = null;
    state.modal.snapshot = null;
    state.modal.pendingCorrection = null;
    document.getElementById("mb-modal-body").innerHTML = "";
    document.getElementById("mb-modal-teach").innerHTML = "";
    document.getElementById("mb-modal").hidden = true;
    // 1) Restore prior exploration state/position
    if (snap) restoreExplore(snap);
    // 2) Then incorporate correction consequences without dumping to a new default
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
    // Soft curator note — do not reset filters/range/query
    const note = `Identity updated: ${pending.personLabel}`;
    if (state.domain.summary && !state.domain.summary.includes(note)) {
      state.domain.summary = `${state.domain.summary} (${note})`;
    }
  }

  function faceBoxStyle(item) {
    const b = item && item.face_box;
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

  function faceBoxHtml(item) {
    const style = faceBoxStyle(item);
    if (!style) return "";
    return `<div class="mb-face-box" style="${style}" title="Face region"></div>`;
  }

  function renderTeachSlot(item) {
    const slot = document.getElementById("mb-modal-teach");
    const t = String(item.type || "").toLowerCase();
    const teachable =
      item.teachable ||
      t === "photo" ||
      (t === "video" && (item.paused_frame !== false));
    if (!teachable) {
      slot.innerHTML =
        "Contextual Review &amp; Learn attaches here for photos, paused video frames, and future voice/transcript teaching — same modal shell.";
      return;
    }
    const opts = (peopleOptions.length ? peopleOptions : [
      { id: "demo:peggy", label: "Peggy" },
      { id: "demo:rick", label: "Rick" },
      { id: "demo:tom", label: "Tom Will" },
    ])
      .map(
        (p) =>
          `<option value="${escapeAttr(p.id)}" data-label="${escapeAttr(p.label)}">${escapeHtml(
            p.label
          )}</option>`
      )
      .join("");
    const current = escapeHtml(item.face_identity || "Unknown");
    slot.innerHTML = `<div class="mb-teach-proof" data-i1-teach-proof="1">
      <h3>Review &amp; Learn — face identity (I1 path)</h3>
      <p class="mb-teach-status">Current assignment: <strong id="mb-teach-current">${current}</strong></p>
      <div class="mb-teach-row">
        <label for="mb-teach-person">Correct identity</label>
        <select id="mb-teach-person">${opts}</select>
        <button type="button" id="mb-teach-correct">Confirm identity</button>
      </div>
      <p class="mb-teach-status" id="mb-teach-status">Uses the owner identity-correction path. Close returns to the same exploration context.</p>
    </div>`;
    document.getElementById("mb-teach-correct").addEventListener("click", () => {
      confirmIdentityCorrection(item);
    });
  }

  async function confirmIdentityCorrection(item) {
    const sel = document.getElementById("mb-teach-person");
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

    // Live I1 API when we have a real person id + video moment coordinates
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
    } else {
      if (status)
        status.textContent =
          "Identity correction recorded (demo / photo path). Close returns to the same exploration context.";
    }
    if (current) current.textContent = personLabel;
  }

  function renderEvidenceBody(item) {
    const t = String(item.type || "").toLowerCase();
    const media = item.media_url || item.thumb_url || "";
    if (t === "photo") {
      const img = media
        ? `<img src="${escapeAttr(media)}" alt="${escapeAttr(item.title || "Photo")}" />`
        : escapeHtml(item.preview || item.title || "Photo");
      return `<div class="mb-ev-photo" aria-label="Photo workspace">${img}
        ${faceBoxHtml(item)}
      </div>
      <p class="mb-ev-meta">${escapeHtml(fmtCardDate(item.date))} · Photo evidence · Face: ${escapeHtml(
        item.face_identity || "Unknown"
      )}</p>
      <p>${escapeHtml(item.detail || "")}</p>`;
    }
    if (t === "video") {
      const poster = media
        ? `<img src="${escapeAttr(media)}" alt="" />`
        : "Paused frame · face teach applies here only (not during playback)";
      const jump = item.play_url
        ? `<p><a class="mb-ev-jump" href="${escapeAttr(item.play_url)}">Open moment in Review @ ${
            item.t != null ? Number(item.t).toFixed(1) + "s" : "?"
          }</a></p>`
        : "";
      return `<div class="mb-ev-video">
        <div class="mb-ev-video-frame" id="mb-ev-video-frame" style="position:relative">
          ${poster}
          ${faceBoxHtml(item)}
        </div>
        <div class="mb-ev-transcript" aria-label="Time-aligned transcript (prepared)">
          <strong>Transcript (architecture)</strong><br/>
          [00:12] …speech span selectable for speaker ID / Learn from voice…<br/>
          ${escapeHtml(item.detail || "Video moment ready for time-aligned teaching.")}
        </div>
      </div>
      ${jump}
      <p class="mb-ev-meta">${escapeHtml(fmtCardDate(item.date))} · Video moment · Face: ${escapeHtml(
        item.face_identity || "Unknown"
      )}</p>`;
    }
    if (t === "email" || t === "sms" || t === "text") {
      return `<div class="mb-ev-email">${escapeHtml(item.detail || item.preview || "")}</div>
        <p class="mb-ev-meta">${escapeHtml(fmtCardDate(item.date))} · Email / text</p>`;
    }
    if (t === "story") {
      return `<p class="mb-ev-meta">${escapeHtml(fmtCardDate(item.date))} · Story (contextual meaning)</p>
        <p>${escapeHtml(item.detail || "")}</p>
        <p style="color:var(--mb-muted);font-size:13px">Stories stay tied to people / evidence / events — not a disconnected writing surface in I4.</p>`;
    }
    const img = media
      ? `<img src="${escapeAttr(media)}" alt="" />`
      : `${escapeHtml(TYPE_GLYPH[t] || "•")} ${escapeHtml(item.preview || t)}`;
    return `<div class="mb-ev-photo" data-type="${escapeAttr(t)}" style="min-height:160px">${img}</div>
      <p class="mb-ev-meta">${escapeHtml(fmtCardDate(item.date))} · ${escapeHtml(t)}</p>
      <p>${escapeHtml(item.detail || "")}</p>`;
  }

  // ——— Timeline interaction ———

  function trackFrac(clientX) {
    if (!hasDatedExtent()) return NaN;
    const track = document.getElementById("mb-tl-track");
    const r = track.getBoundingClientRect();
    const x = Math.min(1, Math.max(0, (clientX - r.left) / r.width));
    return state.timeline.extentStart + x * (state.timeline.extentEnd - state.timeline.extentStart);
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
        const t = trackFrac(e.clientX);
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
      if (bandDrag) {
        const a = Math.min(bandDrag.a, bandDrag.b);
        const b = Math.max(bandDrag.a, bandDrag.b);
        bandDrag = null;
        if (b - a > (state.timeline.extentEnd - state.timeline.extentStart) * 0.01) {
          setActiveRange(a, b);
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
      handleDrag = null;
    });

    hl.addEventListener("pointerdown", (e) => {
      if (!hasDatedExtent()) return;
      e.stopPropagation();
      handleDrag = "l";
      hl.setPointerCapture(e.pointerId);
    });
    hr.addEventListener("pointerdown", (e) => {
      if (!hasDatedExtent()) return;
      e.stopPropagation();
      handleDrag = "r";
      hr.setPointerCapture(e.pointerId);
    });
    const endHandle = () => {
      handleDrag = null;
    };
    hl.addEventListener("pointerup", endHandle);
    hr.addEventListener("pointerup", endHandle);
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
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && state.modal.openId) closeModal();
    });
    const gallery = document.getElementById("mb-explore-gallery");
    gallery.addEventListener("scroll", () => {
      state.gallery.scrollTop = gallery.scrollTop;
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
    renderNav();
    bindChrome();
    bindTimeline();
    render();
    loadPeopleOptions();
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
