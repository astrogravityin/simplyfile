// A company's return (ITR-6), 2026-10-11 - the company part of the Clients editor and the company section of Compute & close.
// Every figure and verdict is the server's (company.py asks chips company.*); this file only draws and sends what was typed.
// Words: chips ui.clients (co_*) and ui.compute (co_*, lo_*, why_*).
import { api, esc, toast, busy, t, confirmDialog } from './app.js';
import { icon } from './icons.js';

// the section's own few styles, once (kept here so the shared stylesheet is not touched)
if (!document.getElementById('co-css')) {
  document.head.insertAdjacentHTML('beforeend', `<style id="co-css">
  .co-card{margin-top:16px}.co-rate{margin:6px 0 10px}.co-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px;margin:10px 0}
  .co-panel{border:1px solid var(--line);border-radius:12px;padding:10px 12px;background:var(--panel)}.co-panel h4{margin:0 0 8px}.co-panel h5{margin:10px 0 4px}
  .co-wide{grid-column:1/-1}.co-dep{width:100%;border-collapse:collapse;font-size:13px}.co-dep th,.co-dep td{padding:5px 8px;border-bottom:1px solid var(--line)}.co-dep th{font-weight:600;font-size:12px;text-align:left;color:var(--muted)}.co-dep .num{text-align:right;white-space:nowrap}.co-dep tr.co-tot td{font-weight:700;border-bottom:0}.co-wide .co-dep td:first-child{min-width:190px}.co-bad{color:var(--bad);font-size:12px}
  .co-year{margin-top:10px}.co-year summary{cursor:pointer;margin-bottom:8px}.co-row{flex-wrap:wrap;margin-bottom:6px}.co-box h3{margin-top:0}
  @media (max-width:640px){.co-dep{display:block;overflow-x:auto}}</style>`);
}
const wc = (k, v) => t('clients', k, v);
const wk = (k, v) => t('compute', k, v);
const money = (n) => `₹${Math.round(Number(n || 0)).toLocaleString('en-IN')}`;
const fld = (id, label, value = '', attrs = '') => `<div class="field"><label for="${id}">${esc(label)}</label>
  <input id="${id}" value="${esc(value ?? '')}" ${attrs}/></div>`;
const check = (id, label, on) => `<label class="check" style="align-self:end;min-height:40px"><input type="checkbox" id="${id}" ${on ? 'checked' : ''}/> <span>${esc(label)}</span></label>`;
const pick = (id, label, rows, value) => `<div class="field"><label for="${id}">${esc(label)}</label><select id="${id}">${rows.map((r) =>
  `<option value="${esc(r.id)}" ${r.id === value ? 'selected' : ''}>${esc(r.label)}</option>`).join('')}</select></div>`;

// rows of inputs (directors, shareholders, losses, credits): removing one asks first (every remove confirms)
function rows(kind, items, cols, words) {
  const one = (x = {}) => `<div class="row tight co-row" data-${kind} style="align-items:end">${cols.map(([f, label, type]) => type === 'check'
    ? `<label class="check small" style="min-width:90px"><input type="checkbox" data-f="${f}" ${x[f] === false ? '' : 'checked'}/> <span>${esc(words(label))}</span></label>`
    : `<div class="field" style="flex:1;min-width:96px;margin:0"><label>${esc(words(label))}</label><input data-f="${f}" ${type ? `type="${type}"` : ''} value="${esc(x[f] ?? '')}"/></div>`).join('')}
    <button type="button" class="small ghost" data-co-rm aria-label="${esc(wc('remove'))}">${icon('close', 12)}</button></div>`;
  return { html: (items || []).map(one).join(''), one };
}
const readRows = (box, kind) => [...box.querySelectorAll(`[data-${kind}]`)].map((r) => Object.fromEntries([...r.querySelectorAll('[data-f]')]
  .map((i) => [i.dataset.f, i.type === 'checkbox' ? i.checked : i.value])));
