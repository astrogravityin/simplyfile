// Intake & map - SimplyFile phase 2. #/intake picks a client; #/intake?c=<id>&ay=<AY> lists that year's statements;
// &f=<file> maps one file's rows: each row with a figure shows its SF Ref (saved, from the file's own column, or a
// suggestion to Use), "Accept all suggestions", "Save refs", and the workbook back with the SF Ref column filled.
// Every word is chip ui.intake; refs are checked on the server (chip intake.ref).
import { api, BASE, esc, toast, busy, pageHead, confirmDialog, t, ps, loadWords, listBox, uploadBox, when, may } from './app.js';
import { icon } from './icons.js';
import { hue, initials } from './page-clients.js';

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
    row: (r) => `<div class="cl-row in-pick-row" data-id="${esc(r.id)}" role="button" tabindex="0">
      <span class="cl-av" style="--h:${hue(r.name)}" aria-hidden="true">${esc(initials(r.name))}</span>
      <div class="cl-main"><div class="cl-name">${esc(r.name)}</div>
        <div class="cl-meta"><code>${esc(r.pan)}</code><span>${esc(r.status)}</span><span>${esc(r.form)}</span></div></div>
      <div class="cl-acts"><button type="button" class="small primary" data-choose>${esc(w('choose'))} ${icon('right', 13)}</button></div></div>`,
    wire: (rows) => rows.querySelectorAll('[data-id]').forEach((el) => {
      const pick = () => { location.hash = `#/${screen}?c=${encodeURIComponent(el.dataset.id)}`; };
      el.onclick = pick;
      el.onkeydown = (e) => { if (e.key === 'Enter') pick(); };
    }),
  });
}

// One thin bar per file: a segment per row state, the chip's order and colours (page.intake ring / ring_color).
function stateBar(c) {
  const P = ps('intake'), n = c.rows || 1;
  let x = 0;
  const segs = P.ring.filter((s) => c[s]).map((s) => {
    const wd = (c[s] / n) * 100;
    const r = `<rect x="${x}%" width="${wd}%" height="8" fill="var(${P.ring_color[s]})"><title>${esc(w(`c_${s}`, { n: c[s] }))}</title></rect>`;
    x += wd;
    return r;
  }).join('');
  return `<svg class="in-bar" width="100%" height="8" role="img" aria-label="${esc(w('c_rows', { n: c.rows }))}"><rect width="100%" height="8" rx="4" fill="var(--line)"/>
    <svg width="100%" height="8"><defs><clipPath id="in-bar-${x | 0}-${c.rows}"><rect width="100%" height="8" rx="4"/></clipPath></defs><g clip-path="url(#in-bar-${x | 0}-${c.rows})">${segs}</g></svg></svg>`;
}

// A spreadsheet mark: a sheet with a grid and its kind (XLSX / XLS / CSV) on a band, coloured per chip ext_color.
const sheetMark = (ext) => {
  const tone = ps('intake').ext_color[ext] || '--muted';
  return `<svg class="in-sheet" width="44" height="52" viewBox="0 0 44 52" aria-hidden="true">
    <path d="M6 2h22l12 12v32a4 4 0 0 1-4 4H6a4 4 0 0 1-4-4V6a4 4 0 0 1 4-4Z" fill="var(--panel)" stroke="var(${tone})" stroke-width="1.8"/>
    <path d="M28 2v9a3 3 0 0 0 3 3h9" fill="none" stroke="var(${tone})" stroke-width="1.8"/>
    <g stroke="var(${tone})" stroke-opacity=".45" stroke-width="1.2"><path d="M8 20h26M8 26h26M8 32h26"/><path d="M17 17v18M26 17v18"/></g>
    <rect x="4" y="37" width="36" height="11" rx="3" fill="var(${tone})"/>
    <text x="22" y="45.2" text-anchor="middle" class="in-sheet-t">${esc(String(ext).toUpperCase())}</text></svg>`;
};

const sumCounts = (files) => files.reduce((a, f) => {
  Object.entries(f.counts || {}).forEach(([k, v]) => { a[k] = (a[k] || 0) + v; });
  return a;
}, {});

