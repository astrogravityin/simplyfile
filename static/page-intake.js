// Intake & map - SimplyFile phase 2. #/intake picks a client; #/intake?c=<id>&ay=<AY> lists that year's statements;
// &f=<file> maps one file's rows: each row with a figure shows its SF Ref (saved, from the file's own column, or a
// suggestion to Use), "Accept all suggestions", "Save refs", and the workbook back with the SF Ref column filled.
// Every word is chip ui.intake; refs are checked on the server (chip intake.ref).
import { api, BASE, esc, toast, busy, pageHead, confirmDialog, t, ps, loadWords, listBox, uploadBox, when, may } from './app.js';
import { icon } from './icons.js';

const w = (k, v) => t('intake', k, v);
const q = () => new URLSearchParams((location.hash.split('?')[1]) || '');
const go = (p) => { location.hash = `#/intake?${new URLSearchParams(p)}`; };
const money = (n) => Number(n).toLocaleString(ps('intake').money_locale, { maximumFractionDigits: ps('intake').money_digits });
const tagOf = (state) => ps('intake').state_tag[state];     // chip page.intake

export async function intakePage(host) {
  await loadWords('intake');
  const p = q();
  if (!p.get('c')) return clientPicker(host, 'intake');
  const K = await api('/api/clients/settings');
  const ay = p.get('ay') || K.current_ay;
  if (p.get('f')) return mapper(host, p.get('c'), ay, p.get('f'));
  return filesView(host, p.get('c'), ay, K);
}

// The client picker every Filing screen opens with (Intake & map, Reconcile ...): one list, Choose sets ?c=.
export function clientPicker(host, screen) {
  host.innerHTML = pageHead(w('pick'), esc(w('pick_lede'))) + '<section class="card" id="in-pick"></section>';
  listBox(host.querySelector('#in-pick'), {
    list: 'clients',
    row: (r) => `<div class="kw-row small" data-id="${esc(r.id)}"><div class="kw-info"><b>${esc(r.name)}</b>
      <span class="muted">${esc(r.pan)} · ${esc(r.status)} · ${esc(r.form)}</span></div>
      <div class="row tight"><button type="button" class="small" data-choose>${icon('right', 12)} ${esc(w('choose'))}</button></div></div>`,
    wire: (rows) => rows.querySelectorAll('[data-id]').forEach((el) => {
      el.querySelector('[data-choose]').onclick = () => { location.hash = `#/${screen}?c=${encodeURIComponent(el.dataset.id)}`; };
    }),
  });
}

const countTags = (c) => ['tagged', 'suggested', 'untagged', 'invalid'].filter((k) => c[k])
  .map((k) => `<span class="${tagOf(k)}">${esc(w(`c_${k}`, { n: c[k] }))}</span>`).join(' ');

async function filesView(host, cid, ay, K) {
  const d = await api(`/api/intake/${cid}/${encodeURIComponent(ay)}`);
  const base = `/api/intake/${cid}/${encodeURIComponent(ay)}`;
  host.innerHTML = pageHead(`${w('title')} · ${d.client.name}`,
    `${esc(d.client.pan)} · ${esc(d.client.status)} · <span class="tag brand">${esc(w('form_is', { form: d.form }))}</span> ${esc(w('lede'))}`,
    `<select id="in-ay" aria-label="${esc(w('ay'))}">${K.years.map((y) => `<option ${y === ay ? 'selected' : ''}>${esc(y)}</option>`).join('')}</select>
     <button type="button" class="ghost" id="in-change">${icon('users', 14)} ${esc(w('change'))}</button>
     <button type="button" id="in-up">${icon('upload', 14)} ${esc(w('upload'))}</button>`)
    + `<section class="card">${d.files.length ? d.files.map((f) => `<div class="kw-row small" data-f="${esc(f.id)}" data-name="${esc(f.name)}">
        <div class="kw-info"><b>${esc(f.name)}</b> <span class="muted">${esc(w('uploaded_at', { when: when(f.uploaded_at) }))} · ${esc(w('c_rows', { n: f.counts.rows }))}</span>
          ${countTags(f.counts)} ${f.pan_seen ? '' : `<span class="tag warn">${icon('alert', 11)} ${esc(w('pan_missing'))}</span>`}</div>
        <div class="row tight">
          <button type="button" class="small" data-map>${icon('link', 12)} ${esc(w('open'))}</button>
          <a class="small ghost button" href="${BASE}${base}/${esc(f.id)}/download">${icon('download', 12)} ${esc(w('download'))}</a>
          ${may('intake', 'delete') ? `<button type="button" class="small ghost" data-del>${icon('trash', 12)}</button>` : ''}</div></div>`).join('')
      : `<p class="small muted">${esc(w('no_files'))}</p>`}</section>`;
  host.querySelector('#in-ay').onchange = (e) => go({ c: cid, ay: e.target.value });
  host.querySelector('#in-change').onclick = () => go({});
  host.querySelector('#in-up').onclick = () => uploadBox(w('upload'), ['.xls', '.xlsx', '.csv'], base, () => filesView(host, cid, ay, K));
  host.querySelectorAll('[data-f]').forEach((el) => {
    el.querySelector('[data-map]').onclick = () => go({ c: cid, ay, f: el.dataset.f });
    const del = el.querySelector('[data-del]');
    if (del) del.onclick = () => confirmDialog(w('delete_title', { name: el.dataset.name }), w('delete_body'), async () => {
      try { await api(`${base}/${el.dataset.f}`, { method: 'DELETE' }); toast(w('deleted'), 'ok'); filesView(host, cid, ay, K); }
      catch (err) { toast(err.message, 'bad', 8); }
    }, w('delete'), { tone: 'danger' });
  });
}

