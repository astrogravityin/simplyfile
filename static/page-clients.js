// Clients & years - SimplyFile (2026-10-03 client voice note: master data typed once, carried every year).
// The register is one list (list.clients) for the chosen assessment year; Open shows the master (name, PAN, status,
// banks, partners) and that year's card (form, 3CD audit, stage, preparer, acknowledgement). Every word is chip
// ui.clients; statuses, forms, years and stages are chip clients.settings.
import { api, esc, toast, busy, pageHead, confirmDialog, t, loadWords, listBox, modal, may } from './app.js';
import { icon } from './icons.js';

const w = (k, v) => t('clients', k, v);
let K = null;      // chip clients.settings
let AY = '';

const field = (id, label, value = '', attrs = '') => `<div class="field"><label for="${id}">${esc(label)}</label>
  <input id="${id}" value="${esc(value)}" ${attrs}/></div>`;
const grid = (html) => `<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px 14px">${html}</div>`;
const stageOf = (id) => K.stages.find((s) => s.id === id) || { label: id, tag: 'tag' };

export async function clientsPage(host) {
  await loadWords('clients');
  K = K || await api('/api/clients/settings');
  AY = AY || K.current_ay;
  host.innerHTML = pageHead(w('title'), esc(w('lede')),
    `<label class="small muted" for="cl-ay">${esc(w('ay'))}</label>
     <select id="cl-ay">${K.years.map((y) => `<option ${y === AY ? 'selected' : ''}>${esc(y)}</option>`).join('')}</select>
     <button type="button" id="cl-new">${icon('plus', 14)} ${esc(w('new'))}</button>`)
    + '<section class="card" id="cl-list"></section>';
  const draw = () => listBox(host.querySelector('#cl-list'), {
    list: 'clients',
    args: { ay: AY },
    empty: w('empty'),
    row: (r) => `<div class="kw-row small" data-id="${esc(r.id)}">
      <div class="kw-info"><b>${esc(r.name)}</b> <span class="muted">${esc(r.pan)} · ${esc(r.status)} · ${esc(r.form)}</span>
        ${r.audit ? `<span class="tag brand">${esc(w('audit_tag'))}</span>` : ''}
        ${r.in_year ? `<span class="${esc(stageOf(r.stage).tag)}">${esc(stageOf(r.stage).label)}</span>`
          : `<span class="muted">${esc(w('not_in_year', { ay: AY }))}</span>`}</div>
      <div class="row tight">${may('intake') ? `<a class="small ghost button" href="#/intake?c=${esc(r.id)}&ay=${esc(AY)}">${icon('upload', 12)} ${esc(w('intake'))}</a>` : ''}
        <button type="button" class="small ghost" data-open>${icon('edit', 12)} ${esc(w('edit'))}</button></div></div>`,
    wire: (rows, _r, load) => rows.querySelectorAll('[data-id]').forEach((el) => {
      el.querySelector('[data-open]').onclick = async () => editor(await api(`/api/clients/${el.dataset.id}`), load);
    }),
  });
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
      <div class="field"><label for="y-stage">${esc(w('y_stage'))}</label><select id="y-stage">${K.stages.map((s) => `<option value="${esc(s.id)}" ${s.id === y.stage ? 'selected' : ''}>${esc(s.label)}</option>`).join('')}</select></div>
      ${field('y-assigned', w('y_assigned'), y.assigned)}${field('y-ack', w('y_ack'), y.ack_no)}
      <label class="check"><input type="checkbox" id="y-audit" ${y.audit ? 'checked' : ''}/> <span>${esc(w('y_audit'))}</span></label>`)
      + `<div class="row tight" style="margin-top:10px"><button type="button" id="y-save">${icon('save', 14)} ${esc(w('save_year'))}</button></div>`
      : `<button type="button" id="y-add">${icon('plus', 14)} ${esc(w('add_to_year', { ay: AY }))}</button>`}</section>`;
  const body = grid(field('c-name', w('f_name'), c.name, 'required') + field('c-relation', w('f_relation'), c.relation)
      + `<div class="field"><label for="c-status">${esc(w('f_status'))}</label><select id="c-status">${K.statuses.map((s) =>
        `<option value="${esc(s.id)}" ${s.id === c.status ? 'selected' : ''}>${esc(s.label)}</option>`).join('')}</select></div>`
      + field('c-pan', w('f_pan'), c.pan, 'maxlength="12" style="text-transform:uppercase"')
      + field('c-email', w('f_email'), c.email, 'type="email"') + field('c-phone', w('f_phone'), c.phone)
      + field('c-gst', w('f_gst'), c.gst, 'maxlength="15" style="text-transform:uppercase"'))
    + `<div class="field"><label for="c-address">${esc(w('f_address'))}</label><textarea id="c-address" rows="2">${esc(c.address || '')}</textarea></div>
    <h3>${esc(w('banks'))}</h3><div id="c-banks">${banks.html}</div>
    <button type="button" class="small ghost" id="c-add-bank">${icon('plus', 12)} ${esc(w('add_bank'))}</button>
    <div id="c-partners-box"><h3>${esc(w('partners'))}</h3><div id="c-partners">${partners.html}</div>
    <button type="button" class="small ghost" id="c-add-partner">${icon('plus', 12)} ${esc(w('add_partner'))}</button></div>
    <div class="field"><label for="c-notes">${esc(w('f_notes'))}</label><textarea id="c-notes" rows="2">${esc(c.notes || '')}</textarea></div>
    ${yearCard}`;
  const footer = `${!isNew && may('clients', 'delete') ? `<button type="button" class="pill" data-del>${icon('trash', 14)} ${esc(w('delete'))}</button>` : ''}
    <button type="button" class="pill solid" data-save>${icon('save', 15)} ${esc(w('save'))}</button>`;
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
        email: v('#c-email'), phone: v('#c-phone'), gst: v('#c-gst'), address: v('#c-address'), notes: v('#c-notes'),
        banks: read('bank'), partners: read('partner') };
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
    if ($('#y-save')) $('#y-save').onclick = saveYear(() => ({ form: $('#y-form').value, stage: $('#y-stage').value,
      audit: $('#y-audit').checked, assigned: $('#y-assigned').value, ack_no: $('#y-ack').value }));
    const del = card.querySelector('[data-del]');
    if (del) del.onclick = () => confirmDialog(w('delete_title', { name: c.name }), w('delete_body'), async () => {
      try { await api(`/api/clients/${c.id}`, { method: 'DELETE' }); toast(w('deleted'), 'ok'); close(true); reload(); }
      catch (err) { toast(err.message, 'bad', 8); }
    }, w('delete'), { tone: 'danger' });
  } });
}