function wireRemove(box) {
  box.querySelectorAll('[data-co-rm]').forEach((b) => { b.onclick = () => confirmDialog(wc('remove'), wc('co_remove_row'), () => b.parentElement.remove(), wc('remove'), { tone: 'warn' }); });
}

const DIRECTOR = [['name', 'co_d_name'], ['din', 'co_d_din'], ['pan', 'co_d_pan'], ['designation', 'co_d_designation'], ['father', 'co_d_father'], ['address', 'co_d_address']];
const HOLDER = [['name', 'co_h_name'], ['pan', 'co_h_pan'], ['pct', 'co_h_pct'], ['shares', 'co_h_shares'], ['face', 'co_h_face'], ['issue', 'co_h_issue'],
  ['allotted', 'co_h_allotted'], ['address', 'co_h_address']];

// --- Clients & years: the company part (shown when the status is Company) ------------------------------------------------------
export function companyBox(c, K) {
  const co = (c && c.company) || {};
  const S = K.company || { kinds: [], options: [] };
  const dirs = rows('co-dir', co.directors || [], DIRECTOR, wc);
  const holders = rows('co-holder', co.shareholders || [], HOLDER, wc);
  return `<div id="co-box" class="card co-box" style="margin-top:14px"><h3>${icon('flag', 15)} ${esc(wc('co_box'))}</h3>
    <p class="small muted">${esc(wc('co_lede'))}</p>
    <div class="grid two">${fld('co-cin', wc('co_cin'), co.cin, 'maxlength="21" style="text-transform:uppercase"')}
      ${fld('co-inc', wc('co_incorporated'), co.incorporated, 'type="date"')}
      ${pick('co-kind', wc('co_kind'), S.kinds, co.kind)}${pick('co-option', wc('co_option'), S.options, co.option)}
      ${fld('co-opt-ay', wc('co_option_ay'), co.option_ay, 'maxlength="7" placeholder="2021-22"')}${fld('co-opt-ack', wc('co_option_ack'), co.option_ack, 'inputmode="numeric" maxlength="15"')}
      ${fld('co-opt-date', wc('co_option_date'), co.option_date, 'type="date"')}${fld('co-nature', wc('co_nature'), co.nature_code, 'inputmode="numeric" maxlength="5"')}
      ${fld('co-trade', wc('co_trade'), co.trade_name)}
      ${check('co-mfg', wc('co_manufacturing'), co.manufacturing)}${check('co-msme', wc('co_msme'), co.msme)}${check('co-indas', wc('co_indas'), co.indas)}</div>
    <h3 style="margin-top:12px">${esc(wc('co_directors'))}</h3><p class="small muted">${esc(wc('co_directors_lede'))}</p>
    <div id="co-dirs">${dirs.html}</div><button type="button" class="small ghost" id="co-add-dir">${icon('plus', 12)} ${esc(wc('co_add_director'))}</button>
    <h3 style="margin-top:12px">${esc(wc('co_holders'))}</h3><p class="small muted">${esc(wc('co_holders_lede'))}</p>
    <div id="co-holders">${holders.html}</div><button type="button" class="small ghost" id="co-add-holder">${icon('plus', 12)} ${esc(wc('co_add_holder'))}</button></div>`;
}

export function wireCompanyBox(card, K) {
  const box = card.querySelector('#co-box');
  if (!box) return;
  const dirs = rows('co-dir', [], DIRECTOR, wc), holders = rows('co-holder', [], HOLDER, wc);
  box.querySelector('#co-add-dir').onclick = () => { box.querySelector('#co-dirs').insertAdjacentHTML('beforeend', dirs.one()); wireRemove(box); };
  box.querySelector('#co-add-holder').onclick = () => { box.querySelector('#co-holders').insertAdjacentHTML('beforeend', holders.one()); wireRemove(box); };
  wireRemove(box);
  const show = () => {
    const st = K.statuses.find((s) => s.id === card.querySelector('#c-status').value);
    box.style.display = st && st.has_company ? '' : 'none';
  };
  card.querySelector('#c-status').addEventListener('change', show);
  show();
}

