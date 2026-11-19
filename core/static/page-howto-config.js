// How to Use pages — the training links each of THIS portal's screens carries, shown as a "How to Use"
// button in its top bar (and on the sign-in screen). Master / detail: every page on the left with its
// count of live links, the selected page's links on the right, edited in place.
// 2026-09-28 owner: the same detail also holds the page's Guide me - import a Guide me script (from the Guide Me
// Builder), pick its voice, save; the top bar's Guide me button follows (core/guide.py, chip guide.<screen>).
import { api, BASE, esc, toast, busy, pageHead, confirmDialog, modal, pickList, t, loadWords, dropZone, wireDrops } from './ui.js';
import { refresh } from './shell.js';
import { icon } from './icons.js';
import { voices, speakLine } from './guide-kit.js';

// Every word on this screen is chip ui.howto_config (core/words.py) - none is written here.
const w = (k, v) => t('howto_config', k, v);
const TYPES = ['doc', 'youtube', 'video', 'instagram', 'link'];
const KIND = { doc: 'book', youtube: 'play', video: 'film', instagram: 'image', link: 'link' };
let selected = '';
let draft = [];
let data = null;

const live = (id) => (data.links[id] || []).filter((l) => l.active !== false).length;

export async function howtoConfigPage(host) {
  await loadWords('howto_config');
  data = await api('/api/core/howto/all');
  if (!data.pages.some((p) => p.id === selected)) selected = data.pages[0].id;
  const covered = data.pages.filter((p) => live(p.id)).length;
  host.innerHTML = `${pageHead(w('title'), w('lede', { covered, total: data.pages.length }))}
    <div class="panes">
      <div class="pane"><div class="top"><span class="finder">${icon('search', 15)}<input id="hc-find" placeholder="${esc(w('find_placeholder'))}"/></span></div>
        <div class="scrollbody"><div class="list" id="hc-list"></div></div></div>
      <div class="pane"><div class="scrollbody pad" id="hc-detail"></div></div>
    </div>`;
  const drawList = (term = '') => {
    const rows = data.pages.filter((p) => `${p.label} ${p.group}`.toLowerCase().includes(term.toLowerCase()));
    const groups = [...new Set(rows.map((p) => p.group || ''))];
    host.querySelector('#hc-list').innerHTML = groups.map((g) => `<div class="grp">${esc(g)}</div>` + rows.filter((p) => (p.group || '') === g)
      .map((p) => `<button type="button" data-page="${esc(p.id)}" class="${p.id === selected ? 'on' : ''}">
        <span class="nm">${esc(p.label)}</span><span class="badge ${live(p.id) ? '' : 'zero'}">${live(p.id)}</span></button>`).join('')).join('')
      || `<div class="none">${esc(w('no_match'))}</div>`;
    host.querySelectorAll('[data-page]').forEach((b) => { b.onclick = () => { selected = b.dataset.page; drawList(term); detail(host); }; });
  };
  host.querySelector('#hc-find').oninput = (e) => drawList(e.target.value);
  drawList();
  detail(host);
}

