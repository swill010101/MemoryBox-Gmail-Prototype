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

  function isVirtualMic(label) {
    return /voicemeeter|vb-audio|cable|stereo mix|what u hear|loopback|virtual/i.test(label || "");
  }

  function micOptionLabel(label) {
    const s = String(label || "Microphone").trim() || "Microphone";
    if (isVirtualMic(s)) return s + " — usually silent";
    return s;
  }

  function preferMicId(devices) {
    const real = (devices || []).filter(function (d) { return !isVirtualMic(d.label); });
    const pool = real.length ? real : (devices || []);
    const saved = localStorage.getItem("mb_nf_mic_id") || "";
    if (saved && pool.some(function (d) { return d.deviceId === saved; })) return saved;
    const named = pool.find(function (d) {
      return /usb|logi|c615|headset|yeti|blue |snowball|array|microphone/i.test(d.label || "");
    });
    return (named && named.deviceId) || (pool[0] && pool[0].deviceId) || "";
  }

  function familyError(kind) {
    if (kind === "permission") {
      return "MemoryBox couldn't use the microphone. You can still type, and you can try again.";
    }
    if (kind === "stt") {
      return "Couldn't turn that into words. You can still listen, type, and save.";
    }
    if (kind === "quiet") {
      return "MemoryBox didn't hear much. Choose your USB microphone, then Start over.";
    }
    if (kind === "virtual") {
      return "MemoryBox was using a virtual audio device, which is usually silent. Choose your USB microphone, then Start over.";
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
    let stillModal = null;
    let pending = emptyPending();
    let playSource = null;
    let playCtx = null;
    let playTimer = null;
    let playOffset = 0;
    let playStartedAt = 0;
    let playing = false;
    let reviewAudio = null;
    let processLabel = "Turning speech into words…";
    let processPct = null;

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
      if (playTimer) {
        clearInterval(playTimer);
        playTimer = null;
      }
      if (playSource) {
        try { playSource.stop(); } catch (_) {}
        playSource = null;
      }
      if (reviewAudio && !reviewAudio.paused) {
        try { reviewAudio.pause(); } catch (_) {}
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
      closeStillThereModal();
      stopPlayback();
      reviewAudio = null;
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
      } else if (mode === "recording" || mode === "paused") {
        addLiveMeter(status);
        const actions = document.createElement("div");
        actions.className = "mb-nf-actions";
        chrome.appendChild(actions);
        function act(label, cls, fn) {
          const b = document.createElement("button");
          b.type = "button";
          b.className = "mb-nf-btn" + (cls ? " " + cls : "");
          b.textContent = label;
          b.onclick = fn;
          actions.appendChild(b);
        }
        if (mode === "paused") {
          act("Resume", "primary", function () { resumeRecording(); });
          act("Stop", "", function () { stopRecording(); });
        } else {
          act("Pause", "", function () { pauseRecording(); });
          act("Stop", "primary", function () { stopRecording(); });
        }
      } else if (mode === "processing") {
        addWorkingChrome(status);
      } else if (mode === "review") {
        status.textContent = "Review the story. Fix the words if needed. Listen back if you want. Save when ready.";
        addReviewPlayer();
      }
    }

    function closeStillThereModal() {
      if (stillModal && stillModal.parentNode) stillModal.parentNode.removeChild(stillModal);
      stillModal = null;
    }

    function pauseCapture(opts) {
      opts = opts || {};
      if (!recorder || recorder.state !== "recording") return false;
      if (!opts.fromSilence) closeStillThereModal();
      silencePrompted = true;
      try { recorder.pause(); } catch (_) {}
      pauseAt = Date.now();
      stopMeter();
      mode = "paused";
      renderChrome();
      return true;
    }

    function pauseRecording() {
      pauseCapture({});
    }

    function openStillThereModal() {
      if (stillModal) return;
      pauseCapture({ fromSilence: true });
      stillModal = document.createElement("div");
      stillModal.className = "mb-nf-modal-back";
      stillModal.innerHTML = '<div class="mb-nf-modal" role="dialog" aria-modal="true">' +
        "<p>Are you still there?</p>" +
        '<p class="mb-nf-modal-note">Recording is paused so this story does not keep going if you stepped away.</p>' +
        '<p class="mb-nf-modal-elapsed">Paused at ' + formatTime(elapsedSec()) + "</p>" +
        '<p class="mb-nf-modal-actions">' +
        '<button type="button" class="mb-nf-btn primary" data-mb-still="continue">Continue recording</button>' +
        '<button type="button" class="mb-nf-btn" data-mb-still="stop">Stop</button>' +
        "</p></div>";
      stillModal.addEventListener("click", function (ev) {
        const t = ev.target;
        if (!t || !t.getAttribute) return;
        if (t.getAttribute("data-mb-still") === "continue") {
          closeStillThereModal();
          resumeRecording();
        }
        if (t.getAttribute("data-mb-still") === "stop") {
          closeStillThereModal();
          stopRecording();
        }
      });
      document.body.appendChild(stillModal);
    }

    function addWorkingChrome(status) {
      status.classList.add("is-working");
      status.textContent = processPct != null
        ? (processLabel + " " + processPct + "%")
        : processLabel;
      const track = document.createElement("div");
      track.className = "mb-nf-progress" + (processPct == null ? " is-indeterminate" : "");
      const fill = document.createElement("span");
      fill.className = "mb-nf-progress-fill";
      if (processPct != null) fill.style.width = processPct + "%";
      track.appendChild(fill);
      chrome.appendChild(track);
    }

    function setProcessProgress(label, pct) {
      processLabel = label;
      processPct = typeof pct === "number" ? Math.max(0, Math.min(100, Math.round(pct))) : null;
      if (mode !== "processing") return;
      const status = chrome.querySelector(".mb-nf-status");
      const track = chrome.querySelector(".mb-nf-progress");
      const fill = chrome.querySelector(".mb-nf-progress-fill");
      if (status) {
        status.classList.add("is-working");
        status.textContent = processPct != null
          ? (processLabel + " " + processPct + "%")
          : processLabel;
      }
      if (track && fill) {
        if (processPct == null) {
          track.classList.add("is-indeterminate");
          fill.style.width = "";
        } else {
          track.classList.remove("is-indeterminate");
          fill.style.width = processPct + "%";
        }
      }
    }

    function postTranscribe(blob, filename, retain) {
      return new Promise(function (resolve) {
        const fd = new FormData();
        fd.append("file", blob, filename || "clip.webm");
        const xhr = new XMLHttpRequest();
        xhr.open("POST", "/capture/transcribe?retain=" + retain);
        xhr.upload.onprogress = function (e) {
          if (e.lengthComputable && e.total > 0) {
            setProcessProgress("Sending the recording…", (e.loaded / e.total) * 100);
          }
        };
        xhr.upload.onload = function () {
          setProcessProgress("Turning speech into words…", null);
        };
        xhr.onerror = function () {
          resolve({ ok: false, data: {} });
        };
        xhr.onload = function () {
          let data = {};
          try {
            data = JSON.parse(xhr.responseText || "{}");
          } catch (_) {
            data = {};
          }
          resolve({
            ok: xhr.status >= 200 && xhr.status < 300,
            data: data,
          });
        };
        setProcessProgress("Sending the recording…", 0);
        xhr.send(fd);
      });
    }

    function addLiveMeter(status) {
      if (mode === "paused") {
        status.textContent = "Paused at " + formatTime(elapsedSec()) + ". Resume to keep the same recording.";
      } else if (isVirtualMic(trackLabel)) {
        status.textContent = "Listening " + formatTime(elapsedSec()) + ". Virtual audio is usually silent — Stop, then pick your USB microphone.";
        status.classList.add("warn");
      } else {
        status.textContent = "Listening " + formatTime(elapsedSec());
      }
      const wrapMeter = document.createElement("div");
      wrapMeter.className = "mb-nf-vu-wrap";
      const lab = document.createElement("div");
      lab.className = "mb-nf-vu-label";
      lab.textContent = "Level";
      const vu = document.createElement("div");
      vu.className = "mb-nf-vu";
      vu.setAttribute("aria-label", "Microphone level");
      const fill = document.createElement("span");
      vu.appendChild(fill);
      wrapMeter.appendChild(lab);
      wrapMeter.appendChild(vu);
      chrome.appendChild(wrapMeter);
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
      const scrub = document.createElement("input");
      scrub.type = "range";
      scrub.min = "0";
      scrub.max = "1000";
      scrub.value = "0";
      scrub.setAttribute("aria-label", "Listen position");
      const again = document.createElement("button");
      again.type = "button";
      again.className = "mb-nf-btn";
      again.textContent = "Start over";
      again.onclick = function () { startOver(); };
      const native = document.createElement("audio");
      native.preload = "auto";
      native.setAttribute("playsinline", "true");
      native.volume = 1;
      native.muted = false;
      if (pending.blobUrl) native.src = pending.blobUrl;
      else if (pending.audio_id) native.src = "/capture/audio/" + encodeURIComponent(pending.audio_id);
      reviewAudio = native;
      box.appendChild(listenBtn);
      box.appendChild(time);
      box.appendChild(scrub);
      box.appendChild(again);
      box.appendChild(native);
      chrome.appendChild(box);

      function duration() {
        if (native && isFinite(native.duration) && native.duration > 0) return native.duration;
        if (pending.buffer && pending.buffer.duration) return pending.buffer.duration;
        return pending.durationSec || 0;
      }

      function showPos(sec) {
        const d = duration();
        time.textContent = formatTime(sec) + " / " + formatTime(d);
        if (d > 0) scrub.value = String(Math.round((sec / d) * 1000));
      }

      native.addEventListener("loadedmetadata", function () {
        if (isFinite(native.duration) && native.duration > 0) {
          pending.durationSec = native.duration;
        }
        showPos(native.currentTime || 0);
      });
      native.addEventListener("timeupdate", function () {
        showPos(native.currentTime || 0);
      });
      native.addEventListener("ended", function () {
        listenBtn.textContent = "Listen";
        showPos(duration());
      });
      native.addEventListener("pause", function () {
        if (native.ended) return;
        listenBtn.textContent = "Listen";
      });
      native.addEventListener("play", function () {
        listenBtn.textContent = "Pause";
      });

      listenBtn.onclick = async function () {
        if (!native.paused && !native.ended) {
          native.pause();
          return;
        }
        try {
          if (native.ended || (duration() > 0 && native.currentTime >= duration() - 0.05)) {
            native.currentTime = 0;
          }
          await native.play();
        } catch (_) {
          fallbackNativeAudio();
        }
      };

      scrub.oninput = function () {
        const d = duration();
        if (d > 0) native.currentTime = d * (Number(scrub.value) / 1000);
        showPos(native.currentTime || 0);
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
      const row = document.createElement("label");
      row.className = "mb-nf-mic-row";
      row.textContent = "Microphone";
      const sel = document.createElement("select");
      sel.className = "mb-nf-mic";
      sel.setAttribute("aria-label", "Microphone");
      row.appendChild(sel);
      chrome.appendChild(row);
      if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) {
        sel.innerHTML = "<option>Microphone list unavailable</option>";
        return;
      }
      navigator.mediaDevices.enumerateDevices().then(function (all) {
        const inputs = all.filter(function (d) { return d.kind === "audioinput"; });
        sel.innerHTML = "";
        if (!inputs.length) {
          sel.innerHTML = "<option>No microphones found</option>";
          return;
        }
        const preferred = preferMicId(inputs);
        inputs.forEach(function (d) {
          const opt = document.createElement("option");
          opt.value = d.deviceId;
          opt.textContent = micOptionLabel(d.label);
          if (d.deviceId === preferred) opt.selected = true;
          sel.appendChild(opt);
        });
        if (preferred) localStorage.setItem("mb_nf_mic_id", preferred);
        sel.onchange = function () {
          const hit = inputs.find(function (d) { return d.deviceId === sel.value; });
          if (hit && isVirtualMic(hit.label)) {
            localStorage.removeItem("mb_nf_mic_id");
          } else if (sel.value) {
            localStorage.setItem("mb_nf_mic_id", sel.value);
          }
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
        fill.style.width = Math.min(100, Math.round(rms * 380)) + "%";
      }
      if (vu) vu.classList.toggle("is-low", rms < HEARD_FLOOR && mode === "recording");
      if (status && mode === "recording") {
        if (isVirtualMic(trackLabel)) {
          status.textContent = "Listening " + formatTime(elapsedSec()) + ". Virtual audio is usually silent — Stop, then pick your USB microphone.";
          status.classList.add("warn");
        } else {
          status.textContent = "Listening " + formatTime(elapsedSec());
          status.classList.toggle("warn", rms < HEARD_FLOOR);
        }
      }
      if (status && mode === "paused") {
        status.classList.remove("warn");
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
            openStillThereModal();
          }
        } else {
          silenceStarted = 0;
        }
      }, 100);
    }

    async function openMicStream() {
      const constraint = {
        channelCount: 1,
        echoCancellation: false,
        noiseSuppression: false,
        autoGainControl: false,
      };
      const saved = localStorage.getItem("mb_nf_mic_id") || "";
      const first = Object.assign({}, constraint);
      if (saved) first.deviceId = { ideal: saved };
      let s = await navigator.mediaDevices.getUserMedia({ audio: first });
      const inputs = (await navigator.mediaDevices.enumerateDevices()).filter(function (d) {
        return d.kind === "audioinput";
      });
      const sel = chrome.querySelector(".mb-nf-mic");
      const want = (sel && sel.value) || preferMicId(inputs);
      const track = s.getAudioTracks()[0];
      const currentId = (track && track.getSettings && track.getSettings().deviceId) || "";
      if (want && want !== currentId) {
        s.getTracks().forEach(function (t) { t.stop(); });
        try {
          s = await navigator.mediaDevices.getUserMedia({
            audio: Object.assign({}, constraint, { deviceId: { exact: want } }),
          });
        } catch (_) {
          s = await navigator.mediaDevices.getUserMedia({ audio: constraint });
        }
      }
      const opened = s.getAudioTracks()[0];
      const label = (opened && opened.label) || "";
      const settingsId = (opened && opened.getSettings && opened.getSettings().deviceId) || want;
      if (settingsId && !isVirtualMic(label)) localStorage.setItem("mb_nf_mic_id", settingsId);
      else localStorage.removeItem("mb_nf_mic_id");
      return s;
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
        stream = await openMicStream();
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
        const mute = audioCtx.createGain();
        mute.gain.value = 0;
        analyser.connect(mute);
        mute.connect(audioCtx.destination);
      }
      recorder.start(250);
      recStartedAt = Date.now();
      mode = "recording";
      renderChrome();
      startMeters();
    }

    function resumeRecording() {
      closeStillThereModal();
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
      closeStillThereModal();
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
      processLabel = "Turning speech into words…";
      processPct = null;
      renderChrome();
      if (speech === "authored-memory") {
        revokeBlob();
        pending.blob = blob;
        pending.blobUrl = URL.createObjectURL(blob);
        pending.durationSec = Number(meta.durationSec) || 0;
        pending.peakRms = Number(meta.peakRms) || 0;
        pending.speech_captured_at = new Date().toISOString();
      }
      const retain = speech === "authored-memory" ? "1" : "0";
      const decodeP = speech === "authored-memory"
        ? ensureBuffer().catch(function () { return null; })
        : Promise.resolve(null);
      let data = {};
      let ok = false;
      try {
        const posted = await postTranscribe(blob, filename, retain);
        data = posted.data || {};
        ok = Boolean(posted.ok);
      } catch (_) {
        data = {};
      }
      try { await decodeP; } catch (_) {}
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
        if (isVirtualMic(trackLabel) || (meta.peakRms || 0) < HEARD_FLOOR) {
          status.textContent = isVirtualMic(trackLabel) ? familyError("virtual") : familyError("quiet");
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
      closeStillThereModal();
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
