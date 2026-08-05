/* MBD-001 curator shell */
const toastEl = document.getElementById('archiveToast');
let toastTimer = null;
let cfg = { hvrt_origin: 'http://127.0.0.1:8788' };
let editingId = null;
let teachContext = null; // selected evidence for teaching

function showArchiveUpdated() {
  toastEl.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toastEl.hidden = true; }, 2200);
}

async function readJson(res) {
  const text = await res.text();
  let data = null;
  try { data = text ? JSON.parse(text) : {}; }
  catch {
    throw new Error((text || res.statusText || 'bad response').slice(0, 160));
  }
  if (!res.ok) {
    const d = data && data.detail;
    throw new Error(typeof d === 'string' ? d : `${res.status}`);
  }
  return data;
}

function hideTeach() {
  teachContext = null;
  const panel = document.getElementById('teachPanel');
  if (panel) panel.hidden = true;
}

function openTeach(item) {
  teachContext = item || null;
  const panel = document.getElementById('teachPanel');
  panel.hidden = false;
  const title = item?.title || '';
  document.getElementById('teachAbout').textContent = title
    ? `About “${title}”`
    : 'About selected evidence';
  document.getElementById('memTitle').value = title || '';
  document.getElementById('memBody').value = '';
  document.getElementById('memBody').focus();
  panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function setView(name) {
  document.querySelectorAll('.nav-btn').forEach(b => {
    b.classList.toggle('is-active', b.dataset.view === name);
  });
  document.querySelectorAll('.view').forEach(v => {
    const on = v.id === `view-${name}`;
    v.hidden = !on;
    v.classList.toggle('is-active', on);
  });
  if (name !== 'ask') hideTeach();
  if (name === 'review') {
    const frame = document.getElementById('hvrtFrame');
    const origin = cfg.hvrt_origin || 'http://127.0.0.1:8788';
    document.getElementById('hvrtOpen').href = origin;
    if (!frame.dataset.loaded) {
      frame.src = origin + '/';
      frame.dataset.loaded = '1';
    }
  }
  if (name === 'library') refreshLibrary();
}

document.querySelectorAll('.nav-btn').forEach(btn => {
  btn.addEventListener('click', () => setView(btn.dataset.view));
});

document.querySelectorAll('.hint[data-q]').forEach(btn => {
  btn.addEventListener('click', () => {
    document.getElementById('askInput').value = btn.dataset.q;
    document.getElementById('askForm').requestSubmit();
  });
});

function renderEvidence(items) {
  const ev = document.getElementById('askEvidence');
  if (!items.length) {
    ev.hidden = true;
    ev.innerHTML = '';
    return;
  }
  ev.hidden = false;
  ev.innerHTML = items.map((item, idx) => {
    const title = item.title || item.type || 'Evidence';
    const snip = item.snippet || item.text || '';
    const ver = item.version != null ? ` · v${item.version}` : '';
    const src = item.source ? ` · ${item.source}` : '';
    const mid = item.id || item.memory_id;
    const isMem = item.type === 'memory' || item.kind === 'voice_note' || item.kind === 'artifact_label';
    const actions = [
      `<button type="button" class="ghost" data-teach="${idx}">Teach about this</button>`,
    ];
    if (isMem) {
      actions.push(`<button type="button" class="ghost" data-edit="${mid}">Edit Memory</button>`);
    }
    if (item.open_hint) {
      actions.push(`<span class="quiet">${escapeHtml(item.open_hint)}</span>`);
    }
    return `<article>
      <h3>${escapeHtml(title)}${escapeHtml(ver)}</h3>
      <p class="snippet">${escapeHtml(snip)}</p>
      <p class="quiet">${escapeHtml((item.modality || item.type || '') + src)}</p>
      <div class="lib-actions">${actions.join('')}</div>
    </article>`;
  }).join('');

  ev.querySelectorAll('[data-teach]').forEach(b => {
    b.addEventListener('click', () => openTeach(items[Number(b.dataset.teach)]));
  });
  ev.querySelectorAll('[data-edit]').forEach(b => {
    b.addEventListener('click', () => openEdit(Number(b.dataset.edit)));
  });
}

document.getElementById('askForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  hideTeach();
  const q = document.getElementById('askInput').value.trim();
  if (!q) return;
  const ans = document.getElementById('askAnswer');
  const ev = document.getElementById('askEvidence');
  ans.hidden = false;
  ans.textContent = 'Listening…';
  ev.hidden = true;
  try {
    const data = await readJson(await fetch('/api/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: q }),
    }));
    ans.textContent = data.answer || '';
    renderEvidence(data.evidence || []);
  } catch (err) {
    ans.textContent = err.message || String(err);
  }
});

document.getElementById('teachCancelBtn').addEventListener('click', hideTeach);

