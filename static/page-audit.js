// Tax audit - #/audit?c=<client>&ay=<year>. Form 3CD worked through for one client-year (2026-10-04 owner: "phase 1, tax audit
// for SMEs"): is an audit needed, every mapped line this year against last, the 3CD clauses that apply, and the open points.
// The server decides everything (audit.py, chips audit.*); this page draws it. Words: ui.audit. Look: page.audit.
import { api, esc, toast, pageHead, t, ps, loadWords, when } from './app.js';
import { clientPicker } from './page-intake.js';
import { icon } from './icons.js';
import { historyButton, wireHistory } from './changes.js';

const w = (k, v) => t('audit', k, v);
const P = () => ps('audit');
const money = (n) => `${Number(n) < 0 ? '−' : ''}₹${Math.abs(Math.round(Number(n || 0))).toLocaleString(P().money_locale)}`;
const pill = (tone, text) => `<span class="sv-pill" style="--c:var(${tone})">${esc(text)}</span>`;

export async function auditPage(host) {
  await loadWords('audit', 'intake', 'changes');
  const p = new URLSearchParams((location.hash.split('?')[1]) || '');
  if (!p.get('c')) return clientPicker(host, 'audit');
  const K = await api('/api/clients/settings');
  const cid = p.get('c');
  const ay = p.get('ay') || K.current_ay;
  const base = `/api/audit/${encodeURIComponent(cid)}/${encodeURIComponent(ay)}`;
  host.innerHTML = pageHead(w('title'), esc(w('lede'))) + `<div class="loading">${esc(w('loading'))}</div>`;
  let d = await api(base);
  host.innerHTML = pageHead(`${w('title')} · ${d.client.name}`, esc(w('lede')),
    `${historyButton()}<button type="button" class="small ghost" id="au-back">${icon('left', 13)} ${esc(t('intake', 'change'))}</button>
     <label class="cl-ay" for="au-ay">${icon('clock', 14)}<span>${esc(w('ay'))}</span>
       <select id="au-ay">${K.years.map((y) => `<option ${y === ay ? 'selected' : ''}>${esc(y)}</option>`).join('')}</select></label>`)
    + `<section class="card an-card" id="au-need"></section>
       <section class="card an-card"><h3 class="rc-h" id="au-trend-h">${icon('pulse', 15)} ${esc(w('trend_title'))}</h3><p class="small muted">${esc(w('trend_sub'))}</p>
         <p class="small" id="au-src"></p>
         <div class="row tight au-bar"><input type="search" id="au-q" class="mp-find" placeholder="${esc(w('find_lines'))}"/>
           <label class="check small"><input type="checkbox" id="au-flagged" checked/> ${esc(w('only_flagged'))}</label></div>
         <div id="au-trend"></div></section>
       <section class="card an-card" id="au-gst-card"><h3 class="rc-h">${icon('money', 15)} ${esc(w('gst_title'))}</h3><p class="small muted">${esc(w('gst_sub'))}</p>
         <div class="au-up"><input type="file" id="au-gst-file" multiple hidden/><button type="button" class="small" id="au-gst-pick">${icon('upload', 13)} ${esc(w('gst_upload'))}</button></div>
         <div id="au-gst"></div></section>
       <section class="card an-card"><h3 class="rc-h">${icon('check', 15)} ${esc(w('check_title'))} <span class="small muted" id="au-done"></span></h3>
         <p class="small muted">${esc(w('check_sub'))}</p>
         <label class="small au-sector">${esc(w('sector'))} <select id="au-sector"></select></label><div id="au-checks"></div></section>
       <section class="card an-card" id="au-stat-card"><h3 class="rc-h">${icon('book', 15)} ${esc(w('stat_title'))} <span class="small muted" id="au-as-done"></span></h3>
         <p class="small muted">${esc(w('stat_sub'))}</p><div id="au-stat"></div></section>
       <section class="card an-card"><h3 class="rc-h">${icon('flag', 15)} ${esc(w('points_title'))}</h3><p class="small muted">${esc(w('points_sub'))}</p>
         <div class="au-new"><input id="au-pt" maxlength="300" placeholder="${esc(w('point_title_ph'))}"/>
           <select id="au-owner"><option value="">${esc(w('nobody'))}</option>${d.people.map((m) => `<option value="${esc(m.id)}">${esc(m.name)}</option>`).join('')}</select>
           <button type="button" class="primary small" id="au-add">${icon('plus', 13)} ${esc(w('point_new'))}</button></div>
         <div id="au-points"></div></section>`;
  wireHistory(host, { cid, ay, name: d.client.name });
  host.querySelector('#au-back').onclick = () => { location.hash = '#/audit'; };   // back to the client list
  host.querySelector('#au-ay').onchange = (e) => { location.hash = `#/audit?c=${encodeURIComponent(cid)}&ay=${encodeURIComponent(e.target.value)}`; };
  const send = async (path, method, body) => {
    try { d = await api(`${base}${path}`, { method, body }); toast(w('saved'), 'ok'); draw(); } catch (e) { toast(e.message, 'bad', 8); }
  };
  const nameOf = (id) => (d.people.find((m) => m.id === id) || {}).name || '';
  const lineName = (r) => `${(P().items || {})[r.item] || r.item}`;

  const need = () => {
    const a = d.applicable;
    host.querySelector('#au-need').innerHTML = `<h3 class="rc-h">${icon(P().need_icon[a.need], 15)} ${esc(w('need_title'))}</h3>
      <div class="au-verdict">${pill(P().need_tone[a.need], w(`need_${a.need}`))}
        <span class="small">${esc(w(a.why, { turnover: money(a.turnover), limit: money(a.limit) }))}</span></div>
      <div class="au-facts">${Object.keys(d.facts).map((f) => `<label class="check small"><input type="checkbox" data-fact="${esc(f)}" ${d.facts[f] ? 'checked' : ''}/> ${esc(w(`fact_${f}`))}</label>`).join('')}</div>
      ${a.need === 'yes' && !d.marked ? `<button type="button" class="small" id="au-mark">${icon('shield', 13)} ${esc(w('mark_audit'))}</button>`
        : d.marked ? `<p class="small muted">${icon('check', 12)} ${esc(w('marked'))}</p>` : ''}`;
    host.querySelectorAll('[data-fact]').forEach((c) => { c.onchange = () => send('/facts', 'PUT', { [c.dataset.fact]: c.checked }); });
    const mk = host.querySelector('#au-mark');
    if (mk) mk.onclick = async () => { await api(`/api/clients/${encodeURIComponent(cid)}/years/${encodeURIComponent(ay)}`, { method: 'PUT', body: { audit: true } }); send('', 'GET'); };
  };

  const trend = () => {
    const tr = d.trend;
    // phase 2: with two or more earlier years, each gets its own column and every line is also checked against its own history
    const ays = tr.history_ays || [], many = ays.length > 1;
    host.querySelector('#au-trend-h').innerHTML = `${icon('pulse', 15)} ${esc(w(many ? 'trend_title_years' : 'trend_title'))}`;
    const pills = (r) => [r.flag, r.pattern].filter(Boolean).map((f) => pill(P().flag_tone[f], w(`flag_${f}`))).join(' ');
    host.querySelector('#au-src').innerHTML = `${esc(w(`src_${tr.source}`, { ay: tr.prev_ay }))} · ${esc(w('turnover'))} <b>${money(tr.revenue)}</b>
      ${tr.revenue_before ? ` · ${esc(w('turnover_change'))} <b>${tr.revenue_pct > 0 ? '+' : ''}${tr.revenue_pct}%</b>` : ''}
      ${many ? `<br>${esc(w('src_years', { n: ays.length, from: ays[0], to: ays[ays.length - 1] }))}` : ''}`;
    // every word typed must be in the line's name, table or item; "only flagged" hides the quiet lines
    const words = host.querySelector('#au-q').value.toLowerCase().split(/\s+/).filter(Boolean);
    const flagged = host.querySelector('#au-flagged').checked;
    const rows = tr.rows.filter((r) => (!flagged || r.flag || r.pattern) && words.every((x) => `${lineName(r)} ${r.item} ${w(`t_${r.table}`)}`.toLowerCase().includes(x)));
    host.querySelector('#au-trend').innerHTML = !tr.rows.length ? `<p class="small muted">${esc(w('no_lines'))}</p>`
      : `<div class="an-scroll"><table class="cc-tbl an-tbl"><thead><tr><th>${esc(w('h_line'))}</th>${many ? ays.map((y) => `<th class="num">${esc(y)}</th>`).join('') : `<th class="num">${esc(w('h_before'))}</th>`}
          <th class="num">${esc(w('h_now'))}</th><th class="num">${esc(w('h_change'))}</th>${many ? `<th class="num" title="${esc(w('h_avg_tip'))}">${esc(w('h_avg'))}</th>` : ''}<th class="num">${esc(w('h_share'))}</th><th>${esc(w('h_flag'))}</th><th></th></tr></thead><tbody>
        ${rows.map((r) => `<tr><td>${esc(lineName(r))} <span class="small muted">${esc(w(`t_${r.table}`))}</span></td>
          ${many ? r.history.map((v) => `<td class="num">${v ? money(v) : '-'}</td>`).join('') : `<td class="num">${tr.before_known ? money(r.before) : '-'}</td>`}<td class="num">${money(r.now)}</td>
          <td class="num">${r.before ? `${r.pct > 0 ? '+' : ''}${r.pct}%` : '-'}</td>${many ? `<td class="num">${r.avg ? `${r.vs_avg > 0 ? '+' : ''}${r.vs_avg}%` : '-'}</td>` : ''}<td class="num">${P().share_tables.includes(r.table) ? `${r.share}%` : '-'}</td>
          <td><span class="au-pills">${pills(r)}</span></td>
          <td>${r.flag || r.pattern ? `<button type="button" class="small ghost" data-raise="${esc(r.id)}">${icon('flag', 12)} ${esc(w('raise'))}</button>` : ''}</td></tr>`).join('')}
        </tbody></table></div>`;
    host.querySelectorAll('[data-raise]').forEach((b) => {
      const r = tr.rows.find((x) => x.id === b.dataset.raise);
      // the year-on-year flag first; a line only its history flags is raised against its average
      b.onclick = () => send('/points', 'POST', r.flag ? { source: d.trend_source, ref: `trend:${r.id}`,
        title: w('point_from_trend', { line: lineName(r), before: money(r.before), now: money(r.now), flag: w(`flag_${r.flag}`) }) }
        : { source: d.pattern_source, ref: `pattern:${r.id}`,
          title: w('point_from_pattern', { line: lineName(r), now: money(r.now), avg: money(r.avg), n: ays.length, flag: w(`flag_${r.pattern}`) }) });
    });
  };

  // GST returns against the books: the year's verdicts first, then month by month, then the files added
  const gst = () => {
    const g = d.gst;
    host.querySelector('#au-gst-file').accept = d.gst_exts.join(',');
    if (!g.files.length) { host.querySelector('#au-gst').innerHTML = `<p class="small muted">${esc(w('gst_none'))}</p>`; return; }
    const mon = (pd) => `${P().gst_months[(Number(pd.slice(0, 2)) + 8) % 12]} ${pd.slice(2)}`;
    const verdict = (key, gap) => (key && key !== 'match' ? `<div class="au-verdict">${pill(P().gst_tone[key], w(`gst_${key}`))}
        <span class="small">${money(Math.abs(gap))}</span>
        <button type="button" class="small ghost" data-gst-raise="${esc(key)}" data-gap="${Math.abs(gap)}">${icon('flag', 12)} ${esc(w('raise'))}</button></div>`
      : key ? `<div class="au-verdict">${pill(P().gst_tone[key], w(`gst_${key}`))}</div>` : '');
    host.querySelector('#au-gst').innerHTML = `<p class="small">${esc(w('gst_books'))} <b>${money(g.books)}</b> · ${esc(w('gst_kind_gstr3b'))} <b>${money(g.r3b)}</b>
        ${g.missing_3b ? `<span class="muted">(${esc(w(g.missing_3b === 1 ? 'gst_missing_one' : 'gst_missing', { n: g.missing_3b }))})</span>` : ''} · ${esc(w('gst_kind_gstr1'))} <b>${money(g.r1)}</b>
        ${g.missing_1 ? `<span class="muted">(${esc(w(g.missing_1 === 1 ? 'gst_missing_one' : 'gst_missing', { n: g.missing_1 }))})</span>` : ''}</p>
      ${verdict(g.books_3b, g.gap_books_3b)}${verdict(g.r3b_1, g.gap_3b_1)}
      <div class="an-scroll"><table class="cc-tbl an-tbl"><thead><tr><th>${esc(w('gst_h_month'))}</th><th class="num">${esc(w('gst_h_3b'))}</th>
        <th class="num">${esc(w('gst_h_r1'))}</th><th class="num">${esc(w('gst_h_diff'))}</th><th></th></tr></thead><tbody>
      ${g.months.map((m) => `<tr><td>${esc(mon(m.period))}</td><td class="num">${m.has_3b ? money(m.r3b) : '-'}</td><td class="num">${m.has_1 ? money(m.r1) : '-'}</td>
        <td class="num">${m.has_3b && m.has_1 ? money(m.r3b - m.r1) : '-'}</td><td>${m.state === 'none' ? '' : pill(P().gst_tone[m.state], w(`gst_${m.state}`))}</td></tr>`).join('')}
      <tr class="au-total"><td><b>${esc(w('gst_total'))}</b></td><td class="num"><b>${money(g.r3b)}</b></td><td class="num"><b>${money(g.r1)}</b></td>
        <td class="num"><b>${money(g.r3b - g.r1)}</b></td><td></td></tr></tbody></table></div>
      <details class="small"><summary>${esc(w('gst_files_title'))} (${g.files.length})</summary><div class="au-files">${g.files.map((f) => `<span class="au-file">
        ${esc(w(`gst_kind_${f.kind}`))} ${esc(mon(f.period))} · ${esc(f.gstin)} <button type="button" class="small ghost" data-gst-del="${esc(f.id)}" title="${esc(w('gst_remove'))}">${icon('close', 11)}</button></span>`).join('')}</div></details>`;
    host.querySelectorAll('[data-gst-del]').forEach((b) => { b.onclick = () => send(`/gst/${encodeURIComponent(b.dataset.gstDel)}`, 'DELETE'); });
    host.querySelectorAll('[data-gst-raise]').forEach((b) => {
      b.onclick = () => send('/points', 'POST', { source: d.gst_source, ref: `gst:${b.dataset.gstRaise}`,
        title: w('point_from_gst', { what: w(`gst_${b.dataset.gstRaise}`), gap: money(b.dataset.gap) }) });
    });
  };

  // statutory audit for a non-company entity: the LLP audit (LLPs only), the ICAI level, and the standards at that level
  const stat = () => {
    const st = d.stat;
    const on = st.standards.filter((r) => r.applies !== 'no'), off = st.standards.filter((r) => r.applies === 'no');
    const done = on.filter((r) => d.done_states.includes(r.state)).length;
    host.querySelector('#au-as-done').textContent = `· ${w('as_done', { done, n: on.length })}`;
    const row = (r) => `<div class="au-check" data-as="${esc(r.id)}" style="--c:var(${P().state_tone[r.state]})">
        <span class="au-clause">${esc(r.std)}${pill(P().as_tone[r.applies], w(`as_${r.applies}`))}</span>
        <div class="au-main"><b>${esc(r.title)}</b>${r.hint ? `<div class="small muted">${esc(r.hint)}</div>` : ''}
          <input class="au-note" data-note value="${esc(r.note || '')}" placeholder="${esc(w('note_ph'))}" maxlength="1000"/></div>
        <select data-state aria-label="${esc(r.title)}">${d.states.map((x) => `<option value="${x}" ${x === r.state ? 'selected' : ''}>${esc(w(`st_${x}`))}</option>`).join('')}</select></div>`;
    host.querySelector('#au-stat').innerHTML = `${st.llp.need !== 'na' ? `<h4 class="au-sub">${esc(w('llp_title'))}</h4>
        <div class="au-verdict">${pill(P().llp_tone[st.llp.need], w(`llp_${st.llp.need}`))}<span class="small">${esc(w(st.llp.why, {
          turnover: money(st.llp.turnover), contribution: money(st.llp.contribution),
          limit: money(st.llp.why === 'llp_why_contribution' ? st.llp.contribution_limit : st.llp.turnover_limit) }))}</span></div>` : ''}
      <h4 class="au-sub">${esc(w('level_title'))}</h4>
      <div class="au-verdict">${pill('--brand', w(`level_${st.level}`))}<span class="small">${esc(w('level_why', { turnover: money(d.trend.revenue), borrowings: money(st.borrowings) }))}</span></div>
      <div class="au-facts">${Object.keys(st.facts).map((f) => `<label class="check small"><input type="checkbox" data-sfact="${esc(f)}" ${st.facts[f] ? 'checked' : ''}/> ${esc(w(`fact_${f}`))}</label>`).join('')}</div>
      <p class="small muted">${icon('info', 12)} ${esc(w('as_confirm'))}</p>
      <div class="au-list">${on.map(row).join('')}</div>
      ${off.length ? `<details class="small au-off"><summary>${esc(w('as_not_here', { n: off.length }))}</summary>
        <ul>${off.map((r) => `<li>${esc(r.std)} - ${esc(r.title)}</li>`).join('')}</ul></details>` : ''}`;
    host.querySelectorAll('[data-sfact]').forEach((c) => { c.onchange = () => send('/facts', 'PUT', { [c.dataset.sfact]: c.checked }); });
    host.querySelectorAll('[data-as]').forEach((el) => {
      const save = () => send(`/standards/${encodeURIComponent(el.dataset.as)}`, 'PUT', { state: el.querySelector('[data-state]').value, note: el.querySelector('[data-note]').value });
      el.querySelector('[data-state]').onchange = save;
      el.querySelector('[data-note]').onchange = save;
    });
  };

  const checks = () => {
    const n = d.checklist.length, done = d.checklist.filter((c) => d.done_states.includes(c.state)).length;
    host.querySelector('#au-done').textContent = `· ${w('checks_done', { done, n })}`;
    const sel = host.querySelector('#au-sector');
    sel.innerHTML = [['', w('sector_none')], ...d.sectors.map((s) => [s, w(`sector_${s}`)])].map(([v, l]) => `<option value="${esc(v)}" ${v === d.sector ? 'selected' : ''}>${esc(l)}</option>`).join('');
    sel.onchange = () => send('/facts', 'PUT', { sector: sel.value });
    // why a clause sits where it does: the flagged lines it watches, the line of business, a large client
    const why = (c) => [c.flagged_lines.length ? w('why_flagged', { lines: c.flagged_lines.map((i) => (P().items || {})[i] || i).join(', ') }) : '',
      c.sector_hit ? w('why_sector', { sector: w(`sector_${d.sector}`).toLowerCase() }) : '', c.big ? w('why_big') : ''].filter(Boolean).join(' · ');
    host.querySelector('#au-checks').innerHTML = `<div class="au-list">${d.checklist.map((c) => `<div class="au-check" data-check="${esc(c.id)}" style="--c:var(${P().state_tone[c.state]})">
        <span class="au-clause">3CD ${esc(c.clause)}<span title="${esc(w('risk_tip'))}">${pill(P().risk_tone[c.level], w(`risk_${c.level}`))}</span></span>
        <div class="au-main"><b>${esc(c.title)}</b>${c.hint ? `<div class="small muted">${esc(c.hint)}</div>` : ''}${why(c) ? `<div class="small au-why">${icon('alert', 11)} ${esc(why(c))}</div>` : ''}
          <input class="au-note" data-note value="${esc(c.note || '')}" placeholder="${esc(w('note_ph'))}" maxlength="1000"/></div>
        <select data-state aria-label="${esc(c.title)}">${d.states.map((s) => `<option value="${s}" ${s === c.state ? 'selected' : ''}>${esc(w(`st_${s}`))}</option>`).join('')}</select></div>`).join('')}</div>`;
    host.querySelectorAll('[data-check]').forEach((el) => {
      const save = () => send(`/checks/${encodeURIComponent(el.dataset.check)}`, 'PUT', { state: el.querySelector('[data-state]').value, note: el.querySelector('[data-note]').value });
      el.querySelector('[data-state]').onchange = save;
      el.querySelector('[data-note]').onchange = save;
    });
  };

  const points = () => {
    const order = P().point_order;
    const list = [...d.points].sort((a, b) => order.indexOf(a.status) - order.indexOf(b.status));
    host.querySelector('#au-points').innerHTML = !list.length ? `<p class="small muted">${esc(w('points_none'))}</p>`
      : `<div class="au-list">${list.map((x) => `<div class="au-point ${order.indexOf(x.status) > 0 ? 'is-done' : ''}" data-point="${esc(x.id)}">
          <div class="au-main"><b>${esc(x.title)}</b><div class="small muted">${esc(w(`from_${x.source}`))} · ${esc(x.by)} · ${esc(when(x.at))}</div>
            <input class="au-note" data-pnote value="${esc(x.note || '')}" placeholder="${esc(w('note_ph'))}" maxlength="1000"/></div>
          <select data-powner aria-label="${esc(w('point_owner'))}"><option value="">${esc(w('nobody'))}</option>${d.people.map((m) => `<option value="${esc(m.id)}" ${m.id === x.owner ? 'selected' : ''}>${esc(m.name)}</option>`).join('')}</select>
          ${pill(P().point_tone[x.status], w(`pt_${x.status}`))}
          ${d.may_clear ? `<button type="button" class="small ghost" data-flip>${esc(w(P().point_button[x.status]))}</button>` : ''}</div>`).join('')}</div>`;
    host.querySelectorAll('[data-point]').forEach((el) => {
      const id = encodeURIComponent(el.dataset.point);
      const x = d.points.find((y) => y.id === el.dataset.point);
      el.querySelector('[data-pnote]').onchange = (e) => send(`/points/${id}`, 'PUT', { note: e.target.value });
      el.querySelector('[data-powner]').onchange = (e) => send(`/points/${id}`, 'PUT', { owner: e.target.value });
      const f = el.querySelector('[data-flip]');
      if (f) f.onclick = () => send(`/points/${id}/status`, 'PUT', { status: P().point_next[x.status] });
    });
  };

  const draw = () => { need(); trend(); gst(); checks(); stat(); points(); };
  host.querySelector('#au-gst-pick').onclick = () => host.querySelector('#au-gst-file').click();
  host.querySelector('#au-gst-file').onchange = async (e) => {
    const fd = new FormData();
    [...e.target.files].forEach((f) => fd.append('files', f));
    e.target.value = '';
    try { d = await api(`${base}/gst`, { method: 'POST', body: fd }); toast(w('gst_added', { n: d.added }), 'ok'); draw(); } catch (err) { toast(err.message, 'bad', 10); }
  };
  host.querySelector('#au-flagged').checked = d.trend.before_known;   // nothing to compare: show every line
  host.querySelector('#au-q').oninput = trend;
  host.querySelector('#au-flagged').onchange = trend;
  host.querySelector('#au-add').onclick = () => {
    const title = host.querySelector('#au-pt').value.trim();
    if (!title) return;
    send('/points', 'POST', { title, owner: host.querySelector('#au-owner').value, source: 'hand' });
    host.querySelector('#au-pt').value = '';
  };
  draw();
}
