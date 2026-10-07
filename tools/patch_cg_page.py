"""2026-10-07 wave 3: My return's page - each sale (typed or read from a statement), losses brought forward, gifts, and a house's
pre-construction interest. A one-time patch of static/page-myreturn.js (it looks first and leaves a page already patched alone).
Run from D:/Simplyfile:  .venv/Scripts/python.exe tools/patch_cg_page.py"""
from pathlib import Path

P = Path(__file__).resolve().parent.parent / "static" / "page-myreturn.js"
s = P.read_text(encoding="utf-8")
if "function cgCard(" in s:
    print("already patched")
    raise SystemExit(0)

REPS = [
    ("""        <div class="field"><label for="h-${i}-co_pan">${esc(w('f_co_pan'))}</label><input id="h-${i}-co_pan" data-h="co_pan" maxlength="10" style="text-transform:uppercase" value="${esc(((h.co_owners || [])[0] || {}).pan || '')}" autocomplete="off"/></div></div>""",
     """        <div class="field"><label for="h-${i}-co_pan">${esc(w('f_co_pan'))}</label><input id="h-${i}-co_pan" data-h="co_pan" maxlength="10" style="text-transform:uppercase" value="${esc(((h.co_owners || [])[0] || {}).pan || '')}" autocomplete="off"/></div>
        <div class="field"><label for="h-${i}-pre_total">${esc(w('f_pre_total'))}</label><input id="h-${i}-pre_total" inputmode="decimal" data-h="pre_total" value="${h.pre_total ? Math.round(h.pre_total) : ''}" placeholder="0"/></div>
        <div class="field"><label for="h-${i}-completed">${esc(w('f_completed'))}</label><input id="h-${i}-completed" type="date" data-h="completed" value="${esc(h.completed || '')}"/></div></div>"""),
    ("""      <section class="card"><h3 class="rc-h">${icon('pulse', 15)} ${esc(w('rv_cg'))} ${src('cg')}</h3><p class="small muted">${esc(w('rv_cg_p'))}</p>
        <div class="grid four">${['stcg_111a', 'ltcg_112a', 'ltcg_112', 'stcg_other'].map((k) => field('cg', k, r.cg[k], r.typed.cg.includes(k))).join('')}</div></section>""",
     """      ${cgCard(r, d, field)}${lossCard(r, d)}${giftCard(r, d)}"""),
    ("""    if ($('#mr-vda-add')) $('#mr-vda-add').onclick = () => put({ vda: [...vdas(), {}] });""",
     """    if ($('#mr-vda-add')) $('#mr-vda-add').onclick = () => put({ vda: [...vdas(), {}] });
    // 2026-10-07: each sale typed (statement rows are read, not typed), losses brought forward, gifts
    const rowsOf = (sel, key) => [...host.querySelectorAll(`[${sel}]`)].map((el) => Object.fromEntries([...el.querySelectorAll(`[${key}]`)].map((x) => [x.getAttribute(key), x.value])));
    const cgs = () => rowsOf('data-cg', 'data-c');
    host.querySelectorAll('[data-c]').forEach((i) => { i.onchange = () => put({ cg_rows: cgs() }); });
    if ($('#mr-cg-add')) $('#mr-cg-add').onclick = () => put({ cg_rows: [...cgs(), { asset: 'equity' }] });
    host.querySelectorAll('[data-cg-del]').forEach((b) => { b.onclick = () => put({ cg_rows: cgs().filter((_, n) => n !== Number(b.dataset.cgDel)) }); });
    const losses = () => rowsOf('data-loss', 'data-l');
    host.querySelectorAll('[data-l]').forEach((i) => { i.onchange = () => put({ losses_bf: losses() }); });
    if ($('#mr-loss-add')) $('#mr-loss-add').onclick = () => put({ losses_bf: [...losses(), { kind: 'stcl' }] });
    if ($('#mr-loss-prev')) $('#mr-loss-prev').onclick = () => put({ losses_from_prev: true });
    const gifts = () => rowsOf('data-gift', 'data-gf');
    host.querySelectorAll('[data-gf]').forEach((i) => { i.onchange = () => put({ gifts: gifts() }); });
    if ($('#mr-gift-add')) $('#mr-gift-add').onclick = () => put({ gifts: [...gifts(), { kind: 'money' }] });"""),
    ("""    const kinds = ['prefill', 'ais', 'form16', '26as', 'filed'].concat(['bank', 'other'].filter((k2) => d.docs.some((x) => x.kind === k2)));""",
     """    const kinds = ['prefill', 'ais', 'form16', '26as', 'filed', 'cg', 'filed_prev'].concat(['bank', 'other'].filter((k2) => d.docs.some((x) => x.kind === k2)));"""),
]
for a, b in REPS:
    assert s.count(a) == 1, a[:70]
    s = s.replace(a, b)

