/* MBD-001 curator shell — evidence detail + People + embedded Review */
const toastEl = document.getElementById('archiveToast');
let toastTimer = null;
let cfg = { review_embed: '/review-embed', hvrt_mounted: false };
let editingId = null;
let lastEvidence = [];
let teachContext = null;
let peopleCache = [];

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

function escapeHtml(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function fmtSec(s) {
  const n = Math.max(0, Number(s) || 0);
  const m = Math.floor(n / 60);
  const r = Math.floor(n % 60);
  return `${m}:${String(r).padStart(2, '0')}`;
}

function setView(name, reviewQuery) {
  document.querySelectorAll('.nav-btn').forEach(b => {
    b.classList.toggle('is-active', b.dataset.view === name);
  });
  document.querySelectorAll('.view').forEach(v => {
    const on = v.id === `view-${name}`;
    v.hidden = !on;
    v.classList.toggle('is-active', on);
  });
  if (name === 'review') loadReview(reviewQuery);
  if (name === 'people') refreshPeople();
}

function loadReview(query) {
  const frame = document.getElementById('hvrtFrame');
  const base = cfg.review_embed || '/review-embed';
  const url = query ? `${base}?${query}` : base;
  if (frame.dataset.src !== url) {
    frame.src = url;
    frame.dataset.src = url;
  }
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

function closeDetail() {
  document.getElementById('detailPanel').hidden = true;
  document.getElementById('teachBlock').hidden = true;
  teachContext = null;
  document.querySelectorAll('#askEvidence article').forEach(a => a.classList.remove('is-selected'));
}

document.getElementById('detailClose').onclick = closeDetail;

function renderEvidence(items) {
  lastEvidence = items || [];
  const ev = document.getElementById('askEvidence');
  closeDetail();
  if (!lastEvidence.length) {
    ev.hidden = true;
    ev.innerHTML = '';
    return;
  }
  ev.hidden = false;
  ev.innerHTML = lastEvidence.map((item, idx) => {
    const title = item.title || item.type || 'Evidence';
    const snip = item.snippet || item.text || '';
    const mod = item.modality || item.type || '';
    const src = item.source ? ` · ${item.source}` : '';
    return `<article data-idx="${idx}" tabindex="0" role="button">
      <h3>${escapeHtml(title)}</h3>
      <p class="snippet">${escapeHtml(snip)}</p>
      <p class="quiet">${escapeHtml(mod + src)}</p>
      <div class="lib-actions">
        <button type="button" class="ghost" data-more="${idx}">Tell me more</button>
      </div>
    </article>`;
  }).join('');

  ev.querySelectorAll('article').forEach(card => {
    const open = () => openEvidence(Number(card.dataset.idx));
    card.addEventListener('click', (e) => {
      if (e.target.closest('button')) return;
      open();
    });
    card.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); }
    });
  });
  ev.querySelectorAll('[data-more]').forEach(b => {
    b.addEventListener('click', (e) => {
      e.stopPropagation();
      openEvidence(Number(b.dataset.more));
    });
  });
}

async function openEvidence(idx) {
  const item = lastEvidence[idx];
  if (!item) return;
  document.querySelectorAll('#askEvidence article').forEach(a => {
    a.classList.toggle('is-selected', Number(a.dataset.idx) === idx);
  });
  const panel = document.getElementById('detailPanel');
  const body = document.getElementById('detailBody');
  const teach = document.getElementById('teachBlock');
  panel.hidden = false;
  body.innerHTML = `<p class="quiet">Loading…</p>`;
  teach.hidden = true;
  teachContext = item;

  try {
    const detail = await loadEvidenceDetail(item);
    body.innerHTML = renderDetailHtml(detail, item);
    wireDetailActions(body, detail, item);
    // Offer teach only after evidence is open
    teach.hidden = false;
    document.getElementById('memTitle').value = item.title || detail.title || '';
    document.getElementById('memBody').value = '';
    panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  } catch (err) {
    body.innerHTML = `<p class="quiet">${escapeHtml(err.message || String(err))}</p>`;
  }
}

