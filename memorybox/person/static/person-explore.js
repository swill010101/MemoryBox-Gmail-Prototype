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

  function editHref() {
    return "/people/" + encodeURIComponent(cfg.personId || "") + "/edit";
  }

  function formatLifeDate(fact) {
    if (!fact) return "";
    if (fact.display_date) return String(fact.display_date);
    const prec = String(fact.date_precision || "day").toLowerCase();
    const raw = String(fact.value_date || "").trim();
    if (!raw) return "";
    const y = raw.slice(0, 4);
    const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
    if (prec === "year") return y;
    const mi = parseInt(raw.slice(5, 7), 10);
    const month = mi >= 1 && mi <= 12 ? months[mi - 1] : "";
    if (prec === "month") return (month + " " + y).trim();
    const d = parseInt(raw.slice(8, 10), 10);
    if (month && d) return month + " " + d + ", " + y;
    return raw.slice(0, 10);
  }

  function firstAlias(aliases) {
    const list = aliases || [];
    const nick = list.find((a) => a.alias_kind === "nickname" && a.alias_text);
    if (nick) return nick.alias_text;
    const alt = list.find((a) => a.alias_text);
    return alt ? alt.alias_text : "";
  }

  function openDrawer(title, html) {
    const drawer = document.getElementById("mb-person-drawer");
    document.getElementById("mb-person-drawer-title").textContent = title;
    document.getElementById("mb-person-drawer-body").innerHTML = html;
    const admin = document.getElementById("mb-person-drawer-admin");
    if (admin) admin.href = editHref();
    drawer.hidden = false;
  }

  function closeDrawer() {
    document.getElementById("mb-person-drawer").hidden = true;
  }

  function groupFamily(profile) {
    const rel = (profile && profile.relationships) || {};
    const groups = [
      ["parents", "Parents"],
      ["siblings", "Siblings"],
      ["spouse_partner", "Spouse or partner"],
      ["children", "Children"],
    ];
    const direct = rel.direct || {};
    const lines = [];
    groups.forEach(([key, label]) => {
      const hits = direct[key] || [];
      hits.forEach((h) => {
        const derived = h.derived || h.is_derived;
        lines.push(
          label +
            ": " +
            (h.display_name || h.to_display_name || "Person") +
            " — " +
            (h.label || h.role_kind || "") +
            (derived ? " (Derived)" : "")
        );
      });
    });
    const ext = rel.extended || [];
    (Array.isArray(ext) ? ext : Object.values(ext).flat()).forEach((h) => {
      lines.push(
        "Other family: " +
          (h.display_name || "Person") +
          " — " +
          (h.label || h.role_kind || "") +
          " (Derived)"
      );
    });
    if (!lines.length && cached.family.length) {
      return cached.family.map((f) => f.name + " — " + f.role);
    }
    return lines;
  }

  function renderAboutDrawer() {
    const p = cached.profile || {};
    const idn = p.identity || {};
    const facts = p.facts || [];
    const aliases = p.aliases || [];
    const birth = facts.find((f) => f.fact_kind === "birth_date");
    const death = facts.find((f) => f.fact_kind === "death_date");
    const notes = facts.filter((f) => f.fact_kind === "note");
    const name = cfg.displayName || idn.display_name || "Person";
    const aliasText = aliases
      .map((a) => a.alias_text || a.value || a.alias)
      .filter(Boolean)
      .join(", ");
    const maps = idn.provider_mappings || [];
    let html = "";
    html +=
      '<section class="mb-person-sec"><h3>Identity</h3><ul>' +
      "<li>Full name: " +
      escapeHtml(name) +
      "</li>" +
      (aliasText
        ? "<li>Also known as: " + escapeHtml(aliasText) + "</li>"
        : "<li>No alternate names recorded.</li>") +
      "<li>MemoryBox Person: " +
      escapeHtml(idn.id || cfg.personId || "") +
      "</li>" +
      "<li>Status: " +
      escapeHtml(idn.status || "—") +
      "</li></ul></section>";
    html +=
      '<section class="mb-person-sec"><h3>Life</h3><ul>' +
      "<li>Born: " +
      escapeHtml(formatLifeDate(birth) || "Not recorded") +
      "</li>" +
      "<li>Died: " +
      escapeHtml(formatLifeDate(death) || "Not recorded") +
      "</li></ul></section>";
    html +=
      '<section class="mb-person-sec"><h3>Notes</h3><ul>' +
      (notes.length
        ? notes
            .map((n) => "<li>" + escapeHtml(n.value_text || n.note || "") + "</li>")
            .join("")
        : "<li>No owner notes yet.</li>") +
      "</ul></section>";
    const fam = groupFamily(p);
    html +=
      '<section class="mb-person-sec"><h3>Family</h3><ul>' +
      (fam.length
        ? fam.map((line) => "<li>" + escapeHtml(line) + "</li>").join("")
        : "<li>No relationships recorded yet.</li>") +
      "</ul></section>";
    const contacts = p.contacts || [];
    html +=
      '<section class="mb-person-sec"><h3>Confirmed contacts</h3><ul>' +
      (contacts.length
        ? contacts
            .map((c) => {
              const kind = escapeHtml(c.contact_kind || "contact");
              const val = escapeHtml(c.value_text || "");
              return "<li>" + kind + ": <b>" + val + "</b> (confirmed)</li>";
            })
            .join("")
        : "<li>No confirmed phone or email yet.</li>") +
      "</ul></section>";
    html +=
      '<section class="mb-person-sec"><h3>Places</h3><ul><li>No important place recorded yet. MemoryBox will not invent a location.</li></ul></section>';
    const confirmed = maps.filter((m) => m.confirmed_at);
    html +=
      '<section class="mb-person-sec"><h3>Provenance and confirmation</h3><ul>' +
      "<li>Canonical MemoryBox Person · status " +
      escapeHtml(idn.status || "—") +
      (p.is_canonical_owner ? " · this is you" : "") +
      "</li>" +
      (maps.length
        ? "<li>Linked provider identities: " +
          escapeHtml(
            maps
              .map((m) => (m.provider_key || "") + " " + (m.label || m.external_id || ""))
              .join("; ")
          ) +
          "</li>"
        : "<li>No provider identities linked.</li>") +
      "<li>Confirmed mappings: " +
      confirmed.length +
      "</li></ul></section>";
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
      editHref() +
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
    const [personRes, profileRes, faceRes, appRes, statsRes] = await Promise.all([
      fetch("/people/" + encodeURIComponent(id)),
      fetch("/people/" + encodeURIComponent(id) + "/profile"),
      fetch("/people/" + encodeURIComponent(id) + "/face-evidence").catch(
        () => null
      ),
      fetch("/people/" + encodeURIComponent(id) + "/appearances").catch(
        () => null
      ),
      fetch("/people/" + encodeURIComponent(id) + "/learn-stats").catch(
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
    const statsPayload = statsRes && statsRes.ok ? await statsRes.json() : {};

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
      if (curatorAv) {
        curatorAv.textContent = "";
        curatorAv.style.backgroundImage = css;
        curatorAv.classList.add("has-photo");
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
    // Immich preferred person thumb only — never race in a face-evidence crop.
    const portraitUrl =
      (personPayload.portrait_url ||
        "/people/" + encodeURIComponent(id) + "/portrait") +
      (personPayload.person && personPayload.person.updated_at
        ? "?v=" + encodeURIComponent(String(personPayload.person.updated_at))
        : "?v=" + Date.now());
    const probe = new Image();
    probe.onload = () => applyPortraitUrl(portraitUrl);
    probe.onerror = () => {
      /* keep letter; do not overwrite with a random library face */
    };
    probe.src = portraitUrl;

    const facts = profile.facts || [];
    const birth = facts.find((f) => f.fact_kind === "birth_date");
    const death = facts.find((f) => f.fact_kind === "death_date");
    const aka = firstAlias(profile.aliases || []);
    const akaEl = document.getElementById("mb-person-aka");
    if (akaEl) {
      if (aka) {
        akaEl.hidden = false;
        akaEl.textContent = "Also known as " + aka;
      } else {
        akaEl.hidden = true;
        akaEl.textContent = "";
      }
    }
    const lifeBits = [];
    const born = formatLifeDate(birth);
    const died = formatLifeDate(death);
    if (born) lifeBits.push("Born " + born);
    if (died) lifeBits.push("Died " + died);
    const lifeEl = document.getElementById("mb-person-life-dates");
    if (lifeEl) lifeEl.textContent = lifeBits.join(" · ");

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
    const kinEl = document.getElementById("mb-person-kin");
    if (kinEl) {
      kinEl.textContent = rel
        ? "Relationship to you: " + rel.charAt(0).toUpperCase() + rel.slice(1)
        : "";
    }
    const placeEl = document.getElementById("mb-person-place");
    if (placeEl) {
      placeEl.hidden = true;
      placeEl.textContent = "";
    }
    const teaser = document.getElementById("mb-person-about-teaser");
    if (teaser) {
      const t = [];
      if (rel) t.push(rel.charAt(0).toUpperCase() + rel.slice(1));
      if (lifeBits.length) t.push(lifeBits.join(" · "));
      teaser.textContent = t.length
        ? t.join(" · ") + ". Open About for the full read-only record."
        : "Open About for the full read-only record.";
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

    const faceN = Number(statsPayload.immich_photos || cached.faces.length) || 0;
    const appN = Number(statsPayload.immich_videos || cached.appearances.length) || 0;
    const faceLabel = statsPayload.immich_photos != null
      ? " Immich photo" + (faceN === 1 ? "" : "s")
      : " confirmed face" + (faceN === 1 ? "" : "s");
    const vidLabel = statsPayload.immich_videos != null
      ? " Immich video" + (appN === 1 ? "" : "s")
      : " video appearance" + (appN === 1 ? "" : "s");
    document.getElementById("mb-person-learn-stats").innerHTML =
      "<li>" +
      faceN +
      faceLabel +
      "</li><li>" +
      appN +
      vidLabel +
      "</li><li>0 voice examples</li>";

    const edit = document.getElementById("mb-person-edit");
    if (edit) {
      edit.href = editHref();
    }
    const aboutBtn = document.getElementById("mb-person-about");
    if (aboutBtn) aboutBtn.onclick = () => renderAboutDrawer();
    const aboutCard = document.getElementById("mb-person-about-card");
    if (aboutCard) aboutCard.onclick = () => renderAboutDrawer();
    const famAdd = document.getElementById("mb-person-family-add");
    if (famAdd) {
      famAdd.onclick = () => {
        if (typeof window.mbOpenRelationshipsModal === "function") {
          window.mbOpenRelationshipsModal();
        }
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
        if (typeof window.mbOpenRelationshipsModal === "function") {
          window.mbOpenRelationshipsModal();
        } else {
          renderFamilyDrawer();
        }
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

  window.mbPersonSyncResults = function (info) {
    const data = info || {};
    const counts = data.counts || {};
    const total = Number(data.total || 0);
    const kindBits = [];
    const labels = [
      ["photo", "photos"],
      ["video", "videos"],
      ["story", "stories"],
      ["email", "emails"],
      ["text", "texts"],
      ["artifact", "artifacts"],
    ];
    labels.forEach(([k, lab]) => {
      const n = Number(counts[k] || 0);
      if (n) kindBits.push(n + " " + lab);
    });
    const totEl = document.getElementById("mb-person-memory-totals");
    if (totEl) {
      totEl.textContent =
        "Total memories: " +
        total +
        (kindBits.length ? " · " + kindBits.join(" · ") : "");
    }
    const rangeEl = document.getElementById("mb-person-result-range");
    const sumEl = document.getElementById("mb-person-result-summary");
    const range = String(data.rangeLabel || "").trim();
    const rangeText = range ? "In this view: " + range : "";
    if (rangeEl) {
      rangeEl.hidden = !rangeText;
      rangeEl.textContent = rangeText;
    }
    if (sumEl) {
      sumEl.hidden = !(rangeText || total);
      sumEl.textContent = rangeText
        ? rangeText + " · " + total + " visible"
        : total
          ? total + " visible in this view"
          : "";
    }
  };

  loadProfile().catch((err) => {
    const body = document.getElementById("mb-explore-curator-body");
    if (body) body.textContent = "Could not load Person: " + err;
  });
})();
