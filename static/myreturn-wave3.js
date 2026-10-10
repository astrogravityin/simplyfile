// My return, wave 3 (2026-10-07): residential status (s.6), income from outside India (Schedule FSI / TR), foreign assets (Schedule FA),
// clubbed income (s.64, Schedule SPI), salary arrears (s.89, Form 10E) and the updated return of an earlier year (ITR-U). The server
// (myreturn.py, chips myreturn.residence / foreign_row / club_row / relief_89 / itru) decides; this draws and sends what is typed.
// Words: chip ui.myreturn.
import { esc, t } from './app.js';
import { icon } from './icons.js';

const w = (k, v) => t('myreturn', k, v);
const money = (n) => `₹${Math.round(Number(n || 0)).toLocaleString('en-IN')}`;
const pairs = (key) => w(key).split('|').map((x) => x.split('='));
const opt = (v, list) => list.map(([o, l]) => `<option value="${esc(o)}" ${String(v ?? '') === o ? 'selected' : ''}>${esc(l)}</option>`).join('');

// one typed row: each field a text / number / date input, a select (pairs from a word) or a checkbox
function rowOf(tag, key, i, x, fields) {
  return fields.map(([k, ty, list]) => {
    const id = `${tag}-${i}-${k}`;
    const lab = `<label for="${id}">${esc(w(`f_${tag}_${k}`))}</label>`;
    if (ty === 'check') return `<label class="check mr-ai"><input type="checkbox" id="${id}" ${key}="${k}" ${x[k] ? 'checked' : ''}/> <span>${esc(w(`f_${tag}_${k}`))}</span></label>`;
    if (ty === 'sel') return `<div class="field">${lab}<select id="${id}" ${key}="${k}">${opt(x[k], list)}</select></div>`;
    const v = ty === 'num' ? (x[k] ? Math.round(x[k]) : '') : (x[k] || '');
    return `<div class="field">${lab}<input id="${id}" ${key}="${k}" ${ty === 'num' ? 'inputmode="decimal" placeholder="0"' : `type="${ty === 'date' ? 'date' : 'text'}" maxlength="125"`} value="${esc(v)}" autocomplete="off"/></div>`;
  }).join('');
}

export function resCard(d) {
  const a = d.answers; const res = d.res || {};
  const num = (k) => `<div class="field"><label for="q-${k}">${esc(w(`f_${k}`))}</label><input id="q-${k}" inputmode="numeric" data-qt="${k}" value="${esc(a[k] ?? '')}" placeholder=""/></div>`;
  const chk = (k) => `<label class="check"><input type="checkbox" data-q="${k}" ${a[k] ? 'checked' : ''}/> <span>${esc(w(`q_${k}`))}</span></label>`;
  const nr = res.status === 'NR';
  return `<section class="card"><h3 class="rc-h">${icon('flag', 15)} ${esc(w('rs_h'))} <span class="tag ${res.status === 'ROR' ? 'ok' : 'warn'}">${esc(w(`rs_${res.status || 'ROR'}`))}</span></h3>
    <p class="small muted">${esc(w('rs_p'))}</p>
    <div class="grid four">${num('days_fy')}${num('days_4y')}${num('nr_years')}${num('days_7y')}${num('indian_income')}</div>
    <div class="mr-qs">${['citizen', 'pio', 'visiting', 'left_for_job', 'taxed_elsewhere'].map(chk).join('')}</div>
    ${nr ? `<div class="grid three"><div class="field"><label for="q-res_country">${esc(w('f_res_country'))}</label><select id="q-res_country" data-qt="res_country"><option value=""></option>${opt(a.res_country, d.countries || [])}</select></div>
      <div class="field"><label for="q-res_tin">${esc(w('f_res_tin'))}</label><input id="q-res_tin" data-qt="res_tin" maxlength="75" value="${esc(a.res_tin || '')}" autocomplete="off"/></div></div>` : ''}
    <p class="small"><b>${esc(res.known ? w(res.why) : w('rs_unknown'))}</b></p>
    ${nr ? `<p class="small muted">${esc(w('rs_nr_note'))}</p>` : res.status === 'RNOR' ? `<p class="small muted">${esc(w('rs_rnor_note'))}</p>` : ''}</section>`;
}

