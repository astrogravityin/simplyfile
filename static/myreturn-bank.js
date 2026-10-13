// The Classify step of My return (2026-10-13, "Small business - only a bank statement"): a bank statement's money in and out,
// grouped by who it is with, each group pre-selected by chip bank.classify's rules; the person taps what each one is
// (Customer receipts / Cash takings / Own money / Loan / Not income) and the turnover, the profit at the presumptive rates, the
// GST limit and what is still needed update at once. myreturn.py / bankclass.py decide (chips bank.*); this draws.
// Words: chip ui.bankonly. Values of names, accounts and amounts carry data-sens so a recorder's privacy mask can blur them.
import { api, esc, toast, t } from './app.js';
import { icon } from './icons.js';

const k = (key, v) => t('bankonly', key, v);
const money = (n) => `₹${Math.round(Number(n || 0)).toLocaleString('en-IN')}`;
const SUMS = ['receipt', 'friend', 'cash', 'own', 'loan', 'other', 'ask'];

/** The totals of a classification, by class, for credits - from the groups as they stand now (taps included). */
function sums(groups) {
  const o = Object.fromEntries(SUMS.map((c) => [c, 0]));
  groups.filter((g) => g.dir === 'cr').forEach((g) => { o[g.class] = (o[g.class] || 0) + g.total; });
  return o;
}

const summary = (b, d) => {
  const cl = b.classify;
  const s = sums(cl.groups);
  const digital = s.receipt; const cash = s.cash;
  const p6 = Math.round((digital * b.rate.digital) / 100); const p8 = Math.round((cash * b.rate.cash) / 100);
  const g = d.regimes[d.regime];
  const rows = [['receipt', 'sum_receipt'], ['friend', 'sum_friend'], ['cash', 'sum_cash'], ['own', 'sum_own'], ['loan', 'sum_loan'], ['other', 'sum_other'], ['ask', 'sum_ask']]
    .filter(([c]) => s[c] || c === 'receipt')
    .map(([c, key]) => `<div class="bk-sum bk-sum-${c}"><span>${esc(k(key))}</span><b>${money(s[c])}</b></div>`).join('');
  const gst = b.gst;
  const gstNote = gst.over ? `<p class="small mr-warn bk-gst">${icon('alert', 12)} ${esc(k('gst_over', { turnover: money(digital + cash), limit: money(gst.limit), supply: k(`supply_${b.supply}`) }))}</p>`
    : gst.near ? `<p class="small bk-gst">${icon('info', 12)} ${esc(k('gst_near', { turnover: money(digital + cash), limit: money(gst.limit) }))}</p>` : '';
  const undecided = cl.groups.filter((x) => x.dir === 'cr' && x.class === 'ask');
  const fee = g.fee_234f + g.interest.total;
  return `<h3 class="rc-h">${icon('chart', 15)} ${esc(k('sum_h'))}</h3>
    <div class="bk-sums">${rows}</div>
    <p class="bk-line"><b>${digital || cash ? esc(k('line', { digital: money(digital), cash: money(cash), p6: money(p6), p8: money(p8), profit: money(p6 + p8), rd: b.rate.digital, rc: b.rate.cash })) : esc(k('line_none'))}</b></p>
    <p class="small muted">${esc(k('line_rule', { rd: b.rate.digital, rc: b.rate.cash }))}</p>
    ${undecided.length ? `<p class="small mr-warn">${icon('alert', 12)} ${esc(k('undecided', { n: undecided.length, amount: money(s.ask) }))}</p>` : ''}
    ${s.friend ? `<p class="small">${icon('info', 12)} ${esc(k('friend_note', { amount: money(s.friend) }))}</p>` : ''}
    ${cl.interest ? `<p class="small">${icon('check', 12)} ${esc(k('interest', { amount: money(cl.interest) }))}</p>` : ''}
    ${cl.salary ? `<p class="small mr-warn">${icon('alert', 12)} ${esc(k('salary', { amount: money(cl.salary) }))}</p>` : ''}
    ${gstNote}
    <div class="bk-res"><h4 class="small">${esc(k('res_h'))}</h4><dl class="mr-dl">
      <dt>${esc(k('res_income'))}</dt><dd>${money(g.tax.total)}</dd>
      <dt>${esc(k('res_tax'))}</dt><dd>${money(g.net_tax ?? g.tax.tax)}</dd>
      ${fee ? `<dt>${esc(k('res_fee'))}</dt><dd>${money(fee)}</dd>` : ''}
      <dt class="mr-tot">${esc(k(g.balance > 0 ? 'res_pay' : 'res_refund'))}</dt><dd class="mr-tot">${money(Math.abs(g.balance))}</dd></dl>
      ${d.late && fee ? `<p class="small muted">${esc(k('late', { due: String(d.dates.due).replace(/(\d{4})(\d\d)(\d\d)/, '$3-$2-$1'), fee: money(g.fee_234f), interest: money(g.interest.total) }))}</p>` : ''}</div>`;
};

