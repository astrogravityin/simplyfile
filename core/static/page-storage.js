// Storage — who holds the disk. Every account by space used, how many files, holding since when; and
// from the same page, the clean-up process: three requests three days apart, then on day 7 the owner
// may delete some or all of that person's items. The server enforces every date; this page shows them.
import { api, esc, say, modal, confirmDialog, toast, busy, pageHead, t, loadWords, listBox, offAttr } from './ui.js';
import { icon } from './icons.js';

// Every word on this screen is chip ui.storage (core/words.py) - none is written here.
const w = (k, v) => t('storage', k, v);

let selected = '';
let d = null;

const size = (n) => (n >= 1024 ** 3 ? `${(n / 1024 ** 3).toFixed(2)} GB` : n >= 1024 ** 2 ? `${Math.round(n / 1024 ** 2)} MB` : n ? `${Math.max(1, Math.round(n / 1024))} KB` : '0');
const day = (tsOrIso) => (tsOrIso ? new Date(typeof tsOrIso === 'number' ? tsOrIso * 1000 : tsOrIso)
  .toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' }) : '—');
const age = (iso) => {
  if (!iso) return '—';
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 864e5);
  return days < 1 ? w('today') : days < 60 ? w(days === 1 ? 'one_day' : 'n_days', { n: days }) : w('n_months', { n: Math.round(days / 30) });
};

function stageTag(p) {
  const s = p.stage;
  if (!s.requests) return '';
  if (s.can_delete) return `<span class="tag bad">${icon('trash', 11)} ${w('may_delete')}</span>`;
  return `<span class="tag warn">${w('n_sent', { n: s.requests, max: d.rules.max_requests })}</span>`;
}

// --- what each person may hold (2026-10-01 owner: "move it under Storage - give the option to edit, and show how much is
// used out of allocated"). The boxes, their words and the numbers are the portal's (core/storage.py register_limits);
// only the owner changes them.
const pct = (p) => Math.min(100, Math.round((100 * p.bytes) / p.limit.quota_bytes));
const tight = (p) => !!(p.limit && p.limit.quota_bytes && pct(p) >= p.limit.tight_pct);
const used = (p) => (p.limit ? w('used_of', { used: size(p.bytes), quota: p.limit.quota_bytes ? size(p.limit.quota_bytes) : w('no_limit') }) : size(p.bytes));
const shown = (f, v) => `${v} ${f.unit || ''}`.trim();

function limitsCard(L) {
  const box = (f) => `<div class="field"><label for="st-f-${esc(f.key)}">${esc(f.label)}</label>
      ${L.can_edit ? `<input id="st-f-${esc(f.key)}" data-limit="${esc(f.key)}" inputmode="numeric" value="${esc(String(L.defaults[f.key] ?? ''))}"/>`
        : `<b id="st-f-${esc(f.key)}">${esc(shown(f, L.defaults[f.key] ?? ''))}</b>`}
      <span class="small muted">${esc(f.note || '')}</span></div>`;
  return `<section class="card" id="st-limits"><h3>${icon('shield', 15)} ${w('limits_title')}</h3>
    <p class="small muted">${w('limits_note')}</p>
    <div class="grid two">${L.fields.map(box).join('')}</div><div id="st-limits-msg"></div>
    ${L.can_edit ? `<div class="row"><button type="button" class="primary" id="st-save-limits">${icon('save')} ${w('save_limits')}</button></div>`
      : `<p class="small muted">${w('limits_owner_only')}</p>`}</section>`;
}

function wireLimits(host) {
  const save = host.querySelector('#st-save-limits');
  if (!save) return;
  save.onclick = (e) => busy(e.currentTarget, async () => {
    const body = Object.fromEntries([...host.querySelectorAll('[data-limit]')].map((i) => [i.dataset.limit, i.value.trim()]));
    try { toast((await api('/api/core/storage/limits', { method: 'PUT', body })).message, 'ok'); storagePage(host); }
    catch (err) { say(host.querySelector('#st-limits-msg'), 'bad', esc(err.message)); }
  });
}

function personLimits(p) {
  const L = p.limit;
  const can = d.limits && d.limits.can_edit;
  const custom = Object.keys(L.own || {}).length > 0;
  return `<section id="st-person-limits"><div class="row between"><h3>${icon('shield', 15)} ${w('their_limit')}</h3>
      <span class="tag ${custom ? 'brand' : ''}">${w(custom ? 'own_badge' : 'default_badge')}</span></div>
    <div class="stats">
      <div class="stat"><b>${size(p.bytes)}</b><span>${w('held')}</span></div>
      <div class="stat"><b>${L.quota_bytes ? size(L.quota_bytes) : w('no_limit')}</b><span>${w('allocated')}</span></div>
      <div class="stat"><b>${L.quota_bytes ? `${pct(p)}%` : '—'}</b><span>${L.quota_bytes ? w('used_pct', { pct: pct(p) }) : w('no_limit')}</span></div></div>
    <i class="usebar ${tight(p) ? 'tight' : ''}"><i style="width:${L.quota_bytes ? pct(p) : 0}%"></i></i>
    <div class="row"><span class="small muted">${w('upload_up_to', { mb: L.max_upload_mb })}</span><span class="spacer"></span>
      ${can ? `<button type="button" id="st-edit-limits">${icon('edit', 13)} ${w('edit_limits')}</button>` : ''}</div></section>`;
}