function detail(host) {
  const page = data.pages.find((p) => p.id === selected);
  draft = (data.links[selected] || []).map((l) => ({ ...l }));
  const outer = host.querySelector('#hc-detail');
  outer.innerHTML = '<div id="hc-links"></div><section class="gm" id="hc-guide"></section>';
  const box = outer.querySelector('#hc-links');
  guideSection(outer.querySelector('#hc-guide'), page);
  const draw = () => {
    box.innerHTML = `<div class="row between"><h2 style="margin:0">${esc(page.label)}</h2>
        <code class="small">#/${esc(page.id)}</code></div>
      <p class="small muted">${w('hint')}</p>
      ${draft.length ? draft.map((l, i) => `<div class="linkrow ${l.active === false ? 'off' : ''}">
          <span class="t-${esc(l.type || 'link')}">${icon(KIND[l.type] || 'link', 18)}</span>
          <div class="stack2"><input data-f="label" data-i="${i}" value="${esc(l.label)}" placeholder="${esc(w('label_placeholder'))}"/>
            <input data-f="url" data-i="${i}" value="${esc(l.url)}" placeholder="https://youtu.be/…"/></div>
          <div class="kind"><select data-f="type" data-i="${i}" aria-label="${esc(w('type_label'))}">${['auto', ...TYPES].map((t) =>
            `<option ${(l.type || 'auto') === t ? 'selected' : ''}>${t}</option>`).join('')}</select>
            <label class="check"><input type="checkbox" data-f="active" data-i="${i}" ${l.active === false ? '' : 'checked'}/> ${w('live')}</label></div>
          <button class="small danger icon" type="button" data-drop="${i}" title="${esc(w('remove'))}">${icon('close', 15)}</button>
        </div>`).join('')
      : `<div class="empty">${icon('help', 36)}<h3>${w('empty_title')}</h3><p>${w('empty_body')}</p></div>`}
      <div class="row" style="margin-top:14px">
        <button type="button" id="hc-add">${icon('plus')} ${w('add')}</button>
        <button type="button" id="hc-rec">${icon('play')} ${w('add_recording')}</button><span class="spacer"></span>
        ${live(selected) ? `<a class="small" href="${BASE}/#/${esc(page.id)}" target="_blank" rel="noopener">${icon('external', 13)} ${w('see_page')}</a>` : ''}
        <button class="primary" type="button" id="hc-save">${icon('save')} ${w('save')}</button></div>`;
    box.querySelectorAll('[data-f]').forEach((el) => {
      el.oninput = el.onchange = () => {
        const l = draft[Number(el.dataset.i)];
        if (el.dataset.f === 'active') l.active = el.checked;
        else if (el.dataset.f === 'type') l.type = el.value === 'auto' ? '' : el.value;
        else l[el.dataset.f] = el.value;
      };
    });
    // 2026-09-22 owner: "delete has no App Warning" - a link is removed only after an App Message says yes
    box.querySelectorAll('[data-drop]').forEach((b) => {
      b.onclick = () => {
        const l = draft[Number(b.dataset.drop)] || {};
        if (!String(l.label || '').trim() && !String(l.url || '').trim()) { draft.splice(Number(b.dataset.drop), 1); draw(); return; }  // an empty row holds nothing
        confirmDialog(w('remove_title'), w('remove_body', { label: l.label || l.url }),
          () => { draft.splice(Number(b.dataset.drop), 1); draw(); }, w('remove'), { tone: 'danger' });
      };
    });
    box.querySelector('#hc-add').onclick = () => { draft.push({ label: '', url: '', type: '', active: true }); draw(); };
    // 2026-09-24 owner: a screen's How to Use is chosen HERE (how to make a video, the same for everyone) - never a card on
    // every recording's page. The portal lists the recordings it can play (GET /api/help/recordings).
    // 2026-10-01 (Phase 3): one search box over list help_recordings - never every recording in the dialog
    box.querySelector('#hc-rec').onclick = () => modal(w('add_recording'), '<div id="hc-recpick"></div>', {
      onOpen: (m, close) => pickList(m.querySelector('#hc-recpick'), { list: 'help_recordings', name: (r) => r.title || r.url,
        onPick: (r) => { draft.push({ label: r.title, url: r.url, type: '', active: true }); close(); draw(); } }) });
    box.querySelector('#hc-save').onclick = (e) => busy(e.currentTarget, async () => {
      try {
        const r = await api(`/api/core/howto/${encodeURIComponent(selected)}`, { method: 'PUT', body: { links: draft } });
        data.links[selected] = r.links;
        toast(w(r.links.length ? 'saved_live' : 'saved_none'), 'ok');
        await refresh();
        const badge = host.querySelector(`[data-page="${CSS.escape(selected)}"] .badge`);
        if (badge) { badge.textContent = live(selected); badge.classList.toggle('zero', !live(selected)); }
        detail(host);
      } catch (err) { toast(err.message, 'bad'); }
    });
  };
  draw();
}