export function foreignCard(r, d) {
  const g = d.regimes[d.regime]; const ex = r.extra || {}; const rel = g.relief || {};
  const rows = (r.foreign_rows || []).map((x, i) => {
    const c = (ex.foreign || [])[i] || {};
    const more = x.head === 'salary' ? [['employer', 'text'], ['city', 'text'], ['zip', 'text']] : x.head === 'house' ? [['address', 'text'], ['zip', 'text'], ['municipal_tax', 'num'], ['interest', 'num']] : [];
    return `<div class="mr-cg" data-fi="${i}"><div class="grid four">${rowOf('fi', 'data-fv', i, x, [['country', 'sel', [['', ''], ...(d.countries || [])]], ['head', 'sel', pairs('fi_heads')],
      ['amount', 'num'], ['tax_paid', 'num'], ['sec', 'sel', [['', ''], ...pairs('fi_secs')]], ['article', 'text'], ['tin', 'text'], ...more,
      ...(d.res && d.res.status === 'RNOR' && x.head === 'business' ? [['controlled', 'check']] : [])])}</div>
      ${c.counts === false ? `<p class="small muted">${esc(w('fi_not', { status: w(`rs_${d.res.status}`) }))}</p>` : ''}</div>`;
  }).join('');
  const relief = (rel.s90 || 0) + (rel.s91 || 0);
  return `<section class="card"><h3 class="rc-h">${icon('globe', 15)} ${esc(w('fi_h'))}</h3><p class="small muted">${esc(w('fi_p'))}</p>
    ${rows || `<p class="muted small">${esc(w('fi_none'))}</p>`}
    ${relief ? `<p class="small"><b>${esc(w('fi_relief', { amount: money(relief), dtaa: money(rel.s90), other: money(rel.s91) }))}</b></p><p class="small mr-warn">${icon('alert', 12)} ${esc(w('fi_form67'))}</p>` : ''}
    <button type="button" class="small ghost" id="mr-fi-add">${icon('plus', 12)} ${esc(w('fi_add'))}</button></section>`;
}

export function faCard(r, d) {
  const need = d.res && d.res.status === 'ROR';
  const head = [['kind', 'sel', pairs('fa_kinds')], ['country', 'sel', [['', ''], ...(d.countries || [])]], ['name', 'text'], ['address', 'text'], ['zip', 'text']];
  const offered = [['taxed', 'num'], ['sch', 'sel', pairs('fa_schs')], ['sch_no', 'text']];
  // 2026-10-08: Schedule FA D-F - an account you can sign for, a trust abroad, other income from outside India
  const more = {
    // 2026-10-10: table B - an interest in a foreign company, firm or other entity
    financial: [['nature', 'text'], ['status', 'sel', pairs('fa_statuses')], ['opened', 'date'], ['cost', 'num'], ['income', 'num'], ['inc_nature', 'text'], ...offered],
    signing: [['holder', 'text'], ['account', 'text'], ['peak', 'num'], ['income', 'num'], ...offered],
    trust: [['trustees', 'text'], ['trustees_addr', 'text'], ['settlor', 'text'], ['settlor_addr', 'text'], ['beneficiaries', 'text'], ['beneficiaries_addr', 'text'],
      ['opened', 'date'], ['income', 'num'], ...offered],
    income: [['income', 'num'], ['nature', 'text'], ...offered],
  };
  const rows = (r.fa_rows || []).map((x, i) => `<div class="mr-cg" data-fa="${i}"><div class="grid four">${rowOf('fa', 'data-fav', i, x, more[x.kind] ? [...head, ...more[x.kind]] : [
    ...head, ...(['bank', 'custodial'].includes(x.kind || 'bank') ? [['account', 'text']] : []), ['status', 'sel', pairs('fa_statuses')], ['opened', 'date'],
    ['peak', 'num'], ['closing', 'num'], ['income', 'num'], ['cost', 'num'], ['proceeds', 'num'], ['nature', 'text'],
    ...(['property', 'other'].includes(x.kind) ? offered : [])])}</div></div>`).join('');
  return `<section class="card"><h3 class="rc-h">${icon('folder', 15)} ${esc(w('fa_h'))}</h3><p class="small muted">${esc(w('fa_p'))}</p>
    ${need ? '' : `<p class="small muted">${esc(w('fa_not_needed', { status: w(`rs_${(d.res || {}).status || 'ROR'}`) }))}</p>`}
    ${rows || `<p class="muted small">${esc(w('fa_none'))}</p>`}
    <button type="button" class="small ghost" id="mr-fa-add">${icon('plus', 12)} ${esc(w('fa_add'))}</button></section>`;
}

