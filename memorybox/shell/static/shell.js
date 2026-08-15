/**
 * MemoryBox P2-I2 shell — light chrome, Global Ask, context stack.
 * Surfaces set data-mb-surface on <html> or body via inject.
 */
(function () {
  // MBUX-001 v0.4 family primary destinations (I4). Review & Learn label locked.
  const FAMILY = [
    { id: "ask", href: "/ask/ui", label: "Ask" },
    { id: "people", href: "/people/ui", label: "People" },
    { id: "story", href: "/story/ui", label: "Stories" },
    { id: "journal", href: "/journal/ui", label: "Journal" },
    { id: "artifact", href: "/artifact/ui", label: "Artifacts" },
    { id: "family-night", href: "/family-night/ui", label: "Family Night" },
    { id: "teach", href: "/review/ui", label: "Review & Learn" },
  ];
  // System / internals — not family primary (Archive Health contextual / settings).
  const SYSTEM = [
    { id: "explore", href: "/explore/ui", label: "Explore" },
    { id: "library", href: "/library/ui", label: "Library" },
    { id: "status", href: "/status/ui", label: "Archive Health" },
    { id: "settings", href: "/settings/ui", label: "Settings" },
    { id: "export", href: "/export/ui", label: "Export" },
  ];

  const STACK_KEY = "mb_shell_context_stack";
  const RECENT_KEY = "mb_shell_recent_asks";
  const ACTIVE_PERSON_KEY = "mb_active_person";
  const ACTIVE_ASK_KEY = "mb_active_ask";

  function readRecent() {
    try {
      const list = JSON.parse(localStorage.getItem(RECENT_KEY) || "[]");
      return Array.isArray(list)
        ? list.map((x) => String(x || "").trim()).filter(Boolean).slice(0, 100)
        : [];
    } catch (_) {
      return [];
    }
  }

  function writeRecent(list) {
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
      localStorage.setItem(RECENT_KEY, JSON.stringify(out));
    } catch (_) {}
    return out;
  }

  function hydrateAskHistory() {
    return fetch("/ask/api/history")
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data && Array.isArray(data.asks)) writeRecent(data.asks.concat(readRecent()));
        return readRecent();
      })
      .catch(() => readRecent());
  }

  function bindAllAskInputs() {
    document
      .querySelectorAll("#mb-explore-ask, #askInput, #mb-global-ask-input")
      .forEach((el) => window.mbShell.bindAskHistory(el));
  }

  function surface() {
    return (
      document.documentElement.getAttribute("data-mb-surface") ||
      document.body.getAttribute("data-mb-surface") ||
      "unknown"
    );
  }

  function readStack() {
    try {
      return JSON.parse(sessionStorage.getItem(STACK_KEY) || "[]");
    } catch (_) {
      return [];
    }
  }

  function writeStack(stack) {
    sessionStorage.setItem(STACK_KEY, JSON.stringify(stack.slice(-12)));
  }

  function getActivePerson() {
    try {
      const raw = sessionStorage.getItem(ACTIVE_PERSON_KEY);
      if (!raw) return null;
      const p = JSON.parse(raw);
      if (!p || (!p.id && !p.name)) return null;
      return p;
    } catch (_) {
      return null;
    }
  }

  function setActivePerson(person) {
    if (!person || (!person.id && !person.name)) {
      sessionStorage.removeItem(ACTIVE_PERSON_KEY);
      return;
    }
    sessionStorage.setItem(
      ACTIVE_PERSON_KEY,
      JSON.stringify({
        id: String(person.id || ""),
        name: String(person.name || ""),
        at: Date.now(),
      })
    );
  }

  function getActiveAsk() {
    try {
      return (sessionStorage.getItem(ACTIVE_ASK_KEY) || "").trim();
    } catch (_) {
      return "";
    }
  }

  function setActiveAsk(text) {
    const t = String(text || "").trim();
    try {
      if (!t) sessionStorage.removeItem(ACTIVE_ASK_KEY);
      else sessionStorage.setItem(ACTIVE_ASK_KEY, t);
    } catch (_) {}
  }

  function withAsk(href) {
    const ask = getActiveAsk();
    if (!ask || !href || href === "/people/ui") return href;
    if (/[?&]q=/.test(href)) return href;
    return href + (href.includes("?") ? "&" : "?") + "q=" + encodeURIComponent(ask);
  }

  /** People destination: continue active person into Person Explorer when present. */
  function peopleHref() {
    const p = getActivePerson();
    if (p && p.id) {
      return withAsk(
        "/people/ui?person=" +
          encodeURIComponent(p.id) +
          (p.name ? "&person_name=" + encodeURIComponent(p.name) : "")
      );
    }
    if (p && p.name) {
      return withAsk("/people/ui?person_name=" + encodeURIComponent(p.name));
    }
    return "/people/ui";
  }

  function refreshPeopleNavLinks() {
    const href = peopleHref();
    document.querySelectorAll('a[href^="/people/ui"]').forEach((a) => {
      const cur = a.getAttribute("href") || "";
      if (cur.includes("admin=")) return;
      a.setAttribute("href", href);
    });
  }

  window.mbShell = {
    pushContext(entry) {
      const stack = readStack();
      stack.push(
        Object.assign(
          {
            at: Date.now(),
            from: surface(),
            href: location.pathname + location.search,
            scrollY: window.scrollY || 0,
          },
          entry || {}
        )
      );
      writeStack(stack);
    },
    peekContext() {
      const stack = readStack();
      return stack.length ? stack[stack.length - 1] : null;
    },
    popContext() {
      const stack = readStack();
      const top = stack.pop();
      writeStack(stack);
      return top || null;
    },
    rememberAsk(text) {
      const t = (text || "").trim();
      if (!t) return;
      writeRecent([t].concat(readRecent().filter((x) => x !== t)));
      fetch("/ask/api/history", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: t }),
      })
        .then((r) => (r.ok ? r.json() : null))
        .then((data) => {
          if (data && Array.isArray(data.asks)) writeRecent(data.asks.concat(readRecent()));
        })
        .catch(() => {});
    },
    recentAsks() {
      return readRecent();
    },
    bindAskHistory(input) {
      if (!input || input.dataset.mbAskHistory === "1") return;
      input.dataset.mbAskHistory = "1";
      let histIndex = -1;
      let draft = "";
      let applying = false;
      const applyHistory = (recent, key) => {
        if (!recent.length) return;
        applying = true;
        if (histIndex < 0) draft = input.value;
        if (key === "ArrowUp") {
          if (histIndex < recent.length - 1) histIndex += 1;
        } else if (histIndex < 0) {
          histIndex = 0;
        } else {
          histIndex -= 1;
        }
        input.value = histIndex < 0 ? draft : recent[histIndex] || "";
        try {
          const n = input.value.length;
          input.setSelectionRange(n, n);
        } catch (_) {}
        applying = false;
      };
      input.addEventListener("focus", () => {
        hydrateAskHistory();
      });
      input.addEventListener("keydown", (e) => {
        if (e.isComposing) return;
        if (e.key !== "ArrowUp" && e.key !== "ArrowDown") return;
        let recent = window.mbShell.recentAsks();
        if (!recent.length) {
          e.preventDefault();
          hydrateAskHistory().then((list) => {
            recent = list || window.mbShell.recentAsks();
            if (!recent.length) return;
            applyHistory(recent, e.key);
          });
          return;
        }
        e.preventDefault();
        applyHistory(recent, e.key);
      });
      input.addEventListener("input", () => {
        if (applying) return;
        histIndex = -1;
      });
    },
    getActivePerson,
    setActivePerson,
    getActiveAsk,
    setActiveAsk,
    bindAskHistory,
    peopleHref,
    refreshPeopleNavLinks,
  };

  function inheritHint() {
    const params = new URLSearchParams(location.search);
    const bits = [];
    ["person", "person_id", "person_name", "place", "q", "video"].forEach((k) => {
      const v = params.get(k);
      if (v) bits.push(k + "=" + v);
    });
    const peek = window.mbShell.peekContext();
    if (peek && peek.label) bits.push("from: " + peek.label);
    return bits.join(" · ");
  }

  function openGlobalAsk() {
    const overlay = document.getElementById("mb-global-ask-overlay");
    if (!overlay) return;
    const chip = document.getElementById("mb-global-ask-context");
    if (chip) chip.textContent = inheritHint() || "No inherited context yet.";
    overlay.classList.add("is-open");
    const input = document.getElementById("mb-global-ask-input");
    if (input) {
      input.focus();
      const person = new URLSearchParams(location.search).get("person_name") ||
        new URLSearchParams(location.search).get("person");
      if (person && !input.value) input.value = "Show me " + person;
    }
  }

  function closeGlobalAsk() {
    const overlay = document.getElementById("mb-global-ask-overlay");
    if (overlay) overlay.classList.remove("is-open");
  }

  function submitGlobalAsk() {
    const input = document.getElementById("mb-global-ask-input");
    const text = (input && input.value || "").trim();
    if (!text) return;
    window.mbShell.rememberAsk(text);
    // On Explore / Person Explorer, typed/STT commands share filter/timeline state.
    if (
      (surface() === "explore" || surface() === "people") &&
      typeof window.mbExploreApplyAsk === "function"
    ) {
      closeGlobalAsk();
      window.mbExploreApplyAsk(text);
      return;
    }
    window.mbShell.pushContext({ label: "before Global Ask", surface: surface() });
    const url = "/ask/ui?q=" + encodeURIComponent(text);
    location.href = url;
  }

  function renderReturnBar() {
    const params = new URLSearchParams(location.search);
    if (params.get("mb_return") !== "1") return;
    const peek = window.mbShell.peekContext();
    if (!peek || !peek.href) return;
    let bar = document.getElementById("mb-return-bar");
    if (!bar) {
      bar = document.createElement("div");
      bar.id = "mb-return-bar";
      bar.className = "mb-return-bar";
      const host = document.querySelector("main") || document.body;
      host.insertBefore(bar, host.firstChild);
    }
    bar.classList.add("is-visible");
    bar.innerHTML =
      '<span>Return to prior exploration</span>' +
      '<button type="button" class="mb-btn-secondary" id="mb-return-btn">Return</button>';
    document.getElementById("mb-return-btn").addEventListener("click", () => {
      const top = window.mbShell.popContext();
      if (top && top.href) location.href = top.href;
    });
  }

  function wireOutboundContext() {
    document.addEventListener("click", (e) => {
      const a = e.target.closest("a[href]");
      if (!a) return;
      let href = a.getAttribute("href") || "";
      if (!href.startsWith("/")) return;
      if (href.startsWith("/ask/ui") && surface() === "ask") return;

      // Explore → People: continue active person into Person Explorer
      try {
        const uPeople = new URL(href, location.origin);
        if (
          uPeople.pathname === "/people/ui" &&
          !uPeople.searchParams.get("person") &&
          !uPeople.searchParams.get("person_id") &&
          !uPeople.searchParams.get("person_name") &&
          uPeople.searchParams.get("admin") !== "1"
        ) {
          const next = peopleHref();
          if (next !== "/people/ui") {
            const uNext = new URL(next, location.origin);
            a.setAttribute("href", uNext.pathname + uNext.search + uNext.hash);
            href = a.getAttribute("href") || next;
          }
        }
      } catch (_) {}

      // Leaving exploration with a drill-down
      if (
        href.includes("/review/ui") ||
        href.includes("/library/ui") ||
        href.includes("/people/ui") ||
        href.includes("/ask/ui")
      ) {
        window.mbShell.pushContext({
          label: a.textContent.trim().slice(0, 80) || href,
          to: href,
        });
        try {
          const u = new URL(href, location.origin);
          if (!u.searchParams.has("mb_return")) {
            u.searchParams.set("mb_return", "1");
            a.setAttribute("href", u.pathname + u.search + u.hash);
          }
        } catch (_) {}
      }
    });
  }

  function injectChrome() {
    if (document.getElementById("mb-site-bar")) return;
    document.body.classList.add("mb-shell");
    const cur = surface();
    const bar = document.createElement("header");
    bar.id = "mb-site-bar";
    bar.className = "mb-site-bar";
    bar.setAttribute("role", "banner");

    const family = FAMILY.map((item) => {
      const href = item.id === "people" ? peopleHref() : item.href;
      const curAttr = item.id === cur ? ' aria-current="page"' : "";
      return `<a href="${href}"${curAttr}>${item.label}</a>`;
    }).join("");

    const system = SYSTEM.map((item) => {
      const curAttr = item.id === cur ? ' aria-current="page"' : "";
      return `<a href="${item.href}"${curAttr}>${item.label}</a>`;
    }).join("");

    bar.innerHTML =
      `<a class="mb-brand" href="/ask/ui">MemoryBox</a>` +
      `<nav class="mb-nav-family" aria-label="Family exploration">${family}` +
      `<button type="button" class="mb-global-ask-btn" id="mb-open-global-ask">Ask</button>` +
      `</nav>` +
      `<nav class="mb-nav-system" aria-label="Owner and system">${system}</nav>`;

    document.body.insertBefore(bar, document.body.firstChild);

    const overlay = document.createElement("div");
    overlay.id = "mb-global-ask-overlay";
    overlay.className = "mb-global-ask-overlay";
    overlay.innerHTML =
      `<div class="mb-global-ask-card" role="dialog" aria-label="Global Ask">` +
      `<h2>Ask MemoryBox</h2>` +
      `<p class="mb-context-chip" id="mb-global-ask-context"></p>` +
      `<div class="mb-ask-bar">` +
      `<input id="mb-global-ask-input" type="text" placeholder="Ask about a person, place, or time…" />` +
      `<button type="button" class="mb-btn-primary" id="mb-global-ask-go">Ask</button>` +
      `</div>` +
      `<button type="button" class="mb-btn-secondary" id="mb-global-ask-close">Close</button>` +
      `</div>`;
    document.body.appendChild(overlay);

    document.getElementById("mb-open-global-ask").addEventListener("click", openGlobalAsk);
    document.getElementById("mb-global-ask-close").addEventListener("click", closeGlobalAsk);
    document.getElementById("mb-global-ask-go").addEventListener("click", submitGlobalAsk);
    const globalInput = document.getElementById("mb-global-ask-input");
    globalInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") submitGlobalAsk();
    });
    window.mbShell.bindAskHistory(globalInput);
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) closeGlobalAsk();
    });
  }

  function boot() {
    injectChrome();
    renderReturnBar();
    wireOutboundContext();
    hydrateAskHistory();
    bindAllAskInputs();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
