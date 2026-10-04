// Compute & close - SimplyFile phases 4 + 5. #/compute?c=<client>&ay=<AY>: the computation of total income from the mapped
// books and the credit as 26AS shows it (every rate is chip compute.settings / compute.tax), the files for filing, the
// reviewer's sign-off, and Filed - which closes the year (chip close.move decides; the server refuses every later write).
// Words: chip ui.compute. The steps strip and the waterfall colours: chip page.compute.
import { api, BASE, esc, toast, busy, pageHead, confirmDialog, t, ps, loadWords, may, when } from './app.js';
import { clientPicker } from './page-intake.js';
import { hue, initials } from './page-clients.js';
import { icon } from './icons.js';

const w = (k, v) => t('compute', k, v);
const money = (n) => `₹${Math.round(Number(n || 0)).toLocaleString(ps('compute').money_locale)}`;
const signed = (n) => (n < 0 ? `(${money(-n)})` : money(n));

// The strip across the top: where this year is on the road to closed.
function steps(d) {
  const done = d.steps;                       // chip close.steps decides which steps are done; the page only draws
  const ids = ps('compute').step_states;
  const at = ids.findIndex((s) => !done[s]);
  return `<ol class="cc-steps">${ids.map((s, i) => `<li class="${done[s] ? 'is-done' : i === at ? 'is-now' : ''}">
    <svg width="26" height="26" viewBox="0 0 26 26" aria-hidden="true"><circle cx="13" cy="13" r="11" fill="${done[s] ? 'var(--ok)' : 'var(--panel)'}"
      stroke="${done[s] ? 'var(--ok)' : i === at ? 'var(--brand)' : 'var(--line-2)'}" stroke-width="2"/>
      ${done[s] ? '<path d="M8 13.5l3.2 3.2L18 9.8" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>'
        : `<text x="13" y="17.5" text-anchor="middle" class="cc-step-n">${i + 1}</text>`}</svg><span>${esc(w(s))}</span></li>`).join('')}</ol>`;
}

// The waterfall: tax, what is added and taken off, down to the balance - one scale, each bar starting where the last ended.
function waterfall(d) {
  const C = ps('compute').bar_color, x = d.tax;
  const items = [
    [w('wf_tax'), x.tax - x.rebate, C.tax, 'base'], [w('wf_surcharge', { rate: x.surcharge_rate }), x.surcharge, C.tax, 'step'],
    [w('wf_relief'), -x.relief, C.credit, 'step'], [w('wf_cess'), x.cess, C.tax, 'step'], [w('wf_total'), x.total, C.tax, 'total'],
    [w('wf_interest'), d.interest, C.tax, 'step'], [w('wf_tds'), -d.tds_total, C.credit, 'step'], [w('wf_paid'), -d.paid_total, C.credit, 'step'],
    [w(`wf_${d.balance.kind}`), d.balance.net, C[`balance_${d.balance.kind}`], 'total']].filter((r) => r[3] !== 'step' || Math.round(r[1]));
  let run = 0;
  const bars = items.map(([label, v, col, kind]) => {
    const from = kind === 'step' ? run : 0;
    run = kind === 'step' ? run + v : v;
    return { label, v, col, lo: Math.min(from, run), hi: Math.max(from, run), kind };
  });
  const top = Math.max(1, ...bars.map((b) => b.hi)), bottom = Math.min(0, ...bars.map((b) => b.lo));
  const W = 440, rowH = 30, L = 118, R = 100, scale = (W - L - R) / (top - bottom || 1), X = (v) => L + (v - bottom) * scale;
  return `<svg class="cc-wf" viewBox="0 0 ${W} ${bars.length * rowH + 10}" role="img" aria-label="${esc(w('waterfall'))}">
    <line x1="${X(0)}" y1="0" x2="${X(0)}" y2="${bars.length * rowH + 4}" stroke="var(--line-2)" stroke-dasharray="3 3"/>
    ${bars.map((b, i) => `<g transform="translate(0 ${i * rowH + 4})">
      <text x="${L - 10}" y="16" text-anchor="end" class="cc-wf-l ${b.kind === 'total' ? 'is-total' : ''}">${esc(b.label)}</text>
      <rect x="${X(b.lo)}" y="3" width="${Math.max(2, (b.hi - b.lo) * scale)}" height="18" rx="4" fill="var(${b.col})" opacity="${b.kind === 'total' ? 1 : 0.78}"/>
      <text x="${W - 4}" y="16" text-anchor="end" class="cc-wf-v ${b.kind === 'total' ? 'is-total' : ''}">${esc(signed(b.v))}</text></g>`).join('')}</svg>`;
}

