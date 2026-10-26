// Menu builder - the menu the portal shows its members, as folders and screens (core/menus.py). A group is a folder
// row with no link: rename it, move it, add one, delete it once empty. Each screen sits under a group ("Under"), with
// its menu label, icon, Live/Draft and place. Save sends the whole menu in its new order; the menu, Access Control
// and the API guard all read the same answer. The framework's own admin screens are not listed: they never move.
import { api, esc, toast, pageHead, confirmDialog, t, loadWords, flexiHit, modal } from './ui.js';
import { refresh } from './shell.js';
import { icon } from './icons.js';

// Every word on this screen is chip ui.menus (core/words.py) - none is written here.
const w = (k, v) => t('menus', k, v);
const ICONS = ['menu', 'book', 'globe', 'sun', 'moon', 'spark', 'sparkles', 'users', 'user', 'eye', 'clock', 'pulse', 'shield',
  'key', 'chip', 'wand', 'help', 'heart', 'folder', 'image', 'film', 'play', 'mic', 'chat', 'notebook', 'flag', 'search', 'list', 'cap',
  'money', 'link', 'deck', 'agent', 'plug', 'alert', 'info', 'lock', 'crop', 'video', 'share', 'bell', 'setup', 'prompt'];

let rows = [];      // the screens this page arranges (not the framework's admin screens)
let fixed = [];     // the framework's admin screens: sent back as they are, after the rest
let groups = [];    // folder names, in menu order ('' = screens in no folder)
let dirty = false;

export async function menusPage(host) {
  await loadWords('menus');
  take((await api('/api/core/menus')).rows);
  dirty = false;
  draw(host, '');
}

function take(all) {
  rows = all.filter((r) => !r.core);
  fixed = all.filter((r) => r.core);
  groups = [...new Set(rows.map((r) => r.group || ''))];
}

/** The screens of one folder, in their order. */
const inGroup = (g) => rows.filter((r) => (r.group || '') === g);
/** Rows follow the folders' order, so the saved order is folder by folder. */
const settle = () => { rows = groups.flatMap(inGroup); };

