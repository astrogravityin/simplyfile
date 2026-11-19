// Portal activity — every request the portal answered, who asked, which screen, how it went and how
// long it took. Body-free: paths and names only. Reports roll it up by person and by screen; Archive
// downloads a range and then clears it.
import { api, BASE, esc, toast, busy, pageHead, confirmDialog, t, loadWords, when, offAttr } from './ui.js';
import { state } from './shell.js';
import { icon } from './icons.js';

let tab = 'ledger';
let q = '';
let outcome = 'all';
let page = 1;
let range = '30d';

const whenS = (iso) => when(iso, true);   // the ledger is read to the second
// Every word on this screen is chip ui.activity (core/words.py) - none is written here.
const w = (k, v) => t('activity', k, v);
const RANGES = () => [['24h', w('range_24h')], ['7d', w('range_7d')], ['30d', w('range_30d')], ['90d', w('range_90d')], ['all', w('all')]];

export async function activityPage(host) {
  await loadWords('activity');
  host.innerHTML = `${pageHead(w('title'), w('lede'))}
    <div class="tabs many" role="tablist">${[['ledger', w('tab_ledger'), 'pulse'], ['reports', w('tab_reports'), 'users'], ['archive', w('tab_archive'), 'download']]
      .map(([id, label, ic]) => `<button type="button" data-tab="${id}" class="${tab === id ? 'on' : ''}">${icon(ic, 14)} ${label}</button>`).join('')}</div>
    <div id="act-body"></div>`;
  host.querySelectorAll('[data-tab]').forEach((b) => { b.onclick = () => { tab = b.dataset.tab; activityPage(host); }; });
  const body = host.querySelector('#act-body');
  await ({ ledger, reports, archive })[tab](body);
}

const statusTag = (s) => `<span class="tag ${s >= 500 ? 'bad' : s >= 400 ? 'warn' : 'ok'}">${s}</span>`;

async function ledger(body) {
  body.innerHTML = `<div class="toolbar">
      <span class="finder">${icon('search', 15)}<input id="act-q" value="${esc(q)}" placeholder="${esc(w('search_placeholder'))}"/></span>
      <div class="switch">${[['all', w('all')], ['ok', w('succeeded')], ['fail', w('failed')], ['anon', w('signed_out_filter')]]
        .map(([id, l]) => `<button type="button" data-out="${id}" class="${outcome === id ? 'on' : ''}">${l}</button>`).join('')}</div>
    </div>
    <div id="act-rows"><div class="empty"><p>${w('loading')}</p></div></div>`;
  const draw = async () => {
    const d = await api(`/api/core/activity?q=${encodeURIComponent(q)}&outcome=${outcome}&page=${page}&size=50`);
    const pages = Math.max(1, Math.ceil(d.total / d.size));
    body.querySelector('#act-rows').innerHTML = d.rows.length ? `<div class="card flush"><div class="scroll"><table class="fixed">
      <colgroup><col style="width:150px"/><col style="width:22%"/><col style="width:70px"/><col/><col style="width:14%"/><col style="width:64px"/><col style="width:70px"/><col style="width:130px"/></colgroup>
      <thead><tr><th>${w('col_when')}</th><th>${w('col_who')}</th><th>${w('col_method')}</th><th>${w('col_path')}</th><th>${w('col_screen')}</th><th>${w('col_status')}</th><th>${w('col_time')}</th><th>${w('col_network')}</th></tr></thead>
      <tbody>${d.rows.map((r) => `<tr><td class="small">${whenS(r.at)}</td>
        <td>${r.email ? esc(r.email) : `<span class="muted">${w('signed_out')}</span>`}</td>
        <td><code>${esc(r.method)}</code></td><td class="small"><code>${esc(r.path)}</code></td>
        <td class="small">${esc(r.screen || '')}</td><td>${statusTag(r.status)}</td>
        <td class="small muted">${w('ms', { n: r.ms })}</td><td class="small muted">${esc(r.ip || '')}</td></tr>`).join('')}</tbody></table></div></div>
      <div class="row between"><span class="small muted">${w('ledger_foot', { total: d.total.toLocaleString(), days: d.keep_days })}</span>
        <span class="row tight"><button class="small" type="button" data-pg="-1" aria-label="${esc(t('shell', 'list_prev'))}"${offAttr(page <= 1 ? t('shell', 'off_first_page') : '')}>${icon('left', 13)}</button>
        <span class="small">${w('page_of', { page, pages })}</span>
        <button class="small" type="button" data-pg="1" aria-label="${esc(t('shell', 'list_next'))}"${offAttr(page >= pages ? t('shell', 'off_last_page') : '')}>${icon('right', 13)}</button></span></div>`
      : `<div class="card"><div class="empty">${icon('pulse', 36)}<h3>${w('nothing_matches')}</h3><p>${w('nothing_matches_hint')}</p></div></div>`;
    body.querySelectorAll('[data-pg]').forEach((b) => { b.onclick = () => { page += Number(b.dataset.pg); draw(); }; });
  };
  let timer = 0;
  body.querySelector('#act-q').oninput = (e) => { clearTimeout(timer); timer = setTimeout(() => { q = e.target.value; page = 1; draw(); }, 300); };
  body.querySelectorAll('[data-out]').forEach((b) => { b.onclick = () => { outcome = b.dataset.out; page = 1; ledger(body); }; });
  await draw();
}