export function clubCard(r, d) {
  const ex = r.extra || {};
  const hs = d.regimes[d.regime].houses || [];
  const rows = (r.club_rows || []).map((x, i) => {
    const c = { ...((ex.club || [])[i] || {}) };
    if (c.house_i !== null && c.house_i !== undefined && hs[c.house_i]) c.included = hs[c.house_i].net;   // a house: what it adds, after the 30% and interest
    return `<div class="mr-cg" data-cl="${i}"><div class="grid four">${rowOf('cl', 'data-clv', i, x, [['name', 'text'], ['pan', 'text'], ['relation', 'sel', pairs('cl_relations')],
      ['head', 'sel', pairs('cl_heads')], ['amount', 'num'], ...(x.head === 'house' ? [['address', 'text']] : []),
      ...(x.relation === 'minor_child' || !x.relation ? [['skill', 'check'], ['disabled', 'check']] : [])])}</div>
      <p class="small">${c.counts === false ? esc(w('cl_not')) : c.counts ? `${esc(w('cl_in', { amount: money(c.included) }))}${c.exempt ? ` · ${esc(w('cl_exempt', { amount: money(c.exempt) }))}` : ''}` : ''}</p></div>`;
  }).join('');
  return `<section class="card"><h3 class="rc-h">${icon('users', 15)} ${esc(w('cl_h'))}</h3><p class="small muted">${esc(w('cl_p'))}</p>
    ${rows || `<p class="muted small">${esc(w('cl_none'))}</p>`}
    <button type="button" class="small ghost" id="mr-cl-add">${icon('plus', 12)} ${esc(w('cl_add'))}</button></section>`;
}

export function arrearCard(r, d) {
  const rel = d.regimes[d.regime].relief || {};
  const rows = (r.arrears || []).map((x, i) => `<div class="grid four" data-ar="${i}">${rowOf('ar', 'data-arv', i, x, [['fy', 'text'], ['amount', 'num'], ['income', 'num'], ['regime', 'sel', pairs('ar_regimes')]])}</div>`).join('');
  const said = !(r.arrears || []).length ? '' : rel.unknown89 ? `<p class="small mr-warn">${esc(w('ar_unknown'))}</p>`
    : rel.s89 ? `<p class="small"><b>${esc(w('ar_relief', { amount: money(rel.s89), now: money(rel.now_extra), past: money(rel.past) }))}</b></p><p class="small mr-warn">${icon('alert', 12)} ${esc(w('ar_form10e'))}</p>`
      : `<p class="small muted">${esc(w('ar_nil'))}</p>`;
  return `<section class="card"><h3 class="rc-h">${icon('clock', 15)} ${esc(w('ar_h'))}</h3><p class="small muted">${esc(w('ar_p'))}</p>
    ${rows || `<p class="muted small">${esc(w('ar_none'))}</p>`}${said}
    <button type="button" class="small ghost" id="mr-ar-add">${icon('plus', 12)} ${esc(w('ar_add'))}</button></section>`;
}

