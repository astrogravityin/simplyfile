// How to Use — the training link and video link each screen carries. This is the module the other
// two feed: a published manual wires itself in here, and a narrated video is pasted in here.
//
// Master / detail, not a table and a dialog. The left pane is every screen, grouped and searchable,
// each row carrying the COUNT of live links — so "which screens are still undocumented?" is answered
// by looking, not by opening things one at a time. The right pane edits the selected screen in place.
import { api, esc, state, project, loadProjects, toast, busy, t, loadWords, confirmDialog, ps } from './app.js';
import { icon, emptyState } from './icons.js';

// Every word on this screen is chip ui.howto (core/words.py) - none is written here.
const w = (k, v) => t('howto', k, v);

// 2026-09-26: the link kinds and their icons are chip page.howto
const TYPES = () => ps('howto').types || [];
const typeIcon = (t) => `<span class="t-${t || 'link'}">${icon((ps('shell').howto_icons || {})[t] || 'link', 15)}</span>`;

/** Mirrors projects.clean_link on the server: with the type left on "auto", this is what gets saved. */
function guessType(url = '') {
  if (/youtu\.?be/i.test(url)) return 'youtube';
  if (/instagram\./i.test(url)) return 'instagram';
  if (/\.(mp4|webm|mov)(\?|$)/i.test(url)) return 'video';
  if (url.startsWith('/m/') || /\.(pdf|html?|docx?)(\?|$)/i.test(url)) return 'doc';
  return 'link';
}

let selected = '';        // which screen the right pane is showing
let draft = [];           // that screen's links, being edited
let dirty = false;