const row = (g, b) => {
  const choices = g.dir === 'cr' ? b.choices.cr.filter((c) => c !== 'cash' || b.choices.cash_for.includes(g.kind)) : b.choices.dr;
  const word = (c) => k(`${g.dir === 'cr' ? 'c' : 'd'}_${c}`);
  const flags = (g.flags || []).map((f) => `<span class="tag bk-flag">${esc(k(`f_${f}`, { days: b.choices.days }))}</span>`).join('');
  return `<div class="bk-row cls-${esc(g.class)} ${g.chosen ? 'is-chosen' : ''}" data-key="${esc(g.key)}">
      <div class="bk-who"><b data-sens>${esc(g.name)}</b>
        <span class="small muted">${esc(k('n_payments', { n: g.count }))} · ${esc(k('dates', { first: g.first, last: g.last }))}</span>${flags}</div>
      <div class="bk-amt">${money(g.total)}</div>
      <div class="bk-choices" role="group" aria-label="${esc(g.name)}">${choices.map((c) => `<button type="button" class="bk-c bk-c-${c}" data-bk="${esc(g.key)}" data-cls="${c}"
        aria-pressed="${g.class === c}">${esc(word(c))}</button>`).join('')}
        ${g.class === 'ask' ? `<span class="tag warn bk-ask">${esc(k('c_ask'))}</span>` : ''}</div></div>`;
};

/** The step's markup. S.bk = { tab: 'cr' | 'dr', more: { cr, dr } } is the page's own view state. */
export function classifyCard(d, S) {
  const b = d.bank;
  S.bk = S.bk || { tab: 'cr', more: { cr: false, dr: false } };
  const docs = b.docs.map((x) => `<li class="${x.ok ? 'bk-ok' : 'bk-bad'}">${icon(x.ok ? 'check' : 'alert', 13)}
      <span>${x.ok ? esc(k('recon_ok', { opening: money(x.opening), credits: money(x.credits), debits: money(x.debits), closing: money(x.closing) }))
    : esc(k('recon_bad'))}</span><span class="small muted">${esc(k('stmt', { rows: x.rows, from: x.from, to: x.to, opening: money(x.opening), closing: money(x.closing) }))}</span></li>`).join('');
  const head = `<section class="card bk-head"><h3 class="rc-h">${icon('bank', 15)} ${esc(k('title'))}</h3><p class="small muted">${esc(k('lede'))}</p><ul class="bk-docs">${docs}</ul></section>`;
  if (!b.ok || !b.classify) return head;
  const cl = b.classify;
  const mine = cl.groups.filter((g) => g.dir === S.bk.tab);
  const n = S.bk.more[S.bk.tab] ? mine.length : Math.min(mine.length, Math.max(b.choices.show, mine.filter((g) => g.class === 'ask').length));
  const tabs = `<div class="bk-tabs" role="tablist">${[['cr', 'tab_in'], ['dr', 'tab_out']].map(([id, key]) => `<button type="button" role="tab" class="bk-tab ${S.bk.tab === id ? 'is-on' : ''}"
      aria-selected="${S.bk.tab === id}" data-tab="${id}">${esc(k(key))} <span class="tag">${cl.groups.filter((g) => g.dir === id).length}</span></button>`).join('')}</div>`;
  const list = `<section class="card bk-list"><h3 class="rc-h">${icon('list', 15)} ${esc(k('tap_h'))}</h3>${tabs}
    ${S.bk.tab === 'dr' ? `<p class="small muted">${esc(k('debit_note'))}</p>` : ''}
    <div class="bk-rows">${mine.slice(0, n).map((g) => row(g, b)).join('') || `<p class="muted small">${esc(k('none_out'))}</p>`}</div>
    ${mine.length > n ? `<button type="button" class="small ghost" id="bk-more">${esc(k('more', { n: mine.length - n }))}</button>`
    : n > b.choices.show ? `<button type="button" class="small ghost" id="bk-more">${esc(k('fewer'))}</button>` : ''}</section>`;
  // what is still needed: the business's code and the contact details no document gave
  const codes = (d.biz_codes || {})['44AD'] || [];
  const common = codes.filter(([c]) => b.common_codes.includes(c));
  const rest = codes.filter(([c]) => !b.common_codes.includes(c));
  const opt = ([c, l]) => `<option value="${esc(c)}" ${d.return.business.code === c ? 'selected' : ''}>${esc(c)} - ${esc(l)}</option>`;
  const text = (f) => `<div class="field"><label for="bk-${f}">${esc(k(`need_${f}`))}</label><input id="bk-${f}" data-qt="${f}" maxlength="80" autocomplete="off"
      ${f === 'mobile' ? 'inputmode="numeric"' : ''} value="${esc(d.answers[f] || '')}" data-sens/></div>`;
  const needs = ['mobile', 'email', 'father', 'address'].filter((f) => b.need.includes(f));
  const code = `<section class="card bk-need"><h3 class="rc-h">${icon('notebook', 15)} ${esc(k('need_h'))}</h3>
    <div class="grid two"><div class="field"><label for="bk-code">${esc(k('code_h'))}</label>
      <select id="bk-code"><option value="">${esc(k('code_pick'))}</option>
        <optgroup label="${esc(k('code_common'))}">${common.map(opt).join('')}</optgroup><optgroup label="${esc(k('code_all'))}">${rest.map(opt).join('')}</optgroup></select></div>
      ${needs.map(text).join('')}</div>
    ${b.need.length ? '' : `<p class="small mr-ok">${icon('check', 12)} ${esc(k('need_ok'))}</p>`}</section>`;
  return head + `<div class="bk-grid"><div class="bk-main">${list}</div><aside class="bk-side"><section class="card bk-summary" id="bk-summary">${summary(b, d)}</section></aside></div>${code}
    <div class="row tight mr-next"><span></span><button type="button" class="primary" data-next="check" data-flags='{"bank_confirmed":true}'>${esc(k('confirm'))} ${icon('right', 14)}</button></div>`;
}

