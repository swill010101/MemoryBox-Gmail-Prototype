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
      const curatorAv = document.getElementById("mb-explore-curator-avatar");
      if (curatorAv && !curatorAv.classList.contains("has-photo")) {
        curatorAv.textContent = (bootName.charAt(0) || "?").toUpperCase();
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

  function photoProxyAssetId(raw) {
    const s = String(raw || "").trim();
    if (!s) return "";
    const uuidRe =
      /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi;
    const path = s.replace(/\\/g, "/");
    if (
      !path.includes("/") &&
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(s)
    ) {
      return s;
    }
    const file = path.match(
      /([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.(jpe?g|webp|png|gif)$/i
    );
    if (file) return file[1];
    const all = path.match(uuidRe);
    return all && all.length ? all[all.length - 1] : "";
  }

  function photoProxyUrl(raw) {
    const id = photoProxyAssetId(raw);
    return id ? "/library/media/photo/" + id : "";
  }

  function applyPersonPortrait(el, personId) {
    if (!el || !personId) return;
    const url = "/people/" + encodeURIComponent(personId) + "/portrait?v=fam";
    const img = new Image();
    img.onload = () => {
      el.textContent = "";
      el.style.backgroundImage = "url(" + JSON.stringify(url) + ")";
      el.classList.add("has-photo");
    };
    img.src = url;
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
    const personPayload = await personRes.json();
    const person = personPayload.person || personPayload;
    const profilePayload = profileRes.ok ? await profileRes.json() : {};
    const profile = profilePayload.profile || profilePayload;
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
    const curatorAv = document.getElementById("mb-explore-curator-avatar");

    function applyPortraitUrl(url) {
      if (!url) return;
      const css = "url(" + JSON.stringify(url) + ")";
      if (portrait) {
        portrait.textContent = "";
        portrait.style.backgroundImage = css;
        portrait.classList.add("has-photo");
      }
      cfg.portraitUrl = url;
      if (window.MB_PERSON_SURFACE) window.MB_PERSON_SURFACE.portraitUrl = url;
    }

    function clearPortraitToInitial() {
      if (portrait) {
        portrait.classList.remove("has-photo");
        portrait.style.backgroundImage = "";
        portrait.textContent = initial(name);
      }
      if (curatorAv) {
        curatorAv.classList.remove("has-photo");
        curatorAv.style.backgroundImage = "";
        curatorAv.textContent = initial(name);
      }
    }

    clearPortraitToInitial();
    // Preferred Immich feature-face thumbnail (server: Immich first, then face evidence)
    const portraitUrl =
      (personPayload.portrait_url ||
        "/people/" + encodeURIComponent(id) + "/portrait") +
      (personPayload.person && personPayload.person.updated_at
        ? "?v=" + encodeURIComponent(String(personPayload.person.updated_at))
        : "?v=" + Date.now());
    const probe = new Image();
    probe.onload = () => applyPortraitUrl(portraitUrl);
    probe.onerror = () => {
      /* keep initial letter; optional evidence fallback below */
    };
    probe.src = portraitUrl;

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

    function namesList(rows) {
      return (rows || [])
        .map((h) => h.display_name || h.name)
        .filter(Boolean);
    }
    function familyHeadline() {
      const rels = (profile.relationships || {});
      const direct = rels.direct || {};
      const spouses = direct.spouse_partner || [];
      const children = direct.children || [];
      const parents = direct.parents || [];
      const siblings = direct.siblings || [];
      const ownerId = (profile.owner && profile.owner.owner_person_id) || "";
      if (ownerId && ownerId !== id) {
        const groups = [
          ["spouse_partner", "Spouse of"],
          ["parents", null],
          ["children", null],
          ["siblings", "Sibling of"],
        ];
        for (const [g, prefix] of groups) {
          const hit = (direct[g] || []).find((h) => h.person_id === ownerId);
          if (!hit) continue;
          const other = hit.display_name || "them";
          if (prefix) return prefix + " " + other;
          if (g === "parents")
            return (hit.label || "Child") + " of " + other;
          if (g === "children")
            return (hit.label === "Child" ? "Parent of " : (hit.label || "Related") + " of ") + other;
          return (hit.label || "Related") + " of " + other;
        }
      }
      if (spouses.length)
        return "Spouse of " + namesList(spouses).join(", ");
      if (children.length) {
        const lab =
          children.some((c) => /father/i.test(c.role_kind || ""))
            ? "Father of "
            : children.some((c) => /mother/i.test(c.role_kind || ""))
              ? "Mother of "
              : "Parent of ";
        return lab + namesList(children).join(", ");
      }
      if (parents.length) return "Child of " + namesList(parents).join(", ");
      if (siblings.length) return "Sibling of " + namesList(siblings).join(", ");
      return "";
    }
    const rel = familyHeadline();
    const subBits = [];
    if (rel) subBits.push(rel);
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
    const spouses = (profile.relationships && profile.relationships.direct && profile.relationships.direct.spouse_partner) || [];
    const children = (profile.relationships && profile.relationships.direct && profile.relationships.direct.children) || [];
    const parents = (profile.relationships && profile.relationships.direct && profile.relationships.direct.parents) || [];
    const extendedKids = ((profile.relationships && profile.relationships.extended) || []).filter(
      (h) => (h.role_kind || "") === "child_of" || (h.group || "") === "extended" && /child/i.test(h.label || "")
    );
    if (spouses.length) row("Spouse of", namesList(spouses).join(", "));
    const childNames = namesList(children).concat(
      namesList(extendedKids).filter((n) => namesList(children).indexOf(n) < 0)
    );
    if (childNames.length) row("Parent of", childNames.join(", "));
    if (parents.length) row("Child of", namesList(parents).join(", "));
    row("Born", birth && birth.value_date);
    row("Died", death && death.value_date);
    if (!about.children.length) {
      about.innerHTML =
        '<p class="mb-person-empty">No profile details recorded yet.</p>';
    }

    const familyRow = document.getElementById("mb-person-family-row");
    familyRow.innerHTML = "";
    const seen = new Set();
    const family = [];
    function pushHit(h, derived) {
      const otherId = h.person_id;
      const otherName = h.display_name || h.name || "Person";
      if (!otherId || seen.has(otherId) || otherId === id) return;
      seen.add(otherId);
      family.push({
        id: otherId,
        name: otherName,
        role: (h.label || roleLabel(h) || "family").toString(),
        derived: Boolean(derived),
      });
    }
    const direct = (profile.relationships && profile.relationships.direct) || {};
    ["parents", "siblings", "spouse_partner", "children"].forEach((g) => {
      (direct[g] || []).forEach((h) => pushHit(h, false));
    });
    ((profile.relationships && profile.relationships.extended) || []).forEach((h) =>
      pushHit(h, true)
    );
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
          '<div class="mb-person-fam-av" data-portrait="' +
          encodeURIComponent(f.id) +
          '">' +
          initial(f.name) +
          '</div><div class="mb-person-fam-label">' +
          escapeHtml(f.name.split(/\s+/)[0]) +
          '</div><div class="mb-person-fam-role">' +
          escapeHtml(f.derived ? "Derived · " + f.role : f.role) +
          "</div>";
        familyRow.appendChild(a);
        applyPersonPortrait(
          a.querySelector(".mb-person-fam-av"),
          f.id
        );
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
        const fromAsset = photoProxyUrl(asset);
        const existing =
          f.thumb_url || f.media_url || f.preview_url || f.image_url || "";
        if (existing && existing.indexOf("/library/media/photo//") === 0) {
          return fromAsset;
        }
        if (existing && existing.indexOf("/data/thumbs/") !== -1) {
          return fromAsset || photoProxyUrl(existing);
        }
        return existing || fromAsset;
      })
      .find(Boolean);
    // Only use face-evidence thumbs if Immich preferred portrait did not load
    if (faceThumb && !(portrait && portrait.classList.contains("has-photo"))) {
      const fb = new Image();
      fb.onload = () => applyPortraitUrl(faceThumb);
      fb.src = faceThumb;
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
