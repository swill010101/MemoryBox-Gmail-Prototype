/**
 * P2-I5 Person Explorer chrome — header / About / Family / Learn + secondary drawers.
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

  // Paint header immediately from URL / boot config (profile fetch fills details)
  (function seedHeader() {
    const bootName = (cfg.displayName || "").trim();
    if (bootName) {
      const nameEl = document.getElementById("mb-person-name");
      if (nameEl) nameEl.textContent = bootName;
      const portrait = document.getElementById("mb-person-portrait");
      if (portrait) {
        portrait.textContent = (bootName.charAt(0) || "?").toUpperCase();
      }
      const label = document.getElementById("mb-person-ask-label");
      if (label) label.textContent = "Ask about " + bootName.split(/\s+/)[0];
      document.title = "MemoryBox — " + bootName;
      document.querySelectorAll("[data-person-first]").forEach((el) => {
        el.textContent = bootName.split(/\s+/)[0] || "them";
      });
    } else {
      const nameEl = document.getElementById("mb-person-name");
      if (nameEl) nameEl.textContent = "Loading…";
    }
  })();

  let cached = {
    person: null,
    profile: null,
    faces: [],
    appearances: [],
    family: [],
  };

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

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function adminHref() {
    return (
      "/people/ui?admin=1&person=" + encodeURIComponent(cfg.personId || "")
    );
  }

  function openDrawer(title, html) {
    const drawer = document.getElementById("mb-person-drawer");
    document.getElementById("mb-person-drawer-title").textContent = title;
    document.getElementById("mb-person-drawer-body").innerHTML = html;
    const admin = document.getElementById("mb-person-drawer-admin");
    if (admin) admin.href = adminHref();
    drawer.hidden = false;
  }

  function closeDrawer() {
    document.getElementById("mb-person-drawer").hidden = true;
  }

  function renderAboutDrawer() {
    const p = cached.profile || {};
    const facts = p.facts || [];
    const aliases = p.aliases || [];
    const birth = facts.find((f) => f.fact_kind === "birth_date");
    const death = facts.find((f) => f.fact_kind === "death_date");
    const notes = facts.filter((f) => f.fact_kind === "note");
    const name = cfg.displayName || "Person";
    const aliasText = aliases
      .map((a) => a.alias_text || a.value || a.alias)
      .filter(Boolean)
      .join(", ");
    let html = "";
    html +=
      '<section class="mb-person-sec"><h3>Identity</h3><ul>' +
      "<li>Full name: " +
      escapeHtml(name) +
      "</li>" +
      (aliasText
        ? "<li>Also known as: " + escapeHtml(aliasText) + "</li>"
        : "<li>No alternate names recorded.</li>") +
      "</ul></section>";
    html +=
      '<section class="mb-person-sec"><h3>Life</h3><ul>' +
      "<li>Born: " +
      escapeHtml((birth && birth.value_date) || "Not recorded") +
      "</li>" +
      "<li>Died: " +
      escapeHtml((death && death.value_date) || "Not recorded") +
      "</li></ul></section>";
    html +=
      '<section class="mb-person-sec"><h3>Family</h3><ul>' +
      (cached.family.length
        ? cached.family
            .map(
              (f) =>
                "<li>" +
                escapeHtml(f.name) +
                " — " +
                escapeHtml(f.role) +
                "</li>"
            )
            .join("")
        : "<li>No relationships recorded yet.</li>") +
      "</ul></section>";
    html +=
      '<section class="mb-person-sec"><h3>Places</h3><ul><li>Important Places can be linked as they are confirmed. No latitude/longitude shown here.</li></ul></section>';
    html +=
      '<section class="mb-person-sec"><h3>Notes</h3><ul>' +
      (notes.length
        ? notes
            .map((n) => "<li>" + escapeHtml(n.value_text || n.note || "") + "</li>")
            .join("")
        : "<li>No owner notes yet.</li>") +
      "</ul></section>";
    openDrawer("About " + firstName(name), html);
  }

  function renderFamilyDrawer() {
    const name = cfg.displayName || "Person";
    let html =
      '<p class="mb-person-empty">Relationships should feel like family, not graph administration.</p>';
    if (!cached.family.length) {
      html +=
        '<p class="mb-person-empty">No family relationships recorded yet. Use Add family to teach MemoryBox.</p>';
    } else {
      html += '<div class="mb-person-family-row" style="justify-content:flex-start">';
      for (const f of cached.family) {
        html +=
          '<a class="mb-person-fam" href="/people/ui?person=' +
          encodeURIComponent(f.id) +
          '"><div class="mb-person-fam-av">' +
          escapeHtml(initial(f.name)) +
          '</div><div class="mb-person-fam-label">' +
          escapeHtml(f.name) +
          '</div><div class="mb-person-fam-role">' +
          escapeHtml(f.role) +
          "</div></a>";
      }
      html += "</div>";
    }
    html +=
      '<p style="margin-top:1rem"><a class="mb-person-panel-link" href="' +
      adminHref() +
      '#relationships">Correct / add relationships</a></p>';
    openDrawer("Family — " + firstName(name), html);
  }

  function renderLearnDrawer() {
    const name = cfg.displayName || "Person";
    const faces = cached.faces || [];
    const apps = cached.appearances || [];
    let html = "";
    html +=
      '<section class="mb-person-sec"><h3>Face</h3>' +
      (faces.length
        ? faces
            .slice(0, 24)
            .map((f) => {
              const src =
                f.thumb_url ||
                f.media_url ||
                f.preview_url ||
                f.image_url ||
                "";
              const label =
                f.label ||
                f.source ||
                f.external_id ||
                f.provider_key ||
                "Face example";
              const trust = f.status || f.confirmation_state || f.trust || "";
              return (
                '<div class="mb-person-learn-item">' +
                (src
                  ? '<img class="mb-person-learn-thumb" src="' +
                    escapeHtml(src) +
                    '" alt="" />'
                  : '<div class="mb-person-learn-thumb"></div>') +
                '<div class="mb-person-learn-meta"><strong>' +
                escapeHtml(String(label).slice(0, 80)) +
                "</strong>" +
                escapeHtml(trust || "Confirmed / learning evidence") +
                "</div></div>"
              );
            })
            .join("")
        : '<p class="mb-person-empty">No confirmed face examples yet. Identify a face while viewing a photo.</p>') +
      "</section>";

    html +=
      '<section class="mb-person-sec"><h3>Video appearances</h3>' +
      (apps.length
        ? apps
            .slice(0, 24)
            .map((a) => {
              const t0 = a.start_sec != null ? Number(a.start_sec) : 0;
              const vid = a.video_external_id || a.external_id || "";
              const href = vid
                ? "/review/ui?video=" +
                  encodeURIComponent(vid) +
                  "&t=" +
                  encodeURIComponent(String(t0))
                : "#";
              const poster =
                a.poster_url ||
                (vid
                  ? "/library/media/video-poster?video=" +
                    encodeURIComponent(vid) +
                    "&t=" +
                    encodeURIComponent(t0.toFixed(3))
                  : "");
              return (
                '<a class="mb-person-learn-item" href="' +
                escapeHtml(href) +
                '">' +
                (poster
                  ? '<img class="mb-person-learn-thumb" src="' +
                    escapeHtml(poster) +
                    '" alt="" />'
                  : '<div class="mb-person-learn-thumb"></div>') +
                '<div class="mb-person-learn-meta"><strong>Moment @ ' +
                t0.toFixed(1) +
                "s</strong>" +
                escapeHtml(a.label || a.method || "Video appearance") +
                "</div></a>"
              );
            })
            .join("")
        : '<p class="mb-person-empty">No video appearances yet.</p>') +
      "</section>";

    html +=
      '<section class="mb-person-sec"><h3>Voice</h3><p class="mb-person-empty">No confirmed voice examples yet. Identify while listening to audio or video.</p></section>';
    html +=
      '<section class="mb-person-sec"><h3>Identity sources</h3><ul>' +
      "<li>Owner confirmation</li><li>Faces</li><li>Video appearances</li>" +
      "<li>Provider People mappings (Immich remains a provider identity)</li>" +
      "<li>Relationships, Stories, aliases when recorded</li>" +
      '</ul><p class="mb-person-empty">Sources stay distinguishable — not flattened into one unexplained score.</p></section>';
    html +=
      '<p style="margin-top:0.75rem"><a class="mb-person-panel-link" href="/review/ui">Open Review</a> to correct face, video, or voice on evidence. Compact Learn stays honest; deep correction lives in Review.</p>';

    openDrawer("Learn about " + firstName(name), html);
  }

  async function loadProfile() {
    const id = cfg.personId;
    const [personRes, profileRes, faceRes, appRes] = await Promise.all([
      fetch("/people/" + encodeURIComponent(id)),
      fetch("/people/" + encodeURIComponent(id) + "/profile"),
      fetch("/people/" + encodeURIComponent(id) + "/face-evidence").catch(
        () => null
      ),
      fetch("/people/" + encodeURIComponent(id) + "/appearances").catch(
        () => null
      ),
    ]);
    if (!personRes.ok) throw new Error("person " + personRes.status);
    const person = await personRes.json();
    const profile = profileRes.ok ? await profileRes.json() : {};
    const facesPayload = faceRes && faceRes.ok ? await faceRes.json() : {};
    const appsPayload = appRes && appRes.ok ? await appRes.json() : {};

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
    portrait.style.backgroundImage = "";

    const facts = profile.facts || [];
    const birth = facts.find((f) => f.fact_kind === "birth_date");
    const death = facts.find((f) => f.fact_kind === "death_date");
    const birthY =
      birth && birth.value_date ? String(birth.value_date).slice(0, 4) : "";
    const deathY =
      death && death.value_date ? String(death.value_date).slice(0, 4) : "";
    const life =
      birthY && deathY
        ? birthY + "–" + deathY
        : birthY
          ? "b. " + birthY
          : deathY
            ? "d. " + deathY
            : "";

    let rel = "";
    const derived =
      (profile.relationships && profile.relationships.derived_edges) || [];
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
    cached.family = family;
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

    const faceList =
      facesPayload.evidence ||
      facesPayload.items ||
      facesPayload.faces ||
      [];
    const appList =
      appsPayload.appearances ||
      appsPayload.items ||
      appsPayload.moments ||
      [];
    cached.faces = Array.isArray(faceList) ? faceList : [];
    cached.appearances = Array.isArray(appList) ? appList : [];
    cached.person = person;
    cached.profile = profile;

    const faceThumb = cached.faces
      .map((f) => {
        const meta = f.exemplar_meta_json || f.exemplar_meta || {};
        const asset =
          f.source_asset_id ||
          (meta && (meta.source_asset_id || meta.assetId)) ||
          "";
        return (
          f.thumb_url ||
          f.media_url ||
          f.preview_url ||
          f.image_url ||
          (asset ? "/library/media/photo/" + asset : "")
        );
      })
      .find(Boolean);
    if (faceThumb) {
      portrait.textContent = "";
      portrait.style.backgroundImage = "url(" + JSON.stringify(faceThumb) + ")";
    } else {
      // Fall back to Immich provider projection thumbnail when present
      try {
        const projRes = await fetch(
          "/people/" + encodeURIComponent(id) + "/provider-projection"
        );
        if (projRes.ok) {
          const proj = await projRes.json();
          const immich =
            (proj.by_provider && proj.by_provider.immich) ||
            proj.immich ||
            [];
          const firstImmich = Array.isArray(immich) ? immich[0] : null;
          // Prefer an Immich face asset from evidence path; else leave initial
          if (firstImmich && typeof firstImmich === "object" && firstImmich.thumb_url) {
            portrait.textContent = "";
            portrait.style.backgroundImage =
              "url(" + JSON.stringify(firstImmich.thumb_url) + ")";
          }
        }
      } catch (_) {
        /* keep initial */
      }
    }

    const faceN = cached.faces.length;
    const appN = cached.appearances.length;
    document.getElementById("mb-person-learn-stats").innerHTML =
      "<li>" +
      faceN +
      " confirmed face" +
      (faceN === 1 ? "" : "s") +
      "</li><li>" +
      appN +
      " video appearance" +
      (appN === 1 ? "" : "s") +
      "</li><li>0 voice examples</li>";

    document.getElementById("mb-person-summary").textContent =
      "Memories load below — Ask, Gallery, Timeline and Map stay on this Person.";

    const edit = document.getElementById("mb-person-edit");
    if (edit) {
      edit.href = adminHref();
      edit.onclick = (e) => {
        e.preventDefault();
        renderAboutDrawer();
      };
    }
    const aboutEdit = document.getElementById("mb-person-about-edit");
    if (aboutEdit) aboutEdit.onclick = () => renderAboutDrawer();
    const famAdd = document.getElementById("mb-person-family-add");
    if (famAdd) {
      famAdd.onclick = () => {
        window.location.href = adminHref() + "#relationships";
      };
    }
    const famOpen = document.getElementById("mb-person-family-open");
    if (famOpen) famOpen.onclick = () => renderFamilyDrawer();
    const learnEx = document.getElementById("mb-person-learn-explore");
    if (learnEx) learnEx.onclick = () => renderLearnDrawer();
    const learnHeader = document.getElementById("mb-person-learn-link");
    if (learnHeader) {
      learnHeader.onclick = (e) => {
        e.preventDefault();
        renderLearnDrawer();
      };
    }
    const relHeader = document.getElementById("mb-person-relationships");
    if (relHeader) {
      relHeader.onclick = (e) => {
        e.preventDefault();
        renderFamilyDrawer();
      };
    }

    window.dispatchEvent(
      new CustomEvent("mb-person-ready", {
        detail: { personId: id, displayName: name },
      })
    );
    if (window.mbShell && window.mbShell.setActivePerson) {
      window.mbShell.setActivePerson({ id: id, name: name });
      window.mbShell.refreshPeopleNavLinks();
    }
  }

  document
    .getElementById("mb-person-drawer-close")
    .addEventListener("click", closeDrawer);
  document.getElementById("mb-person-drawer").addEventListener("click", (e) => {
    if (e.target.id === "mb-person-drawer") closeDrawer();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeDrawer();
  });

  document.querySelectorAll(".mb-person-mode").forEach((btn) => {
    btn.addEventListener("click", () => {
      const mode = btn.getAttribute("data-mode") === "all" ? "all" : "highlights";
      if (typeof window.mbPersonSetMemoryMode === "function") {
        window.mbPersonSetMemoryMode(mode);
      } else if (window.MB_PERSON_SURFACE) {
        window.MB_PERSON_SURFACE.memoryMode = mode;
      }
    });
  });
  document.querySelectorAll(".mb-person-view").forEach((btn) => {
    btn.addEventListener("click", () => {
      const view = btn.getAttribute("data-view") || "gallery";
      if (typeof window.mbExploreSetViewMode === "function") {
        window.mbExploreSetViewMode(view);
      }
    });
  });

  // Keep header summary honest after gallery loads
  const summaryEl = document.getElementById("mb-person-summary");
  const metaObs = new MutationObserver(() => {
    const meta = document.getElementById("mb-explore-meta");
    if (!meta || !summaryEl) return;
    const m = String(meta.textContent || "").match(/(\d+)\s+visible/i);
    if (m) {
      const n = m[1];
      summaryEl.textContent =
        n +
        " memor" +
        (n === "1" ? "y" : "ies") +
        " in the current view across photos, video, stories, communications and artifacts.";
    }
  });
  const meta = document.getElementById("mb-explore-meta");
  if (meta) metaObs.observe(meta, { childList: true, characterData: true, subtree: true });

  loadProfile().catch((err) => {
    const body = document.getElementById("mb-explore-curator-body");
    if (body) body.textContent = "Could not load Person: " + err;
  });
})();