s += """
// --- Capital gains (2026-10-07, wave 3): each sale - typed, or read from a broker / CAMS / KFintech statement - its exemption,
// the property's choice (12.5% without indexation or 20% with it), and the year after every set-off ----------------------------
function cgCard(r, d, field) {
  const cw = r.cgw || { rows: [], final: {}, cf: {}, bf_used: {} };
  const typed = (r.cg_rows || []).filter((x) => !x.doc);
  const read = (cw.rows || []).filter((x) => x.doc);
  const assets = w('cg_assets').split('|').map((a) => a.split('='));
  const sel = (i, k, opts, v) => `<div class="field"><label for="cg-${i}-${k}">${esc(w(`f_cg_${k}`))}</label><select id="cg-${i}-${k}" data-c="${k}">${opts.map(([o, l]) => `<option value="${esc(o)}" ${String(v || '') === o ? 'selected' : ''}>${esc(l)}</option>`).join('')}</select></div>`;
  const inp = (i, k, x, ty = 'num', max = 60) => `<div class="field"><label for="cg-${i}-${k}">${esc(w(`f_cg_${k}`))}</label><input id="cg-${i}-${k}" data-c="${k}" ${ty === 'num' ? 'inputmode="decimal" placeholder="0"' : `type="${ty === 'date' ? 'date' : 'text'}" maxlength="${max}"`} value="${esc(ty === 'num' ? (x[k] ? Math.round(x[k] * 100) / 100 : '') : (x[k] || ''))}" autocomplete="off"/></div>`;
  const res = (c) => {
    if (!c) return '<span></span>';
    const out = [`<b>${esc(w(`b_${c.bucket}`))}</b> - ${esc(w('cg_gain', { gain: money(c.final) }))}`];
    if (c.deemed_50aa) out.push(esc(w('cg_res_50aa')));
    if (c.grandfathered) out.push(esc(w('cg_res_gf', { cost: money(c.cost_used) })));
    if (c.s50c) out.push(esc(w('cg_res_50c', { value: money(c.consideration) })));
    if (c.exempt) out.push(esc(w('cg_res_ex', { amount: money(c.exempt), kind: c.ex_kind })));
    if (c.ex_why) out.push(`<span class="mr-warn">${esc(w(c.ex_why))}</span>`);
    if (c.index_ok) out.push(esc(w('cg_res_choice', { plain: money(c.tax_plain), indexed: money(c.tax_indexed), chosen: w(`cg_chosen_${c.chosen}`) })));
    return `<p class="small">${out.join(' · ')}</p>`;
  };
  const exKinds = [['', w('ex_none')], ['54', w('ex_54')], ['54EC', w('ex_54EC')], ['54F', w('ex_54F')]];
  const rows = typed.map((x, i) => {
    const c = (cw.rows || [])[i];
    const prop = ['land', 'house'].includes(x.asset);
    return `<div class="mr-cg" data-cg="${i}"><div class="grid four">
      ${sel(i, 'asset', assets, x.asset)}${inp(i, 'name', x, 'text', 125)}${x.asset === 'equity' ? inp(i, 'isin', x, 'text', 12) : ''}${prop ? '' : inp(i, 'units', x)}
      ${inp(i, 'acquired', x, 'date')}${inp(i, 'sold', x, 'date')}${x.acquired && x.sold ? '' : sel(i, 'term', [['', w('cg_term_auto')], ['long', w('cg_term_long')], ['short', w('cg_term_short')]], x.term)}
      ${inp(i, 'sale', x)}${inp(i, 'cost', x)}${inp(i, 'expenses', x)}${x.asset === 'equity' ? inp(i, 'fmv', x) : ''}
      ${prop ? inp(i, 'stamp', x) + inp(i, 'improve', x) + inp(i, 'improve_on', x, 'date') + inp(i, 'buyer', x, 'text', 125) + inp(i, 'buyer_pan', x, 'text', 10) + inp(i, 'address', x, 'text', 200) + inp(i, 'pin', x, 'text', 6) + inp(i, 'tds', x) : ''}
      ${sel(i, 'ex_kind', exKinds, x.ex_kind)}
      ${x.ex_kind ? inp(i, 'ex_amount', x) + inp(i, 'ex_on', x, 'date') : ''}${x.ex_kind && x.ex_kind !== '54EC' ? inp(i, 'cgas', x) + inp(i, 'cgas_on', x, 'date') + inp(i, 'cgas_acc', x, 'text', 20) + inp(i, 'cgas_ifsc', x, 'text', 11) : ''}
      ${x.ex_kind === '54F' ? inp(i, 'other_houses', x) : ''}</div>
      <div class="row tight">${res(c)}<button type="button" class="small ghost" data-cg-del="${i}" aria-label="${esc(w('cg_remove'))}">${icon('trash', 12)}</button></div></div>`;
  }).join('');
  const readList = read.length ? `<h4 class="small">${esc(w('cg_read_h', { n: read.length }))}</h4><table class="mr-cmp-t"><thead><tr><th>${esc(w('f_cg_name'))}</th><th>${esc(w('f_cg_sold'))}</th><th class="num">${esc(w('f_cg_sale'))}</th><th>${esc(w('cg_bucket'))}</th><th class="num">${esc(w('cg_gain_h'))}</th></tr></thead>
    <tbody>${read.slice(0, 200).map((c) => `<tr><td>${esc(c.name || c.isin || '-')}</td><td>${esc(c.sold || '')}</td><td class="num">${money(c.sale)}</td><td class="small">${esc(w(`b_${c.bucket}`))}</td><td class="num">${money(c.final)}</td></tr>`).join('')}</tbody></table>` : '';
  const f = cw.final || {};
  const after = cw.any ? `<h4 class="small">${esc(w('cg_sum_h'))}</h4><p class="small">${['stcg_111a', 'stcg_app', 'ltcg_112', 'ltcg_112a'].filter((b) => f[b]).map((b) => `${esc(w(`b_${b}`))} <b>${money(f[b])}</b>`).join(' · ') || esc(w('cg_sum_nil'))}</p>
    ${cw.excess ? `<p class="small">${esc(w('cg_excess', { amount: money(cw.excess) }))}</p>` : ''}
    ${cw.cf && (cw.cf.stcl || cw.cf.ltcl) ? `<p class="small ${cw.cf_ok === false ? 'mr-warn' : ''}">${esc(w(cw.cf_ok === false ? 'cg_cf_late' : 'cg_cf', { stcl: money(cw.cf.stcl), ltcl: money(cw.cf.ltcl) }))}</p>` : ''}` : '';
  return `<section class="card"><h3 class="rc-h">${icon('pulse', 15)} ${esc(w('rv_cg'))}</h3><p class="small muted">${esc(w('rv_cg_p2'))}</p>
    ${readList}<h4 class="small">${esc(w('cg_rows_h'))}</h4>${rows || `<p class="muted small">${esc(w('cg_none'))}</p>`}
    <button type="button" class="small ghost" id="mr-cg-add">${icon('plus', 12)} ${esc(w('cg_add'))}</button>
    ${after}
    <details class="mr-more" ${['stcg_111a', 'ltcg_112a', 'ltcg_112', 'stcg_other'].some((k) => r.cg[k]) ? 'open' : ''}><summary>${esc(w('cg_totals_h'))}</summary>
      <div class="grid four">${['stcg_111a', 'ltcg_112a', 'ltcg_112', 'stcg_other'].map((k) => field('cg', k, r.cg[k], r.typed.cg.includes(k))).join('')}</div></details></section>`;
}

function lossCard(r, d) {
  const cw = r.cgw || { life: [] };
  const y = Number(String(d.ay).slice(0, 4));
  const ays = Array.from({ length: 8 }, (_, n) => `${y - n - 1}-${String((y - n) % 100).padStart(2, '0')}`);
  const life = cw.life || [];
  const rows = (r.losses_bf || []).map((x, i) => {
    const lf = life[i] || {};
    return `<div class="grid four mr-loss" data-loss="${i}">
      <div class="field"><label for="ls-${i}-ay">${esc(w('f_loss_ay'))}</label><select id="ls-${i}-ay" data-l="ay">${[x.ay && !ays.includes(x.ay) ? x.ay : null, ...ays].filter(Boolean).map((a) => `<option value="${a}" ${x.ay === a ? 'selected' : ''}>${a}</option>`).join('')}</select></div>
      <div class="field"><label for="ls-${i}-kind">${esc(w('f_loss_kind'))}</label><select id="ls-${i}-kind" data-l="kind">${['stcl', 'ltcl', 'hp'].map((k) => `<option value="${k}" ${x.kind === k ? 'selected' : ''}>${esc(w(`loss_${k}`))}</option>`).join('')}</select></div>
      <div class="field"><label for="ls-${i}-amount">${esc(w('f_loss_amount'))}</label><input id="ls-${i}-amount" inputmode="decimal" data-l="amount" value="${x.amount ? Math.round(x.amount) : ''}" placeholder="0"/></div>
      <div class="field"><label for="ls-${i}-filed_on">${esc(w('f_loss_filed_on'))}</label><input id="ls-${i}-filed_on" type="date" data-l="filed_on" value="${esc(x.filed_on || '')}"/></div>
      ${lf.usable === false ? `<p class="small mr-warn">${icon('alert', 12)} ${esc(w('loss_gone', { ay: x.ay }))}</p>` : ''}</div>`;
  }).join('');
  const used = Object.values(cw.bf_used || {}).reduce((a, b) => a + b, 0) + ((d.regimes[d.regime].hp || {}).bf || 0);
  const prev = d.docs.some((x) => x.kind === 'filed_prev');
  return `<section class="card"><h3 class="rc-h">${icon('clock', 15)} ${esc(w('loss_h'))}</h3><p class="small muted">${esc(w('loss_p'))}</p>
    ${rows || `<p class="muted small">${esc(w('loss_none'))}</p>`}${used ? `<p class="small"><b>${esc(w('loss_used', { amount: money(used) }))}</b></p>` : ''}
    <div class="row tight"><button type="button" class="small ghost" id="mr-loss-add">${icon('plus', 12)} ${esc(w('loss_add'))}</button>
    ${prev ? `<button type="button" class="small ghost" id="mr-loss-prev">${icon('refresh', 12)} ${esc(w('loss_prev'))}</button>` : `<span class="small muted">${esc(w('loss_prev_how'))}</span>`}</div></section>`;
}

function giftCard(r, d) {
  const g = d.regimes[d.regime].gifts || { total: 0 };
  const pairs = (key) => w(key).split('|').map((x) => x.split('='));
  const opt = (v, list) => list.map(([o, l]) => `<option value="${esc(o)}" ${String(v || '') === o ? 'selected' : ''}>${esc(l)}</option>`).join('');
  const sel = (i, k, x, key) => `<div class="field"><label for="gf-${i}-${k}">${esc(w(`f_gift_${k}`))}</label><select id="gf-${i}-${k}" data-gf="${k}">${opt(x[k], pairs(key))}</select></div>`;
  const num = (i, k, x) => `<div class="field"><label for="gf-${i}-${k}">${esc(w(`f_gift_${k}`))}</label><input id="gf-${i}-${k}" inputmode="decimal" data-gf="${k}" value="${x[k] ? Math.round(x[k]) : ''}" placeholder="0"/></div>`;
  const rows = (r.gifts || []).map((x, i) => `<div class="grid four mr-gift" data-gift="${i}">
      <div class="field"><label for="gf-${i}-from">${esc(w('f_gift_from'))}</label><input id="gf-${i}-from" data-gf="from" maxlength="80" value="${esc(x.from || '')}" autocomplete="off"/></div>
      ${sel(i, 'relation', x, 'gift_relations')}${sel(i, 'occasion', x, 'gift_occasions')}${sel(i, 'kind', x, 'gift_kinds')}${num(i, 'value', x)}${num(i, 'paid', x)}
      <div class="field"><label for="gf-${i}-on">${esc(w('f_gift_on'))}</label><input id="gf-${i}-on" type="date" data-gf="on" value="${esc(x.on || '')}"/></div></div>`).join('');
  return `<section class="card"><h3 class="rc-h">${icon('money', 15)} ${esc(w('gift_h'))}</h3><p class="small muted">${esc(w('gift_p'))}</p>
    ${rows || `<p class="muted small">${esc(w('gift_none'))}</p>`}${(r.gifts || []).length ? `<p class="small"><b>${esc(w('gift_total', { amount: money(g.total) }))}</b></p>` : ''}
    <button type="button" class="small ghost" id="mr-gift-add">${icon('plus', 12)} ${esc(w('gift_add'))}</button></section>`;
}
"""
P.write_text(s, encoding="utf-8")
print("patched", P)