async function loadEvidenceDetail(item) {
  const t = item.type;
  if (t === 'email') return readJson(await fetch(`/api/evidence/email/${item.id}`));
  if (t === 'sms') return readJson(await fetch(`/api/evidence/sms/${item.id}`));
  if (t === 'hvrt_person') return readJson(await fetch(`/api/evidence/hvrt/person/${item.id}`));
  if (t === 'person' && item.id) {
    // memorybox person hub — show Ask hits for that name
    return {
      type: 'person',
      title: item.title,
      snippet: item.snippet,
      body_text: item.snippet || '',
      review_name: item.title,
    };
  }
  if (t === 'memory') return readJson(await fetch(`/api/memories/${item.id}`));
  if (t === 'hvrt_transcript' || t === 'hvrt_place' || t === 'calendar' || t === 'photo' || t === 'immich_photo' || t === 'immich_person') {
    return { ...item, body_text: item.snippet || '' };
  }
  return { ...item, body_text: item.snippet || '' };
}

function renderDetailHtml(detail, item) {
  const t = detail.type || item.type;
  if (t === 'email') {
    return `
      <h2 class="edit-title">${escapeHtml(detail.title)}</h2>
      <p class="quiet">From ${escapeHtml(detail.from_addr || '?')} · ${escapeHtml((detail.date_utc || '').slice(0, 19))}</p>
      <div class="body-block">${escapeHtml(detail.body_text || '')}</div>`;
  }
  if (t === 'sms') {
    return `
      <h2 class="edit-title">${escapeHtml(detail.title)}</h2>
      <p class="quiet">${escapeHtml(detail.timestamp || '')}</p>
      <div class="body-block">${escapeHtml(detail.body || '')}</div>`;
  }
  if (t === 'hvrt_person') {
    const hits = detail.hits || [];
    const rows = hits.length
      ? hits.map(h => `
        <div class="hit-row">
          <div>
            <strong>${escapeHtml(h.filename)}</strong>
            <div class="quiet">${fmtSec(h.start_sec)} → ${fmtSec(h.end_sec)} · conf ${Number(h.confidence || 0).toFixed(2)}</div>
          </div>
          <button type="button" class="ghost" data-open-review="${detail.id}" data-name="${escapeHtml(detail.name || '')}">Open in Review</button>
        </div>`).join('')
      : `<p class="quiet">No face appearance rows yet — open Review to enroll / Learn.</p>`;
    return `
      <h2 class="edit-title">${escapeHtml(detail.name || detail.title)}</h2>
      <p class="quiet">${hits.length} face hit(s) in HVRT</p>
      <div class="actions" style="margin-bottom:.5rem">
        <button type="button" class="primary" data-open-review="${detail.id}" data-name="${escapeHtml(detail.name || '')}">Open in Review (box face, enroll, spoken text)</button>
      </div>
      <div>${rows}</div>`;
  }
  if (t === 'memory') {
    return `
      <h2 class="edit-title">${escapeHtml(detail.title || 'Memory')}</h2>
      <p class="quiet">v${detail.current_version} · ${escapeHtml(detail.updated_at || '')}</p>
      <div class="body-block">${escapeHtml(detail.body_text || '')}</div>
      <div class="actions"><button type="button" class="ghost" data-edit-mem="${detail.id}">Edit Memory</button></div>`;
  }
  return `
    <h2 class="edit-title">${escapeHtml(detail.title || item.title || 'Evidence')}</h2>
    <p class="quiet">${escapeHtml(detail.modality || detail.type || '')} · ${escapeHtml(detail.source || '')}</p>
    <div class="body-block">${escapeHtml(detail.body_text || detail.snippet || '')}</div>
    ${detail.review_name || detail.title ? `<div class="actions"><button type="button" class="primary" data-open-review-name="${escapeHtml(detail.review_name || detail.title)}">Open in Review</button></div>` : ''}`;
}

function wireDetailActions(root, detail, item) {
  root.querySelectorAll('[data-open-review]').forEach(b => {
    b.addEventListener('click', () => {
      const pid = b.dataset.openReview;
      const name = b.dataset.name || '';
      const q = new URLSearchParams({ person_id: pid, person_name: name }).toString();
      setView('review', q);
    });
  });
  root.querySelectorAll('[data-open-review-name]').forEach(b => {
    b.addEventListener('click', () => {
      const q = new URLSearchParams({ person_name: b.dataset.openReviewName }).toString();
      setView('review', q);
    });
  });
  root.querySelectorAll('[data-edit-mem]').forEach(b => {
    b.addEventListener('click', () => openEdit(Number(b.dataset.editMem)));
  });
}