// The donut: one arc per row state, in the chip's order and colours (page.intake ring), done = the chip's done_states.
function ring(c) {
  const P = ps('intake'), R = 30, L = 2 * Math.PI * R, n = c.rows || 1;
  let at = 0;
  const arcs = P.ring.filter((s) => c[s]).map((s) => {
    const len = (c[s] / n) * L;
    const arc = `<circle r="${R}" cx="40" cy="40" fill="none" stroke="var(${P.ring_color[s]})" stroke-width="9" stroke-linecap="butt"
      stroke-dasharray="${len.toFixed(2)} ${(L - len).toFixed(2)}" stroke-dashoffset="${(-at).toFixed(2)}"/>`;
    at += len;
    return arc;
  }).join('');
  const done = P.done_states.reduce((a, s) => a + (c[s] || 0), 0);
  return `<svg class="sf-ring" viewBox="0 0 80 80" role="img" aria-label="${esc(w('progress', { done, n: c.rows }))}">
      <circle r="${R}" cx="40" cy="40" fill="none" stroke="var(--line)" stroke-width="9"/>
      <g transform="rotate(-90 40 40)">${arcs}</g>
      <text x="40" y="38" text-anchor="middle" class="sf-ring-pct">${Math.round((done / n) * 100)}%</text>
      <text x="40" y="52" text-anchor="middle" class="sf-ring-sub">${done}/${c.rows}</text></svg>`;
}

