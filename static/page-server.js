// Server & sites - #/server. The VPS's sites, disk and backups for the portal admin, READ-ONLY (2026-10-04 owner:
// "wire it read-only, no restart button"). The server reads the box and the chips decide what each reading means
// (server.py, chips server.*); this page draws it with the same tiles, bars and tables as the analytics pages.
// Words: chip ui.server. Colours: chip page.server.
import { api, esc, pageHead, t, ps, loadWords } from './app.js';
import { icon } from './icons.js';
import { kpiTile } from './page-clients.js';

const w = (k, v) => t('server', k, v);
const P = () => ps('server');
const size = (n) => { const a = Math.abs(n || 0); const s = a >= 1024 ** 3 ? `${(a / 1024 ** 3).toFixed(1)} GB` : a >= 1024 ** 2 ? `${(a / 1024 ** 2).toFixed(1)} MB` : `${Math.round(a / 1024)} KB`; return (n < 0 ? '-' : '') + s; };
const ago = (h) => (h == null ? '-' : h < 1 ? w('ago_m', { n: Math.round(h * 60) }) : w('ago_h', { n: Math.round(h) }));
const every = (h) => (!h ? '-' : h === 1 ? w('every_1') : h >= 24 ? w('daily') : w('every_h', { n: h }));
const pill = (tone, text) => `<span class="sv-pill" style="--c:var(${tone})">${esc(text)}</span>`;

function duTable(d) {
  const top = Math.max(1, ...d.rows.map((r) => r.size));
  const up = d.path === '/' ? '' : d.path.replace(/\/[^/]+$/, '') || '/';
  return `<div class="sv-path"><code>${esc(d.path)}</code>${up ? `<button class="btn ghost sm" data-du="${esc(up)}">${icon('up', 13)} ${esc(w('up'))}</button>` : ''}</div>
    <div class="an-bars">${d.rows.map((r) => `<div class="an-brow sv-brow"><button class="link" data-du="${esc(r.path)}" title="${esc(r.path)}">${esc(r.path.split('/').pop() || r.path)}</button>
      <svg width="100%" height="10"><rect width="100%" height="10" rx="5" fill="var(--panel-2)"/><rect width="${Math.max(2, (r.size / top) * 100)}%" height="10" rx="5" fill="var(--brand)"/></svg><b>${esc(size(r.size))}</b></div>`).join('')}</div>`;
}

