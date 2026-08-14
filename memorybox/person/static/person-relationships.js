/**
 * P2-I6 Relationships modal — Direct / Extended kinship over Person Explorer.
 */
(function () {
  const cfg = window.MB_PERSON_SURFACE || {};
  if (!cfg.personId) return;

  let bundle = null;
  let peopleIndex = [];
  let activeTab = "direct";
  let sheetMode = "add"; // add | edit | change_person
  let editing = null; // { assertionId, personId, role }
  let openMenuId = null;

  const GROUP_LABELS = {
    parents: "Parents",
    siblings: "Siblings",
    spouse_partner: "Spouse / Partner",
    children: "Children",
  };

  function $(id) {
    return document.getElementById(id);
  }

  function escapeHtml(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function initial(name) {
    return String(name || "?").trim().charAt(0).toUpperCase() || "?";
  }

  async function loadPeopleOptions() {
    try {
      const res = await fetch("/people");
      if (!res.ok) return;
      const data = await res.json();
      const list = data.people || data.items || data || [];
      peopleIndex = Array.isArray(list) ? list : [];
      const dl = $("mb-rel-people-list");
      if (!dl) return;
      dl.innerHTML = peopleIndex
        .map((p) => {
          const id = p.id || p.person_id || "";
          const name = p.display_name || p.name || id;
          return `<option value="${escapeHtml(name)}" data-id="${escapeHtml(id)}"></option>`;
        })
        .join("");
    } catch (_) {
      peopleIndex = [];
    }
  }

  function resolvePersonIdFromInput() {
    const q = ($("mb-rel-person-q").value || "").trim();
    const hidden = $("mb-rel-person-id").value;
    if (hidden) return hidden;
    const hit = peopleIndex.find((p) => {
      const name = String(p.display_name || p.name || "").toLowerCase();
      return name === q.toLowerCase();
    });
    return hit ? hit.id || hit.person_id : "";
  }

  async function refreshBundle() {
    const id = cfg.personId;
    const res = await fetch("/people/" + encodeURIComponent(id) + "/relationships");
    if (!res.ok) throw new Error("relationships " + res.status);
    bundle = await res.json();
    renderBody();
  }

  function cardHtml(hit, { derived }) {
    const name = hit.display_name || hit.person_id || "Person";
    const role = hit.label || hit.role_kind || "";
    const aid = (hit.assertion_ids && hit.assertion_ids[0]) || hit.assertion_id || "";
    const menuId = "m-" + (aid || hit.person_id);
    const path = hit.path_summary
      ? `<p class="mb-rel-path">${escapeHtml(hit.path_summary)}</p>`
      : "";
    const badge = derived
      ? `<span class="mb-rel-badge">Derived</span>`
      : "";
    const actions = derived
      ? `<div class="mb-rel-menu" id="${menuId}" hidden>
          <button type="button" data-act="path" data-person="${escapeHtml(hit.person_id)}">View relationship path</button>
          <button type="button" data-act="correct" data-ids="${escapeHtml((hit.assertion_ids || []).join(","))}">Correct underlying relationship</button>
        </div>`
      : `<div class="mb-rel-menu" id="${menuId}" hidden>
          <button type="button" data-act="edit" data-aid="${escapeHtml(aid)}" data-person="${escapeHtml(hit.person_id)}" data-role="${escapeHtml(hit.role_kind || "")}">Edit Relationship</button>
          <button type="button" data-act="change" data-aid="${escapeHtml(aid)}" data-person="${escapeHtml(hit.person_id)}" data-role="${escapeHtml(hit.role_kind || "")}">Change Person</button>
          <button type="button" class="is-danger" data-act="remove" data-aid="${escapeHtml(aid)}" data-name="${escapeHtml(name)}">Remove Relationship</button>
          <button type="button" data-act="history" data-aid="${escapeHtml(aid)}">View History</button>
        </div>`;
    return `<div class="mb-rel-card${derived ? " is-derived" : ""}" data-menu-host="${menuId}">
      <div class="mb-rel-av" data-portrait="${escapeHtml(hit.person_id || "")}" aria-hidden="true">${escapeHtml(initial(name))}</div>
      <div class="mb-rel-card-text">
        <div class="mb-rel-card-name">${escapeHtml(name)}${badge}</div>
        <div class="mb-rel-card-role">${escapeHtml(role)}</div>
        ${path}
      </div>
      <button type="button" class="mb-rel-more" data-menu="${menuId}" aria-label="Actions">⋯</button>
      ${actions}
    </div>`;
  }

  function renderBody() {
    const body = $("mb-rel-body");
    if (!body || !bundle) return;
    const extCount = (bundle.extended || []).length;
    const countEl = $("mb-rel-ext-count");
    if (countEl) countEl.textContent = String(extCount);

    if (activeTab === "extended") {
      const ext = bundle.extended || [];
      if (!ext.length) {
        body.innerHTML =
          '<p class="mb-rel-empty">No extended kinship derived yet. Add parents, siblings, and children — MemoryBox will derive aunts, nephews, cousins, and more.</p>';
        return;
      }
      body.innerHTML =
        '<div class="mb-rel-group"><h4>Extended Relationships</h4><div class="mb-rel-cards">' +
        ext.map((h) => cardHtml(h, { derived: true })).join("") +
        "</div></div>";
      bindCardMenus(body);
      paintRelPortraits(body);
      return;
    }

    const direct = bundle.direct || {};
    const order = ["parents", "siblings", "spouse_partner", "children"];
    let html = "";
    let any = false;
    for (const g of order) {
      const rows = direct[g] || [];
      if (!rows.length) continue;
      any = true;
      html +=
        `<div class="mb-rel-group"><h4>${GROUP_LABELS[g] || g} (${rows.length})</h4><div class="mb-rel-cards">` +
        rows.map((h) => cardHtml(h, { derived: false })).join("") +
        "</div></div>";
    }
    if (!any) {
      html =
        '<p class="mb-rel-empty">No direct relationships yet. Use + Add Relationship to teach MemoryBox about this family.</p>';
    }
    body.innerHTML = html;
    bindCardMenus(body);
    paintRelPortraits(body);
  }

  function paintRelPortraits(root) {
    (root || document).querySelectorAll(".mb-rel-av[data-portrait]").forEach((el) => {
      const pid = el.getAttribute("data-portrait") || "";
      if (!pid) return;
      const url = "/people/" + encodeURIComponent(pid) + "/portrait?v=rel";
      const img = new Image();
      img.onload = () => {
        el.textContent = "";
        el.style.backgroundImage = "url(" + JSON.stringify(url) + ")";
        el.classList.add("has-photo");
      };
      img.src = url;
    });
  }

  function closeMenus() {
    document.querySelectorAll(".mb-rel-menu").forEach((el) => {
      el.hidden = true;
    });
    openMenuId = null;
  }

  function bindCardMenus(root) {
    root.querySelectorAll(".mb-rel-more").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const id = btn.getAttribute("data-menu");
        const menu = $(id);
        if (!menu) return;
        const wasOpen = !menu.hidden;
        closeMenus();
        if (!wasOpen) {
          menu.hidden = false;
          openMenuId = id;
        }
      });
    });
    root.querySelectorAll(".mb-rel-menu button").forEach((btn) => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const act = btn.getAttribute("data-act");
        closeMenus();
        if (act === "path") {
          const pid = btn.getAttribute("data-person");
          const hit = (bundle.extended || []).find((h) => h.person_id === pid);
          alert(
            (hit && hit.path_summary) ||
              "No path available. Derived from direct parent/sibling/spouse relationships."
          );
          return;
        }
        if (act === "correct") {
          activeTab = "direct";
          syncTabs();
          renderBody();
          alert(
            "Derived kinship can’t be edited directly. Correct the underlying Parent / Sibling / Child relationship on the Direct tab, then Extended will refresh."
          );
          return;
        }
        if (act === "history") {
          const aid = btn.getAttribute("data-aid");
          const hist = (bundle.history || []).filter(
            (h) => h.assertion_id === aid || true
          );
          const lines = (bundle.history || [])
            .slice()
            .reverse()
            .slice(0, 12)
            .map((h) => {
              return `${h.created_at || "—"} · ${h.status} · ${h.from_display_name || h.from_person_id} ${h.label || h.role_kind} ${h.to_display_name || h.to_person_id} (by ${h.actor_key || "owner"})`;
            });
          alert(lines.length ? lines.join("\n") : "No history rows yet.");
          return;
        }
        if (act === "remove") {
          const aid = btn.getAttribute("data-aid");
          const name = btn.getAttribute("data-name") || "this person";
          if (
            !confirm(
              `Remove the relationship with ${name}?\n\nThis unlinks the relationship only — it does not delete either Person. Derived kinship will recompute.`
            )
          ) {
            return;
          }
          const res = await fetch(
            "/people/relationships/" + encodeURIComponent(aid) + "/withdraw",
            { method: "POST" }
          );
          if (!res.ok) {
            alert("Could not remove relationship (" + res.status + ")");
            return;
          }
          await refreshBundle();
          return;
        }
        if (act === "edit" || act === "change") {
          editing = {
            assertionId: btn.getAttribute("data-aid"),
            personId: btn.getAttribute("data-person"),
            role: btn.getAttribute("data-role") || "sibling",
          };
          sheetMode = act === "edit" ? "edit" : "change_person";
          openSheet();
        }
      });
    });
  }

  function syncTabs() {
    document.querySelectorAll(".mb-rel-tab").forEach((t) => {
      const on = t.getAttribute("data-rel-tab") === activeTab;
      t.classList.toggle("is-active", on);
      t.setAttribute("aria-selected", on ? "true" : "false");
    });
    const add = $("mb-rel-add");
    if (add) add.hidden = activeTab !== "direct";
  }

  async function openModal() {
    const modal = $("mb-rel-modal");
    if (!modal) return;
    const name = cfg.displayName || "Person";
    $("mb-rel-title").textContent = "Relationships for " + name;
    activeTab = "direct";
    syncTabs();
    modal.hidden = false;
    try {
      await loadPeopleOptions();
      await refreshBundle();
    } catch (err) {
      $("mb-rel-body").innerHTML =
        '<p class="mb-rel-empty">Could not load relationships: ' +
        escapeHtml(String(err)) +
        "</p>";
    }
  }

  function closeModal() {
    const modal = $("mb-rel-modal");
    if (modal) modal.hidden = true;
    closeMenus();
    closeSheet();
  }

  function openSheet() {
    const sheet = $("mb-rel-sheet");
    const title = $("mb-rel-sheet-title");
    const err = $("mb-rel-sheet-err");
    if (err) {
      err.hidden = true;
      err.textContent = "";
    }
    if (sheetMode === "add") {
      title.textContent = "Add Relationship";
      $("mb-rel-person-q").value = "";
      $("mb-rel-person-id").value = "";
      $("mb-rel-person-q").disabled = false;
      $("mb-rel-role").disabled = false;
      $("mb-rel-note").value = "";
    } else if (sheetMode === "edit") {
      title.textContent = "Edit Relationship";
      const p = peopleIndex.find(
        (x) => (x.id || x.person_id) === (editing && editing.personId)
      );
      $("mb-rel-person-q").value =
        (p && (p.display_name || p.name)) || (editing && editing.personId) || "";
      $("mb-rel-person-id").value = (editing && editing.personId) || "";
      $("mb-rel-person-q").disabled = true;
      $("mb-rel-role").disabled = false;
      // Map role_kind to UX select value
      const rk = (editing && editing.role) || "sibling";
      const map = {
        mother_of: "mother",
        father_of: "father",
        parent_of: "parent",
        son_of: "son",
        daughter_of: "daughter",
        child_of: "child",
        sibling_of: "sibling",
        spouse_of: "spouse",
        partner_of: "partner",
      };
      $("mb-rel-role").value = map[rk] || "sibling";
    } else {
      title.textContent = "Change Person";
      $("mb-rel-person-q").value = "";
      $("mb-rel-person-id").value = "";
      $("mb-rel-person-q").disabled = false;
      $("mb-rel-role").disabled = true;
      const rk = (editing && editing.role) || "sibling";
      const map = {
        mother_of: "mother",
        father_of: "father",
        parent_of: "parent",
        son_of: "son",
        daughter_of: "daughter",
        child_of: "child",
        sibling_of: "sibling",
        spouse_of: "spouse",
        partner_of: "partner",
      };
      $("mb-rel-role").value = map[rk] || "sibling";
    }
    sheet.hidden = false;
  }

  function closeSheet() {
    const sheet = $("mb-rel-sheet");
    if (sheet) sheet.hidden = true;
    editing = null;
    sheetMode = "add";
  }

  async function saveSheet() {
    const err = $("mb-rel-sheet-err");
    const subject = cfg.personId;
    const roleUx = $("mb-rel-role").value;
    const note = ($("mb-rel-note").value || "").trim() || null;
    // Selected person RELATED TO viewed person:
    // e.g. Mother of Peggy => from=selected, role=mother_of, to=Peggy
    let otherId = resolvePersonIdFromInput();
    if (!otherId && sheetMode !== "edit") {
      err.hidden = false;
      err.textContent = "Choose an existing Person from the list.";
      return;
    }
    if (sheetMode === "edit") otherId = editing.personId;

    // Role from selected person's perspective toward subject
    const role = roleUx; // server normalize_ux_role

    try {
      if (sheetMode === "add") {
        const res = await fetch("/people/relationships", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            from_person_id: otherId,
            to_person_id: subject,
            role_kind: role,
            note: note,
          }),
        });
        if (!res.ok) {
          const t = await res.text();
          throw new Error(t || res.status);
        }
      } else {
        const res = await fetch(
          "/people/relationships/" +
            encodeURIComponent(editing.assertionId) +
            "/supersede",
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              from_person_id: otherId,
              to_person_id: subject,
              role_kind: role,
              note: note,
            }),
          }
        );
        if (!res.ok) {
          const t = await res.text();
          throw new Error(t || res.status);
        }
      }
      closeSheet();
      await refreshBundle();
    } catch (ex) {
      err.hidden = false;
      err.textContent = "Save failed: " + String(ex.message || ex);
    }
  }

  // Wire openers from I5 chrome
  function wireOpeners() {
    const open = () => openModal();
    const relHeader = $("mb-person-relationships");
    if (relHeader) {
      relHeader.onclick = (e) => {
        e.preventDefault();
        open();
      };
    }
    const famOpen = $("mb-person-family-open");
    if (famOpen) famOpen.onclick = open;
    const famAdd = $("mb-person-family-add");
    if (famAdd) {
      famAdd.onclick = () => {
        openModal().then(() => {
          sheetMode = "add";
          openSheet();
        });
      };
    }
  }

  function bindChrome() {
    $("mb-rel-close") && $("mb-rel-close").addEventListener("click", closeModal);
    $("mb-rel-close-btn") &&
      $("mb-rel-close-btn").addEventListener("click", closeModal);
    $("mb-rel-modal") &&
      $("mb-rel-modal").addEventListener("click", (e) => {
        if (e.target.id === "mb-rel-modal") closeModal();
      });
    document.querySelectorAll(".mb-rel-tab").forEach((t) => {
      t.addEventListener("click", () => {
        activeTab = t.getAttribute("data-rel-tab") || "direct";
        syncTabs();
        renderBody();
      });
    });
    $("mb-rel-add") &&
      $("mb-rel-add").addEventListener("click", () => {
        sheetMode = "add";
        editing = null;
        openSheet();
      });
    $("mb-rel-sheet-cancel") &&
      $("mb-rel-sheet-cancel").addEventListener("click", closeSheet);
    $("mb-rel-sheet-save") &&
      $("mb-rel-sheet-save").addEventListener("click", saveSheet);
    $("mb-rel-person-q") &&
      $("mb-rel-person-q").addEventListener("change", () => {
        const q = ($("mb-rel-person-q").value || "").trim().toLowerCase();
        const hit = peopleIndex.find(
          (p) => String(p.display_name || p.name || "").toLowerCase() === q
        );
        $("mb-rel-person-id").value = hit ? hit.id || hit.person_id || "" : "";
      });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        if ($("mb-rel-sheet") && !$("mb-rel-sheet").hidden) closeSheet();
        else if ($("mb-rel-modal") && !$("mb-rel-modal").hidden) closeModal();
      }
    });
    document.addEventListener("click", () => closeMenus());
  }

  // Defer until person chrome exists
  function boot() {
    if (!$("mb-rel-modal")) return;
    bindChrome();
    // Override I5 drawer openers once DOM ready
    const tryWire = () => wireOpeners();
    tryWire();
    window.addEventListener("mb-person-ready", tryWire);
    // Also patch after a tick (person-explore binds onclick in loadProfile)
    setTimeout(tryWire, 500);
    setTimeout(tryWire, 1500);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }

  window.mbOpenRelationshipsModal = openModal;
})();
