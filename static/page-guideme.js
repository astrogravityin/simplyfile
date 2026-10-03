// Guide Me Builder (SteadyMove, 2026-09-28): bring a Guide Me script (format guide-me/1), have the server check it,
// preview it as the live tour, and export the complete code for any page of any site (guideme.py).
// Home = the import box + this person's builds (one searched page at a time, chip guideme.list_view).
// An open build = its facts, its steps, Preview / Export / Replace script / Delete. Every word: chip ui.guideme.
import { api, BASE, esc, toast, busy, pageHead, modal, confirmDialog, t, loadWords, dropZone, wireDrops, state, when } from './app.js';
import { icon, emptyState } from './icons.js';
import { openTour } from '../core-static/guide-kit.js';

const w = (k, v) => t('guideme', k, v);
const sw = (k, v) => t('shell', k, v);      // the portal's own words: Cancel, Delete, Close - one word everywhere
let view = { q: '', page: 1 };
let current = null;                      // the open build (with its script), or null = Home

export async function guidemePage(host) {
  await loadWords('guideme');
  if (current) return build(host);
  host.innerHTML = pageHead(w('title'), w('lede')) + `
    <section class="card" id="gm-import">
      <h2>${icon('upload', 17)} ${esc(w('import_title'))}</h2>
      <p class="small muted">${esc(w('import_line'))}</p>
      ${importFields('gm')}
      <div class="row" style="margin-top:12px"><button type="button" class="primary" id="gm-create">${icon('spark', 15)} ${esc(w('create'))}</button></div>
    </section>
    <section class="card" id="gm-list">
      <h2>${icon('book', 17)} ${esc(w('list_title'))}</h2>
      <div class="row tight"><input id="gm-q" type="search" value="${esc(view.q)}" placeholder="${esc(w('search_ph'))}" aria-label="${esc(w('search_ph'))}" autocomplete="off" style="max-width:320px"/>
        <span class="small muted" id="gm-count"></span></div>
      <div id="gm-rows" style="margin-top:10px"></div>
      <div class="row tight" id="gm-pager"></div>
    </section>`;
  wireImport(host, 'gm', host.querySelector('#gm-create'), async (body) => {
    const row = await api('/api/guideme', { method: 'POST', body });
    toast(row.message, 'ok');
    current = row;
    build(host);
  });
  let wait = 0;
  host.querySelector('#gm-q').oninput = (e) => { clearTimeout(wait); wait = setTimeout(() => { view.q = e.target.value; view.page = 1; load(host); }, 250); };
  await load(host);
}

/** The drop zone, the paste box and the place the problems are listed - the same on Home and in Replace script. */
function importFields(p) {
  return `${dropZone(`${p}-file`, { accept: '.json,application/json', title: w('drop_title'), hint: w('drop_hint') })}
    <label class="small" for="${p}-text" style="display:block;margin-top:12px">${esc(w('paste_label'))}</label>
    <textarea id="${p}-text" rows="7" spellcheck="false" placeholder="${esc(w('paste_ph'))}" style="width:100%;font-family:ui-monospace,monospace;font-size:12.5px"></textarea>
    <div id="${p}-problems"></div>`;
}