function draw(host, term) {
  const drafts = rows.filter((r) => r.draft).length;
  const shown = (r) => flexiHit(`${r.label} ${r.base?.label || ''} ${r.group} ${r.id}`, term);
  const under = (r) => `<select data-under aria-label="${esc(w('col_under'))}">${groups.map((g) => `<option value="${esc(g)}" ${g === (r.group || '') ? 'selected' : ''}>${esc(g || w('no_group'))}</option>`).join('')}</select>`;
  const order = (attr, i, n) => `<span class="mb-order">
      <button type="button" class="small ghost" ${attr}="-1" ${i === 0 ? 'disabled' : ''} title="${esc(w('move_up'))}" aria-label="${esc(w('move_up'))}">${icon('up', 14)}</button>
      <button type="button" class="small ghost" ${attr}="1" ${i === n - 1 ? 'disabled' : ''} title="${esc(w('move_down'))}" aria-label="${esc(w('move_down'))}">${icon('down', 14)}</button></span>`;

  const body = groups.map((g, gi) => {
    const kids = inGroup(g);
    const kidsShown = kids.filter(shown);
    if (term && !kidsShown.length && !flexiHit(g, term)) return '';
    return `<tr class="mb-group" data-g="${gi}">
        <td colspan="2"><span class="mb-gname">${icon('folder', 16)}<input data-gname value="${esc(g)}" placeholder="${esc(w('no_group'))}" aria-label="${esc(w('group_name'))}"/></span></td>
        <td class="small muted">${esc(kids.length ? w('group_count', { n: kids.length }) : w('group_empty'))}</td><td></td><td></td>
        <td class="mb-acts">${order('data-gmove', gi, groups.length)}
          <button type="button" class="small ghost" data-gdel ${kids.length ? `disabled title="${esc(w('group_not_empty'))}"` : `title="${esc(w('delete_group'))}"`} aria-label="${esc(w('delete_group'))}">${icon('trash', 14)}</button></td></tr>`
      + kidsShown.map((r) => `<tr class="mb-screen ${r.draft ? 'warn' : ''}" data-id="${esc(r.id)}">
        <td><div class="mb-sname">${esc(r.base?.label || r.label)}</div><code class="small muted">${esc(r.id)}</code></td>
        <td>${under(r)}</td>
        <td><input data-label value="${esc(r.label)}" placeholder="${esc(r.base?.label || '')}" aria-label="${esc(w('col_label'))}"/></td>
        <td><button type="button" class="iconpick" data-icon title="${esc(w('pick_icon'))}" aria-label="${esc(w('pick_icon'))}: ${esc(r.icon || 'menu')}">${icon(r.icon || 'menu', 18)}</button></td>
        <td><button type="button" class="small mb-state ${r.draft ? 'draft' : 'live'}" data-live title="${esc(w(r.draft ? 'make_live' : 'make_draft'))}">${icon(r.draft ? 'lock' : 'check', 13)} ${esc(w(r.draft ? 'draft' : 'live'))}</button></td>
        <td class="mb-acts">${term ? '' : order('data-move', kids.indexOf(r), kids.length)}
          <button type="button" class="small ghost" data-reset title="${esc(w('reset'))}" aria-label="${esc(w('reset'))}">${icon('rotccw', 14)}</button></td></tr>`).join('');
  }).join('');

  host.innerHTML = `${pageHead(w('title'), w('lede'), `<button type="button" id="mb-new">${icon('plus', 15)} ${w('new_group')}</button>
      <button type="button" class="primary" id="mb-save">${icon('save', 15)} ${w('save')}</button>`)}
    ${drafts ? `<p class="small" style="color:var(--warn)">${icon('alert', 14)} ${esc(w('drafts_waiting', { n: drafts }))}</p>` : ''}
    <div class="card flush">
      <div class="row between" style="padding:12px 14px"><span class="finder">${icon('search', 15)}<input id="mb-find" value="${esc(term)}" placeholder="${esc(w('find_placeholder'))}"/></span>
        <span class="small muted" id="mb-dirty" ${dirty ? '' : 'hidden'}>${esc(w('unsaved'))}</span></div>
      <div class="scroll" style="max-height:none"><table class="fixed menus-table"><thead><tr>
        <th style="width:24%">${w('col_screen')}</th><th style="width:21%">${w('col_under')}</th><th>${w('col_label')}</th>
        <th style="width:64px">${w('col_icon')}</th><th style="width:150px">${w('col_state')}</th><th style="width:118px">${w('col_order')}</th></tr></thead>
        <tbody id="mb-rows">${body || `<tr><td colspan="6" class="muted">${esc(w('no_match'))}</td></tr>`}</tbody></table></div>
    </div>`;

  const tb = host.querySelector('#mb-rows');
  const mark = () => { dirty = true; host.querySelector('#mb-dirty').hidden = false; };
  const redraw = () => { dirty = true; draw(host, term); };
  const rowOf = (el) => rows.find((r) => r.id === el.closest('tr').dataset.id);
  const gOf = (el) => Number(el.closest('tr').dataset.g);

  tb.querySelectorAll('[data-gname]').forEach((inp) => {
    inp.oninput = () => {                              // renames the folder for every screen in it
      const gi = gOf(inp), old = groups[gi], name = inp.value.trim();
      rows.forEach((r) => { if ((r.group || '') === old) r.group = name; });
      groups[gi] = name;
      mark();
    };
    inp.onchange = () => { groups = [...new Set(groups)]; settle(); redraw(); };   // a name already in use joins that folder
  });
  tb.querySelectorAll('[data-gmove]').forEach((b) => {
    b.onclick = () => { const i = gOf(b), j = i + Number(b.dataset.gmove); [groups[i], groups[j]] = [groups[j], groups[i]]; settle(); redraw(); };
  });
  tb.querySelectorAll('[data-gdel]').forEach((b) => {
    b.onclick = () => {
      const i = gOf(b);
      confirmDialog(w('delete_group_q'), w('delete_group_body', { name: groups[i] || w('no_group') }), () => { groups.splice(i, 1); redraw(); });
    };
  });
  tb.querySelectorAll('[data-under]').forEach((s) => {
    s.onchange = () => { const r = rowOf(s); rows = rows.filter((x) => x !== r); r.group = s.value; rows.push(r); settle(); redraw(); };
  });
  tb.querySelectorAll('[data-move]').forEach((b) => {
    b.onclick = () => {
      const r = rowOf(b), kids = inGroup(r.group || ''), other = kids[kids.indexOf(r) + Number(b.dataset.move)];
      const i = rows.indexOf(r), j = rows.indexOf(other);
      [rows[i], rows[j]] = [rows[j], rows[i]];
      redraw();
    };
  });
  tb.querySelectorAll('[data-label]').forEach((inp) => { inp.oninput = () => { rowOf(inp).label = inp.value; mark(); }; });
  tb.querySelectorAll('[data-live]').forEach((b) => { b.onclick = () => { const r = rowOf(b); r.draft = !r.draft; redraw(); }; });
  // 2026-10-26 owner: the icon is picked by its picture, never typed by name
  tb.querySelectorAll('[data-icon]').forEach((b) => {
    b.onclick = () => {
      const r = rowOf(b);
      modal(w('pick_icon'), `<div class="icongrid">${ICONS.map((i) => `<button type="button" data-pick="${i}" class="${i === r.icon ? 'on' : ''}"
        title="${i}" aria-label="${i}">${icon(i, 20)}</button>`).join('')}</div>`, {
        onOpen: (box, close) => box.querySelectorAll('[data-pick]').forEach((p) => {
          p.onclick = () => { r.icon = p.dataset.pick; close(); redraw(); };
        }),
      });
    };
  });
  tb.querySelectorAll('[data-reset]').forEach((b) => {
    b.onclick = () => {
      const r = rowOf(b);
      confirmDialog(w('reset_q'), w('reset_body', { label: r.label }), async () => {
        take((await api(`/api/core/menus/${encodeURIComponent(r.id)}`, { method: 'DELETE' })).rows);
        await refresh();
        draw(host, term);
      });
    };
  });

  host.querySelector('#mb-new').onclick = () => {
    let name = w('new_group_name'), n = 2;
    while (groups.includes(name)) name = `${w('new_group_name')} ${n++}`;
    groups.unshift(name);
    dirty = true;
    draw(host, '');
    const inp = host.querySelector('[data-gname]');
    inp.focus(); inp.select();
  };
  const find = host.querySelector('#mb-find');
  find.oninput = () => { draw(host, find.value); const f = host.querySelector('#mb-find'); f.focus(); f.setSelectionRange(f.value.length, f.value.length); };
  host.querySelector('#mb-save').onclick = async () => {
    settle();
    const send = [...rows, ...fixed].map(({ id, label, group, icon: ic, draft, base }) => ({ id, label: (label || '').trim() || base?.label, group, icon: ic, draft }));
    take((await api('/api/core/menus', { method: 'PUT', body: { rows: send } })).rows);
    dirty = false;
    toast(w('saved'));
    await refresh();                                     // the menu follows at once
    draw(host, term);
  };
}
