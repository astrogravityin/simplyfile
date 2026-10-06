// My return - #/myreturn[?c=<client>&ay=<year>]. An individual's own ITR-1 / ITR-2 as one journey of five steps:
// Gather (drop the pre-filled JSON, the AIS, each Form 16, 26AS - each is read and says what it found), Check (the same
// figure from two documents, side by side), Choose (both regimes worked out, the cheaper one marked), Review (every
// figure with where it came from, and the person's own over it), File (the department's JSON, checked against its schema).
// myreturn.py decides and adds up (chips myreturn.*); this draws. Pictures: myreturn-art.js. Words: chip ui.myreturn.
import { api, BASE, esc, toast, busy, pageHead, t, loadWords, dropZone, wireDrops } from './app.js';
import { icon } from './icons.js';
import { stepper, docArt, waterfall, regimeBars, tdsMap } from './myreturn-art.js';

const w = (k, v) => t('myreturn', k, v);
const money = (n) => `₹${Math.round(Number(n || 0)).toLocaleString('en-IN')}`;
const STEPS = ['gather', 'check', 'choose', 'review', 'file'];

export async function myReturnPage(host) {
  await loadWords('myreturn');
  const q = new URLSearchParams((location.hash.split('?')[1]) || '');
  const home = await api('/api/myreturn');
  let cid = q.get('c') || (home.self && home.clients[0] ? home.clients[0].id : '');
  const ay = q.get('ay') || home.current_ay;
  if (!cid) { pick(host, home, ay); return; }
  const S = { d: await api(`/api/myreturn/${encodeURIComponent(cid)}/${encodeURIComponent(ay)}`), step: '' };
  const url = (p = '') => `/api/myreturn/${encodeURIComponent(cid)}/${encodeURIComponent(ay)}${p}`;
  const put = async (body, quiet) => { try { S.d = await api(url(), { method: 'PUT', body }); if (!quiet) toast(w('saved'), 'ok'); draw(); } catch (e) { toast(e.message, 'bad', 8); } };

  const draw = () => {
    S.W = Math.round(Math.min(720, Math.max(300, (host.clientWidth || 720) - 40)));   // the pictures are drawn at the width they get, never shrunk
    const d = S.d;
    const step = S.step || d.step;
    const g = d.regimes[d.regime];
    const head = pageHead(w('title', { ay: d.ay }), esc(w('lede', { name: d.client.name })),
      `<span class="tag" style="--t:var(--brand)">${esc(d.form.form)}</span>`);
    const rail = `<div class="card mr-rail-card">${stepper(STEPS.map((s) => ({ id: s, label: w(`s_${s}`) })), step, d.steps.done, S.W)}</div>`;
    const glance = `<div class="mr-glance">${[
      ['income', w('g_income'), money(g.tax.total)],
      ['tax', w('g_tax'), money(g.tax.tax)],
      [g.balance > 0 ? 'pay' : 'refund', w(g.balance > 0 ? 'g_pay' : 'g_refund'), money(Math.abs(g.balance))],
      ['regime', w('g_regime'), w(`r_${d.regime}`)],
    ].map(([k, l, v]) => `<div class="mr-kpi k-${k}"><span>${esc(l)}</span><b>${esc(v)}</b></div>`).join('')}</div>`;
    host.innerHTML = head + rail + glance + `<div class="mr-panel">${({ gather, check, choose, review, file })[step](d, g)}</div>`;
    wire(step);
  };

  // --- 1 Gather --------------------------------------------------------------------------------------------------------
  const ready = (d) => {
    const L = d.checklist; const have = new Set(d.have); const mine = new Set(d.ready);
    const on = (r) => (r.kind && have.has(r.kind)) || mine.has(r.id);
    const n = L.rows.filter(on).length;
    return `<details class="card mr-ready" ${d.docs.length ? '' : 'open'}><summary><h3 class="rc-h">${icon('notebook', 15)} ${esc(w('ready_h'))}</h3>
        <span class="tag ${n === L.rows.length ? 'ok' : ''}">${esc(w('ready_n', { n, total: L.rows.length }))}</span></summary>
      <p class="small muted">${esc(w('ready_p'))}</p>
      <div class="mr-ready-grid">${Object.entries(L.groups).map(([g, gl]) => `<section><h4>${esc(gl)}</h4>${L.rows.filter((r) => r.group === g).map((r) => `<label class="check mr-ready-row ${on(r) ? 'is-on' : ''}">
        <input type="checkbox" data-ready="${esc(r.id)}" ${on(r) ? 'checked' : ''} ${r.kind && have.has(r.kind) ? 'disabled' : ''}/>
        <span><b>${esc(r.label)}</b><span class="small muted">${esc(r.why)}</span></span></label>`).join('')}</section>`).join('')}</div></details>`;
  };

  const gather = (d) => {
    const kinds = ['prefill', 'ais', 'form16', '26as', 'filed'];
    const cards = kinds.map((k) => {
      const docs = d.docs.filter((x) => x.kind === k);
      return `<article class="mr-dcard ${docs.length ? 'is-in' : ''}">${docArt(k, docs.length > 0)}
        <div class="mr-dbody"><h4>${esc(w(`k_${k}`))}</h4><p class="small muted">${esc(w(`k_${k}_why`))}</p>
          ${docs.map((x) => `<div class="mr-got"><span class="tag ok">${icon('check', 11)} ${esc(w(x.method === 'ai' ? 'read_ai' : 'read_ok'))}</span>
            <span class="small">${esc(x.name)}</span>
            <a class="small ghost button" href="${BASE}${url(`/docs/${x.id}/file`)}" aria-label="${esc(w('open'))}">${icon('eye', 12)}</a>
            <button type="button" class="small ghost" data-del="${esc(x.id)}" aria-label="${esc(w('remove'))}">${icon('trash', 12)}</button>
            ${(x.found || []).length ? `<ul class="mr-found">${x.found.map((f) => `<li>${esc(f.label)} <b>${esc(f.value)}</b></li>`).join('')}</ul>` : ''}
            ${(x.problems || []).map((p) => `<div class="small mr-warn">${icon('alert', 12)} ${esc(p)}</div>`).join('')}</div>`).join('')}
          <details class="mr-how"><summary class="small">${esc(w('how_get'))}</summary><ol class="small">${w(`k_${k}_how`, { ay: d.ay }).split('|').map((s) => `<li>${esc(s)}</li>`).join('')}</ol></details>
        </div></article>`;
    }).join('');
    return `${ready(d)}<section class="card"><h3 class="rc-h">${icon('upload', 15)} ${esc(w('gather_h'))}</h3><p class="small muted">${esc(w('gather_p'))}</p>
        ${dropZone('mr-file', { accept: '.pdf,.json,.csv,.txt,.xlsx,.zip', title: w('drop'), hint: w('drop_hint') })}
        <div class="grid two mr-opts"><div class="field"><label for="mr-pw">${esc(w('pw'))}</label><input id="mr-pw" type="password" autocomplete="off" placeholder="${esc(w('pw_ph'))}"/></div>
          <label class="check mr-ai"><input type="checkbox" id="mr-ai" ${d.answers.ai_ok ? 'checked' : ''}/> <span>${esc(w('ai_ok'))}</span></label></div>
        <div class="row tight" style="justify-content:flex-end"><button type="button" class="primary" id="mr-up">${icon('upload', 14)} ${esc(w('read'))}</button></div></section>
      <div class="mr-dgrid">${cards}</div>
      ${next('check')}`;
  };

  // --- 2 Check ---------------------------------------------------------------------------------------------------------
  const check = (d) => {
    const tds = d.checks.filter((c) => c.what === 'tds');
    const rows = tds.map((c) => ({ left: w('c_f16', { tan: c.tan }), right: w('c_credit', { tan: c.tan }), a: c.a, b: c.b, level: c.accepted ? 'ok' : c.level }));
    const others = d.checks.filter((c) => c.what !== 'tds');
    const list = d.checks.map((c) => `<div class="mr-chk lv-${esc(c.accepted ? 'ok' : c.level)}">
        <span class="mr-chk-dot">${icon(c.level === 'ok' || c.accepted ? 'check' : 'alert', 13)}</span>
        <div><b>${esc(w(`c_${c.what}`, { tan: c.tan || '' }))}</b><div class="small muted">${esc(w(`lv_${c.level}`, { a: money(c.a), b: money(c.b), gap: money(Math.abs(c.gap)) }))}</div></div>
        ${c.level !== 'ok' && !c.accepted ? `<button type="button" class="small" data-accept="${esc(c.key)}">${esc(w('accept'))}</button>` : ''}</div>`).join('');
    return `<section class="card"><h3 class="rc-h">${icon('check', 15)} ${esc(w('check_h'))}</h3><p class="small muted">${esc(w('check_p'))}</p>
        ${rows.length ? tdsMap(rows, { title: w('check_h'), left: w('c_left'), right: w('c_right') }, S.W) : ''}
        ${list || `<p class="muted">${esc(w('check_none'))}</p>`}
        ${others.length ? '' : ''}</section>${next('choose')}`;
  };

  // --- 3 Choose --------------------------------------------------------------------------------------------------------
  const choose = (d) => {
    const n = d.regimes.new; const o = d.regimes.old; const b = d.better;
    const flow = (r) => {
      const rows = [{ label: w('wf_gross'), value: r.salary.gross + Math.max(r.other, 0) + Math.max(r.hp.net, 0) + r.gti - r.gti_normal, kind: 'start' }];
      if (r.salary.exempt) rows.push({ label: w('wf_exempt'), value: r.salary.exempt, kind: 'minus' });
      if (r.salary.std + r.salary.prof_tax) rows.push({ label: w('wf_std'), value: r.salary.std + r.salary.prof_tax, kind: 'minus' });
      if (r.hp.net < 0) rows.push({ label: w('wf_hp'), value: -r.hp.net, kind: 'minus' });
      if (r.via.total) rows.push({ label: w('wf_via'), value: r.via.total, kind: 'minus' });
      rows.push({ label: w('wf_taxable'), value: r.tax.total, kind: 'total' });
      rows.push({ label: w('wf_tax'), value: r.tax.tax, kind: 'end' });
      return rows;
    };
    const side = (r, id) => `<article class="mr-reg ${d.regime === id ? 'is-on' : ''} ${b.better === id ? 'is-best' : ''}">
        <header><h4>${esc(w(`r_${id}`))}</h4>${b.better === id ? `<span class="tag ok">${esc(w('cheaper'))}</span>` : ''}</header>
        <dl class="mr-dl">${[['d_income', r.tax.total], ['d_via', r.via.total], ['d_tax', r.tax.on_normal + r.tax.on_special], ['d_rebate', -(r.tax.rebate + r.tax.relief_87a)],
          ['d_sur', r.tax.surcharge], ['d_cess', r.tax.cess], ['d_fee', r.fee_234f + r.interest.total]].filter(([, v]) => v).map(([k, v]) => `<dt>${esc(w(k))}</dt><dd>${esc(money(v))}</dd>`).join('')}
          <dt class="mr-tot">${esc(w('d_total'))}</dt><dd class="mr-tot">${esc(money(r.tax.tax + r.fee_234f + r.interest.total))}</dd></dl>
        ${id === 'old' && !d.old_ok ? `<p class="small mr-warn">${icon('lock', 12)} ${esc(w('old_closed_short'))}</p>`
          : `<button type="button" class="${d.regime === id ? 'primary' : ''}" data-regime="${id}">${esc(w(d.regime === id ? 'chosen' : 'choose_this'))}</button>`}</article>`;
    return `<section class="card"><h3 class="rc-h">${icon('money', 15)} ${esc(w('choose_h'))}</h3>
        <p class="mr-verdict">${esc(b.saving ? w('verdict', { regime: w(`r_${b.better}`), saving: money(b.saving) }) : w('verdict_same'))}</p>
        ${d.old_ok ? '' : `<p class="small muted">${icon('info', 12)} ${esc(w('old_closed'))}</p>`}
        ${regimeBars({ label: w('r_new'), tax: n.tax.tax + n.fee_234f + n.interest.total }, { label: w('r_old'), tax: o.tax.tax + o.fee_234f + o.interest.total }, b.better, { best: w('cheaper') }, S.W)}
        <div class="mr-regs">${side(n, 'new')}${side(o, 'old')}</div></section>
      <section class="card"><h3 class="rc-h">${icon('pulse', 15)} ${esc(w('flow_h', { regime: w(`r_${d.regime}`) }))}</h3>${waterfall(flow(d.regimes[d.regime]), S.W)}</section>
      ${next('review', { regime_seen: true })}`;
  };

  // --- 4 Review --------------------------------------------------------------------------------------------------------
  const src = (sec) => { const f = d0().return.from[sec]; return f ? `<span class="tag mr-src">${esc(w(`k_${f.kind}`))}</span>` : ''; };
  const d0 = () => S.d;
  const field = (sec, k, v, typed) => `<div class="field mr-f"><label for="e-${sec}-${k}">${esc(w(`f_${k}`))}${typed ? ` <span class="tag mr-you">${esc(w('you'))}</span>` : ''}</label>
      <input id="e-${sec}-${k}" inputmode="decimal" data-sec="${sec}" data-k="${k}" value="${v ? Math.round(v) : ''}" placeholder="0"/></div>`;
  const review = (d) => {
    const r = d.return;
    const emp = r.employers.map((e, i) => `<div class="mr-emp"><h4>${icon('users', 13)} ${esc(e.name || w('employer_n', { n: i + 1 }))} <span class="small muted">${esc(e.tan)}</span></h4>
        <div class="grid three">${['gross_17_1', 'perq_17_2', 'profit_17_3', 'exempt_all', 'exempt_new', 'prof_tax', 'basic_da', 'tds'].map((k) => `<div class="field mr-f"><label for="emp-${i}-${k}">${esc(w(`f_${k}`))}${(e.typed || []).includes(k) ? ` <span class="tag mr-you">${esc(w('you'))}</span>` : ''}</label>
          <input id="emp-${i}-${k}" inputmode="decimal" data-emp="${i}" data-k="${k}" value="${e[k] ? Math.round(e[k]) : ''}" placeholder="0"/></div>`).join('')}</div></div>`).join('');
    const houses = (r.houses || []).map((h, i) => `<div class="grid four mr-house" data-house="${i}">
        <div class="field"><label for="h-${i}-kind">${esc(w('f_kind'))}</label><select id="h-${i}-kind" data-h="kind"><option value="self" ${h.kind === 'self' ? 'selected' : ''}>${esc(w('h_self'))}</option><option value="let" ${h.kind === 'let' ? 'selected' : ''}>${esc(w('h_let'))}</option></select></div>
        ${['rent', 'municipal_tax', 'interest'].map((k) => `<div class="field"><label for="h-${i}-${k}">${esc(w(`f_${k}`))}</label><input id="h-${i}-${k}" inputmode="decimal" data-h="${k}" value="${h[k] ? Math.round(h[k]) : ''}" placeholder="0"/></div>`).join('')}</div>`).join('');
    const qs = ['resident', 'director', 'unlisted', 'foreign', 'parents_senior', 'metro'].map((k) => `<label class="check"><input type="checkbox" data-q="${k}" ${d.answers[k] ? 'checked' : ''}/> <span>${esc(w(`q_${k}`))}</span></label>`).join('');
    const who = `<div class="grid three mr-who"><div class="field"><label for="q-father">${esc(w('q_father'))}</label><input id="q-father" data-qt="father" value="${esc(d.answers.father || '')}" autocomplete="off"/></div>
      <div class="field"><label for="q-state">${esc(w('q_state'))}</label><select id="q-state" data-qt="state"><option value="">${esc(w('pick'))}</option>${w('states').split('|').map((x) => { const [c, n] = x.split('='); return `<option value="${esc(c)}" ${String(d.answers.state || d.return.person.state || '') === c ? 'selected' : ''}>${esc(n)}</option>`; }).join('')}</select></div>
      <div class="field"><label for="q-emp">${esc(w('q_employer_category'))}</label><select id="q-emp" data-qt="employer_category">${w('emp_cats').split('|').map((x) => { const [c, n] = x.split('='); return `<option value="${esc(c)}" ${(d.answers.employer_category || 'OTH') === c ? 'selected' : ''}>${esc(n)}</option>`; }).join('')}</select></div></div>`;
    return `<section class="card"><h3 class="rc-h">${icon('users', 15)} ${esc(w('rv_salary'))} ${src('employers')}</h3>${emp || `<p class="muted small">${esc(w('no_salary'))}</p>`}
        <button type="button" class="small ghost" id="mr-emp-add">${icon('plus', 12)} ${esc(w('add_employer'))}</button></section>
      <section class="card"><h3 class="rc-h">${icon('folder', 15)} ${esc(w('rv_house'))}</h3>${houses || `<p class="muted small">${esc(w('no_house'))}</p>`}
        <button type="button" class="small ghost" id="mr-house-add">${icon('plus', 12)} ${esc(w('add_house'))}</button></section>
      <section class="card"><h3 class="rc-h">${icon('money', 15)} ${esc(w('rv_other'))} ${src('other')}</h3>
        <div class="grid three">${['savings', 'deposits', 'dividend', 'family_pension', 'refund_interest', 'other'].map((k) => field('other', k, r.other[k], r.typed.other.includes(k))).join('')}</div></section>
      <section class="card"><h3 class="rc-h">${icon('pulse', 15)} ${esc(w('rv_cg'))} ${src('cg')}</h3><p class="small muted">${esc(w('rv_cg_p'))}</p>
        <div class="grid four">${['stcg_111a', 'ltcg_112a', 'ltcg_112', 'stcg_other'].map((k) => field('cg', k, r.cg[k], r.typed.cg.includes(k))).join('')}</div></section>
      <section class="card"><h3 class="rc-h">${icon('shield', 15)} ${esc(w('rv_via'))} ${src('via')}</h3><p class="small muted">${esc(w('rv_via_p'))}</p>
        <div class="grid three">${['c80c', 'c80ccc', 'c80ccd1', 'c80ccd1b', 'c80ccd2', 'c80d_self', 'c80d_parents', 'c80e', 'c80g'].map((k) => field('via', k, r.via[k], r.typed.via.includes(k))).join('')}</div></section>
      <section class="card"><h3 class="rc-h">${icon('info', 15)} ${esc(w('rv_q'))}</h3>${who}<div class="mr-qs">${qs}</div></section>
      ${next('file', { reviewed: true })}`;
  };

  // --- 5 File ----------------------------------------------------------------------------------------------------------
  const filedCard = (d) => `<section class="card"><h3 class="rc-h">${icon('clock', 15)} ${esc(w('filed_h'))}</h3><p class="small muted">${esc(w('filed_p'))}</p>
      <div class="grid three"><div class="field"><label for="mr-filed-on">${esc(w('filed_on'))}</label><input id="mr-filed-on" type="date" data-qt="filed_on" value="${esc(d.answers.filed_on || '')}" max="${new Date().toISOString().slice(0, 10)}"/></div>
        <div class="field"><label for="mr-ack">${esc(w('ack_no'))}</label><input id="mr-ack" inputmode="numeric" maxlength="15" data-qt="ack_no" value="${esc(d.answers.ack_no || '')}"/></div></div>
      ${d.has_filed ? '<div id="mr-cmp" class="small muted">…</div>' : `<p class="small muted">${esc(w('k_filed_why'))}</p>`}</section>`;
  const file = (d) => filedCard(d) + `<section class="card mr-file"><div class="mr-form">${docArt('prefill', true)}<div>
        <h3>${esc(w('file_h', { form: d.form.form }))}</h3><p>${esc(w(d.form.why))}</p>
        <div id="mr-schema" class="small muted">${esc(w('schema_wait'))}</div></div></div>
      <div class="row tight mr-acts"><button type="button" class="primary" id="mr-json">${icon('download', 14)} ${esc(w('download', { form: d.form.form }))}</button></div>
      <h4>${esc(w('upload_h'))}</h4><ol class="mr-up">${w('upload_steps').split('|').map((s) => `<li>${esc(s)}</li>`).join('')}</ol>
      <p class="small muted">${esc(w('file_note'))}</p></section>`;

  const next = (to, flags) => `<div class="row tight mr-next"><span></span><button type="button" class="primary" data-next="${to}" data-flags='${flags ? esc(JSON.stringify(flags)) : ''}'>${esc(w(`go_${to}`))} ${icon('right', 14)}</button></div>`;

  const wire = (step) => {
    const $ = (s) => host.querySelector(s);
    host.querySelectorAll('.mr-node').forEach((n) => { const go = () => { S.step = n.dataset.step; draw(); }; n.onclick = go; n.onkeydown = (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go(); } }; });
    host.querySelectorAll('[data-next]').forEach((b) => { b.onclick = (e) => busy(e.currentTarget, async () => {
      S.step = b.dataset.next; const f = b.dataset.flags ? JSON.parse(b.dataset.flags) : null;
      if (f) await put(f, true); else draw();
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }); });
    if (step === 'gather') {
      wireDrops(host);
      $('#mr-ai').onchange = (e) => put({ answers: { ai_ok: e.target.checked } }, true);
      $('#mr-up').onclick = (e) => busy(e.currentTarget, async () => {
        const f = $('#mr-file').files[0];
        if (!f) { toast(w('drop'), 'warn'); return; }
        const fd = new FormData(); fd.append('file', f); fd.append('password', $('#mr-pw').value);
        try { S.d = await api(url('/docs'), { method: 'POST', body: fd }); toast(w('read_done', { kind: w(`k_${S.d.added.kind}`) }), 'ok'); draw(); } catch (err) { toast(err.message, 'bad', 10); }
      });
      host.querySelectorAll('[data-del]').forEach((b) => { b.onclick = (e) => busy(e.currentTarget, async () => { try { S.d = await api(url(`/docs/${b.dataset.del}`), { method: 'DELETE' }); draw(); } catch (err) { toast(err.message, 'bad', 8); } }); });
    }
    host.querySelectorAll('[data-accept]').forEach((b) => { b.onclick = () => put({ accept: b.dataset.accept }); });
    host.querySelectorAll('[data-ready]').forEach((i) => { i.onchange = () => put({ ready: [...host.querySelectorAll('[data-ready]:checked:not(:disabled)')].map((x) => x.dataset.ready) }, true); });
    host.querySelectorAll('[data-regime]').forEach((b) => { b.onclick = () => put({ regime: b.dataset.regime, regime_seen: true }); });
    host.querySelectorAll('[data-sec]').forEach((i) => { i.onchange = () => put({ edits: { [i.dataset.sec]: { [i.dataset.k]: i.value } } }); });
    host.querySelectorAll('[data-emp]').forEach((i) => { i.onchange = () => put({ employers: { [i.dataset.emp]: { [i.dataset.k]: i.value } } }); });
    host.querySelectorAll('[data-q]').forEach((i) => { i.onchange = () => put({ answers: { [i.dataset.q]: i.checked } }); });
    host.querySelectorAll('[data-qt]').forEach((i) => { i.onchange = () => put({ answers: { [i.dataset.qt]: i.value } }); });
    const houses = () => [...host.querySelectorAll('[data-house]')].map((el) => Object.fromEntries([...el.querySelectorAll('[data-h]')].map((x) => [x.dataset.h, x.value])));
    host.querySelectorAll('[data-h]').forEach((i) => { i.onchange = () => put({ houses: houses() }); });
    if ($('#mr-house-add')) $('#mr-house-add').onclick = () => put({ houses: [...houses(), { kind: 'self' }] });
    if ($('#mr-emp-add')) $('#mr-emp-add').onclick = () => put({ employers: { [S.d.return.employers.length]: { name: w('employer_n', { n: S.d.return.employers.length + 1 }) } } });
    if (step === 'file') {
      $('#mr-json').onclick = () => { location.href = `${BASE}${url('/itr.json')}`; };
      if (S.d.has_filed) api(url('/compare')).then((c) => {
        const el = $('#mr-cmp'); if (!el) return;
        el.className = 'mr-cmp';
        el.innerHTML = `<h4>${esc(w('cmp_h'))}</h4><p class="small muted">${esc(w('cmp_p', { file: c.file, filed: c.form_filed, ours: c.form_ours }))} ${esc(w('cmp_regime', { regime: w(`r_${c.regime_filed}`) }))}</p>
          ${c.same ? `<p class="mr-ok">${icon('check', 13)} ${esc(w('cmp_same'))}</p>` : ''}
          <table class="mr-cmp-t"><thead><tr><th>${esc(w('cmp_fig'))}</th><th class="num">${esc(w('cmp_ours'))}</th><th class="num">${esc(w('cmp_theirs'))}</th><th class="num">${esc(w('cmp_gap'))}</th></tr></thead>
          <tbody>${c.rows.map((x) => `<tr class="lv-${esc(x.level)}"><td>${esc(w(x.word))}</td><td class="num">${money(x.ours)}</td>
            <td class="num">${x.theirs === null ? `<span class="muted small">${esc(w('cmp_missing'))}</span>` : money(x.theirs)}</td>
            <td class="num">${x.level === 'ok' ? icon('check', 12) : money(x.gap)}</td></tr>`).join('')}</tbody></table>`;
      }).catch((e) => toast(e.message, 'bad', 8));
      api(url('/itr-check')).then((r) => {
        const el = $('#mr-schema'); if (!el) return;
        el.className = `small ${r.valid ? 'mr-ok' : 'mr-warn'}`;
        el.innerHTML = r.valid ? `${icon('check', 12)} ${esc(w('schema_ok', { schema: r.schema }))}`
          : `${icon('alert', 12)} ${esc(w('schema_bad', { n: r.error_count }))}<ul>${r.errors.slice(0, 8).map((x) => `<li>${esc(x.field || x.path)}: ${esc(x.what)}</li>`).join('')}</ul>`;
      }).catch((e) => toast(e.message, 'bad', 8));
    }
  };
  draw();
}

function pick(host, home, ay) {
  host.innerHTML = pageHead(w('title', { ay }), esc(w('pick_lede')))
    + `<section class="card">${home.clients.length ? `<div class="mr-pick">${home.clients.filter((c) => ['individual', 'huf'].includes(c.status)).map((c) => `<a class="mr-pick-row" href="#/myreturn?c=${encodeURIComponent(c.id)}&ay=${encodeURIComponent(ay)}">
        ${icon('user', 16)}<span><b>${esc(c.name)}</b> <span class="small muted">${esc(c.pan)}</span></span>${icon('right', 14)}</a>`).join('')}</div>`
      : `<p class="muted">${esc(w('pick_none'))}</p>`}</section>`;
}
