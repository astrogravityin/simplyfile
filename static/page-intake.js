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

async function mapper(host, cid, ay, fid) {
  const url = `/api/intake/${cid}/${encodeURIComponent(ay)}/${fid}`;
  let v = await api(url);
  let only = false;
  host.innerHTML = pageHead(v.file.name, `<span class="tag brand">${esc(w('form_is', { form: v.form }))}</span> <span id="in-counts"></span>`,
    `<button type="button" class="ghost" id="in-back">${icon('left', 14)} ${esc(w('back'))}</button>
     <select id="in-only" aria-label="${esc(w('filter'))}"><option value="">${esc(w('f_all'))}</option><option value="1">${esc(w('f_open'))}</option></select>
     <button type="button" class="ghost" id="in-accept">${icon('check', 14)} ${esc(w('accept_all'))}</button>
     <button type="button" id="in-save">${icon('save', 14)} ${esc(w('save'))}</button>`)
    + `<section class="card"><p class="small muted">${esc(w('ref_hint'))}</p><div style="overflow-x:auto"><table class="tbl" style="width:100%">
      <thead><tr><th>${esc(w('h_row'))}</th><th>${esc(w('h_label'))}</th><th style="text-align:right">${esc(w('h_numbers'))}</th><th>${esc(w('h_ref'))}</th></tr></thead>
      <tbody id="in-rows"></tbody></table></div></section>`;
  const body = host.querySelector('#in-rows');
  const draw = () => {
    host.querySelector('#in-counts').innerHTML = countTags(v.counts);
    body.innerHTML = v.rows.filter((x) => !only || ps('intake').open_states.includes(x.state)).map((x) => `<tr data-k="${esc(x.key)}">
      <td class="small muted" style="white-space:nowrap">${esc(x.key)}</td>
      <td><b>${esc(x.label || '—')}</b>${x.heading ? `<div class="small muted">${esc(x.heading.slice(0, ps('intake').heading_chars))}</div>` : ''}</td>
      <td class="small" style="text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums">${x.numbers.slice(0, ps('intake').numbers_shown).map(money).join('<br>')}</td>
      <td style="min-width:240px"><input data-ref value="${esc(x.ref)}" placeholder="${esc(x.suggestion)}" aria-label="${esc(w('h_ref'))}" style="width:100%"/>
        <div class="row tight small"><span class="${tagOf(x.state)}">${esc(w(`s_${x.state}`))}</span>
        ${x.from === 'file' ? `<span class="muted">${esc(w('from_file'))}</span>` : ''}
        ${x.suggestion ? `<button type="button" class="small ghost" data-use>${esc(w('use'))}: ${esc(x.suggestion)}</button>` : ''}</div></td></tr>`).join('');
    body.querySelectorAll('[data-use]').forEach((b) => {
      b.onclick = () => { const r = b.closest('tr'); r.querySelector('[data-ref]').value = v.rows.find((x) => x.key === r.dataset.k).suggestion; };
    });
  };
  draw();
  host.querySelector('#in-back').onclick = () => go({ c: cid, ay });
  host.querySelector('#in-only').onchange = (e) => { only = !!e.target.value; draw(); };
  host.querySelector('#in-accept').onclick = (e) => busy(e.currentTarget, async () => {
    try { v = await api(`${url}/accept`, { method: 'POST' }); toast(w('saved'), 'ok'); draw(); } catch (err) { toast(err.message, 'bad', 8); }
  });
  host.querySelector('#in-save').onclick = (e) => busy(e.currentTarget, async () => {
    const was = Object.fromEntries(v.rows.map((x) => [x.key, x.ref]));
    const tags = {};
    body.querySelectorAll('tr[data-k]').forEach((r) => {
      const val = r.querySelector('[data-ref]').value.trim();
      if (val !== (was[r.dataset.k] || '')) tags[r.dataset.k] = val;
    });
    try { v = await api(`${url}/tags`, { method: 'PUT', body: { tags } }); toast(w('saved'), 'ok'); draw(); } catch (err) { toast(err.message, 'bad', 8); }
  });
}