async function reports(body) {
  const d = await api(`/api/core/activity/report?range=${range}`);
  const tot = d.totals;
  const tile = (n, label) => `<div class="stat"><b>${Number(n || 0).toLocaleString()}</b><span>${label}</span></div>`;
  const maxJoin = Math.max(1, ...d.joins.map((j) => j.count));
  body.innerHTML = `<div class="toolbar"><div class="switch">${RANGES().map(([id, l]) =>
      `<button type="button" data-range="${id}" class="${range === id ? 'on' : ''}">${l}</button>`).join('')}</div></div>
    <div class="stats">${tile(tot.requests, w('tile_requests'))}${tile(tot.people, w('tile_people'))}${tile(tot.anonymous, w('tile_anonymous'))}${tile(tot.errors, w('tile_errors'))}</div>
    <div class="split">
      <div class="card flush"><div class="head" style="padding:14px 16px 0"><h2>${icon('users', 16)} ${w('by_person')}</h2></div>
        ${d.people.length ? `<table><thead><tr><th>${w('col_person')}</th><th>${w('col_requests')}</th><th>${w('col_failed')}</th><th>${w('col_screens')}</th><th>${w('col_last_seen')}</th></tr></thead>
        <tbody>${d.people.map((p) => `<tr><td>${esc(p.email)}</td><td>${p.requests}</td>
          <td>${p.failed ? `<span class="tag warn">${p.failed}</span>` : '0'}</td><td>${p.screens}</td><td class="small muted">${whenS(p.last_at)}</td></tr>`).join('')}</tbody></table>`
          : `<p class="muted small" style="padding:0 16px 16px">${w('no_people')}</p>`}</div>
      <div class="card flush"><div class="head" style="padding:14px 16px 0"><h2>${icon('film', 16)} ${w('by_screen')}</h2></div>
        ${d.screens.length ? `<table><thead><tr><th>${w('col_screen')}</th><th>${w('col_requests')}</th><th>${w('col_people')}</th><th>${w('col_failed')}</th><th>${w('col_avg')}</th></tr></thead>
        <tbody>${d.screens.map((s) => `<tr><td>${esc(s.label)}</td><td>${s.requests}</td><td>${s.people}</td>
          <td>${s.failed ? `<span class="tag warn">${s.failed}</span>` : '0'}</td><td class="small muted">${w('ms', { n: s.avg_ms })}</td></tr>`).join('')}</tbody></table>`
          : `<p class="muted small" style="padding:0 16px 16px">${w('no_screens')}</p>`}</div>
    </div>
    <div class="split">
      <div class="card"><h2>${icon('plus', 16)} ${w('new_accounts')}</h2>
        ${d.joins.length ? `<div class="hbars">${d.joins.map((j) => `<div class="hbar"><span>${esc(j.day)}</span>
          <i style="width:${(100 * j.count) / maxJoin}%"></i><b>${j.count}</b></div>`).join('')}</div>`
          : `<p class="muted small">${w('no_joins')}</p>`}</div>
      <div class="card"><h2>${icon('key', 16)} ${w('signins')}</h2>
        ${d.signins.length ? `<table><thead><tr><th>${w('col_day')}</th><th>${w('succeeded')}</th><th>${w('col_refused')}</th></tr></thead>
          <tbody>${d.signins.map((s) => `<tr><td>${esc(s.day)}</td><td>${s.ok}</td>
            <td>${s.failed ? `<span class="tag ${s.failed > 20 ? 'bad' : 'warn'}">${s.failed}</span>` : '0'}</td></tr>`).join('')}</tbody></table>`
          : `<p class="muted small">${w('no_signins')}</p>`}</div>
    </div>`;
  body.querySelectorAll('[data-range]').forEach((b) => { b.onclick = () => { range = b.dataset.range; reports(body); }; });
}