async function filesView(host, cid, ay, K) {
  const d = await api(`/api/intake/${cid}/${encodeURIComponent(ay)}`);
  const base = `/api/intake/${cid}/${encodeURIComponent(ay)}`;
  const P = ps('intake');
  const all = sumCounts(d.files);
  const done = P.done_states.reduce((a, s) => a + (all[s] || 0), 0);
  host.innerHTML = pageHead(w('statements'), esc(w('lede')),
    `<label class="cl-ay" for="in-ay">${icon('clock', 14)}<span>${esc(w('ay'))}</span>
       <select id="in-ay">${K.years.map((y) => `<option ${y === ay ? 'selected' : ''}>${esc(y)}</option>`).join('')}</select></label>
     <button type="button" class="primary" id="in-up">${icon('upload', 15)} ${esc(w('upload'))}</button>`)
    + `<section class="card in-hero">
        <div class="in-who"><span class="cl-av" style="--h:${hue(d.client.name)}" aria-hidden="true">${esc(initials(d.client.name))}</span>
          <div><div class="cl-name">${esc(d.client.name)} <span class="tag brand">${esc(w('form_is', { form: d.form }))}</span></div>
          <div class="cl-meta"><code>${esc(d.client.pan)}</code><span>${esc(d.client.status)}</span></div>
          <button type="button" class="small ghost in-change" id="in-change">${icon('users', 13)} ${esc(w('change'))}</button></div></div>
        ${d.files.length ? `<div class="in-year">${ring(all)}<div class="sf-sum-txt"><b>${esc(w('year_progress', { done, n: all.rows || 0, files: d.files.length }))}</b>
          <div class="sf-legend">${P.ring.filter((s) => all[s]).map((s) => `<span class="sf-key"><i style="background:var(${P.ring_color[s]})"></i>${esc(w(`c_${s}`, { n: all[s] }))}</span>`).join('')}</div></div></div>` : ''}
        ${d.files.length && may('recon') ? `<a class="in-next" href="#/recon?c=${encodeURIComponent(cid)}&ay=${encodeURIComponent(ay)}">
          <span>${esc(w('next_recon'))}</span><b>${esc(w('reconcile'))} ${icon('right', 14)}</b></a>` : ''}</section>`
    + `<details class="in-formats"><summary>${icon('info', 14)} ${esc(w('formats_title'))}</summary>
        <p><b class="in-ok">${icon('check', 13)}</b>${esc(w('formats_ok'))}</p><p><b class="in-part">${icon('alert', 13)}</b>${esc(w('formats_partly'))}</p>
        <p><b class="in-no">${icon('ban', 13)}</b>${esc(w('formats_no'))}</p></details>`
    + (d.files.length ? `<section class="in-files">${d.files.map((f) => `<article class="in-file" data-f="${esc(f.id)}" data-name="${esc(f.name)}">
        <div class="in-file-top">${sheetMark(f.ext || String(f.name).split('.').pop())}
          <div class="in-file-id"><b title="${esc(f.name)}">${esc(f.name)}</b>
            <span class="small muted">${esc(w('uploaded_at', { when: when(f.uploaded_at) }))} · ${esc(w('c_rows', { n: f.counts.rows }))}</span>
            ${f.pan_seen ? '' : `<span class="tag warn">${icon('alert', 11)} ${esc(w('pan_missing'))}</span>`}
            ${(f.notes || []).map((n) => `<span class="in-note">${icon('info', 12)} ${esc(n)}</span>`).join('')}</div>
          ${may('intake', 'delete') ? `<button type="button" class="small ghost in-del" data-del aria-label="${esc(w('delete'))}">${icon('trash', 13)}</button>` : ''}</div>
        ${stateBar(f.counts)}
        <div class="sf-legend">${P.ring.filter((s) => f.counts[s]).map((s) => `<span class="sf-key"><i style="background:var(${P.ring_color[s]})"></i>${esc(w(`c_${s}`, { n: f.counts[s] }))}</span>`).join('')}</div>
        <div class="in-file-acts"><button type="button" class="primary small" data-map>${icon('link', 13)} ${esc(w('open'))}</button>
          <a class="small ghost button" href="${BASE}${base}/${esc(f.id)}/download">${icon('download', 13)} ${esc(w('download'))}</a></div></article>`).join('')}</section>`
      : `<section class="card in-drop"><svg width="120" height="96" viewBox="0 0 120 96" aria-hidden="true">
          <rect x="22" y="14" width="56" height="70" rx="8" fill="var(--panel-2)" stroke="var(--line-2)" stroke-width="2" transform="rotate(-8 50 49)"/>
          <rect x="40" y="8" width="58" height="74" rx="8" fill="var(--panel)" stroke="var(--brand)" stroke-width="2"/>
          <g stroke="var(--brand)" stroke-opacity=".35" stroke-width="2"><path d="M50 30h38M50 40h38M50 50h38M50 60h24"/></g>
          <circle cx="92" cy="74" r="15" fill="var(--brand)"/><path d="M92 81V67M86 73l6-6 6 6" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>
        <b>${esc(w('drop_title'))}</b><p class="small muted">${esc(w('no_files'))}</p>
        <button type="button" class="primary" id="in-up2">${icon('upload', 15)} ${esc(w('upload'))}</button></section>`);
  const upload = () => uploadBox(w('upload'), d.exts, base, () => filesView(host, cid, ay, K));
  host.querySelector('#in-ay').onchange = (e) => go({ c: cid, ay: e.target.value });
  host.querySelector('#in-change').onclick = () => go({});
  host.querySelector('#in-up').onclick = upload;
  if (host.querySelector('#in-up2')) host.querySelector('#in-up2').onclick = upload;
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
  const back = `/api/intake/${cid}/${encodeURIComponent(ay)}`;
  let v = await api(url);
  let only = false;
  const typed = {};          // row key -> what the person typed and has not saved yet (kept across redraws and filters)
  const unsaved = () => Object.keys(typed).length;
  const ext = v.file.ext || String(v.file.name).split('.').pop();
  host.innerHTML = pageHead(w('open'), '',
    `<button type="button" class="ghost" id="in-back">${icon('left', 14)} ${esc(w('back'))}</button>
     <a class="button" href="${BASE}${back}/${esc(fid)}/download">${icon('download', 14)} ${esc(w('download'))}</a>`)
    + `<section class="card mp-hero">
        <div class="mp-file">${sheetMark(ext)}<div class="mp-file-id"><b title="${esc(v.file.name)}">${esc(v.file.name)}</b>
          <div class="mp-client"><span class="cl-av" style="--h:${hue(v.client.name)}" aria-hidden="true">${esc(initials(v.client.name))}</span>
            <span>${esc(v.client.name)}</span><code>${esc(v.client.pan)}</code><span class="tag brand">${esc(w('form_is', { form: v.form }))}</span></div></div></div>
        <div class="mp-prog"><div id="in-ring"></div><div class="sf-sum-txt"><b id="in-progress"></b><div class="sf-legend" id="in-legend"></div></div></div>
        <div class="tabs sf-only" role="tablist" aria-label="${esc(w('filter'))}">${[['', w('f_all')], ['1', w('f_open')]].map(([id, label]) =>
          `<button type="button" role="tab" data-only="${id}" class="${id ? '' : 'on'}">${esc(label)}<span class="cl-count" data-c="${id}"></span></button>`).join('')}</div></section>
      <div class="mp-tools"><p class="mp-hint">${icon('info', 13)} <span>${esc(w('ref_hint'))}</span><span class="muted">· ${esc(w('enter_hint'))}</span></p>
        <span class="spacer"></span><button type="button" class="small ghost" id="in-expand">${icon('down', 13)} ${esc(w('expand_all'))}</button>
        <button type="button" class="small ghost" id="in-collapse">${icon('up', 13)} ${esc(w('collapse_all'))}</button></div>
      <div id="in-rows" class="mp-rows"></div>
      <datalist id="in-refs"></datalist>
      <div class="sf-bar" role="region" aria-label="${esc(w('save'))}"><span class="sf-bar-state" id="in-state"></span><span class="spacer"></span>
        <button type="button" class="ghost" id="in-accept">${icon('check', 14)} ${esc(w('accept_all'))}</button>
        <button type="button" class="primary" id="in-save">${icon('save', 15)} ${esc(w('save'))}</button></div>`;
  const body = host.querySelector('#in-rows');
  // Which headings are folded: a per-viewer convenience, kept per file in this browser (never needed to work).
  const foldKey = `sf.map.closed.${fid}`;
  let closed = new Set();
  try { closed = new Set(JSON.parse(localStorage.getItem(foldKey) || '[]')); } catch { /* private window: start open */ }
  const keepFolds = () => { try { localStorage.setItem(foldKey, JSON.stringify([...closed])); } catch { /* fine */ } };
  const state = () => {
    const el = host.querySelector('#in-state');
    el.className = `sf-bar-state ${unsaved() ? 'is-dirty' : 'is-clean'}`;
    el.innerHTML = `<span class="sf-dot"></span>${esc(unsaved() ? w('unsaved', { n: unsaved() }) : w('all_saved'))}`;
    host.querySelector('#in-save').disabled = !unsaved();
    host.querySelector('#in-accept').disabled = !v.counts.suggested;
  };
  // One row card: number, label (+ its heading), figures, the SF Ref box with its state dot, the suggestion chip.
  const card = (x) => {
    const val = x.key in typed ? typed[x.key] : x.ref;
    return `<div class="mp-row st-${esc(x.state)} ${x.key in typed ? 'is-dirty' : ''}" data-k="${esc(x.key)}">
      <span class="sf-rowno">${esc(x.key)}</span>
      <div class="mp-label"><div class="sf-label">${esc(x.label || '—')}</div></div>
      <div class="mp-nums">${x.numbers.slice(0, ps('intake').numbers_shown).map((n) => `<div>${money(n)}</div>`).join('')}</div>
      <div class="sf-refcell"><div class="sf-ref"><span class="sf-state" title="${esc(w(`s_${x.state}`))}"></span>
          <input data-ref list="in-refs" value="${esc(val)}" placeholder="${esc(x.suggestion || w('ref_placeholder'))}" aria-label="${esc(w('h_ref'))} ${esc(x.label || x.key)}"/></div>
        <div class="sf-ref-meta"><span class="${tagOf(x.state)}">${esc(w(`s_${x.state}`))}</span>
          ${x.from === 'file' ? `<span class="muted">${esc(w('from_file'))}</span>` : ''}
          ${x.suggestion && x.state === 'suggested' ? `<button type="button" class="sf-use" data-use>${icon('spark', 12)} ${esc(w('use'))} <b>${esc(x.suggestion)}</b></button>` : ''}</div></div></div>`;
  };
  const draw = () => {
    const c = v.counts, P = ps('intake');
    host.querySelector('#in-ring').innerHTML = ring(c);
    host.querySelector('#in-progress').textContent = w('progress', { done: P.done_states.reduce((a, s) => a + (c[s] || 0), 0), n: c.rows });
    host.querySelector('#in-legend').innerHTML = P.ring.filter((s) => c[s]).map((s) =>
      `<span class="sf-key"><i style="background:var(${P.ring_color[s]})"></i>${esc(w(`c_${s}`, { n: c[s] }))}</span>`).join('');
    host.querySelector('[data-c=""]').textContent = c.rows;
    host.querySelector('[data-c="1"]').textContent = P.open_states.reduce((a, s) => a + (c[s] || 0), 0);
    // Every ref already in this file, offered while typing (presentation: the server still checks each one).
    host.querySelector('#in-refs').innerHTML = [...new Set(v.rows.flatMap((x) => [x.ref, x.suggestion]).filter(Boolean))].sort()
      .map((r) => `<option value="${esc(r)}"></option>`).join('');
    const rows = v.rows.filter((x) => !only || P.open_states.includes(x.state));
    // Rows grouped under the statement's own headings, in file order.
    const groups = [];
    rows.forEach((x) => {
      const h = x.heading || '';
      if (!groups.length || groups[groups.length - 1].h !== h) groups.push({ h, rows: [] });
      groups[groups.length - 1].rows.push(x);
    });
    // Each heading folds: its title, the row numbers it covers, how many rows, their total and what still needs a person.
    body.innerHTML = rows.length ? groups.map((g, gi) => {
      const key = g.h || '-';
      const sg = (v.groups || [])[g.rows[0].group] || { net: 0, stated: null };   // the server adds it (chip intake.row_sign)
      const check = sg.stated === null ? '' : `<span class="mp-chip ${sg.agrees ? 'is-ok' : 'is-todo'}" title="${esc(w(sg.agrees ? 'group_agrees' : 'group_differs', { stated: money(sg.stated) }))}">${icon(sg.agrees ? 'check' : 'alert', 11)} ${esc(w(sg.agrees ? 'group_agrees_short' : 'group_differs_short', { stated: money(sg.stated) }))}</span>`;
      const todo = g.rows.filter((x) => P.open_states.includes(x.state)).length;
      const span = g.rows.length > 1 ? `${g.rows[0].key} – ${g.rows[g.rows.length - 1].key}` : g.rows[0].key;
      const shut = closed.has(key);
      return `<section class="mp-group ${shut ? 'is-closed' : ''}" data-g="${esc(key)}">
        <button type="button" class="mp-group-h" aria-expanded="${!shut}" aria-controls="mp-g${gi}">
          <svg class="mp-chev" width="14" height="14" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6l6 6-6 6" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>
          <span class="mp-group-t">${esc((g.h || w('no_heading')).slice(0, P.heading_chars))}</span>
          <span class="mp-group-meta"><span class="mp-chip">${esc(span)}</span><span class="mp-chip">${esc(w('group_count', { n: g.rows.length }))}</span>
            ${todo ? `<span class="mp-chip is-todo">${esc(w('group_todo', { n: todo }))}</span>` : ''}${check}<b class="mp-sum" title="${esc(w('group_net'))}">${money(sg.net)}</b></span></button>
        <div class="mp-group-body" id="mp-g${gi}">${g.rows.map(card).join('')}</div></section>`;
    }).join('')
      : `<div class="card sf-empty">${icon('check', 20)} ${esc(w('none_open'))}</div>`;
    body.querySelectorAll('.mp-group-h').forEach((b) => {
      b.onclick = () => {
        const sec = b.closest('[data-g]');
        const shut = !sec.classList.contains('is-closed');
        sec.classList.toggle('is-closed', shut);
        b.setAttribute('aria-expanded', String(!shut));
        if (shut) closed.add(sec.dataset.g); else closed.delete(sec.dataset.g);
        keepFolds();
      };
    });
    const inputs = [...body.querySelectorAll('[data-ref]')];
    inputs.forEach((inp, i) => {
      const r = inp.closest('[data-k]');
      const was = v.rows.find((x) => x.key === r.dataset.k).ref || '';
      inp.oninput = () => {
        if (inp.value.trim() !== was) typed[r.dataset.k] = inp.value.trim();
        else delete typed[r.dataset.k];
        r.classList.toggle('is-dirty', r.dataset.k in typed);
        state();
      };
      const next = () => inputs.slice(i + 1).find((x) => x.offsetParent) || inp;      // skip rows in a folded heading
      inp.onkeydown = (e) => { if (e.key === 'Enter') { e.preventDefault(); next().focus(); } };
      const use = r.querySelector('[data-use]');
      if (use) use.onclick = () => { inp.value = v.rows.find((x) => x.key === r.dataset.k).suggestion; inp.oninput(); next().focus(); };
    });
    state();
  };
  draw();
  // Leaving with typed refs not saved asks first (Back, another screen, closing the tab).
  const guard = (e) => { if (unsaved()) { e.preventDefault(); e.returnValue = ''; } };
  window.addEventListener('beforeunload', guard);
  window.addEventListener('hashchange', () => window.removeEventListener('beforeunload', guard), { once: true });
  const leave = () => { if (!unsaved() || window.confirm(w('leave_unsaved'))) { window.removeEventListener('beforeunload', guard); go({ c: cid, ay }); } };
  host.querySelector('#in-back').onclick = leave;
  const foldAll = (shut) => () => {
    body.querySelectorAll('[data-g]').forEach((sec) => {
      sec.classList.toggle('is-closed', shut);
      sec.querySelector('.mp-group-h').setAttribute('aria-expanded', String(!shut));
      if (shut) closed.add(sec.dataset.g); else closed.delete(sec.dataset.g);
    });
    keepFolds();
  };
  host.querySelector('#in-expand').onclick = foldAll(false);
  host.querySelector('#in-collapse').onclick = foldAll(true);
  host.querySelectorAll('[data-only]').forEach((b) => {
    b.onclick = () => { only = !!b.dataset.only; host.querySelectorAll('[data-only]').forEach((x) => x.classList.toggle('on', x === b)); draw(); };
  });
  host.querySelector('#in-accept').onclick = async (e) => { await busy(e.currentTarget, async () => {
    try { v = await api(`${url}/accept`, { method: 'POST' }); toast(w('saved'), 'ok'); draw(); } catch (err) { toast(err.message, 'bad', 8); }
  }); state(); };   // busy() puts the button back as it was - the state decides
  host.querySelector('#in-save').onclick = async (e) => { await busy(e.currentTarget, async () => {
    try {
      v = await api(`${url}/tags`, { method: 'PUT', body: { tags: { ...typed } } });
      Object.keys(typed).forEach((k) => delete typed[k]);
      toast(w('saved'), 'ok'); draw();
    } catch (err) { toast(err.message, 'bad', 8); }
  }); state(); };
}
