(() => {
  const listEl = document.getElementById("response-list");
  const emptyEl = document.getElementById("empty-state");
  const listTitle = document.getElementById("list-title");
  const placeholder = document.getElementById("placeholder");
  const detailBody = document.getElementById("detail-body");
  const btnReview = document.getElementById("btn-review");
  const btnUnreview = document.getElementById("btn-unreview");
  const btnRefresh = document.getElementById("btn-refresh");
  const btnEvsExtract = document.getElementById("btn-evs-extract");
  const btnEvsRemove = document.getElementById("btn-evs-remove");
  const batchStatus = document.getElementById("batch-status");
  const btnMemExtract = document.getElementById("btn-mem-extract");
  const btnMemOpenQuestions = document.getElementById("btn-mem-open-questions");
  const btnMemValidate = document.getElementById("btn-mem-validate");
  const btnMemSends = document.getElementById("btn-mem-sends");
  const memStatus = document.getElementById("mem-status");
  let memSendsOn = false;

  function renderMemSendsButton() {
    btnMemSends.textContent = memSendsOn ? "MEM sends: ON" : "MEM sends: OFF";
    btnMemSends.setAttribute("aria-pressed", memSendsOn ? "true" : "false");
  }

  async function refreshMemStatus() {
    const data = await fetchJSON("/api/mem/status");
    memSendsOn = Boolean(data.enabled);
    renderMemSendsButton();
    return data;
  }

  let view = "inbox";
  let selectedId = null;
  let current = null;

  async function fetchJSON(url, options) {
    const res = await fetch(url, options);
    if (!res.ok) {
      const text = await res.text();
      throw new Error(text || res.statusText);
    }
    return res.json();
  }

  function formatDate(value) {
    if (!value) return "";
    try {
      return new Date(value).toLocaleString();
    } catch {
      return value;
    }
  }

  function listLabel(item) {
    const snippet = (item.response_text || "").trim().replace(/\s+/g, " ");
    const short = snippet.length > 72 ? snippet.slice(0, 69) + "…" : snippet;
    if ((item.prompt_type || "").toUpperCase() === "EVS") {
      const seg = String(item.segment_index || 1).padStart(2, "0");
      if (short) return `EVS-${seg}: ${short}`;
      return `EVS-${seg}`;
    }
    if (short) return short;
    return item.subject || item.prompt_subject || item.prompt_id || "Response";
  }

  async function loadList() {
    const reviewed = view === "reviewed";
    const data = await fetchJSON(`/api/responses?reviewed=${reviewed}`);
    listEl.innerHTML = "";
    listTitle.textContent = reviewed ? "Reviewed" : "Inbox";

    if (!reviewed && data.duplicates_collapsed) {
      batchStatus.textContent = `Collapsed ${data.duplicates_collapsed} duplicate(s) → Reviewed.`;
    }

    if (!data.responses.length) {
      emptyEl.classList.remove("hidden");
      emptyEl.textContent = "Nothing here yet.";
      return;
    }
    emptyEl.classList.add("hidden");

    for (const item of data.responses) {
      const li = document.createElement("li");
      const btn = document.createElement("button");
      btn.type = "button";
      btn.dataset.id = String(item.id);
      if (item.id === selectedId) btn.classList.add("selected");
      btn.innerHTML = `
        <span class="item-subject">${escapeHtml(listLabel(item))}</span>
        <span class="item-meta">${escapeHtml(formatDate(item.received_date))} · ${escapeHtml(item.prompt_type || item.prompt_id)}</span>
      `;
      btn.addEventListener("click", () => selectResponse(item.id));
      li.appendChild(btn);
      listEl.appendChild(li);
    }
  }

  function escapeHtml(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  async function selectResponse(id) {
    selectedId = id;
    const detail = await fetchJSON(`/api/responses/${id}`);
    current = detail;
    placeholder.classList.add("hidden");
    detailBody.classList.remove("hidden");

    const seg =
      (detail.prompt_type || "").toUpperCase() === "EVS"
        ? ` · segment ${String(detail.segment_index || 1).padStart(2, "0")}`
        : "";
    document.getElementById("d-meta").textContent =
      `${detail.prompt_type || detail.prompt_id}${seg} · received ${formatDate(detail.received_date)}` +
      (detail.reviewed ? " · reviewed" : "");
    document.getElementById("d-prompt-subject").textContent =
      detail.subject || detail.prompt_subject || "";
    let promptBody = detail.prompt_body || "";
    if (promptBody.includes("Ad-hoc journal") || promptBody.includes("Ad-hoc EVS") ||
        promptBody.includes("Ad-hoc memory") || promptBody.includes("Ad-hoc capture") ||
        promptBody.includes("original outbound not in DB") || promptBody.includes("Ad-hoc")) {
      // Keep clarifying copy; already humanized in new captures
    }
    document.getElementById("d-prompt-body").textContent = promptBody;
    document.getElementById("d-reply").textContent =
      detail.response_text || "(no text body — see attachments)";

    const attList = document.getElementById("d-attachments");
    const noAtt = document.getElementById("d-no-attachments");
    attList.innerHTML = "";
    // MBC-003: EVS ignores attachments in the review UI
    const atts =
      (detail.prompt_type || "").toUpperCase() === "EVS" ? [] : detail.attachments || [];
    if (!atts.length) {
      noAtt.classList.remove("hidden");
      noAtt.textContent =
        (detail.prompt_type || "").toUpperCase() === "EVS"
          ? "EVS ignores attachments (text / Whisper only)."
          : "No attachments.";
    } else {
      noAtt.classList.add("hidden");
      for (const a of atts) {
        const li = document.createElement("li");
        li.innerHTML = `
          <a href="/api/attachments/${a.id}/file" target="_blank" rel="noopener">${escapeHtml(a.filename)}</a>
          <span class="att-meta">${escapeHtml(a.mime_type || "")}${a.is_audio ? " · audio" : ""} · ${escapeHtml(a.transcript_status || "")}</span>
        `;
        attList.appendChild(li);
      }
    }

    const transcripts = atts.filter((a) => a.transcript);
    const tSection = document.getElementById("transcript-section");
    const tArrow = document.querySelector(".transcript-arrow");
    const tBody = document.getElementById("d-transcripts");
    if (transcripts.length) {
      tSection.classList.remove("hidden");
      tArrow.classList.remove("hidden");
      tBody.textContent = transcripts
        .map((a) => `— ${a.filename} —\n${a.transcript}`)
        .join("\n\n");
    } else {
      tSection.classList.add("hidden");
      tArrow.classList.add("hidden");
      tBody.textContent = "";
    }

    const isReviewed = Boolean(detail.reviewed);
    btnReview.classList.toggle("hidden", isReviewed);
    btnUnreview.classList.toggle("hidden", !isReviewed);

    for (const btn of listEl.querySelectorAll("button")) {
      btn.classList.toggle("selected", Number(btn.dataset.id) === id);
    }
  }

  async function setReviewed(reviewed) {
    if (!selectedId) return;
    await fetchJSON(`/api/responses/${selectedId}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reviewed }),
    });
    selectedId = null;
    current = null;
    placeholder.classList.remove("hidden");
    detailBody.classList.add("hidden");
    await loadList();
  }

  async function extractEvs() {
    const suggested = `evs_export_${new Date().toISOString().slice(0, 10)}.txt`;
    const filename = window.prompt("Save EVS export as filename:", suggested);
    if (!filename) return;
    batchStatus.textContent = "Extracting…";
    const res = await fetch("/api/evs/extract", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename }),
    });
    if (!res.ok) {
      batchStatus.textContent = `Extract failed: ${await res.text()}`;
      return;
    }
    const blob = await res.blob();
    const disp = res.headers.get("Content-Disposition") || "";
    const match = /filename=\"([^\"]+)\"/.exec(disp);
    const outName = match ? match[1] : filename;
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = outName;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    batchStatus.textContent = `Downloaded ${outName}`;
  }

  async function removeEvs() {
    const ok = window.confirm(
      "Remove ALL EVS responses from the database and delete their linked files on disk?\n\nDo this after Extract. JRN/MEM are not affected."
    );
    if (!ok) return;
    batchStatus.textContent = "Removing…";
    const data = await fetchJSON("/api/evs/remove", { method: "POST" });
    batchStatus.textContent =
      `Removed ${data.responses_deleted} EVS · ${data.files_removed} files`;
    selectedId = null;
    placeholder.classList.remove("hidden");
    detailBody.classList.add("hidden");
    await loadList();
  }

  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", async () => {
      document.querySelectorAll(".tab").forEach((t) => {
        t.classList.remove("active");
        t.setAttribute("aria-selected", "false");
      });
      tab.classList.add("active");
      tab.setAttribute("aria-selected", "true");
      view = tab.dataset.view;
      selectedId = null;
      placeholder.classList.remove("hidden");
      detailBody.classList.add("hidden");
      await loadList();
    });
  });

  btnReview.addEventListener("click", () => setReviewed(true));
  btnUnreview.addEventListener("click", () => setReviewed(false));
  btnRefresh.addEventListener("click", () => loadList());
  btnEvsExtract.addEventListener("click", () => extractEvs().catch((e) => {
    batchStatus.textContent = e.message;
  }));
  btnEvsRemove.addEventListener("click", () => removeEvs().catch((e) => {
    batchStatus.textContent = e.message;
  }));
  btnMemExtract.addEventListener("click", () => {
    memStatus.textContent = "Exporting…";
    fetchJSON("/api/mem/extract", { method: "POST" })
      .then((data) => {
        memStatus.textContent = `Wrote ${data.count} Q&A → ${data.batch_dir}`;
      })
      .catch((e) => {
        memStatus.textContent = e.message;
      });
  });
  btnMemOpenQuestions.addEventListener("click", () => {
    memStatus.textContent = "Opening…";
    fetchJSON("/api/mem/questions/open", { method: "POST" })
      .then((data) => {
        memStatus.textContent = `Opened ${data.path} — use ids 1..N contiguous`;
      })
      .catch((e) => {
        memStatus.textContent = e.message;
      });
  });
  btnMemSends.addEventListener("click", () => {
    const next = !memSendsOn;
    memStatus.textContent = next ? "Enabling sends…" : "Disabling sends…";
    fetchJSON("/api/mem/sends", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled: next }),
    })
      .then((data) => {
        memSendsOn = Boolean(data.enabled);
        renderMemSendsButton();
        memStatus.textContent = data.hint || (memSendsOn ? "MEM sends ON" : "MEM sends OFF");
      })
      .catch((e) => {
        memStatus.textContent = e.message;
      });
  });
  btnMemValidate.addEventListener("click", () => {
    memStatus.textContent = "Validating…";
    fetchJSON("/api/mem/questions/validate")
      .then((data) => {
        if (data.ok) {
          const samples = (data.sample || [])
            .map((s) => `#${s.id}: ${s.text}`)
            .join(" | ");
          memStatus.textContent = `OK — ${data.count} questions. ${samples}`;
        } else {
          memStatus.textContent = `INVALID — ${(data.errors || []).join("; ")}`;
        }
      })
      .catch((e) => {
        memStatus.textContent = e.message;
      });
  });

  refreshMemStatus().catch(() => {
    btnMemSends.textContent = "MEM sends: ?";
  });

  loadList().catch((err) => {
    emptyEl.classList.remove("hidden");
    emptyEl.textContent = `Failed to load: ${err.message}`;
  });
})();