// --- Guide me for the selected page ----------------------------------------------------------------------------
async function guideSection(sec, page) {
  let view;
  try { view = await api(`/api/core/guide-admin/${encodeURIComponent(page.id)}`); } catch { sec.hidden = true; return; }
  if (view.guidable === false) { sec.hidden = true; return; }      // e.g. the sign-in page: no guide, no error
  const vc = { ...(view.settings || {}), ...(view.voice || {}) };
  const names = () => voices().map((v) => v.name);
  const draw = (problems = []) => {
    sec.innerHTML = `<h3 class="row" style="gap:8px;margin:22px 0 6px">${icon('spark', 16)} ${w('gm_h')}</h3>
      <p class="small">${view.has ? `${w('gm_have', { title: esc(view.title), n: view.steps })} ${w(view.source === 'data' ? 'gm_imported' : 'gm_shipped')}` : w('gm_none')}</p>
      ${view.has ? `<div class="gm-voice">
        <label class="field"><span>${w('gm_voice')}</span><select id="gm-name"><option value="">${esc(w('gm_voice_auto'))}</option>
          ${names().map((n) => `<option ${n === vc.voice_name ? 'selected' : ''}>${esc(n)}</option>`).join('')}</select></label>
        <label class="field"><span>${w('gm_rate')} <b id="gm-rate-v">${Number(vc.rate || 1).toFixed(2)}</b></span>
          <input type="range" id="gm-rate" min="0.5" max="2" step="0.02" value="${Number(vc.rate || 1)}"/></label>
        <label class="field"><span>${w('gm_pitch')} <b id="gm-pitch-v">${Number(vc.pitch || 1).toFixed(2)}</b></span>
          <input type="range" id="gm-pitch" min="0" max="2" step="0.05" value="${Number(vc.pitch || 1)}"/></label>
        <div class="row"><button type="button" id="gm-try">${icon('speaker', 14)} ${w('gm_try')}</button>
          <button type="button" class="primary" id="gm-save">${icon('save')} ${w('gm_save_voice')}</button><span class="spacer"></span>
          <a class="small" href="${BASE}/#/${esc(page.id)}" target="_blank" rel="noopener">${icon('external', 13)} ${w('gm_open')}</a></div>
        ${'speechSynthesis' in window ? '' : `<p class="small muted">${w('gm_no_speech')}</p>`}</div>` : ''}
      <div class="gm-import">
        ${dropZone('gm-file', { accept: '.json,application/json', title: w('gm_import'), hint: w('gm_import_hint') })}
        <textarea id="gm-text" rows="4" placeholder="${esc(w('gm_paste'))}"></textarea>
        <div class="row"><button type="button" class="primary" id="gm-import">${icon('upload', 14)} ${w('gm_import')}</button><span class="spacer"></span>
          ${view.source === 'data' ? `<button type="button" class="danger" id="gm-remove">${icon('trash', 14)} ${w('gm_remove')}</button>` : ''}</div>
        ${problems.length ? `<div class="gm-problems"><b>${w('gm_problems')}</b><ul>${problems.map((x) => `<li>${esc(x)}</li>`).join('')}</ul></div>` : ''}
      </div>`;
    wireDrops(sec);
    const setting = () => ({ ...vc, voice_name: sec.querySelector('#gm-name')?.value || '',
      rate: Number(sec.querySelector('#gm-rate')?.value || vc.rate), pitch: Number(sec.querySelector('#gm-pitch')?.value || vc.pitch) });
    ['rate', 'pitch'].forEach((k) => {
      const el = sec.querySelector(`#gm-${k}`);
      if (el) el.oninput = () => { sec.querySelector(`#gm-${k}-v`).textContent = Number(el.value).toFixed(2); };
    });
    const tryBtn = sec.querySelector('#gm-try');
    if (tryBtn) tryBtn.onclick = () => { if (!speakLine(w('gm_try_line'), setting())) toast(w('gm_no_speech'), 'warn'); };
    const save = sec.querySelector('#gm-save');
    if (save) {
      save.onclick = (e) => busy(e.currentTarget, async () => {
        const v = setting();
        try {
          view = await api(`/api/core/guide-admin/${encodeURIComponent(page.id)}/voice`, { method: 'PUT',
            body: { voice: { voice_name: v.voice_name, rate: v.rate, pitch: v.pitch } } });
          Object.assign(vc, view.voice);
          toast(w('gm_voice_saved'), 'ok');
          draw();
        } catch (err) { draw(err.data?.problems || []); toast(err.message, 'bad'); }
      });
    }
    sec.querySelector('#gm-import').onclick = (e) => busy(e.currentTarget, async () => {
      const f = sec.querySelector('#gm-file').files[0];
      const text = f ? await f.text() : sec.querySelector('#gm-text').value.trim();
      if (!text) { toast(w('gm_pick_first'), 'warn'); return; }
      try {
        view = await api(`/api/core/guide-admin/${encodeURIComponent(page.id)}/script`, { method: 'PUT', body: { script_text: text } });
        Object.assign(vc, view.settings || {}, view.voice || {});
        toast(w('gm_imported_ok'), 'ok');
        await refresh();
        draw();
      } catch (err) { draw(err.data?.problems || []); toast(err.message, 'bad'); }
    });
    const rm = sec.querySelector('#gm-remove');
    if (rm) {
      rm.onclick = () => confirmDialog(w('gm_remove_title'), w('gm_remove_body'), async () => {
        try {
          view = await api(`/api/core/guide-admin/${encodeURIComponent(page.id)}`, { method: 'DELETE' });
          toast(w('gm_removed'), 'ok');
          await refresh();
          draw();
        } catch (err) { toast(err.message, 'bad'); }
      }, w('gm_remove'), { tone: 'danger' });
    }
  };
  draw();
  if (!names().length && 'speechSynthesis' in window) {   // the browser lists its voices a moment after load
    try { speechSynthesis.addEventListener('voiceschanged', () => { if (sec.isConnected) draw(); }, { once: true }); } catch { /* old browser */ }
  }
}
