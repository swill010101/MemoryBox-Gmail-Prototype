(function () {
  const rowsEl = document.getElementById("traceRows");
  const detailEl = document.getElementById("detail");
  const liveEl = document.getElementById("liveFollow");
  const pollEl = document.getElementById("pollMs");
  const qEl = document.getElementById("filterQ");
  const classEl = document.getElementById("filterClass");
  const maxEl = document.getElementById("maxTraces");
  const daysEl = document.getElementById("retDays");
  const hintEl = document.getElementById("settingsHint");
  const scenarioBox = document.getElementById("scenarioBtns");

  let selectedId = null;
  let traces = [];
  let timer = null;

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function pretty(v) {
    if (v == null) return "—";
    try {
      return JSON.stringify(v, null, 2);
    } catch (_) {
      return String(v);
    }
  }

  function when(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleTimeString();
  }

  async function jget(url) {
    const r = await fetch(url, { cache: "no-store" });
    if (!r.ok) throw new Error(url + " " + r.status);
    return r.json();
  }

  async function jsend(url, method, body) {
    const r = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    });
    return r.json();
  }

  function renderList() {
    rowsEl.innerHTML = traces
      .map((t) => {
        const active = t.trace_id === selectedId ? "active" : "";
        return (
          "<tr class=\"" +
          active +
          "\" data-id=\"" +
          esc(t.trace_id) +
          "\">" +
          "<td>" +
          esc(when(t.updated_at || t.created_at)) +
          "</td>" +
          "<td>" +
          esc((t.originating_ask || "").slice(0, 80)) +
          "</td>" +
          "<td>" +
          esc(t.purpose || "") +
          "</td>" +
          "<td>" +
          esc(t.model_call_count || 0) +
          "</td>" +
          "<td>" +
          esc(t.duration_ms == null ? "" : t.duration_ms) +
          "</td>" +
          "<td class=\"status-" +
          esc(t.status || "") +
          "\">" +
          esc(t.status || "") +
          "</td>" +
          "<td>" +
          esc(t.error_class || "") +
          "</td>" +
          "</tr>"
        );
      })
      .join("");
  }

  function pane(title, klass, body) {
    return (
      "<section class=\"pane " +
      klass +
      "\"><h3>" +
      esc(title) +
      "</h3><pre>" +
      esc(pretty(body)) +
      "</pre></section>"
    );
  }

  function renderDetail(pack) {
    const t = pack.trace || pack;
    const spans = t.spans || [];
    const modelSpans = spans.filter((s) => s.operation === "chat" || s.operation === "embed");
    const firstModel = modelSpans[0] || {};
    selectedId = t.trace_id;
    const timeline = spans
      .map((s) => {
        return (
          "<li><strong>" +
          esc(s.stage) +
          "</strong> · " +
          esc(s.component) +
          " / " +
          esc(s.operation) +
          " · " +
          esc(s.status) +
          (s.error_class ? " · " + esc(s.error_class) : "") +
          " · " +
          esc(s.duration_ms == null ? "" : s.duration_ms + " ms") +
          "</li>"
        );
      })
      .join("");
    detailEl.innerHTML =
      "<h2>" +
      esc(t.originating_ask || t.trace_id) +
      "</h2>" +
      "<div class=\"meta\">" +
      "<span>id <code id=\"traceId\">" +
      esc(t.trace_id) +
      "</code></span>" +
      "<span>" +
      esc(t.request_kind) +
      "</span>" +
      "<span class=\"status-" +
      esc(t.status) +
      "\">" +
      esc(t.status) +
      (t.error_class ? " · " + esc(t.error_class) : "") +
      "</span>" +
      "<span>" +
      esc(t.model_call_count || 0) +
      " model call(s)</span>" +
      "<span>" +
      esc(t.duration_ms == null ? "" : t.duration_ms + " ms") +
      "</span>" +
      "</div>" +
      "<div class=\"actions\">" +
      "<button type=\"button\" id=\"copyId\">Copy Trace ID</button>" +
      "<button type=\"button\" id=\"copyJson\">Export JSON</button>" +
      "</div>" +
      "<p class=\"hint\">Assembled MemoryBox context is what the planner/orchestrator built. Provider payload is exactly what was sent.</p>" +
      "<div class=\"panes\">" +
      pane("Assembled MemoryBox context", "mb", t.assembled_context || firstModel.assembled_context) +
      pane("Exact provider payload sent", "prov", firstModel.provider_payload) +
      pane("Raw model / provider return", "", firstModel.raw_response) +
      pane("Parsed / validated", "", firstModel.parsed || spans.find((s) => s.stage === "parse_validate")) +
      pane("MemoryBox result", "mb", t.final_disposition) +
      pane("Error", t.error_class ? "err" : "", t.error) +
      "</div>" +
      "<h3>Stage timeline</h3><ul class=\"timeline\">" +
      timeline +
      "</ul>";
    const copyId = document.getElementById("copyId");
    const copyJson = document.getElementById("copyJson");
    if (copyId) {
      copyId.onclick = function () {
        navigator.clipboard.writeText(t.trace_id || "");
      };
    }
    if (copyJson) {
      copyJson.onclick = function () {
        navigator.clipboard.writeText(JSON.stringify(t, null, 2));
      };
    }
    renderList();
  }

  async function loadList() {
    const params = new URLSearchParams();
    if (qEl.value.trim()) params.set("q", qEl.value.trim());
    if (classEl.value) params.set("error_class", classEl.value);
    const data = await jget("/dev/api/ai-trace?" + params.toString());
    traces = data.traces || [];
    if (data.settings) {
      if (!maxEl.dataset.dirty) maxEl.value = data.settings.max_traces;
      if (!daysEl.dataset.dirty) daysEl.value = data.settings.retention_days;
    }
    if (liveEl.checked && traces.length) {
      selectedId = traces[0].trace_id;
    }
    renderList();
    if (selectedId) {
      try {
        const pack = await jget("/dev/api/ai-trace/" + selectedId);
        renderDetail(pack);
      } catch (_) {
        /* keep list */
      }
    }
  }

  function tick() {
    if (timer) clearInterval(timer);
    timer = setInterval(function () {
      loadList().catch(function () {});
    }, Number(pollEl.value || 750));
  }

  rowsEl.addEventListener("click", function (ev) {
    const tr = ev.target.closest("tr");
    if (!tr) return;
    liveEl.checked = false;
    selectedId = tr.getAttribute("data-id");
    jget("/dev/api/ai-trace/" + selectedId).then(renderDetail);
  });

  document.getElementById("btnRefresh").onclick = function () {
    loadList().catch(function (e) {
      hintEl.textContent = String(e);
    });
  };
  document.getElementById("btnClear").onclick = function () {
    if (!confirm("Clear all AI traces on this machine?")) return;
    jsend("/dev/api/ai-trace/clear", "POST").then(function () {
      selectedId = null;
      detailEl.innerHTML = "<p class=\"empty\">Cleared.</p>";
      return loadList();
    });
  };
  document.getElementById("btnSaveSettings").onclick = function () {
    jsend("/dev/api/ai-trace/settings", "PATCH", {
      max_traces: Number(maxEl.value),
      retention_days: Number(daysEl.value),
    }).then(function (s) {
      hintEl.textContent = "Saved · max " + s.max_traces + " / " + s.retention_days + " days";
      maxEl.dataset.dirty = "";
      daysEl.dataset.dirty = "";
    });
  };
  maxEl.addEventListener("input", function () {
    maxEl.dataset.dirty = "1";
  });
  daysEl.addEventListener("input", function () {
    daysEl.dataset.dirty = "1";
  });
  qEl.addEventListener("input", function () {
    loadList().catch(function () {});
  });
  classEl.addEventListener("change", function () {
    loadList().catch(function () {});
  });
  pollEl.addEventListener("change", tick);
  liveEl.addEventListener("change", function () {
    if (liveEl.checked) loadList().catch(function () {});
  });

  ["T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9", "T10"].forEach(function (name) {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = name;
    b.onclick = function () {
      jsend("/dev/api/ai-trace/scenario", "POST", { scenario: name }).then(function (res) {
        hintEl.textContent = name + (res.ok ? " ok" : " failed");
        if (res.trace_id) {
          liveEl.checked = false;
          selectedId = res.trace_id;
        }
        return loadList();
      });
    };
    scenarioBox.appendChild(b);
  });

  loadList().catch(function (e) {
    hintEl.textContent = String(e);
  });
  tick();
})();