/** One person's own limits: a blank box follows the default for everyone; Use defaults asks first. */
function limitsDialog(p, done) {
  const L = d.limits;
  const own = p.limit.own || {};
  const fields = L.fields.filter((f) => f.person);
  const url = `/api/core/storage/${encodeURIComponent(p.id)}/limits`;
  modal(w('person_limits_title', { name: p.name || p.email }), `<p class="small muted">${w('person_limits_note')}</p>
    <div class="grid two">${fields.map((f) => `<div class="field"><label for="sp-${esc(f.key)}">${esc(f.label)}</label>
      <input id="sp-${esc(f.key)}" data-own="${esc(f.key)}" inputmode="numeric" value="${esc(String(own[f.key] ?? ''))}" placeholder="${esc(String(L.defaults[f.key] ?? ''))}"/>
      <span class="small muted">${w('default_hint', { value: esc(shown(f, L.defaults[f.key] ?? '')) })}</span></div>`).join('')}</div><div id="sp-msg"></div>`, {
    footer: `<button type="button" data-cancel>${w('cancel')}</button>
      ${Object.keys(own).length ? `<button type="button" class="ghost" id="sp-default">${icon('refresh', 13)} ${w('use_default')}</button>` : ''}
      <button type="button" class="primary" id="sp-save">${icon('save', 13)} ${w('save_limits')}</button>`,
    onOpen: (body, close) => {
      const m = body.closest('.modal');
      m.querySelector('[data-cancel]').onclick = close;
      m.querySelector('#sp-save').onclick = (e) => busy(e.currentTarget, async () => {
        const vals = Object.fromEntries([...body.querySelectorAll('[data-own]')].map((i) => [i.dataset.own, i.value.trim()]));
        try { toast((await api(url, { method: 'PUT', body: vals })).message, 'ok'); close(); done(); }
        catch (err) { say(body.querySelector('#sp-msg'), 'bad', esc(err.message)); }
      });
      const back = m.querySelector('#sp-default');
      if (back) back.onclick = () => confirmDialog(w('use_default_title', { name: p.name || p.email }), w('use_default_body'), async () => {
        try { toast((await api(url, { method: 'DELETE' })).message, 'ok'); close(); done(); }
        catch (err) { say(body.querySelector('#sp-msg'), 'bad', esc(err.message)); }
      }, w('use_default'), { tone: 'warn' });
    } });
}

// 2026-09-28 owner "tens of thousands": the people are list storage_people - one searched page at a time; a person's
// items come only with their own row when they are opened.
export async function storagePage(host) {
  [d] = await Promise.all([api('/api/core/storage'), loadWords('storage')]);
  const T = d.totals;
  const tile = (n, label) => `<div class="stat"><b>${n}</b><span>${label}</span></div>`;
  host.innerHTML = `${pageHead(w('title'), w('lede', { gap: d.rules.gap_days, day: d.rules.delete_after_days }))}
    ${d.can_email ? '' : `<div class="note warn">${icon('mail')}<div>${w('no_email')}</div></div>`}
    <div class="stats">${tile(size(T.bytes), w('tile_held'))}${tile(T.files.toLocaleString(), w('tile_files'))}
      ${tile(T.holders, w('tile_holders'))}${tile(d.disk.free !== undefined ? size(d.disk.free) : '—', w('tile_free'))}
      ${tile(T.open, w('tile_open'))}</div>
    ${d.limits ? limitsCard(d.limits) : ''}
    <div class="panes">
      <div class="pane"><div class="scrollbody" id="st-list"></div></div>
      <div class="pane"><div class="scrollbody pad" id="st-detail"></div></div>
    </div>`;
  wireLimits(host);
  const max = Math.max(1, T.max_bytes || 0);
  listBox(host.querySelector('#st-list'), { list: 'storage_people', empty: w('no_accounts'),
    row: (p) => `<button type="button" data-user="${esc(p.id)}" class="${p.id === selected ? 'on' : ''} stack-row">
        <span class="nm"><b>${esc(p.email)}</b>
          <span class="small muted">${used(p)} · ${w('n_files', { n: p.files })}${p.since ? ` · ${w('held_for', { age: age(p.since) })}` : ''}</span>
          <i class="usebar ${tight(p) ? 'tight' : ''}"><i style="width:${p.limit && p.limit.quota_bytes ? pct(p) : (100 * p.bytes) / max}%"></i></i></span>
        ${stageTag(p)}</button>`,
    wrap: (html) => `<div class="list">${html}</div>`,
    wire: (rows, r) => {
      rows.querySelectorAll('[data-user]').forEach((b) => {
        b.onclick = () => {
          selected = b.dataset.user;
          rows.querySelectorAll('[data-user]').forEach((x) => x.classList.toggle('on', x.dataset.user === selected));
          detail(host);
        };
      });
      if (!selected && r.rows[0]) { selected = r.rows[0].id; rows.querySelector('[data-user]').classList.add('on'); detail(host); }
    } });
  if (selected) detail(host);
}

