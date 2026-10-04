// Firm analytics - #/analytics?ay=<AY>. How the firm's year is going: deadlines, pipeline, workload, money handled for
// clients, the practice mix, advisory leads and year on year. The server decides everything (analytics.py, chips
// analytics.*); this page draws it. Words: chip ui.analytics. Colours and icons: chip page.analytics.
import { api, esc, pageHead, t, ps, loadWords, listBox, modal } from './app.js';
import { icon } from './icons.js';
import { kpiTile } from './page-clients.js';

const w = (k, v) => t('analytics', k, v);
const P = () => ps('analytics');
const money = (n) => `₹${Math.round(Number(n || 0)).toLocaleString(P().money_locale)}`;
const pct = (a, b) => (b ? Math.round((a / b) * 100) : 0);
const day = (iso) => (iso ? iso.split('-').reverse().join('/') : '');

// One horizontal bar split by group, each part in its chip colour, with a legend under it.
function stackBar(groups, order, colorOf, labelOf) {
  const total = groups.reduce((a, g) => a + g.n, 0) || 1;
  const seg = order.map((id) => groups.find((g) => g.key === id)).filter(Boolean);
  let x = 0;
  const rects = seg.map((g) => { const wd = (g.n / total) * 100; const r = `<rect x="${x}%" width="${wd}%" height="14" fill="var(${colorOf(g.key)})"><title>${esc(labelOf(g.key))}: ${g.n}</title></rect>`; x += wd; return r; }).join('');
  return `<svg class="an-bar" width="100%" height="14" role="img"><rect width="100%" height="14" rx="7" fill="var(--line)"/>
      <svg width="100%" height="14"><defs><clipPath id="an-c-${order.join('')}"><rect width="100%" height="14" rx="7"/></clipPath></defs><g clip-path="url(#an-c-${order.join('')})">${rects}</g></svg></svg>
    <div class="sf-legend">${seg.map((g) => `<span class="sf-key"><i style="background:var(${colorOf(g.key)})"></i>${esc(labelOf(g.key))} <b>${g.n}</b></span>`).join('')}</div>`;
}

// Labelled bars, longest first: the practice mix, the year on year.
export function bars(groups, field = 'n', keep = false) {
  const top = Math.max(1, ...groups.map((g) => g[field] || 0));
  return `<div class="an-bars">${(keep ? groups : groups.slice().sort((a, b) => (b[field] || 0) - (a[field] || 0))).map((g) => `<div class="an-brow"><span>${esc(g.key || '-')}</span>
    <svg width="100%" height="10"><rect width="100%" height="10" rx="5" fill="var(--panel-2)"/><rect width="${Math.max(2, ((g[field] || 0) / top) * 100)}%" height="10" rx="5" fill="var(--brand)"/></svg><b>${g[field] || 0}</b></div>`).join('')}</div>`;
}

const tile = (ic, label, value, sub, tone = '--brand') => kpiTile(ic, tone, label, value, sub);

