/**
 * MemoryBox P2-I4 — Mixed-Media Exploration
 *
 * Separated state layers (MBUX-001 / I4 directive):
 *   domain  — query, chips, type filter, result membership
 *   timeline — result extent, active range, playhead, precision
 *   gallery  — density (presentation only), scroll position
 *   modal    — open item; close restores explore snapshot
 *
 * Typed Ask commands and future STT must manipulate the same domain/timeline state.
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

  const TYPE_ICON = {
    photo: "📷",
    video: "🎬",
    email: "✉️",
    artifact: "📦",
    story: "📖",
    audio: "🎧",
    sms: "💬",
    calendar: "📅",
    recipe: "🍲",
    document: "📄",
  };

  const NAV = [
    { id: "ask", label: "Ask", href: "/ask/ui" },
    { id: "people", label: "People", href: "/people/ui" },
    { id: "stories", label: "Stories", href: "/story/ui" },
    { id: "journal", label: "Journal", href: "/journal/ui" },
    { id: "artifacts", label: "Artifacts", href: "/artifact/ui" },
    { id: "family-night", label: "Family Night", href: "/family-night/ui" },
    { id: "teach", label: "Teach", href: "/review/ui" },
  ];

  // Ask command examples (typed today; STT later shares applyAskCommand):
  // "Only photos." "Add video." "Clear filters." "Show everything."
  // "Show 2005 through 2011." "Clear context and go to People."

  /** @type {{
   *   domain: {
   *     askText: string,
   *     title: string,
   *     summary: string,
   *     chips: Array<{label:string,kind?:string}>,
   *     typeFilter: string,
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
   *   gallery: { density: number, scrollTop: number },
   *   modal: { openId: string|null, snapshot: object|null },
   * }} */
  let state = null;
  let rawItems = [];
  let bandDrag = null;
  let handleDrag = null;
  let scrubDrag = null;

  function dayMs(y, m, d) {
    return Date.UTC(y, m - 1, d);
  }

  function parseISO(s) {
    const p = String(s || "").slice(0, 10).split("-");
    if (p.length < 3) return NaN;
    return dayMs(+p[0], +p[1], +p[2]);
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
    if (!items.length) {
      const now = Date.now();
      return { start: now, end: now };
    }
    let lo = Infinity;
    let hi = -Infinity;
    for (const it of items) {
      const t = parseISO(it.date);
      if (!Number.isFinite(t)) continue;
      lo = Math.min(lo, t);
      hi = Math.max(hi, t);
    }
    if (!Number.isFinite(lo)) {
      const now = Date.now();
      return { start: now, end: now };
    }
    // pad slightly so edge items aren't on the rim
    const pad = Math.max((hi - lo) * 0.02, 86400000);
    return { start: lo - pad, end: hi + pad };
  }

  function matchesType(item, filter) {
    if (!filter || filter === "all") return true;
    const t = String(item.type || "").toLowerCase();
    if (filter === "email") return t === "email" || t === "sms" || t === "text";
    return t === filter;
  }

  function visibleItems() {
    const { typeFilter } = state.domain;
    const { rangeStart, rangeEnd } = state.timeline;
    return rawItems
      .filter((it) => matchesType(it, typeFilter))
      .filter((it) => {
        const t = parseISO(it.date);
        return Number.isFinite(t) && t >= rangeStart && t <= rangeEnd;
      })
      .sort((a, b) => parseISO(a.date) - parseISO(b.date));
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
      state.timeline.rangeStart <= state.timeline.extentStart + 1 &&
      state.timeline.rangeEnd >= state.timeline.extentEnd - 1;
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
    const range = fmtRangeLabel(
      state.timeline.rangeStart,
      state.timeline.rangeEnd,
      state.timeline.precision
    );
    const filterLabel =
      FILTERS.find((f) => f.id === state.domain.typeFilter)?.label || "All";
    state.domain.summary = `Showing ${vis.length} memories (${filterLabel}) for ${range}${
      parts.length ? ": " + parts.join(", ") + "." : "."
    }`;
  }

  // ——— Ask command architecture (typed today; STT later shares this) ———

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
      state.domain.typeFilter = "all";
      resetTimelineExtent(false);
      render();
      return;
    }

    if (/only photos?\.?/.test(lower) || /^photos?\.?$/.test(lower)) {
      state.domain.typeFilter = "photo";
      render();
      return;
    }
    if (/only videos?\.?/.test(lower) || /add video/.test(lower)) {
      if (/add video/.test(lower) && state.domain.typeFilter === "photo") {
        state.domain.typeFilter = "all"; // expand to include video among mixed
      } else if (/only videos?/.test(lower)) {
        state.domain.typeFilter = "video";
      } else {
        // "Add video" while filtered: clear to all so video appears with others
        state.domain.typeFilter = "all";
      }
      render();
      return;
    }
    if (/only (email|emails|text)/.test(lower)) {
      state.domain.typeFilter = "email";
      render();
      return;
    }
    if (/only artifacts?/.test(lower)) {
      state.domain.typeFilter = "artifact";
      render();
      return;
    }
    if (/only stories?/.test(lower)) {
      state.domain.typeFilter = "story";
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

    // Soft query update — keep exploring current fixture set with note
    state.domain.title = text.length > 48 ? text.slice(0, 45) + "…" : text;
    refreshCuratorFromVisible();
    render();
  }

  function setActiveRange(start, end) {
    let a = Math.min(start, end);
    let b = Math.max(start, end);
    a = Math.max(a, state.timeline.extentStart);
    b = Math.min(b, state.timeline.extentEnd);
    if (b - a < 86400000) b = a + 86400000;
    state.timeline.rangeStart = a;
    state.timeline.rangeEnd = b;
    state.timeline.precision = computePrecision(a, b);
    state.timeline.playhead = a;
  }

  function resetTimelineExtent(andRender) {
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
    // Family destinations come from the injected Product Shell (MBUX FAMILY).
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
    chips.innerHTML = (state.domain.chips || [])
      .map((c) => `<span class="mb-chip">${escapeHtml(c.label)}</span>`)
      .join("");
  }

  function renderFilters() {
    const el = document.getElementById("mb-explore-filters");
    el.innerHTML = FILTERS.map((f) => {
      const on = state.domain.typeFilter === f.id;
      return `<button type="button" data-filter="${f.id}" aria-pressed="${on}">${f.label}</button>`;
    }).join("");
    el.querySelectorAll("button").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.domain.typeFilter = btn.getAttribute("data-filter");
        render();
      });
    });
  }

  function renderGallery() {
    const gallery = document.getElementById("mb-explore-gallery");
    const items = visibleItems();
    state.domain.items = items;
    gallery.dataset.density = String(state.gallery.density);
    gallery.innerHTML = items
      .map((it) => {
        const icon = TYPE_ICON[it.type] || "•";
        const title = escapeHtml(it.title || it.type);
        const date = escapeHtml(it.date || "");
        const prev = escapeHtml(it.preview || "");
        return `<button type="button" class="mb-card" data-id="${escapeAttr(it.id)}" data-type="${escapeAttr(it.type)}">
          <div class="mb-card-media" data-type="${escapeAttr(it.type)}">${icon}<span class="mb-card-preview">${prev}</span></div>
          <div class="mb-card-meta">
            <div class="mb-card-title">${title}</div>
            <div class="mb-card-sub">${date} · ${escapeHtml(it.type)}</div>
          </div>
        </button>`;
      })
      .join("");

    gallery.querySelectorAll(".mb-card").forEach((card) => {
      card.addEventListener("click", () => openModal(card.getAttribute("data-id")));
    });

    // restore scroll after re-render
    requestAnimationFrame(() => {
      gallery.scrollTop = state.gallery.scrollTop || 0;
    });

    const meta = document.getElementById("mb-explore-meta");
    meta.textContent = `${items.length} visible · density ${state.gallery.density} · filter ${state.domain.typeFilter}`;
  }

  function renderTimeline() {
    const { extentStart, extentEnd, rangeStart, rangeEnd, playhead, precision } =
      state.timeline;
    const span = Math.max(extentEnd - extentStart, 1);
    const band = document.getElementById("mb-tl-band");
    const ph = document.getElementById("mb-tl-playhead");
    const hl = document.getElementById("mb-tl-handle-l");
    const hr = document.getElementById("mb-tl-handle-r");
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

    // density dots from raw items (type-filtered but full extent for context)
    const dotsEl = document.getElementById("mb-tl-dots");
    const typed = rawItems.filter((it) => matchesType(it, state.domain.typeFilter));
    dotsEl.innerHTML = typed
      .map((it) => {
        const t = parseISO(it.date);
        if (!Number.isFinite(t)) return "";
        const x = ((t - extentStart) / span) * 100;
        return `<span class="mb-tl-dot" style="left:${x}%" title="${escapeAttr(it.date)}"></span>`;
      })
      .join("");

    // ticks
    const ticks = document.getElementById("mb-tl-ticks");
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

  function render() {
    document.getElementById("mb-explore-ask").value = state.domain.askText || "";
    renderCurator();
    renderFilters();
    renderGallery();
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

    const modal = document.getElementById("mb-modal");
    document.getElementById("mb-modal-kicker").textContent = String(
      item.type || "Evidence"
    ).toUpperCase();
    document.getElementById("mb-modal-title").textContent = item.title || item.id;
    const body = document.getElementById("mb-modal-body");
    body.innerHTML = renderEvidenceBody(item);
    modal.hidden = false;
    document.getElementById("mb-modal-close").focus();
  }

  function closeModal() {
    const snap = state.modal.snapshot;
    state.modal.openId = null;
    state.modal.snapshot = null;
    document.getElementById("mb-modal-body").innerHTML = "";
    document.getElementById("mb-modal").hidden = true;
    if (snap) restoreExplore(snap);
    render();
    requestAnimationFrame(() => {
      const g = document.getElementById("mb-explore-gallery");
      g.scrollTop = state.gallery.scrollTop || 0;
    });
  }

  function renderEvidenceBody(item) {
    const t = String(item.type || "").toLowerCase();
    if (t === "photo") {
      return `<div class="mb-ev-photo" aria-label="Photo workspace">${escapeHtml(
        item.preview || "Photo"
      )}
        <div style="position:absolute;inset:12% 18%;border:2px dashed rgba(255,255,255,.45);border-radius:8px;display:flex;align-items:flex-end;justify-content:center;padding:8px;font-size:12px;color:#fff;background:rgba(0,0,0,.15)">
          Face teach region (assign / reassign / Learn) — prepared, not full Teach product
        </div>
      </div>
      <p class="mb-ev-meta">${escapeHtml(item.date || "")} · Photo evidence</p>
      <p>${escapeHtml(item.detail || "")}</p>`;
    }
    if (t === "video") {
      return `<div class="mb-ev-video">
        <div class="mb-ev-video-frame" id="mb-ev-video-frame">Paused frame · face teach applies here only (not during playback)</div>
        <div class="mb-ev-transcript" aria-label="Time-aligned transcript (prepared)">
          <strong>Transcript (architecture)</strong><br/>
          [00:12] …speech span selectable for speaker ID / Learn from voice…<br/>
          ${escapeHtml(item.detail || "Video moment ready for time-aligned teaching.")}
        </div>
      </div>
      <p class="mb-ev-meta">${escapeHtml(item.date || "")} · Video moment</p>`;
    }
    if (t === "email" || t === "sms" || t === "text") {
      return `<div class="mb-ev-email">${escapeHtml(item.detail || item.preview || "")}</div>
        <p class="mb-ev-meta">${escapeHtml(item.date || "")} · Email / text</p>`;
    }
    if (t === "story") {
      return `<p class="mb-ev-meta">${escapeHtml(item.date || "")} · Story (contextual meaning)</p>
        <p>${escapeHtml(item.detail || "")}</p>
        <p style="color:var(--mb-muted);font-size:13px">Stories stay tied to people / evidence / events — not a disconnected writing surface in I4.</p>`;
    }
    // artifact / audio / calendar / recipe / document / default
    return `<div class="mb-ev-photo" data-type="${escapeAttr(t)}" style="min-height:160px">${escapeHtml(
      TYPE_ICON[t] || "•"
    )} ${escapeHtml(item.preview || t)}</div>
      <p class="mb-ev-meta">${escapeHtml(item.date || "")} · ${escapeHtml(t)}</p>
      <p>${escapeHtml(item.detail || "")}</p>`;
  }

  // ——— Timeline interaction ———

  function trackFrac(clientX) {
    const track = document.getElementById("mb-tl-track");
    const r = track.getBoundingClientRect();
    const x = Math.min(1, Math.max(0, (clientX - r.left) / r.width));
    return state.timeline.extentStart + x * (state.timeline.extentEnd - state.timeline.extentStart);
  }

  function scrollGalleryToward(ms) {
    const items = visibleItems();
    if (!items.length) return;
    const gallery = document.getElementById("mb-explore-gallery");
    // find nearest item at/after playhead
    let idx = 0;
    for (let i = 0; i < items.length; i++) {
      if (parseISO(items[i].date) >= ms) {
        idx = i;
        break;
      }
      idx = i;
    }
    const card = gallery.querySelectorAll(".mb-card")[idx];
    if (card) {
      card.scrollIntoView({ inline: "nearest", block: "nearest", behavior: "smooth" });
      state.gallery.scrollTop = gallery.scrollTop;
    }
  }

  function bindTimeline() {
    const track = document.getElementById("mb-tl-track");
    const hl = document.getElementById("mb-tl-handle-l");
    const hr = document.getElementById("mb-tl-handle-r");

    document.getElementById("mb-tl-reset").addEventListener("click", () => {
      resetTimelineExtent(true);
    });

    // Band drag = redefine active range (explore period)
    track.addEventListener("pointerdown", (e) => {
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
        const delta = t - scrubDrag.last;
        scrubDrag.last = t;
        state.timeline.playhead = t;
        // Scrub mental model: small move = slow scroll, large = fast
        const gallery = document.getElementById("mb-explore-gallery");
        const span = state.timeline.extentEnd - state.timeline.extentStart;
        const speed = Math.min(80, Math.abs(delta) / span * 4000);
        gallery.scrollTop += (delta >= 0 ? 1 : -1) * Math.max(8, speed);
        state.gallery.scrollTop = gallery.scrollTop;
        scrollGalleryToward(t);
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
      e.stopPropagation();
      handleDrag = "l";
      hl.setPointerCapture(e.pointerId);
    });
    hr.addEventListener("pointerdown", (e) => {
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
    rawItems = Array.isArray(payload.items) ? payload.items.slice() : [];
    const ext = extentOf(rawItems);
    state = {
      domain: {
        askText: payload.ask_text || "",
        title: payload.title || "Memories",
        summary: payload.summary || "",
        _fixtureSummary: payload.summary || "",
        chips: payload.chips || [],
        typeFilter: "all",
        items: [],
      },
      timeline: {
        extentStart: ext.start,
        extentEnd: ext.end,
        rangeStart: ext.start,
        rangeEnd: ext.end,
        playhead: ext.start,
        precision: computePrecision(ext.start, ext.end),
      },
      gallery: { density: 2, scrollTop: 0 },
      modal: { openId: null, snapshot: null },
    };
    renderNav();
    bindChrome();
    bindTimeline();
    render();
  }

  async function main() {
    const params = new URLSearchParams(location.search);
    const demo = params.get("demo") || "peggy-christmas";
    try {
      const res = await fetch(`/explore/api/demo/${encodeURIComponent(demo)}`);
      if (!res.ok) throw new Error(`demo ${res.status}`);
      const payload = await res.json();
      bootFromPayload(payload);
    } catch (err) {
      document.getElementById("mb-explore-curator-body").textContent =
        "Could not load exploration demo: " + err;
    }
  }

  main();
})();