async function detail(host) {
  const box = host.querySelector('#st-detail');
  const p = selected ? (await api(`/api/lists/storage_people?${new URLSearchParams({ id: selected })}`)).rows[0] : null;
  if (!p) { box.innerHTML = `<div class="empty"><p>${w('no_accounts')}</p></div>`; return; }
  const s = p.stage;
  const sent = (p.case.requests || []);
  const R = d.rules;
  // The four steps, each with the date it happened or the date it becomes possible.
  const step = (i) => {
    const r = sent[i];
    const due = i === 0 ? null : sent[i - 1] ? new Date(sent[i - 1].at).getTime() / 1000 + R.gap_days * 86400 : null;
    return `<li class="${r ? 'done' : ''}"><b>${i === 0 ? w('ask') : w(i === R.max_requests - 1 ? 'final_reminder' : 'reminder')}</b>
      <span>${r ? `${w(r.emailed ? 'sent_email' : 'sent_banner', { date: day(r.at) })}${r.note ? ` — “${esc(r.note.slice(0, 80))}”` : ''}`
        : due ? w('possible_from', { date: day(due) }) : i === 0 ? w('any_time') : w('after_previous', { n: R.gap_days })}</span></li>`;
  };
  const nextLabel = s.requests === 0 ? w('ask') : w(s.requests === R.max_requests - 1 ? 'send_final' : 'send_reminder');
  box.innerHTML = `
    <div class="row between"><div><h2 style="margin:0">${esc(p.name || p.email)}</h2><span class="small muted">${esc(p.email)} · ${esc(p.role)}</span></div>
      ${stageTag(p)}</div>
    <div class="stats" style="margin-top:14px">
      <div class="stat"><b>${size(p.bytes)}</b><span>${w('held')}</span></div>
      <div class="stat"><b>${p.files}</b><span>${w(p.items_n === 1 ? 'files_in_one' : 'files_in_n', { n: p.items_n })}</span></div>
      <div class="stat"><b>${age(p.since)}</b><span>${p.since ? w('since', { date: day(p.since) }) : w('holding_nothing')}</span></div></div>

    ${p.limit ? personLimits(p) : ''}
    <h3>${icon('mail', 15)} ${w('cleanup')}</h3>
    <ol class="timeline">${[0, 1, 2].map(step).join('')}
      <li class="${s.can_delete ? 'done' : ''}"><b>${w('delete_allowed')}</b>
        <span>${s.requests ? (s.can_delete ? w('delete_since', { date: day(s.delete_at) }) : w('delete_from', { date: day(s.delete_at), n: R.max_requests })) : w('delete_day', { n: R.delete_after_days })}</span></li></ol>
    <div class="row" style="margin:10px 0 18px">
      ${s.requests < R.max_requests ? `<button class="primary" type="button" id="st-ask"${offAttr(!p.files ? w('no_files_to_ask') : !s.can_request ? w('ask_wait') : '')}>${icon('send')} ${nextLabel}</button>` : ''}
      ${!p.files ? `<span class="small muted">${w('no_files_to_ask')}</span>`
        : !s.can_request && s.requests < R.max_requests ? `<span class="small muted">${w('next_from', { date: day(s.next_request_at) })}</span>` : ''}
      ${s.requests ? `<span class="spacer"></span><button type="button" id="st-close">${icon('check')} ${w('close_button')}</button>` : ''}
    </div>

    <h3>${icon('folder', 15)} ${w('their_items')}</h3>
    ${p.items.length ? `<div class="scroll" style="max-height:none"><table>
      <thead><tr><th style="width:34px"><input type="checkbox" id="st-all" ${s.can_delete ? '' : 'disabled'} aria-label="${esc(w('select_all'))}"/></th>
        <th>${w('col_item')}</th><th>${w('col_files')}</th><th>${w('col_size')}</th><th>${w('col_created')}</th><th>${w('col_age')}</th></tr></thead>
      <tbody>${p.items.map((it) => `<tr><td><input type="checkbox" data-item="${esc(it.id)}" ${s.can_delete ? '' : 'disabled'} aria-label="${esc(it.title)}"/></td>
        <td>${esc(it.title)}</td><td>${it.files}</td><td>${size(it.bytes)}</td><td class="small">${day(it.created_at)}</td>
        <td class="small muted">${age(it.created_at)}</td></tr>`).join('')}</tbody></table></div>
      <div class="row" style="margin-top:12px">
        <button class="danger" type="button" id="st-del-some">${icon('trash')} ${w('delete_selected')}</button>
        <button class="danger" type="button" id="st-del-all"${offAttr(s.can_delete ? '' : w('delete_locked'))}>${icon('trash')} ${w('delete_all', { n: p.items_n })}</button>
        ${p.items_n > p.items.length ? `<span class="small muted">${esc(w('items_more', { shown: p.items.length, n: p.items_n }))}</span>` : ''}
        ${s.can_delete ? '' : `<span class="small muted">${icon('lock', 13)} ${s.requests ? w(s.requests < R.max_requests ? 'opens_on_after_final' : 'opens_on', { date: day(s.delete_at) }) : w('opens_after_first', { n: R.delete_after_days })}</span>`}
      </div>` : `<p class="muted small">${w('no_files')}</p>`}`;

  const edit = box.querySelector('#st-edit-limits');
  if (edit) edit.onclick = () => limitsDialog(p, () => { storagePage(host); });
  const ask = box.querySelector('#st-ask');
  if (ask) ask.onclick = () => modal(w('ask_title', { action: nextLabel, email: p.email }), `
      <div id="ask-msg"></div>
      <p class="small muted">${w(d.can_email ? 'ask_body' : 'ask_body_no_email', { size: size(p.bytes), files: p.files })}</p>
      <div class="field"><label for="ask-note">${w('note_label')}</label>
        <textarea id="ask-note" maxlength="1000" placeholder="${esc(w('note_placeholder'))}"></textarea></div>`, {
    footer: `<button type="button" data-cancel>${w('cancel')}</button><button type="button" class="primary" id="ask-go">${icon('send')} ${w('send')}</button>`,
    onOpen: (body, close) => {
      const card = body.closest('.modal');
      card.querySelector('[data-cancel]').onclick = close;
      card.querySelector('#ask-go').onclick = (e) => busy(e.currentTarget, async () => {
        try {
          const r = await api(`/api/core/storage/${p.id}/request`, { method: 'POST', body: { note: body.querySelector('#ask-note').value } });
          close();
          toast(r.emailed ? w('sent_to', { email: p.email }) : w('recorded', { why: r.why }), r.emailed ? 'ok' : 'warn', 7);
          storagePage(host);
        } catch (err) { say(body.querySelector('#ask-msg'), 'bad', esc(err.message)); }
      });
    } });

  const close = box.querySelector('#st-close');
  if (close) close.onclick = () => confirmDialog(w('close_title'), w('close_body'), async () => {
    try { await api(`/api/core/storage/${p.id}/close`, { method: 'POST' }); toast(w('closed'), 'ok'); storagePage(host); }
    catch (e) { toast(e.message, 'bad'); }
  }, w('close'), { tone: 'warn' });

  const picked = () => [...box.querySelectorAll('[data-item]:checked')].map((c) => c.dataset.item);
  const some = box.querySelector('#st-del-some');

  const all = box.querySelector('#st-all');
  if (all) all.onchange = () => { box.querySelectorAll('[data-item]').forEach((c) => { c.checked = all.checked; }); };
  const remove = (ids, everything) => {
    const n = everything ? p.items_n : ids.length;
    const bytes = everything ? p.items_bytes : p.items.filter((i) => ids.includes(i.id)).reduce((t, i) => t + i.bytes, 0);
    confirmDialog(w(n === 1 ? 'delete_title_one' : 'delete_title_n', { n, email: p.email }),
      `${w(n === 1 ? 'delete_body_one' : 'delete_body_n', { size: size(bytes) })}${d.can_email ? w('delete_told') : ''}`,
      async () => {
        try {
          const r = await api(`/api/core/storage/${p.id}/delete`, { method: 'POST', body: everything ? { all: true } : { ids } });
          toast(`${w('deleted', { n: r.deleted, size: size(r.freed_bytes) })}${r.skipped.length ? w('skipped', { n: r.skipped.length, why: r.skipped[0].why }) : ''}`,
            r.skipped.length ? 'warn' : 'ok', 8);
          storagePage(host);
        } catch (e) { toast(e.message, 'bad'); }
      }, w('delete_for_good'), { tone: 'danger' });
  };
  if (some) some.onclick = () => (picked().length ? remove(picked(), false) : toast(w('tick_first'), 'warn'));   // never greyed
  const delAll = box.querySelector('#st-del-all');
  if (delAll) delAll.onclick = () => remove([], true);
}