document.getElementById('askForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  closeDetail();
  const q = document.getElementById('askInput').value.trim();
  if (!q) return;
  const ans = document.getElementById('askAnswer');
  ans.hidden = false;
  ans.textContent = 'Listening…';
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

document.getElementById('saveMemoryBtn').addEventListener('click', async () => {
  const title = document.getElementById('memTitle').value.trim();
  const body_text = document.getElementById('memBody').value.trim();
  if (!body_text) {
    alert('Add a note first');
    return;
  }
  const asset_ref = teachContext
    ? `${teachContext.type || 'evidence'}:${teachContext.id || ''}`
    : null;
  try {
    const data = await readJson(await fetch('/api/memories', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kind: 'voice_note', title: title || null, body_text, asset_ref }),
    }));
    if (data.archive_updated) showArchiveUpdated();
    document.getElementById('memBody').value = '';
  } catch (err) {
    alert(err.message || String(err));
  }
});

async function refreshPeople() {
  const q = document.getElementById('peopleSearch').value.trim();
  const url = q ? `/api/people?q=${encodeURIComponent(q)}` : '/api/people';
  const list = document.getElementById('peopleList');
  list.innerHTML = '<li class="quiet">Loading…</li>';
  document.getElementById('personDetail').hidden = true;
  try {
    const data = await readJson(await fetch(url));
    peopleCache = data.people || [];
    if (!peopleCache.length) {
      list.innerHTML = '<li class="quiet">No people found in HVRT / memorybox hubs.</li>';
      return;
    }
    list.innerHTML = peopleCache.map((p, idx) => `
      <li data-idx="${idx}" tabindex="0" role="button">
        <h3>${escapeHtml(p.name)}</h3>
        <p class="snippet">${escapeHtml(p.snippet || p.role || '')}</p>
        <p class="quiet">${(p.sources || []).join(' · ')}${p.face_hits ? ` · ${p.face_hits} faces` : ''}</p>
      </li>`).join('');
    list.querySelectorAll('li[data-idx]').forEach(li => {
      const open = () => openPerson(Number(li.dataset.idx));
      li.addEventListener('click', open);
      li.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); }
      });
    });
  } catch (err) {
    list.innerHTML = `<li class="quiet">${escapeHtml(err.message || String(err))}</li>`;
  }
}

async function openPerson(idx) {
  const p = peopleCache[idx];
  if (!p) return;
  document.querySelectorAll('#peopleList li').forEach(li => {
    li.classList.toggle('is-selected', Number(li.dataset.idx) === idx);
  });
  const panel = document.getElementById('personDetail');
  const body = document.getElementById('personDetailBody');
  panel.hidden = false;
  body.innerHTML = `<p class="quiet">Loading…</p>`;

  if (p.hvrt_person_id) {
    try {
      const detail = await readJson(await fetch(`/api/evidence/hvrt/person/${p.hvrt_person_id}`));
      body.innerHTML = renderDetailHtml(detail, { type: 'hvrt_person', title: p.name });
      wireDetailActions(body, detail, p);
      return;
    } catch (err) {
      body.innerHTML = `<p class="quiet">${escapeHtml(err.message || String(err))}</p>`;
      return;
    }
  }

  body.innerHTML = `
    <h2 class="edit-title">${escapeHtml(p.name)}</h2>
    <p class="quiet">${escapeHtml(p.role || '')} · ${(p.sources || []).join(' · ')}</p>
    <p class="snippet">${escapeHtml(p.snippet || '')}</p>
    <div class="actions">
      <button type="button" class="primary" id="askThisPerson">Ask about ${escapeHtml(p.name)}</button>
      <button type="button" class="ghost" data-open-review-name="${escapeHtml(p.name)}">Open in Review</button>
    </div>`;
  body.querySelector('#askThisPerson')?.addEventListener('click', () => {
    setView('ask');
    document.getElementById('askInput').value = p.name;
    document.getElementById('askForm').requestSubmit();
  });
  wireDetailActions(body, { title: p.name, review_name: p.name }, p);
}

document.getElementById('personDetailClose').onclick = () => {
  document.getElementById('personDetail').hidden = true;
};
document.getElementById('peopleRefresh').onclick = refreshPeople;
document.getElementById('peopleSearch').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') refreshPeople();
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

document.getElementById('editCancel').onclick = () => document.getElementById('editDialog').close();
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
  } catch (err) {
    alert(err.message || String(err));
  }
});

fetch('/api/config').then(r => r.json()).then(c => {
  cfg = c;
  const s = c.sources || {};
  const bits = [];
  if (s.hvrt_present) bits.push('HVRT');
  if (s.memorybox_present) bits.push('email/SMS');
  if (s.immich_configured) bits.push('Immich');
  document.getElementById('askHint').textContent = bits.length
    ? `Searching ${bits.join(' + ')}${c.hvrt_mounted ? ' · Review embedded' : ''}`
    : 'POC databases not found';
}).catch(() => {});
