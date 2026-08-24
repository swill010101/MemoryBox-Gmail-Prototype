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
    { id: "memory", label: "Memory" },
    { id: "photo", label: "Photos" },
    { id: "video", label: "Video" },
    { id: "email", label: "Communications" }, // I7 Email/Text
    { id: "calendar", label: "Calendar" },
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
    { id: "ask", label: "Ask", href: "/explore/ui", ico: "?" },
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
    const commsAt = FILTERS.findIndex((f) => f.id === "email");
    FILTERS.splice(commsAt >= 0 ? commsAt : 3, 0, { id: "audio", label: "Audio" });
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

  // MBQL-001 shared verb ids — must match memorybox/mbql/verbs.py VERB_IDS
  const MBQL_VERBS = {
    clear_filters: /^clear filters\.?$/i,
    show_everything: /^show everything\.?$/i,
    only_undated: /^only undated\.?$|^undated\.?$|^show undated\.?$/i,
    clear_undated: /^clear undated\.?$|^include dated\.?$/i,
    show_map: /^show map\.?$|^map view\.?$|^on the map\.?$/i,
    show_gallery: /^show gallery\.?$|^gallery view\.?$|^list view\.?$/i,
    clear_place: /^clear location\.?$|^clear place\.?$|^clear map selection\.?$/i,
    clear_time: /^clear date\.?$|^clear time\.?$|^clear timeline\.?$/i,
    reset: /^reset\.?$/i,
    reset_timeline: /^reset timeline\.?$|^full result range\.?$|^reset range\.?$/i,
    only_photos: /^only photos?\.?$|^photos?\.?$/i,
    only_video: /^only videos?\.?$/i,
    add_video: /^add video\.?$/i,
    add_texts: /^(add|include)\s+(texts?|sms|imessage|i-?message)s?\.?$|^add texts?\.?$/i,
    only_texts: /^only (texts?|sms|imessage|i-?message)\b/i,
    add_email: /^(add|include)\s+(e-?mails?)\.?$/i,
    only_email: /^only (e-?mails?)\b/i,
    add_communications: /^(add|include)\s+communications?\.?$|^add comms\.?$/i,
    add_calendar: /^(add|include)\s+calendar\.?$/i,
    only_calendar: /^only calendar\.?$/i,
    attachments_only: /^attachments only\.?$|^only attachments\.?$/i,
    show_memory: /^memory\.?$|^show memory\.?$|^memory view\.?$/i,
    only_artifacts: /^only artifacts?\.?$/i,
    only_stories: /^only stories?\.?$/i,
    go_to_people: /clear context.*people|go to people/i,
    go_to_person: /^(?:go to\s+(.+?)\s+instead|select\s+(.+?)|switch to\s+(.+?))\.?$/i,
  };

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
  let chromeBound = false;
  let timelineBound = false;
  let findGen = 0;
  let pendingPresent = null;
  let histHydrate = null;

  function bumpFindGen() {
    pendingPresent = null;
    setGalleryLocked(false);
    return ++findGen;
  }

  function dayMs(y, m, d) {
    return Date.UTC(y, m - 1, d);
  }

  function parseISO(s) {
    if (!s) return NaN;
    const raw = String(s || "").trim();
    if (/^\d{4}$/.test(raw)) return dayMs(+raw, 1, 1);
    const p = raw.slice(0, 10).split("-");
    if (p.length === 2 && p[0] && p[1]) return dayMs(+p[0], +p[1], 1);
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
      item.original_filename,
      item.exif && item.exif.albums,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
  }

  function matchesPlace(item, placeFilter, specOverride) {
    if (!placeFilter) return true;
    const spec = specOverride || (state && state.domain && state.domain.placeMatch) || {};
    const needles = Array.isArray(spec.needles) && spec.needles.length
      ? spec.needles.map((n) => String(n || "").trim().toLowerCase()).filter(Boolean)
      : [String(placeFilter).trim().toLowerCase()].filter(Boolean);
    if (!needles.length) return true;
    const blob = itemPlaceBlob(item);
    const stateVal = String(item && (item.state || "")).trim().toLowerCase().replace(/\./g, "");
    for (let i = 0; i < needles.length; i++) {
      const n = needles[i];
      const compact = n.replace(/\./g, "");
      if (compact.length <= 3) {
        if (stateVal === compact) return true;
        if (blob && new RegExp("(,\\s*|\\s)" + compact.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "(?:\\s|,|$)").test(blob)) {
          return true;
        }
      } else if (blob.includes(n)) {
        return true;
      }
    }
    const bbox = spec.bbox;
    const ll = itemLatLng(item);
    if (bbox && bbox.length === 4 && ll) {
      const latMin = Number(bbox[0]);
      const latMax = Number(bbox[1]);
      const lonMin = Number(bbox[2]);
      const lonMax = Number(bbox[3]);
      if (
        Number.isFinite(latMin) &&
        ll.lat >= latMin &&
        ll.lat <= latMax &&
        ll.lng >= lonMin &&
        ll.lng <= lonMax
      ) {
        return true;
      }
    }
    return false;
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

  /** Dated items that should paint the Timeline rail (not the gallery).
   *  Hidden SMS stay off cards (I7) but must still mark years on All. */
  function timelineDatedItems() {
    const filter = (state && state.domain && state.domain.typeFilter) || "all";
    const place = state && state.domain ? state.domain.placeFilter : null;
    const plotHiddenSms = !filter || filter === "all" || filter === "email";
    return rawItems.filter((it) => {
      if (!isDated(it)) return false;
      if (isSmsTextItem(it)) {
        if (!plotHiddenSms) return false;
        if (it.gallery_default_hidden) return true;
        return matchesType(it, filter);
      }
      return (
        matchesType(it, filter) &&
        matchesPlace(it, place)
      );
    });
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

  function isEmailItem(item) {
    return String((item && item.type) || "").toLowerCase() === "email";
  }

  function isCalendarItem(item) {
    return String((item && item.type) || "").toLowerCase() === "calendar";
  }

  function itemAttachCount(item) {
    if (!item) return 0;
    if (Array.isArray(item.attachments)) return item.attachments.length;
    return Number(item.attachment_count || 0) || 0;
  }

  function matchesType(item, filter, opts) {
    const d = (opts && opts.domain) || (state && state.domain) || {};
    // Communications chip uses typeFilter "email" (I7 leftover). That must not
    // force Text or Email on — the Communications filter checkboxes own this.
    const includeTexts = Boolean(
      (opts && opts.includeTexts) || d.includeTexts || d.galleryShowSms
    );
    const includeEmail = Boolean(d.includeEmail || d.galleryShowEmail);
    const includeCalendar = Boolean(
      d.includeCalendar || d.galleryShowCalendar || filter === "calendar"
    );
    const memoryOn = Boolean(d.memoryPresentation || filter === "memory");
    const attachmentsOnly = Boolean(d.attachmentsOnly);
    if (memoryOn && (isSmsTextItem(item) || isEmailItem(item) || isCalendarItem(item))) {
      return false;
    }
    if (isSmsTextItem(item)) {
      if (filter === "email") {
        if (!includeTexts) return false;
        if (attachmentsOnly && !itemAttachCount(item)) return false;
        return true;
      }
      if (!filter || filter === "all") {
        if (item.gallery_default_hidden && !includeTexts) return false;
        if (attachmentsOnly && !itemAttachCount(item)) return false;
        return includeTexts;
      }
      return false;
    }
    if (isEmailItem(item)) {
      if (filter === "email") {
        if (!includeEmail) return false;
        if (attachmentsOnly && !itemAttachCount(item)) return false;
        return true;
      }
      if (!filter || filter === "all") {
        if (item.gallery_default_hidden && !includeEmail) return false;
        if (attachmentsOnly && !itemAttachCount(item)) return false;
        return includeEmail;
      }
      return false;
    }
    if (isCalendarItem(item)) {
      if (filter === "calendar") return true;
      if (!filter || filter === "all") {
        if (item.gallery_default_hidden && !includeCalendar) return false;
        return includeCalendar;
      }
      return false;
    }
    if (!filter || filter === "all") return true;
    if (filter === "location") {
      if (itemLatLng(item)) return true;
      return Boolean(itemPlaceBlob(item).trim());
    }
    const t = String(item.type || "").toLowerCase();
    if (filter === "memory") {
      return t === "photo" || t === "video" || t === "story" || t === "artifact";
    }
    if (filter === "email" || filter === "calendar") {
      // Communications / Calendar surface keeps photos & video in the mixed gallery.
      return t === "photo" || t === "video" || t === "story" || t === "artifact";
    }
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
      if (state.domain && state.domain.typeFilter === "email") {
        if (state && state.domain) state.domain._eligibleBeforeHighlights = list.length;
        return list;
      }
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
    const ext = extentOf(timelineDatedItems());
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

  function maybeMergePersonVisuals() {
    const hasVisual = rawItems.some((it) => {
      const t = String(it.type || "").toLowerCase();
      return t === "photo" || t === "video";
    });
    if (hasVisual) return;
    const person = (state.domain.chips || []).find((c) => c && c.kind === "person");
    const name =
      (person && person.label) ||
      (PERSON && PERSON.displayName) ||
      "";
    if (!name || !liveMode) return;
    liveFind("Show " + name)
      .then((payload) => {
        const extras = (payload.items || []).filter((it) => {
          const t = String(it.type || "").toLowerCase();
          return t === "photo" || t === "video";
        });
        extras.forEach((it) => {
          if (!rawItems.some((x) => x.id === it.id)) rawItems.push(Object.assign({}, it));
        });
        syncTimelineToEligibleDatedExtent();
        render();
      })
      .catch(() => {});
  }

  function setTypeFilter(id) {
    state.domain.typeFilter = id || "all";
    if (id === "email") {
      state.domain.memoryPresentation = false;
      if (state.domain.emailPinned || state.domain.textsPinned) {
        state.domain.includeEmail = Boolean(state.domain.emailPinned);
        state.domain.includeTexts = Boolean(state.domain.textsPinned);
      } else if (!state.domain.includeEmail && !state.domain.includeTexts) {
        state.domain.includeEmail = true;
        state.domain.includeTexts = true;
      }
    } else if (id === "calendar") {
      state.domain.includeCalendar = true;
      state.domain.memoryPresentation = false;
    } else if (id === "memory") {
      state.domain.memoryPresentation = true;
      state.domain.includeTexts = false;
      state.domain.includeEmail = false;
      state.domain.includeCalendar = false;
    } else if (id === "all") {
      // Filter-only Email/Text must not pin SMS onto All. I7 hides texts
      // on All unless this find was an explicit text ask or Add texts.
      if (!state.domain.galleryShowSms && !state.domain.textsPinned) {
        state.domain.includeTexts = false;
      }
      if (!state.domain.galleryShowEmail && !state.domain.emailPinned) {
        state.domain.includeEmail = false;
      }
      if (!state.domain.galleryShowCalendar && !state.domain.calendarPinned) {
        state.domain.includeCalendar = false;
      }
      state.domain.memoryPresentation = false;
    }
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
    const c = { photo: 0, video: 0, email: 0, text: 0, artifact: 0, story: 0, other: 0 };
    for (const it of items) {
      const t = String(it.type || "").toLowerCase();
      if (t === "sms" || t === "text" || t === "imessage" || t === "mms" || t === "rcs") {
        c.text += 1;
      } else if (t in c) c[t] += 1;
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
    if (
      state.domain.outputMode === "tell" &&
      state.domain._askSummary &&
      state.domain.summary !== "Searching…"
    ) {
      state.domain.summary = state.domain._askSummary;
      return;
    }
    if (state.domain.typeFilter === "all" && atFull && state.domain._fixtureSummary) {
      state.domain.summary = state.domain._fixtureSummary;
      return;
    }
    // Prefer Ask clarification over empty "0 memories" noise.
    // Do not keep the server's photo count when the Gallery is empty
    // (FlightSim: "I found 311 photos" while Christmas AND showed 0 cards).
    if (state.domain._askSummary && state.domain._askKind === "clarification") {
      state.domain.summary = state.domain._askSummary;
      return;
    }
    const hiddenSms = Number(state.domain.smsHidden || 0) || 0;
    const availableSms = Number(state.domain.smsAvailable || 0) || 0;
    const includeTexts = Boolean(
      state.domain.includeTexts || state.domain.galleryShowSms
    );
    const allAsk =
      !state.domain.typeFilter || state.domain.typeFilter === "all";
    const c = countByType(vis);
    if (allAsk && !includeTexts && (hiddenSms || availableSms)) {
      c.text = Math.max(c.text, availableSms || hiddenSms);
    }
    const parts = [];
    if (c.photo) parts.push(`${c.photo} photo${c.photo === 1 ? "" : "s"}`);
    if (c.video) parts.push(`${c.video} video moment${c.video === 1 ? "" : "s"}`);
    if (c.text) parts.push(`${c.text} text${c.text === 1 ? "" : "s"}`);
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
    const trunc =
      state.domain.smsTruncated && state.domain.smsMatchTotal
        ? ` Showing ${vis.length} of ${state.domain.smsMatchTotal} texts.`
        : "";
    const archiveN =
      allAsk && !includeTexts && hiddenSms ? vis.length + hiddenSms : vis.length;
    let hideNote = "";
    if (allAsk && !includeTexts && (hiddenSms || availableSms)) {
      hideNote = ` ${availableSms || hiddenSms} texts are in the archive (Communications to show them).`;
    }
    const cards = galleryCardsFromVisible(vis);
    const dayCards = cards.filter((it) => String(it.type) === "daycard");
    const grain = (state.domain._showingDays || {}).grain;
    let cardNote = "";
    if (dayCards.length) {
      cardNote = ` ${dayCards.length} ${grain || "grouped"} card${
        dayCards.length === 1 ? "" : "s"
      }.`;
    }
    const emailOnly =
      Boolean(state.domain.includeEmail) &&
      !state.domain.includeTexts &&
      state.domain.typeFilter === "email";
    if (emailOnly && !c.email) {
      cardNote += " No emails matched this person.";
    }
    const shown = parts.length
      ? parts.join(", ")
      : `${archiveN} memor${archiveN === 1 ? "y" : "ies"}`;
    state.domain.summary = `${shown} · ${range} (${filterLabel}).${trunc}${hideNote}${cardNote}`;
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
    if (/^go to\b/.test(lower) || /^(select|switch to)\b/.test(lower)) return q;
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
    const text = String(raw || "").trim();
    const lower = text.toLowerCase();
    let who = "";
    const go = lower.match(/^go to\s+(.+?)\s+instead\.?$/);
    const select = lower.match(/^(?:select|switch to)\s+(.+?)\.?$/);
    const show = text.match(/^show\s+(?:me\s+)?(.+?)\.?$/i);
    if (go) who = go[1].replace(/\.$/, "").trim();
    else if (select) who = select[1].replace(/\.$/, "").trim();
    else if (show && PERSON_MODE) {
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
    const locked = String((PERSON && PERSON.displayName) || "").toLowerCase();
    const lockedFirst = locked.split(/\s+/)[0] || "";
    const lockedTokens = locked.split(/\s+/).filter(Boolean);
    const whoTokens = whoL.split(/\s+/).filter(Boolean);
    const samePerson =
      whoL === locked ||
      (whoTokens.length === 1 && whoTokens[0] === lockedFirst);
    if (samePerson) {
      return false;
    }
    if (
      /^(christmas|easter|thanksgiving|halloween|summer|winter|spring|fall|labor|memorial|nye|nyd|new year|photos?|videos?|audio|everything|map|gallery|undated|highlights|all memories|\d{4}|texts?|sms|imessage|messages?|all the|all my)/.test(
        whoL
      ) ||
      /\b(text|sms|imessage|i-?message|mms|message)s?\b/.test(whoL)
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

  function emptyExplorePayload(askText) {
    return {
      ok: true,
      demo: false,
      live: true,
      ask_text: String(askText || ""),
      title: "What would you like to see?",
      summary: "Ask MemoryBox about a person, place, time, or kind of memory.",
      chips: [],
      items: [],
      counts: {},
      session_id: sessionId,
      provider_status: {},
    };
  }

  function showSearching(askText) {
    const title = String(askText || "").trim();
    const heading = title
      ? title.length > 48
        ? title.slice(0, 45) + "…"
        : title
      : "Memories";
    const titleEl = document.getElementById("mb-explore-curator-title");
    const bodyEl = document.getElementById("mb-explore-curator-body");
    const curator = document.getElementById("mb-explore-curator");
    if (titleEl) titleEl.textContent = heading;
    if (bodyEl) bodyEl.textContent = "Searching…";
    if (curator) {
      curator.classList.add("is-searching");
      curator.classList.remove("is-tell");
    }
    const actions = document.getElementById("mb-explore-curator-actions");
    const note = document.getElementById("mb-explore-curator-note");
    if (actions) actions.hidden = true;
    if (note) note.hidden = true;
    const askField = document.querySelector(".mb-explore-ask-field");
    if (askField) askField.classList.add("is-searching");
    if (state && state.domain) {
      state.domain.title = heading;
      state.domain.summary = "Searching…";
    }
  }

  function markAskDirty() {
    const el = document.getElementById("mb-explore-ask");
    if (el) el.dataset.mbAskDirty = "1";
  }

  function clearAskDirty() {
    const el = document.getElementById("mb-explore-ask");
    if (el) el.dataset.mbAskDirty = "";
  }

  async function liveFind(askText, extras) {
    const q = personScopedAsk(askText);
    let url =
      "/explore/api/find?q=" +
      encodeURIComponent(q) +
      (sessionId ? "&session_id=" + encodeURIComponent(sessionId) : "");
    const present = extras && extras.present;
    if (present) url += "&present=" + encodeURIComponent(present);
    const res = await fetch(url);
    if (!res.ok) throw new Error("find " + res.status);
    return res.json();
  }

  function currentAskText() {
    return (
      (state && state.domain && state.domain.askText) ||
      (document.getElementById("mb-explore-ask") || {}).value ||
      ""
    );
  }

  function applyPresentFlags(present) {
    const kind = String(present || "").toLowerCase();
    state.domain.memoryPresentation = false;
    if (kind === "calendar" || kind === "cal") {
      state.domain.includeCalendar = true;
      state.domain.calendarPinned = true;
      state.domain.typeFilter = "calendar";
    } else if (kind === "email") {
      state.domain.includeEmail = true;
      state.domain.includeTexts = false;
      state.domain.emailPinned = true;
      state.domain.textsPinned = false;
      state.domain.typeFilter = "email";
    } else if (kind === "sms" || kind === "texts" || kind === "text") {
      state.domain.includeEmail = false;
      state.domain.includeTexts = true;
      state.domain.emailPinned = false;
      state.domain.textsPinned = true;
      state.domain.typeFilter = "email";
    } else {
      state.domain.includeEmail = true;
      state.domain.includeTexts = true;
      state.domain.emailPinned = true;
      state.domain.textsPinned = true;
      state.domain.typeFilter = "email";
    }
    syncTimelineToEligibleDatedExtent();
  }

  function askNeedsPersonOrTime(ask) {
    const q = String(ask || "").trim();
    if (!q) return true;
    return /^(add communications|add calendar)\.?$/i.test(q);
  }

  function promptNeedPersonOrTime(present) {
    hideQuickPreview();
    const cal = String(present || "").toLowerCase() === "calendar";
    if (!state) return;
    state.domain.title = cal ? "Calendar" : "Communications";
    state.domain.summary = cal
      ? "Who would you like to see on the calendar? Add a person and/or a time in Ask."
      : "Who would you like to see? Communications needs a person and/or a time in Ask.";
    const askEl = document.getElementById("mb-explore-ask");
    if (askEl && /^(add communications|add calendar)\.?$/i.test(String(askEl.value || "").trim())) {
      askEl.value = "";
      state.domain.askText = "";
    }
    const curator = document.getElementById("mb-explore-curator");
    if (curator) curator.classList.remove("is-searching");
    const askField = document.querySelector(".mb-explore-ask-field");
    if (askField) askField.classList.remove("is-searching");
    render();
  }

  function setGalleryLocked(on) {
    if (state && state.domain) state.domain.galleryLocked = Boolean(on);
    const g = document.getElementById("mb-explore-gallery");
    const root = document.getElementById("mb-explore-root");
    if (g) g.classList.toggle("is-locked", Boolean(on));
    if (root) root.classList.toggle("is-present-locked", Boolean(on));
  }

  function applyPresentPayload(payload, present) {
    const priorMem = rawItems.filter((it) => {
      const t = String(it.type || "").toLowerCase();
      return t === "photo" || t === "video" || t === "story" || t === "artifact";
    });
    applyPayloadToState(payload, { keepPresentation: true });
    const comms = rawItems.filter(
      (it) => isSmsTextItem(it) || isEmailItem(it) || isCalendarItem(it)
    );
    const seen = {};
    const mem = [];
    priorMem.forEach((it) => {
      seen[it.id] = 1;
      mem.push(it);
    });
    rawItems.forEach((it) => {
      const t = String(it.type || "").toLowerCase();
      if (
        (t === "photo" || t === "video" || t === "story" || t === "artifact") &&
        !seen[it.id]
      ) {
        mem.push(it);
      }
    });
    rawItems = mem.concat(comms);
    if (state && state.domain) state.domain.undatedFilter = false;
    applyPresentFlags(present);
    syncTimelineToEligibleDatedExtent();
    setGalleryLocked(false);
    pendingPresent = null;
    render();
  }

  function presentWithoutRewritingAsk(present) {
    const ask = currentAskText().trim();
    if (askNeedsPersonOrTime(ask)) {
      promptNeedPersonOrTime(present);
      return;
    }
    const gen = bumpFindGen();
    pendingPresent = null;
    setGalleryLocked(true);
    hideQuickPreview();
    showSearching(ask);
    liveFind(ask, { present: present })
      .then((payload) => {
        if (gen !== findGen) return;
        if (state.modal && state.modal.openId) {
          pendingPresent = { payload: payload, present: present, gen: gen };
          return;
        }
        applyPresentPayload(payload, present);
      })
      .catch(() => {
        if (gen !== findGen) return;
        setGalleryLocked(false);
        render();
      });
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
    if (Array.isArray(planPlaces) && planPlaces.length >= 1) {
      placeFilter = planPlaces[0];
    }
    const placeMatch = exploreHint.place_match || null;
    let nextType = typeFilter;
    const galleryShowSms = Boolean(exploreHint.gallery_show_sms);
    const galleryShowEmail = Boolean(exploreHint.gallery_show_email);
    const galleryShowCalendar = Boolean(exploreHint.gallery_show_calendar);
    // New find owns visibility. Do not keep includeTexts from a prior SMS ask
    // when this Ask is a broad memory query (FlightSim: Show me Peggy after texts).
    // Photos pill must not leak SMS.
    const includeTexts = galleryShowSms;
    const keepTexts = includeTexts;
    const includeEmail = galleryShowEmail;
    const includeCalendar = galleryShowCalendar;
    if (plan.want_cross_source) {
      nextType = "all";
    } else if (exploreHint.prefer_story_filter) {
      nextType = "story";
    } else if ((galleryShowSms || galleryShowEmail) && !plan.want_story) {
      // Text-only ask → Email/Text filter. A Story ask must not hide Stories.
      nextType = "email";
    } else if (galleryShowCalendar && !plan.want_story) {
      nextType = "calendar";
    } else {
      const vs = exploreHint.visual_scope || plan.visual_scope || "";
      if (vs === "still_only") nextType = "photo";
      else if (vs === "video_only") nextType = "video";
      else if (vs === "broad" || !keepPresentation) nextType = "all";
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
          const lo = Math.min(a, b);
          // Date-only window end is midnight at the start of that day.
          const hi = Math.max(a, b) + 86400000 - 1;
          return [lo, hi];
        })
        .filter(Boolean);
      if (!temporalWindows.length) temporalWindows = null;
    }
    const ext = extentOf(
      rawItems.filter((it) => {
        if (!isDated(it)) return false;
        if (isSmsTextItem(it)) {
          if (nextType === "photo" || nextType === "video") return false;
          if (it.gallery_default_hidden) return nextType === "all" || nextType === "email";
          return matchesType(it, nextType, {
            includeTexts,
            domain: { includeTexts, galleryShowSms, typeFilter: nextType },
          });
        }
        return (
          matchesType(it, nextType, {
            includeTexts,
            domain: { includeTexts, galleryShowSms, typeFilter: nextType },
          }) && matchesPlace(it, placeFilter, placeMatch)
        );
      })
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
        outputMode: payload.output_mode || (payload.plan || {}).output_mode || "show",
        citations: payload.citations || [],
        livingView: payload.living_view || null,
        coverage: payload.coverage || null,
        chips: chips,
        typeFilter: nextType,
        includeTexts: includeTexts,
        includeEmail: includeEmail,
        includeCalendar: includeCalendar,
        galleryShowSms: galleryShowSms,
        galleryShowEmail: galleryShowEmail,
        galleryShowCalendar: galleryShowCalendar,
        textsPinned: Boolean(galleryShowSms),
        emailPinned: Boolean(galleryShowEmail),
        calendarPinned: Boolean(galleryShowCalendar),
        memoryPresentation: false,
        attachmentsOnly: false,
        smsAvailable: Number(exploreHint.sms_available || 0) || 0,
        smsHidden: Number(exploreHint.sms_hidden || 0) || 0,
        smsMatchTotal: Number(exploreHint.sms_match_total || 0) || 0,
        emailMatchTotal: Number(exploreHint.email_match_total || exploreHint.email_available || 0) || 0,
        smsTruncated: Boolean(exploreHint.sms_truncated),
        placeFilter: placeFilter,
        placeMatch: placeMatch,
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

  const ASK_HIST_KEY = "mb_shell_recent_asks";

  function readAskHistory() {
    try {
      const list = JSON.parse(localStorage.getItem(ASK_HIST_KEY) || "[]");
      return Array.isArray(list)
        ? list.map((x) => String(x || "").trim()).filter(Boolean).slice(0, 100)
        : [];
    } catch (_) {
      return [];
    }
  }

  function writeAskHistory(list) {
    const uniq = [];
    const seen = {};
    (list || []).forEach((item) => {
      const t = String(item || "").trim();
      if (!t || seen[t]) return;
      seen[t] = 1;
      uniq.push(t);
    });
    const out = uniq.slice(0, 100);
    try {
      localStorage.setItem(ASK_HIST_KEY, JSON.stringify(out));
    } catch (_) {}
    return out;
  }

  function rememberAskLocal(text) {
    const t = String(text || "").trim();
    if (!t) return;
    writeAskHistory([t].concat(readAskHistory().filter((x) => x !== t)));
    if (window.mbShell && window.mbShell.rememberAsk) window.mbShell.rememberAsk(t);
    else {
      fetch("/ask/api/history", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: t }),
      }).catch(() => {});
    }
  }

  function applyAskCommand(raw) {
    const text = String(raw || "").trim();
    if (!text) return;
    clearAskDirty();
    rememberAskLocal(text);
    if (!state) {
      applyPayloadToState(emptyExplorePayload(text), { keepPresentation: false });
    }
    if (state && state.domain) state.domain.askText = text;
    const lower = text.toLowerCase();

    // Navigation / clear context — bare People picker (drop active person)
    if (MBQL_VERBS.go_to_people.test(text)) {
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
      const gen = bumpFindGen();
      showSearching("Show " + (PERSON.displayName || "person"));
      liveFind("Show " + (PERSON.displayName || "person"))
        .then((payload) => {
          if (gen !== findGen) return;
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

    if (PERSON_MODE && MBQL_VERBS.go_to_person.test(text)) {
      const m = String(text).match(MBQL_VERBS.go_to_person);
        const who = (m && (m[1] || m[2] || m[3]) ? (m[1] || m[2] || m[3]) : "")
          .replace(/\.$/, "")
          .trim();
        if (who) {
          const hit = resolvePersonOption(who);
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

    if (MBQL_VERBS.clear_filters.test(text)) {
      setTypeFilter("all");
      clearPlaceFilter();
      setUndatedFilter(false);
      setViewMode("gallery");
      state.domain.includeTexts = Boolean(state.domain.galleryShowSms);
      state.domain.includeEmail = Boolean(state.domain.galleryShowEmail);
      state.domain.includeCalendar = Boolean(state.domain.galleryShowCalendar);
      state.domain.memoryPresentation = false;
      render();
      return;
    }
    if (MBQL_VERBS.show_everything.test(text)) {
      setTypeFilter("all");
      clearPlaceFilter();
      setUndatedFilter(false);
      setViewMode("gallery");
      state.domain.includeTexts = true;
      state.domain.includeEmail = true;
      state.domain.includeCalendar = true;
      state.domain.textsPinned = true;
      state.domain.emailPinned = true;
      state.domain.calendarPinned = true;
      state.domain.memoryPresentation = false;
      render();
      return;
    }

    if (MBQL_VERBS.only_undated.test(text)) {
      setUndatedFilter(true);
      render();
      return;
    }
    if (MBQL_VERBS.clear_undated.test(text)) {
      setUndatedFilter(false);
      render();
      return;
    }

    if (MBQL_VERBS.show_map.test(text)) {
      setViewMode("map");
      render();
      return;
    }
    if (MBQL_VERBS.show_gallery.test(text)) {
      setViewMode("gallery");
      render();
      return;
    }

    if (MBQL_VERBS.clear_place.test(text)) {
      clearPlaceFilter();
      render();
      return;
    }

    if (MBQL_VERBS.clear_time.test(text)) {
      state.domain.temporalWindows = null;
      resetTimelineExtent(true);
      render();
      return;
    }

    if (MBQL_VERBS.reset.test(text)) {
      setTypeFilter("all");
      clearPlaceFilter();
      setUndatedFilter(false);
      state.domain.includeTexts = Boolean(state.domain.galleryShowSms);
      state.domain.includeEmail = Boolean(state.domain.galleryShowEmail);
      state.domain.includeCalendar = Boolean(state.domain.galleryShowCalendar);
      state.domain.memoryPresentation = false;
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

    if (MBQL_VERBS.only_photos.test(text) || /only photos?\.?/.test(lower)) {
      setTypeFilter("photo");
      render();
      return;
    }
    if (MBQL_VERBS.only_video.test(text) || MBQL_VERBS.add_video.test(text)) {
      if (MBQL_VERBS.add_video.test(text) && state.domain.typeFilter === "photo") {
        setTypeFilter("all");
      } else if (MBQL_VERBS.only_video.test(text)) {
        setTypeFilter("video");
      } else {
        setTypeFilter("all");
      }
      render();
      return;
    }
    if (MBQL_VERBS.add_texts.test(text)) {
      state.domain.includeTexts = true;
      state.domain.textsPinned = true;
      state.domain.memoryPresentation = false;
      syncTimelineToEligibleDatedExtent();
      render();
      return;
    }
    if (MBQL_VERBS.only_texts.test(text)) {
      state.domain.includeTexts = true;
      state.domain.includeEmail = false;
      state.domain.textsPinned = true;
      state.domain.memoryPresentation = false;
      setTypeFilter("email");
      state.domain.includeEmail = false;
      render();
      return;
    }
    if (MBQL_VERBS.add_email.test(text)) {
      state.domain.includeEmail = true;
      state.domain.emailPinned = true;
      state.domain.memoryPresentation = false;
      syncTimelineToEligibleDatedExtent();
      render();
      return;
    }
    if (MBQL_VERBS.only_email.test(text)) {
      state.domain.includeEmail = true;
      state.domain.includeTexts = false;
      state.domain.emailPinned = true;
      state.domain.memoryPresentation = false;
      setTypeFilter("email");
      state.domain.includeTexts = false;
      render();
      return;
    }
    if (MBQL_VERBS.add_communications.test(text)) {
      state.domain.includeTexts = true;
      state.domain.includeEmail = true;
      state.domain.textsPinned = true;
      state.domain.emailPinned = true;
      state.domain.memoryPresentation = false;
      setTypeFilter("email");
      render();
      return;
    }
    if (MBQL_VERBS.add_calendar.test(text) || MBQL_VERBS.only_calendar.test(text)) {
      state.domain.includeCalendar = true;
      state.domain.calendarPinned = true;
      state.domain.memoryPresentation = false;
      if (MBQL_VERBS.only_calendar.test(text)) setTypeFilter("calendar");
      else syncTimelineToEligibleDatedExtent();
      render();
      return;
    }
    if (MBQL_VERBS.attachments_only.test(text)) {
      state.domain.attachmentsOnly = true;
      render();
      return;
    }
    if (MBQL_VERBS.show_memory.test(text)) {
      setTypeFilter("memory");
      render();
      return;
    }
    if (MBQL_VERBS.only_artifacts.test(text)) {
      setTypeFilter("artifact");
      render();
      return;
    }
    if (MBQL_VERBS.only_stories.test(text)) {
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

    if (MBQL_VERBS.reset_timeline.test(text) || /reset timeline|full result range|reset range/.test(lower)) {
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
          const gen = bumpFindGen();
          showSearching("Show " + (PERSON.displayName || ""));
          liveFind("Show " + (PERSON.displayName || ""))
            .then((payload) => {
              if (gen !== findGen) return;
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
      const gen = bumpFindGen();
      showSearching(text);
      liveFind(text)
        .then((payload) => {
          if (gen !== findGen) return;
          applyPayloadToState(payload, { keepPresentation: true });
          ensureLockedPersonChip();
          if (payload.explore_state && payload.explore_state.gallery_show_sms) {
            setTypeFilter("email");
            state.domain.includeTexts = true;
            state.domain.galleryShowSms = true;
          }
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
      const hit = resolvePersonOption(name);
      if (hit) id = hit.id;
    }
    if (window.mbShell && window.mbShell.setActivePerson) {
      window.mbShell.setActivePerson({ id: id || "", name: name });
      if (state.domain.askText && window.mbShell.setActiveAsk) {
        window.mbShell.setActiveAsk(state.domain.askText);
      }
      window.mbShell.refreshPeopleNavLinks();
    }
  }

  function peopleNavHref() {
    let href = "/people/ui";
    if (window.mbShell && typeof window.mbShell.peopleHref === "function") {
      href = window.mbShell.peopleHref();
    }
    const chip =
      state &&
      state.domain &&
      (state.domain.chips || []).find((c) => c && c.kind === "person");
    if (PERSON_MODE && PERSON && PERSON.personId) {
      href =
        "/people/ui?person=" +
        encodeURIComponent(PERSON.personId) +
        (PERSON.displayName
          ? "&person_name=" + encodeURIComponent(PERSON.displayName)
          : "");
    } else if (chip && chip.label && href === "/people/ui") {
      href = "/people/ui?person_name=" + encodeURIComponent(chip.label);
    }
    const ask = (state && state.domain && state.domain.askText) || "";
    if (href && href !== "/people/ui" && ask) {
      href += (href.includes("?") ? "&" : "?") + "q=" + encodeURIComponent(ask);
    }
    return href;
  }

  function renderNav() {
    const el = document.getElementById("mb-explore-nav");
    if (!el) return;
    el.innerHTML = NAV.map((n) => {
      const href =
        n.id === "people"
          ? peopleNavHref()
          : n.id === "ask" && window.mbShell && typeof window.mbShell.askHref === "function"
            ? window.mbShell.askHref()
            : n.href;
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
    const askRaw = String(state.domain.askText || "").trim();
    const personChip = (state.domain.chips || []).find((c) => c && c.kind === "person");
    const personLabel = (personChip && personChip.label) || "";
    let heading = state.domain.title || "Memories";
    if (personLabel) heading = personLabel;
    else if (askRaw && String(heading).trim().toLowerCase() === askRaw.toLowerCase()) {
      heading = "Memories";
    }
    const titleNode = document.getElementById("mb-explore-curator-title");
    const bodyNode = document.getElementById("mb-explore-curator-body");
    if (titleNode) titleNode.textContent = heading;
    if (bodyNode) bodyNode.textContent = state.domain.summary || "";
    const curator = document.getElementById("mb-explore-curator");
    const tell = state.domain.outputMode === "tell" && !PERSON_MODE;
    if (curator) curator.classList.toggle("is-tell", Boolean(tell));
    const actions = document.getElementById("mb-explore-curator-actions");
    const note = document.getElementById("mb-explore-curator-note");
    if (actions) actions.hidden = !tell;
    if (note) note.hidden = !tell;
    if (PERSON_MODE) pushPersonResultSummary();
    const covEl = document.getElementById("mb-explore-coverage");
    if (covEl) {
      const cov = state.domain.coverage;
      if (cov && (cov.summary || cov.missing)) {
        const bits = [];
        const keys = ["photos", "video", "spoken", "email", "sms", "calendar", "story", "journal", "artifact"];
        keys.forEach((k) => {
          const n = Number(cov[k] || 0);
          if (n > 0) bits.push(`${k} ${n}`);
        });
        const miss = Array.isArray(cov.missing) ? cov.missing : [];
        let line = bits.length ? bits.join(" · ") : "No sourced items yet";
        if (miss.length) line += ` · missing ${miss.join(", ")} (0)`;
        if (Array.isArray(cov.conflicts) && cov.conflicts.length > 1) {
          line += " · date conflict kept (not elected)";
        }
        covEl.textContent = line;
        covEl.hidden = false;
      } else {
        covEl.textContent = "";
        covEl.hidden = true;
      }
    }
    if (curator && state.domain.summary && state.domain.summary !== "Searching…") {
      curator.classList.remove("is-searching");
      const askField = document.querySelector(".mb-explore-ask-field");
      if (askField) askField.classList.remove("is-searching");
    }
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
    if (av) applyCuratorPortrait();
  }

  function applyCuratorPortrait() {
    const av = document.getElementById("mb-explore-curator-avatar");
    if (!av) return;
    const personChip = (state.domain.chips || []).find((c) => c && c.kind === "person");
    const label = (personChip && personChip.label) || "";
    const opt = label ? resolvePersonOption(label) : null;
    let url =
      (PERSON && PERSON.portraitUrl) ||
      (window.MB_PERSON_SURFACE && window.MB_PERSON_SURFACE.portraitUrl) ||
      "";
    if (!url && opt && opt.id) {
      url = "/people/" + encodeURIComponent(opt.id) + "/portrait";
    }
    if (!url && opt && opt.immichId) {
      url = "/library/media/immich-person/" + encodeURIComponent(opt.immichId);
    }
    if (!url) {
      const pic = rawItems.find((it) => {
        const ty = String(it.type || "").toLowerCase();
        return (ty === "photo" || ty === "video") && (it.thumb_url || it.media_url);
      });
      if (pic) url = pic.thumb_url || pic.media_url;
    }
    const initial = String(label || state.domain.title || "M").trim().charAt(0).toUpperCase() || "M";
    if (!url) {
      av.classList.remove("has-photo");
      av.style.backgroundImage = "";
      av.textContent = initial;
      return;
    }
    const probe = new Image();
    probe.onload = () => {
      av.textContent = "";
      av.style.backgroundImage = "url(" + JSON.stringify(url) + ")";
      av.classList.add("has-photo");
    };
    probe.onerror = () => {
      av.classList.remove("has-photo");
      av.style.backgroundImage = "";
      av.textContent = initial;
    };
    probe.src = url;
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
        if (state.domain && state.domain.galleryLocked) return;
        const fid = btn.getAttribute("data-filter");
        if (fid === "email") {
          if (askNeedsPersonOrTime(currentAskText())) {
            promptNeedPersonOrTime("communications");
            return;
          }
          openCommsFilter();
          return;
        }
        if (fid === "calendar") {
          if (askNeedsPersonOrTime(currentAskText())) {
            promptNeedPersonOrTime("calendar");
            return;
          }
          const visCal = rawItems.some((it) => isCalendarItem(it) && !it.gallery_default_hidden);
          if (visCal) {
            state.domain.includeCalendar = true;
            state.domain.calendarPinned = true;
            state.domain.memoryPresentation = false;
            state.domain.undatedFilter = false;
            state.domain.typeFilter = "calendar";
            syncTimelineToEligibleDatedExtent();
            render();
            return;
          }
          presentWithoutRewritingAsk("calendar");
          return;
        }
        setTypeFilter(fid);
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
      const from = String(it.from || "").trim();
      const to = String(it.to || "").trim();
      const who =
        t === "email" && from && to
          ? escapeHtml(from) + " → " + escapeHtml(to)
          : escapeHtml(from || to || "Message");
      const nAtt = Array.isArray(it.attachments) ? it.attachments.length : Number(it.attachment_count || 0);
      const att = nAtt
        ? `<span class="mb-card-attach" title="${nAtt} attachment${nAtt === 1 ? "" : "s"} linked to this message">📎 ${nAtt}</span>`
        : "";
      return `${att}<div class="mb-card-textbody"><strong>${who}</strong>${escapeHtml(it.title || "")}</div><span class="mb-card-preview">${prev}</span>`;
    }
    if (t === "story") {
      const bg = media
        ? `<img class="mb-card-thumb" data-src="${escapeAttr(media)}" alt="" />`
        : "";
      return `${bg}<div class="mb-card-textbody"><strong>Story</strong>${prev || escapeHtml(it.title || "")}</div><span class="mb-card-preview">${prev}</span>`;
    }
    if (t === "video") {
      const startClock =
        it.t != null
          ? `${Math.floor(Number(it.t) / 60)}:${String(
              Math.floor(Number(it.t) % 60)
            ).padStart(2, "0")}`
          : "";
      const bg = media
        ? `<img class="mb-card-thumb" data-src="${escapeAttr(media)}" alt="" />`
        : "";
      return `${bg}<span class="mb-card-play" aria-hidden="true">▶</span>${
        startClock ? `<span class="mb-card-dur">${startClock}</span>` : ""
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
      return `<img class="mb-card-thumb" data-src="${escapeAttr(media)}" alt="" /><span class="mb-card-preview">${prev || escapeHtml(it.title || "")}</span>`;
    }
    return `<span class="mb-card-preview">${prev || escapeHtml(it.title || "")}</span>`;
  }

  function bindLazyThumbs(root) {
    if (!root) return;
    if (root._mbLazyIo) {
      try {
        root._mbLazyIo.disconnect();
      } catch (_) {}
      root._mbLazyIo = null;
    }
    const imgs = root.querySelectorAll("img.mb-card-thumb[data-src]");
    let inFlight = 0;
    let paused = false;
    const queue = [];
    const pump = () => {
      while (!paused && inFlight < 3 && queue.length) {
        const img = queue.shift();
        const src = img && img.getAttribute("data-src");
        if (!src || img.getAttribute("src")) continue;
        inFlight += 1;
        img.onload = () => {
          inFlight = Math.max(0, inFlight - 1);
          pump();
        };
        img.onerror = () => {
          inFlight = Math.max(0, inFlight - 1);
          pump();
        };
        img.setAttribute("src", src);
        img.removeAttribute("data-src");
      }
    };
    const load = (img) => {
      if (paused || !img || img.getAttribute("src")) return;
      queue.push(img);
      pump();
    };
    if (!("IntersectionObserver" in window)) {
      imgs.forEach((img, i) => {
        if (i < 6) load(img);
      });
      return;
    }
    const io = new IntersectionObserver(
      (ents) => {
        ents.forEach((e) => {
          if (!e.isIntersecting) return;
          load(e.target);
          io.unobserve(e.target);
        });
      },
      { root: root, rootMargin: "40px" }
    );
    imgs.forEach((img) => io.observe(img));
    root._mbLazyIo = io;
  }

  const I8A_BUCKET_CAP = 80;

  function dayKey(item) {
    const s = String((item && item.date) || "").slice(0, 10);
    return s.length >= 10 ? s : "";
  }

  function bucketKeyFor(item, grain) {
    const d = dayKey(item);
    if (!d) return "undated";
    if (grain === "month") return d.slice(0, 7);
    if (grain === "year") return d.slice(0, 4);
    return d;
  }

  function pickGrain(datedKeys) {
    if (datedKeys.length <= I8A_BUCKET_CAP) return "day";
    const months = new Set(datedKeys.map((k) => String(k).slice(0, 7)));
    if (months.size <= I8A_BUCKET_CAP) return "month";
    return "year";
  }

  function yearFairTake(keysNewestFirst, cap) {
    const byYear = {};
    keysNewestFirst.forEach((k) => {
      const y = String(k).slice(0, 4);
      (byYear[y] = byYear[y] || []).push(k);
    });
    const years = Object.keys(byYear).sort().reverse();
    const out = [];
    let i = 0;
    while (out.length < cap) {
      let added = false;
      years.forEach((y) => {
        if (out.length >= cap) return;
        const k = byYear[y][i];
        if (k) {
          out.push(k);
          added = true;
        }
      });
      if (!added) break;
      i += 1;
    }
    return out;
  }

  function orderBucketKeys(keys, sort) {
    const dated = keys.filter((k) => k && k !== "undated").sort();
    const undated = keys.filter((k) => !k || k === "undated");
    if (sort === "oldest") return dated.concat(undated);
    return dated.reverse().concat(undated);
  }

  function fmtBucketDate(k) {
    if (!k || k === "undated") return "Undated";
    if (/^\d{4}$/.test(k)) return k;
    if (/^\d{4}-\d{2}$/.test(k)) {
      const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
      const m = Number(k.slice(5, 7)) - 1;
      return (months[m] || k) + " " + k.slice(0, 4);
    }
    return fmtCardDate(k);
  }

  function commsCalItems(list) {
    return (list || []).filter(
      (it) => isSmsTextItem(it) || isEmailItem(it) || isCalendarItem(it)
    );
  }

  function memoryLikeItems(list) {
    return (list || []).filter((it) => {
      const t = String(it.type || "").toLowerCase();
      return t === "photo" || t === "video" || t === "story" || t === "artifact";
    });
  }

  function threadKey(it) {
    return convoKey(it);
  }

  function convoKey(it) {
    const tid = String((it && it.thread_id) || "").trim();
    if (tid) return "t:" + tid;
    const handles = []
      .concat(Array.isArray(it && it.identity_mapped) ? it.identity_mapped : [])
      .map((m) => String((m && (m.normalized || m.handle)) || "").trim().toLowerCase())
      .filter(Boolean)
      .sort();
    if (handles.length) return "h:" + handles.join("|");
    const names = []
      .concat(Array.isArray(it && it.people) ? it.people : [])
      .concat(it && it.from ? [it.from] : [])
      .map((n) => String(n || "").trim().toLowerCase())
      .filter(Boolean)
      .sort();
    const uniq = [];
    names.forEach((n) => {
      if (uniq.indexOf(n) < 0) uniq.push(n);
    });
    if (uniq.length) return "p:" + uniq.join("|");
    return "id:" + String((it && it.id) || "msg");
  }

  function smsMessageBody(item) {
    const title = String((item && item.title) || "").trim();
    const peopleJoin = []
      .concat((item && item.people) || [])
      .map((n) => String(n || "").trim())
      .filter(Boolean)
      .join(" & ");
    const from = String((item && item.from) || "").trim();
    const skip = new Set(
      [title, peopleJoin, from, peopleJoin.replace(/\s+&\s+/g, ", ")]
        .map((s) => s.toLowerCase())
        .filter(Boolean)
    );
    const candidates = [item && item.detail, item && item.preview];
    for (let i = 0; i < candidates.length; i += 1) {
      const s = String(candidates[i] || "").trim();
      if (!s) continue;
      if (skip.has(s.toLowerCase())) continue;
      return s;
    }
    return "";
  }

  function uniqueSmsThreadItems(items) {
    const seenId = {};
    const seenSig = {};
    const out = [];
    (items || []).forEach((it) => {
      const eid = String(it.evidence_id || it.id || "");
      if (eid && seenId[eid]) return;
      const body = smsMessageBody(it);
      const sig = [
        convoKey(it),
        String(it.date || ""),
        String(it.from || "").toLowerCase(),
        body.toLowerCase(),
      ].join("|");
      if (seenSig[sig]) return;
      if (eid) seenId[eid] = 1;
      seenSig[sig] = 1;
      if (!body && itemAttachCount(it) < 1) return;
      out.push(it);
    });
    return out;
  }

  function textListKey(it, grain) {
    const ck = convoKey(it);
    if (grain === "day") return ck;
    return ck + "|" + (dayKey(it) || "undated");
  }

  function summarizeDay(items) {
    const emails = items.filter(isEmailItem);
    const texts = items.filter(isSmsTextItem);
    const cals = items.filter(isCalendarItem);
    const eThreads = new Set(emails.map(convoKey));
    const tConv = new Set(texts.map(convoKey));
    return {
      emails,
      texts,
      cals,
      emailN: emails.length,
      textN: texts.length,
      calN: cals.length,
      emailThreads: eThreads.size,
      textConvos: tConv.size,
      attachN:
        emails.reduce((n, it) => n + itemAttachCount(it), 0) +
        texts.reduce((n, it) => n + itemAttachCount(it), 0),
    };
  }

  function threadCards(items) {
    const by = {};
    (items || []).forEach((it) => {
      const k = convoKey(it) || it.id || "msg";
      (by[k] = by[k] || []).push(it);
    });
    return Object.keys(by).map((k) => {
      const group = by[k].slice().sort((a, b) => {
        const da = parseISO(a.date);
        const db = parseISO(b.date);
        const sa = Number.isFinite(da) ? da : 0;
        const sb = Number.isFinite(db) ? db : 0;
        return sb - sa;
      });
      const head = Object.assign({}, group[0]);
      head._threadItems = group;
      if (group.length > 1) {
        head.id = "thread:" + k;
        head.preview = group.length + " messages in this thread";
      }
      return head;
    });
  }

  function photoThumbForBucket(k) {
    const key = String(k || "");
    if (!key || key === "undated") return "";
    const y = key.slice(0, 4);
    const mo = key.length >= 7 ? key.slice(0, 7) : "";
    const pics = rawItems.filter((it) => {
      const ty = String(it.type || "").toLowerCase();
      if (ty !== "photo" && ty !== "video") return false;
      if (!(it.thumb_url || it.media_url)) return false;
      const d = String(it.date || "");
      if (mo) return d.slice(0, 7) === mo;
      return d.slice(0, 4) === y;
    });
    if (!pics.length) return "";
    let h = 0;
    for (let i = 0; i < key.length; i += 1) h = (h + key.charCodeAt(i) * (i + 1)) % 997;
    const pick = pics[h % pics.length];
    return pick.thumb_url || pick.media_url || "";
  }

  function makeCombinedCard(k, group, grain) {
    const s = summarizeDay(group);
    const openLabel = grain === "day" ? "Open day →" : "Open →";
    return {
      id: "daycard:" + k,
      type: "daycard",
      title: "Communications" + (s.calN ? " & calendar" : ""),
      date: k === "undated" ? "" : k,
      undated: k === "undated",
      _dayItems: group,
      _daySummary: s,
      _grain: grain,
      _openLabel: openLabel,
      _personThumb: photoThumbForBucket(k),
      preview:
        (s.emailThreads ? s.emailThreads + " email threads" : "") +
        (s.textN
          ? (s.emailThreads ? " · " : "") +
            s.textN +
            " texts · " +
            s.textConvos +
            " conversation" +
            (s.textConvos === 1 ? "" : "s")
          : "") +
        (s.calN ? (s.emailThreads || s.textConvos ? " · " : "") + s.calN + " events" : ""),
    };
  }

  function bucketCombined(items, grain) {
    const by = {};
    items.forEach((it) => {
      const k = bucketKeyFor(it, grain);
      (by[k] = by[k] || []).push(it);
    });
    const keys = Object.keys(by);
    const dated = keys.filter((k) => k && k !== "undated");
    const sort = state.gallery.sort || "newest";
    let shownDated = orderBucketKeys(dated, sort).filter((k) => k !== "undated");
    if (shownDated.length > I8A_BUCKET_CAP) {
      const newestFirst = sort === "oldest" ? shownDated.slice().reverse() : shownDated;
      shownDated = yearFairTake(newestFirst, I8A_BUCKET_CAP);
      if (sort === "oldest") shownDated = shownDated.slice().reverse();
    }
    const shown = orderBucketKeys(shownDated.concat(keys.filter((k) => k === "undated")), sort);
    state.domain._showingDays = { shown: shown.length, total: keys.length, grain: grain };
    return shown.map((k) => makeCombinedCard(k, by[k], grain));
  }

  function insertCombinedIntoGallery(combined, allItems) {
    const mem = memoryLikeItems(allItems);
    if (!mem.length) return combined;
    const sort = state.gallery.sort || "newest";
    const byYear = {};
    const undatedMem = [];
    mem.forEach((it) => {
      if (isUndated(it)) {
        undatedMem.push(it);
        return;
      }
      const y = String(it.date || "").slice(0, 4);
      if (!/^\d{4}$/.test(y)) {
        undatedMem.push(it);
        return;
      }
      (byYear[y] = byYear[y] || []).push(it);
    });
    const combinedByYear = {};
    const undatedCombined = [];
    (combined || []).forEach((c) => {
      const y = String(c.date || "").slice(0, 4);
      if (!y || c.undated || !/^\d{4}$/.test(y)) undatedCombined.push(c);
      else combinedByYear[y] = c;
    });
    const years = new Set(
      Object.keys(byYear).concat(Object.keys(combinedByYear))
    );
    const ordered = [...years].sort((a, b) =>
      sort === "oldest" ? a.localeCompare(b) : b.localeCompare(a)
    );
    const out = [];
    ordered.forEach((y) => {
      if (combinedByYear[y]) out.push(combinedByYear[y]);
      const pics = (byYear[y] || []).slice().sort((a, b) => {
        const d = parseISO(a.date) - parseISO(b.date);
        return sort === "oldest" ? d : -d;
      });
      out.push.apply(out, pics);
    });
    out.push.apply(out, undatedCombined);
    out.push.apply(out, undatedMem);
    return out;
  }

  function galleryCardsFromVisible(items) {
    const d = state.domain || {};
    const commsOn = Boolean(d.includeTexts || d.includeEmail || d.typeFilter === "email");
    const calOn = Boolean(d.includeCalendar || d.typeFilter === "calendar");
    const mix = memoryLikeItems(items).length > 0 && commsCalItems(items).length > 0;
    const commsOnly =
      commsCalItems(items).length > 0 && memoryLikeItems(items).length === 0;
    if (!commsOn && !calOn) return items;
    const emailOnly = Boolean(d.includeEmail) && !d.includeTexts && !d.includeCalendar;
    const textOnly = Boolean(d.includeTexts) && !d.includeEmail && !d.includeCalendar;
    if (emailOnly && commsOnly) {
      const threads = threadCards(items.filter(isEmailItem));
      const other = items.filter((it) => !isEmailItem(it));
      const dated = threads.filter((it) => dayKey(it));
      const grain = pickGrain(dated.map(dayKey));
      if (grain === "day" && threads.length <= I8A_BUCKET_CAP) {
        const sort = state.gallery.sort || "newest";
        return threads.slice().sort((a, b) => {
          if (isUndated(a) && isUndated(b)) return 0;
          if (isUndated(a)) return 1;
          if (isUndated(b)) return -1;
          const da = parseISO(a.date) - parseISO(b.date);
          return sort === "oldest" ? da : -da;
        }).concat(other);
      }
      return insertCombinedIntoGallery(bucketCombined(threads, grain), items);
    }
    if ((textOnly || (commsOn && !calOn && commsOnly) || mix || (commsOn && calOn)) && commsCalItems(items).length) {
      const cc = commsCalItems(items);
      const datedKeys = cc.map(dayKey).filter(Boolean);
      const grain = pickGrain(datedKeys);
      return insertCombinedIntoGallery(bucketCombined(cc, grain), items);
    }
    return items;
  }

  function openCommsFilter() {
    hideQuickPreview();
    const el = document.getElementById("mb-comms-filter");
    if (!el) return;
    const pinned = Boolean(
      state.domain.emailPinned ||
        state.domain.textsPinned ||
        state.domain.includeEmail ||
        state.domain.includeTexts
    );
    document.getElementById("mb-comms-src-email").checked = pinned
      ? Boolean(state.domain.includeEmail || state.domain.emailPinned)
      : true;
    document.getElementById("mb-comms-src-text").checked = pinned
      ? Boolean(state.domain.includeTexts || state.domain.textsPinned)
      : true;
    const att = state.domain.attachmentsOnly;
    el.querySelectorAll('input[name="mb-comms-show"]').forEach((r) => {
      r.checked = att ? r.value === "attachments" : r.value === "messages";
    });
    const ctx = document.getElementById("mb-comms-ctx");
    if (ctx) {
      const person = ((state.domain.chips || []).find((c) => c.kind === "person") || {}).label || "—";
      ctx.textContent = "CURRENT CONTEXT · " + person + " · Person and timeline unchanged";
    }
    el.hidden = false;
  }

  function openCalFilter() {
    hideQuickPreview();
    const el = document.getElementById("mb-cal-filter");
    if (!el) return;
    el.hidden = false;
  }

  let dayStack = { day: null, tab: "email", items: [], rows: [], rowIndex: 0 };

  function convoTitle(items) {
    const names = [];
    const seen = {};
    (items || []).forEach((it) => {
      const bag = []
        .concat(Array.isArray(it.people) ? it.people : [])
        .concat(it.from ? [it.from] : []);
      bag.forEach((n) => {
        const s = String(n || "").trim();
        const k = s.toLowerCase();
        if (!s || seen[k]) return;
        seen[k] = 1;
        names.push(s);
      });
    });
    return names.slice(0, 4).join(" · ") || (items[0] && items[0].title) || "Conversation";
  }

  function syncDayNav() {
    const n = (dayStack.rows || []).length;
    const i = Number(dayStack.rowIndex) || 0;
    const det = document.getElementById("mb-day-detail");
    const has = Boolean(det && !det.hidden);
    const viewer = document.querySelector(".mb-day-viewer");
    if (viewer) viewer.classList.toggle("is-detail", has);
    const prev = document.getElementById("mb-day-prev");
    const next = document.getElementById("mb-day-next");
    const count = document.getElementById("mb-day-count");
    const back = document.getElementById("mb-day-detail-back");
    if (count) count.textContent = has && n ? i + 1 + " of " + n : n ? n + " groups" : "—";
    if (prev) prev.disabled = !has || i <= 0;
    if (next) next.disabled = !has || i >= n - 1;
    if (back) back.hidden = !has;
  }

  function openDayStack(card, tab) {
    if (state.domain && state.domain.galleryLocked) return;
    const items = (card && card._dayItems) || [];
    if (!items.length) return;
    hideQuickPreview();
    const galleryEl = document.getElementById("mb-explore-gallery");
    const scrollTop = (galleryEl || {}).scrollTop || 0;
    state.gallery.scrollTop = scrollTop;
    dayStack = {
      day: card.date || "",
      tab: "email",
      items: items,
      card: card,
      rows: [],
      rowIndex: 0,
      scrollTop: scrollTop,
    };
    const det0 = document.getElementById("mb-day-detail");
    if (det0) det0.hidden = true;
    const viewer0 = document.getElementById("mb-day-viewer");
    if (viewer0) viewer0.classList.add("is-detail");
    const s = card._daySummary || summarizeDay(items);
    const want = String(tab || "");
    if (want === "email" && s.emailN) dayStack.tab = "email";
    else if (want === "text" && s.textN) dayStack.tab = "text";
    else if (want === "calendar" && s.calN) dayStack.tab = "calendar";
    else if (s.emailN) dayStack.tab = "email";
    else if (s.textN) dayStack.tab = "text";
    else dayStack.tab = "calendar";
    renderDayStack();
    document.getElementById("mb-day-stack").hidden = false;
  }

  function closeDayStack() {
    const y = (dayStack && dayStack.scrollTop) || (state.gallery && state.gallery.scrollTop) || 0;
    const stack = document.getElementById("mb-day-stack");
    if (stack) stack.hidden = true;
    const det = document.getElementById("mb-day-detail");
    if (det) det.hidden = true;
    render();
    requestAnimationFrame(() => {
      const g = document.getElementById("mb-explore-gallery");
      if (g) g.scrollTop = y;
    });
  }

  function renderDayStack() {
    const card = dayStack.card || {};
    const s = card._daySummary || summarizeDay(dayStack.items);
    document.getElementById("mb-day-title").textContent = fmtBucketDate(dayStack.day);
    document.getElementById("mb-day-sub").textContent = [
      s.emailThreads ? s.emailThreads + " email thread" + (s.emailThreads === 1 ? "" : "s") : "",
      s.textN
        ? s.textN + " texts · " + s.textConvos + " conversation" + (s.textConvos === 1 ? "" : "s")
        : "",
      s.calN ? s.calN + " calendar event" + (s.calN === 1 ? "" : "s") : "",
    ]
      .filter(Boolean)
      .join(" · ") || "No matching groups";
    const tabs = document.getElementById("mb-day-tabs");
    tabs.innerHTML =
      `<button type="button" data-tab="email" class="${dayStack.tab === "email" ? "is-on" : ""}">Email · ${s.emailThreads} threads · ${s.emailN} messages</button>` +
      `<button type="button" data-tab="text" class="${dayStack.tab === "text" ? "is-on" : ""}">Text · ${s.textN} texts · ${s.textConvos} conversation${s.textConvos === 1 ? "" : "s"}</button>` +
      `<button type="button" data-tab="calendar" class="${dayStack.tab === "calendar" ? "is-on" : ""}">Calendar · ${s.calN} events</button>`;
    tabs.querySelectorAll("[data-tab]").forEach((b) => {
      b.addEventListener("click", () => {
        dayStack.tab = b.getAttribute("data-tab");
        const det = document.getElementById("mb-day-detail");
        if (det) det.hidden = true;
        dayStack.rowIndex = 0;
        renderDayStack();
      });
    });
    let rows = [];
    if (dayStack.tab === "email") {
      const by = {};
      s.emails.forEach((it) => {
        const k = threadKey(it);
        (by[k] = by[k] || []).push(it);
      });
      rows = Object.keys(by).map((k) => ({
        kind: "thread",
        items: by[k],
        title: convoTitle(by[k]) || by[k][0].title || k,
      }));
    } else if (dayStack.tab === "text") {
      const by = {};
      const grain = (dayStack.card && dayStack.card._grain) || "year";
      s.texts.forEach((it) => {
        const k = textListKey(it, grain);
        (by[k] = by[k] || []).push(it);
      });
      rows = Object.keys(by)
        .map((k) => {
          const group = uniqueSmsThreadItems(by[k]);
          if (!group.length) return null;
          return {
            kind: "convo",
            items: group,
            title: convoTitle(group),
          };
        })
        .filter(Boolean);
    } else {
      rows = s.cals.map((it) => ({ kind: "event", items: [it], title: it.title || "Event" }));
    }
    const list = document.getElementById("mb-day-list");
    dayStack.rows = rows;
    document.getElementById("mb-day-showing").textContent =
      "Showing " + rows.length + " of " + rows.length;
    list.innerHTML = rows
      .map((row, i) => {
        const it = row.items[0];
        const preview = escapeHtml(smsMessageBody(it) || it.preview || it.detail || "");
        let newest = it && it.date;
        let newestMs = parseISO(newest);
        (row.items || []).forEach((msg) => {
          const ms = parseISO(msg.date);
          if (Number.isFinite(ms) && (!Number.isFinite(newestMs) || ms >= newestMs)) {
            newestMs = ms;
            newest = msg.date;
          }
        });
        const n = (row.items || []).length;
        const countBit =
          row.kind === "convo"
            ? n + " text" + (n === 1 ? "" : "s")
            : row.kind === "thread"
              ? n + " message" + (n === 1 ? "" : "s")
              : "";
        const dateLabel = escapeHtml(fmtCardDate(newest));
        const on = i === dayStack.rowIndex;
        return `<button type="button" class="mb-day-row${on ? " is-on" : ""}" data-row="${i}"><strong>${escapeHtml(
          row.title
        )}</strong><div class="mb-day-row-date">${dateLabel}${
          countBit ? " · " + countBit : ""
        }</div><div>${preview}</div></button>`;
      })
      .join("");
    list.querySelectorAll("[data-row]").forEach((btn) => {
      btn.addEventListener("click", () => {
        openDayDetailAt(+btn.getAttribute("data-row"));
      });
    });
    const viewer = document.getElementById("mb-day-viewer");
    if (viewer) viewer.classList.add("is-detail");
    if (rows.length) {
      if (dayStack.rowIndex >= rows.length) dayStack.rowIndex = 0;
      openDayDetailAt(dayStack.rowIndex);
    } else {
      syncDayNav();
    }
  }

  function sortMessages(items, oldestFirst) {
    return (items || []).slice().sort((a, b) => {
      const da = parseISO(a.date);
      const db = parseISO(b.date);
      const sa = Number.isFinite(da) ? da : 0;
      const sb = Number.isFinite(db) ? db : 0;
      return oldestFirst ? sa - sb : sb - sa;
    });
  }

  function openDayDetailAt(index) {
    const row = (dayStack.rows || [])[index];
    if (!row) return;
    dayStack.rowIndex = index;
    if (dayStack.tab === "text") {
      openDayDetailThread(sortMessages(row.items, true));
    } else {
      openDayDetail(sortMessages(row.items, false)[0] || row.items[0]);
    }
    document.querySelectorAll(".mb-day-row").forEach((el) => {
      el.classList.toggle("is-on", +el.getAttribute("data-row") === index);
    });
    syncDayNav();
  }

  function openDayDetailThread(items) {
    const wrap = document.getElementById("mb-day-detail");
    const body = document.getElementById("mb-day-detail-body");
    if (!wrap || !body) return;
    wrap.hidden = false;
    const unique = uniqueSmsThreadItems(items);
    const n = unique.length;
    const blocks = unique.map((item) => {
      const text = smsMessageBody(item);
      const attachN = itemAttachCount(item);
      const bodyHtml = text
        ? escapeHtml(text)
        : attachN
          ? escapeHtml(attachN + " attachment" + (attachN === 1 ? "" : "s"))
          : "";
      return `<article class="mb-day-msg">
        <p class="mb-day-msg-meta">${escapeHtml(item.from || "")} · ${escapeHtml(fmtCardDate(item.date))}</p>
        <div class="mb-day-msg-body">${bodyHtml}</div>
      </article>`;
    });
    body.innerHTML =
      `<p class="mb-day-msg-count">${n.toLocaleString()} text${n === 1 ? "" : "s"} in this conversation</p>` +
      blocks.join("");
  }

  function openDayDetail(item) {
    const wrap = document.getElementById("mb-day-detail");
    const body = document.getElementById("mb-day-detail-body");
    if (!wrap || !body) return;
    wrap.hidden = false;
    body.innerHTML = `<h3>${escapeHtml(item.title || "Detail")}</h3>
      <p>${escapeHtml(item.from || "")} · ${escapeHtml(fmtCardDate(item.date))}</p>
      <div>${escapeHtml(item.detail || item.preview || "")}</div>`;
    if (isEmailItem(item) && item.evidence_id && typeof bindEmailStructuredView === "function") {
      body.innerHTML += `<div class="mb-ev-email-wrap" data-evidence-id="${escapeAttr(
        item.evidence_id
      )}"></div>`;
      bindEmailStructuredView(body.querySelector(".mb-ev-email-wrap"), item);
    }
  }

  function bindI8aChrome() {
    const cc = document.getElementById("mb-comms-cancel");
    const ca = document.getElementById("mb-comms-apply");
    if (cc) cc.onclick = () => {
      document.getElementById("mb-comms-filter").hidden = true;
    };
    if (ca)
      ca.onclick = () => {
        state.domain.includeEmail = document.getElementById("mb-comms-src-email").checked;
        state.domain.includeTexts = document.getElementById("mb-comms-src-text").checked;
        state.domain.emailPinned = state.domain.includeEmail;
        state.domain.textsPinned = state.domain.includeTexts;
        const att = document.querySelector('input[name="mb-comms-show"]:checked');
        state.domain.attachmentsOnly = Boolean(att && att.value === "attachments");
        state.domain.memoryPresentation = false;
        document.getElementById("mb-comms-filter").hidden = true;
        hideQuickPreview();
        const wantEmail = state.domain.includeEmail;
        const wantText = state.domain.includeTexts;
        const haveVisibleTexts = rawItems.some(
          (it) => isSmsTextItem(it) && !it.gallery_default_hidden
        );
        const haveVisibleMail = rawItems.some(
          (it) => isEmailItem(it) && !it.gallery_default_hidden
        );
        const needTexts = wantText && !haveVisibleTexts;
        const needMail = wantEmail && !haveVisibleMail;
        if (needMail || needTexts) {
          if (wantEmail && wantText) presentWithoutRewritingAsk("communications");
          else if (wantEmail) presentWithoutRewritingAsk("email");
          else presentWithoutRewritingAsk("sms");
          return;
        }
        if (wantEmail || wantText) {
          state.domain.typeFilter = "email";
          state.domain.memoryPresentation = false;
          syncTimelineToEligibleDatedExtent();
        }
        render();
      };
    const kcan = document.getElementById("mb-cal-cancel");
    const kap = document.getElementById("mb-cal-apply");
    if (kcan) kcan.onclick = () => {
      document.getElementById("mb-cal-filter").hidden = true;
    };
    if (kap)
      kap.onclick = () => {
        const mode = document.querySelector('input[name="mb-cal-show"]:checked');
        state.domain.includeCalendar = true;
        state.domain.calendarPinned = true;
        state.domain.calShowMode = (mode && mode.value) || "events";
        state.domain.memoryPresentation = false;
        document.getElementById("mb-cal-filter").hidden = true;
        setTypeFilter("calendar");
        render();
      };
    const close = document.getElementById("mb-day-close");
    const dback = document.getElementById("mb-day-detail-back");
    const prev = document.getElementById("mb-day-prev");
    const next = document.getElementById("mb-day-next");
    if (close) close.onclick = closeDayStack;
    if (dback)
      dback.onclick = () => {
        const det = document.getElementById("mb-day-detail");
        if (det) det.hidden = true;
        document.querySelectorAll(".mb-day-row").forEach((el) => el.classList.remove("is-on"));
        syncDayNav();
      };
    if (prev)
      prev.onclick = () => {
        if (dayStack.rowIndex > 0) openDayDetailAt(dayStack.rowIndex - 1);
      };
    if (next)
      next.onclick = () => {
        if (dayStack.rowIndex < (dayStack.rows || []).length - 1) {
          openDayDetailAt(dayStack.rowIndex + 1);
        }
      };
    syncDayNav();
  }

  function renderGallery() {
    const gallery = document.getElementById("mb-explore-gallery");
    if (!gallery) return;
    const items = galleryCardsFromVisible(visibleItems());
    state.domain.items = items;
    gallery.dataset.density = String(state.gallery.density);
    const densLabel = document.getElementById("mb-density-label");
    if (densLabel) densLabel.textContent = densityLabel();
    const sortEl = document.getElementById("mb-explore-sort");
    if (sortEl) sortEl.value = state.gallery.sort || "newest";

    gallery.innerHTML = items
      .map((it) => {
        if (String(it.type) === "daycard") {
          const s = it._daySummary || {};
          const bits = [];
          if (s.emailThreads)
            bits.push(
              `<button type="button" class="mb-day-pill mb-day-e" data-day-tab="email">${s.emailThreads} email thread${s.emailThreads === 1 ? "" : "s"}</button>`
            );
          if (s.textN)
            bits.push(
              `<button type="button" class="mb-day-pill mb-day-t" data-day-tab="text"><span class="mb-day-t-n">${s.textN.toLocaleString()} texts</span><span class="mb-day-t-c">${s.textConvos} conversation${s.textConvos === 1 ? "" : "s"}</span></button>`
            );
          if (s.calN)
            bits.push(
              `<button type="button" class="mb-day-pill mb-day-c" data-day-tab="calendar">${s.calN} event${s.calN === 1 ? "" : "s"}</button>`
            );
          if (!bits.length) bits.push(`<span class="mb-day-e">No matching groups</span>`);
          const face = it._personThumb
            ? `<img class="mb-day-face" src="${escapeAttr(it._personThumb)}" alt="" />`
            : "";
          return `<div class="mb-card mb-card-day" data-id="${escapeAttr(
            it.id
          )}" data-type="daycard">
          <div class="mb-card-media" data-type="daycard">
            <div class="mb-day-counts">${bits.join("")}</div>
          </div>
          <div class="mb-card-meta">
            ${face}
            <span class="mb-card-type" aria-hidden="true">▦</span>
            <div>
              <div class="mb-card-title">${escapeHtml(it.title || "Communications")}</div>
              <div class="mb-card-sub">${escapeHtml(fmtBucketDate(it.date))}</div>
            </div>
          </div>
        </div>`;
        }
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
      card.addEventListener("click", (ev) => {
        if (state.domain && state.domain.galleryLocked) return;
        const pill = ev.target.closest("[data-day-tab]");
        if (String(card.getAttribute("data-type")) === "daycard") {
          const it = items.find((x) => x.id === id);
          if (!it) return;
          openDayStack(it, pill ? pill.getAttribute("data-day-tab") : "");
          return;
        }
        openModal(id);
      });
      bindCardPreview(card, id);
    });
    bindLazyThumbs(gallery);

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
    const totalBit =
      state.domain.smsTruncated && state.domain.smsMatchTotal
        ? ` · ${state.domain.smsMatchTotal} matching texts (year-fair sample)`
        : "";
    meta.textContent = `${items.length} visible · ${densityLabel()} · filter ${
      state.domain.typeFilter
    }${placeBit}${undatedBit}${refineBit}${viewBit}${totalBit}`;
    if (PERSON_MODE) pushPersonResultSummary(items);
  }

  function pushPersonResultSummary(itemList) {
    if (!PERSON_MODE) return;
    const vis = Array.isArray(itemList) ? itemList : visibleItems();
    let rangeLabel = "";
    try {
      if (hasDatedExtent()) {
        rangeLabel = fmtRangeLabel(
          state.timeline.rangeStart,
          state.timeline.rangeEnd,
          state.timeline.precision
        );
      }
    } catch (_) {
      rangeLabel = "";
    }
    const payload = {
      total: vis.length,
      counts: countByType(vis),
      rangeLabel,
    };
    window.MB_PERSON_LAST_RESULTS = payload;
    if (typeof window.mbPersonSyncResults === "function") {
      window.mbPersonSyncResults(payload);
    }
    const curator = document.getElementById("mb-explore-curator");
    if (curator) {
      curator.hidden = true;
      curator.setAttribute("aria-hidden", "true");
    }
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
      if (band) {
        band.style.left = "0%";
        band.style.width = "100%";
      }
      if (hl) hl.style.left = "0%";
      if (hr) hr.style.left = "100%";
      if (ph) ph.style.left = "0%";
      const rangeLab = document.getElementById("mb-tl-range-label");
      if (rangeLab) rangeLab.textContent = "No dated memories on the Timeline";
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
    const typedDated = timelineDatedItems();
    // Always clear first — prevents leftover dots after zoom
    if (dotsEl) dotsEl.innerHTML = "";
    if (!empty && dotsEl) {
      const span = Math.max(extentEnd - extentStart, 1);
      const parts = [];
      // Year precision: one 7px dot per card stacks and looks empty. Hidden
      // SMS stay off cards (I7) but still mark years. Always density on long spans.
      const useYearDensity =
        precision === "years" || (extentEnd - extentStart) / 86400000 > 900;
      if (useYearDensity) {
        const bins = new Map();
        for (const it of typedDated) {
          const t = parseISO(it.date);
          if (!Number.isFinite(t) || t < extentStart || t > extentEnd) continue;
          const y = new Date(t).getUTCFullYear();
          bins.set(y, (bins.get(y) || 0) + 1);
        }
        let maxN = 1;
        bins.forEach((n) => {
          if (n > maxN) maxN = n;
        });
        bins.forEach((n, y) => {
          const t0 = dayMs(y, 1, 1);
          const t1 = dayMs(y + 1, 1, 1);
          const left = ((t0 - extentStart) / span) * 100;
          const width = Math.max(((t1 - t0) / span) * 100, 0.35);
          const op = (0.22 + (n / maxN) * 0.7).toFixed(2);
          parts.push(
            `<span class="mb-tl-bar" style="left:${Math.max(0, left)}%;width:${width}%;opacity:${op}" title="${escapeAttr(
              `${y}: ${n}`
            )}"></span>`
          );
        });
      } else {
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
      }
      dotsEl.innerHTML = parts.join("");
    }

    const ticks = document.getElementById("mb-tl-ticks");
    if (empty) {
      if (ticks) ticks.innerHTML = "";
    } else if (ticks) {
      const span = Math.max(extentEnd - extentStart, 1);
      const years = [];
      const y0 = new Date(extentStart).getUTCFullYear();
      const y1 = new Date(extentEnd).getUTCFullYear();
      for (let y = y0; y <= y1; y++) years.push(y);
      const step = years.length > 16 ? 4 : years.length > 10 ? 2 : 1;
      const chosen = years.filter(
        (y, i) => i === 0 || i === years.length - 1 || y % step === 0
      );
      const placed = [];
      ticks.innerHTML = chosen
        .map((y) => {
          const t0 = Math.max(extentStart, dayMs(y, 1, 1));
          const t1 = Math.min(extentEnd, dayMs(y + 1, 1, 1));
          const t = t1 > t0 ? (t0 + t1) / 2 : t0;
          let x = ((t - extentStart) / span) * 100;
          if (!Number.isFinite(x)) return "";
          x = Math.min(97.5, Math.max(1.2, x));
          const prev = placed.length ? placed[placed.length - 1] : -999;
          if (x - prev < 3.2 && y !== years[0] && y !== years[years.length - 1]) {
            return "";
          }
          if (x - prev < 2.2) return "";
          placed.push(x);
          return `<span style="left:${x}%">${y}</span>`;
        })
        .join("");
    }
  }

  function render() {
    const askEl = document.getElementById("mb-explore-ask");
    if (askEl && document.activeElement !== askEl && askEl.dataset.mbAskDirty !== "1") {
      askEl.value = state.domain.askText || "";
    }
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
    const vis = visibleItems().map((x) => x.id);
    const openId = state && state.modal && state.modal.openId;
    if (openId && vis.indexOf(openId) < 0) {
      const cur = rawItems.find((x) => x.id === openId);
      const related = [];
      if (cur && String(cur.type || "") !== "story") {
        const photoKey = String(cur.external_id || cur.id || "").replace(/^photo:/, "");
        rawItems.forEach((x) => {
          if (String(x.type || "") !== "story") return;
          const src = String(x.external_id || x.source_photo_id || "");
          if (src && photoKey && src === photoKey) related.push(x.id);
        });
      }
      return [openId].concat(related, vis.filter((id) => related.indexOf(id) < 0));
    }
    return vis;
  }

  function openModal(id) {
    const modal = document.getElementById("mb-modal");
    const item = rawItems.find((x) => x.id === id);
    if (!item || !modal) return;
    if (state.domain && state.domain.galleryLocked && !String(id).startsWith("video:direct:")) return;
    hideQuickPreview();
    state.gallery.scrollTop =
      document.getElementById("mb-explore-gallery").scrollTop || 0;
    if (!state.modal.snapshot) state.modal.snapshot = snapshotExplore();
    state.modal.openId = id;
    state.modal.pendingCorrection = null;
    if (!state.modal.railTab) state.modal.railTab = "people";
    state.modal.transcriptOn = String(item.type || "").toLowerCase() === "video";
    state.modal.speechAutoStarted = false;
    state.modal.transcriptHasWords = false;
    state.modal.speechSpan = null;
    state.modal.zoom = 1;
    renderViewer(item);
    modal.hidden = false;
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
    bindSmsAttachActions(item);
    bindEmailStructuredView(item);
    bindExploreVideoPlayer(item);
    bindFaceHoldReveal();
    renderViewerFooter(item);
    bindSpeechTranscript(item);
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
    state.modal.transcriptOn = String(item.type || "").toLowerCase() === "video";
    state.modal.speechSpan = null;
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
    state.modal.speechSpan = null;
    stopSpeechPoll();
    stopLearnBoxing();
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
    if (pendingPresent && pendingPresent.gen === findGen) {
      const p = pendingPresent;
      pendingPresent = null;
      applyPresentPayload(p.payload, p.present);
      return;
    }
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
      if (/^(re|fw|fwd)\s*:/i.test(s)) return;
      if (s.length > 80) return;
      if (["attachments", "attachment", "image", "messages", "message", "and"].includes(s.toLowerCase())) return;
      if (!seen.includes(s)) seen.push(s);
    };
    if (Array.isArray(item.people)) item.people.forEach(push);
    push(item.face_identity);
    push(item.mb_person_name);
    (state.domain.chips || []).forEach((c) => {
      if (c && c.kind === "person") push(c.label);
    });
    const t = String(item.type || "").toLowerCase();
    if (t !== "email" && t !== "sms" && t !== "text") {
      const titleHead = String(item.title || "").split(" · ")[0].trim();
      const vid = String(item.video_external_id || item.external_id || "").trim();
      if (titleHead && titleHead !== vid && !looksLikeUuid(titleHead)) push(titleHead);
    }
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
      ["File / id", item.original_filename || item.video_external_id || item.external_id || item.id || "—"],
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
        const cur = rawItems.find((x) => x.id === state.modal.openId);
        const qs = new URLSearchParams();
        if (cur) {
          const photoId = String(cur.external_id || "").trim();
          if (photoId) qs.set("photo", photoId);
          if (cur.date) qs.set("taken", String(cur.date).slice(0, 32));
          const thumb = cur.thumb_url || cur.media_url || "";
          if (thumb) qs.set("thumb", thumb);
          if (cur.title) qs.set("title", String(cur.title).slice(0, 80));
          const who =
            cur.mb_person_name ||
            (Array.isArray(cur.people) && cur.people[0]) ||
            "";
          if (who) qs.set("about", String(who));
        }
        qs.set("new", "1");
        window.location.href = "/story/ui" + (qs.toString() ? "?" + qs.toString() : "");
      });
    }
  }

  function mediaSourceForStory(item) {
    const t = String(item.type || "").toLowerCase();
    if (t === "photo" || item.external_id) {
      if (t === "photo" || (!item.video_external_id && item.external_id && t !== "video")) {
        const id = String(item.external_id || "").replace(/^photo:/, "");
        if (id && (t === "photo" || t === "")) return { kind: "photo", id };
      }
    }
    if (t === "video" || item.video_external_id) {
      const id = String(item.video_external_id || item.external_id || "").replace(/^video:/, "");
      if (id) return { kind: "video", id };
    }
    if (t === "photo") {
      const id = String(item.external_id || "").replace(/^photo:/, "");
      if (id) return { kind: "photo", id };
    }
    return null;
  }

  function storyRailHref(s) {
    if (!s || !s.id) return "/story/ui";
    if (s.lifecycle === "draft_only") return "/story/ui?id=" + encodeURIComponent(s.id) + "&edit=1";
    return "/story/ui?id=" + encodeURIComponent(s.id);
  }

  function renderStoryRail(item, panel) {
    const media = mediaSourceForStory(item);
    const typeLabel = media && media.kind === "video" ? "VIDEO" : "PHOTO";
    const noun = (media && media.kind) || "memory";
    if (String(item.type || "").toLowerCase() === "story") {
      panel.innerHTML = `<h3>Story</h3>
        <p><strong>${escapeHtml(item.story_title || item.title || "Story")}</strong></p>
        <p><a class="mb-viewer-footbtn" href="${escapeHtml(storyRailHref({ id: item.story_id || item.domain_id, lifecycle: "saved" }))}">Open story</a></p>`;
      return;
    }
    if (!media) {
      panel.innerHTML = `<h3>STORIES USING THIS MEMORY</h3>
        <p class="mb-rail-empty">This item cannot be linked as a supporting memory.</p>`;
      return;
    }
    panel.innerHTML = `<h3>STORIES USING THIS ${typeLabel}</h3>
      <p class="mb-rail-empty">Loading…</p>`;
    fetch(
      "/story/by-media?kind=" +
        encodeURIComponent(media.kind) +
        "&source_id=" +
        encodeURIComponent(media.id)
    )
      .then((r) => r.json())
      .then((data) => {
        const items = data.items || [];
        const cards = items
          .map((s) => {
            const draft = s.has_working_draft && !s.ask_available;
            const people = (s.people || [])
              .slice(0, 3)
              .map((p) => {
                const name = p.display_name || "";
                const src = p.portrait_url || "/people/" + p.id + "/portrait";
                return `<img src="${escapeHtml(src)}" alt="${escapeHtml(name)}" title="${escapeHtml(name)}" style="width:22px;height:22px;border-radius:99px;object-fit:cover;margin-right:2px" />`;
              })
              .join("");
            return `<a class="mb-rail-story-card" href="${escapeHtml(storyRailHref(s))}" style="display:block;text-decoration:none;color:inherit;background:#141b27;border:1px solid rgba(255,255,255,0.12);border-radius:10px;padding:0.55rem 0.65rem;margin:0.45rem 0">
              <div style="display:flex;justify-content:space-between;gap:0.4rem">
                <strong>${escapeHtml(s.title || "Untitled")}</strong>
                <span style="font-size:0.75rem;color:${draft ? "#fb923c" : "#3dcf9a"}">${draft ? "Draft" : "Saved"}</span>
              </div>
              <p style="margin:0.25rem 0;color:#94a3b8;font-size:0.78rem">${escapeHtml(s.description || "")}</p>
              <p style="margin:0;color:#94a3b8;font-size:0.72rem">${escapeHtml(s.narrator_display_name ? "Narrated by " + s.narrator_display_name : "")} · ${(s.memories || []).length} linked memories</p>
              <div style="margin-top:0.35rem">${people}</div>
            </a>`;
          })
          .join("");
        const newQs = new URLSearchParams({ new: "1" });
        newQs.set(media.kind === "video" ? "video" : "photo", media.id);
        if (item.date) newQs.set("taken", String(item.date).slice(0, 32));
        if (item.thumb_url || item.media_url) newQs.set("thumb", item.thumb_url || item.media_url);
        if (item.title) newQs.set("title", String(item.title).slice(0, 80));
        const peopleNames = peopleList(item);
        if (peopleNames.length) newQs.set("people", peopleNames.slice(0, 8).join(","));
        if (item.mb_person_id) newQs.set("person", String(item.mb_person_id));
        panel.innerHTML = `<h3>STORIES USING THIS ${typeLabel}</h3>
          <p class="mb-rail-empty">This ${noun} supports ${items.length} stor${items.length === 1 ? "y" : "ies"}.</p>
          ${cards || `<p class="mb-rail-empty">No stories use this ${noun} yet.</p>`}
          <p><button type="button" class="mb-viewer-footbtn" id="mb-rail-add-to-story">+ Add to story</button></p>
          <p><a class="mb-viewer-footbtn" href="/story/ui?${newQs.toString()}">Create a new story</a></p>
          <p class="mb-rail-empty">Adding this ${noun} links it as evidence. The original remains unchanged.</p>`;
        const addBtn = document.getElementById("mb-rail-add-to-story");
        if (addBtn) {
          addBtn.addEventListener("click", () => openAddToStoryPicker(media, items));
        }
      })
      .catch(() => {
        panel.innerHTML = `<h3>STORIES USING THIS ${typeLabel}</h3>
          <p class="mb-rail-empty">Could not load stories for this ${noun}.</p>`;
      });
  }

  function openAddToStoryPicker(media, already) {
    const used = new Set((already || []).map((s) => s.id));
    fetch("/story?limit=100")
      .then((r) => r.json())
      .then((data) => {
        const stories = (data.stories || data.items || []).filter((s) => !used.has(s.id));
        const panel = document.getElementById("mb-rail-panel");
        if (!panel) return;
        const rows = stories
          .map(
            (s) =>
              `<button type="button" class="mb-viewer-footbtn mb-add-existing-story" data-id="${escapeHtml(s.id)}" style="display:block;width:100%;text-align:left;margin:0.3rem 0">${escapeHtml(s.title || "Untitled")} · ${s.ask_available ? "Saved" : "Draft"}</button>`
          )
          .join("");
        panel.insertAdjacentHTML(
          "beforeend",
          `<div id="mb-add-story-pick" style="margin-top:0.7rem;padding-top:0.5rem;border-top:1px solid rgba(255,255,255,0.12)">
            <p><strong>Add to an existing story</strong></p>
            ${rows || `<p class="mb-rail-empty">No other stories yet.</p>`}
            <button type="button" class="mb-viewer-footbtn" id="mb-add-story-cancel">Cancel</button>
          </div>`
        );
        const cancel = document.getElementById("mb-add-story-cancel");
        if (cancel) cancel.addEventListener("click", () => {
          const box = document.getElementById("mb-add-story-pick");
          if (box) box.remove();
        });
        panel.querySelectorAll(".mb-add-existing-story").forEach((btn) => {
          btn.addEventListener("click", () => {
            fetch("/story/" + encodeURIComponent(btn.dataset.id) + "/working/memories", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                source_kind: media.kind,
                source_id: media.id,
                label_snapshot: media.kind === "video" ? "Video" : "Photo",
              }),
            })
              .then((r) => r.json())
              .then(() => {
                const cur = rawItems.find((x) => x.id === state.modal.openId);
                if (cur) renderRailPanel(cur);
              })
              .catch(() => window.alert("Could not add this memory to the story."));
          });
        });
      })
      .catch(() => window.alert("Could not load stories."));
  }

  function artifactRailHref(a) {
    if (!a || !a.id) return "/artifact/ui";
    return "/artifact/ui?id=" + encodeURIComponent(a.id);
  }

  function renderArtifactRail(item, panel) {
    const media = mediaSourceForStory(item);
    const typeLabel = media && media.kind === "video" ? "VIDEO" : "PHOTO";
    const noun = (media && media.kind) || "memory";
    if (String(item.type || "").toLowerCase() === "artifact") {
      const aid = item.artifact_id || item.domain_id || item.id;
      panel.innerHTML = `<h3>Artifact</h3>
        <p><strong>${escapeHtml(item.artifact_title || item.title || "Artifact")}</strong></p>
        <p><a class="mb-viewer-footbtn" href="${escapeHtml(artifactRailHref({ id: aid }))}">Open artifact</a></p>`;
      return;
    }
    if (!media) {
      panel.innerHTML = `<h3>ARTIFACTS USING THIS MEMORY</h3>
        <p class="mb-rail-empty">This item cannot be linked as supporting evidence from here.</p>
        <p><a class="mb-viewer-footbtn" href="/artifact/ui">Browse artifacts</a></p>`;
      return;
    }
    panel.innerHTML = `<h3>ARTIFACTS USING THIS ${typeLabel}</h3>
      <p class="mb-rail-empty">Loading…</p>`;
    fetch(
      "/artifact/by-media?kind=" +
        encodeURIComponent(media.kind) +
        "&source_id=" +
        encodeURIComponent(media.id)
    )
      .then((r) => r.json())
      .then((data) => {
        const items = data.items || [];
        const cards = items
          .map((a) => {
            const people = (a.people || [])
              .slice(0, 3)
              .map((p) => {
                const name = p.display_name || "";
                const src = p.portrait_url || "/people/" + p.id + "/portrait";
                return `<img src="${escapeHtml(src)}" alt="${escapeHtml(name)}" title="${escapeHtml(name)}" style="width:22px;height:22px;border-radius:99px;object-fit:cover;margin-right:2px" />`;
              })
              .join("");
            const mid = a.link_memory_id || "";
            return `<div class="mb-rail-story-card" style="background:#141b27;border:1px solid rgba(255,255,255,0.12);border-radius:10px;padding:0.55rem 0.65rem;margin:0.45rem 0">
              <div style="display:flex;justify-content:space-between;gap:0.4rem">
                <a href="${escapeHtml(artifactRailHref(a))}" style="color:inherit;text-decoration:none"><strong>${escapeHtml(a.label || "Untitled")}</strong></a>
                <button type="button" class="mb-viewer-footbtn mb-rail-art-overflow" data-id="${escapeHtml(a.id)}" data-mid="${escapeHtml(mid)}" aria-label="Artifact link actions">⋮</button>
              </div>
              <p style="margin:0.25rem 0;color:#94a3b8;font-size:0.78rem">${escapeHtml(a.description || "")}</p>
              <p style="margin:0;color:#94a3b8;font-size:0.72rem">${escapeHtml(a.kind || "")} · ${(a.memories || []).length} linked memories</p>
              <div style="margin-top:0.35rem">${people}</div>
              <p style="margin:0.4rem 0 0"><a class="mb-viewer-footbtn" href="${escapeHtml(artifactRailHref(a))}">Open</a></p>
            </div>`;
          })
          .join("");
        const newQs = new URLSearchParams({ new: "1" });
        newQs.set(media.kind === "video" ? "video" : "photo", media.id);
        if (item.thumb_url || item.media_url) newQs.set("thumb", item.thumb_url || item.media_url);
        if (item.title) newQs.set("title", String(item.title).slice(0, 80));
        panel.innerHTML = `<h3>ARTIFACTS USING THIS ${typeLabel}</h3>
          <p class="mb-rail-empty">This ${noun} supports ${items.length} artifact${items.length === 1 ? "" : "s"} as evidence.</p>
          ${cards || `<p class="mb-rail-empty">No artifacts use this ${noun} yet.</p>`}
          <p><button type="button" class="mb-viewer-footbtn" id="mb-rail-add-to-artifact">+ Add to existing artifact</button></p>
          <p><a class="mb-viewer-footbtn" href="/artifact/ui?${newQs.toString()}">Create a new artifact</a></p>
          <p class="mb-rail-empty">This ${noun} is supporting evidence, not a representation of the object. Linking keeps the original unchanged and does not delete the artifact.</p>`;
        const addBtn = document.getElementById("mb-rail-add-to-artifact");
        if (addBtn) {
          addBtn.addEventListener("click", () => openAddToArtifactPicker(media, items));
        }
        panel.querySelectorAll(".mb-rail-art-overflow").forEach((btn) => {
          btn.addEventListener("click", () => {
            if (!btn.dataset.mid) {
              window.alert("This link cannot be removed from here.");
              return;
            }
            if (!window.confirm("Remove this link? The original media and the artifact stay. Only the supporting-evidence link is removed.")) {
              return;
            }
            fetch(
              "/artifact/" +
                encodeURIComponent(btn.dataset.id) +
                "/memories/" +
                encodeURIComponent(btn.dataset.mid) +
                "/removed",
              { method: "POST" }
            )
              .then((r) => r.json())
              .then(() => {
                const cur = rawItems.find((x) => x.id === state.modal.openId);
                if (cur) renderRailPanel(cur);
              })
              .catch(() => window.alert("Could not remove this artifact link."));
          });
        });
      })
      .catch(() => {
        panel.innerHTML = `<h3>ARTIFACTS USING THIS ${typeLabel}</h3>
          <p class="mb-rail-empty">Could not load artifacts for this ${noun}.</p>`;
      });
  }

  function openAddToArtifactPicker(media, already) {
    const used = new Set((already || []).map((a) => a.id));
    fetch("/artifact?limit=100")
      .then((r) => r.json())
      .then((data) => {
        const artifacts = (data.artifacts || data.items || []).filter((a) => !used.has(a.id));
        const panel = document.getElementById("mb-rail-panel");
        if (!panel) return;
        const rows = artifacts
          .map(
            (a) =>
              `<button type="button" class="mb-viewer-footbtn mb-add-existing-artifact" data-id="${escapeHtml(a.id)}" style="display:block;width:100%;text-align:left;margin:0.3rem 0">${escapeHtml(a.label || "Untitled")} · ${escapeHtml(a.kind || "")}</button>`
          )
          .join("");
        panel.insertAdjacentHTML(
          "beforeend",
          `<div id="mb-add-artifact-pick" style="margin-top:0.7rem;padding-top:0.5rem;border-top:1px solid rgba(255,255,255,0.12)">
            <p><strong>Add to an existing artifact</strong></p>
            ${rows || `<p class="mb-rail-empty">No other artifacts yet.</p>`}
            <button type="button" class="mb-viewer-footbtn" id="mb-add-artifact-cancel">Cancel</button>
          </div>`
        );
        const cancel = document.getElementById("mb-add-artifact-cancel");
        if (cancel) cancel.addEventListener("click", () => {
          const box = document.getElementById("mb-add-artifact-pick");
          if (box) box.remove();
        });
        panel.querySelectorAll(".mb-add-existing-artifact").forEach((btn) => {
          btn.addEventListener("click", () => {
            fetch("/artifact/" + encodeURIComponent(btn.dataset.id) + "/memories", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                source_kind: media.kind,
                source_id: media.id,
                label_snapshot: media.kind === "video" ? "Video" : "Photo",
              }),
            })
              .then((r) => r.json())
              .then(() => {
                const cur = rawItems.find((x) => x.id === state.modal.openId);
                if (cur) renderRailPanel(cur);
              })
              .catch(() => window.alert("Could not add this memory to the artifact."));
          });
        });
      })
      .catch(() => window.alert("Could not load artifacts."));
  }

  function renderRailPanel(item) {
    const panel = document.getElementById("mb-rail-panel");
    const teach = document.getElementById("mb-modal-teach");
    if (!panel) return;
    const tab = state.modal.railTab || "people";
    if (teach) {
      teach.hidden = true;
      teach.innerHTML = "";
    }
    if (tab !== "learn") stopLearnBoxing();

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
      renderStoryRail(item, panel);
      return;
    }

    if (tab === "artifact") {
      renderArtifactRail(item, panel);
      return;
    }

    if (tab === "source") {
      panel.innerHTML = sourceDetailsHtml(item);
      return;
    }


    if (tab === "learn") {
      renderLearnRail(item);
      return;
    }
  }

  function correlationSubjectForItem(item) {
    if (!item) return null;
    if (item.evidence_id) {
      return { subject_type: "evidence", subject_id: String(item.evidence_id) };
    }
    if (item.artifact_id) {
      return { subject_type: "artifact", subject_id: String(item.artifact_id) };
    }
    if (item.story_id) {
      return { subject_type: "story", subject_id: String(item.story_id) };
    }
    if (item.journal_id) {
      return { subject_type: "journal", subject_id: String(item.journal_id) };
    }
    const t = String(item.type || "").toLowerCase();
    if (t === "photo" && item.external_id) {
      return { subject_type: "photo", subject_id: String(item.external_id) };
    }
    if (t === "video") {
      const vid = item.video_external_id || item.external_id;
      if (vid) return { subject_type: "video", subject_id: String(vid) };
    }
    return null;
  }

  function notThisEventHtml(item) {
    const eventId =
      state && state.domain && state.domain.coverage && state.domain.coverage.event_id;
    const subj = correlationSubjectForItem(item);
    if (!eventId || !subj) return "";
    return `<div class="mb-learn-block">
      <h4>This event</h4>
      <p class="mb-rail-empty">If this item does not belong here, reject the correlation. The rejection sticks.</p>
      <div class="mb-learn-actions">
        <button type="button" class="mb-viewer-footbtn" id="mb-not-this-event">Not this event</button>
      </div>
      <p class="mb-rail-empty" id="mb-not-this-event-status"></p>
    </div>`;
  }

  function bindNotThisEvent(item) {
    const btn = document.getElementById("mb-not-this-event");
    if (!btn) return;
    btn.addEventListener("click", () => unlinkItemFromEvent(item));
  }

  async function unlinkItemFromEvent(item) {
    const eventId =
      state && state.domain && state.domain.coverage && state.domain.coverage.event_id;
    const subj = correlationSubjectForItem(item);
    const statusEl = document.getElementById("mb-not-this-event-status");
    const btn = document.getElementById("mb-not-this-event");
    if (!eventId || !subj) return;
    if (btn) btn.disabled = true;
    try {
      const res = await fetch("/correlate/unlink", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          subject_type: subj.subject_type,
          subject_id: subj.subject_id,
          object_type: "event",
          object_id: String(eventId),
        }),
      });
      if (!res.ok) throw new Error("unlink " + res.status);
      closeModal();
      const payload = await liveFind(currentAskText());
      applyPayloadToState(payload, { keepPresentation: true });
      render();
    } catch (err) {
      if (statusEl) {
        statusEl.textContent =
          "Could not unlink: " + (err && err.message ? err.message : String(err));
      }
      if (btn) btn.disabled = false;
    }
  }

  function knownPeopleOptions() {
    return (peopleOptions || []).filter((p) => {
      const key = String((p && (p.key || p.id)) || "");
      if (!p || !key) return false;
      if (key.startsWith("demo:")) return false;
      if (String(p.id || "").startsWith("demo:")) return false;
      return true;
    });
  }

  function personSelectValue(p) {
    return String((p && (p.key || p.id)) || "");
  }

  function videoLearnId(item) {
    return String((item && (item.video_external_id || item.external_id)) || "").trim();
  }

  function learnSessionForItem(item) {
    if (!state.modal.learnOnVideo) state.modal.learnOnVideo = {};
    const vid = videoLearnId(item) || String(item.id || "");
    if (!state.modal.learnOnVideo[vid]) {
      state.modal.learnOnVideo[vid] = { people: [], lastLabel: "", lastCrop: "" };
    }
    return state.modal.learnOnVideo[vid];
  }

  function rememberLearnPerson(item, person) {
    const sess = learnSessionForItem(item);
    const id = String((person && (person.id || person.person_id)) || "");
    const label = String((person && (person.label || person.display_name)) || "Person");
    sess.lastLabel = label;
    if (person && person.crop) sess.lastCrop = person.crop;
    const rest = (sess.people || []).filter((p) => p.id !== id);
    sess.people = [{ id, label, taught: true, justNow: true }].concat(rest);
  }

  function learnOnVideoHtml(item) {
    const sess = learnSessionForItem(item);
    const rows = sess.people || [];
    if (!rows.length && !sess.lastLabel) return "";
    const list = rows
      .map((p) => {
        const mark = p.justNow || p.taught ? "Taught just now" : p.native ? "Already on this video" : "Known on this video";
        return `<div class="mb-rail-person"><span class="mb-rail-avatar" aria-hidden="true">${escapeHtml(
          (p.label || "?")[0] || "?"
        ).toUpperCase()}</span><div><strong>${escapeHtml(p.label)}</strong><div style="font-size:0.72rem;color:#86efac">${escapeHtml(
          mark
        )}</div></div></div>`;
      })
      .join("");
    const crop =
      sess.lastCrop
        ? `<div class="mb-learn-confirm-crop"><img src="${escapeAttr(sess.lastCrop)}" alt="" /><span>Confirmed crop</span></div>`
        : "";
    return `<div class="mb-learn-confirm" id="mb-learn-confirm">
      <p class="mb-learn-confirm-title">Learned${sess.lastLabel ? ": " + escapeHtml(sess.lastLabel) : ""}</p>
      <p class="mb-rail-empty">Already known on this video — no need to re-teach them. Box a different face to add someone else. Person dropdown stays empty until you choose.</p>
      ${crop}
      ${list}
    </div>`;
  }

  function mergeVideoPeopleIntoSession(item, apiPeople) {
    const sess = learnSessionForItem(item);
    const have = {};
    (sess.people || []).forEach((p) => {
      have[p.id] = p;
    });
    (apiPeople || []).forEach((p) => {
      const id = String(p.person_id || p.id || "");
      if (!id) return;
      const label = String(p.display_name || p.label || "Person");
      if (have[id]) {
        have[id].taught = have[id].taught || Boolean(p.taught);
        have[id].native = have[id].native || Boolean(p.native);
        have[id].label = have[id].label || label;
      } else {
        have[id] = {
          id,
          label,
          taught: Boolean(p.taught),
          native: Boolean(p.native),
          justNow: false,
        };
      }
    });
    sess.people = Object.keys(have)
      .map((k) => have[k])
      .sort((a, b) => {
        const ar = a.justNow ? 0 : a.taught ? 1 : 2;
        const br = b.justNow ? 0 : b.taught ? 1 : 2;
        if (ar !== br) return ar - br;
        return String(a.label || "").localeCompare(String(b.label || ""));
      });
  }

  function refreshLearnOnVideo(item) {
    const vid = videoLearnId(item);
    const host = document.getElementById("mb-learn-on-video");
    if (!vid) {
      if (host) host.innerHTML = learnOnVideoHtml(item);
      return;
    }
    fetch("/recognition/video-people?video_external_id=" + encodeURIComponent(vid))
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data && Array.isArray(data.people)) mergeVideoPeopleIntoSession(item, data.people);
        const el = document.getElementById("mb-learn-on-video");
        if (el) el.innerHTML = learnOnVideoHtml(item);
      })
      .catch(() => {
        const el = document.getElementById("mb-learn-on-video");
        if (el) el.innerHTML = learnOnVideoHtml(item);
      });
  }

  function personSelectHtml() {
    const known = knownPeopleOptions();
    const opts = ['<option value="">Choose a person…</option>'].concat(
      known.map(
        (p) =>
          `<option value="${escapeAttr(personSelectValue(p))}" data-label="${escapeAttr(p.label)}">${escapeHtml(
            p.label
          )}</option>`
      )
    );
    return opts.join("");
  }

  function fillLearnPersonSelect() {
    const sel = document.getElementById("mb-learn-person");
    if (!sel) return;
    const prev = sel.value;
    sel.innerHTML = personSelectHtml();
    if (prev && Array.from(sel.options).some((o) => o.value === prev)) sel.value = prev;
    else sel.value = "";
    syncLearnSubmitEnabled();
  }

  function renderLearnRail(item) {
    const panel = document.getElementById("mb-rail-panel");
    if (!panel) return;
    const t = String(item.type || "").toLowerCase();
    const canBox = t === "video" || t === "photo";
    const unlinkHtml = notThisEventHtml(item);
    if (!canBox) {
      panel.innerHTML = `<div class="mb-learn-panel">
        <h3>Learn</h3>
        <p class="mb-rail-empty">Pause a video or open a photo, then box a face.</p>
        ${unlinkHtml}
      </div>`;
      bindNotThisEvent(item);
      return;
    }
    const sess = learnSessionForItem(item);
    const known = knownPeopleOptions();
    panel.innerHTML = `<div class="mb-learn-panel">
      <h3>Learn</h3>
      <div id="mb-learn-on-video">${learnOnVideoHtml(item)}</div>
      <p class="mb-rail-empty">Choose a person, then box a face and/or highlight transcript words. <strong>Learn</strong> teaches MemoryBox whichever evidence you captured.</p>
      ${
        known.length
          ? `<p class="mb-rail-empty">${known.length} people in MemoryBox.</p>`
          : `<p class="mb-rail-empty" id="mb-learn-people-empty">Loading known people…</p>`
      }
      <label for="mb-learn-person">Person</label>
      <select id="mb-learn-person">${personSelectHtml()}</select>
      <div class="mb-learn-block">
        <h4>Face</h4>
        <p class="mb-rail-empty">Pause the video, then box a face.</p>
        <div class="mb-learn-actions">
          <button type="button" class="mb-viewer-footbtn" id="mb-learn-box"${t === "photo" || t === "video" ? "" : " disabled"}>Box face</button>
        </div>
        <div class="mb-learn-crop" id="mb-learn-crop"><img id="mb-learn-crop-img" alt="" /><span class="mb-rail-empty" id="mb-learn-crop-meta"></span></div>
      </div>
      ${
        t === "video"
          ? `<div class="mb-learn-block">
        <h4>Voice</h4>
        <p class="mb-rail-empty">Highlight words in the transcript under the video, then Learn. MemoryBox scores <em>this Person</em> on other videos — not every person against every file.</p>
        <div class="mb-learn-actions">
          <button type="button" class="mb-viewer-footbtn" id="mb-transcribe-this" data-transcribe-this="1">Transcribe this video</button>
        </div>
      </div>`
          : ""
      }
      <div class="mb-learn-actions mb-learn-actions-primary">
        <button type="button" class="mb-viewer-footbtn" id="mb-learn-submit" disabled>Learn</button>
      </div>
      <p class="mb-rail-empty" id="mb-learn-status">${
        sess.lastLabel ? "Learned " + escapeHtml(sess.lastLabel) + ". Capture another face or voice span for someone else." : ""
      }</p>
      <div class="mb-learn-block">
        <h4>Share</h4>
        <div class="mb-learn-actions">
          <button type="button" class="mb-viewer-footbtn" id="mb-share-toggle">Share</button>
        </div>
        <div class="mb-share-menu" id="mb-share-menu" hidden>
          <a class="mb-viewer-footbtn" id="mb-share-download" href="#" download>Download</a>
          <a class="mb-viewer-footbtn" id="mb-share-email" href="mailto:">Send via email</a>
        </div>
      </div>
      ${unlinkHtml}
    </div>`;
    const boxBtn = document.getElementById("mb-learn-box");
    const learnBtn = document.getElementById("mb-learn-submit");
    const personSel = document.getElementById("mb-learn-person");
    if (boxBtn) boxBtn.addEventListener("click", () => startLearnBoxing(item));
    if (learnBtn) learnBtn.addEventListener("click", () => submitExploreLearn(item));
    if (personSel) {
      personSel.value = "";
      personSel.addEventListener("change", () => syncLearnSubmitEnabled());
    }
    bindTranscribeThisTape(item);
    bindShareMenu(item);
    bindNotThisEvent(item);
    syncTranscribeButton();
    pauseExploreMedia();
    refreshLearnOnVideo(item);
    if (!known.length) {
      loadPeopleOptions().then(() => {
        if (state.modal.railTab !== "learn" || state.modal.openId !== item.id) return;
        fillLearnPersonSelect();
        const empty = document.getElementById("mb-learn-people-empty");
        if (empty) {
          empty.textContent = knownPeopleOptions().length
            ? ""
            : "No MemoryBox people yet — Teach a Person first, then return here.";
        }
      });
    }
  }

  function pauseExploreMedia() {
    const el = document.querySelector(".mb-ev-video-player");
    if (el && typeof el.pause === "function") {
      try {
        el.pause();
      } catch (e) {}
    }
  }

  function learnMediaEl() {
    return (
      document.querySelector(".mb-ev-video-player") ||
      document.querySelector(".mb-ev-photo-zoom img") ||
      document.querySelector(".mb-ev-photo-frame img")
    );
  }

  function learnFrameEl() {
    return (
      document.querySelector(".mb-ev-video-frame") ||
      document.querySelector(".mb-ev-photo-frame")
    );
  }

  function stopLearnBoxing() {
    state.modal.learnBoxing = false;
    state.modal.learnDrawing = false;
    const overlay = document.getElementById("mb-learn-overlay");
    if (overlay) overlay.classList.remove("is-boxing");
    const frame = learnFrameEl();
    if (frame) frame.classList.remove("is-learn-boxing");
  }

  function syncLearnOverlaySize() {
    const overlay = document.getElementById("mb-learn-overlay");
    const media = learnMediaEl();
    const frame = learnFrameEl();
    if (!overlay || !media || !frame) return;
    const mr = media.getBoundingClientRect();
    const fr = frame.getBoundingClientRect();
    const w = Math.max(1, Math.round(mr.width));
    const h = Math.max(1, Math.round(mr.height));
    overlay.style.left = Math.round(mr.left - fr.left) + "px";
    overlay.style.top = Math.round(mr.top - fr.top) + "px";
    overlay.style.width = w + "px";
    overlay.style.height = h + "px";
    overlay.width = w;
    overlay.height = h;
  }

  function mediaContentRect() {
    const media = learnMediaEl();
    const overlay = document.getElementById("mb-learn-overlay");
    if (!media || !overlay) return null;
    const nw = media.videoWidth || media.naturalWidth || 0;
    const nh = media.videoHeight || media.naturalHeight || 0;
    if (!nw || !nh) return null;
    const ew = overlay.width;
    const eh = overlay.height;
    const scale = Math.min(ew / nw, eh / nh);
    const drawW = nw * scale;
    const drawH = nh * scale;
    return {
      nw,
      nh,
      drawW,
      drawH,
      offsetX: (ew - drawW) / 2,
      offsetY: (eh - drawH) / 2,
    };
  }

  function drawLearnBox() {
    const overlay = document.getElementById("mb-learn-overlay");
    if (!overlay) return;
    const ctx = overlay.getContext("2d");
    ctx.clearRect(0, 0, overlay.width, overlay.height);
    const box = state.modal.learnBox;
    if (!box) return;
    const x = Math.min(box.x0, box.x1);
    const y = Math.min(box.y0, box.y1);
    const w = Math.abs(box.x1 - box.x0);
    const h = Math.abs(box.y1 - box.y0);
    ctx.strokeStyle = "#5ad1ff";
    ctx.lineWidth = 2;
    ctx.strokeRect(x, y, w, h);
    ctx.fillStyle = "rgba(90,209,255,0.15)";
    ctx.fillRect(x, y, w, h);
  }

  function overlayEventToLearnCanvas(e) {
    const overlay = document.getElementById("mb-learn-overlay");
    const r = overlay.getBoundingClientRect();
    return {
      x: (e.clientX - r.left) * (overlay.width / Math.max(1, r.width)),
      y: (e.clientY - r.top) * (overlay.height / Math.max(1, r.height)),
    };
  }

  function learnBoxToMediaPixels() {
    const content = mediaContentRect();
    const box = state.modal.learnBox;
    if (!content || !box) throw new Error("Pause until the picture is visible, then box again.");
    const { nw, nh, drawW, drawH, offsetX, offsetY } = content;
    let sx0 = ((Math.min(box.x0, box.x1) - offsetX) / drawW) * nw;
    let sy0 = ((Math.min(box.y0, box.y1) - offsetY) / drawH) * nh;
    let sx1 = ((Math.max(box.x0, box.x1) - offsetX) / drawW) * nw;
    let sy1 = ((Math.max(box.y0, box.y1) - offsetY) / drawH) * nh;
    sx0 = Math.max(0, Math.min(nw, sx0));
    sy0 = Math.max(0, Math.min(nh, sy0));
    sx1 = Math.max(0, Math.min(nw, sx1));
    sy1 = Math.max(0, Math.min(nh, sy1));
    const x = Math.floor(Math.min(sx0, sx1));
    const y = Math.floor(Math.min(sy0, sy1));
    const w = Math.ceil(Math.abs(sx1 - sx0));
    const h = Math.ceil(Math.abs(sy1 - sy0));
    if (w < 8 || h < 8) throw new Error("Face box too small — drag over the face.");
    return { x, y, w, h, vw: nw, vh: nh };
  }

  function captureLearnCrop() {
    const pix = learnBoxToMediaPixels();
    const media = learnMediaEl();
    const fw = media.videoWidth || media.naturalWidth || pix.vw;
    const fh = media.videoHeight || media.naturalHeight || pix.vh;
    const pad = 0.45;
    const x = Math.max(0, Math.floor(pix.x - pix.w * pad));
    const y = Math.max(0, Math.floor(pix.y - pix.h * pad));
    const x2 = Math.min(fw, Math.ceil(pix.x + pix.w + pix.w * pad));
    const y2 = Math.min(fh, Math.ceil(pix.y + pix.h + pix.h * pad));
    const w = Math.max(8, x2 - x);
    const h = Math.max(8, y2 - y);
    const full = document.createElement("canvas");
    full.width = Math.max(1, fw);
    full.height = Math.max(1, fh);
    const fctx = full.getContext("2d", { willReadFrequently: true });
    fctx.drawImage(media, 0, 0, full.width, full.height);
    const c = document.createElement("canvas");
    c.width = w;
    c.height = h;
    c.getContext("2d").drawImage(full, x, y, w, h, 0, 0, w, h);
    return {
      dataUrl: c.toDataURL("image/jpeg", 0.92),
      pix: { x, y, w, h, vw: fw, vh: fh },
    };
  }

  function updateLearnCropPreview() {
    const wrap = document.getElementById("mb-learn-crop");
    const img = document.getElementById("mb-learn-crop-img");
    const meta = document.getElementById("mb-learn-crop-meta");
    try {
      const { dataUrl, pix } = captureLearnCrop();
      if (img) img.src = dataUrl;
      if (meta) meta.textContent = `${pix.w}×${pix.h}px`;
      if (wrap) wrap.classList.add("is-on");
      state.modal.learnCrop = dataUrl;
      state.modal.learnPix = pix;
    } catch (err) {
      if (wrap) wrap.classList.remove("is-on");
      state.modal.learnCrop = null;
      state.modal.learnPix = null;
      if (meta) meta.textContent = err.message || "";
    }
    syncLearnSubmitEnabled();
  }

  function syncLearnSubmitEnabled() {
    const btn = document.getElementById("mb-learn-submit");
    const sel = document.getElementById("mb-learn-person");
    if (!btn) return;
    const span = state.modal.speechSpan;
    const hasSpan = span && Number(span.tEnd) > Number(span.tStart);
    btn.disabled = !((state.modal.learnCrop || hasSpan) && sel && sel.value);
  }

  function startLearnBoxing(item) {
    pauseExploreMedia();
    state.modal.learnBoxing = true;
    state.modal.learnBox = null;
    state.modal.learnCrop = null;
    state.modal.learnPix = null;
    const overlay = document.getElementById("mb-learn-overlay");
    const status = document.getElementById("mb-learn-status");
    const frame = learnFrameEl();
    if (!overlay) {
      if (status) status.textContent = "Open the video/photo first, then Box face.";
      return;
    }
    overlay.classList.add("is-boxing");
    if (frame) frame.classList.add("is-learn-boxing");
    syncLearnOverlaySize();
    drawLearnBox();
    bindLearnOverlayOnce();
    const media = learnMediaEl();
    if (media && media.getAttribute("data-learn-resize") !== "1") {
      media.setAttribute("data-learn-resize", "1");
      media.addEventListener("loadedmetadata", () => {
        if (state.modal.learnBoxing) syncLearnOverlaySize();
      });
    }
    if (status) status.textContent = "Crosshair on. Drag a box; a new drag starts over.";
    const wrap = document.getElementById("mb-learn-crop");
    if (wrap) wrap.classList.remove("is-on");
    syncLearnSubmitEnabled();
  }

  function bindLearnOverlayOnce() {
    const overlay = document.getElementById("mb-learn-overlay");
    if (!overlay || overlay.getAttribute("data-bound") === "1") return;
    overlay.setAttribute("data-bound", "1");
    const onPoint = (e) => {
      if (e.touches && e.touches[0]) {
        return { clientX: e.touches[0].clientX, clientY: e.touches[0].clientY };
      }
      return e;
    };
    overlay.addEventListener("mousedown", (e) => {
      if (!state.modal.learnBoxing) return;
      e.preventDefault();
      const p = overlayEventToLearnCanvas(onPoint(e));
      state.modal.learnBox = { x0: p.x, y0: p.y, x1: p.x, y1: p.y };
      state.modal.learnDrawing = true;
      drawLearnBox();
    });
    overlay.addEventListener("mousemove", (e) => {
      if (!state.modal.learnDrawing || !state.modal.learnBox) return;
      const p = overlayEventToLearnCanvas(onPoint(e));
      state.modal.learnBox.x1 = p.x;
      state.modal.learnBox.y1 = p.y;
      drawLearnBox();
    });
    overlay.addEventListener(
      "touchstart",
      (e) => {
        if (!state.modal.learnBoxing) return;
        e.preventDefault();
        const p = overlayEventToLearnCanvas(onPoint(e));
        state.modal.learnBox = { x0: p.x, y0: p.y, x1: p.x, y1: p.y };
        state.modal.learnDrawing = true;
        drawLearnBox();
      },
      { passive: false }
    );
    overlay.addEventListener(
      "touchmove",
      (e) => {
        if (!state.modal.learnDrawing || !state.modal.learnBox) return;
        e.preventDefault();
        const p = overlayEventToLearnCanvas(onPoint(e));
        state.modal.learnBox.x1 = p.x;
        state.modal.learnBox.y1 = p.y;
        drawLearnBox();
      },
      { passive: false }
    );
    const endDraw = () => {
      if (!state.modal.learnDrawing) return;
      state.modal.learnDrawing = false;
      updateLearnCropPreview();
    };
    window.addEventListener("mouseup", endDraw);
    window.addEventListener("touchend", endDraw);
    if (!window.__mbLearnOverlayResize) {
      window.__mbLearnOverlayResize = true;
      window.addEventListener("resize", () => {
        if (!state.modal.learnBoxing) return;
        syncLearnOverlaySize();
        drawLearnBox();
      });
    }
  }

  async function ensureLearnPersonId(personKey) {
    const key = String(personKey || "").trim();
    if (!key) return null;
    if (key.startsWith("mb:")) {
      const person_id = key.slice(3);
      const res = await fetch("/people/ensure", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ person_id }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || res.statusText);
      return data.person && (data.person.id || person_id);
    }
    if (key.startsWith("immich:")) {
      const rest = key.slice("immich:".length);
      const i = rest.indexOf(":");
      if (i < 0) throw new Error("Invalid photo-library person.");
      const external_id = decodeURIComponent(rest.slice(0, i));
      const display_name = decodeURIComponent(rest.slice(i + 1));
      const res = await fetch("/people/ensure", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider_key: "immich",
          external_id,
          display_name,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || res.statusText);
      return data.person && data.person.id;
    }
    const res = await fetch("/people/ensure", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ person_id: key }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || res.statusText);
    return data.person && (data.person.id || key);
  }

  async function submitExploreLearn(item) {
    const status = document.getElementById("mb-learn-status");
    const sel = document.getElementById("mb-learn-person");
    try {
      const span = state.modal.speechSpan;
      const hasSpan = span && Number(span.tEnd) > Number(span.tStart);
      if ((!state.modal.learnCrop || !state.modal.learnPix) && !hasSpan) {
        throw new Error("Box a face or select a transcript span first.");
      }
      if (!sel || !sel.value) throw new Error("Choose a person. Nothing is pre-selected.");
      const personId = await ensureLearnPersonId(sel.value);
      if (!personId) throw new Error("Could not resolve that person in MemoryBox.");
      const learnedLabel =
        (sel.options[sel.selectedIndex] && sel.options[sel.selectedIndex].getAttribute("data-label")) ||
        "Person";
      const did = [];
      if (hasSpan) {
        const res = await fetch("/speech/learn", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            person_id: personId,
            video_external_id: item.video_external_id || item.external_id,
            t_start: Number(span.tStart),
            t_end: Number(span.tEnd),
            video_provider_key: item.video_provider_key || item.provider_key || "hvrt",
          }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok || data.ok === false) {
          throw new Error(data.detail || data.reason || res.statusText);
        }
        const n = Number(data.queued_other_videos || 0);
        did.push(
          "voice on this video" +
            (n
              ? "; scoring " + learnedLabel + " on " + n + " other videos (this Person only)"
              : "")
        );
      }
      if (state.modal.learnCrop && state.modal.learnPix) {
        const media = learnMediaEl();
        const tSec =
          media && media.currentTime != null ? Number(media.currentTime) : Number(item.t || 0);
        const pix = state.modal.learnPix;
        const faceId = "explore-learn-" + String(Date.now());
        const res = await fetch("/recognition/learn", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            person_id: personId,
            face_external_id: faceId,
            video_external_id: item.video_external_id || item.external_id || null,
            t_sec: tSec,
            bbox: {
              x: pix.x,
              y: pix.y,
              w: pix.w,
              h: pix.h,
              frame_w: pix.vw,
              frame_h: pix.vh,
            },
            crop_jpeg_base64: state.modal.learnCrop,
            provider_key: item.video_provider_key || item.provider_key || "immich",
          }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok || data.ok === false) {
          throw new Error(data.detail || data.reason || res.statusText);
        }
        did.push("face on this video");
        if (!Array.isArray(item.people)) item.people = [];
        if (!item.people.includes(learnedLabel)) item.people.push(learnedLabel);
      }
      rememberLearnPerson(item, {
        id: personId,
        label: learnedLabel,
        crop: state.modal.learnCrop || null,
      });
      if (status)
        status.textContent = "Learned " + learnedLabel + " — " + did.join("; ") + ".";
      renderLearnRail(item);
      return;
    } catch (err) {
      if (status) status.textContent = String(err.message || err);
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
      /* Learn / Share / Transcribe live on the Learn tab. Footer is transcript only. */
    } else {
      bits.push(
        `<span class="mb-ev-meta">${escapeHtml(fmtCardDate(item.date))} · ${escapeHtml(
          t || "evidence"
        )}</span>`
      );
    }
    foot.innerHTML =
      (bits.length ? `<div class="mb-viewer-footrow">${bits.join("")}</div>` : "") +
      (t === "video"
        ? `<div class="mb-ev-transcript is-on" id="mb-ev-transcript" aria-label="Synchronized transcript"><div class="mb-ev-transcript-empty">Loading transcript…</div></div>`
        : "");
    bindTranscribeThisTape(item);
  }


  function renderTeachSlot(_item) {
    const slot = document.getElementById("mb-modal-teach");
    if (!slot) return;
    slot.hidden = true;
    slot.innerHTML = "";
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

  function bindSmsAttachActions(item) {
    const eid = item && item.evidence_id;
    if (!eid) return;
    const attachApi =
      item.type === "email" || item.channel === "email" ? "email-attachment" : "sms-attachment";
    document.querySelectorAll(".mb-sms-attach-img").forEach((img) => {
      const li = img.closest("li");
      const idx = li ? li.getAttribute("data-att-index") || "0" : "0";
      const pending = img.getAttribute("data-src");
      if (pending) {
        fetch(
          `/explore/api/${attachApi}/${encodeURIComponent(eid)}/meta?index=${idx}`
        )
          .then((r) => (r.ok ? r.json() : null))
          .then((data) => {
            if (data && data.bytes_present) {
              img.setAttribute("src", pending);
              img.removeAttribute("data-src");
              return;
            }
            img.dispatchEvent(new Event("error"));
          })
          .catch(() => img.dispatchEvent(new Event("error")));
      }
      img.addEventListener("error", () => {
        const box = img.parentElement;
        if (!box) return;
        const name = img.getAttribute("alt") || "attachment";
        const li = img.closest("li");
        if (li) {
          const extra = li.querySelector(".mb-sms-optional-artifact");
          if (extra) extra.remove();
        }
        box.innerHTML =
          "<p>This attachment is listed on the message, but the image bytes were not stored at ingest.</p>" +
          "<p class=\"mb-ev-meta\">Missing file: " +
          escapeHtml(name) +
          "</p>";
        const idx = li ? li.getAttribute("data-att-index") || "0" : "0";
        fetch(
          `/explore/api/${attachApi}/${encodeURIComponent(eid)}/meta?index=${idx}`
        )
          .then((r) => (r.ok ? r.json() : null))
          .then((data) => {
            if (!data || data.bytes_present) return;
            const bits = [];
            if (data.import_path) bits.push("export: " + data.import_path);
            if (data.attachments_dir) bits.push("attachments dir: " + data.attachments_dir);
            if (bits.length) {
              const p = document.createElement("p");
              p.className = "mb-ev-meta";
              p.textContent = bits.join(" · ");
              box.appendChild(p);
            }
          })
          .catch(() => {});
      });
    });
    document.querySelectorAll(".mb-sms-to-library").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const idx = Number(btn.getAttribute("data-att-index") || 0);
        const status = btn.parentElement && btn.parentElement.querySelector(".mb-sms-to-library-status");
        btn.disabled = true;
        if (status) {
          status.hidden = false;
          status.textContent = "Copying into MemoryBox…";
        }
        try {
          const res = await fetch(
            `/explore/api/${attachApi}/${encodeURIComponent(eid)}/to-library?index=${idx}`,
            { method: "POST" }
          );
          const data = await res.json().catch(() => ({}));
          if (!res.ok) throw new Error(data.detail || res.status);
          if (status) {
            status.textContent = "In MemoryBox library (not Immich).";
          }
          if (data.href) {
            const a = document.createElement("a");
            a.className = "mb-viewer-footbtn";
            a.href = data.href;
            a.textContent = "Open in Artifacts";
            btn.replaceWith(a);
          } else {
            btn.textContent = "Added";
          }
        } catch (err) {
          btn.disabled = false;
          if (status) status.textContent = "Could not add: " + err;
        }
      });
    });
  }

  const FACE_HOLD_MS = 1000;

  function bindFaceHoldReveal() {
    const frame =
      document.querySelector(".mb-ev-photo-frame") ||
      document.querySelector(".mb-ev-video-frame");
    if (!frame) return;
    let holdTimer = 0;
    const clearHold = () => {
      if (holdTimer) {
        window.clearTimeout(holdTimer);
        holdTimer = 0;
      }
      frame.classList.remove("mb-faces-revealed");
    };
    const startHold = () => {
      if (holdTimer) window.clearTimeout(holdTimer);
      holdTimer = window.setTimeout(() => {
        frame.classList.add("mb-faces-revealed");
        holdTimer = 0;
      }, FACE_HOLD_MS);
    };
    frame.addEventListener("mouseenter", startHold);
    frame.addEventListener("mouseleave", clearHold);
  }

  function stopSpeechPoll() {
    if (state.modal && state.modal.speechPoll) {
      window.clearTimeout(state.modal.speechPoll);
      state.modal.speechPoll = 0;
    }
  }

  function setSpeechStatus(message) {
    const msg = String(message || "");
    const learn = document.getElementById("mb-learn-status");
    if (learn && msg) learn.textContent = msg;
    const box = document.getElementById("mb-ev-transcript");
    if (!box) return;
    box.classList.add("is-on");
    const empty = box.querySelector(".mb-ev-transcript-empty");
    if (empty) empty.textContent = msg;
  }

  function syncTranscribeButton() {
    document.querySelectorAll("[data-transcribe-this]").forEach((el) => {
      if (state.modal.transcriptHasWords) {
        el.disabled = true;
        el.textContent = "Already transcribed";
        el.title = "This video already has a transcript. Pressing it again will not duplicate words.";
      } else {
        el.disabled = false;
        el.textContent = "Transcribe this video";
        el.title = "";
      }
    });
  }

  function bindShareMenu(item) {
    const href = String(item.play_url || item.media_url || "").split("?")[0];
    const toggle = document.getElementById("mb-share-toggle");
    const menu = document.getElementById("mb-share-menu");
    if (toggle && menu) {
      toggle.addEventListener("click", () => {
        menu.hidden = !menu.hidden;
      });
    }
    const dl = document.getElementById("mb-share-download");
    if (dl) {
      if (href) {
        dl.href = href;
        dl.setAttribute("download", String(item.video_external_id || item.external_id || "memory") + ".mp4");
      } else {
        dl.setAttribute("aria-disabled", "true");
      }
    }
    const em = document.getElementById("mb-share-email");
    if (em) {
      const title = String(item.title || item.video_external_id || "MemoryBox video");
      em.href =
        "mailto:?subject=" +
        encodeURIComponent("MemoryBox: " + title) +
        "&body=" +
        encodeURIComponent(
          "Sharing a MemoryBox video.\n\n" +
            title +
            "\nId: " +
            String(item.video_external_id || item.external_id || "") +
            "\n\nDownload the file from MemoryBox first if you need to attach it."
        );
    }
  }

  function bindTranscribeThisTape(item) {
    document.querySelectorAll("[data-transcribe-this]").forEach((btn) => {
      btn.onclick = () => {
        if (state.modal.transcriptHasWords || btn.disabled) return;
        queueThisTape(item, btn);
      };
    });
    syncTranscribeButton();
  }

  function queueThisTape(item, btn) {
    const vid = String(item.video_external_id || item.external_id || "").trim();
    const box = document.getElementById("mb-ev-transcript");
    if (!vid) return;
    if (state.modal.transcriptHasWords) {
      syncTranscribeButton();
      return;
    }
    state.modal.transcriptOn = true;
    document.querySelectorAll("[data-transcribe-this]").forEach((el) => {
      el.disabled = true;
      el.textContent = "Transcribing…";
    });
    setSpeechStatus("Transcribing this video…");
    if (box) {
      box.classList.add("is-on");
      box.innerHTML = '<div class="mb-ev-transcript-empty">Transcribing this video…</div>';
    }
    const pk = String(item.video_provider_key || item.provider_key || "").trim();
    let url = "/speech/transcribe-now?video_external_id=" + encodeURIComponent(vid);
    if (pk) url += "&video_provider_key=" + encodeURIComponent(pk);
    fetch(url, { method: "POST" })
      .then((r) => r.json().then((data) => ({ ok: r.ok, data })))
      .then(({ ok, data }) => {
        if (!ok || (data && data.ok === false)) {
          const err = (data && (data.detail || data.error)) || "transcribe failed";
          throw new Error(err);
        }
        if (data && data.already_transcribed) {
          state.modal.transcriptHasWords = true;
          syncTranscribeButton();
          bindSpeechTranscript(item);
          return;
        }
        setSpeechStatus("Transcribing this video… words appear here when faster-whisper finishes.");
        state.modal.speechPoll = window.setTimeout(() => bindSpeechTranscript(item), 1500);
      })
      .catch((err) => {
        document.querySelectorAll("[data-transcribe-this]").forEach((el) => {
          el.disabled = false;
          el.textContent = "Transcribe this video";
        });
        setSpeechStatus(String(err.message || err));
        if (box) {
          box.innerHTML =
            '<div class="mb-ev-transcript-empty">' +
            escapeHtml(String(err.message || err)) +
            "</div>";
        }
      });
  }

  function paintTranscriptEmpty(box, item, message, opts) {
    const busy = !!(opts && opts.busy);
    state.modal.transcriptHasWords = false;
    setSpeechStatus(message);
    box.innerHTML = '<div class="mb-ev-transcript-empty">' + escapeHtml(message) + "</div>";
    bindTranscribeThisTape(item);
    if (state.modal.transcriptOn) box.classList.add("is-on");
    syncTranscribeButton();
    const footBtn = document.getElementById("mb-transcribe-this");
    if (footBtn && busy) {
      footBtn.disabled = true;
      footBtn.textContent = "Transcribing…";
    }
  }

  function bindSpeechTranscript(item) {
    const box = document.getElementById("mb-ev-transcript");
    if (!box) return;
    stopSpeechPoll();
    const vid = String(item.video_external_id || item.external_id || "").trim();
    if (!vid) {
      paintTranscriptEmpty(box, item, "No video id for transcript.", {});
      return;
    }
    const ac = new AbortController();
    const abortTimer = window.setTimeout(() => ac.abort(), 12000);
    fetch("/speech/transcript?video_external_id=" + encodeURIComponent(vid), {
      signal: ac.signal,
    })
      .then((r) =>
        r.json().then(
          (data) => ({ ok: r.ok, data }),
          () => ({ ok: false, data: null })
        )
      )
      .then(({ ok, data }) => {
        window.clearTimeout(abortTimer);
        if (!ok || !data) {
          paintTranscriptEmpty(
            box,
            item,
            "Transcript API did not return words. Use Learn → Transcribe this video (restart Serve if the button fails).",
            {}
          );
          return;
        }
        const words = Array.isArray(data.words) ? data.words : [];
        const turns = Array.isArray(data.turns) ? data.turns : [];
        const moments = Array.isArray(data.moments) ? data.moments : [];
        const fullText = String(data.full_text || "").trim();
        const qst = String((data.queue && data.queue.status) || "");
        const reason = String((data.queue && data.queue.reason) || "").trim();
        if (!words.length && !moments.length && !fullText) {
          let empty =
            "No words on this video yet. Use Learn → Transcribe this video.";
          let busy = false;
          if (qst === "queued" || qst === "running") {
            empty = "Transcribing this video… words appear here when faster-whisper finishes.";
            busy = true;
            state.modal.speechPoll = window.setTimeout(() => bindSpeechTranscript(item), 2000);
          } else if (qst === "failed") {
            empty =
              "Transcribe failed" +
              (reason ? ": " + reason : ".") +
              " Use Learn → Transcribe this video to retry.";
          } else if (qst === "completed") {
            empty = "Last pass stored no speech. Use Learn → Transcribe this video to retry.";
          }
          paintTranscriptEmpty(box, item, empty, { busy: busy || !state.modal.speechAutoStarted });
          if (!state.modal.speechAutoStarted && qst !== "running") {
            state.modal.speechAutoStarted = true;
            queueThisTape(item);
          }
          return;
        }
        const tokens = words.length
          ? words
          : moments.length
            ? moments.map((m) => ({ token: m.text, t_start: m.t_start, t_end: m.t_end }))
            : [{ token: fullText, t_start: 0, t_end: 0 }];
        state.modal.transcriptHasWords = tokens.some((w) =>
          String(w.token || w.text || w.word || "").trim()
        );
        box.innerHTML = tokens
          .map((w, i) => {
            const st = Number(w.t_start != null ? w.t_start : w.start_sec || 0);
            const en = Number(w.t_end != null ? w.t_end : w.end_sec || st);
            const label = String(w.token || w.text || w.word || "").trim();
            const spk = (turns.find((t) => Number(t.t_start) <= st && Number(t.t_end) >= st) || {})
              .status;
            const who = spk && spk !== "anonymous" ? " " + String(spk) : "";
            return (
              '<span class="mb-ev-word" data-i="' +
              i +
              '" data-start="' +
              st +
              '" data-end="' +
              en +
              '" title="' +
              escapeAttr(st.toFixed(1) + "s") +
              '">' +
              escapeHtml(label) +
              who +
              "</span>"
            );
          })
          .join(" ");
        syncTranscribeButton();
        const player = document.querySelector(".mb-ev-video-player");
        const markActive = () => {
          if (!player) return;
          const t = Number(player.currentTime || 0);
          box.querySelectorAll(".mb-ev-word").forEach((el) => {
            const a = Number(el.getAttribute("data-start") || 0);
            const b = Number(el.getAttribute("data-end") || a);
            el.classList.toggle("is-active", t >= a - 0.05 && t <= b + 0.12);
          });
        };
        if (player) player.addEventListener("timeupdate", markActive);
        box.addEventListener("click", (ev) => {
          const el = ev.target.closest(".mb-ev-word");
          if (!el || !player) return;
          const st = Number(el.getAttribute("data-start") || 0);
          try {
            player.currentTime = st;
          } catch (e) {}
        });
        box.addEventListener("mouseup", () => {
          const sel = window.getSelection && window.getSelection();
          if (!sel || sel.isCollapsed) return;
          const wordsEls = Array.from(box.querySelectorAll(".mb-ev-word"));
          const picked = wordsEls.filter((el) => sel.containsNode(el, true));
          if (!picked.length) return;
          const tStart = Number(picked[0].getAttribute("data-start") || 0);
          const tEnd = Number(picked[picked.length - 1].getAttribute("data-end") || tStart);
          state.modal.speechSpan = { tStart, tEnd };
          syncLearnSubmitEnabled();
          const status = document.getElementById("mb-learn-status");
          if (status)
            status.textContent =
              "Voice span " + tStart.toFixed(1) + "s–" + tEnd.toFixed(1) + "s. Choose a person and Learn.";
        });
        box.addEventListener("keydown", (ev) => {
          const span = state.modal.speechSpan;
          if (!span) return;
          if (ev.key === "ArrowLeft") {
            span.tStart = Math.max(0, Number(span.tStart) - (ev.shiftKey ? 0.2 : 0.05));
            ev.preventDefault();
          }
          if (ev.key === "ArrowRight") {
            span.tEnd = Number(span.tEnd) + (ev.shiftKey ? 0.2 : 0.05);
            ev.preventDefault();
          }
          state.modal.speechSpan = span;
          syncLearnSubmitEnabled();
        });
        box.setAttribute("tabindex", "0");
        if (state.modal.transcriptOn) box.classList.add("is-on");
        syncTranscribeButton();
      })
      .catch(() => {
        window.clearTimeout(abortTimer);
        setSpeechStatus("Transcript unavailable. Restart Serve, then Learn → Transcribe this video.");
        paintTranscriptEmpty(
          box,
          item,
          "Transcript unavailable. Restart Serve, then Learn → Transcribe this video.",
          {}
        );
      });
  }

  function appearanceViewBounds(item) {
    const t0raw = item && item.start_sec != null ? item.start_sec : item && item.t;
    const t0 = Number(t0raw);
    const t1 = item && item.end_sec != null ? Number(item.end_sec) : NaN;
    const start = Number.isFinite(t0) && t0 >= 0 ? t0 : 0;
    const stop = Number.isFinite(t1) && t1 > start ? t1 : null;
    return { start, stop };
  }

  function bindAppearanceView(el, item) {
    /* ACR-P2-001: view into the original [start, stop], then end. No continue-on-tape. */
    const bounds = appearanceViewBounds(item);
    const start = bounds.start;
    const stop = bounds.stop;
    const EPS = 0.08;
    const seekToStart = () => {
      try {
        if (Number.isFinite(start)) el.currentTime = start;
      } catch (e) {}
    };
    const clampVisit = () => {
      if (stop == null) return;
      try {
        if (el.currentTime < start - EPS) el.currentTime = start;
        if (el.currentTime >= stop - EPS) {
          el.pause();
          el.currentTime = stop;
        }
      } catch (e) {}
    };
    const onMeta = () => {
      seekToStart();
      el.removeEventListener("loadedmetadata", onMeta);
    };
    el.addEventListener("loadedmetadata", onMeta);
    el.addEventListener("timeupdate", clampVisit);
    el.addEventListener("seeking", clampVisit);
    el.addEventListener("seeked", clampVisit);
    el.addEventListener("play", () => {
      if (stop != null && el.currentTime >= stop - EPS) seekToStart();
    });
    seekToStart();
  }

  function bindExploreVideoPlayer(item) {
    const el = document.querySelector(".mb-ev-video-player");
    if (!el) return;
    const attach = () => bindAppearanceView(el, item);
    const immichSrc = immichVideoSrc(item);
    if (immichSrc) {
      el.src = String(immichSrc).split("?")[0];
      el.preload = "metadata";
      attach();
      el.load();
      return;
    }
    const vid = String((item && item.video_external_id) || "").trim();
    if (!vid) return;
    const encoded = encodeURIComponent(vid);
    fetch("/review/videos/" + encoded + "/browser-proxy", { method: "POST" })
      .then((res) => {
        el.src =
          "/review/media/" + encoded + (res.ok ? "?proxy=1" : "");
        attach();
        el.load();
      })
      .catch(() => {
        el.src = "/review/media/" + encoded;
        attach();
        el.load();
      });
  }

  function looksLikeUuid(value) {
    const raw = String(value || "").trim();
    return raw.length === 36 && (raw.match(/-/g) || []).length === 4;
  }

  function photoDeepLinkItem(photoId) {
    const id = String(photoId || "").trim();
    const thumb = "/library/media/photo/" + encodeURIComponent(id);
    return {
      id: "photo:immich:" + id,
      type: "photo",
      title: "Photo",
      external_id: id,
      provider_key: "immich",
      media_url: thumb,
      thumb_url: thumb,
      teachable: true,
    };
  }

  function videoDeepLinkItem(videoId, t0) {
    const vid = String(videoId || "").trim();
    const t = Number(t0) || 0;
    const immich = looksLikeUuid(vid);
    return {
      id: "video:direct:" + vid + ":" + t,
      type: "video",
      kind: "video",
      title: vid,
      video_external_id: vid,
      external_id: vid,
      provider_key: immich ? "immich" : "hvrt",
      video_provider_key: immich ? "immich" : "hvrt",
      t: t,
      start_sec: t,
      play_url: immich
        ? "/library/media/immich-video/" + encodeURIComponent(vid) + "?t=" + t
        : "/review/media/" + encodeURIComponent(vid) + "?t=" + t,
      teachable: true,
      paused_frame: true,
    };
  }

  function immichVideoSrc(item) {
    const play = String((item && item.play_url) || "");
    if (play.indexOf("/library/media/immich-video/") >= 0) {
      return play.split("?")[0];
    }
    const pk = String((item && item.provider_key) || "").toLowerCase();
    const asset = String(
      (item && (item.video_external_id || item.external_id)) || ""
    ).trim();
    const useAsset =
      looksLikeUuid(String((item && item.video_external_id) || "").trim())
        ? String(item.video_external_id).trim()
        : looksLikeUuid(asset) && pk === "immich"
          ? asset
          : "";
    if (
      useAsset &&
      String((item && item.type) || "").toLowerCase() === "video"
    ) {
      return "/library/media/immich-video/" + encodeURIComponent(useAsset);
    }
    return "";
  }

  function firstImageAttachIndex(item) {
    const atts = Array.isArray(item.attachments) ? item.attachments : [];
    const idx = atts.findIndex((a) =>
      /image|jpe?g|png|gif|heic|webp|bmp|tif/i.test(
        String((a && (a.attachment_type || a.mime_type || a.filename)) || "")
      )
    );
    return idx >= 0 ? idx : atts.length ? 0 : -1;
  }

  function parseQuotedEmail(text) {
    const raw = String(text || "").replace(/\r\n/g, "\n").trim();
    if (!raw) return [];
    const re = /^(On .{8,240}? wrote:|-----Original Message-----)\s*$/gm;
    const parts = raw.split(re);
    const turns = [];
    const lead = (parts[0] || "").trim();
    if (lead) turns.push({ header: null, from: null, body: lead });
    for (let i = 1; i < parts.length; i += 2) {
      const header = String(parts[i] || "").trim();
      const body = String(parts[i + 1] || "").trim();
      let from = null;
      const addrM = header.match(/<([^>]+@[^>]+)>/);
      const addr = addrM ? addrM[1] : "";
      let name = "";
      const pm = header.match(/\b(?:AM|PM),?\s+([^<]+?)\s*</i);
      if (pm && !/^\d/.test(pm[1].trim())) name = pm[1].trim().replace(/^,/, "").trim();
      if (!name) {
        const commas = [...header.matchAll(/,\s*([^,<\n]+)\s*</g)];
        if (commas.length) name = commas[commas.length - 1][1].trim();
      }
      if (name && addr) from = name + " <" + addr + ">";
      else from = name || addr || (/^-----/.test(header) ? "Earlier message" : null);
      turns.push({ header, from, body });
    }
    return turns.length ? turns : [{ header: null, from: null, body: raw }];
  }

  function emailTurnsHtml(turns, opts) {
    const compact = !!(opts && opts.compact);
    const list = Array.isArray(turns) ? turns : [];
    const shown = compact ? list.slice(0, 4) : list;
    if (!shown.length) return "";
    return (
      '<div class="mb-ev-turns" id="mb-email-turns">' +
      shown
        .map((turn, i) => {
          const who = escapeHtml(turn.from || (i === 0 ? "This message" : "Quoted"));
          const hd = turn.header
            ? '<div class="mb-ev-turn-hd">' + escapeHtml(turn.header) + "</div>"
            : '<div class="mb-ev-turn-hd">' + who + "</div>";
          return (
            '<article class="mb-ev-turn">' +
            hd +
            '<div class="mb-ev-turn-body">' +
            escapeHtml(turn.body || "") +
            "</div></article>"
          );
        })
        .join("") +
      (compact && list.length > shown.length
        ? '<p class="mb-ev-meta">Open the card for the rest of the quoted history.</p>'
        : "") +
      "</div>"
    );
  }

  function bindEmailStructuredView(item) {
    const t = String((item && item.type) || "").toLowerCase();
    const eid = item && item.evidence_id;
    if (t !== "email" || !eid) return;
    const host = document.getElementById("mb-email-turns");
    if (!host) return;
    fetch("/explore/api/email/" + encodeURIComponent(eid))
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!data || !data.ok) return;
        item._emailView = data;
        if (Array.isArray(data.people) && data.people.length) {
          item.people = data.people;
          renderRailPanel(item);
        }
        const wrap = document.createElement("div");
        wrap.innerHTML = emailTurnsHtml(data.turns);
        const next = wrap.firstElementChild;
        if (next) host.replaceWith(next);
        const note = document.getElementById("mb-email-thread-note");
        if (note && data.quoted_history_in_body) {
          note.hidden = false;
        }
      })
      .catch(() => {});
  }

  function renderEvidenceBody(item) {
    const t = String(item.type || "").toLowerCase();
    const media = item.media_url || item.thumb_url || "";
    if (t === "photo") {
      const zoom = Number(state.modal.zoom) || 1;
      // Width-based zoom on the photo+faces wrapper so Immich boxes stay aligned.
      const img = media
        ? `<img src="${escapeAttr(media)}" alt="${escapeAttr(
            item.title || "Photo"
          )}" />`
        : escapeHtml(item.preview || item.title || "Photo");
      const zoomWrapStyle =
        zoom === 1
          ? ""
          : ` style="width:${(zoom * 100).toFixed(2)}%;max-width:none"`;
      return `<div class="mb-ev-photo${zoom !== 1 ? " is-zoomed" : ""}" aria-label="Photo workspace">
        <div class="mb-ev-photo-frame"><div class="mb-ev-photo-zoom"${zoomWrapStyle}>${img}${faceBoxHtml(item)}</div>
        <canvas class="mb-learn-overlay" id="mb-learn-overlay"></canvas></div>
      </div>`;
    }
    if (t === "video") {
      const t0 = item.t != null ? Number(item.t) : 0;
      const vid = String(item.video_external_id || "").trim();
      const immichStream = immichVideoSrc(item);
      const canStream =
        Boolean(vid) &&
        !vid.startsWith("video-peggy-") &&
        !vid.startsWith("video-library-") &&
        !immichStream;
      const stream = immichStream
        ? immichStream
        : canStream
          ? `/review/media/${encodeURIComponent(vid)}?proxy=1`
          : "";
      const posterAttr = media ? ` poster="${escapeAttr(media)}"` : "";
      const stage = stream
        ? `<video class="mb-ev-video-player" controls preload="metadata" src="${escapeAttr(
            stream
          )}"${posterAttr}></video>`
        : media
          ? `<img src="${escapeAttr(media)}" alt="" />`
          : "Paused frame · face teach applies here only (not during playback)";
      return `<div class="mb-ev-video-shell">
        <div class="mb-ev-video-frame" id="mb-ev-video-frame">
          ${stage}
          ${faceBoxHtml(item)}
          <canvas class="mb-learn-overlay" id="mb-learn-overlay"></canvas>
        </div>
        ${
          stream
            ? ""
            : `<div class="mb-ev-video-transport" aria-label="Video transport">
          <span>▶︎</span>
          <span>${t0.toFixed(1)}s · paused frame</span>
        </div>`
        }
      </div>`;
    }
    if (t === "email" || isSmsTextItem(item)) {
      const atts = Array.isArray(item.attachments) ? item.attachments : [];
      const mapped = Array.isArray(item.identity_mapped) ? item.identity_mapped : [];
      const eid = escapeAttr(item.evidence_id || "");
      const attachApi = t === "email" ? "email-attachment" : "sms-attachment";
      const attItems = atts
        .map((a, i) => {
          const name = escapeHtml(a.filename || a.source_ref || "attachment");
          const kindBits = [];
          if (a.kind) kindBits.push(String(a.kind));
          if (a.attachment_type) kindBits.push(String(a.attachment_type));
          if (a.mime_type) kindBits.push(String(a.mime_type));
          if (a.content_id) kindBits.push("cid:" + String(a.content_id));
          const kind = kindBits.length ? " · " + escapeHtml(kindBits.join(" · ")) : "";
          const src = "/explore/api/" + attachApi + "/" + eid + "?index=" + i;
          const isImg = /image|jpe?g|png|gif|heic|webp|bmp|tif/i.test(
            String(a.attachment_type || a.mime_type || a.filename || "")
          );
          const preview = isImg
            ? '<div class="mb-ev-attach-preview"><img class="mb-sms-attach-img" data-src="' +
              escapeAttr(src) +
              '" alt="' +
              name +
              '" /></div>'
            : '<p><a class="mb-viewer-footbtn" href="' +
              escapeAttr(src) +
              '" target="_blank" rel="noopener">Open ' +
              name +
              "</a></p>";
          return (
            '<li data-att-index="' +
            i +
            '">' +
            name +
            kind +
            preview +
            '<details class="mb-sms-optional-artifact"><summary>Optional: copy into Artifacts (not automatic)</summary>' +
            '<button type="button" class="mb-viewer-footbtn mb-sms-to-library" data-att-index="' +
            i +
            '">Copy to Artifacts</button>' +
            '<span class="mb-sms-to-library-status" hidden></span></details></li>'
          );
        })
        .join("");
      const attLabel =
        t === "email"
          ? "MIME part on this email; stored at ingest (not Immich, not a Gallery photo). Optional Artifact copy is explicit only."
          : "first-class on this SMS; stored at ingest (not Immich). Optional Artifact copy is not required.";
      const attHtml = atts.length
        ? '<div class="mb-ev-attach"><strong>📎 ' +
          atts.length +
          " attachment" +
          (atts.length === 1 ? "" : "s") +
          "</strong> — " +
          attLabel +
          "<ul>" +
          attItems +
          "</ul></div>"
        : "";
      const phoneHtml = mapped.length
        ? `<p class="mb-ev-meta">Confirmed phone/handle: ${mapped
            .map((m) => escapeHtml(m.handle || m.normalized || ""))
            .filter(Boolean)
            .join(", ")} — also shown on People.</p>`
        : "";
      return `<div class="mb-ev-email-wrap">
        <p class="mb-ev-meta">${escapeHtml(item.from || "")}${
        item.title ? " · " + escapeHtml(item.title) : ""
      }</p>
        ${emailTurnsHtml(parseQuotedEmail(item.detail || item.preview || ""))}
        <p class="mb-ev-meta" id="mb-email-thread-note" hidden>Quoted history is in this message body — not an invented RFC thread.</p>
        ${attHtml}
        <p class="mb-ev-meta">${escapeHtml(fmtCardDate(item.date))} · Email${
        item.direction ? " · " + escapeHtml(item.direction) : ""
      }</p>${phoneHtml}</div>`;
    }
    if (t === "story") {
      const img = media
        ? `<div class="mb-ev-photo"><img src="${escapeAttr(media)}" alt="" style="max-width:100%;border-radius:10px" /></div>`
        : "";
      return `${img}<p class="mb-ev-meta">${escapeHtml(fmtCardDate(item.date))} · Story (contextual meaning)</p>
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
    if (String(item.type || "") === "daycard") {
      const s = item._daySummary || summarizeDay(item._dayItems || []);
      return `<div class="mb-qp-body mb-qp-day">
      <div class="mb-qp-type">${escapeHtml(fmtBucketDate(item.date))} · matching groups</div>
      <ul>
        <li>${s.emailThreads} email threads · ${s.emailN} messages · ${s.attachN} attachments</li>
        <li>${s.textN} texts · ${s.textConvos} conversations</li>
        <li>${s.calN} calendar events</li>
      </ul>
      <div class="mb-qp-line">Open day →</div>
    </div>`;
    }
    const t = String(item.type || "memory");
    const media = item.thumb_url || item.media_url || "";
    const peeps = peopleList(item).slice(0, 4).join(", ");
    const place = item.place || item.location || item.city || "";
    const isText = t === "email" || isSmsTextItem(item);
    const body = String(item.detail || item.preview || item.title || "");
    const nAtt = Array.isArray(item.attachments) ? item.attachments.length : Number(item.attachment_count || 0);
    const dur =
      item.duration_sec != null
        ? `${Math.floor(item.duration_sec / 60)}:${String(
            Math.floor(item.duration_sec % 60)
          ).padStart(2, "0")}`
        : item.t != null
          ? `@ ${Number(item.t).toFixed(0)}s`
          : "";
    if (isText && state.preview && state.preview.attach) {
      const atts = Array.isArray(item.attachments) ? item.attachments : [];
      const idx = firstImageAttachIndex(item);
      const att = idx >= 0 ? atts[idx] : {};
      const name = escapeHtml(att.filename || att.source_ref || "attachment");
      const eid = item.evidence_id || "";
      const api =
        t === "email" || item.channel === "email" ? "email-attachment" : "sms-attachment";
      const isImg =
        idx >= 0 &&
        /image|jpe?g|png|gif|heic|webp|bmp|tif/i.test(
          String(att.attachment_type || att.mime_type || att.filename || "")
        );
      const img =
        isImg && eid
          ? `<div class="mb-qp-media"><img src="${escapeAttr(
              "/explore/api/" + api + "/" + eid + "?index=" + idx
            )}" alt="${name}" /></div>`
          : "";
      return `<div class="mb-qp-body mb-qp-attach">${img}
      <div class="mb-qp-type">Attachment</div>
      <div class="mb-qp-line">${name}</div>
    </div>`;
    }
    if (isText) {
      const turns = parseQuotedEmail(body);
      return `<div class="mb-qp-body mb-qp-text mb-qp-textbody">
      <div class="mb-qp-type">${escapeHtml(t)}${nAtt ? " · 📎 " + nAtt : ""}</div>
      <div class="mb-qp-title">${escapeHtml(item.from || item.title || "Message")}</div>
      <div class="mb-qp-line">${escapeHtml(fmtCardDate(item.date))}${
        item.direction ? " · " + escapeHtml(item.direction) : ""
      }</div>
      ${peeps ? `<div class="mb-qp-line">${escapeHtml(peeps)}</div>` : ""}
      ${emailTurnsHtml(turns, { compact: true })}
    </div>`;
    }
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
      bindExploreVideoPlayer(item);
      bindFaceHoldReveal();
      renderRailPanel(item);
      renderRailTools(item);
      bindPhotoPan();
    } catch (_err) {
      /* keep ask-scoped people */
    }
  }

  function centerPhotoZoom() {
    const stage = document.querySelector(".mb-ev-photo.is-zoomed");
    if (!stage) return;
    const center = () => {
      stage.scrollLeft = Math.max(0, (stage.scrollWidth - stage.clientWidth) / 2);
      stage.scrollTop = Math.max(0, (stage.scrollHeight - stage.clientHeight) / 2);
    };
    center();
    requestAnimationFrame(center);
  }

  function bindPhotoPan() {
    if (state.modal._panCleanup) {
      state.modal._panCleanup();
      state.modal._panCleanup = null;
    }
    centerPhotoZoom();
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
  const ATTACH_PREVIEW_DELAY_MS = 1000;
  const DAY_PREVIEW_DELAY_MS = 500;

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
      state.preview.attach = false;
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

  function scheduleQuickPreview(item, clientX, clientY, opts) {
    if (!state.preview) {
      state.preview = { timer: null, itemId: null, x: 0, y: 0, visible: false, attach: false };
    }
    clearPreviewTimer();
    state.preview.x = clientX;
    state.preview.y = clientY;
    state.preview.attach = !!(opts && opts.attach);
    const delay =
      String(item.type || "") === "daycard"
        ? DAY_PREVIEW_DELAY_MS
        : state.preview.attach
          ? ATTACH_PREVIEW_DELAY_MS
          : QUICK_PREVIEW_DELAY_MS;
    state.preview.timer = setTimeout(() => {
      state.preview.timer = null;
      if (state.modal.openId) return;
      renderQuickPreview(item);
    }, delay);
  }

  function bindCardPreview(card, id) {
    card.addEventListener("mouseenter", (ev) => {
      if (state.modal.openId) return;
      if (ev.target && ev.target.closest && ev.target.closest(".mb-card-attach")) return;
      const it =
        ((state.domain && state.domain.items) || []).find((x) => x.id === id) ||
        rawItems.find((x) => x.id === id);
      if (it) scheduleQuickPreview(it, ev.clientX, ev.clientY);
    });
    card.addEventListener("mousemove", (ev) => {
      if (!state.preview || state.preview.visible) return;
      state.preview.x = ev.clientX;
      state.preview.y = ev.clientY;
    });
    card.addEventListener("mouseleave", hideQuickPreview);
    const attachIcon = card.querySelector(".mb-card-attach");
    if (attachIcon) {
      attachIcon.addEventListener("mouseenter", (ev) => {
        ev.stopPropagation();
        if (state.modal.openId) return;
        const it = rawItems.find((x) => x.id === id);
        if (it) scheduleQuickPreview(it, ev.clientX, ev.clientY, { attach: true });
      });
      attachIcon.addEventListener("mouseleave", (ev) => {
        ev.stopPropagation();
        hideQuickPreview();
        if (card.matches(":hover") && !state.modal.openId) {
          const it = rawItems.find((x) => x.id === id);
          if (it) scheduleQuickPreview(it, ev.clientX, ev.clientY);
        }
      });
    }
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
    if (timelineBound) return;
    timelineBound = true;
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

  function hydrateExploreHistory() {
    if (histHydrate) return histHydrate;
    histHydrate = fetch("/ask/api/history")
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        const server = data && Array.isArray(data.asks) ? data.asks : [];
        return writeAskHistory(server.concat(readAskHistory()));
      })
      .catch(() => readAskHistory());
    return histHydrate;
  }

  function bindExploreAskHistory(input) {
    // PowerShell-style: empty Ask, Up = last command in the box, Up again = previous. No dropdown.
    if (!input || input.dataset.mbExploreHist === "1") return;
    input.dataset.mbExploreHist = "1";
    let histIndex = -1;
    let draft = "";
    let applying = false;

    const cycle = (key, recent) => {
      if (!recent.length) return;
      applying = true;
      if (histIndex < 0) draft = input.value;
      if (key === "ArrowUp") {
        if (histIndex < recent.length - 1) histIndex += 1;
      } else if (histIndex < 0) {
        applying = false;
        return;
      } else {
        histIndex -= 1;
      }
      input.value = histIndex < 0 ? draft : recent[histIndex] || "";
      markAskDirty();
      try {
        const n = input.value.length;
        input.setSelectionRange(n, n);
      } catch (_) {}
      applying = false;
    };

    input.addEventListener(
      "keydown",
      (e) => {
        if (e.isComposing) return;
        if (e.key !== "ArrowUp" && e.key !== "ArrowDown") return;
        e.preventDefault();
        e.stopPropagation();
        const local = readAskHistory();
        if (local.length) {
          cycle(e.key, local);
          return;
        }
        hydrateExploreHistory().then((recent) => cycle(e.key, recent || readAskHistory()));
      },
      true
    );
    input.addEventListener("input", () => {
      if (!applying) histIndex = -1;
      markAskDirty();
    });
    hydrateExploreHistory();
  }

  function bindChrome() {
    if (chromeBound) return;
    chromeBound = true;
    bindI8aChrome();
    document.getElementById("mb-explore-ask-go").addEventListener("click", () => {
      applyAskCommand(document.getElementById("mb-explore-ask").value);
    });
    const copyBtn = document.getElementById("mb-explore-copy");
    if (copyBtn) {
      copyBtn.addEventListener("click", async () => {
        const text = String(state.domain._askSummary || state.domain.summary || "");
        try {
          if (navigator.clipboard && navigator.clipboard.writeText) {
            await navigator.clipboard.writeText(text);
          } else {
            throw new Error("clipboard");
          }
          copyBtn.textContent = "Copied";
          setTimeout(() => {
            copyBtn.textContent = "Copy";
          }, 1600);
        } catch (err) {
          copyBtn.textContent = "Copy failed";
          setTimeout(() => {
            copyBtn.textContent = "Copy";
          }, 1600);
        }
      });
    }
    const saveStoryBtn = document.getElementById("mb-explore-save-story");
    if (saveStoryBtn) {
      saveStoryBtn.addEventListener("click", async () => {
        const body = String(state.domain._askSummary || state.domain.summary || "").trim();
        if (!body || body === "Searching…") return;
        saveStoryBtn.disabled = true;
        try {
          const plan = (state.domain.livingView && state.domain.livingView.plan) || {};
          const memories = [];
          const seen = {};
          (state.domain.citations || []).forEach((c) => {
            let source_kind = "";
            let source_id = "";
            const kind = String((c && c.kind) || "");
            if (kind === "photo") {
              source_kind = "photo";
              source_id = String(c.external_id || "");
            } else if (kind === "video") {
              source_kind = "video";
              source_id = String(c.video_external_id || c.external_id || "");
            } else if (kind === "journal") {
              source_kind = "journal";
              source_id = String(c.journal_id || "");
            } else if (kind === "artifact") {
              source_kind = "artifact";
              source_id = String(c.artifact_id || "");
            } else if (kind === "evidence") {
              const ek = String(c.evidence_kind || c.source || "").toLowerCase();
              source_id = String(c.evidence_id || "");
              if (ek.indexOf("sms") >= 0 || ek === "text" || ek === "imessage") {
                source_kind = "sms_conversation";
              } else if (ek.indexOf("calendar") >= 0) {
                source_kind = "calendar_event";
              } else if (ek.indexOf("email") >= 0 || ek.indexOf("mail") >= 0) {
                source_kind = "email_thread";
              } else {
                source_kind = "evidence";
              }
            }
            if (!source_kind || !source_id) return;
            const key = source_kind + ":" + source_id;
            if (seen[key]) return;
            seen[key] = true;
            memories.push({
              source_kind,
              source_id,
              label_snapshot: String(c.label || c.title || c.summary || "") || null,
            });
          });
          const title =
            String(state.domain.title || "").trim() ||
            String(state.domain.askText || "From Ask").trim().slice(0, 80);
          const resp = await fetch("/story/drafts", {
            method: "POST",
            headers: { "Content-Type": "application/json", Accept: "application/json" },
            body: JSON.stringify({
              title,
              body_text: body,
              person_ids: plan.person_ids || [],
              place_label: (plan.place_names || [])[0] || null,
              described_start_date: plan.time_start || null,
              described_end_date: plan.time_end || null,
              memories,
              composed_by_model: true,
            }),
          });
          const data = await resp.json().catch(() => ({}));
          if (!resp.ok || !data.ok || !data.story || !data.story.id) {
            throw new Error((data && data.detail) || "draft failed");
          }
          window.location.href = "/story/ui?id=" + encodeURIComponent(data.story.id) + "&edit=1";
        } catch (err) {
          saveStoryBtn.disabled = false;
          saveStoryBtn.textContent = "Save failed";
          setTimeout(() => {
            saveStoryBtn.textContent = "Save as Story";
          }, 1800);
        }
      });
    }
    const home = document.getElementById("mb-home");
    if (home) {
      home.addEventListener("click", (e) => {
        e.preventDefault();
        if (window.mbShell && typeof window.mbShell.clearExploration === "function") {
          window.mbShell.clearExploration();
        }
        window.location.href = "/explore/ui";
      });
    }
    const askInput = document.getElementById("mb-explore-ask");
    askInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        applyAskCommand(e.target.value);
      }
    });
    bindExploreAskHistory(askInput);
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
    applyPayloadToState(payload, { keepPresentation: Boolean(state) });
    ensureLockedPersonChip();
    syncActivePersonContext();
    renderNav();
    bindChrome();
    bindTimeline();
    render();
    loadPeopleOptions().then(() => {
      syncActivePersonContext();
      renderNav();
      applyCuratorPortrait();
      if (state && state.modal && state.modal.openId && state.modal.railTab === "learn") {
        fillLearnPersonSelect();
      }
    });
  }

  async function fetchJsonTimeout(url, ms) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), ms);
    try {
      const res = await fetch(url, { signal: ctrl.signal });
      if (!res.ok) throw new Error(String(res.status));
      return await res.json();
    } finally {
      clearTimeout(timer);
    }
  }

  function mapPickerOption(p) {
    const personId = String((p && (p.person_id || p.id)) || "").trim();
    const key = String(
      (p && p.key) ||
        (personId ? "mb:" + personId : "") ||
        (p && p.external_id
          ? "immich:" + encodeURIComponent(p.external_id) + ":" + encodeURIComponent(p.display_name || p.name || "")
          : "")
    );
    return {
      key,
      id: personId || key,
      label: String((p && (p.label || p.display_name || p.name)) || "Person"),
      immichId: String(
        (p &&
          ((Array.isArray(p.immich_external_ids) && p.immich_external_ids[0]) ||
            p.external_id)) ||
          ""
      ),
    };
  }

  async function loadPeopleOptions() {
    const fallback = [
      { key: "demo:peggy", id: "demo:peggy", label: "Peggy" },
      { key: "demo:rick", id: "demo:rick", label: "Rick" },
      { key: "demo:tom", id: "demo:tom", label: "Tom Will" },
    ];
    const seen = {};
    const uniq = [];
    const add = (p) => {
      const mapped = mapPickerOption(p);
      if (!mapped.key || mapped.key.startsWith("demo:") || seen[mapped.key]) return;
      seen[mapped.key] = 1;
      uniq.push(mapped);
    };
    const publish = () => {
      peopleOptions = uniq.length ? uniq.slice() : liveMode ? [] : fallback;
      if (state && state.modal && state.modal.openId && state.modal.railTab === "learn") {
        fillLearnPersonSelect();
      }
    };
    try {
      const list = await fetchJsonTimeout("/people?limit=300", 8000);
      (list.people || []).forEach(add);
      publish();
    } catch (_) {}
    try {
      const data = await fetchJsonTimeout("/people/picker-options", 12000);
      (data.options || data.people || []).forEach(add);
      publish();
    } catch (_) {}
    if (!peopleOptions.length) publish();
    return peopleOptions;
  }

  async function main() {
    const params = new URLSearchParams(location.search);
    const demo = params.get("demo");
    const q = params.get("q") || "";
    const videoId = (params.get("video") || "").trim();
    const photoId = (params.get("photo") || "").trim();
    sessionId =
      params.get("session_id") ||
      localStorage.getItem("mb_ask_session") ||
      null;
    // Bind Ask chrome before any find so Enter / Up / Down work on first paint.
    bindChrome();
    try {
      let payload;
      if (demo) {
        // Explicit demo/prove path only — not required for real experience
        const res = await fetch(`/explore/api/demo/${encodeURIComponent(demo)}`);
        if (!res.ok) throw new Error(`demo ${res.status}`);
        payload = await res.json();
        bootFromPayload(payload);
        return;
      }
      if (videoId) {
        const t0 = Number(params.get("t") || 0) || 0;
        const item = videoDeepLinkItem(videoId, t0);
        payload = emptyExplorePayload("");
        payload.items = [item];
        payload.title = "Video";
        payload.summary = "Opened from video id. Transcript is on for voice Learn.";
        bootFromPayload(payload);
        if (state && state.domain) state.domain.galleryLocked = false;
        openModal(item.id);
        state.modal.transcriptOn = true;
        const box = document.getElementById("mb-ev-transcript");
        if (box) box.classList.add("is-on");
        const tr = document.getElementById("mb-transcript-toggle");
        if (tr) {
          tr.setAttribute("aria-pressed", "true");
          tr.textContent = "Transcript on";
        }
        return;
      }
      if (photoId) {
        const item = photoDeepLinkItem(photoId);
        payload = emptyExplorePayload("");
        payload.items = [item];
        payload.title = "Photo";
        payload.summary = "Opened from Stories.";
        bootFromPayload(payload);
        if (state && state.domain) state.domain.galleryLocked = false;
        openModal(item.id);
        return;
      }
      let bootQ = String(q).trim();
      if (!PERSON_MODE && !bootQ && window.mbShell && typeof window.mbShell.getActivePerson === "function") {
        const locked = window.mbShell.getActivePerson();
        if (locked && locked.name) bootQ = "Show " + locked.name;
      }
      if (!PERSON_MODE && !bootQ) {
        bootFromPayload(emptyExplorePayload(""));
        return;
      }
      const bootGen = bumpFindGen();
      bootFromPayload(emptyExplorePayload(bootQ));
      const seed = PERSON_MODE
        ? bootQ || ("Show " + (PERSON.displayName || "person"))
        : bootQ;
      if (PERSON_MODE && bootQ.trim() && PERSON) {
        PERSON.memoryMode = "all";
        if (window.MB_PERSON_SURFACE) window.MB_PERSON_SURFACE.memoryMode = "all";
      }
      showSearching(seed);
      payload = await liveFind(seed);
      if (bootGen !== findGen) return;
      if (payload.session_id) {
        localStorage.setItem("mb_ask_session", payload.session_id);
      }
      bootFromPayload(payload);
    } catch (err) {
      document.getElementById("mb-explore-curator-body").textContent =
        "Could not load exploration: " + err;
    }
  }

  main();
})();