document.getElementById('saveMemoryBtn').addEventListener('click', async () => {
  const title = document.getElementById('memTitle').value.trim();
  const body_text = document.getElementById('memBody').value.trim();
  if (!body_text) {
    alert('Add what you know first');
    return;
  }
  const asset_ref = teachContext
    ? `${teachContext.type || 'evidence'}:${teachContext.id || ''}`
    : null;
  try {
    const data = await readJson(await fetch('/api/memories', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        kind: 'voice_note',
        title: title || null,
        body_text,
        asset_ref,
      }),
    }));
    if (data.archive_updated) showArchiveUpdated();
    hideTeach();
  } catch (err) {
    alert(err.message || String(err));
  }
});

async function refreshLibrary() {
  const q = document.getElementById('libSearch').value.trim();
  const url = q ? `/api/library?q=${encodeURIComponent(q)}` : '/api/library';
  const list = document.getElementById('libList');
  list.innerHTML = '<li class="quiet">Loading…</li>';
  try {
    const data = await readJson(await fetch(url));
    const items = data.items || [];
    if (!items.length) {
      list.innerHTML = '<li class="quiet">No archive rows yet — check that memorybox.db and hvrt/database/hvrt.sqlite are present.</li>';
      return;
    }
    list.innerHTML = items.map((it, idx) => {
      const ver = it.version != null ? ` · v${it.version}` : '';
      const edit = it.memory_id
        ? `<button type="button" class="ghost" data-edit="${it.memory_id}">Edit Memory</button>`
        : `<button type="button" class="ghost" data-teach-idx="${idx}">Teach about this</button>`;
      return `<li>
      <h3>${escapeHtml(it.title || '')}${escapeHtml(ver)}</h3>
      <p class="snippet">${escapeHtml(it.snippet || '')}</p>
      <p class="quiet">${escapeHtml(it.when || '')} · ${escapeHtml(it.modality || '')} · ${escapeHtml(it.source || '')}</p>
      <div class="lib-actions">${edit}</div>
    </li>`;
    }).join('');
    list._items = items;
    list.querySelectorAll('[data-edit]').forEach(b => {
      b.addEventListener('click', () => openEdit(Number(b.dataset.edit)));
    });
    list.querySelectorAll('[data-teach-idx]').forEach(b => {
      b.addEventListener('click', () => {
        const it = list._items[Number(b.dataset.teachIdx)];
        setView('ask');
        openTeach({
          type: (it.raw && it.raw.type) || it.modality,
          id: it.raw && it.raw.id,
          title: it.title,
        });
      });
    });
  } catch (err) {
    list.innerHTML = `<li class="quiet">${escapeHtml(err.message || String(err))}</li>`;
  }
}

document.getElementById('libRefresh').addEventListener('click', refreshLibrary);
document.getElementById('libSearch').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') refreshLibrary();
});

async function openEdit(id) {
  editingId = id;
  const m = await readJson(await fetch(`/api/memories/${id}`));
  document.getElementById('editBody').value = m.body_text || '';
  document.getElementById('editNote').value = '';
  document.getElementById('editMeta').textContent =
    `${m.title || m.kind} · current v${m.current_version} · ${m.updated_at || ''}`;
  const hist = (m.versions || []).map(v =>
    `v${v.version} · ${v.created_at}${v.note ? ' · ' + v.note : ''}`
  ).join('<br>');
  document.getElementById('editHistory').innerHTML = hist
    ? `<strong>History</strong><br>${hist}`
    : '';
  document.getElementById('editDialog').showModal();
}

document.getElementById('editCancel').addEventListener('click', () => {
  document.getElementById('editDialog').close();
});

document.getElementById('editForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  if (!editingId) return;
  const body_text = document.getElementById('editBody').value.trim();
  const note = document.getElementById('editNote').value.trim();
  try {
    const data = await readJson(await fetch(`/api/memories/${editingId}/edit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ body_text, note: note || null }),
    }));
    if (data.archive_updated) showArchiveUpdated();
    document.getElementById('editDialog').close();
    refreshLibrary();
  } catch (err) {
    alert(err.message || String(err));
  }
});

function escapeHtml(s) {
  return String(s || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

fetch('/api/config').then(r => r.json()).then(c => {
  cfg = c;
  const s = c.sources || {};
  const bits = [];
  if (s.hvrt_present) bits.push('HVRT');
  if (s.memorybox_present) bits.push('email/SMS');
  if (s.immich_configured) bits.push('Immich');
  document.getElementById('askHint').textContent = bits.length
    ? `Searching ${bits.join(' + ')}`
    : 'POC databases not found — place memorybox.db and hvrt/database/hvrt.sqlite under the repo';
  document.getElementById('hvrtOpen').href = c.hvrt_origin || 'http://127.0.0.1:8788';
}).catch(() => {});
