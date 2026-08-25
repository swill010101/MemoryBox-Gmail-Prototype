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
  let lastDetailKey = "";
  let detailPinned = false;

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
    const aside = rowsEl.closest("aside");
    const keepList = aside ? aside.scrollTop : 0;
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
    if (aside) aside.scrollTop = keepList;
  }

  let copyStore = {};

  function pane(title, klass, body, copyId) {
    const id = copyId || ("pane-" + title.replace(/\s+/g, "-").toLowerCase());
    copyStore[id] = pretty(body);
    return (
      "<section class=\"pane " +
      klass +
      "\"><div class=\"pane-head\"><h3>" +
      esc(title) +
      "</h3><button type=\"button\" class=\"copy-pane\" data-copy=\"" +
      esc(id) +
      "\">Copy</button></div><pre>" +
      esc(pretty(body)) +
      "</pre></section>"
    );
  }

  function payloadBytes(obj) {
    try {
      return JSON.stringify(obj || {}).length;
    } catch (_) {
      return 0;
    }
  }

  function renderDetail(pack, opts) {
    const force = opts && opts.force;
    const t = pack.trace || pack;
    const spans = t.spans || [];
    const detailKey = [
      t.trace_id,
      t.status,
      t.model_call_count || 0,
      spans.length,
      (spans[spans.length - 1] || {}).status || "",
    ].join("|");
    if (!force && detailKey === lastDetailKey && t.trace_id === selectedId) {
      renderList();
      return;
    }
    const keepScroll = detailEl.scrollTop;
    const maxBefore = Math.max(0, detailEl.scrollHeight - detailEl.clientHeight);
    const wasAtBottom = keepScroll >= maxBefore - 8;
    lastDetailKey = detailKey;
    const modelSpans = spans.filter((s) => s.operation === "chat" || s.operation === "embed");
    const firstModel = modelSpans[0] || {};
    const resSpan = spans.find((s) => s.operation === "retrieval_resolution") || {};
    const infSpans = spans.filter((s) => s.component === "i11a");
    const infLeaf = infSpans.find((s) => s.operation === "leaf") || {};
    const infVal = infSpans.find((s) => s.operation === "validate") || {};
    const chatSpans = modelSpans.filter((s) => s.operation === "chat");
    const fattestChat = chatSpans.slice().sort(function (a, b) {
      return payloadBytes(b.provider_payload) - payloadBytes(a.provider_payload);
    })[0] || {};
    const copyPayload =
      fattestChat.provider_payload ||
      infLeaf.provider_payload ||
      firstModel.provider_payload;
    const narratorSpan =
      chatSpans.find((s) => {
        const msgs = ((s.provider_payload || {}).messages || []);
        return msgs.some((m) => String((m && m.content) || "").indexOf("NARRATIVE_SYNTHESIS") >= 0);
      }) || {};
    copyStore = {};
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
      "<button type=\"button\" id=\"copyJson\">Copy Full Trace JSON</button>" +
      "<button type=\"button\" id=\"exportJsonFile\">Export JSON</button>" +
      "</div>" +
      "<p class=\"hint\">I11A Light: copy each pane in full (not the on-screen truncation). Developer-only; not family evidence.</p>" +
      "<div class=\"panes\">" +
      pane("Assembled MemoryBox context", "mb", t.assembled_context || firstModel.assembled_context, "copy-assembled") +
      pane("Retrieval resolution", "mb", resSpan.assembled_context || resSpan.parsed, "copy-retrieval-resolution") +
      pane("PersonContext / requestor / focal", "mb", (infVal.assembled_context || {}).request_context || infVal.assembled_context, "copy-person-context") +
      pane("Copy Provider Payload", "prov", copyPayload, "copy-provider-payload") +
      pane("Copy Raw Model Response", "", infLeaf.raw_response || firstModel.raw_response, "copy-raw-response") +
      pane("Copy Parsed Inference", "", infLeaf.parsed || infVal.parsed, "copy-parsed-inference") +
      pane("Copy Validated Semantic Pack", "mb", (infVal.disposition || {}).validated_semantic_pack || infVal.parsed, "copy-validated-pack") +
      pane("Validation / rejected", "", infVal.validation, "copy-validation") +
      pane("Narrator payload / response", "", { payload: narratorSpan.provider_payload, raw: narratorSpan.raw_response }, "copy-narrator") +
      pane("MemoryBox result", "mb", t.final_disposition, "copy-result") +
      pane("Error", t.error_class ? "err" : "", t.error, "copy-error") +
      "</div>" +
      "<h3>Stage timeline</h3><ul class=\"timeline\">" +
      timeline +
      "</ul>";
    const copyId = document.getElementById("copyId");
    const copyJson = document.getElementById("copyJson");
    const exportBtn = document.getElementById("exportJsonFile");
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
    if (exportBtn) {
      exportBtn.onclick = function () {
        const blob = new Blob([JSON.stringify(t, null, 2)], { type: "application/json" });
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = "ai-trace-" + (t.trace_id || "export") + ".json";
        a.click();
        URL.revokeObjectURL(a.href);
      };
    }
    detailEl.querySelectorAll(".copy-pane").forEach(function (btn) {
      btn.onclick = function () {
        const key = btn.getAttribute("data-copy");
        navigator.clipboard.writeText(copyStore[key] || "");
      };
    });
    renderList();
    const maxAfter = Math.max(0, detailEl.scrollHeight - detailEl.clientHeight);
    if (wasAtBottom && liveEl.checked && !detailPinned) {
      detailEl.scrollTop = maxAfter;
    } else {
      detailEl.scrollTop = Math.min(keepScroll, maxAfter);
    }
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
      } catch (err) {
        const msg = String((err && err.message) || err || "");
        if (msg.indexOf(" 404") !== -1) {
          selectedId = null;
          if (!liveEl.checked) {
            detailEl.innerHTML =
              "<p class=\"empty\">That trace is no longer in the store (retention or clear).</p>";
          }
        }
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
    lastDetailKey = "";
    detailPinned = false;
    jget("/dev/api/ai-trace/" + selectedId).then(function (pack) {
      renderDetail(pack, { force: true });
    });
  });

  detailEl.addEventListener("scroll", function () {
    const max = Math.max(0, detailEl.scrollHeight - detailEl.clientHeight);
    detailPinned = max > 8 && detailEl.scrollTop < max - 8;
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
