/**
 * P2-I10A.1 family Person Profile/Editor — /people/{id}/edit
 */
(function () {
  const cfg = window.MB_PERSON_EDIT || {};
  const pid = String(cfg.personId || "").trim();
  const viewMode = new URLSearchParams(window.location.search).get("view") === "1";
  let peopleIndex = [];
  let profile = {};

  function $(id) {
    return document.getElementById(id);
  }
  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }
  function status(msg, err) {
    const el = $("mb-edit-status");
    if (!el) return;
    el.hidden = !msg;
    el.textContent = msg || "";
    el.classList.toggle("err", Boolean(err));
  }
  async function j(url, opt) {
    const res = await fetch(url, opt || {});
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw { detail: data.detail || res.statusText || String(res.status) };
    return data;
  }
  function resolvePerson(q) {
    const t = String(q || "").trim().toLowerCase();
    if (!t) return "";
    const hit = peopleIndex.find((p) => {
      const name = String(p.display_name || p.name || "").toLowerCase();
      return name === t || String(p.id) === t;
    });
    return hit ? hit.id || hit.person_id : "";
  }
  function factDateValue(f) {
    if (!f) return "";
    const prec = String(f.date_precision || "day");
    const raw = String(f.value_date || "").slice(0, 10);
    if (!raw) return "";
    if (prec === "year") return raw.slice(0, 4);
    if (prec === "month") return raw.slice(0, 7);
    return raw;
  }

  async function loadPeople() {
    try {
      const data = await j("/people");
      peopleIndex = data.people || data.items || [];
      const dl = $("mb-edit-people-list");
      if (!dl) return;
      dl.innerHTML = peopleIndex
        .map((p) => '<option value="' + esc(p.display_name || p.id) + '"></option>')
        .join("");
    } catch (_) {
      peopleIndex = [];
    }
  }

  function paintProfile() {
    const idn = profile.identity || {};
    const name = idn.display_name || cfg.displayName || "";
    $("mb-edit-title").textContent = name || "Person";
    $("mb-edit-name").value = name;
    const facts = profile.facts || [];
    const birth = facts.find((f) => f.fact_kind === "birth_date");
    const death = facts.find((f) => f.fact_kind === "death_date");
    const notes = facts.filter((f) => f.fact_kind === "note");
    $("mb-edit-birth").value = factDateValue(birth);
    $("mb-edit-birth-prec").value = (birth && birth.date_precision) || "day";
    $("mb-edit-death").value = factDateValue(death);
    $("mb-edit-death-prec").value = (death && death.date_precision) || "day";
    $("mb-edit-fact-note").value = (birth && birth.note) || (death && death.note) || "";
    $("mb-edit-notes").value = notes.map((n) => n.value_text || "").filter(Boolean).join("\n");
    const aliases = profile.aliases || [];
    $("mb-edit-aliases").innerHTML = aliases.length
      ? "<ul>" + aliases.map((a) => "<li>" + esc(a.alias_kind) + ": <b>" + esc(a.alias_text) + "</b></li>").join("") + "</ul>"
      : "<p class='mb-edit-muted'>No nicknames yet.</p>";
    const contacts = profile.contacts || [];
    $("mb-edit-contacts").innerHTML = contacts.length
      ? contacts
          .map((c) => {
            return (
              '<div data-cid="' +
              esc(c.id) +
              '" data-kind="' +
              esc(c.contact_kind) +
              '">' +
              esc(c.contact_kind) +
              ": <b>" +
              esc(c.value_text) +
              "</b> <button type='button' class='mb-edit-btn contact-super'>Correct</button></div>"
            );
          })
          .join("")
      : "<p class='mb-edit-muted'>No confirmed contacts yet.</p>";
    $("mb-edit-contacts").querySelectorAll(".contact-super").forEach((btn) => {
      btn.onclick = async () => {
        const wrap = btn.parentElement;
        const kind = wrap.getAttribute("data-kind");
        const next = window.prompt("New " + kind + " value");
        if (!next) return;
        let val = next.trim();
        if (kind === "phone") val = val.replace(/\D/g, "");
        await j("/people/contacts/" + encodeURIComponent(wrap.getAttribute("data-cid")) + "/supersede", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ value_text: val, note: "owner correction" }),
        });
        await reload();
      };
    });
    const port = $("mb-edit-portrait");
    const url = "/people/" + encodeURIComponent(pid) + "/portrait?v=" + Date.now();
    const img = new Image();
    img.onload = () => {
      port.style.backgroundImage = "url(" + JSON.stringify(url) + ")";
      port.classList.add("has-photo");
      port.textContent = "";
    };
    img.onerror = () => {
      port.classList.remove("has-photo");
      port.textContent = (name.charAt(0) || "?").toUpperCase();
    };
    img.src = url;
  }

  function paintRelationships() {
    const rel = profile.relationships || {};
    const direct = rel.direct || {};
    const groups = [
      ["parents", "Parents"],
      ["siblings", "Siblings"],
      ["spouse_partner", "Spouse or partner"],
      ["children", "Children"],
    ];
    let html = "";
    groups.forEach(([key, label]) => {
      const hits = direct[key] || [];
      html += '<div class="mb-edit-rel-group"><h4>' + esc(label) + "</h4>";
      if (!hits.length) html += "<p class='mb-edit-muted'>None recorded.</p>";
      else {
        html += "<ul>";
        hits.forEach((h) => {
          const derived = h.derived || h.is_derived;
          html +=
            "<li>" +
            esc(h.display_name || h.to_display_name || "Person") +
            " — " +
            esc(h.label || h.role_kind || "") +
            (derived ? " <i>(Derived)</i>" : "") +
            "</li>";
        });
        html += "</ul>";
      }
      html += "</div>";
    });
    const ext = rel.extended || [];
    const extList = Array.isArray(ext) ? ext : Object.values(ext).flat();
    html += '<div class="mb-edit-rel-group"><h4>Other family</h4>';
    if (!extList.length) html += "<p class='mb-edit-muted'>None derived.</p>";
    else {
      html += "<ul>";
      extList.forEach((h) => {
        html +=
          "<li>" +
          esc(h.display_name || "Person") +
          " — " +
          esc(h.label || h.role_kind || "") +
          " <i>(Derived)</i></li>";
      });
      html += "</ul>";
    }
    html += "</div>";
    $("mb-edit-rel-groups").innerHTML = html;
    const events = profile.life_events || [];
    $("mb-edit-marriages").innerHTML = events.length
      ? "<ul>" +
        events
          .map((e) => {
            const names = (e.participants || []).map((p) => p.display_name || p.person_id).join(" & ");
            return "<li>" + esc(names) + " — " + esc(e.event_date || "date unknown") + "</li>";
          })
          .join("") +
        "</ul>"
      : "";
  }

  function paintIdentity() {
    const idn = profile.identity || {};
    const maps = idn.provider_mappings || [];
    let html =
      "<p>Canonical MemoryBox Person <b>" +
      esc(idn.id || pid) +
      "</b></p><p>Status: " +
      esc(idn.status || "—") +
      (profile.is_canonical_owner ? " · this is you" : "") +
      "</p>";
    if (idn.identity_authority) html += "<p>Identity authority: " + esc(idn.identity_authority) + "</p>";
    html += "<h3>Linked provider identities</h3>";
    if (!maps.length) html += "<p class='mb-edit-muted'>None linked. Immich people are not the MemoryBox source of truth.</p>";
    else {
      html += "<ul>";
      maps.forEach((m) => {
        html +=
          "<li>" +
          esc(m.provider_key || "") +
          " · " +
          esc(m.label || m.external_id || "") +
          (m.confirmed_at ? " · confirmed" : " · unconfirmed") +
          "</li>";
      });
      html += "</ul>";
    }
    $("mb-edit-identity-body").innerHTML = html;
    const sel = $("mb-edit-reject-ext");
    sel.innerHTML = '<option value="">(choose)</option>';
    maps.forEach((m) => {
      const opt = document.createElement("option");
      opt.value = m.external_id;
      opt.textContent = (m.provider_key || "") + " · " + (m.label || m.external_id);
      sel.appendChild(opt);
    });
    const ownerNote = $("mb-edit-owner-note");
    if (profile.owner && profile.owner.env_overrides) {
      ownerNote.textContent = "MEMORYBOX_OWNER_PERSON_ID is set — the environment wins over this control.";
    } else {
      ownerNote.textContent = profile.is_canonical_owner ? "This person is already you." : "";
    }
  }

  function applyViewMode() {
    if (!viewMode) return;
    document.body.classList.add("mb-edit-readonly");
    const kicker = document.querySelector(".mb-edit-kicker");
    if (kicker) kicker.textContent = "About";
    const title = $("mb-edit-title");
    document.title = "MemoryBox — About " + ((title && title.textContent) || "person");
    const sub = document.querySelector(".mb-edit-sub");
    if (sub) {
      sub.textContent =
        "Read-only MemoryBox record. Edit opens the same screen so you can change it. Immich is never updated.";
    }
    document
      .querySelectorAll(".mb-edit-card input, .mb-edit-card select, .mb-edit-card textarea")
      .forEach((el) => {
        el.disabled = true;
      });
    ["mb-edit-save", "mb-edit-rel-save", "mb-edit-mar-save"].forEach((id) => {
      const el = $(id);
      if (el) el.hidden = true;
    });
    const relWrite = $("mb-edit-rel-write");
    if (relWrite) relWrite.hidden = true;
    const marWrite = $("mb-edit-mar-write");
    if (marWrite) marWrite.hidden = true;
    const adv = $("mb-edit-advanced");
    if (adv) adv.hidden = true;
    const enter = $("mb-edit-enter-edit");
    if (enter) {
      enter.hidden = false;
      enter.href = "/people/" + encodeURIComponent(pid) + "/edit";
    }
    const contacts = $("mb-edit-contacts");
    if (contacts) {
      contacts.querySelectorAll(".contact-super").forEach((btn) => {
        btn.hidden = true;
      });
    }
    ["mb-edit-nick", "mb-edit-alt", "mb-edit-email", "mb-edit-phone"].forEach((id) => {
      const el = $(id);
      const lab = el && el.closest("label");
      if (lab) lab.hidden = true;
    });
  }

  async function reload() {
    const data = await j("/people/" + encodeURIComponent(pid) + "/profile");
    profile = data.profile || data;
    paintProfile();
    paintRelationships();
    paintIdentity();
    applyViewMode();
  }

  async function saveProfile() {
    const idn = profile.identity || {};
    const facts = profile.facts || [];
    const curBirth = facts.find((f) => f.fact_kind === "birth_date");
    const curDeath = facts.find((f) => f.fact_kind === "death_date");
    const name = $("mb-edit-name").value.trim();
    if (name.length >= 2 && name !== String(idn.display_name || "").trim()) {
      await j("/people/" + encodeURIComponent(pid) + "/name", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ display_name: name }),
      });
    }
    const nick = $("mb-edit-nick").value.trim();
    if (nick) {
      await j("/people/" + encodeURIComponent(pid) + "/aliases", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ alias_kind: "nickname", alias_text: nick }),
      });
      $("mb-edit-nick").value = "";
    }
    const alt = $("mb-edit-alt").value.trim();
    if (alt) {
      await j("/people/" + encodeURIComponent(pid) + "/aliases", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ alias_kind: "alternate_name", alias_text: alt }),
      });
      $("mb-edit-alt").value = "";
    }
    const birth = $("mb-edit-birth").value.trim();
    const birthPrec = $("mb-edit-birth-prec").value;
    const factNote = $("mb-edit-fact-note").value.trim() || null;
    const birthChanged =
      birth &&
      (birth !== factDateValue(curBirth) ||
        birthPrec !== ((curBirth && curBirth.date_precision) || "day") ||
        factNote !== ((curBirth && curBirth.note) || null));
    if (birthChanged) {
      await j("/people/" + encodeURIComponent(pid) + "/facts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          fact_kind: "birth_date",
          value_date: birth,
          date_precision: birthPrec,
          note: factNote,
        }),
      });
    }
    const death = $("mb-edit-death").value.trim();
    const deathPrec = $("mb-edit-death-prec").value;
    const deathChanged =
      death &&
      (death !== factDateValue(curDeath) ||
        deathPrec !== ((curDeath && curDeath.date_precision) || "day") ||
        factNote !== ((curDeath && curDeath.note) || null));
    if (deathChanged) {
      await j("/people/" + encodeURIComponent(pid) + "/facts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          fact_kind: "death_date",
          value_date: death,
          date_precision: deathPrec,
          note: factNote,
        }),
      });
    }
    const existingNotes = facts
      .filter((f) => f.fact_kind === "note")
      .map((n) => n.value_text || "")
      .filter(Boolean)
      .join("\n");
    const note = $("mb-edit-notes").value.trim();
    if (note && note !== existingNotes) {
      await j("/people/" + encodeURIComponent(pid) + "/facts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ fact_kind: "note", value_text: note }),
      });
    }
    const email = $("mb-edit-email").value.trim();
    if (email) {
      await j("/people/" + encodeURIComponent(pid) + "/contacts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ contact_kind: "email", value_text: email }),
      });
      $("mb-edit-email").value = "";
    }
    const phone = $("mb-edit-phone").value.replace(/\D/g, "");
    if (phone) {
      await j("/people/" + encodeURIComponent(pid) + "/contacts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ contact_kind: "phone", value_text: phone }),
      });
      $("mb-edit-phone").value = "";
    }
  }

  $("mb-edit-save").onclick = async () => {
    try {
      status("Saving…");
      await saveProfile();
      await reload();
      status("Saved in MemoryBox. Immich was not updated.");
    } catch (err) {
      status(err.detail || String(err), true);
    }
  };
  $("mb-edit-rel-save").onclick = async () => {
    try {
      const toId = resolvePerson($("mb-edit-rel-q").value);
      if (!toId) throw { detail: "Choose a related person from the list." };
      await j("/people/relationships", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          from_person_id: pid,
          to_person_id: toId,
          role_kind: $("mb-edit-rel-role").value,
        }),
      });
      $("mb-edit-rel-q").value = "";
      await reload();
      status("Relationship saved. Inverse is understood automatically.");
    } catch (err) {
      status(err.detail || String(err), true);
    }
  };
  $("mb-edit-mar-save").onclick = async () => {
    try {
      const other = resolvePerson($("mb-edit-mar-q").value);
      if (!other) throw { detail: "Choose a partner from the list." };
      await j("/people/life-events/marriage", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          person_a_id: pid,
          person_b_id: other,
          event_date: $("mb-edit-mar-date").value.trim() || null,
        }),
      });
      await reload();
      status("Marriage date saved.");
    } catch (err) {
      status(err.detail || String(err), true);
    }
  };
  $("mb-edit-owner").onclick = async () => {
    if (!window.confirm("Set yourself as this person in MemoryBox?")) return;
    try {
      await j("/people/owner", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ person_id: pid }),
      });
      await reload();
      status("Owner updated in MemoryBox.");
    } catch (err) {
      status(err.detail || String(err), true);
    }
  };
  $("mb-edit-reject").onclick = async () => {
    const ext = $("mb-edit-reject-ext").value;
    if (!ext) return;
    if (!window.confirm("Reject this provider mapping? Immich faces are not changed.")) return;
    try {
      await j("/people/reject", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ person_id: pid, provider_key: "immich", external_id: ext }),
      });
      await reload();
      status("Mapping rejected in MemoryBox.");
    } catch (err) {
      status(err.detail || String(err), true);
    }
  };
  $("mb-edit-merge").onclick = async () => {
    const loser = resolvePerson($("mb-edit-merge-q").value);
    if (!loser || loser === pid) {
      status("Choose a different person to merge away.", true);
      return;
    }
    if (!window.confirm("Merge that person into this one? This cannot be undone in the UI.")) return;
    try {
      await j("/people/merge", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ survivor_person_id: pid, loser_person_id: loser }),
      });
      await reload();
      status("Merged in MemoryBox.");
    } catch (err) {
      status(err.detail || String(err), true);
    }
  };
  $("mb-edit-teach").onclick = async () => {
    const ext = $("mb-edit-teach-ext").value.trim();
    if (!ext) return;
    try {
      await j("/people/teach", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          display_name: $("mb-edit-name").value.trim() || cfg.displayName || "Person",
          provider_key: "immich",
          external_id: ext,
        }),
      });
      await reload();
      status("Taught in MemoryBox. Immich person name was not patched.");
    } catch (err) {
      status(err.detail || String(err), true);
    }
  };
  $("mb-edit-map").onclick = async () => {
    const ext = $("mb-edit-map-ext").value.trim();
    if (!ext) return;
    try {
      await j("/people/" + encodeURIComponent(pid) + "/map", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          display_name: $("mb-edit-name").value.trim() || "Person",
          provider_key: "immich",
          external_id: ext,
        }),
      });
      await reload();
      status("Mapped in MemoryBox.");
    } catch (err) {
      status(err.detail || String(err), true);
    }
  };
  $("mb-edit-reconcile").onclick = async () => {
    const neu = $("mb-edit-recon-new").value.trim();
    if (!neu) return;
    try {
      await j("/people/" + encodeURIComponent(pid) + "/reconcile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider_key: "immich",
          new_external_id: neu,
          previous_external_id: $("mb-edit-recon-old").value.trim() || null,
        }),
      });
      await reload();
      status("Reconciled in MemoryBox.");
    } catch (err) {
      status(err.detail || String(err), true);
    }
  };

  if (!pid || pid.indexOf("__MB_") === 0) {
    status("Missing person id.", true);
    return;
  }
  if (window.MBNarrativeField) {
    const notes = $("mb-edit-notes");
    if (notes) {
      window.MBNarrativeField.mount(notes, { speech: "convenience" });
    }
  }
  Promise.all([loadPeople(), reload()]).catch((err) => status(err.detail || String(err), true));
})();
