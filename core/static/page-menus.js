// Menu builder - every screen's name, group, icon and place in the menu, and Live for a screen that arrived as a
// draft (core/menus.py). One table: drag a row to move it, type over a name or group, pick an icon. Save sends the
// whole menu in its new order; the menu, Access Control and the API guard all read the same answer.
import { api, esc, toast, pageHead, confirmDialog, t, loadWords, flexiHit, dragRows, modal } from './ui.js';
import { refresh } from './shell.js';
import { icon } from './icons.js';

// Every word on this screen is chip ui.menus (core/words.py) - none is written here.
const w = (k, v) => t('menus', k, v);
const ICONS = ['menu', 'book', 'globe', 'sun', 'moon', 'spark', 'sparkles', 'users', 'user', 'eye', 'clock', 'pulse', 'shield',
  'key', 'chip', 'wand', 'help', 'heart', 'folder', 'image', 'film', 'play', 'mic', 'chat', 'notebook', 'flag', 'search', 'list', 'cap',
  'money', 'link', 'deck', 'agent', 'plug', 'alert', 'info', 'lock', 'crop', 'video', 'share', 'bell', 'setup', 'prompt'];

let rows = [];
let dirty = false;

export async function menusPage(host) {
  await loadWords('menus');
  rows = (await api('/api/core/menus')).rows;
  dirty = false;
  draw(host, '');
}

function draw(host, term) {
  const drafts = rows.filter((r) => r.draft).length;
  const groups = [...new Set(rows.map((r) => r.group).filter(Boolean))];
  host.innerHTML = `${pageHead(w('title'), w('lede'), `<button type="button" class="primary" id="mb-save">${icon('save', 15)} ${w('save')}</button>`)}
    ${drafts ? `<p class="small" style="color:var(--warn)">${icon('alert', 14)} ${esc(w('drafts_waiting', { n: drafts }))}</p>` : ''}
    <div class="card flush">
      <div class="row between" style="padding:10px 12px"><span class="finder">${icon('search', 15)}<input id="mb-find" value="${esc(term)}" placeholder="${esc(w('find_placeholder'))}"/></span>
        <span class="small muted" id="mb-dirty" ${dirty ? '' : 'hidden'}>${esc(w('unsaved'))}</span></div>
      <div class="scroll" style="max-height:none"><table class="fixed menus-table"><thead><tr><th style="width:34px"></th><th>${w('col_name')}</th>
        <th>${w('col_group')}</th><th style="width:76px">${w('col_icon')}</th><th style="width:170px">${w('col_state')}</th><th style="width:44px"></th></tr></thead>
        <tbody id="mb-rows"></tbody></table></div>
      <datalist id="mb-groups">${groups.map((g) => `<option value="${esc(g)}">`).join('')}</datalist>
    </div>`;
  const body = host.querySelector('#mb-rows');
  const shown = rows.filter((r) => flexiHit(`${r.label} ${r.group} ${r.id}`, term));
  body.innerHTML = shown.map((r) => `<tr data-id="${esc(r.id)}" class="${r.draft ? 'warn' : ''}">
      <td><span ${term ? `title="${esc(w('drag_off'))}"` : `data-grip tabindex="0" title="${esc(w('drag'))}" style="cursor:grab"`}>${icon('grip', 15)}</span></td>
      <td><input data-f="label" value="${esc(r.label)}"/><div class="small muted"><code>${esc(r.id)}</code></div></td>
      <td><input data-f="group" list="mb-groups" value="${esc(r.group || '')}"/></td>
      <td><button type="button" class="iconpick" data-icon title="${esc(w('pick_icon'))}" aria-label="${esc(w('pick_icon'))}: ${esc(r.icon || 'menu')}">${icon(r.icon || 'menu', 18)}</button></td>
      <td>${r.core ? `<span class="small muted">${icon('lock', 13)} ${esc(w('owner_only'))}</span>` : `<button type="button" class="small" data-live="${r.draft ? '1' : '0'}" aria-pressed="${!r.draft}" title="${esc(w(r.draft ? 'make_live' : 'make_draft'))}"
        style="${r.draft ? 'color:var(--warn);border-color:var(--warn)' : 'color:var(--ok);border-color:var(--ok)'}">${icon(r.draft ? 'lock' : 'check', 13)} ${esc(w(r.draft ? 'draft' : 'live'))}</button>`}</td>
      <td><button type="button" class="small" data-reset title="${esc(w('reset'))}" aria-label="${esc(w('reset'))}">${icon('rotccw', 14)}</button></td>
    </tr>`).join('') || `<tr><td colspan="6" class="muted">${esc(w('no_match'))}</td></tr>`;

  const mark = () => { dirty = true; host.querySelector('#mb-dirty').hidden = false; };
  const rowOf = (el) => rows.find((r) => r.id === el.closest('tr').dataset.id);
  body.querySelectorAll('input[data-f]').forEach((inp) => {
    inp.oninput = () => { rowOf(inp)[inp.dataset.f] = inp.value; mark(); };
  });
  // 2026-10-26 owner: the icon is picked by its picture, never typed by name
  body.querySelectorAll('[data-icon]').forEach((b) => {
    b.onclick = () => {
      const r = rowOf(b);
      modal(w('pick_icon'), `<div class="icongrid">${ICONS.map((i) => `<button type="button" data-pick="${i}" class="${i === r.icon ? 'on' : ''}"
        title="${i}" aria-label="${i}">${icon(i, 20)}</button>`).join('')}</div>`, {
        onOpen: (box, close) => box.querySelectorAll('[data-pick]').forEach((p) => {
          p.onclick = () => { r.icon = p.dataset.pick; dirty = true; close(); draw(host, term); };
        }),
      });
    };
  });
  body.querySelectorAll('[data-live]').forEach((b) => {
    b.onclick = () => { rowOf(b).draft = b.dataset.live === '0'; dirty = true; draw(host, term); };
  });
  body.querySelectorAll('[data-reset]').forEach((b) => {
    b.onclick = () => {
      const r = rowOf(b);
      confirmDialog(w('reset_q'), w('reset_body', { label: r.label }), async () => {
        rows = (await api(`/api/core/menus/${encodeURIComponent(r.id)}`, { method: 'DELETE' })).rows;
        await refresh();
        draw(host, term);
      });
    };
  });
  if (!term) {
    dragRows(body, (ids) => { rows = ids.map((id) => rows.find((r) => r.id === id)); mark(); });
  }
  const find = host.querySelector('#mb-find');
  find.oninput = () => { draw(host, find.value); const f = host.querySelector('#mb-find'); f.focus(); f.setSelectionRange(f.value.length, f.value.length); };
  host.querySelector('#mb-save').onclick = async () => {
    rows = (await api('/api/core/menus', { method: 'PUT', body: { rows: rows.map(({ id, label, group, icon: ic, draft }) => ({ id, label, group, icon: ic, draft })) } })).rows;
    dirty = false;
    toast(w('saved'));
    await refresh();                                     // the menu on the left follows at once
    draw(host, term);
  };
}
