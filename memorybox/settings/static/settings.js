(function () {
  const form = document.getElementById("mb-set-video-root-form");
  const input = document.getElementById("mb-set-video-root");
  const meta = document.getElementById("mb-set-video-root-meta");
  const status = document.getElementById("mb-set-video-root-status");
  const clearBtn = document.getElementById("mb-set-video-root-clear");
  if (!form || !input) return;

  function setStatus(text, kind) {
    if (!status) return;
    status.textContent = text || "";
    status.classList.toggle("is-ok", kind === "ok");
    status.classList.toggle("is-err", kind === "err");
  }

  function applyPayload(data) {
    const effective = data.effective_root || "";
    const stored = data.stored_root || data.sidecar_root || "";
    input.value = stored || effective;
    const bits = [];
    bits.push("In use: " + (effective || "(unset)"));
    bits.push("source " + (data.source || "unset"));
    if (data.reachable === true) bits.push("folder reachable");
    if (data.reachable === false && effective) bits.push("folder not reachable from this serve process");
    if (data.env_root && data.settings_overrides_env) {
      bits.push("env default " + data.env_root + " is overridden");
    } else if (data.env_root) {
      bits.push("env default " + data.env_root);
    }
    if (meta) meta.textContent = bits.join(" · ");
  }

  async function load() {
    setStatus("");
    try {
      const res = await fetch("/settings/video-media-root", { headers: { Accept: "application/json" } });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || res.statusText);
      applyPayload(data);
    } catch (err) {
      if (meta) meta.textContent = "Could not load video path.";
      setStatus(String(err), "err");
    }
  }

  async function save(path) {
    setStatus("Saving…");
    try {
      const res = await fetch("/settings/video-media-root", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ path: path || "" }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || res.statusText);
      applyPayload(data);
      setStatus(
        data.saved_root
          ? "Saved. Video worker uses this path on the next scan."
          : "Cleared. Falling back to MEMORYBOX_VIDEO_MEDIA_ROOT if set.",
        "ok"
      );
    } catch (err) {
      setStatus(String(err), "err");
    }
  }

  form.addEventListener("submit", (ev) => {
    ev.preventDefault();
    save(input.value);
  });
  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      input.value = "";
      save("");
    });
  }
  load();
})();
