// Portal analytics - #/portalstats?ay=<AY>. Every firm on the portal for the portal admin: firms, people, returns, files,
// and the firms that need the admin today. The server decides everything (portal_stats.py, chips portalstats.*); this
// page draws it with the same tiles, bars and cards as Firm analytics. Words: chip ui.portalstats.
import { api, esc, pageHead, t, ps, loadWords, listBox, modal } from './app.js';
import { icon } from './icons.js';
import { kpiTile } from './page-clients.js';
import { bars } from './page-analytics.js';

const w = (k, v) => t('portalstats', k, v);
const size = (n) => (n >= 1024 ** 3 ? `${(n / 1024 ** 3).toFixed(1)} GB` : n >= 1024 ** 2 ? `${(n / 1024 ** 2).toFixed(1)} MB` : `${Math.round((n || 0) / 1024)} KB`);
const P = () => ps('portalstats');   // chip page.portalstats: each card's icon and colour

export async function portalstatsPage(host) {
  await loadWords('portalstats');
  const p = new URLSearchParams((location.hash.split('?')[1]) || '');
  host.innerHTML = pageHead(w('title'), esc(w('lede'))) + `<div class="loading">${esc(w('loading'))}</div>`;
  const d = await api(`/api/portalstats?ay=${encodeURIComponent(p.get('ay') || '')}`);
  const r = d.roll;
  const seen = (f) => (!f.last_seen ? w('never') : f.idle_days <= 0 ? w('today') : w('days_ago', { n: f.idle_days }));
  const chip = (n) => `<a class="an-chip" href="#/approvals">${esc(n)}</a>`;
  const flag = (id) => {
    const list = r[id] || [], n = d.flag_n[id] || 0;
    return `<div class="card an-lead"><div class="an-lead-h"><span class="an-lead-ic" style="color:var(${P().flag_tone[id]})">${icon(P().flag_icon[id], 16)}</span>
        <div><b>${esc(w(`f_${id}`))}</b></div><span class="an-lead-n">${n}</span></div>
      ${list.length ? `<div class="an-chips">${list.map(chip).join('')}${n > list.length
          ? `<button type="button" class="an-chip an-more" data-flag="${esc(id)}">${esc(w('see_all', { n }))}</button>` : ''}</div>`
        : `<div class="small muted">${esc(w('f_none'))}</div>`}</div>`;
  };
  const top = Math.max(1, ...d.days.map((x) => x.n));
  const SPAN = 30;   // ponytail: the server sends the last 30 days; one slot each, newest on the right
  host.innerHTML = pageHead(w('title'), esc(w('lede')),
    `<label class="cl-ay" for="ps-ay">${icon('clock', 14)}<span>${esc(w('ay'))}</span>
       <select id="ps-ay">${d.years.map((y) => `<option ${y === d.ay ? 'selected' : ''}>${esc(y)}</option>`).join('')}</select></label>`)
    + `<section class="sf-kpis an-kpis">
        ${kpiTile('shield', '--brand', w('k_firms'), String(r.firms), w('k_firms_sub', { n: r.approved }))}
        ${kpiTile('users', '--brand', w('k_people'), String(r.people), w('k_people_sub', { n: r.active7 }))}
        ${kpiTile('folder', '--brand', w('k_clients'), String(r.clients), w('k_clients_sub', { n: r.years }))}
        ${kpiTile('check', '--ok', w('k_filed'), String(r.filed), w('k_filed_sub', { n: r.returns }))}
        ${kpiTile('alert', d.flag_n.review ? '--warn' : '--ok', w('k_review'), String(d.flag_n.review), w('k_review_sub'))}
        ${kpiTile('archive', '--brand', w('k_space'), size(r.bytes), w('k_space_sub'))}</section>
      <section class="an-leads-h"><h3 class="rc-h">${icon('spark', 15)} ${esc(w('need_title'))}</h3><p class="small muted">${esc(w('need_sub'))}</p></section>
      <section class="an-leads ps-flags">${['review', 'stuck', 'empty', 'dormant'].map(flag).join('')}</section>
      <section class="card an-card"><h3 class="rc-h">${icon('shield', 15)} ${esc(w('firms_title'))}</h3><p class="small muted">${esc(w('firms_sub'))}</p>
        <div id="ps-firms"></div></section>
      <div class="an-grid">
        <section class="card an-card"><h3 class="rc-h">${icon('check', 15)} ${esc(w('mix_title'))}</h3>
          <div class="an-two"><div><h4>${esc(w('state_title'))}</h4>${bars(r.by_state.map((g) => ({ ...g, key: (d.states[g.key] || {}).label || g.key })))}</div><div><h4>${esc(w('kind_title'))}</h4>${bars(r.by_kind.map((g) => ({ ...g, key: d.kinds[g.key] || g.key })))}</div></div></section>
        <section class="card an-card"><h3 class="rc-h">${icon('users', 15)} ${esc(w('role_title'))}</h3>${bars(r.by_role.map((g) => ({ ...g, key: g.key === 'self' ? w('r_self') : d.roles[g.key] || g.key })))}</section>
      </div>
      <div class="an-grid">
        <section class="card an-card"><h3 class="rc-h">${icon('clock', 15)} ${esc(w('month_title'))}</h3>${bars(r.by_month, 'n', true)}</section>
        <section class="card an-card"><h3 class="rc-h">${icon('pulse', 15)} ${esc(w('use_title'))}</h3><p class="small muted">${esc(w('use_sub'))}</p>
          <svg class="ps-use" viewBox="0 0 ${SPAN * 10} 60" preserveAspectRatio="none" role="img">${d.days.slice(-SPAN).map((x, i, a) =>
            `<rect x="${(SPAN - a.length + i) * 10 + 1}" y="${60 - (x.n / top) * 58}" width="8" height="${(x.n / top) * 58}" rx="2" fill="var(--brand)"><title>${esc(x.day)}: ${x.n}</title></rect>`).join('')}</svg>
          <div class="small muted ps-use-k"><span>${esc((d.days[0] || {}).day || '')}</span><span>${esc((d.days[d.days.length - 1] || {}).day || '')}</span></div></section>
      </div>`;
  // the firms table and every card in full: list.portal_firms / list.portal_flags, searched and paged on the server
  listBox(host.querySelector('#ps-firms'), { list: 'portal_firms', args: { ay: d.ay },
    wrap: (html) => `<div class="an-scroll"><table class="cc-tbl an-tbl ps-firms"><colgroup><col class="ps-name"><col><col class="ps-state"><col><col><col><col><col><col></colgroup><thead><tr><th>${esc(w('h_firm'))}</th><th>${esc(w('h_kind'))}</th><th>${esc(w('h_state'))}</th>
          <th class="num">${esc(w('h_team'))}</th><th class="num">${esc(w('h_clients'))}</th><th class="num">${esc(w('h_filed'))}</th><th class="num">${esc(w('h_returns'))}</th>
          <th class="num">${esc(w('h_space'))}</th><th>${esc(w('h_seen'))}</th></tr></thead><tbody>${html}</tbody></table></div>`,
    row: (f) => `<tr><td>${esc(f.name)}</td><td>${esc(d.kinds[f.kind] || f.kind)}</td><td><span class="${esc((d.states[f.state] || {}).tag || 'tag')}">${esc((d.states[f.state] || {}).label || f.state)}</span></td><td class="num">${f.team}</td>
          <td class="num">${f.clients}</td><td class="num">${f.filed} / ${f.years}</td><td class="num">${f.returns}</td><td class="num">${esc(size(f.bytes))}</td>
          <td>${esc(seen(f))}</td></tr>` });
  host.querySelectorAll('[data-flag]').forEach((b) => { b.onclick = () => modal(w(`f_${b.dataset.flag}`), '<div data-all></div>', {
    onOpen: (m) => listBox(m.querySelector('[data-all]'), { list: 'portal_flags', args: { ay: d.ay, flag: b.dataset.flag },
      wrap: (html) => `<div class="an-chips">${html}</div>`, row: (x) => chip(x.name) }) }); });
  host.querySelector('#ps-ay').onchange = (e) => { location.hash = `#/portalstats?ay=${encodeURIComponent(e.target.value)}`; };
}