async function mapper(host, cid, ay, fid) {
  const url = `/api/intake/${cid}/${encodeURIComponent(ay)}/${fid}`;
  let v = await api(url);
  let only = false;
  const dirty = new Set();
  host.innerHTML = pageHead(v.file.name, `<span class="tag brand">${esc(w('form_is', { form: v.form }))}</span>`,
    `<button type="button" class="ghost" id="in-back">${icon('left', 14)} ${esc(w('back'))}</button>`)
    + `<section class="card sf-sum"><div id="in-ring"></div><div class="sf-sum-txt"><b id="in-progress"></b>
        <div class="sf-legend" id="in-legend"></div></div>
        <div class="tabs sf-only" role="tablist" aria-label="${esc(w('filter'))}">${[['', w('f_all')], ['1', w('f_open')]].map(([id, label]) =>
          `<button type="button" role="tab" data-only="${id}" class="${id ? '' : 'on'}">${esc(label)}</button>`).join('')}</div></section>
      <section class="card sf-map"><p class="small muted">${icon('info', 13)} ${esc(w('ref_hint'))}</p><div class="sf-tbl-wrap"><table class="tbl sf-tbl">
      <thead><tr><th>${esc(w('h_row'))}</th><th>${esc(w('h_label'))}</th><th class="num">${esc(w('h_numbers'))}</th><th>${esc(w('h_ref'))}</th></tr></thead>
      <tbody id="in-rows"></tbody></table></div></section>
      <div class="sf-bar" role="region" aria-label="${esc(w('save'))}"><span class="sf-bar-state" id="in-state"></span><span class="spacer"></span>
        <button type="button" class="ghost" id="in-accept">${icon('check', 14)} ${esc(w('accept_all'))}</button>
        <button type="button" class="primary" id="in-save">${icon('save', 15)} ${esc(w('save'))}</button></div>`;
  const body = host.querySelector('#in-rows');
  const state = () => {
    const el = host.querySelector('#in-state');
    el.className = `sf-bar-state ${dirty.size ? 'is-dirty' : 'is-clean'}`;
    el.innerHTML = `<span class="sf-dot"></span>${esc(dirty.size ? w('unsaved', { n: dirty.size }) : w('all_saved'))}`;
    host.querySelector('#in-save').disabled = !dirty.size;
    host.querySelector('#in-accept').disabled = !v.counts.suggested;
  };
  const draw = () => {
    const c = v.counts, P = ps('intake');
    host.querySelector('#in-ring').innerHTML = ring(c);
    host.querySelector('#in-progress').textContent = w('progress', { done: P.done_states.reduce((a, s) => a + (c[s] || 0), 0), n: c.rows });
    host.querySelector('#in-legend').innerHTML = P.ring.filter((s) => c[s]).map((s) =>
      `<span class="sf-key"><i style="background:var(${P.ring_color[s]})"></i>${esc(w(`c_${s}`, { n: c[s] }))}</span>`).join('');
    const rows = v.rows.filter((x) => !only || P.open_states.includes(x.state));
    body.innerHTML = rows.length ? rows.map((x) => `<tr data-k="${esc(x.key)}" class="st-${esc(x.state)}">
      <td><span class="sf-rowno">${esc(x.key)}</span></td>
      <td><div class="sf-label">${esc(x.label || '—')}</div>${x.heading ? `<div class="small muted">${esc(x.heading.slice(0, P.heading_chars))}</div>` : ''}</td>
      <td class="num">${x.numbers.slice(0, P.numbers_shown).map((n) => `<div>${money(n)}</div>`).join('')}</td>
      <td class="sf-refcell"><div class="sf-ref"><span class="sf-state" title="${esc(w(`s_${x.state}`))}"></span>
          <input data-ref value="${esc(x.ref)}" placeholder="${esc(x.suggestion || w('ref_placeholder'))}" aria-label="${esc(w('h_ref'))}"/></div>
        <div class="sf-ref-meta"><span class="${tagOf(x.state)}">${esc(w(`s_${x.state}`))}</span>
        ${x.from === 'file' ? `<span class="muted">${esc(w('from_file'))}</span>` : ''}
        ${x.suggestion && x.state === 'suggested' ? `<button type="button" class="sf-use" data-use>${icon('spark', 12)} ${esc(w('use'))} <b>${esc(x.suggestion)}</b></button>` : ''}</div></td></tr>`).join('')
      : `<tr><td colspan="4" class="sf-empty">${icon('check', 18)} ${esc(w('none_open'))}</td></tr>`;
    body.querySelectorAll('tr[data-k]').forEach((r) => {
      const inp = r.querySelector('[data-ref]');
      const was = v.rows.find((x) => x.key === r.dataset.k).ref || '';
      if (dirty.has(r.dataset.k)) r.classList.add('is-dirty');
      inp.oninput = () => { const ch = inp.value.trim() !== was; dirty[ch ? 'add' : 'delete'](r.dataset.k); r.classList.toggle('is-dirty', ch); state(); };
      const use = r.querySelector('[data-use]');
      if (use) use.onclick = () => { inp.value = v.rows.find((x) => x.key === r.dataset.k).suggestion; inp.oninput(); };
    });
    state();
  };
  const pending = () => Object.fromEntries([...body.querySelectorAll('tr[data-k]')].filter((r) => dirty.has(r.dataset.k))
    .map((r) => [r.dataset.k, r.querySelector('[data-ref]').value.trim()]));
  draw();
  host.querySelector('#in-back').onclick = () => go({ c: cid, ay });
  host.querySelectorAll('[data-only]').forEach((b) => {
    b.onclick = () => { only = !!b.dataset.only; host.querySelectorAll('[data-only]').forEach((x) => x.classList.toggle('on', x === b)); draw(); };
  });
  host.querySelector('#in-accept').onclick = (e) => busy(e.currentTarget, async () => {
    try { v = await api(`${url}/accept`, { method: 'POST' }); toast(w('saved'), 'ok'); draw(); } catch (err) { toast(err.message, 'bad', 8); }
  });
  host.querySelector('#in-save').onclick = (e) => busy(e.currentTarget, async () => {
    try { v = await api(`${url}/tags`, { method: 'PUT', body: { tags: pending() } }); dirty.clear(); toast(w('saved'), 'ok'); draw(); }
    catch (err) { toast(err.message, 'bad', 8); }
  });
}
