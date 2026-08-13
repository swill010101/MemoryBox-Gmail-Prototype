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
      let recent = [];
      try {
        recent = JSON.parse(localStorage.getItem(RECENT_KEY) || "[]");
      } catch (_) {}
      recent = [t].concat(recent.filter((x) => x !== t)).slice(0, 6);
      localStorage.setItem(RECENT_KEY, JSON.stringify(recent));
    },
    recentAsks() {
      try {
        return JSON.parse(localStorage.getItem(RECENT_KEY) || "[]");
      } catch (_) {
        return [];
      }
    },
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
    // On Explore, typed/STT commands must share the same context/filter/timeline state.
    if (surface() === "explore" && typeof window.mbExploreApplyAsk === "function") {
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
      const href = a.getAttribute("href") || "";
      if (!href.startsWith("/")) return;
      if (href.startsWith("/ask/ui") && surface() === "ask") return;
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
      const curAttr = item.id === cur ? ' aria-current="page"' : "";
      return `<a href="${item.href}"${curAttr}>${item.label}</a>`;
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
    document.getElementById("mb-global-ask-input").addEventListener("keydown", (e) => {
      if (e.key === "Enter") submitGlobalAsk();
    });
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) closeGlobalAsk();
    });
  }

  function boot() {
    injectChrome();
    renderReturnBar();
    wireOutboundContext();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
