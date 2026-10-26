// Menu builder - the menu the portal shows its members, as folders and screens (core/menus.py). A folder is a row
// with no link: rename it, drag it, add one, delete it once empty. Each screen sits under a folder with its menu
// label, icon and Live/Draft; drag it by its grip to move it, into another folder too. Removing a screen takes it off
// the MENU only - the page stays and still opens by its link; "Not in the menu" puts it back. Save sends the whole
// menu in its new order; the menu, Access Control and the API guard all read the same answer. The framework's own
// admin screens are not listed: they never move.
import { api, esc, toast, pageHead, confirmDialog, t, loadWords, flexiHit, dragRows, modal } from './ui.js';
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
  groups = [...new Set(rows.filter((r) => !r.hidden).map((r) => r.group || ''))];
}

/** The menu screens of one folder, in their order. */
const inGroup = (g) => rows.filter((r) => !r.hidden && (r.group || '') === g);
/** Rows follow the folders' order; a screen whose folder is gone (off the menu) keeps its place at the end. */
const settle = () => {
  rows = [...groups.flatMap((g) => rows.filter((r) => (r.group || '') === g)), ...rows.filter((r) => !groups.includes(r.group || ''))];
};

function draw(host, term) {
  const drafts = rows.filter((r) => r.draft && !r.hidden).length;
  const off = rows.filter((r) => r.hidden);
  const shown = (r) => flexiHit(`${r.label} ${r.base?.label || ''} ${r.group} ${r.id}`, term);
  const grip = term ? `<span class="mb-grip off" title="${esc(w('drag_off'))}">${icon('grip', 14)}</span>`
    : `<span class="mb-grip" data-grip tabindex="0" title="${esc(w('drag'))}" aria-label="${esc(w('drag'))}">${icon('grip', 14)}</span>`;
  const under = (r) => `<select data-under aria-label="${esc(w('col_under'))}">${groups.map((g) => `<option value="${esc(g)}" ${g === (r.group || '') ? 'selected' : ''}>${esc(g || w('no_group'))}</option>`).join('')}</select>`;
  const screenRow = (r) => `<tr class="mb-screen${r.draft ? ' draft' : ''}" data-id="${esc(r.id)}">
      <td>${grip}</td>
      <td><span class="mb-sname">${esc(r.base?.label || r.label)}</span> <code>${esc(r.id)}</code></td>
      <td>${under(r)}</td>
      <td><input data-label value="${esc(r.label)}" placeholder="${esc(r.base?.label || '')}" aria-label="${esc(w('col_label'))}"/></td>
      <td><button type="button" class="ghost mb-ico" data-icon title="${esc(w('pick_icon'))}" aria-label="${esc(w('pick_icon'))}: ${esc(r.icon || 'menu')}">${icon(r.icon || 'menu', 16)}</button></td>
      <td><button type="button" class="mb-state ${r.draft ? 'draft' : 'live'}" data-live title="${esc(w(r.draft ? 'make_live' : 'make_draft'))}">${esc(w(r.draft ? 'draft' : 'live'))}</button></td>
      <td class="mb-acts"><button type="button" class="ghost" data-reset title="${esc(w('reset'))}" aria-label="${esc(w('reset'))}">${icon('rotccw', 14)}</button>
        <button type="button" class="ghost" data-hide title="${esc(w('hide'))}" aria-label="${esc(w('hide'))}">${icon('trash', 14)}</button></td></tr>`;

  const body = groups.map((g, gi) => {
    const kids = inGroup(g);
    const kidsShown = kids.filter(shown);
    if (term && !kidsShown.length && !flexiHit(g, term)) return '';
    return `<tr class="mb-group" data-id="g:${gi}">
        <td>${grip}</td>
        <td colspan="2"><span class="mb-gname">${icon('folder', 15)}<input data-gname value="${esc(g)}" placeholder="${esc(w('no_group'))}" aria-label="${esc(w('group_name'))}"/>
          <span class="mb-count">${esc(kids.length ? w('group_count', { n: kids.length }) : w('group_empty'))}</span></span></td>
        <td colspan="3"></td>
        <td class="mb-acts"><button type="button" class="ghost" data-gdel ${kids.length ? `disabled title="${esc(w('group_not_empty'))}"` : `title="${esc(w('delete_group'))}"`} aria-label="${esc(w('delete_group'))}">${icon('trash', 14)}</button></td></tr>`
      + kidsShown.map(screenRow).join('');
  }).join('');

  host.innerHTML = `${pageHead(w('title'), w('lede'), `<button type="button" id="mb-new">${icon('plus', 15)} ${w('new_group')}</button>
      <button type="button" class="primary" id="mb-save">${icon('save', 15)} ${w('save')}</button>`)}
    <div class="card flush mb-card">
      <div class="mb-bar"><span class="finder">${icon('search', 14)}<input id="mb-find" value="${esc(term)}" placeholder="${esc(w('find_placeholder'))}"/></span>
        ${drafts ? `<span class="mb-note warn">${icon('alert', 13)} ${esc(w('drafts_waiting', { n: drafts }))}</span>` : ''}
        <span class="mb-note" id="mb-dirty" ${dirty ? '' : 'hidden'}>${esc(w('unsaved'))}</span></div>
      <table class="fixed menus-table"><thead><tr><th style="width:30px"></th>
        <th style="width:25%">${w('col_screen')}</th><th style="width:19%">${w('col_under')}</th><th>${w('col_label')}</th>
        <th style="width:48px">${w('col_icon')}</th><th style="width:96px">${w('col_state')}</th><th style="width:70px"></th></tr></thead>
        <tbody id="mb-rows">${body || `<tr><td colspan="7" class="muted">${esc(w('no_match'))}</td></tr>`}</tbody>
        ${off.length ? `<tbody class="mb-off"><tr class="mb-group"><td></td><td colspan="6"><span class="mb-gname">${icon('eye', 15)}<b>${esc(w('off_menu_title'))}</b>
            <span class="mb-count">${esc(w('off_menu_note'))}</span></span></td></tr>
          ${off.filter(shown).map((r) => `<tr class="mb-screen" data-id="${esc(r.id)}"><td></td>
            <td><span class="mb-sname">${esc(r.label)}</span> <code>${esc(r.id)}</code></td>
            <td colspan="3" class="mb-count">${esc(r.group || w('no_group'))}</td>
            <td class="mb-acts" colspan="2"><button type="button" class="ghost" data-unhide title="${esc(w('put_back'))}">${icon('plus', 14)} ${esc(w('put_back'))}</button></td></tr>`).join('')}</tbody>` : ''}
      </table>
    </div>`;

  const tb = host.querySelector('#mb-rows');
  const mark = () => { dirty = true; host.querySelector('#mb-dirty').hidden = false; };
  const redraw = () => { dirty = true; draw(host, term); };
  const rowOf = (el) => rows.find((r) => r.id === el.closest('tr').dataset.id);
  const gOf = (el) => Number(el.closest('tr').dataset.id.slice(2));

  tb.querySelectorAll('[data-gname]').forEach((inp) => {
    inp.oninput = () => {                              // renames the folder for every screen in it
      const gi = gOf(inp), old = groups[gi], name = inp.value.trim();
      rows.forEach((r) => { if ((r.group || '') === old) r.group = name; });
      groups[gi] = name;
      mark();
    };
    inp.onchange = () => { groups = [...new Set(groups)]; settle(); redraw(); };   // a name already in use joins that folder
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
  // 2026-10-26 owner: deleting a menu row takes the screen off the MENU - the page itself is never deleted
  tb.querySelectorAll('[data-hide]').forEach((b) => {
    b.onclick = () => {
      const r = rowOf(b);
      confirmDialog(w('hide_q'), w('hide_body', { label: r.label }), () => { r.hidden = true; redraw(); }, w('hide_yes'));
    };
  });
  host.querySelectorAll('[data-unhide]').forEach((b) => {
    b.onclick = () => { const r = rowOf(b); r.hidden = false; if (!groups.includes(r.group || '')) groups.push(r.group || ''); settle(); redraw(); };
  });
  // Drag by the grip (Alt + arrow keys too): a folder carries its screens; a screen joins the folder it lands under.
  if (!term) {
    dragRows(tb, (ids) => {
      const folders = ids.filter((i) => i.startsWith('g:')).map((i) => groups[Number(i.slice(2))]);
      if (folders.join('\u0001') !== groups.join('\u0001')) groups = folders;
      else {
        let g = groups[0];
        const moved = [];
        ids.forEach((i) => { if (i.startsWith('g:')) g = groups[Number(i.slice(2))]; else { const r = rows.find((x) => x.id === i); r.group = g; moved.push(r); } });
        rows = [...moved, ...rows.filter((r) => !moved.includes(r))];
      }
      settle();
      redraw();
    });
  }

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
    const send = [...rows, ...fixed].map(({ id, label, group, icon: ic, draft, hidden, base }) => ({ id, label: (label || '').trim() || base?.label, group, icon: ic, draft, hidden }));
    take((await api('/api/core/menus', { method: 'PUT', body: { rows: send } })).rows);
    dirty = false;
    toast(w('saved'));
    await refresh();                                     // the menu follows at once
    draw(host, term);
  };
}
