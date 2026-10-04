// Delegations - #/delegate. Lend your own powers to a colleague for one filing, one client, some or all clients for a
// year, or (the portal owner) day-to-day portal screens - for set dates; take it back any time (2026-10-04 owner). The
// server decides everything (delegation.py, chips delegation.*): what may be lent, whether a delegation may be made,
// what it covers today. This page draws it. Words: chip ui.delegate.
import { api, esc, toast, busy, pageHead, confirmDialog, t, ps, loadWords, modal, listBox } from './app.js';
import { icon } from './icons.js';

const w = (k, v) => t('delegate', k, v);
const TONE = () => ps('delegate').state_tone || {};   // chip page.delegate
const plusDays = (iso, n) => { const d = new Date(`${iso}T00:00:00`); d.setDate(d.getDate() + n); return d.toISOString().slice(0, 10); };
const day = (iso) => (iso ? iso.split('-').reverse().join('/') : '');

function scope(d) {
  const who = d.kind === 'year_all' ? w('all_clients') : (d.client_names || []).join(', ');
  return d.kind === 'portal' ? '' : `${esc(who)}${d.ay ? ` · ${esc(d.ay)}` : d.kind === 'client' ? ` · ${esc(w('every_year'))}` : ''}`;
}

const head = (html) => `<div class="an-scroll"><table class="cc-tbl an-tbl"><colgroup><col class="dl-who"><col class="dl-scope"><col><col class="dl-dates"><col class="dl-state"></colgroup>
    <thead><tr><th>${esc(w('h_who'))}</th><th>${esc(w('h_scope'))}</th><th>${esc(w('h_can'))}</th><th>${esc(w('h_dates'))}</th><th>${esc(w('h_state'))}</th></tr></thead><tbody>
    ${html}</tbody></table></div>`;

const row = (D, who, mayRevoke) => (d) => `<tr><td><b>${esc(who(d))}</b>${d.note ? `<div class="small muted">${esc(d.note)}</div>` : ''}</td>
      <td>${esc((D.kindOf[d.kind] || {}).label || d.kind)}<div class="small muted">${scope(d)}</div></td>
      <td class="small">${d.grant_labels.map(esc).join(', ')}</td><td class="small">${esc(day(d.starts))} - ${esc(day(d.ends))}</td>
      <td><span class="sv-pill" style="--c:var(${TONE()[d.state]})">${esc(w(`st_${d.state}`))}</span>
        ${mayRevoke && ['active', 'future'].includes(d.state) ? `<button class="btn ghost sm" data-revoke="${esc(d.id)}" data-to="${esc(d.to_label)}">${esc(w('revoke'))}</button>` : ''}</td></tr>`;

