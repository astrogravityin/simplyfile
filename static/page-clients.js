// Clients & years - SimplyFile (2026-10-03 client voice note: master data typed once, carried every year).
// The register is one list (list.clients) for the chosen assessment year; Open shows the master (name, PAN, status,
// banks, partners) and that year's card (form, 3CD audit, stage, preparer, acknowledgement). Every word is chip
// ui.clients; statuses, forms, years and stages are chip clients.settings.
import { api, esc, toast, busy, pageHead, confirmDialog, t, loadWords, listBox, modal, may } from './app.js';
import { icon } from './icons.js';

const w = (k, v) => t('clients', k, v);
let K = null;      // chip clients.settings
let AY = '';
let VIEW = '';     // '' = active clients, 'archived' = the Archived tab

const field = (id, label, value = '', attrs = '') => `<div class="field"><label for="${id}">${esc(label)}</label>
  <input id="${id}" value="${esc(value)}" ${attrs}/></div>`;
const grid = (html) => `<div class="grid two">${html}</div>`;   // the framework grid: labels line up (no stacked .field margin)
const stageOf = (id) => K.stages.find((s) => s.id === id) || { label: id, tag: 'tag' };

// Presentation only: a steady colour per name for the initials badge.
export const hue = (name) => [...String(name)].reduce((h, ch) => (h * 31 + ch.charCodeAt(0)) % 360, 7);
export const initials = (name) => String(name).split(/\s+/).filter(Boolean).slice(0, 2).map((x) => x[0]).join('').toUpperCase() || '?';

// Dots on a line: the stages done, the one the year is at, the ones to come (colours = chip clients.settings).
function stepper(stageId) {
  const i = K.stages.findIndex((s) => s.id === stageId), n = K.stages.length, gap = 14;
  const col = i >= 0 ? K.stages[i].color : '--line';
  const dots = K.stages.map((s, k) => `<circle cx="${5 + k * gap}" cy="6" r="${k === i ? 4.5 : 3.2}"
      fill="${k <= i ? `var(${col})` : 'var(--panel)'}" stroke="${k <= i ? `var(${col})` : 'var(--line-2)'}" stroke-width="1.5"/>`).join('');
  return `<svg class="cl-step" width="${10 + (n - 1) * gap}" height="12" viewBox="0 0 ${10 + (n - 1) * gap} 12" role="img"
      aria-label="${esc(w('stage_of', { i: i + 1, n }))}"><line x1="5" y1="6" x2="${5 + (n - 1) * gap}" y2="6" stroke="var(--line)" stroke-width="2"/>
      ${i > 0 ? `<line x1="5" y1="6" x2="${5 + i * gap}" y2="6" stroke="var(${col})" stroke-width="2"/>` : ''}${dots}</svg>`;
}

// The year's pipeline as one stacked bar, a segment per stage.
function pipeline(sum) {
  const total = Object.values(sum.stages).reduce((a, b) => a + b, 0);
  if (!total) return `<div class="small muted">${esc(w('k_none_year', { ay: AY }))}</div>`;
  let x = 0;
  const segs = K.stages.filter((s) => sum.stages[s.id]).map((s) => {
    const wd = (sum.stages[s.id] / total) * 100;
    const r = `<rect x="${x}%" y="0" width="${wd}%" height="10" fill="var(${s.color})"><title>${esc(s.label)}: ${sum.stages[s.id]}</title></rect>`;
    x += wd;
    return r;
  }).join('');
  return `<svg class="cl-pipe" width="100%" height="10" role="img" aria-label="${esc(w('k_pipeline', { ay: AY }))}">
      <defs><clipPath id="cl-pipe-r"><rect width="100%" height="10" rx="5"/></clipPath></defs><g clip-path="url(#cl-pipe-r)">${segs}</g></svg>
    <div class="cl-pipe-key">${K.stages.filter((s) => sum.stages[s.id]).map((s) =>
      `<span><i style="background:var(${s.color})"></i>${esc(s.label)} <b>${sum.stages[s.id]}</b></span>`).join('')}</div>`;
}