/** Wires one import: the chosen file wins over the box; the server checks, and any problems are listed in full. */
function wireImport(root, p, button, send) {
  wireDrops(root);
  const box = root.querySelector(`#${p}-problems`);
  button.onclick = () => busy(button, async () => {
    box.innerHTML = '';
    const file = root.querySelector(`#${p}-file`).files[0];
    let text = root.querySelector(`#${p}-text`).value;
    if (file) {
      try { text = await file.text(); } catch { toast(w('file_unread'), 'bad'); return; }
    }
    if (!text.trim()) { toast(w('need_script'), 'warn'); return; }
    try { await send({ script_text: text }); } catch (err) {
      const list = (err.data && err.data.problems) || [];
      if (!list.length) { toast(err.message, 'bad', 8); return; }
      box.innerHTML = `<div class="note bad" style="margin-top:12px">${icon('alert')}<div><b>${esc(err.message)}</b>
        <p class="small" style="margin:6px 0 4px">${esc(w('problems_title'))}</p>
        <ul class="small" style="margin:0;padding-left:18px">${list.map((x) => `<li>${esc(x)}</li>`).join('')}</ul></div></div>`;
      box.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  });
}

async function load(host) {
  const d = await api(`/api/guideme?${new URLSearchParams({ q: view.q, page: view.page })}`);
  view.page = d.page;
  host.querySelector('#gm-count').textContent = d.total_all ? w('count', { n: d.total_all }) : '';
  const rows = host.querySelector('#gm-rows');
  rows.innerHTML = d.rows.length ? `<div class="scroll"><table><thead><tr>
      <th>${esc(w('col_title'))}</th><th>${esc(w('col_portal'))}</th><th>${esc(w('col_page'))}</th><th>${esc(w('col_steps'))}</th><th>${esc(w('col_updated'))}</th><th></th></tr></thead>
      <tbody>${d.rows.map((r) => `<tr>
        <td><b>${esc(r.title)}</b>${r.lede ? `<br/><span class="small muted">${esc(r.lede)}</span>` : ''}</td>
        <td><span class="tag">${esc(r.portal)}</span></td><td><code>${esc(r.page)}</code></td><td>${esc(r.steps)}</td>
        <td class="small muted">${esc(when(r.updated_at))}</td>
        <td class="a"><button type="button" class="small" data-open="${esc(r.id)}">${icon('edit', 14)} ${esc(w('open'))}</button>
          <button type="button" class="small" data-export="${esc(r.id)}" data-tip="${esc(w('export_tip'))}">${icon('download', 14)} ${esc(w('export'))}</button>
          <button type="button" class="small danger icon" data-del="${esc(r.id)}" title="${esc(w('delete_tip'))}" aria-label="${esc(w('delete'))}">${icon('trash', 15)}</button></td></tr>`).join('')}</tbody></table></div>`
    : (view.q ? `<p class="small muted">${esc(w('no_match'))}</p>` : emptyState('manuals', w('none_title'), w('none_body')));
  // no greyed buttons: a pager button is simply not there at either end
  const pager = host.querySelector('#gm-pager');
  pager.innerHTML = d.pages > 1 ? `${d.page > 1 ? `<button type="button" class="small ghost" data-gm-page="${d.page - 1}">${icon('left', 12)} ${esc(w('prev'))}</button>` : ''}
    <span class="small muted">${esc(w('page', { page: d.page, pages: d.pages }))}</span>
    ${d.page < d.pages ? `<button type="button" class="small ghost" data-gm-page="${d.page + 1}">${esc(w('next'))} ${icon('right', 12)}</button>` : ''}` : '';
  pager.querySelectorAll('[data-gm-page]').forEach((b) => { b.onclick = () => { view.page = Number(b.dataset.gmPage); load(host); }; });
  const row = (id) => d.rows.find((r) => r.id === id);
  rows.querySelectorAll('[data-open]').forEach((b) => {
    b.onclick = async () => { current = await api(`/api/guideme/${encodeURIComponent(b.dataset.open)}`); build(host); };
  });
  rows.querySelectorAll('[data-export]').forEach((b) => { b.onclick = () => download(b.dataset.export); });
  rows.querySelectorAll('[data-del]').forEach((b) => {
    const r = row(b.dataset.del);
    b.onclick = () => confirmDialog(w('delete_title'), w('delete_body', { title: r.title }), () => remove(host, r.id), w('delete'), { tone: 'danger' });
  });
}

/** The zip, through a link with `download` (never a page change - the leave guard stays quiet). */
function download(id) {
  const a = document.createElement('a');
  a.href = `${BASE}/api/guideme/${encodeURIComponent(id)}/export`;
  a.download = '';
  document.body.appendChild(a);
  a.click();
  a.remove();
}

async function remove(host, id) {
  try {
    const x = await api(`/api/guideme/${encodeURIComponent(id)}`, { method: 'DELETE' });
    toast(x.message, 'ok');
    current = null;
    guidemePage(host);
  } catch (err) { toast(err.message, 'bad', 8); }
}

// --- an open build ------------------------------------------------------------------------------------

function build(host) {
  const b = current;
  const s = b.script || { steps: [] };
  const fact = (k, v) => `<div><dt class="small muted">${esc(w(k))}</dt><dd style="margin:2px 0 10px">${v}</dd></div>`;
  host.innerHTML = `<div class="row" style="justify-content:space-between;align-items:flex-start">
      <div><h1 style="margin-bottom:2px">${esc(b.title)}</h1><p class="muted small" style="margin:0"><span class="tag">${esc(b.portal)}</span> <code>${esc(b.page)}</code></p></div>
      <button type="button" id="gm-back">${icon('left', 15)} ${esc(w('all_builds'))}</button></div>
    <div class="row tight" id="gm-acts" style="margin:14px 0">
      <button type="button" class="primary" id="gm-preview" data-tip="${esc(w('preview_tip'))}">${icon('play', 15)} ${esc(w('preview'))}</button>
      <button type="button" id="gm-export" data-tip="${esc(w('export_tip'))}">${icon('download', 15)} ${esc(w('export'))}</button>
      <button type="button" id="gm-replace" data-tip="${esc(w('replace_tip'))}">${icon('upload', 15)} ${esc(w('replace'))}</button>
      <button type="button" class="ghost danger" id="gm-delete" title="${esc(w('delete_tip'))}">${icon('trash', 15)} ${esc(w('delete'))}</button>
    </div>
    <section class="card" id="gm-facts">
      <h2>${icon('info', 17)} ${esc(w('facts_title'))}</h2>
      <dl style="display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:4px 18px;margin:8px 0 0">
        ${fact('f_portal', `<span class="tag">${esc(b.portal)}</span>`)}${fact('f_page', `<code>${esc(b.page)}</code>`)}
        ${fact('f_title', esc(b.title))}${fact('f_steps', esc(b.steps))}${fact('f_minutes', esc(w('minutes', { n: s.minutes || 1 })))}
        ${fact('f_created', when(b.created_at))}${fact('f_updated', when(b.updated_at))}</dl>
      ${b.lede ? `<p class="small muted" style="margin:4px 0 0"><b>${esc(w('f_lede'))}</b> ${esc(b.lede)}</p>` : ''}
    </section>
    <section class="card" id="gm-steps">
      <h2>${icon('spark', 17)} ${esc(w('steps_title'))}</h2>
      <div class="scroll"><table><thead><tr><th>${esc(w('s_n'))}</th><th>${esc(w('s_title'))}</th><th>${esc(w('s_say'))}</th>
        <th>${esc(w('s_target'))}</th><th>${esc(w('s_open'))}</th><th>${esc(w('s_art'))}</th></tr></thead>
        <tbody>${s.steps.map((x, i) => `<tr><td>${i + 1}</td><td><b>${esc(x.title)}</b></td><td class="small">${esc(x.say)}</td>
          <td><code class="small">${esc(x.target || '')}</code></td><td><code class="small">${esc(x.open || '')}</code></td>
          <td class="small">${esc((x.art && x.art.kind) || '')}</td></tr>`).join('')}</tbody></table></div>
    </section>`;
  host.querySelector('#gm-back').onclick = () => { current = null; guidemePage(host); };
  // the kit carries no words or settings of its own: the server hands them with the build (chips ui.guide, guide.settings)
  const kit = b.kit || {};
  host.querySelector('#gm-preview').onclick = () => openTour({ ...s, settings: { ...(kit.settings || {}), ...(s.voice || {}) } },
    { words: kit.words || {}, product: state.productName || '' });
  host.querySelector('#gm-export').onclick = () => download(b.id);
  host.querySelector('#gm-replace').onclick = () => replaceScript(host);
  host.querySelector('#gm-delete').onclick = () => confirmDialog(w('delete_title'), w('delete_body', { title: b.title }), () => remove(host, b.id), w('delete'), { tone: 'danger' });
}

function replaceScript(host) {
  modal(w('replace_title'), `<p class="small muted">${esc(w('replace_line'))}</p>${importFields('gr')}`, {
    stay: true,
    footer: `<button type="button" data-cancel>${esc(sw('cancel'))}</button><button type="button" class="primary" id="gr-go">${icon('upload', 15)} ${esc(w('replace'))}</button>`,
    onOpen: (body, close) => {
      const card = body.closest('.modal');
      card.querySelector('[data-cancel]').onclick = () => close();
      wireImport(card, 'gr', card.querySelector('#gr-go'), async (sent) => {
        const row = await api(`/api/guideme/${encodeURIComponent(current.id)}/script`, { method: 'POST', body: sent });
        close();
        toast(row.message, 'ok');
        current = row;
        build(host);
      });
    } });
}
