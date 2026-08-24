/**
 * P2-I10A.2 shared narrative field.
 * MBNarrativeField.mount(textarea, { speech: "off"|"convenience"|"authored-memory", autoStart, onChange })
 */
(function (global) {
  const SILENCE_MS = 30000;
  const SILENCE_FLOOR = 0.025;
  const HEARD_FLOOR = 0.02;

  function insertAtCursor(ta, text) {
    const value = ta.value || "";
    let start = typeof ta.selectionStart === "number" ? ta.selectionStart : value.length;
    let end = typeof ta.selectionEnd === "number" ? ta.selectionEnd : start;
    if (start !== end) {
      start = end;
    }
    const before = value.slice(0, start);
    const after = value.slice(start);
    const glueLeft = before && !/\s$/.test(before) ? " " : "";
    const glueRight = after && !/^\s/.test(after) ? " " : "";
    const chunk = glueLeft + text + glueRight;
    ta.value = before + chunk + after;
    const caret = (before + chunk).length;
    try {
      ta.setSelectionRange(caret, caret);
    } catch (_) {}
    return { start: before.length, end: caret };
  }

  function pickMime() {
    const candidates = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];
    for (let i = 0; i < candidates.length; i++) {
      if (global.MediaRecorder && MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(candidates[i])) {
        return candidates[i];
      }
    }
    return "";
  }

  function formatTime(sec) {
    const n = Math.max(0, Math.round(Number(sec) || 0));
    const m = Math.floor(n / 60);
    const s = n % 60;
    return m + ":" + String(s).padStart(2, "0");
  }

  function familyError(kind) {
    if (kind === "permission") {
      return "MemoryBox couldn't use the microphone. You can still type, and you can try again.";
    }
    if (kind === "stt") {
      return "Couldn't turn that into words. You can still listen, type, and save.";
    }
    if (kind === "quiet") {
      return "MemoryBox didn't hear much. Check the microphone, then try again or type.";
    }
    if (kind === "insecure") {
      return "This page can't use the microphone here. You can still type.";
    }
    return "Recording didn't work. You can still type.";
  }

  function mount(textarea, opts) {
    opts = opts || {};
    if (!textarea || textarea.nodeName !== "TEXTAREA") {
      throw new Error("MBNarrativeField.mount expects a textarea");
    }
    if (textarea._mbNarrative) {
      textarea._mbNarrative.destroy();
    }
    const speech = opts.speech || "off";
    const wrap = document.createElement("div");
    wrap.className = "mb-nf";
    wrap.dataset.mbNarrativeField = "1";
    wrap.dataset.mbSpeech = speech;
    textarea.parentNode.insertBefore(wrap, textarea);
    wrap.appendChild(textarea);

    const chrome = document.createElement("div");
    chrome.className = "mb-nf-chrome";
    wrap.appendChild(chrome);

    const api = {
      speech: speech,
      getValue: function () { return textarea.value; },
      setValue: function (v) {
        textarea.value = v || "";
        if (opts.onChange) opts.onChange();
      },
      getCommit: function () { return commitSnapshot(); },
      consumeCommit: function () { clearPending(false); },
      discardUnsaved: function () { return discardPending(true); },
      start: function () { return startRecording(); },
      restoreCommit: function (commit) { restoreCommit(commit); },
      destroy: function () { teardown(); },
    };
    textarea._mbNarrative = api;

    if (speech === "off") {
      return api;
    }

    let mode = "ready";
    let recorder = null;
    let stream = null;
    let meterStream = null;
    let chunks = [];
    let mime = "";
    let audioCtx = null;
    let analyser = null;
    let meterTimer = null;
    let silenceStarted = 0;
    let silencePrompted = false;
    let snapshotBeforeTake = "";
    let recStartedAt = 0;
    let pausedMs = 0;
    let pauseAt = 0;
    let peakRms = 0;
    let trackLabel = "";
    let pending = emptyPending();
    let playSource = null;
    let playCtx = null;
    let playTimer = null;
    let playOffset = 0;
    let playStartedAt = 0;
    let playing = false;

    function emptyPending() {
      return {
        audio_id: null,
        audio_uri: null,
        blobUrl: null,
        blob: null,
        buffer: null,
        durationSec: 0,
        peakRms: 0,
        sttText: "",
        speech_user_edited: false,
        speech_captured_at: null,
      };
    }

    function emit() {
      if (opts.onChange) opts.onChange();
      try {
        textarea.dispatchEvent(new Event("input", { bubbles: true }));
      } catch (_) {}
    }

    function commitSnapshot() {
      if (speech !== "authored-memory") return {};
      if (!pending.audio_uri) return {};
      return {
        audio_id: pending.audio_id,
        audio_uri: pending.audio_uri,
        speech_origin: "speech",
        speech_user_edited: pending.speech_user_edited,
        speech_captured_at: pending.speech_captured_at,
        durationSec: pending.durationSec,
      };
    }

    function elapsedSec() {
      if (!recStartedAt) return 0;
      let ms = Date.now() - recStartedAt - pausedMs;
      if (pauseAt) ms -= Date.now() - pauseAt;
      return Math.max(0, ms / 1000);
    }

    function stopMeter() {
      if (meterTimer) {
        clearInterval(meterTimer);
        meterTimer = null;
      }
      silenceStarted = 0;
    }

    function stopPlayback() {
      playing = false;
      playOffset = 0;
      if (playTimer) {
        clearInterval(playTimer);
        playTimer = null;
      }
      if (playSource) {
        try { playSource.stop(); } catch (_) {}
        playSource = null;
      }
    }

    async function releaseStream() {
      stopMeter();
      if (analyser) {
        try { analyser.disconnect(); } catch (_) {}
        analyser = null;
      }
      if (audioCtx) {
        try { await audioCtx.close(); } catch (_) {}
        audioCtx = null;
      }
      if (meterStream) {
        meterStream.getTracks().forEach(function (t) { t.stop(); });
        meterStream = null;
      }
      if (stream) {
        stream.getTracks().forEach(function (t) { t.stop(); });
        stream = null;
      }
      recorder = null;
    }

    function revokeBlob() {
      if (pending.blobUrl) {
        try { URL.revokeObjectURL(pending.blobUrl); } catch (_) {}
        pending.blobUrl = null;
      }
    }

    async function deleteServerAudio(audioId) {
      if (!audioId) return;
      try {
        await fetch("/capture/audio/" + encodeURIComponent(audioId), { method: "DELETE" });
      } catch (_) {}
    }

    async function discardPending(deleteServer) {
      const id = pending.audio_id;
      stopPlayback();
      revokeBlob();
      pending = emptyPending();
      if (deleteServer) await deleteServerAudio(id);
      mode = "ready";
      renderChrome();
    }

    function clearPending(deleteServer) {
      discardPending(deleteServer);
    }

    function restoreCommit(commit) {
      if (speech !== "authored-memory" || !commit || !commit.audio_uri) return;
      pending.audio_id = commit.audio_id || null;
      pending.audio_uri = commit.audio_uri;
      pending.speech_user_edited = Boolean(commit.speech_user_edited);
      pending.speech_captured_at = commit.speech_captured_at || null;
      pending.durationSec = Number(commit.durationSec) || 0;
      pending.blobUrl = pending.audio_id
        ? "/capture/audio/" + encodeURIComponent(pending.audio_id)
        : null;
      mode = "review";
      renderChrome();
    }

    function renderChrome() {
      chrome.innerHTML = "";
      if (speech === "off") return;

      const status = document.createElement("p");
      status.className = "mb-nf-status";
      chrome.appendChild(status);

      function btn(label, cls, fn) {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "mb-nf-btn" + (cls ? " " + cls : "");
        b.textContent = label;
        b.onclick = fn;
        chrome.appendChild(b);
        return b;
      }

      if (mode === "ready") {
        status.textContent = speech === "authored-memory"
          ? "Tell the story when you are ready. Save on this page when it is right."
          : "Speak to add words. MemoryBox keeps the text, not a separate voice memory.";
        btn(speech === "authored-memory" ? "Tell this story" : "Speak", "primary", function () { startRecording(); });
        addFileFallback();
        addMicPicker();
      } else if (mode === "recording" || mode === "silence" || mode === "paused") {
        addLiveMeter(status);
        if (mode === "paused") {
          btn("Resume", "primary", function () { resumeRecording(); });
          btn("Stop", "", function () { stopRecording(); });
        } else {
          btn("Pause", "", function () { pauseRecording(); });
          btn("Stop", "primary", function () { stopRecording(); });
        }
      } else if (mode === "processing") {
        status.textContent = "Turning speech into words…";
      } else if (mode === "review") {
        status.textContent = "Review the story. Fix the words if needed. Listen back if you want. Save when ready.";
        addReviewPlayer();
        btn("Start over", "", function () { startOver(); });
      }

      if (mode === "silence") {
        const box = document.createElement("div");
        box.className = "mb-nf-prompt";
        box.setAttribute("role", "status");
        const p = document.createElement("p");
        p.textContent = "Are you still there?";
        box.appendChild(p);
        const cont = document.createElement("button");
        cont.type = "button";
        cont.className = "mb-nf-btn primary";
        cont.textContent = "Continue recording";
        cont.onclick = function () {
          silencePrompted = false;
          silenceStarted = 0;
          mode = "recording";
          startMeters();
          renderChrome();
        };
        const stop = document.createElement("button");
        stop.type = "button";
        stop.className = "mb-nf-btn";
        stop.textContent = "Stop";
        stop.onclick = function () { stopRecording(); };
        box.appendChild(cont);
        box.appendChild(stop);
        chrome.appendChild(box);
      }
    }

    function addLiveMeter(status) {
      const mic = trackLabel ? " · " + trackLabel : "";
      if (mode === "paused") {
        status.textContent = "Paused at " + formatTime(elapsedSec()) + mic + ". Resume to keep the same recording.";
      } else {
        status.textContent = "Listening " + formatTime(elapsedSec()) + mic;
      }
      const row = document.createElement("div");
      row.className = "mb-nf-meter";
      const vu = document.createElement("div");
      vu.className = "mb-nf-vu";
      vu.setAttribute("aria-label", "Microphone level");
      const fill = document.createElement("span");
      vu.appendChild(fill);
      row.appendChild(vu);
      chrome.appendChild(row);
    }

    function addReviewPlayer() {
      const box = document.createElement("div");
      box.className = "mb-nf-listen";
      const listenBtn = document.createElement("button");
      listenBtn.type = "button";
      listenBtn.className = "mb-nf-btn primary";
      listenBtn.textContent = "Listen";
      const time = document.createElement("span");
      time.className = "mb-nf-elapsed";
      const dur = pending.durationSec || 0;
      time.textContent = "0:00 / " + formatTime(dur);
      const scrub = document.createElement("input");
      scrub.type = "range";
      scrub.min = "0";
      scrub.max = "1000";
      scrub.value = "0";
      scrub.setAttribute("aria-label", "Listen position");
      box.appendChild(listenBtn);
      box.appendChild(time);
      box.appendChild(scrub);
      chrome.appendChild(box);

      function duration() {
        if (pending.buffer && pending.buffer.duration) return pending.buffer.duration;
        return pending.durationSec || 0;
      }

      function showPos(sec) {
        const d = duration();
        time.textContent = formatTime(sec) + " / " + formatTime(d);
        if (d > 0) scrub.value = String(Math.round((sec / d) * 1000));
      }

      function tick() {
        if (!playing) return;
        const d = duration();
        const sec = Math.min(d, playOffset + (Date.now() - playStartedAt) / 1000);
        showPos(sec);
        if (sec >= d && d > 0) {
          stopPlayback();
          listenBtn.textContent = "Listen";
          showPos(d);
        }
      }

      listenBtn.onclick = async function () {
        if (playing) {
          const sec = playOffset + (Date.now() - playStartedAt) / 1000;
          stopPlayback();
          playOffset = sec;
          listenBtn.textContent = "Listen";
          return;
        }
        try {
          await ensureBuffer();
        } catch (_) {}
        const d = duration();
        if (!pending.buffer || d <= 0) {
          fallbackNativeAudio();
          return;
        }
        if (playOffset >= d) playOffset = 0;
        const AudioCtx = global.AudioContext || global.webkitAudioContext;
        if (!playCtx) playCtx = new AudioCtx();
        try { await playCtx.resume(); } catch (_) {}
        playSource = playCtx.createBufferSource();
        playSource.buffer = pending.buffer;
        playSource.connect(playCtx.destination);
        playSource.onended = function () {
          if (!playing) return;
          stopPlayback();
          listenBtn.textContent = "Listen";
          showPos(duration());
        };
        playing = true;
        playStartedAt = Date.now();
        playSource.start(0, Math.max(0, playOffset));
        listenBtn.textContent = "Pause";
        if (playTimer) clearInterval(playTimer);
        playTimer = setInterval(tick, 100);
      };

      scrub.oninput = function () {
        const d = duration();
        const sec = d * (Number(scrub.value) / 1000);
        playOffset = sec;
        showPos(sec);
        if (playing) {
          listenBtn.click();
          listenBtn.click();
        }
      };

      showPos(0);
    }

    function fallbackNativeAudio() {
      const native = document.createElement("audio");
      native.className = "mb-nf-player";
      native.controls = true;
      native.preload = "auto";
      native.volume = 1;
      native.muted = false;
      if (pending.blobUrl) native.src = pending.blobUrl;
      else if (pending.audio_id) native.src = "/capture/audio/" + encodeURIComponent(pending.audio_id);
      chrome.appendChild(native);
      native.addEventListener("loadedmetadata", function () {
        if (isFinite(native.duration) && native.duration > 0) {
          pending.durationSec = native.duration;
        }
      });
    }

    async function ensureBuffer() {
      if (pending.buffer) return pending.buffer;
      let data = pending.blob;
      if (!data && pending.audio_id) {
        const r = await fetch("/capture/audio/" + encodeURIComponent(pending.audio_id));
        data = await r.blob();
      }
      if (!data) throw new Error("no audio");
      const AudioCtx = global.AudioContext || global.webkitAudioContext;
      const ctx = playCtx || new AudioCtx();
      playCtx = ctx;
      const copy = await data.arrayBuffer();
      pending.buffer = await ctx.decodeAudioData(copy);
      if (pending.buffer && pending.buffer.duration) {
        pending.durationSec = pending.buffer.duration;
      }
      return pending.buffer;
    }

    function addMicPicker() {
      const sel = document.createElement("select");
      sel.className = "mb-nf-mic";
      sel.setAttribute("aria-label", "Microphone");
      sel.hidden = true;
      chrome.appendChild(sel);
      if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) return;
      navigator.mediaDevices.enumerateDevices().then(function (all) {
        const inputs = all.filter(function (d) { return d.kind === "audioinput"; });
        if (inputs.length < 2) return;
        sel.hidden = false;
        const saved = localStorage.getItem("mb_nf_mic_id") || "";
        inputs.forEach(function (d) {
          const opt = document.createElement("option");
          opt.value = d.deviceId;
          opt.textContent = d.label || "Microphone";
          if (d.deviceId === saved) opt.selected = true;
          sel.appendChild(opt);
        });
        sel.onchange = function () {
          if (sel.value) localStorage.setItem("mb_nf_mic_id", sel.value);
        };
      }).catch(function () {});
    }

    function addFileFallback() {
      const lab = document.createElement("label");
      lab.className = "mb-nf-file";
      lab.textContent = "Or add a spoken recording ";
      const inp = document.createElement("input");
      inp.type = "file";
      inp.accept = "audio/*,.webm,.wav,.mp3,.m4a";
      inp.onchange = function () {
        const file = inp.files && inp.files[0];
        if (file) handleBlob(file, file.name || "clip.webm");
      };
      lab.appendChild(inp);
      chrome.appendChild(lab);
    }

    function rmsFromAnalyser() {
      if (!analyser) return 0;
      const data = new Uint8Array(analyser.fftSize);
      analyser.getByteTimeDomainData(data);
      let sum = 0;
      for (let i = 0; i < data.length; i++) {
        const v = (data[i] - 128) / 128;
        sum += v * v;
      }
      return Math.sqrt(sum / data.length);
    }

    function paintMeter() {
      const fill = chrome.querySelector(".mb-nf-vu span");
      const vu = chrome.querySelector(".mb-nf-vu");
      const status = chrome.querySelector(".mb-nf-status");
      const rms = mode === "paused" ? 0 : rmsFromAnalyser();
      if (rms > peakRms) peakRms = rms;
      if (fill) {
        fill.style.width = Math.min(100, Math.round(rms * 220)) + "%";
      }
      if (vu) vu.classList.toggle("is-low", rms < HEARD_FLOOR && mode === "recording");
      if (status && (mode === "recording" || mode === "silence")) {
        const mic = trackLabel ? " · " + trackLabel : "";
        status.textContent = "Listening " + formatTime(elapsedSec()) + mic;
        status.classList.toggle("warn", rms < HEARD_FLOOR);
      }
    }

    function startMeters() {
      stopMeter();
      silenceStarted = 0;
      meterTimer = setInterval(function () {
        paintMeter();
        if (mode !== "recording") return;
        const rms = rmsFromAnalyser();
        if (rms < SILENCE_FLOOR) {
          if (!silenceStarted) silenceStarted = Date.now();
          if (!silencePrompted && Date.now() - silenceStarted >= SILENCE_MS) {
            mode = "silence";
            renderChrome();
          }
        } else {
          silenceStarted = 0;
        }
      }, 100);
    }

    async function startRecording() {
      if (speech === "off") return;
      if (pending.audio_uri && speech === "authored-memory") {
        const ok = confirm("Start a new recording? The unsaved take will be discarded.");
        if (!ok) return;
        await discardPending(true);
      }
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        mode = "ready";
        renderChrome();
        const el = chrome.querySelector(".mb-nf-status");
        if (el) {
          el.textContent = familyError("insecure");
          el.classList.add("warn");
        }
        return;
      }
      snapshotBeforeTake = textarea.value;
      chunks = [];
      silencePrompted = false;
      peakRms = 0;
      pausedMs = 0;
      pauseAt = 0;
      recStartedAt = 0;
      try {
        const deviceId = (localStorage.getItem("mb_nf_mic_id") || "").trim();
        const audio = {
          channelCount: 1,
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false,
        };
        if (deviceId) audio.deviceId = { ideal: deviceId };
        stream = await navigator.mediaDevices.getUserMedia({ audio: audio });
      } catch (err) {
        const name = String((err && err.name) || "");
        const msg = name === "NotAllowedError" || name === "PermissionDeniedError"
          ? familyError("permission")
          : familyError("mic");
        mode = "ready";
        renderChrome();
        const el = chrome.querySelector(".mb-nf-status");
        if (el) {
          el.textContent = msg;
          el.classList.add("warn");
        }
        return;
      }
      const track = stream.getAudioTracks()[0];
      trackLabel = (track && track.label) || "";
      mime = pickMime();
      recorder = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
      recorder.ondataavailable = function (e) {
        if (e.data && e.data.size) chunks.push(e.data);
      };
      const AudioCtx = global.AudioContext || global.webkitAudioContext;
      if (AudioCtx) {
        audioCtx = new AudioCtx();
        try { await audioCtx.resume(); } catch (_) {}
        try {
          meterStream = stream.clone();
        } catch (_) {
          meterStream = stream;
        }
        const source = audioCtx.createMediaStreamSource(meterStream);
        analyser = audioCtx.createAnalyser();
        analyser.fftSize = 2048;
        source.connect(analyser);
      }
      recorder.start(250);
      recStartedAt = Date.now();
      mode = "recording";
      renderChrome();
      startMeters();
    }

    function pauseRecording() {
      if (!recorder || recorder.state !== "recording") return;
      try { recorder.pause(); } catch (_) {}
      pauseAt = Date.now();
      stopMeter();
      mode = "paused";
      renderChrome();
    }

    function resumeRecording() {
      if (!recorder || recorder.state !== "paused") return;
      try { recorder.resume(); } catch (_) {}
      if (pauseAt) {
        pausedMs += Date.now() - pauseAt;
        pauseAt = 0;
      }
      silencePrompted = false;
      silenceStarted = 0;
      mode = "recording";
      renderChrome();
      startMeters();
    }

    function stopRecording() {
      if (!recorder) return;
      const rec = recorder;
      const durationSec = elapsedSec();
      const heard = peakRms;
      rec.onstop = function () {
        const type = rec.mimeType || mime || "audio/webm";
        const blob = new Blob(chunks, { type: type });
        releaseStream();
        handleBlob(blob, type.indexOf("mp4") >= 0 ? "clip.m4a" : "clip.webm", {
          durationSec: durationSec,
          peakRms: heard,
        });
      };
      try { rec.requestData(); } catch (_) {}
      if (rec.state !== "inactive") {
        try { rec.stop(); } catch (_) {}
      }
    }

    async function handleBlob(blob, filename, meta) {
      meta = meta || {};
      if (!blob || !blob.size) {
        mode = "ready";
        renderChrome();
        const el = chrome.querySelector(".mb-nf-status");
        if (el) {
          el.textContent = "Nothing was recorded. You can try again or type.";
          el.classList.add("warn");
        }
        return;
      }
      mode = "processing";
      renderChrome();
      if (speech === "authored-memory") {
        revokeBlob();
        pending.blob = blob;
        pending.blobUrl = URL.createObjectURL(blob);
        pending.durationSec = Number(meta.durationSec) || 0;
        pending.peakRms = Number(meta.peakRms) || 0;
        pending.speech_captured_at = new Date().toISOString();
        try {
          await ensureBuffer();
        } catch (_) {}
      }
      const retain = speech === "authored-memory" ? "1" : "0";
      const fd = new FormData();
      fd.append("file", blob, filename || "clip.webm");
      let data = {};
      let ok = false;
      try {
        const r = await fetch("/capture/transcribe?retain=" + retain, { method: "POST", body: fd });
        data = await r.json().catch(function () { return {}; });
        ok = r.ok;
      } catch (_) {
        data = {};
      }
      const detail = data && data.detail;
      const audioFromErr = detail && typeof detail === "object" ? detail.audio : null;
      const draft = (data && data.draft) || data || {};
      const audioId = draft.audio_id || (audioFromErr && audioFromErr.audio_id) || null;
      const audioUri = draft.audio_uri || (audioFromErr && audioFromErr.audio_uri) || null;
      const text = (draft.text || "").trim();

      if (speech === "convenience") {
        if (text) {
          insertAtCursor(textarea, text);
          emit();
        }
        mode = "ready";
        renderChrome();
        if (!ok || !text) {
          const el = chrome.querySelector(".mb-nf-status");
          if (el) {
            el.textContent = familyError("stt");
            el.classList.add("warn");
          }
        }
        return;
      }

      pending.audio_id = audioId;
      pending.audio_uri = audioUri;
      pending.sttText = text;
      pending.speech_user_edited = false;
      if (text) {
        insertAtCursor(textarea, text);
        emit();
      }
      textarea.addEventListener("input", markEdited);
      mode = "review";
      renderChrome();
      const status = chrome.querySelector(".mb-nf-status");
      if (status) {
        if ((meta.peakRms || 0) < HEARD_FLOOR) {
          status.textContent = familyError("quiet");
          status.classList.add("warn");
        } else if (!ok && !text) {
          status.textContent = familyError("stt");
          status.classList.add("warn");
        }
      }
    }

    function markEdited() {
      pending.speech_user_edited = true;
    }

    async function startOver() {
      const meaningful = Boolean(pending.audio_uri || pending.blobUrl || pending.blob || (textarea.value || "").length > snapshotBeforeTake.length);
      if (meaningful && !confirm("Discard this recording and start over?")) return;
      textarea.removeEventListener("input", markEdited);
      textarea.value = snapshotBeforeTake;
      emit();
      await discardPending(true);
      startRecording();
    }

    function teardown() {
      textarea.removeEventListener("input", markEdited);
      window.removeEventListener("pagehide", onPageHide);
      stopPlayback();
      if (playCtx) {
        try { playCtx.close(); } catch (_) {}
        playCtx = null;
      }
      releaseStream();
      revokeBlob();
      if (wrap.parentNode) {
        wrap.parentNode.insertBefore(textarea, wrap);
        wrap.parentNode.removeChild(wrap);
      }
      textarea._mbNarrative = null;
    }

    function onPageHide() {
      if (speech !== "authored-memory") return;
      const id = pending && pending.audio_id;
      if (!id) return;
      try {
        fetch("/capture/audio/" + encodeURIComponent(id), { method: "DELETE", keepalive: true });
      } catch (_) {}
    }

    window.addEventListener("pagehide", onPageHide);

    textarea.addEventListener("input", function () {
      if (opts.onChange) opts.onChange();
    });

    renderChrome();
    if (opts.autoStart) {
      setTimeout(function () { startRecording(); }, 50);
    }
    return api;
  }

  global.MBNarrativeField = { mount: mount };
})(window);