function kpis(sum) {
  const card = (ic, tone, label, big, sub) => `<div class="cl-kpi"><span class="cl-kpi-ic" style="--k:var(${tone})">${icon(ic, 18)}</span>
    <div><div class="cl-kpi-lbl">${esc(label)}</div><div class="cl-kpi-big">${big}</div><div class="cl-kpi-sub">${esc(sub)}</div></div></div>`;
  return card('users', '--brand', w('k_clients'), sum.active, w('k_archived', { n: sum.archived }))
    + card('clock', '--brand-2', w('k_in_year', { ay: AY }), sum.in_year, w('k_of', { n: sum.active }))
    + card('shield', '--warn', w('k_audit'), sum.audit, w('k_audit_sub'))
    + `<div class="cl-kpi cl-kpi-wide"><div class="cl-kpi-lbl">${esc(w('k_pipeline', { ay: AY }))}</div>${pipeline(sum)}</div>`;
}

export async function clientsPage(host) {
  await loadWords('clients');
  K = K || await api('/api/clients/settings');
  AY = AY || K.current_ay;
  host.innerHTML = pageHead(w('title'), esc(w('lede')),
    `<label class="cl-ay" for="cl-ay">${icon('clock', 14)}<span>${esc(w('ay'))}</span>
       <select id="cl-ay">${K.years.map((y) => `<option ${y === AY ? 'selected' : ''}>${esc(y)}</option>`).join('')}</select></label>
     <button type="button" class="primary" id="cl-new">${icon('plus', 15)} ${esc(w('new'))}</button>`)
    + '<section class="cl-kpis" id="cl-kpis" aria-live="polite"></section>'
    + `<section class="card cl-card"><div class="cl-bar"><div class="tabs cl-tabs" role="tablist">${[['', 'tab_active', 'active'], ['archived', 'tab_archived', 'archived']].map(([id, label, n]) =>
      `<button type="button" role="tab" data-view="${id}" data-n="${n}" class="${VIEW === id ? 'on' : ''}" aria-selected="${VIEW === id}">${esc(w(label))}<span class="cl-count"></span></button>`).join('')}</div></div>
      <div id="cl-list"></div></section>`;
  host.querySelectorAll('[data-view]').forEach((b) => { b.onclick = () => { VIEW = b.dataset.view; clientsPage(host); }; });
  const head = async () => {
    const sum = await api(`/api/clients/summary?ay=${encodeURIComponent(AY)}`);
    host.querySelector('#cl-kpis').innerHTML = kpis(sum);
    host.querySelectorAll('[data-n]').forEach((b) => { b.querySelector('.cl-count').textContent = sum[b.dataset.n]; });
  };
  const draw = () => { head(); return listBox(host.querySelector('#cl-list'), {
    list: 'clients',
    args: { ay: AY, view: VIEW },
    empty: w(VIEW ? 'empty_archived' : 'empty'),
    row: (r) => `<div class="cl-row" data-id="${esc(r.id)}">
      <span class="cl-av" style="--h:${hue(r.name)}" aria-hidden="true">${esc(initials(r.name))}</span>
      <div class="cl-main"><div class="cl-name">${esc(r.name)}
          ${r.archived_at ? `<span class="tag">${esc(w('archived_tag'))}</span>` : ''}
          ${r.audit ? `<span class="tag brand">${icon('shield', 11)} ${esc(w('audit_tag'))}</span>` : ''}</div>
        <div class="cl-meta"><code>${esc(r.pan)}</code><span>${esc(r.status)}</span><span>${esc(r.form)}</span></div></div>
      <div class="cl-stage">${r.in_year ? `${stepper(r.stage)}<span>${esc(stageOf(r.stage).label)}</span>`
        : `<span class="muted">${esc(w('not_in_year', { ay: AY }))}</span>`}</div>
      <div class="cl-acts">${may('intake') ? `<a class="small ghost button" href="#/intake?c=${esc(r.id)}&ay=${esc(AY)}">${icon('upload', 13)} ${esc(w('intake'))}</a>` : ''}
        <button type="button" class="small" data-open>${icon('edit', 13)} ${esc(w('edit'))}</button></div></div>`,
    wire: (rows, _r, load) => rows.querySelectorAll('[data-id]').forEach((el) => {
      el.querySelector('[data-open]').onclick = async () => editor(await api(`/api/clients/${el.dataset.id}`), () => { load(); head(); });
    }),
  }); };
  host.querySelector('#cl-ay').onchange = (e) => { AY = e.target.value; draw(); };
  host.querySelector('#cl-new').onclick = () => editor(null, draw);
  draw();
}

function rowsBox(kind, items, cols) {
  const one = (x = {}) => `<div class="row tight" data-${kind} style="align-items:end">${cols.map(([f, label]) =>
    `<div class="field" style="flex:1;min-width:110px;margin:0"><label>${esc(w(label))}</label><input data-f="${f}" value="${esc(x[f] || '')}"/></div>`).join('')}
    <button type="button" class="small ghost" data-rm aria-label="${esc(w('remove'))}">${icon('close', 12)}</button></div>`;
  return { html: items.map(one).join(''), one };
}