export async function serverPage(host) {
  await loadWords('server');
  host.innerHTML = pageHead(w('title'), esc(w('lede'))) + `<div class="loading">${esc(w('loading'))}</div>`;
  let d;
  try { d = await api('/api/server'); } catch (e) {
    host.innerHTML = pageHead(w('title'), esc(w('lede'))) + `<div class="card"><p>${icon('info', 14)} ${esc(e.message)}</p></div>`;
    return;
  }
  const up = d.sites.filter((s) => s.state === 'up').length;
  const late = d.backups.filter((b) => b.state !== 'ok').length;
  const h = d.history;
  const tone = (map, k) => (P()[map] || {})[k] || '--muted';
  const topH = Math.max(1, ...h.series.map((x) => x.used));
  host.innerHTML = pageHead(w('title'), esc(w('lede')), `<button class="btn ghost" id="sv-again">${icon('refresh', 14)} ${esc(w('refresh'))}</button>`)
    + `<section class="sf-kpis">
        ${kpiTile('globe', up === d.sites.length ? '--ok' : '--bad', w('k_sites'), `${up} / ${d.sites.length}`, up === d.sites.length ? w('k_sites_ok') : w('k_sites_sub', { down: d.sites.length - up }))}
        ${kpiTile('folder', tone('level_tone', d.disk.level), w('k_disk'), `${d.disk.pct}%`, w('k_disk_sub', { free: size(d.disk.free), total: size(d.disk.total) }))}
        ${kpiTile('archive', late ? '--bad' : '--ok', w('k_backups'), `${d.backups.length - late} / ${d.backups.length}`, late ? w('k_backups_sub', { late }) : w('k_backups_ok'))}
        ${kpiTile('pulse', h.days_to_full != null && h.days_to_full < 60 ? '--warn' : '--brand', w('k_growth'), h.per_day == null ? '-' : `${size(h.per_day)}/d`,
          !h.series.length ? w('k_growth_na') : h.days_to_full == null ? w('k_growth_none') : w('k_growth_sub', { days: h.days_to_full }))}</section>
      <section class="card an-card"><h3 class="rc-h">${icon('globe', 15)} ${esc(w('sites_title'))}</h3><p class="small muted">${esc(w('sites_sub'))}</p>
        <div class="an-scroll"><table class="cc-tbl an-tbl"><colgroup><col class="sv-wide"><col><col><col><col class="sv-num"></colgroup><thead><tr><th>${esc(w('h_site'))}</th><th>${esc(w('h_state'))}</th>
          <th>${esc(w('h_commit'))}</th><th>${esc(w('h_since'))}</th><th class="num">${esc(w('h_jobs'))}</th></tr></thead><tbody>
        ${d.sites.map((s) => `<tr><td><b>${esc(s.label)}</b><div class="small muted">${esc(s.host)} · <code>${esc(s.service)}</code></div></td>
          <td>${pill(tone('state_tone', s.state), w(`st_${s.state}`))}</td><td><code>${esc(s.commit || '-')}</code></td><td class="small">${esc(s.since || '-')}</td>
          <td class="num">${s.jobs}</td></tr>`).join('')}</tbody></table></div></section>
      <section class="card an-card"><h3 class="rc-h">${icon('archive', 15)} ${esc(w('bk_title'))}</h3><p class="small muted">${esc(w('bk_sub'))}</p>
        <div class="an-scroll"><table class="cc-tbl an-tbl"><colgroup><col class="sv-wide"><col><col class="sv-num"><col class="sv-num"><col><col></colgroup><thead><tr><th>${esc(w('h_backup'))}</th><th>${esc(w('h_schedule'))}</th>
          <th class="num">${esc(w('h_copies'))}</th><th class="num">${esc(w('h_space'))}</th><th>${esc(w('h_newest'))}</th><th>${esc(w('h_state'))}</th></tr></thead><tbody>
        ${d.backups.map((b) => `<tr><td><b>${esc(b.label)}</b><div class="small muted"><code>${esc(b.dir)}</code>${b.plan ? ` · ${esc(b.plan)}` : ''}</div></td>
          <td>${esc(every(b.every_h))}${b.keep_h ? `<div class="small muted">${esc(w('keep_h', { n: b.keep_h }))}</div>` : ''}</td>
          <td class="num">${b.copies}</td><td class="num">${esc(size(b.bytes))}</td><td>${esc(ago(b.newest_h))}</td>
          <td>${pill(tone('backup_tone', b.state), w(`bs_${b.state}`))}</td></tr>`).join('')}</tbody></table></div></section>
      <div class="an-grid">
        <section class="card an-card"><h3 class="rc-h">${icon('folder', 15)} ${esc(w('disk_title'))}</h3><p class="small muted">${esc(w('disk_sub'))}</p>
          <div class="sv-roots">${d.roots.map((r) => `<button class="an-chip" data-du="${esc(r)}">${esc(r)}</button>`).join('')}</div><div id="sv-du"></div></section>
        <section class="card an-card"><h3 class="rc-h">${icon('pulse', 15)} ${esc(w('hist_title'))}</h3><p class="small muted">${esc(w('hist_sub'))}</p>
          ${h.series.length ? `<svg class="ps-use" viewBox="0 0 ${h.series.length * 10} 60" preserveAspectRatio="none" role="img">${h.series.map((x, i) =>
            `<rect x="${i * 10 + 1}" y="${60 - (x.used / topH) * 58}" width="8" height="${(x.used / topH) * 58}" rx="2" fill="var(--brand)"><title>${esc(x.day)}: ${esc(size(x.used))}</title></rect>`).join('')}</svg>
            <div class="small muted ps-use-k"><span>${esc(h.series[0].day)}</span><span>${esc(h.series[h.series.length - 1].day)}</span></div>
            ${h.grew.length ? `<h4>${esc(w('grow_title'))}</h4><table class="cc-tbl an-tbl"><colgroup><col class="sv-wide"><col class="sv-num"><col class="sv-num"></colgroup><thead><tr><th>${esc(w('h_folder'))}</th>
              <th class="num">${esc(w('h_size'))}</th><th class="num">${esc(w('h_change'))}</th></tr></thead><tbody>${h.grew.map((g) => `<tr><td><code>${esc(g.path)}</code></td>
              <td class="num">${esc(size(g.size))}</td><td class="num">${esc(size(g.change))}</td></tr>`).join('')}</tbody></table>` : ''}`
            : `<p class="small muted">${esc(w('hist_none'))}</p>`}</section>
      </div>
      <p class="small muted an-note">${icon('lock', 13)} ${esc(w('control'))}</p>`;
  const du = async (path) => {
    const box = host.querySelector('#sv-du');
    box.innerHTML = `<div class="loading">${esc(w('loading'))}</div>`;
    try { box.innerHTML = duTable(await api(`/api/server/du?path=${encodeURIComponent(path)}`)); } catch (e) { box.innerHTML = `<p class="small muted">${esc(e.message)}</p>`; }
  };
  host.onclick = (e) => { const b = e.target.closest('[data-du]'); if (b) du(b.dataset.du); };
  host.querySelector('#sv-again').onclick = () => serverPage(host);
  du('/');
}
