/**
 * P2-I5 Person Explorer chrome — header / About / Family / Learn.
 * Gallery, Timeline, Map, Ask, and Shared Evidence Viewer live in explore.js
 * with window.MB_PERSON_SURFACE pre-context (same shared exploration state).
 */
(function () {
  const cfg = window.MB_PERSON_SURFACE || {};
  if (!cfg.personId) {
    const body = document.getElementById("mb-explore-curator-body");
    if (body) {
      body.textContent =
        "Open a Person from People, or add ?person=<id> to this URL.";
    }
    return;
  }

  function firstName(name) {
    const n = String(name || "").trim();
    return n.split(/\s+/)[0] || "them";
  }

  function setFirstSpans(name) {
    document.querySelectorAll("[data-person-first]").forEach((el) => {
      el.textContent = firstName(name);
    });
  }

  function initial(name) {
    return (String(name || "?").trim().charAt(0) || "?").toUpperCase();
  }

  function roleLabel(edge) {
    return (
      edge.sot_role_kind ||
      edge.role_phrase ||
      edge.relationship_kind ||
      edge.participant_role ||
      "family"
    )
      .toString()
      .replace(/_/g, " ");
  }

  async function loadProfile() {
    const id = cfg.personId;
    const [personRes, profileRes, faceRes, appRes] = await Promise.all([
      fetch("/people/" + encodeURIComponent(id)),
      fetch("/people/" + encodeURIComponent(id) + "/profile"),
      fetch("/people/" + encodeURIComponent(id) + "/face-evidence").catch(() => null),
      fetch("/people/" + encodeURIComponent(id) + "/appearances").catch(() => null),
    ]);
    if (!personRes.ok) throw new Error("person " + personRes.status);
    const person = await personRes.json();
    const profile = profileRes.ok ? await profileRes.json() : {};
    const faces = faceRes && faceRes.ok ? await faceRes.json() : {};
    const apps = appRes && appRes.ok ? await appRes.json() : {};

    const name =
      person.display_name ||
      (profile.identity && profile.identity.display_name) ||
      cfg.displayName ||
      "Person";
    cfg.displayName = name;
    window.MB_PERSON_SURFACE.displayName = name;

    document.getElementById("mb-person-name").textContent = name;
    document.title = "MemoryBox — " + name;
    const label = document.getElementById("mb-person-ask-label");
    if (label) label.textContent = "Ask about " + firstName(name);
    setFirstSpans(name);

    const portrait = document.getElementById("mb-person-portrait");
    portrait.textContent = initial(name);

    const facts = profile.facts || [];
    const birth = facts.find((f) => f.fact_kind === "birth_date");
    const death = facts.find((f) => f.fact_kind === "death_date");
    const birthY = birth && birth.value_date ? String(birth.value_date).slice(0, 4) : "";
    const deathY = death && death.value_date ? String(death.value_date).slice(0, 4) : "";
    const life =
      birthY && deathY ? birthY + "–" + deathY : birthY ? "b. " + birthY : deathY ? "d. " + deathY : "";

    // Owner-relative relationship when present on derived edges
    let rel = "";
    const derived = (profile.relationships && profile.relationships.derived_edges) || [];
    const owner = profile.owner || {};
    if (owner.owner_person_id && derived.length) {
      const hit = derived.find(
        (e) =>
          e.from_person_id === owner.owner_person_id ||
          e.to_person_id === owner.owner_person_id
      );
      if (hit) rel = roleLabel(hit);
    }
    const subBits = [];
    if (rel) subBits.push(rel.charAt(0).toUpperCase() + rel.slice(1));
    if (life) subBits.push(life);
    document.getElementById("mb-person-sub").textContent =
      subBits.join(" · ") || "Canonical MemoryBox Person";

    const about = document.getElementById("mb-person-about-dl");
    about.innerHTML = "";
    function row(k, v) {
      if (!v) return;
      const dt = document.createElement("dt");
      dt.textContent = k;
      const dd = document.createElement("dd");
      dd.textContent = v;
      about.appendChild(dt);
      about.appendChild(dd);
    }
    row("Full name", name);
    row("Relationship", rel ? rel.charAt(0).toUpperCase() + rel.slice(1) : null);
    row("Born", birth && birth.value_date);
    row("Died", death && death.value_date);
    if (!about.children.length) {
      about.innerHTML =
        '<p class="mb-person-empty">No profile details recorded yet.</p>';
    }

    const familyRow = document.getElementById("mb-person-family-row");
    familyRow.innerHTML = "";
    const assertions =
      (profile.relationships && profile.relationships.assertions_sot) || [];
    const seen = new Set();
    const family = [];
    for (const a of assertions.concat(derived)) {
      const otherId =
        a.from_person_id === id
          ? a.to_person_id
          : a.to_person_id === id
            ? a.from_person_id
            : a.from_person_id || a.to_person_id;
      const otherName =
        a.from_person_id === id
          ? a.to_display_name || a.to_name
          : a.to_person_id === id
            ? a.from_display_name || a.from_name
            : a.from_display_name || a.display_name;
      if (!otherId || seen.has(otherId) || otherId === id) continue;
      seen.add(otherId);
      family.push({
        id: otherId,
        name: otherName || "Person",
        role: roleLabel(a),
      });
    }
    if (!family.length) {
      familyRow.innerHTML =
        '<p class="mb-person-empty">No family relationships recorded yet.</p>';
    } else {
      for (const f of family.slice(0, 8)) {
        const a = document.createElement("a");
        a.className = "mb-person-fam";
        a.href = "/people/ui?person=" + encodeURIComponent(f.id);
        a.innerHTML =
          '<div class="mb-person-fam-av">' +
          initial(f.name) +
          '</div><div class="mb-person-fam-label">' +
          escapeHtml(f.name.split(/\s+/)[0]) +
          '</div><div class="mb-person-fam-role">' +
          escapeHtml(f.role) +
          "</div>";
        familyRow.appendChild(a);
      }
    }

    const faceList = faces.evidence || faces.items || faces.faces || [];
    const faceN = Array.isArray(faceList) ? faceList.length : Number(faces.count || 0);
    const appList = apps.appearances || apps.items || apps.moments || [];
    const appN = Array.isArray(appList) ? appList.length : Number(apps.count || 0);
    const learn = document.getElementById("mb-person-learn-stats");
    learn.innerHTML =
      "<li>" +
      faceN +
      " confirmed face" +
      (faceN === 1 ? "" : "s") +
      "</li><li>" +
      appN +
      " video appearance" +
      (appN === 1 ? "" : "s") +
      "</li><li>0 voice examples</li>";

    const edit = document.getElementById("mb-person-edit");
    const aboutEdit = document.getElementById("mb-person-about-edit");
    const admin = "/people/ui?admin=1&person=" + encodeURIComponent(id);
    if (edit) edit.href = admin;
    if (aboutEdit) aboutEdit.href = admin;
    const famAdd = document.getElementById("mb-person-family-add");
    if (famAdd) famAdd.href = admin + "#relationships";
    const learnEx = document.getElementById("mb-person-learn-explore");
    if (learnEx) {
      learnEx.href =
        "/review/ui?person_id=" + encodeURIComponent(id) + "&person_name=" + encodeURIComponent(name);
    }

    // Notify explore.js person chrome is ready (name may have resolved).
    window.dispatchEvent(
      new CustomEvent("mb-person-ready", { detail: { personId: id, displayName: name } })
    );
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  // Highlights / All Memories + Gallery / Map (presentation only)
  document.querySelectorAll(".mb-person-mode").forEach((btn) => {
    btn.addEventListener("click", () => {
      const mode = btn.getAttribute("data-mode") || "all";
      window.MB_PERSON_SURFACE.memoryMode = mode;
      document.querySelectorAll(".mb-person-mode").forEach((b) => {
        const on = b === btn;
        b.classList.toggle("is-active", on);
        b.setAttribute("aria-selected", on ? "true" : "false");
      });
      if (typeof window.mbPersonSetMemoryMode === "function") {
        window.mbPersonSetMemoryMode(mode);
      }
    });
  });
  document.querySelectorAll(".mb-person-view").forEach((btn) => {
    btn.addEventListener("click", () => {
      const view = btn.getAttribute("data-view") || "gallery";
      document.querySelectorAll(".mb-person-view").forEach((b) => {
        b.classList.toggle("is-active", b === btn);
      });
      if (typeof window.mbExploreSetViewMode === "function") {
        window.mbExploreSetViewMode(view);
      }
    });
  });

  loadProfile().catch((err) => {
    const body = document.getElementById("mb-explore-curator-body");
    if (body) body.textContent = "Could not load Person: " + err;
  });
})();