export function itruCard(d) {
  const u = d.itru || {};
  const f = (k, ty, list) => rowOf('iu', 'data-iu', 0, u, [[k, ty, list]]);
  const ids = d.itru_bars || [];
  const lines = w('iu_lines', { pct: u.pct || 0 }).split('|');
  const vals = [u.tax_before, u.tax_after, u.extra_tax, u.i234a, u.i234b, u.i234c, u.additional, u.fee_234f, u.pay];
  const result = !u.ay ? `<p class="small muted">${esc(w('iu_none'))}</p>` : !u.ok ? `<p class="small mr-warn">${icon('alert', 12)} ${esc(w(u.why))}</p>`
    : `<p class="small mr-ok">${icon('check', 12)} ${esc(w('iu_ok', { by: String(u.updated_by || '').replace(/(\d{4})(\d{2})(\d{2})/, '$3-$2-$1') }))}</p>
      <table class="mr-cmp-t"><tbody>${lines.map((l, n) => `<tr><td>${esc(l)}</td><td class="num">${money(vals[n])}</td></tr>`).join('')}</tbody></table>
      ${u.surcharge ? `<p class="small muted">${esc(w('iu_sur', { amount: money(u.surcharge) }))}</p>` : ''}
      <ol class="small">${w('iu_steps', { ay: u.ay }).split('|').map((s) => `<li>${esc(s)}</li>`).join('')}</ol>
      ${u.schema ? '' : `<p class="small muted">${esc(w('iu_no_schema', { ay: u.ay }))}</p>`}`;
  return `<section class="card"><h3 class="rc-h">${icon('refresh', 15)} ${esc(w('iu_h'))}</h3><p class="small muted">${esc(w('iu_p'))}</p>
    <div class="grid four" data-iurow>${f('ay', 'sel', [['', ''], ...(d.itru_years || []).map((y) => [y, y])])}${f('filed', 'sel', pairs('iu_filed'))}${f('orig_income', 'num')}${f('added', 'num')}
      ${f('tds_added', 'num')}${f('tds', 'num')}${f('advance', 'num')}${f('regime', 'sel', pairs('ar_regimes'))}${f('reason', 'sel', [['', ''], ...pairs('iu_reasons')])}${f('on', 'date')}</div>
    <details class="mr-more" ${['orig_111a', 'orig_112a', 'orig_112', 'orig_30', 'add_111a', 'add_112a', 'add_112', 'add_30'].some((k) => u[k]) ? 'open' : ''}><summary>${esc(w('iu_special_h'))}</summary>
      <div class="grid four" data-iurow2>${['orig_111a', 'orig_112a', 'orig_112', 'orig_30', 'add_111a', 'add_112a', 'add_112', 'add_30'].map((k) => f(k, 'num')).join('')}
        ${u.ay === '2025-26' ? f('early', 'sel', pairs('iu_early')) : ''}</div></details>
    <details class="mr-more" ${['adv_q1', 'adv_q2', 'adv_q3', 'adv_q4'].some((k) => u[k]) ? 'open' : ''}><summary>${esc(w('iu_adv_h'))}</summary>
      <div class="grid four">${['adv_q1', 'adv_q2', 'adv_q3', 'adv_q4'].map((k) => f(k, 'num')).join('')}</div></details>
    <h4 class="small">${esc(w('iu_bars_h'))}</h4><div class="mr-qs">${ids.map((b) => `<label class="check"><input type="checkbox" data-iub="${b}" ${(u.bars || []).includes(b) ? 'checked' : ''}/> <span>${esc(w(`iu_bar_${b}`))}</span></label>`).join('')}</div>
    ${result}</section>`;
}

// what is typed, sent back: each card's rows (a checkbox as true / false), the ITR-U card as one record
export function wireWave3(host, S, put) {
  const $ = (s) => host.querySelector(s);
  const rows = (sel, key) => [...host.querySelectorAll(`[${sel}]`)].map((el) => Object.fromEntries([...el.querySelectorAll(`[${key}]`)].map((x) => [x.getAttribute(key), x.type === 'checkbox' ? x.checked : x.value])));
  const cards = [['data-fi', 'data-fv', 'foreign_rows', '#mr-fi-add', { head: 'salary' }], ['data-fa', 'data-fav', 'fa_rows', '#mr-fa-add', { kind: 'bank' }],
    ['data-cl', 'data-clv', 'club_rows', '#mr-cl-add', { relation: 'minor_child', head: 'interest' }], ['data-ar', 'data-arv', 'arrears', '#mr-ar-add', {}]];
  for (const [sel, key, body, add, blank] of cards) {
    host.querySelectorAll(`[${key}]`).forEach((i) => { i.onchange = () => put({ [body]: rows(sel, key) }); });
    if ($(add)) $(add).onclick = () => put({ [body]: [...rows(sel, key), blank] });
  }
  const iu = () => ({ ...Object.fromEntries([...host.querySelectorAll('[data-iu]')].map((x) => [x.dataset.iu, x.value])),
    bars: [...host.querySelectorAll('[data-iub]:checked')].map((x) => x.dataset.iub) });
  host.querySelectorAll('[data-iu], [data-iub]').forEach((i) => { i.onchange = () => put({ itru: iu() }); });
  return S;
}
