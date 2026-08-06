(() => {
  const listEl = document.getElementById("response-list");
  const emptyEl = document.getElementById("empty-state");
  const listTitle = document.getElementById("list-title");
  const placeholder = document.getElementById("placeholder");
  const detailBody = document.getElementById("detail-body");
  const btnReview = document.getElementById("btn-review");
  const btnUnreview = document.getElementById("btn-unreview");
  const btnRefresh = document.getElementById("btn-refresh");

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

  async function loadList() {
    const reviewed = view === "reviewed";
    const data = await fetchJSON(`/api/responses?reviewed=${reviewed}`);
    listEl.innerHTML = "";
    listTitle.textContent = reviewed ? "Reviewed" : "Inbox";

    if (!data.responses.length) {
      emptyEl.classList.remove("hidden");
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
        <span class="item-subject">${escapeHtml(item.prompt_subject || item.prompt_id)}</span>
        <span class="item-meta">${escapeHtml(formatDate(item.received_date))} · ${escapeHtml(item.prompt_id)}</span>
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

    document.getElementById("d-meta").textContent =
      `${detail.prompt_id} · received ${formatDate(detail.received_date)}` +
      (detail.reviewed ? " · reviewed" : "");
    document.getElementById("d-prompt-subject").textContent = detail.prompt_subject || "";
    document.getElementById("d-prompt-body").textContent = detail.prompt_body || "";
    document.getElementById("d-reply").textContent =
      detail.response_text || "(no text body — see attachments)";

    const attList = document.getElementById("d-attachments");
    const noAtt = document.getElementById("d-no-attachments");
    attList.innerHTML = "";
    const atts = detail.attachments || [];
    if (!atts.length) {
      noAtt.classList.remove("hidden");
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

  loadList().catch((err) => {
    emptyEl.classList.remove("hidden");
    emptyEl.textContent = `Failed to load: ${err.message}`;
  });
})();