/** Wire the step: tabs, show more, the taps (optimistic, then the server's answer), the business code. */
export function wireClassify(host, S, put, url, draw) {
  const b = () => S.d.bank;
  let chain = Promise.resolve();
  host.querySelectorAll('[data-tab]').forEach((x) => { x.onclick = () => { S.bk.tab = x.dataset.tab; draw(); }; });
  const more = host.querySelector('#bk-more');
  if (more) more.onclick = () => { S.bk.more[S.bk.tab] = !S.bk.more[S.bk.tab]; draw(); };
  host.querySelectorAll('[data-bk]').forEach((x) => {
    x.onclick = () => {
      const key = x.dataset.bk; const cls = x.dataset.cls;
      const g = b().classify.groups.find((y) => y.key === key);
      if (!g || g.class === cls) return;
      g.class = cls; g.chosen = true;                         // at once: the row and the totals
      const rowEl = host.querySelector(`.bk-row[data-key="${CSS.escape(key)}"]`);
      if (rowEl) {
        rowEl.className = `bk-row cls-${cls} is-chosen`;
        rowEl.querySelectorAll('[data-bk]').forEach((y) => y.setAttribute('aria-pressed', String(y.dataset.cls === cls)));
        const ask = rowEl.querySelector('.bk-ask'); if (ask) ask.remove();
      }
      const sum = host.querySelector('#bk-summary'); if (sum) sum.innerHTML = summary(b(), S.d);
      chain = chain.then(async () => {                        // the server's figures (the same ones the JSON will carry) replace the guess
        try {
          const r = await api(url(), { method: 'PUT', body: { bank_class: { [key]: cls } } });
          S.d = r;
          const s2 = host.querySelector('#bk-summary'); if (s2) s2.innerHTML = summary(b(), S.d);
        } catch (e) { toast(e.message, 'bad', 8); }
      });
    };
  });
  const code = host.querySelector('#bk-code');
  if (code) code.onchange = () => {
    const label = code.selectedOptions[0] ? code.selectedOptions[0].textContent.replace(/^\S+ - /, '') : '';
    const biz = S.d.return.business;
    put({ business: { kind: biz.kind || '44AD', code: code.value, name: biz.name || label } });
  };
}

/** s.139(1): whether the person must file at all (chip myreturn.must_file). Not required: plainly "not compulsory, but recommended" with the
 *  three things that would make it so (data-q, saved as answers); required for a reason beyond income: that reason, in words. */
export function mustFileCard(d) {
  const m = d.must_file; const w = (key, v) => t('myreturn', key, v);
  if (!m || !m.show) return '';
  const date = (n) => String(n).replace(/(\d{4})(\d\d)(\d\d)/, '$3-$2-$1');
  if (m.required) {
    return m.why === 'income' ? '' : `<section class="card mr-mf is-required"><h3 class="rc-h">${icon('alert', 15)} ${esc(w('mf_req_h'))}</h3>
      <p class="small">${esc(w('mf_req_p', { why: w(`mf_why_${m.why}`), due: date(d.dates.due) }))}</p></section>`;
  }
  const box = (q, key) => `<label class="check"><input type="checkbox" data-q="${q}" ${d.answers[q] ? 'checked' : ''}/> <span>${esc(w(key))}</span></label>`;
  return `<section class="card mr-mf"><h3 class="rc-h">${icon('info', 15)} ${esc(w('mf_h'))}</h3>
    <p class="small">${esc(w('mf_p', { income: money(m.income), limit: money(m.limit), belated: m.belated }))}</p>
    ${d.bank ? `<p class="small muted">${esc(w('mf_savings', { amount: money(m.savings) }))}</p>` : ''}
    <p class="small muted">${esc(w('mf_confirm'))}</p>
    <div class="mr-mf-q">${box('foreign_travel', 'mf_travel')}${box('electricity', 'mf_elec')}${box('current_deposits', 'mf_current')}</div></section>`;
}