export function readCompany(card) {
  const box = card.querySelector('#co-box');
  if (!box || box.style.display === 'none') return undefined;
  const v = (id) => box.querySelector(id).value;
  return { cin: v('#co-cin'), incorporated: v('#co-inc'), kind: v('#co-kind'), option: v('#co-option'), option_ay: v('#co-opt-ay'),
    option_ack: v('#co-opt-ack'), option_date: v('#co-opt-date'), nature_code: v('#co-nature'), trade_name: v('#co-trade'),
    manufacturing: box.querySelector('#co-mfg').checked, msme: box.querySelector('#co-msme').checked, indas: box.querySelector('#co-indas').checked,
    directors: readRows(box, 'co-dir'), shareholders: readRows(box, 'co-holder') };
}

// --- Compute & close: the company section -------------------------------------------------------------------------------------
const BF = [['ay', 'co_bf_ay'], ['business', 'co_bf_business'], ['dep', 'co_bf_dep'], ['filed_on', 'co_bf_filed', 'date'], ['filed_ok', 'co_bf_ok', 'check']];
const MC = [['ay', 'co_mc_ay'], ['amount', 'co_mc_amount']];

export function companyCard(d, K, ro) {
  const co = d.company, y = co.year || {}, r = co.rate, m = co.mat;
  const opt = ((K.company || {}).options || []).find((o) => o.id === co.option) || { label: co.option };
  const py = co.turnover_py_label;
  const bf = rows('co-bf', y.bf_losses || [], BF, wk), mc = rows('co-mc', y.mat_credit || [], MC, wk);
  const tr = (label, v, cls = '') => `<tr class="${cls}"><td>${esc(label)}</td><td class="num">${esc(money(v))}</td></tr>`;
  const dep = co.dep.blocks.length ? `<div style="overflow-x:auto"><table class="co-dep"><thead><tr><th>${esc(wk('co_dep_block'))}</th><th class="num">${esc(wk('co_dep_open'))}</th>
      <th class="num">${esc(wk('co_dep_add'))}</th><th class="num">${esc(wk('co_dep_sales'))}</th><th class="num">${esc(wk('co_dep_dep'))}</th>
      <th class="num">${esc(wk('co_dep_addl'))}</th><th class="num">${esc(wk('co_dep_wdv'))}</th></tr></thead><tbody>
      ${co.dep.blocks.map((b) => `<tr><td>${esc(b.label)}</td><td class="num">${esc(money(b.in.opening))}</td>
        <td class="num">${esc(money(b.in.more))} / ${esc(money(b.in.less))}</td><td class="num">${esc(money(b.in.sales))}</td>
        <td class="num">${esc(money(b.dep_full + b.dep_half))}</td><td class="num">${b.addl ? esc(money(b.addl)) : '-'}</td><td class="num">${esc(money(b.wdv_last))}</td></tr>`).join('')}
      <tr class="co-tot"><td colspan="4">${esc(wk('co_dep_total'))}</td><td class="num" colspan="3">${esc(money(co.dep.total))}</td></tr></tbody></table></div>`
    : `<p class="small muted">${esc(wk('co_dep_none'))}</p>`;
  const bfRows = co.bfla.length ? `<table class="co-dep"><tbody>${co.bfla.map((x) => `<tr><td><b>${esc(x.ay)}</b> · ${esc(wk(x.kind === 'dep' ? 'co_bf_dep' : 'co_bf_business'))}
      <div class="${x.ok ? 'muted' : 'co-bad'}">${esc(wk(x.why))}</div></td><td class="num">${esc(money(x.amount))}<div class="small muted">−${esc(money(x.used))} → ${esc(money(x.left))}</div></td></tr>`).join('')}</tbody></table>` : '';
  const cr = co.credits.length ? `<table class="co-dep"><tbody>${co.credits.map((x) => `<tr><td><b>${esc(x.ay)}</b><div class="${x.ok ? 'muted' : 'co-bad'}">${esc(wk(x.why))}</div></td>
      <td class="num">${esc(money(x.amount))}<div class="small muted">−${esc(money(x.used))} → ${esc(money(x.left))}</div></td></tr>`).join('')}</tbody></table>` : '';
  const cf = co.cyla;
  return `<section class="card co-card" id="co-card"><div class="cc-comp-top"><h3 class="rc-h">${icon('flag', 15)} ${esc(wk('co_title'))}</h3>
      <span class="tag brand">${esc(opt.label)}</span></div>
    <p class="small muted">${esc(wk('co_lede'))}</p>
    <div class="co-rate"><b>${esc(wk('co_rate'))} ${esc(r.rate)}%${r.split_business ? ` / ${esc(r.other_rate)}%` : ''}</b> · ${esc(wk('co_surcharge'))}
      ${esc(r.flat ? wk('co_sur_flat', { rate: r.steps[0].rate }) : wk('co_sur_bands'))}<div class="small muted">${esc(wk(r.why, { py }))}</div></div>
    ${co.warnings.map((x) => `<div class="cc-warn">${icon('alert', 15)} ${esc(wk(x, { py }))}</div>`).join('')}
    <div class="co-grid">
      <div class="co-panel co-wide"><h4>${esc(wk('co_dep'))}</h4>${dep}</div>
      <div class="co-panel"><h4>${esc(wk('co_setoff'))}</h4><table class="co-dep"><tbody>
        ${cf.hp_used ? tr(wk('co_cyla_hp'), cf.hp_used) : ''}${cf.bp_used ? tr(wk('co_cyla_bp'), cf.bp_used) : ''}</tbody></table>
        ${bfRows ? `<h5>${esc(wk('co_bfla'))}</h5>${bfRows}` : ''}
        <table class="co-dep"><tbody>${tr(wk('co_cf_business'), cf.bp_cf)}${tr(wk('co_cf_dep'), cf.ud_cf + co.bfla.filter((x) => x.kind === 'dep').reduce((a, x) => a + x.left, 0))}
          ${cf.hp_cf ? tr(wk('co_cf_hp'), cf.hp_cf) : ''}${co.cg.st_loss_cf + co.cg.lt_loss_cf ? tr(wk('co_cf_cg'), co.cg.st_loss_cf + co.cg.lt_loss_cf) : ''}</tbody></table>
        <p class="small muted">${esc(wk('co_cf_note'))}</p>
        <h5>${esc(wk('co_80m'))} · ${esc(wk('co_80g'))}</h5><table class="co-dep"><tbody>
          <tr><td>${esc(wk('co_80m'))}${co.d80m.deduction || !y.dividend_paid ? '' : `<div class="co-bad">${esc(wk('co_80m_late'))}</div>`}</td><td class="num">${esc(money(co.d80m.deduction))}</td></tr>
          <tr><td>${esc(wk('co_80g'))}${co.rate.via.includes('80G') ? '' : `<div class="muted">${esc(wk('co_80g_barred'))}</div>`}</td><td class="num">${esc(money(co.d80g.total))}</td></tr></tbody></table></div>
      <div class="co-panel"><h4>${esc(wk('co_mat'))}</h4>${r.mat ? `<table class="co-dep"><tbody>
          <tr><td>${esc(wk('co_book_profit'))}${co.book_from === 'pl' ? `<div class="small muted">${esc(wk('co_book_from_pl'))}</div>` : ''}</td><td class="num">${esc(money(co.book_profit))}</td></tr>
          ${tr(wk('co_normal_tax'), co.normal.total)}${tr(wk('co_mat_tax', { rate: 15 }), m.mat)}</tbody></table>
          <div class="cc-check ${m.pays_mat ? 'is-bad' : 'is-ok'}">${esc(m.pays_mat ? wk('co_pays_mat', { amount: money(co.credit_new) }) : wk('co_pays_normal'))}</div>
          ${m.credit_used ? `<table class="co-dep"><tbody>${tr(wk('co_credit_used'), m.credit_used)}</tbody></table>` : ''}`
        : `<p class="small muted">${esc(wk('co_mat_none', { option: opt.label }))}</p>`}
        ${cr ? `<h5>${esc(wk('co_mc'))}</h5>${cr}` : ''}
        <table class="co-dep"><tbody>${tr(wk('co_credit_cf'), co.credits.reduce((a, x) => a + x.left, 0) + co.credit_new)}</tbody></table></div>
    </div>
    <details class="co-year" ${ro ? '' : 'open'}><summary><b>${esc(wk('co_year'))}</b></summary>
      <div class="grid two">${fld('co-turnover', wk('co_turnover', { py }), y.turnover_py || '', 'type="number" min="0" step="1"')}
        ${check('co-s79', wk('co_s79'), y.s79_ok !== false)}
        ${fld('co-div', wk('co_div_paid'), y.dividend_paid || '', 'type="number" min="0" step="1"')}${fld('co-div-on', wk('co_div_on'), y.dividend_paid_on, 'type="date"')}
        ${co.option !== 'normal' ? check('co-opt-now', wk('co_opt_now'), y.opt_now) + fld('co-opt-now-ack', wk('co_opt_ack'), y.opt_now_ack, 'inputmode="numeric" maxlength="15"')
          + fld('co-opt-now-date', wk('co_opt_date'), y.opt_now_date, 'type="date"') : ''}
        ${fld('co-audit-on', wk('co_audit_on'), y.audit_on, 'type="date"')}${fld('co-audit-ack', wk('co_audit_ack'), y.audit_ack, 'inputmode="numeric" maxlength="15"')}</div>
      <h5>${esc(wk('co_bf'))}</h5><div id="co-bfs">${bf.html}</div>
      <button type="button" class="small ghost" id="co-add-bf" ${ro ? 'disabled' : ''}>${icon('plus', 12)} ${esc(wk('co_add_bf'))}</button>
      <h5>${esc(wk('co_mc'))}</h5><div id="co-mcs">${mc.html}</div>
      <button type="button" class="small ghost" id="co-add-mc" ${ro ? 'disabled' : ''}>${icon('plus', 12)} ${esc(wk('co_add_mc'))}</button>
      ${ro ? '' : `<div class="row tight" style="margin-top:10px"><button type="button" class="primary" id="co-save">${icon('save', 14)} ${esc(wk('co_save'))}</button></div>`}
    </details></section>`;
}

