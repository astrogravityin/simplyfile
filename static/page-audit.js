// Tax audit - #/audit?c=<client>&ay=<year>. Form 3CD worked through for one client-year (2026-10-04 owner: "phase 1, tax audit
// for SMEs"): is an audit needed, every mapped line this year against last, the 3CD clauses that apply, and the open points.
// The server decides everything (audit.py, chips audit.*); this page draws it. Words: ui.audit. Look: page.audit.
import { api, esc, toast, pageHead, t, ps, loadWords, when } from './app.js';
import { clientPicker } from './page-intake.js';
import { icon } from './icons.js';

const w = (k, v) => t('audit', k, v);
const P = () => ps('audit');
const money = (n) => `₹${Math.round(Number(n || 0)).toLocaleString(P().money_locale)}`;
const pill = (tone, text) => `<span class="sv-pill" style="--c:var(${tone})">${esc(text)}</span>`;

export async function auditPage(host) {
  await loadWords('audit', 'intake');
  const p = new URLSearchParams((location.hash.split('?')[1]) || '');
  if (!p.get('c')) return clientPicker(host, 'audit');
  const K = await api('/api/clients/settings');
  const cid = p.get('c');
  const ay = p.get('ay') || K.current_ay;
  const base = `/api/audit/${encodeURIComponent(cid)}/${encodeURIComponent(ay)}`;
  host.innerHTML = pageHead(w('title'), esc(w('lede'))) + `<div class="loading">${esc(w('loading'))}</div>`;
  let d = await api(base);
  host.innerHTML = pageHead(`${w('title')} · ${d.client.name}`, esc(w('lede')),
    `<label class="cl-ay" for="au-ay">${icon('clock', 14)}<span>${esc(w('ay'))}</span>
       <select id="au-ay">${K.years.map((y) => `<option ${y === ay ? 'selected' : ''}>${esc(y)}</option>`).join('')}</select></label>`)
    + `<section class="card an-card" id="au-need"></section>
       <section class="card an-card"><h3 class="rc-h">${icon('pulse', 15)} ${esc(w('trend_title'))}</h3><p class="small muted">${esc(w('trend_sub'))}</p>
         <p class="small" id="au-src"></p>
         <div class="row tight au-bar"><input type="search" id="au-q" class="mp-find" placeholder="${esc(w('find_lines'))}"/>
           <label class="check small"><input type="checkbox" id="au-flagged" checked/> ${esc(w('only_flagged'))}</label></div>
         <div id="au-trend"></div></section>
       <section class="card an-card"><h3 class="rc-h">${icon('check', 15)} ${esc(w('check_title'))} <span class="small muted" id="au-done"></span></h3>
         <p class="small muted">${esc(w('check_sub'))}</p><div id="au-checks"></div></section>
       <section class="card an-card"><h3 class="rc-h">${icon('flag', 15)} ${esc(w('points_title'))}</h3><p class="small muted">${esc(w('points_sub'))}</p>
         <div class="au-new"><input id="au-pt" maxlength="300" placeholder="${esc(w('point_title_ph'))}"/>
           <select id="au-owner"><option value="">${esc(w('nobody'))}</option>${d.people.map((m) => `<option value="${esc(m.id)}">${esc(m.name)}</option>`).join('')}</select>
           <button type="button" class="primary small" id="au-add">${icon('plus', 13)} ${esc(w('point_new'))}</button></div>
         <div id="au-points"></div></section>`;
  host.querySelector('#au-ay').onchange = (e) => { location.hash = `#/audit?c=${encodeURIComponent(cid)}&ay=${encodeURIComponent(e.target.value)}`; };
  const send = async (path, method, body) => {
    try { d = await api(`${base}${path}`, { method, body }); toast(w('saved'), 'ok'); draw(); } catch (e) { toast(e.message, 'bad', 8); }
  };
  const nameOf = (id) => (d.people.find((m) => m.id === id) || {}).name || '';
  const lineName = (r) => `${(P().items || {})[r.item] || r.item}`;

  const need = () => {
    const a = d.applicable;
    host.querySelector('#au-need').innerHTML = `<h3 class="rc-h">${icon(P().need_icon[a.need], 15)} ${esc(w('need_title'))}</h3>
      <div class="au-verdict">${pill(P().need_tone[a.need], w(`need_${a.need}`))}
        <span class="small">${esc(w(a.why, { turnover: money(a.turnover), limit: money(a.limit) }))}</span></div>
      <div class="au-facts">${Object.keys(d.facts).map((f) => `<label class="check small"><input type="checkbox" data-fact="${esc(f)}" ${d.facts[f] ? 'checked' : ''}/> ${esc(w(`fact_${f}`))}</label>`).join('')}</div>
      ${a.need === 'yes' && !d.marked ? `<button type="button" class="small" id="au-mark">${icon('shield', 13)} ${esc(w('mark_audit'))}</button>`
        : d.marked ? `<p class="small muted">${icon('check', 12)} ${esc(w('marked'))}</p>` : ''}`;
    host.querySelectorAll('[data-fact]').forEach((c) => { c.onchange = () => send('/facts', 'PUT', { [c.dataset.fact]: c.checked }); });
    const mk = host.querySelector('#au-mark');
    if (mk) mk.onclick = async () => { await api(`/api/clients/${encodeURIComponent(cid)}/years/${encodeURIComponent(ay)}`, { method: 'PUT', body: { audit: true } }); send('', 'GET'); };
  };

  const trend = () => {
    const tr = d.trend;
    host.querySelector('#au-src').innerHTML = `${esc(w(`src_${tr.source}`, { ay: tr.prev_ay }))} · ${esc(w('turnover'))} <b>${money(tr.revenue)}</b>
      ${tr.revenue_before ? ` · ${esc(w('turnover_change'))} <b>${tr.revenue_pct > 0 ? '+' : ''}${tr.revenue_pct}%</b>` : ''}`;
    // every word typed must be in the line's name, table or item; "only flagged" hides the quiet lines
    const words = host.querySelector('#au-q').value.toLowerCase().split(/\s+/).filter(Boolean);
    const flagged = host.querySelector('#au-flagged').checked;
    const rows = tr.rows.filter((r) => (!flagged || r.flag) && words.every((x) => `${lineName(r)} ${r.item} ${w(`t_${r.table}`)}`.toLowerCase().includes(x)));
    host.querySelector('#au-trend').innerHTML = !tr.rows.length ? `<p class="small muted">${esc(w('no_lines'))}</p>`
      : `<div class="an-scroll"><table class="cc-tbl an-tbl"><thead><tr><th>${esc(w('h_line'))}</th><th class="num">${esc(w('h_before'))}</th>
          <th class="num">${esc(w('h_now'))}</th><th class="num">${esc(w('h_change'))}</th><th class="num">${esc(w('h_share'))}</th><th>${esc(w('h_flag'))}</th><th></th></tr></thead><tbody>
        ${rows.map((r) => `<tr><td>${esc(lineName(r))} <span class="small muted">${esc(w(`t_${r.table}`))}</span></td>
          <td class="num">${tr.source === 'none' ? '-' : money(r.before)}</td><td class="num">${money(r.now)}</td>
          <td class="num">${r.before ? `${r.pct > 0 ? '+' : ''}${r.pct}%` : '-'}</td><td class="num">${r.table === 'PL' ? `${r.share}%` : '-'}</td>
          <td>${r.flag ? pill(P().flag_tone[r.flag], w(`flag_${r.flag}`)) : ''}</td>
          <td>${r.flag ? `<button type="button" class="small ghost" data-raise="${esc(r.id)}">${icon('flag', 12)} ${esc(w('raise'))}</button>` : ''}</td></tr>`).join('')}
        </tbody></table></div>`;
    host.querySelectorAll('[data-raise]').forEach((b) => {
      const r = tr.rows.find((x) => x.id === b.dataset.raise);
      b.onclick = () => send('/points', 'POST', { source: 'trend', ref: `trend:${r.id}`,
        title: `${lineName(r)}: ${money(r.before)} → ${money(r.now)} (${w(`flag_${r.flag}`)})` });
    });
  };

  const checks = () => {
    const n = d.checklist.length, done = d.checklist.filter((c) => ['done', 'na'].includes(c.state)).length;
    host.querySelector('#au-done').textContent = `· ${w('checks_done', { done, n })}`;
    host.querySelector('#au-checks').innerHTML = `<div class="au-list">${d.checklist.map((c) => `<div class="au-check" data-check="${esc(c.id)}" style="--c:var(${P().state_tone[c.state]})">
        <span class="au-clause">3CD ${esc(c.clause)}</span>
        <div class="au-main"><b>${esc(c.title)}</b>${c.hint ? `<div class="small muted">${esc(c.hint)}</div>` : ''}
          <input class="au-note" data-note value="${esc(c.note || '')}" placeholder="${esc(w('note_ph'))}" maxlength="1000"/></div>
        <select data-state aria-label="${esc(c.title)}">${d.states.map((s) => `<option value="${s}" ${s === c.state ? 'selected' : ''}>${esc(w(`st_${s}`))}</option>`).join('')}</select></div>`).join('')}</div>`;
    host.querySelectorAll('[data-check]').forEach((el) => {
      const save = () => send(`/checks/${encodeURIComponent(el.dataset.check)}`, 'PUT', { state: el.querySelector('[data-state]').value, note: el.querySelector('[data-note]').value });
      el.querySelector('[data-state]').onchange = save;
      el.querySelector('[data-note]').onchange = save;
    });
  };

  const points = () => {
    const list = [...d.points].sort((a, b) => (a.status === 'open' ? 0 : 1) - (b.status === 'open' ? 0 : 1));
    host.querySelector('#au-points').innerHTML = !list.length ? `<p class="small muted">${esc(w('points_none'))}</p>`
      : `<div class="au-list">${list.map((x) => `<div class="au-point ${x.status === 'cleared' ? 'is-done' : ''}" data-point="${esc(x.id)}">
          <div class="au-main"><b>${esc(x.title)}</b><div class="small muted">${esc(w(`from_${x.source}`))} · ${esc(x.by)} · ${esc(when(x.at))}</div>
            <input class="au-note" data-pnote value="${esc(x.note || '')}" placeholder="${esc(w('note_ph'))}" maxlength="1000"/></div>
          <select data-powner aria-label="${esc(w('point_owner'))}"><option value="">${esc(w('nobody'))}</option>${d.people.map((m) => `<option value="${esc(m.id)}" ${m.id === x.owner ? 'selected' : ''}>${esc(m.name)}</option>`).join('')}</select>
          ${pill(x.status === 'open' ? '--warn' : '--ok', w(`pt_${x.status}`))}
          ${d.may_clear ? `<button type="button" class="small ghost" data-flip>${esc(w(x.status === 'open' ? 'clear' : 'reopen'))}</button>` : ''}</div>`).join('')}</div>`;
    host.querySelectorAll('[data-point]').forEach((el) => {
      const id = encodeURIComponent(el.dataset.point);
      const x = d.points.find((y) => y.id === el.dataset.point);
      el.querySelector('[data-pnote]').onchange = (e) => send(`/points/${id}`, 'PUT', { note: e.target.value });
      el.querySelector('[data-powner]').onchange = (e) => send(`/points/${id}`, 'PUT', { owner: e.target.value });
      const f = el.querySelector('[data-flip]');
      if (f) f.onclick = () => send(`/points/${id}/status`, 'PUT', { status: x.status === 'open' ? 'cleared' : 'open' });
    });
  };

  const draw = () => { need(); trend(); checks(); points(); };
  host.querySelector('#au-flagged').checked = d.trend.source !== 'none';   // nothing to compare: show every line
  host.querySelector('#au-q').oninput = trend;
  host.querySelector('#au-flagged').onchange = trend;
  host.querySelector('#au-add').onclick = () => {
    const title = host.querySelector('#au-pt').value.trim();
    if (!title) return;
    send('/points', 'POST', { title, owner: host.querySelector('#au-owner').value, source: 'hand' });
    host.querySelector('#au-pt').value = '';
  };
  draw();
}