function form(D, done) {
  const kinds = D.kinds.map((k, i) => `<label class="dl-kind"><input type="radio" name="dl-kind" value="${esc(k.id)}" ${i ? '' : 'checked'}/>
      <span><b>${esc(k.label)}</b><span class="small muted">${esc(k.sub)}</span></span></label>`).join('');
  const body = `<div class="field"><label for="dl-to">${esc(w('f_to'))}</label><select id="dl-to"><option value="">${esc(w('f_to_pick'))}</option>
      ${D.people.map((p) => `<option value="${esc(p.id)}">${esc(p.name)} · ${esc(p.email)}</option>`).join('')}</select></div>
    <div class="field"><label>${esc(w('f_kind'))}</label><div class="dl-kinds">${kinds}</div></div>
    <div class="field dl-clients-f"><label>${esc(w('f_clients'))} <span class="muted small" data-chosen></span></label>
      <input type="search" data-find placeholder="${esc(w('f_find'))}"/>
      <div class="dl-clients">${D.clients.map((c) => `<label class="ii-opt" data-hay="${esc(`${c.name} ${c.pan}`.toLowerCase())}"><input type="checkbox" value="${esc(c.id)}"/>
      <span>${esc(c.name)} <code class="small">${esc(c.pan)}</code></span></label>`).join('')}<p class="muted small" data-none hidden>${esc(w('no_match'))}</p></div></div>
    <div class="field dl-ay-f"><label for="dl-ay">${esc(w('f_ay'))}</label><select id="dl-ay">${D.years.map((y) => `<option ${y === D.ay ? 'selected' : ''}>${esc(y)}</option>`).join('')}</select></div>
    <div class="field"><label>${esc(w('f_grants'))}</label><div class="dl-grants">${D.lendable.map((g) => `<label class="ii-opt"><input type="checkbox" value="${esc(g.id)}"/><span>${esc(g.label)}</span></label>`).join('')}</div></div>
    <div class="grid two"><div class="field"><label for="dl-from">${esc(w('f_from'))}</label><input id="dl-from" type="date" value="${esc(D.today)}"/></div>
      <div class="field"><label for="dl-until">${esc(w('f_until'))}</label><input id="dl-until" type="date" value="${esc(plusDays(D.today, D.default_days))}"/></div></div>
    <div class="field"><label for="dl-note">${esc(w('f_note'))}</label><input id="dl-note" maxlength="300" placeholder="${esc(w('f_note_ph'))}"/></div>`;
  modal(w('new'), body, {
    stay: true,
    footer: `<button type="button" class="primary" id="dl-save">${icon('share', 14)} ${esc(w('save'))}</button>`,
    onOpen: (b, close) => {
      const root = b.closest('.modal');
      const kind = () => (b.querySelector('[name=dl-kind]:checked') || {}).value;
      const sync = () => {
        const k = D.kindOf[kind()] || {};
        b.querySelector('.dl-clients-f').hidden = k.clients === 'none';
        b.querySelector('.dl-ay-f').hidden = !k.ay;
        b.querySelectorAll('.dl-clients input').forEach((x) => { x.type = k.clients === 'one' ? 'radio' : 'checkbox'; x.name = 'dl-c'; });
      };
      // every word typed must appear somewhere in name + PAN, in any order
      const find = () => {
        const words = b.querySelector('[data-find]').value.toLowerCase().split(/\s+/).filter(Boolean);
        let shown = 0;
        b.querySelectorAll('.dl-clients [data-hay]').forEach((l) => {
          l.hidden = !words.every((x) => l.dataset.hay.includes(x)) && !l.querySelector('input').checked;
          shown += !l.hidden;
        });
        b.querySelector('[data-none]').hidden = shown > 0;
      };
      const count = () => {
        const n = b.querySelectorAll('.dl-clients input:checked').length;
        b.querySelector('[data-chosen]').textContent = n ? `· ${w('n_chosen', { n, all: D.clients.length })}` : '';
      };
      b.querySelector('[data-find]').oninput = find;
      b.querySelector('.dl-clients').onchange = () => { count(); };
      b.querySelectorAll('[name=dl-kind]').forEach((x) => { x.onchange = () => { sync(); count(); }; });
      sync();
      root.querySelector('#dl-save').onclick = (ev) => busy(ev.currentTarget, async () => {
        const k = D.kindOf[kind()] || {};
        const r = await api('/api/delegate', { method: 'POST', body: {
          to: b.querySelector('#dl-to').value, kind: kind(),
          clients: k.clients === 'none' ? [] : [...b.querySelectorAll('.dl-clients input:checked')].map((x) => x.value),
          ay: k.ay ? b.querySelector('#dl-ay').value : '',
          grants: [...b.querySelectorAll('.dl-grants input:checked')].map((x) => x.value),
          starts: b.querySelector('#dl-from').value, ends: b.querySelector('#dl-until').value, note: b.querySelector('#dl-note').value } });
        toast(r.say);
        close();
        done();
      });
    },
  });
}

export async function delegatePage(host) {
  await loadWords('delegate');
  const D = await api('/api/delegate');
  D.kindOf = Object.fromEntries([...D.kinds, { id: 'portal', label: '' }].map((k) => [k.id, k]));
  // each table is list.delegations (side given / received / firm): searched and paged on the server, one page drawn here
  const section = (side, title, ic, has, none, mayRevoke) => (has || side !== 'firm'
    ? `<section class="card an-card"><h3 class="rc-h">${icon(ic, 15)} ${esc(title)}</h3>${has ? `<div data-side="${side}" data-revokes="${mayRevoke ? 1 : ''}"></div>` : `<p class="small muted">${esc(none)}</p>`}</section>` : '');
  const WHO = { given: (d) => d.to_label, received: (d) => d.from_label, firm: (d) => `${d.from_label} → ${d.to_label}` };
  host.innerHTML = pageHead(w('title'), esc(w('lede')),
    D.lendable.length ? `<button type="button" class="primary" id="dl-new">${icon('plus', 14)} ${esc(w('new'))}</button>` : '')
    + section('given', w('given'), 'share', D.given, w('none_given'), true)
    + section('received', w('received'), 'download', D.received, w('none_received'), false)
    + section('firm', w('firm_all'), 'users', D.firm, '', true);
  const nb = host.querySelector('#dl-new');
  if (nb) nb.onclick = () => form(D, () => delegatePage(host));
  host.querySelectorAll('[data-side]').forEach((el) => listBox(el, {
    list: 'delegations', args: { side: el.dataset.side }, row: row(D, WHO[el.dataset.side], !!el.dataset.revokes), wrap: head,
    wire: (rows, r, reload) => rows.querySelectorAll('[data-revoke]').forEach((b) => {
      b.onclick = () => confirmDialog(w('revoke_q'), w('revoke_body', { to: b.dataset.to }), async () => {
        const x = await api(`/api/delegate/${encodeURIComponent(b.dataset.revoke)}/revoke`, { method: 'POST' });
        toast(x.say);
        reload();
      }, w('revoke'), { tone: 'warn' });
    }) }));