export async function analyticsPage(host) {
  await loadWords('analytics');
  const p = new URLSearchParams((location.hash.split('?')[1]) || '');
  host.innerHTML = pageHead(w('title'), esc(w('lede'))) + `<div class="loading">${esc(w('loading'))}</div>`;
  const [d, K] = await Promise.all([api(`/api/analytics?ay=${encodeURIComponent(p.get('ay') || '')}`), api('/api/clients/settings')]);
  const r = d.roll;
  const stageLabel = (id) => (K.stages.find((s) => s.id === id) || { label: id || '-' }).label;
  const toCompute = (id, ay = d.ay) => `#/compute?c=${encodeURIComponent(id)}&ay=${encodeURIComponent(ay)}`;
  const team = r.by_assignee.map((g) => ({ ...g, key: g.key || w('unassigned') }));
  const who = [...new Set(r.team.map((x) => x.who))].map((name) => ({ name, signed: (r.team.find((x) => x.who === name && x.what === 'signed') || {}).n || 0,
    filed: (r.team.find((x) => x.who === name && x.what === 'filed') || {}).n || 0 }));
  const chip = (id) => (c) => `<a class="an-chip" href="${toCompute(c.id, c.to || d.ay)}">${esc(c.name)}${
    id === 'advance_tax' ? ` · ${money(c.interest_bc)}` : id === 'tds_refund' ? ` · ${money(c.refund)}` : 'pct' in c ? ` · ${c.pct > 0 ? '+' : ''}${c.pct}%` : ''}</a>`;
  const lead = (id) => {
    const list = d.leads[id] || [], n = d.lead_n[id] || 0;
    return `<div class="card an-lead"><div class="an-lead-h"><span class="an-lead-ic">${icon(P().lead_icon[id] || 'info', 16)}</span>
        <div><b>${esc(w(`l_${id}`))}</b><div class="small muted">${esc(w(`l_${id}_sub`, { pct: id === 'shrinking' ? d.drop_pct : d.grow_pct }))}</div></div><span class="an-lead-n">${n}</span></div>
      ${list.length ? `<div class="an-chips">${list.map(chip(id)).join('')}${n > list.length
          ? `<button type="button" class="an-chip an-more" data-lead="${esc(id)}">${esc(w('see_all', { n }))}</button>` : ''}</div>`
        : `<div class="small muted">${esc(w('lead_none'))}</div>`}</div>`;
  };

  host.innerHTML = pageHead(w('title'), esc(w('lede')),
    `<label class="cl-ay" for="an-ay">${icon('clock', 14)}<span>${esc(w('ay'))}</span>
       <select id="an-ay">${d.years.map((y) => `<option ${y === d.ay ? 'selected' : ''}>${esc(y)}</option>`).join('')}</select></label>`)
    + `<section class="sf-kpis an-kpis">
        ${tile('users', w('k_clients'), String(r.clients), w('k_clients_sub', { audit: r.audit }))}
        ${tile('check', w('k_filed'), `${r.filed} / ${r.clients}`, w('k_filed_sub', { pct: pct(r.filed, r.clients) }))}
        ${tile('clock', w('k_ontime'), String(r.on_time), w('k_ontime_sub', { pct: pct(r.on_time, r.filed) }))}
        ${tile('money', w('k_tax'), money(r.tax), w('k_tax_sub'))}
        ${tile('download', w('k_refund'), money(r.refund), w('k_refund_sub', { ri: money(r.refund_interest) }), '--ok')}
        ${tile('alert', w('k_interest'), money(r.interest), w('k_interest_sub', { bc: money(r.interest_bc) }), '--warn')}
        ${tile('folder', w('k_returns'), String(r.returns), w('k_returns_sub', { years: d.history_years.length }))}</section>
      <section class="card an-card"><h3 class="rc-h">${icon('clock', 15)} ${esc(w('due_title'))}</h3><p class="small muted">${esc(w('due_sub'))}</p>
        ${stackBar(r.by_bucket, d.bucket_order, (b) => P().bucket_color[b], (b) => w(`b_${b}`))}
        ${d.radar ? '<div id="an-radar"></div>' : `<p class="small muted">${esc(w('due_none'))}</p>`}</section>
      <div class="an-grid">
        <section class="card an-card"><h3 class="rc-h">${icon('pulse', 15)} ${esc(w('pipe_title'))}</h3><p class="small muted">${esc(w('pipe_sub'))}</p>
          ${stackBar(r.by_stage, K.stages.map((s) => s.id), (s) => P().stage_color[s] || '--muted', stageLabel)}</section>
        <section class="card an-card"><h3 class="rc-h">${icon('deck', 15)} ${esc(w('mix_title'))}</h3>
          <div class="an-two"><div><h4>${esc(w('mix_form'))}</h4>${bars(r.by_form)}</div><div><h4>${esc(w('mix_status'))}</h4>${bars(r.by_status)}</div></div></section>
      </div>
      <div class="an-grid">
        <section class="card an-card"><h3 class="rc-h">${icon('users', 15)} ${esc(w('team_title'))}</h3><p class="small muted">${esc(w('team_sub'))}</p>
          <table class="cc-tbl an-tbl"><thead><tr><th>${esc(w('h_assigned'))}</th><th class="num">${esc(w('h_clients'))}</th><th class="num">${esc(w('h_filed'))}</th>
            <th class="num">${esc(w('h_open'))}</th><th class="num">${esc(w('h_tax'))}</th></tr></thead><tbody>
          ${team.map((g) => `<tr><td>${esc(g.key)}</td><td class="num">${g.n}</td><td class="num">${g.filed}</td><td class="num">${g.n - g.filed}</td><td class="num">${money(g.tax)}</td></tr>`).join('')}</tbody></table></section>
        <section class="card an-card"><h3 class="rc-h">${icon('check', 15)} ${esc(w('acts_title'))}</h3><p class="small muted">${esc(w('acts_sub'))}</p>
          <table class="cc-tbl an-tbl"><thead><tr><th>${esc(w('h_assigned'))}</th><th class="num">${esc(w('w_signed'))}</th><th class="num">${esc(w('w_filed'))}</th></tr></thead><tbody>
          ${who.map((x) => `<tr><td>${esc(x.name)}</td><td class="num">${x.signed}</td><td class="num">${x.filed}</td></tr>`).join('')}</tbody></table></section>
      </div>
      <section class="an-leads-h"><h3 class="rc-h">${icon('spark', 15)} ${esc(w('lead_title'))}</h3><p class="small muted">${esc(w('lead_sub'))}</p></section>
      <section class="an-leads">${d.lead_order.map(lead).join('')}</section>
      <section class="card an-card"><h3 class="rc-h">${icon('clock', 15)} ${esc(w('years_title'))}</h3><p class="small muted">${esc(w('years_sub'))}</p>
        <div class="an-three"><div><h4>${esc(w('y_clients'))}</h4>${bars(r.years, 'n', true)}</div><div><h4>${esc(w('y_filed'))}</h4>${bars(r.years, 'filed', true)}</div>
          <div><h4>${esc(w('y_income'))}</h4>${bars(r.years.map((y) => ({ ...y, lakh: Math.round((y.income || 0) / 100000) })), 'lakh', true)}</div></div></section>
      <p class="small muted an-note">${icon('info', 13)} ${esc(w('note'))}</p>`;
  // the radar and every lead in full: list.due_radar / list.advice_leads, searched and paged on the server
  const radar = host.querySelector('#an-radar');
  if (radar) listBox(radar, { list: 'due_radar', args: { ay: d.ay },
    wrap: (html) => `<div class="an-scroll"><table class="cc-tbl an-tbl"><thead><tr><th>${esc(w('h_client'))}</th><th>${esc(w('h_form'))}</th><th>${esc(w('h_due'))}</th>
            <th>${esc(w('h_days'))}</th><th>${esc(w('h_stage'))}</th><th>${esc(w('h_who'))}</th></tr></thead><tbody>${html}</tbody></table></div>`,
    row: (x) => `<tr><td><a href="${toCompute(x.id)}">${esc(x.name)}</a></td><td>${esc(x.form)}</td><td>${esc(day(x.due))}</td>
            <td><span class="an-days" style="--c:var(${P().bucket_color[x.bucket]})">${esc(x.days_left < 0 ? w('days_late', { n: -x.days_left }) : w('days_left', { n: x.days_left }))}</span></td>
            <td>${esc(stageLabel(x.stage))}</td><td>${esc(x.assigned || w('unassigned'))}</td></tr>` });
  host.querySelectorAll('[data-lead]').forEach((b) => { b.onclick = () => modal(w(`l_${b.dataset.lead}`), '<div data-all></div>', {
    onOpen: (m, close) => listBox(m.querySelector('[data-all]'), { list: 'advice_leads', args: { ay: d.ay, lead: b.dataset.lead },
      wrap: (html) => `<div class="an-chips">${html}</div>`, row: chip(b.dataset.lead), wire: (rows) => rows.querySelectorAll('a').forEach((a) => { a.onclick = () => close(); }) }) }); });
  host.querySelector('#an-ay').onchange = (e) => { location.hash = `#/analytics?ay=${encodeURIComponent(e.target.value)}`; };
}