export async function howtoPage(host) {
  await loadWords('howto');
  const p = project();
  if (!p) {                                             // the page keeps its name even before a project exists
    host.innerHTML = `<h1>${w('title')}</h1><div class="card" id="ht-none">${emptyState('projects', w('no_project_title'),
      w('no_project_body'),
      `<a href="#/setup"><button class="primary" type="button">${w('register_project')}</button></a>`)}</div>`;
    return;
  }

  const screens = p.screens || [];
  const links = p.links || {};
  const live = (key) => (links[key] || []).filter((l) => l.active !== false).length;
  const total = screens.reduce((n, s) => n + live(s.key), 0);
  const covered = screens.filter((s) => live(s.key)).length;

  if (!screens.some((s) => s.key === selected)) selected = screens[0] ? screens[0].key : '';

  host.innerHTML = `<h1>${w('title')}</h1>
    <p class="muted">${w('lede', { project: esc(p.name) })}</p>

    ${screens.length ? '' : `<div class="note warn">${icon('alert')}<div>${w('no_screens')}</div></div>`}

    <div class="row" id="ht-stats" style="margin:0 0 14px;gap:18px">
      <span class="row tight small muted">${icon('help', 15)} ${w('documented', { covered, total: screens.length })}</span>
      <span class="row tight small muted">${icon('link', 15)} ${w('live_links', { n: total })}</span>
    </div>

    <div class="panes">
      <div class="pane">
        <div class="top">
          <div class="finder">${icon('search', 15)}<input id="ht-q" placeholder="${esc(w('find_placeholder'))}"/></div>
          <label class="check small" style="margin-top:9px">
            <input type="checkbox" id="ht-only"/> ${w('only_empty')}</label>
        </div>
        <div class="scrollbody"><div class="list" id="ht-list"></div></div>
      </div>

      <div class="pane"><div class="scrollbody pad" id="ht-detail"></div></div>
    </div>

    <div class="card" id="ht-reading" style="margin-top:18px"><h2>${icon('external', 17)} ${w('reading_title')}</h2>
      <p class="muted small">${w('reading_line')}</p>
      <pre>fetch('${esc(state.portalUrl || '')}/api/public/howto/${esc(p.key)}')
  .then(r =&gt; r.json())
  .then(d =&gt; d.screens['${esc((screens[0] || {}).key || 'screen-key')}'])</pre></div>`;

  const listEl = host.querySelector('#ht-list');
  const q = host.querySelector('#ht-q');
  const only = host.querySelector('#ht-only');

  const drawList = () => {
    const needle = q.value.trim().toLowerCase();
    const shown = screens.filter((s) => (!needle || `${s.label} ${s.key} ${s.route || ''}`.toLowerCase().includes(needle))
      && (!only.checked || !live(s.key)));
    if (!shown.length) { listEl.innerHTML = `<div class="none">${w('nothing_matches')}</div>`; return; }

    // Grouped the way Setup grouped them; ungrouped screens fall under one quiet heading.
    const groups = new Map();
    shown.forEach((s) => {
      const g = s.group || w('group_screens');
      if (!groups.has(g)) groups.set(g, []);
      groups.get(g).push(s);
    });
    listEl.innerHTML = [...groups.entries()].map(([g, rows]) => `<div class="grp">${esc(g)}</div>`
      + rows.map((s) => {
        const n = live(s.key);
        return `<button type="button" data-pick="${esc(s.key)}" class="${s.key === selected ? 'on' : ''}">
          <span class="nm" title="${esc(s.label)}">${esc(s.label)}</span>
          <span class="badge ${n ? '' : 'zero'}">${n}</span></button>`;
      }).join('')).join('');

    listEl.querySelectorAll('[data-pick]').forEach((b) => {
      b.onclick = () => {
        const go = () => { selected = b.dataset.pick; drawList(); drawDetail(); };
        if (!dirty) { go(); return; }
        confirmDialog(w('discard_title'), w('discard_confirm'), go, w('discard_yes'), { tone: 'warn' });
      };
    });
  };

  const drawDetail = () => {
    const box = host.querySelector('#ht-detail');
    const screen = screens.find((s) => s.key === selected);
    if (!screen) {
      box.innerHTML = emptyState('screens', w('no_screen_title'), w('no_screen_body'));
      return;
    }
    draft = JSON.parse(JSON.stringify(links[screen.key] || []));
    dirty = false;

    box.innerHTML = `
      <div class="head" style="align-items:flex-start">
        <div>
          <h2 style="display:flex;gap:9px;align-items:center">${icon('help', 18)} ${esc(screen.label)}</h2>
          <p class="small muted" style="margin:2px 0 0">
            <code>${esc(screen.key)}</code>${screen.route ? ` · ${esc(screen.route)}` : ''}</p>
        </div>
      </div>
      <div id="ht-rows"></div>
      <div class="row between" style="margin-top:16px">
        <button class="small" id="ht-add" type="button">${icon('plus', 14)} ${w('add_link')}</button>
        <button class="primary" id="ht-save" type="button">${icon('save')} ${w('save_links')}</button>
      </div>
      <p class="small muted" style="margin-top:12px">${w('live_note')}</p>`;

    const rows = box.querySelector('#ht-rows');

    const drawRows = () => {
      rows.innerHTML = draft.length ? draft.map((l, i) => `
        <div class="linkrow ${l.active === false ? 'off' : ''}">
          <label class="check" title="${esc(w('live_tip'))}">
            <input type="checkbox" data-i="${i}" data-f="active" ${l.active !== false ? 'checked' : ''}/></label>
          <div class="stack2">
            <input data-i="${i}" data-f="label" value="${esc(l.label || '')}" placeholder="${esc(w('label_placeholder'))}"/>
            <input data-i="${i}" data-f="url" value="${esc(l.url || '')}" placeholder="https://…"/>
          </div>
          <div class="kind"><span data-typeicon="${i}">${typeIcon(l.type)}</span>
            <select data-i="${i}" data-f="type" aria-label="${esc(w('type_label'))}">
              <option value="" ${l.type ? '' : 'selected'}>${w('type_auto')}</option>
              ${TYPES().map((t) => `<option ${l.type === t ? 'selected' : ''}>${t}</option>`).join('')}</select></div>
          <button class="small danger icon" data-drop="${i}" type="button" title="${esc(w('remove'))}">${icon('close', 15)}</button>
          ${l.manual_id ? `<p class="from">${w('from_manual')}</p>` : ''}
        </div>`).join('')
        : emptyState('links', w('nothing_title'),
            w('nothing_body'));

      rows.querySelectorAll('[data-i]').forEach((inp) => {
        inp.oninput = inp.onchange = () => {
          const row = draft[Number(inp.dataset.i)];
          row[inp.dataset.f] = inp.type === 'checkbox' ? inp.checked : inp.value;
          dirty = true;
          const card = inp.closest('.linkrow');
          if (inp.dataset.f === 'active') card.classList.toggle('off', !inp.checked);
          // The glyph follows the type as you change it — and follows the ADDRESS while the type is
          // still "auto", which is how the server will read it.
          const guess = row.type || guessType(row.url);
          card.querySelector('[data-typeicon]').innerHTML = typeIcon(guess);
        };
      });
      rows.querySelectorAll('[data-drop]').forEach((b) => {
        b.onclick = () => confirmDialog(w('row_remove_title'), w('row_remove_body'), () => { draft.splice(Number(b.dataset.drop), 1); dirty = true; drawRows(); }, w('remove'), { tone: 'danger' });
      });
    };
    drawRows();

    box.querySelector('#ht-add').onclick = () => {
      draft.push({ label: '', url: '', type: '', active: true });
      dirty = true;
      drawRows();
      const last = rows.querySelector('tbody tr:last-child input[data-f="label"]');
      if (last) last.focus();
    };

    box.querySelector('#ht-save').onclick = (e) => busy(e.currentTarget, async () => {
      try {
        await api(`/api/projects/${p.id}/links/${encodeURIComponent(screen.key)}`, {
          method: 'PUT', body: { links: draft } });
        dirty = false;
        await loadProjects();
        toast(w('saved', { screen: screen.label }), 'ok');
        howtoPage(host);
      } catch (err) { toast(err.message, 'bad', 7); }
    });
  };

  q.oninput = drawList;
  only.onchange = drawList;
  drawList();
  drawDetail();
}