function editor(c, reload) {
  const isNew = !c;
  c = c || { status: K.statuses[0].id, banks: [{}], partners: [], years: {} };
  const banks = rowsBox('bank', c.banks.length ? c.banks : [{}],
    [['bank', 'b_bank'], ['branch', 'b_branch'], ['type', 'b_type'], ['account', 'b_account'], ['ifsc', 'b_ifsc']]);
  const partners = rowsBox('partner', c.partners, [['name', 'p_name'], ['pan', 'p_pan'], ['share', 'p_share']]);
  const y = (c.years || {})[AY];
  const yearCard = isNew ? '' : `<section class="card" style="margin-top:14px"><h3>${esc(w('year_card', { ay: AY }))}</h3>
    ${y ? grid(`<div class="field"><label for="y-form">${esc(w('y_form'))}</label><select id="y-form">${K.forms.map((f) => `<option ${f === y.form ? 'selected' : ''}>${esc(f)}</option>`).join('')}</select></div>
      <div class="field"><label>${esc(w('y_stage'))}</label><div class="cl-stage-ro">${stepper(y.stage)}<b>${esc(stageOf(y.stage).label)}</b></div>
        <div class="small muted">${esc(w('stage_auto'))}</div></div>
      ${field('y-assigned', w('y_assigned'), y.assigned)}
      <div class="field"><label>${esc(w('y_ack'))}</label><div class="cl-stage-ro">${y.ack_no ? `<code>${esc(y.ack_no)}</code>` : '<span class="muted">-</span>'}${y.revising ? ` <span class="tag warn">${esc(w('revising_tag'))}</span>` : ''}</div>
        <div class="small muted">${esc(w('ack_auto'))} ${may('compute') ? `<a href="#/compute?c=${esc(c.id)}&ay=${esc(AY)}">${esc(w('to_compute'))}</a>` : ''}</div></div>
      <label class="check" style="align-self:end;min-height:40px"><input type="checkbox" id="y-audit" ${y.audit ? 'checked' : ''}/> <span>${esc(w('y_audit'))}</span></label>
      <label class="check" style="align-self:end;min-height:40px"><input type="checkbox" id="y-tp" ${y.tp ? 'checked' : ''}/> <span>${esc(w('y_tp'))}</span></label>
      <label class="check" style="align-self:end;min-height:40px"><input type="checkbox" id="y-pres" ${y.presumptive ? 'checked' : ''}/> <span>${esc(w('y_presumptive'))}</span></label>`)
      + `<div class="row tight" style="margin-top:10px"><button type="button" id="y-save">${icon('save', 14)} ${esc(w('save_year'))}</button></div>`
      : `<button type="button" id="y-add">${icon('plus', 14)} ${esc(w('add_to_year', { ay: AY }))}</button>`}</section>`;
  const body = grid(field('c-name', w('f_name'), c.name, 'required') + field('c-relation', w('f_relation'), c.relation)
      + `<div class="field"><label for="c-status">${esc(w('f_status'))}</label><select id="c-status">${K.statuses.map((s) =>
        `<option value="${esc(s.id)}" ${s.id === c.status ? 'selected' : ''}>${esc(s.label)}</option>`).join('')}</select></div>`
      + field('c-pan', w('f_pan'), c.pan, 'maxlength="12" style="text-transform:uppercase"')
      + field('c-email', w('f_email'), c.email, 'type="email"') + field('c-phone', w('f_phone'), c.phone)
      + field('c-dob', w('f_dob'), c.dob, 'type="date"')
      + field('c-father', w('f_father'), c.father)
      + field('c-signer', w('f_signer_pan'), c.signer_pan, 'maxlength="10" style="text-transform:uppercase"')
      + `<label class="check" style="align-self:end;min-height:40px"><input type="checkbox" id="c-nri" ${c.nri ? 'checked' : ''}/> <span>${esc(w('f_nri'))}</span></label>`
      + field('c-gst', w('f_gst'), c.gst, 'maxlength="15" style="text-transform:uppercase"'))
    + `<div class="field"><label for="c-address">${esc(w('f_address'))}</label><textarea id="c-address" rows="2">${esc(c.address || '')}</textarea></div>
    <h3>${esc(w('banks'))}</h3><div id="c-banks">${banks.html}</div>
    <button type="button" class="small ghost" id="c-add-bank">${icon('plus', 12)} ${esc(w('add_bank'))}</button>
    <div id="c-partners-box"><h3>${esc(w('partners'))}</h3><div id="c-partners">${partners.html}</div>
    <button type="button" class="small ghost" id="c-add-partner">${icon('plus', 12)} ${esc(w('add_partner'))}</button></div>
    <div class="field" style="margin-top:14px"><label for="c-notes">${esc(w('f_notes'))}</label><textarea id="c-notes" rows="2">${esc(c.notes || '')}</textarea></div>
    ${yearCard}`;
  const footer = `${!isNew && may('clients', 'archive') ? (c.archived_at
      ? `<button type="button" data-restore>${icon('refresh', 14)} ${esc(w('restore'))}</button>`
      : `<button type="button" data-archive>${icon('archive', 14)} ${esc(w('archive'))}</button>`) : ''}
    <button type="button" class="primary" data-save>${icon('save', 15)} ${esc(w('save'))}</button>`;
  modal(isNew ? w('new') : c.name, body, { wide: true, footer, stay: true, onOpen: (b, close) => {
    const card = b.closest('.modal');
    const $ = (s) => card.querySelector(s);
    const wireRm = () => card.querySelectorAll('[data-rm]').forEach((x) => { x.onclick = () => x.parentElement.remove(); });
    const showPartners = () => {
      const st = K.statuses.find((s) => s.id === $('#c-status').value);
      $('#c-partners-box').style.display = st && st.has_partners ? '' : 'none';
    };
    $('#c-add-bank').onclick = () => { $('#c-banks').insertAdjacentHTML('beforeend', banks.one()); wireRm(); };
    $('#c-add-partner').onclick = () => { $('#c-partners').insertAdjacentHTML('beforeend', partners.one()); wireRm(); };
    $('#c-status').onchange = showPartners;
    wireRm(); showPartners();
    const read = (kind) => [...card.querySelectorAll(`[data-${kind}]`)].map((r) =>
      Object.fromEntries([...r.querySelectorAll('[data-f]')].map((i) => [i.dataset.f, i.value])));
    $('[data-save]').onclick = (e) => busy(e.currentTarget, async () => {
      const v = (id) => $(id).value;
      const data = { name: v('#c-name'), relation: v('#c-relation'), status: v('#c-status'), pan: v('#c-pan'),
        email: v('#c-email'), phone: v('#c-phone'), gst: v('#c-gst'), address: v('#c-address'), notes: v('#c-notes'), dob: v('#c-dob'), father: v('#c-father'), signer_pan: v('#c-signer'), nri: $('#c-nri').checked,
        banks: read('bank'), partners: read('partner'), ay: AY };
      try {
        await api(isNew ? '/api/clients' : `/api/clients/${c.id}`, { method: isNew ? 'POST' : 'PUT', body: data });
        toast(w('saved'), 'ok'); close(true); reload();
      } catch (err) { toast(err.message, 'bad', 8); }
    });
    const saveYear = (patch) => async (e) => busy(e.currentTarget, async () => {
      try {
        const fresh = await api(`/api/clients/${c.id}/years/${encodeURIComponent(AY)}`, { method: 'PUT', body: patch() });
        toast(w('saved'), 'ok'); close(true); reload(); editor(fresh, reload);
      } catch (err) { toast(err.message, 'bad', 8); }
    });
    if ($('#y-add')) $('#y-add').onclick = saveYear(() => ({}));
    if ($('#y-save')) $('#y-save').onclick = saveYear(() => ({ form: $('#y-form').value, audit: $('#y-audit').checked, tp: $('#y-tp').checked, presumptive: $('#y-pres').checked, assigned: $('#y-assigned').value }));
    const setArchived = (on) => async () => {
      try { await api(`/api/clients/${c.id}/archive`, { method: 'POST', body: { archived: on } }); toast(w(on ? 'archived' : 'restored'), 'ok'); close(true); reload(); }
      catch (err) { toast(err.message, 'bad', 8); }
    };
    const arch = card.querySelector('[data-archive]');
    if (arch) arch.onclick = () => confirmDialog(w('archive_title', { name: c.name }), w('archive_body', { name: c.name }), setArchived(true), w('archive'), { tone: 'warn' });
    const rest = card.querySelector('[data-restore]');
    if (rest) rest.onclick = (e) => busy(e.currentTarget, setArchived(false));
  } });
}