const fileMark = (label, tone) => `<svg width="30" height="36" viewBox="0 0 34 40" aria-hidden="true">
  <path d="M4 2h18l10 10v24a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2Z" fill="var(--panel)" stroke="var(${tone})" stroke-width="1.6"/>
  <path d="M22 2v8a2 2 0 0 0 2 2h8" fill="none" stroke="var(${tone})" stroke-width="1.6"/>
  <rect x="5" y="24" width="24" height="10" rx="3" fill="var(${tone})"/><text x="17" y="31.6" text-anchor="middle" class="rc-doc-t">${esc(label)}</text></svg>`;

export async function computePage(host) {
  await loadWords('compute');
  const p = new URLSearchParams((location.hash.split('?')[1]) || '');
  if (!p.get('c')) return clientPicker(host, 'compute');
  const K = await api('/api/clients/settings');
  const cid = p.get('c');
  const ay = p.get('ay') || K.current_ay;
  const base = `/api/compute/${encodeURIComponent(cid)}/${encodeURIComponent(ay)}`;
  host.innerHTML = '<div class="loading"></div>';

  const draw = (d) => {
    const ro = d.locked;
    const x = d.tax;
    const line = (label, v, cls = '') => `<tr class="${cls}"><td>${esc(label)}</td><td class="num">${esc(signed(v))}</td></tr>`;
    host.innerHTML = pageHead(`${w('title')} · ${d.client.name}`, esc(w('lede')),
      `<label class="cl-ay" for="cc-ay">${icon('clock', 14)}<span>${esc(w('ay'))}</span>
         <select id="cc-ay">${K.years.map((y) => `<option ${y === ay ? 'selected' : ''}>${esc(y)}</option>`).join('')}</select></label>`)
      + `<section class="card cc-head">
          <div class="in-who"><span class="cl-av" style="--h:${hue(d.client.name)}" aria-hidden="true">${esc(initials(d.client.name))}</span>
            <div><div class="cl-name">${esc(d.client.name)} <span class="tag brand">${esc(d.client.form)}</span>${ro ? ` <span class="tag ok">${icon('lock', 11)} ${esc(w('s_close'))}</span>` : ''}</div>
              <div class="cl-meta"><code>${esc(d.client.pan)}</code><span>${esc(d.client.status)}</span></div></div></div>
          ${steps(d)}</section>`
      + [!d.has_books && w('no_books'), !d.has_26as && w('no_26as'), d.open_red && w('red_open', { n: d.open_red })].filter(Boolean)
        .map((m) => `<div class="cc-warn">${icon('alert', 15)} ${esc(m)}</div>`).join('')
      + `<div class="cc-grid">
        <section class="card cc-comp"><div class="cc-comp-top"><h3 class="rc-h">${icon('money', 15)} ${esc(w('x_title'))}</h3>
            <label class="cc-regime">${esc(w('regime'))}<select id="cc-regime" ${ro ? 'disabled' : ''}>${d.regimes.map((r) =>
              `<option value="${esc(r)}" ${r === d.regime ? 'selected' : ''}>${esc(w(`regime_${r}`))}</option>`).join('')}</select></label></div>
          <table class="cc-tbl"><colgroup><col><col class="cc-numcol"></colgroup><tbody>
          ${d.heads.map((h) => `<tr class="cc-h"><td colspan="2">${esc(w(`head_${h.id}`))}</td></tr>
            <tr><td colspan="2"><details class="cc-lines"><summary>${esc(w('from_books'))} · ${esc(w('lines', { n: h.lines.length }))}</summary>
              <table><colgroup><col><col class="cc-numcol-s"></colgroup>${h.lines.map((l) => `<tr><td>${esc(l.label)} <span class="muted small">${esc(l.key)}</span></td><td class="num">${esc(signed(l.amount))}</td></tr>`).join('')}</table></details></td></tr>
            ${'std' in h ? line(w('hp_nav'), h.gross, 'cc-sub') + line(w('hp_std'), -h.std, 'cc-sub') : ''}
            ${line(w('head_total'), h.net, 'cc-net')}`).join('')}
          ${line(w('gti'), d.gti, 'cc-key')}
          ${d.deductions ? line(w('deductions'), -d.deductions) : ''}
          ${line(w('total_income'), d.income, 'cc-big')}
          ${line(w('t_tax'), x.tax)}${x.rebate ? line(w('t_rebate'), -x.rebate) : ''}
          ${x.surcharge ? line(w('t_surcharge', { rate: x.surcharge_rate }), x.surcharge) : ''}${x.relief ? line(w('t_relief'), -x.relief) : ''}
          ${line(w('t_cess'), x.cess)}${line(w('t_total'), x.total, 'cc-key')}
          <tr><td>${esc(w('t_interest'))}<div class="small muted">${esc(w('interest_hint'))}</div></td>
            <td class="num"><input id="cc-int" type="number" min="0" step="1" value="${Math.round(d.interest)}" ${ro ? 'disabled' : ''} aria-label="${esc(w('interest'))}"/></td></tr>
          ${line(w('t_tds'), -d.tds_total)}${line(w('t_paid'), -d.paid_total)}
          <tr class="cc-bal is-${esc(d.balance.kind)}"><td>${esc(w(`bal_${d.balance.kind}`))}</td><td class="num">${esc(money(d.balance.amount))}</td></tr>
          </tbody></table></section>
        <div class="cc-side">
          <section class="card"><h3 class="rc-h">${icon('pulse', 15)} ${esc(w('waterfall'))}</h3>${waterfall(d)}</section>
          <section class="card"><h3 class="rc-h">${icon('download', 15)} ${esc(w('downloads'))}</h3><div class="cc-dl">
            <a class="cc-file" href="${BASE}${base}/computation.xlsx">${fileMark('XLSX', '--ok')}<span><b>${esc(w('dl_comp'))}</b></span></a>
            <a class="cc-file" href="${BASE}${base}/utility.zip">${fileMark('CSV', '--brand-2')}<span><b>${esc(w('dl_util'))}</b><small>${esc(w('dl_util_hint'))}</small></span></a>
            <a class="cc-file" href="${BASE}${base}/3cd.xlsx">${fileMark('3CD', '--warn')}<span><b>${esc(w('dl_3cd'))}</b></span></a></div></section>
          <section class="card cc-close"><h3 class="rc-h">${icon('shield', 15)} ${esc(w('steps'))}</h3>
            ${d.signoff ? `<div class="cc-sig ${d.signed ? 'is-ok' : 'is-stale'}">${icon(d.signed ? 'check' : 'alert', 14)}
                ${esc(d.signed ? w('signed_by', { by: d.signoff.by, at: when(d.signoff.at) }) : w('sign_stale'))}</div>` : ''}
            ${ro ? `<p class="small">${esc(w('closed_note'))}</p><div class="cc-ack"><span class="muted small">${esc(w('ack'))}</span><code>${esc(d.ack_no)}</code></div>
                ${may('compute', 'reopen') ? `<button type="button" id="cc-reopen">${icon('refresh', 14)} ${esc(w('reopen'))}</button>` : ''}`
              : `${may('compute', 'signoff') ? `<div class="row tight"><button type="button" class="${d.signed ? '' : 'primary'}" id="cc-sign">${icon('check', 14)} ${esc(w(d.signed ? 'unsign' : 'sign'))}</button></div>` : ''}
                ${may('compute', 'file') ? `<div class="field"><label for="cc-ack">${esc(w('ack'))}</label><input id="cc-ack" value="${esc(d.ack_no)}" placeholder="e.g. 123456789012345"/></div>
                <button type="button" class="primary" id="cc-file" ${d.signed ? '' : 'disabled'}>${icon('lock', 14)} ${esc(w('file'))}</button>` : ''}`}
          </section>
          <section class="card"><h3 class="rc-h">${icon('shield', 15)} ${esc(w('tds_title'))}</h3>
            <table class="cc-tbl small"><colgroup><col><col class="cc-numcol-s"></colgroup>${d.tds.map((e) => `<tr><td>${esc(e.party)}<div class="muted">${esc(e.tan)} · ${esc(e.section)} · ${esc(money(e.gross))}</div></td><td class="num">${esc(money(e.tax))}</td></tr>`).join('')}</table>
            <h3 class="rc-h" style="margin-top:14px">${icon('check', 15)} ${esc(w('paid_title'))}</h3>
            <table class="cc-tbl small"><colgroup><col><col class="cc-numcol-s"></colgroup>${d.paid.map((e) => `<tr><td>${esc(e.date)}<div class="muted">${esc(w('bsr'))} ${esc(e.bsr)} · ${esc(w('challan'))} ${esc(e.challan)}</div></td><td class="num">${esc(money(e.amount))}</td></tr>`).join('')}</table></section>
        </div></div>`;

    host.querySelector('#cc-ay').onchange = (e) => { location.hash = `#/compute?c=${encodeURIComponent(cid)}&ay=${encodeURIComponent(e.target.value)}`; };
    const put = async (body) => { try { draw(await api(base, { method: 'PUT', body })); toast(w('saved'), 'ok'); } catch (err) { toast(err.message, 'bad', 8); } };
    const reg = host.querySelector('#cc-regime');
    if (reg && !ro) reg.onchange = () => put({ regime: reg.value });
    const int = host.querySelector('#cc-int');
    if (int && !ro) int.onchange = () => put({ interest: int.value });
    const sign = host.querySelector('#cc-sign');
    if (sign) sign.onclick = () => (d.signed
      ? busy(sign, async () => { try { draw(await api(`${base}/signoff`, { method: 'POST', body: { on: false } })); } catch (err) { toast(err.message, 'bad', 8); } })
      : confirmDialog(w('sign_title'), w('sign_body', { income: money(d.income), tax: money(x.total), balance: `${w(`bal_${d.balance.kind}`)} ${money(d.balance.amount)}` }), async () => {
        try { draw(await api(`${base}/signoff`, { method: 'POST', body: { on: true } })); toast(w('saved'), 'ok'); } catch (err) { toast(err.message, 'bad', 8); }
      }, w('sign'), { tone: 'brand' }));
    const file = host.querySelector('#cc-file');
    if (file) file.onclick = () => confirmDialog(w('file_title'), w('file_body'), async () => {
      try { draw(await api(`${base}/file`, { method: 'POST', body: { ack_no: host.querySelector('#cc-ack').value } })); toast(w('filed_ok'), 'ok'); }
      catch (err) { toast(err.message, 'bad', 8); }
    }, w('file'), { tone: 'warn' });
    const reopen = host.querySelector('#cc-reopen');
    if (reopen) reopen.onclick = () => busy(reopen, async () => {
      try { draw(await api(`${base}/reopen`, { method: 'POST' })); toast(w('reopened'), 'ok'); } catch (err) { toast(err.message, 'bad', 8); }
    });
  };
  draw(await api(base));
}