export function wireCompanyCard(host, d, base, redraw) {
  const card = host.querySelector('#co-card');
  if (!card) return;
  const bf = rows('co-bf', [], BF, wk), mc = rows('co-mc', [], MC, wk);
  const add = (btn, list, r) => { const b = card.querySelector(btn); if (b) b.onclick = () => { card.querySelector(list).insertAdjacentHTML('beforeend', r.one()); wireRemove(card); }; };
  add('#co-add-bf', '#co-bfs', bf);
  add('#co-add-mc', '#co-mcs', mc);
  wireRemove(card);
  const save = card.querySelector('#co-save');
  if (!save) return;
  save.onclick = () => busy(save, async () => {
    const v = (id) => (card.querySelector(id) || {}).value || '';
    const on = (id) => !!(card.querySelector(id) || {}).checked;
    const body = { company: { turnover_py: v('#co-turnover'), s79_ok: on('#co-s79'), dividend_paid: v('#co-div'), dividend_paid_on: v('#co-div-on'),
      opt_now: on('#co-opt-now'), opt_now_ack: v('#co-opt-now-ack'), opt_now_date: v('#co-opt-now-date'), audit_on: v('#co-audit-on'),
      audit_ack: v('#co-audit-ack'), bf_losses: readRows(card, 'co-bf'), mat_credit: readRows(card, 'co-mc') } };
    try { redraw(await api(base, { method: 'PUT', body })); toast(wk('co_saved'), 'ok'); } catch (err) { toast(err.message, 'bad', 8); }
  });
}