async function archive(body) {
  const owner = state.user.role === 'owner';
  const d = await api('/api/core/activity?size=10');
  const monthAgo = new Date(Date.now() - 30 * 864e5).toISOString().slice(0, 10);
  body.innerHTML = `<div class="card"><h2>${icon('download', 17)} ${w('archive_title')}</h2>
      <p class="muted small">${w('archive_lede', { days: d.keep_days })}</p>
      <div class="grid two">
        <div class="field"><label for="ar-table">${w('what')}</label>
          <select id="ar-table"><option value="activity">${w('what_activity')}</option><option value="views">${w('what_views')}</option></select></div>
        <div class="field"><label for="ar-before">${w('before')}</label><input id="ar-before" type="date" value="${monthAgo}"/></div>
      </div>
      <div class="row" style="margin-top:12px">
        <button class="primary" type="button" id="ar-get">${icon('download')} ${w('download')}</button>
        ${owner ? `<button class="danger" type="button" id="ar-clear">${icon('trash')} ${w('clear_it')}</button>` : ''}</div></div>
    ${owner ? `<div class="card"><h2>${icon('clock', 17)} ${w('keep_title')}</h2>
      <div class="row"><div class="field" style="max-width:200px"><label for="ar-keep">${w('days')}</label>
        <input id="ar-keep" inputmode="numeric" value="${d.keep_days}"/></div>
        <button type="button" id="ar-keep-save" style="align-self:flex-end">${icon('save')} ${w('save')}</button></div></div>` : ''}`;
  const pick = () => ({ table: body.querySelector('#ar-table').value, before: body.querySelector('#ar-before').value });
  body.querySelector('#ar-get').onclick = () => {
    const { table, before } = pick();
    if (!before) { toast(w('pick_date'), 'warn'); return; }
    location.href = `${BASE}/api/core/archive/${table}?before=${encodeURIComponent(before)}`;
  };
  const clear = body.querySelector('#ar-clear');
  if (clear) clear.onclick = () => {
    const { table, before } = pick();
    if (!before) { toast(w('pick_date'), 'warn'); return; }
    confirmDialog(w('clear_title'), w('clear_body', { table, before }), async () => {
      try {
        const r = await api(`/api/core/archive/${table}/clear`, { method: 'POST', body: { before } });
        toast(w('cleared', { n: r.deleted.toLocaleString() }), 'ok');
      } catch (e) { toast(e.message, 'bad'); }
    }, w('clear'), { tone: 'danger' });
  };
  const keep = body.querySelector('#ar-keep-save');
  if (keep) keep.onclick = (e) => busy(e.currentTarget, async () => {
    try {
      const r = await api('/api/core/archive/keep', { method: 'PUT', body: { days: body.querySelector('#ar-keep').value } });
      toast(w('kept', { n: r.keep_days }), 'ok');
    } catch (err) { toast(err.message, 'bad'); }
  });
}
