// Ops & Chips Builder (OCB) — this portal's library of decisions.
//
// Left pane: Chips · Ops · Scenarios, a search box and a status filter. Right pane: the selected item.
//   * A CHIP opens as collapsible sections — About, Knobs, Logic, Tests, Check, Used by, History, More
//     fields — edited on a local working copy and sent through draft → review → live. Every field of
//     the chip's JSON has a typed editor (the two-way rule): there is no raw-JSON box anywhere.
//   * An OP is Python and cannot be rewritten from a screen. The owner can switch it off with a note;
//     "Make a chip from this op" is the builder's "new op" — a chip over the op, with its knobs.
//   * A SCENARIO is a named set of facts that Try and the tests run on.
// Who may do what is the server's answer (`me.can` in the catalog, `can` per item, both from the
// `builder.can` chip) — this page only shows the buttons that answer allows.
import { esc, toast, pageHead, modal, confirmDialog, busy, say, hooks, t, loadWords, when } from './ui.js';
import { icon } from './icons.js';
import {
  loadBuilderCss, h, valueEditor, exprEditor, paramsEditor, testsEditor, checkPanel, statusTag, historyList,
  B, chipCache, short, nodeKind, TYPES, builderWords,
} from './builder-ui.js';

// Every word on this screen is chip ui.ocb (core/words.py) - none is written here. The shared editors'
// words are chip ui.builder. (`w` is the working copy of a chip or scenario below, so this is `tw`.)
const tw = (k, v) => t('ocb', k, v);

let cssLoaded = false;
function loadCss() {
  if (cssLoaded) return;
  cssLoaded = true;
  const link = document.createElement('link');
  link.rel = 'stylesheet';
  link.href = new URL('./page-ocb.css', import.meta.url).href;
  document.head.appendChild(link);
}

// --- page state (kept between visits, like the other master/detail screens) ------------------------

const S = {
  cat: null,
  tab: 'chips',            // chips | ops | scenarios
  term: '',
  filter: 'all',           // all | live | drafts | off
  sel: null,               // {type: 'chip'|'op'|'scenario', id, isNew?, from?}
  trail: [],               // where "Back" goes after drilling into a nested chip or op
  open: {},                // which sections are open, by key
  tryScenario: '',
  scans: {},               // "who uses this" results, until the next reload
  jump: '',                // a section to open and scroll to after the next draw
};
const CLOSED = new Set(['used', 'history', 'extra', 'scextra', 'scused']);
let host = null;
let E = null;              // the open editor: {dirty()}
let loadToken = 0;
let lastSelKey = '';
let chipDetail = chipCache();
let uid = 0;

// The id rules come from the server (engine.ID_RE, chip builder.settings), never repeated here.
const ID_RE = { test: (v) => new RegExp((S.cat && S.cat.rules_ui && S.cat.rules_ui.chip_id_pattern) || '(?!)').test(v) };
const SCEN_RE = { test: (v) => new RegExp((S.cat && S.cat.rules_ui && S.cat.rules_ui.scenario_id_pattern) || '(?!)').test(v) };
const KNOWN = new Set(['chip_id', 'kind', 'set', 'audience', 'label', 'aliases', 'params', 'expr', 'returns',
  'description_nl', 'test_cases', 'status', 'version', 'updated_by', 'updated_at']);
const SOURCE = () => ({ core: tw('src_core'), portal: tw('src_portal'), data: tw('src_data') });
const TAB_OF = { chip: 'chips', op: 'ops', scenario: 'scenarios' };

const clone = (v) => (v === undefined ? undefined : JSON.parse(JSON.stringify(v)));
/** JSON with object keys sorted, so "changed?" does not depend on key order. */
const stable = (v) => JSON.stringify(v === undefined ? null : v, (k, x) => (x && typeof x === 'object' && !Array.isArray(x)
  ? Object.fromEntries(Object.keys(x).sort().map((kk) => [kk, x[kk]])) : x));
const tidy = (item) => { const c = clone(item || {}); delete c.source; return c; };   // `source` is added by the server on read
const ico = (name, size = 14) => h('span.ocb-ico', { html: icon(name, size) });
const selKey = (s) => (s ? `${s.type}:${s.isNew ? 'new' : s.id}` : '');
const ready = (c) => !!c && !(c.problems || []).length && (c.tests || []).length > 0 && c.tests.every((t) => t.ok);
const noop = () => {};

/** api() turns a structured error body into "[object Object]"; say something a person can act on. */
function errText(e) {
  const m = e && e.message;
  return !m || m === '[object Object]' ? tw('server_refused') : m;
}
/** Run an async action from a button: spinner while it works, a toast if it fails. */
function run(btn, fn) {
  return busy(btn, async () => {
    try { await fn(); } catch (e) { toast(errText(e), 'bad'); }
  });
}
function fire(fn) {
  return Promise.resolve().then(fn).catch((e) => toast(errText(e), 'bad'));
}
/** The catalog's `me.can` is asked for someone else's work (own = false), so an author's "may I start
 *  my OWN chip" is not in it. Anyone who may submit or make scenarios may start one; the server still
 *  decides on save. */
const mayCreate = () => { const c = S.cat.me.can || {}; return !!(c.draft || c.submit || c.scenario); };

function field(label, control, hint) {
  if (!control.id) control.id = `ocb-f${++uid}`;
  return h('div.field', {}, h('label', { for: control.id }, label), control, hint ? h('span.small', {}, hint) : null);
}
function noteNode(kind, text) {
  return h(`div.note.${kind}`, {}, h('span.ocb-ico', { html: icon(kind === 'ok' ? 'check' : kind === 'info' ? 'info' : 'alert') }), h('div', {}, text));
}
function emptyNode(iconName, title, line) {
  return h('div.empty', { html: `${icon(iconName, 36)}<h3>${esc(title)}</h3><p>${esc(line)}</p>` });
}
/** Walks a node for the chips and ops it names (the same reading as engine.refs). */
function refsOf(node, f = { chips: new Set(), vops: new Set() }) {
  if (Array.isArray(node)) node.forEach((x) => refsOf(x, f));
  else if (node && typeof node === 'object') {
    if (typeof node.chip === 'string') f.chips.add(node.chip);
    if (typeof node.vop === 'string' && node.vop !== 'choose') f.vops.add(node.vop);
    Object.values(node).forEach((x) => refsOf(x, f));
  }
  return f;
}

// --- the page ------------------------------------------------------------------------------------

export async function ocbPage(el) {
  host = el;
  hooks.isDirty = () => !!(E && E.dirty());   // the shell asks before a menu click or Back loses edits
  loadCss();
  loadBuilderCss();
  await loadWords('ocb');
  await builderWords();
  try {
    S.cat = await B.catalog();
  } catch (e) {
    host.innerHTML = `${pageHead(tw('title'), tw('lede'))}`;
    host.append(noteNode('bad', errText(e)));
    return;
  }
  chipDetail = chipCache();
  S.scans = {};
  validateSel();
  lastSelKey = '';
  host.innerHTML = `${pageHead(tw('title'), tw('lede'))}
    <datalist id="xb-chip-list"></datalist><datalist id="ocb-sets"></datalist><datalist id="ocb-returns"></datalist>
    <div class="panes ocb">
      <section class="pane" aria-label="${esc(tw('list_pane'))}"><div class="top ocb-top" id="ocb-top"></div>
        <div class="scrollbody"><div class="list" id="ocb-list"></div></div></section>
      <section class="pane" aria-label="${esc(tw('detail_pane'))}"><div class="scrollbody pad ocb-detail" id="ocb-detail"></div></section>
    </div>`;
  fillDatalists();
  drawTop();
  drawList();
  drawDetail();
}

async function reloadAll() {
  S.cat = await B.catalog();
  chipDetail = chipCache();
  S.scans = {};
  if (!host || !host.isConnected) return;
  validateSel();
  fillDatalists();
  drawTop();
  drawList();
  await drawDetail();
}

function validateSel() {
  if (!S.sel || S.sel.isNew) return;
  const { type, id } = S.sel;
  const found = type === 'chip' ? S.cat.chips.some((c) => c.id === id)
    : type === 'op' ? S.cat.ops.some((o) => o.op === id)
      : S.cat.scenarios.some((s) => s.scenario_id === id);
  if (!found) { S.sel = null; S.trail = []; }
}

/** The shared expression editor looks for a datalist of chip ids by this id. Kept OUTSIDE the parts
 *  that redraw, so it never disappears when an editor is rebuilt. */
function fillDatalists() {
  const fill = (id, rows) => {
    const dl = host.querySelector(`#${id}`);
    if (dl) dl.replaceChildren(...rows.map(([v, l]) => h('option', { value: v }, l || '')));
  };
  fill('xb-chip-list', S.cat.chips.map((c) => [c.id, c.label]));
  fill('ocb-sets', [...new Set(S.cat.chips.map((c) => c.set).filter(Boolean))].sort().map((s) => [s]));
  fill('ocb-returns', [...new Set([...TYPES, 'boolean', ...S.cat.chips.map((c) => c.returns).filter(Boolean)])].sort().map((s) => [s]));
}

// --- navigation ------------------------------------------------------------------------------------

function guard(fn) {
  if (E && E.dirty()) {
    confirmDialog(tw('leave_title'), tw('leave_body'),
      fn, tw('leave_yes'), { tone: 'warn' });
  } else fn();
}

function switchTab(sel) {
  const t = TAB_OF[sel.type];
  if (t && t !== S.tab) { S.tab = t; drawTop(); }
}

function go(sel, { push = false } = {}) {
  if (selKey(sel) === selKey(S.sel)) return;
  guard(() => {
    if (push && S.sel) S.trail.push(S.sel);
    else S.trail = [];
    S.sel = sel;
    switchTab(sel);
    drawList();
    drawDetail();
  });
}

function back() {
  guard(() => {
    S.sel = S.trail.pop() || null;
    if (S.sel) switchTab(S.sel);
    validateSel();
    drawList();
    drawDetail();
  });
}

/** After creating something: open it, no questions (its content is already saved). */
async function openNew(sel) {
  S.trail = [];
  S.sel = sel;
  switchTab(sel);
  await reloadAll();
}

function backBtn() {
  const prev = S.trail[S.trail.length - 1];
  if (!prev) return null;
  const name = prev.type === 'chip' ? prev.id : `${prev.type} ${prev.id}`;
  return h('button.link.small.ocb-back', { type: 'button', on: { click: back } }, ico('left', 13), tw('back_to', { name }));
}

// --- left pane -------------------------------------------------------------------------------------

function chipCounts() {
  const c = S.cat.chips;
  return {
    all: c.length,
    live: c.filter((x) => x.status === 'published').length,
    drafts: c.filter((x) => x.draft).length,
    review: c.filter((x) => x.draft && x.draft.status === 'review').length,
    off: c.filter((x) => x.status === 'inactive').length,
  };
}

function drawTop() {
  const top = host.querySelector('#ocb-top');
  if (!top) return;
  const c = S.cat;
  const n = chipCounts();
  const tabs = [['chips', tw('tab_chips'), c.chips.length], ['ops', tw('tab_ops'), c.ops.length], ['scenarios', tw('tab_scenarios'), c.scenarios.length]];
  const placeholder = { chips: tw('find_chips'), ops: tw('find_ops'), scenarios: tw('find_scenarios') }[S.tab];
  const newBtn = S.tab === 'chips' && mayCreate()
    ? `<button type="button" class="small primary" id="ocb-new">${icon('plus', 14)} ${tw('new_chip')}</button>`
    : S.tab === 'scenarios' && c.me.can.scenario
      ? `<button type="button" class="small primary" id="ocb-new">${icon('plus', 14)} ${tw('new_scenario')}</button>` : '';
  const filters = [['all', tw('f_all'), n.all], ['live', tw('f_live'), n.live], ['drafts', tw('f_drafts'), n.drafts], ['off', tw('f_off'), n.off]];
  top.innerHTML = `
    <div class="tabs many" role="tablist" aria-label="${esc(tw('list_aria'))}">
      ${tabs.map(([k, l, count]) => `<button type="button" role="tab" data-tab="${k}" aria-selected="${S.tab === k}" class="${S.tab === k ? 'on' : ''}">
        ${esc(l)} <span class="ocb-n">${count}</span>${k === 'chips' && n.review ? `<span class="badge" title="${esc(tw(n.review === 1 ? 'review_waiting_one' : 'review_waiting_many', { n: n.review }))}">${n.review}</span>` : ''}</button>`).join('')}
    </div>
    <div class="ocb-find"><span class="finder">${icon('search', 15)}<input id="ocb-q" type="search" aria-label="${esc(placeholder)}" placeholder="${esc(placeholder)}" value="${esc(S.term)}" autocomplete="off"/></span>${newBtn}</div>
    ${S.tab === 'chips' ? `<div class="ocb-filters" role="group" aria-label="${esc(tw('show_chips'))}">${filters.map(([k, l, count]) =>
    `<button type="button" data-filter="${k}" aria-pressed="${S.filter === k}">${esc(l)} <span class="ocb-n">${count}</span></button>`).join('')}</div>` : ''}`;
  top.querySelectorAll('[data-tab]').forEach((b) => {
    b.onclick = () => {
      if (S.tab === b.dataset.tab) return;
      S.tab = b.dataset.tab;
      drawTop();
      drawList();
      top.querySelector(`[data-tab="${S.tab}"]`)?.focus();
    };
  });
  top.querySelectorAll('[data-filter]').forEach((b) => {
    b.onclick = () => {
      S.filter = b.dataset.filter;
      top.querySelectorAll('[data-filter]').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
      drawList();
    };
  });
  top.querySelector('#ocb-q').oninput = (e) => { S.term = e.target.value; drawList(); };
  const nb = top.querySelector('#ocb-new');
  if (nb) nb.onclick = () => (S.tab === 'chips' ? guard(newChip) : guard(() => { S.trail = []; S.sel = { type: 'scenario', isNew: true }; drawList(); drawDetail(); }));
}

function drawList() {
  const list = host.querySelector('#ocb-list');
  if (!list) return;
  const q = S.term.trim().toLowerCase();
  const hit = (s) => !q || s.toLowerCase().includes(q);
  const cur = selKey(S.sel);
  const on = (key) => (cur === key ? 'class="on" aria-current="true"' : '');
  let html = '';
  let none = '';
  if (S.tab === 'chips') {
    const rows = S.cat.chips
      .filter((c) => hit(`${c.id} ${c.label || ''} ${c.set || ''} ${c.kind || ''} ${c.returns || ''} ${c.draft ? c.draft.author || '' : ''}`))
      .filter((c) => S.filter === 'all' || (S.filter === 'live' && c.status === 'published')
        || (S.filter === 'drafts' && c.draft) || (S.filter === 'off' && c.status === 'inactive'));
    const sets = [...new Set(rows.map((c) => c.set || ''))].sort();
    html = sets.map((s) => {
      const inSet = rows.filter((c) => (c.set || '') === s);
      return `<div class="grp">${esc(s || tw('no_set'))} · ${inSet.length}</div>${inSet.map((c) => `
        <button type="button" data-type="chip" data-id="${esc(c.id)}" ${on(`chip:${c.id}`)} title="${esc(c.id)}">
          <span class="ocb-li"><span class="nm">${esc(c.label || c.id)}</span><code class="ocb-id">${esc(c.id)}</code></span>
          <span class="ocb-tags">${statusTag(c)}</span></button>`).join('')}`;
    }).join('');
    none = tw(S.cat.chips.length ? 'no_chip_match' : 'no_chips');
  } else if (S.tab === 'ops') {
    const rows = S.cat.ops.filter((o) => hit(`${o.op} ${o.doc || ''} ${(o.params || []).join(' ')}`));
    const groups = [[tw('grp_off'), rows.filter((o) => o.inactive)], [tw('tab_ops'), rows.filter((o) => !o.inactive)]];
    html = groups.filter(([, r]) => r.length).map(([g, r]) => `<div class="grp">${esc(g)} · ${r.length}</div>${r.map((o) => `
      <button type="button" data-type="op" data-id="${esc(o.op)}" ${on(`op:${o.op}`)} title="${esc(o.doc || o.op)}">
        <span class="ocb-li"><code class="nm ocb-id">${esc(o.op)}</code><span class="ocb-doc-line">${esc(o.doc || '')}</span></span>
        <span class="badge ${o.used_by ? '' : 'zero'}" title="${esc(tw((o.used_by || 0) === 1 ? 'op_used_one' : 'op_used_many', { n: o.used_by || 0 }))}">${o.used_by || 0}</span></button>`).join('')}`).join('');
    none = tw('no_op_match');
  } else {
    const rows = S.cat.scenarios.filter((s) => hit(`${s.scenario_id} ${s.label || ''} ${s.subject || ''}`));
    const subjLabel = (name) => (S.cat.subjects.find((x) => x.name === name) || {}).label || name || tw('no_subject');
    const subjects = [...new Set(rows.map((s) => s.subject || ''))].sort();
    html = (cur === 'scenario:new' ? `<button type="button" class="on" aria-current="true" disabled><span class="ocb-li"><span class="nm">${tw('new_scenario')}</span><code class="ocb-id">${tw('not_saved')}</code></span></button>` : '')
      + subjects.map((sub) => {
        const r = rows.filter((s) => (s.subject || '') === sub);
        return `<div class="grp">${esc(subjLabel(sub))} · ${r.length}</div>${r.map((s) => `
          <button type="button" data-type="scenario" data-id="${esc(s.scenario_id)}" ${on(`scenario:${s.scenario_id}`)} title="${esc(s.scenario_id)}">
            <span class="ocb-li"><span class="nm">${esc(s.label || s.scenario_id)}</span><code class="ocb-id">${esc(s.scenario_id)}</code></span>
            ${s.source === 'data' ? `<span class="tag brand">${tw('edited_here')}</span>` : ''}
            <span class="badge" title="${esc(tw(Object.keys(s.facts || {}).length === 1 ? 'facts_one' : 'facts_many', { n: Object.keys(s.facts || {}).length }))}">${Object.keys(s.facts || {}).length}</span></button>`).join('')}`;
      }).join('');
    none = tw(S.cat.scenarios.length ? 'no_scen_match' : 'no_scens');
  }
  list.innerHTML = html || `<div class="none">${esc(none)}</div>`;
  list.querySelectorAll('[data-type]').forEach((b) => { b.onclick = () => go({ type: b.dataset.type, id: b.dataset.id }); });
  // Keep the selected row in view inside the list only — never scroll the page itself.
  const onEl = list.querySelector('.on');
  const sc = list.parentElement;
  if (onEl && sc) {
    const r = onEl.getBoundingClientRect();
    const box = sc.getBoundingClientRect();
    if (r.top < box.top) sc.scrollTop -= box.top - r.top + 8;
    else if (r.bottom > box.bottom) sc.scrollTop += r.bottom - box.bottom + 8;
  }
}

// --- right pane ----------------------------------------------------------------------------------

async function drawDetail() {
  const box = host && host.querySelector('#ocb-detail');
  if (!box) return;
  const token = ++loadToken;
  E = null;
  const key = selKey(S.sel);
  const same = key === lastSelKey;
  const keep = same ? box.scrollTop : 0;
  lastSelKey = key;
  try {
    if (!S.sel) drawOverview(box);
    else if (S.sel.type === 'chip') {
      if (!same) box.replaceChildren(h('div.empty', { html: `<p>${tw('loading_chip')}</p>` }));
      const d = await B.get('chips', S.sel.id);
      if (token !== loadToken) return;
      renderChip(box, S.sel.id, d, token);
    } else if (S.sel.type === 'op') drawOp(box, S.sel.id);
    else drawScenario(box, S.sel, token);
  } catch (e) {
    if (token !== loadToken) return;
    box.replaceChildren(noteNode('bad', errText(e)));
  }
  if (token === loadToken) {
    box.scrollTop = keep;
    if (S.jump && E && E.kit) { E.kit.open(S.jump); }
    S.jump = '';
  }
}

/** Collapsible sections that redraw one at a time, keeping the focus where the person left it. */
function sectionKit() {
  const all = {};
  const pending = new Set();
  let timer = 0;
  const add = (key, title, build, { hint = '', badge } = {}) => {
    const body = h('div.ocb-secbody');
    const badgeEl = h('span.ocb-secbadge');
    const isOpen = key in S.open ? S.open[key] : !CLOSED.has(key);
    const el = h('details.ocb-sec', { open: isOpen || undefined, 'data-sec': key },
      h('summary', {}, h('span.ocb-sectitle', {}, title), hint ? h('span.ocb-sechint', {}, hint) : null, badgeEl), body);
    el.addEventListener('toggle', () => { S.open[key] = el.open; });
    const drawBadge = () => { if (badge) badgeEl.innerHTML = badge() || ''; };
    const redraw = () => {
      const focusables = () => [...body.querySelectorAll('input,select,textarea,button')];
      const idx = body.contains(document.activeElement) ? focusables().indexOf(document.activeElement) : -1;
      body.replaceChildren(...[build()].flat(9).filter((x) => x instanceof Node));
      drawBadge();
      if (idx >= 0) { const t = focusables()[idx]; if (t) t.focus({ preventScroll: true }); }
    };
    redraw();
    all[key] = { el, redraw, badge: drawBadge };
    return el;
  };
  // A change is recorded at once; the editors redraw a tick later, after the focus has moved on.
  const later = (keys) => {
    keys.forEach((k) => pending.add(k));
    if (!timer) {
      timer = setTimeout(() => {
        timer = 0;
        const ks = [...pending];
        pending.clear();
        ks.forEach((k) => all[k] && all[k].redraw());
      }, 0);
    }
  };
  const open = (key) => {
    const s = all[key];
    if (!s) return;
    s.el.open = true;
    S.open[key] = true;
    s.el.scrollIntoView({ block: 'start', behavior: 'smooth' });
  };
  return { add, later, all, open };
}

function drawOverview(box) {
  const c = S.cat;
  const n = chipCounts();
  const opsOff = c.ops.filter((o) => o.inactive).length;
  const stat = (v, l) => `<div class="stat"><b>${v}</b><span>${esc(l)}</span></div>`;
  const queue = (title, rows, line) => (rows.length ? h('div.ocb-queue', {}, h('h3', {}, title),
    rows.map((x) => h('button', { type: 'button', on: { click: () => go({ type: 'chip', id: x.id }) } },
      h('span.ocb-li', {}, h('span.nm', {}, x.label || x.id), h('code.ocb-id', {}, `${x.id} · ${line(x)}`)),
      h('span.ocb-tags', { html: statusTag(x) })))) : null);
  box.replaceChildren(h('div.ocb-over', {},
    h('div.stats', { html: stat(n.live, tw('st_live')) + stat(n.review, tw('st_review')) + stat(n.drafts - n.review, tw('st_drafts'))
      + stat(n.off, tw('st_off')) + stat(c.ops.length - opsOff, opsOff ? tw('st_ops_on_off', { off: opsOff }) : tw('st_ops_on')) + stat(c.scenarios.length, tw('st_scenarios')) }),
    queue(tw('q_review'), c.chips.filter((x) => x.draft && x.draft.status === 'review'), (x) => tw('q_sent_by', { who: x.draft.author || tw('someone'), at: when(x.draft.at) })),
    queue(tw('q_drafts'), c.chips.filter((x) => x.draft && x.draft.status !== 'review'), (x) => tw('q_by', { who: x.draft.author || tw('someone'), at: when(x.draft.at) })),
    emptyNode('chip', tw('pick_title'), tw('pick_line'))));
}

// --- a chip ----------------------------------------------------------------------------------------

function renderChip(box, id, d, token) {
  const me = S.cat.me;
  const can = d.can || {};
  const editable = !!can.draft;
  const meta = (d.draft && d.draft.meta) || {};
  const ownDraft = !!d.draft && meta.author_id === me.id;
  const usages = d.usages || { chips: [], rules: [] };
  const base = d.draft ? clone(d.draft.item) : tidy(d.live);   // only a live read carries the added `source`
  const baseStr = stable(base);
  let w = clone(base);
  let check = d.check;
  const dirty = () => stable(w) !== baseStr;
  const kit = sectionKit();
  E = { dirty, kit };
  const alive = () => token === loadToken && box.isConnected;
  const ro = (node) => (editable ? node : h('fieldset.ocb-ro', { disabled: true }, node));

  // ---- header ----
  const titleEl = h('span', {}, w.label || id);
  const dot = h('span.ocb-dot', { title: tw('unsaved'), role: 'img', 'aria-label': tw('unsaved') });
  dot.hidden = !dirty();
  const readyEl = h('span.ocb-ready', { 'aria-live': 'polite' });
  const drawReady = () => {
    if (!check) { readyEl.innerHTML = ''; return; }
    const tests = check.tests || [];
    const passed = tests.filter((t) => t.ok).length;
    readyEl.innerHTML = ready(check) ? `<span class="tag ok">${tw('ready_tag')}</span>`
      : `<span class="tag warn">${tw((check.problems || []).length === 1 ? 'ready_warn_one' : 'ready_warn_many', { n: (check.problems || []).length, passed, total: tests.length })}</span>`;
  };
  const tagsEl = h('span.ocb-tags');
  const drawTags = () => {
    tagsEl.innerHTML = statusTag({ status: d.live ? d.live.status : 'unpublished', draft: d.draft ? { status: meta.status } : null })
      + (d.framework ? `<span class="tag brand">${tw('tag_framework')}</span>` : '')
      + `<span class="tag">${tw(w.kind === 'accessor' ? 'gives_value' : 'yes_no')}</span>`;
  };
  const bits = [d.live ? tw('live_version', { v: d.live.version ?? 1 }) : tw('never_published')];
  if (d.live && SOURCE()[d.live.source]) bits.push(SOURCE()[d.live.source]);
  if (d.live && d.live.updated_by) bits.push(tw('published_by', { by: d.live.updated_by, at: when(d.live.updated_at) }));
  if (d.draft) {
    bits.push(tw(meta.status === 'review' ? 'bit_review' : 'bit_draft', { who: meta.author_email || tw('someone'), at: when(meta.at) })
      + (meta.last_by && meta.last_by !== meta.author_email ? ` ${tw('last_edit', { who: meta.last_by })}` : ''));
  }
  bits.push(usages.chips.length || usages.rules.length
    ? tw('used_by_line', {
      chips: tw(usages.chips.length === 1 ? 'n_chip_one' : 'n_chip_many', { n: usages.chips.length }),
      rules: tw(usages.rules.length === 1 ? 'n_rule_one' : 'n_rule_many', { n: usages.rules.length }),
    }) : tw('nothing_uses'));

  const notes = [];
  if (d.draft && meta.returned_by && meta.note) notes.push(['warn', tw('sent_back_note', { who: meta.returned_by, note: meta.note })]);
  else if (d.draft && meta.note) notes.push(['info', meta.note]);
  if (!editable) {
    notes.push(['info', d.framework ? tw('ro_framework')
      : d.draft && !ownDraft ? tw('ro_other_draft', { who: meta.author_email || tw('someone_else') })
        : tw('ro_chip')]);
  }
  if (editable && (usages.chips.length || usages.rules.length)) {
    notes.push(['info', tw('reaches', { list: `${[...usages.chips, ...usages.rules].slice(0, 6).join(', ')}${usages.chips.length + usages.rules.length > 6 ? '…' : ''}` })]);
  }

  // ---- actions ----
  const acts = h('div.ocb-acts', { role: 'toolbar', 'aria-label': tw('acts_chip') });
  const saveIfNeeded = async () => (dirty() || !d.draft ? (await B.draft('chips', id, w)).check : null);
  const saveAct = async () => {
    await B.draft('chips', id, w);
    toast(tw('draft_saved'));
    await reloadAll();
  };
  const checkAct = async () => {
    const c = await B.check('chips', w);
    if (!alive()) return;
    check = c;
    kit.all.check.redraw();
    kit.all.tests.badge();
    drawReady();
    kit.open('check');
    toast(tw(ready(c) ? 'ready_toast' : 'not_ready_toast'), ready(c) ? 'ok' : 'warn');
  };
  const submitAct = async () => {
    await saveIfNeeded();
    await B.submit('chips', id);
    toast(tw('sent_review'));
    await reloadAll();
  };
  const notReady = async () => {
    S.open.check = true;
    S.jump = 'check';
    await reloadAll();
    toast(tw('not_published'), 'bad');
  };
  const publishAct = async () => {
    const saved = await saveIfNeeded();
    const c = saved || await B.check('chips', w);
    if (!ready(c)) { await notReady(); return; }
    let r;
    try {
      r = await B.publish('chips', id);
    } catch (e) {
      if (errText(e) !== e.message) { await notReady(); return; }   // the 422 with its check attached
      throw e;
    }
    toast(tw('published', { id, v: (r && r.item && r.item.version) || '' }));
    await reloadAll();
  };
  const returnAct = () => modal(tw('return_title'),
    `<p class="small muted">${tw('return_lede')}</p>
     <div class="field"><label for="ocb-rnote">${esc(tw('return_note_label', { who: meta.author_email || tw('the_author') }))}</label>
       <textarea id="ocb-rnote" rows="4" maxlength="1000" placeholder="${esc(tw('return_ph'))}"></textarea></div>`, {
    eyebrow: id,
    footer: `<button type="button" data-no>${tw('cancel')}</button><button type="button" class="primary" data-yes>${icon('send', 15)} ${tw('send_back')}</button>`,
    onOpen: (body, close) => {
      const card = body.closest('.modal');
      card.querySelector('[data-no]').onclick = () => close();
      const yes = card.querySelector('[data-yes]');
      yes.onclick = () => run(yes, async () => {
        const note = body.querySelector('#ocb-rnote').value.trim();
        if (!note) { toast(tw('note_first'), 'warn'); return; }
        await B.sendBack('chips', id, note);
        close();
        toast(tw('sent_back'));
        await reloadAll();
      });
      body.querySelector('#ocb-rnote').focus();
    },
  });
  const discardAct = () => confirmDialog(tw('discard_title'),
    `${tw(dirty() ? 'discard_body_dirty' : 'discard_body', { id })} ${tw(d.live ? 'discard_live' : 'discard_never')}`,
    () => fire(async () => { await B.discard('chips', id); toast(tw('discarded')); await reloadAll(); }), tw('discard_draft'), { tone: 'danger' });
  const offAct = () => {
    const chipStatus = (cid) => (S.cat.chips.find((x) => x.id === cid) || {}).status;
    const ruleStatus = (rid) => (S.cat.rules.find((x) => x.id === rid) || {}).status;
    const liveChips = usages.chips.filter((cid) => chipStatus(cid) !== 'inactive');
    const liveRules = usages.rules.filter((rid) => ruleStatus(rid) === 'published');
    if (liveChips.length || liveRules.length) {
      modal(tw('off_first_title'), '', {
        eyebrow: tw('off_first_eyebrow'),
        onOpen: (body, close) => body.append(
          h('p', {}, tw('off_first_body', { id })),
          h('div.ocb-pills', {},
            liveChips.map((cid) => h('button.ocb-pill', { type: 'button', on: { click: () => { close(); go({ type: 'chip', id: cid }, { push: true }); } } }, ico('chip', 13), cid)),
            liveRules.map((rid) => h('span.ocb-pill.static', {}, ico('shield', 13), rid)))),
      });
      return;
    }
    confirmDialog(tw('off_title'), tw('off_body', { id }),
      () => fire(async () => { await B.status('chips', id, 'inactive'); toast(tw('off_done', { id })); await reloadAll(); }), tw('switch_off'), { tone: 'warn' });
  };
  const onAct = async () => { await B.status('chips', id, 'published'); toast(tw('on_done', { id })); await reloadAll(); };
  const deleteAct = () => confirmDialog(tw('delete_title'),
    tw('delete_body', { id }),
    () => fire(async () => { await B.remove('chips', id); toast(tw('deleted', { id })); await reloadAll(); }), tw('delete_yes'), { tone: 'danger' });
  const copyAct = () => chipIdModal({
    title: tw('copy_title'), eyebrow: id,
    lede: tw('copy_lede'),
    id: `${id}_copy`, label: tw('copy_of', { name: w.label || id }),
    submit: async (nid, label) => {
      const copy = clone(w);
      ['status', 'version', 'updated_by', 'updated_at'].forEach((k) => delete copy[k]);
      copy.chip_id = nid;
      copy.label = label || copy.label;
      copy.set = nid.split('.')[0];
      if (copy.audience === 'admin' && me.role !== 'owner') delete copy.audience;
      await B.draft('chips', nid, copy);
      toast(tw('draft_made', { id: nid }));
      await openNew({ type: 'chip', id: nid });
    },
  });

  const drawActs = () => {
    const isDirty = dirty();
    const st = meta.status;
    const btns = [];
    const add = (label, iconName, fn, { primary = false, danger = false, disabled = false, title } = {}) => {
      // 2026-10-02 sweep: Save / Delete were greyed - a button is never greyed; one that cannot act now says why (its title)
      const b = h(`button.small${primary ? '.primary' : ''}${danger ? '.danger' : ''}`, { type: 'button', title },
        ico(iconName), label);
      b.addEventListener('click', () => (disabled ? toast(title || tw('nothing_changed'), 'info') : run(b, fn)));
      btns.push(b);
    };
    if (editable) add(tw('save_draft'), 'save', saveAct, { primary: isDirty, disabled: !isDirty, title: isDirty ? undefined : tw('nothing_changed') });
    if (can.test) add(tw('check'), 'check', checkAct);
    if (editable && can.submit && ((d.draft && st !== 'review') || isDirty)) add(tw('submit'), 'send', submitAct);
    if (editable && can.publish && (d.draft || isDirty)) add(tw('publish'), 'upload', publishAct, { primary: !isDirty });
    if (can.return && d.draft && st === 'review') add(tw('return_btn'), 'left', returnAct);
    if (d.draft && (ownDraft || can.publish)) add(tw('discard_draft'), 'trash', discardAct, { danger: true });
    if (d.live && can.deactivate) {
      if (d.live.status === 'inactive') add(tw('switch_on'), 'pulse', onAct);
      else add(tw('switch_off'), 'ban', offAct);
    }
    if (mayCreate()) add(tw('copy_btn'), 'plus', copyAct);
    if (d.live && d.live.source === 'data' && !d.shipped && can.delete) {
      const used = usages.chips.length + usages.rules.length > 0;
      add(tw('delete'), 'trash', deleteAct, { danger: true, disabled: used, title: used ? tw('delete_used_tip') : undefined });
    }
    acts.replaceChildren(...btns);
  };

  // ---- editing ----
  let checkTimer = 0;
  let checkN = 0;
  const scheduleCheck = () => {
    if (!can.test) return;
    clearTimeout(checkTimer);
    readyEl.innerHTML = `<span class="tag">${tw('checking')}</span>`;
    checkTimer = setTimeout(async () => {
      const n = ++checkN;
      try {
        const c = await B.check('chips', w);
        if (n !== checkN || !alive()) return;
        check = c;
        kit.all.check.redraw();
        kit.all.tests.badge();
        drawReady();
      } catch (e) {
        if (alive()) readyEl.innerHTML = `<span class="tag bad" title="${esc(errText(e))}">${tw('check_failed')}</span>`;
      }
    }, 600);
  };
  let wasDirty = dirty();
  const markChanged = (keys = []) => {
    kit.later(keys);
    const now = dirty();
    dot.hidden = !now;
    titleEl.textContent = w.label || id;
    drawTags();
    if (now !== wasDirty) { wasDirty = now; drawActs(); }
    scheduleCheck();
  };
  const set = (patch, keys = []) => { w = { ...w, ...patch }; markChanged(keys); };

  const aboutBuild = () => {
    const label = h('input', { value: w.label || '', placeholder: tw('label_ph'), on: { input: (e) => set({ label: e.target.value }) } });
    const setIn = h('input', { value: w.set || '', list: 'ocb-sets', placeholder: tw('set_ph'), autocomplete: 'off', on: { input: (e) => set({ set: e.target.value.trim() }) } });
    const kind = h('select', { on: { change: (e) => set({ kind: e.target.value }, ['logic', 'tests']) } },
      [['predicate', tw('kind_pred')], ['accessor', tw('kind_acc')]].map(([v, l]) => h('option', { value: v, selected: w.kind === v }, l)));
    const returns = h('input', { value: w.returns || '', list: 'ocb-returns', placeholder: tw('returns_ph'), autocomplete: 'off', on: { input: (e) => set({ returns: e.target.value.trim() }) } });
    const aud = h('select', { on: { change: (e) => set({ audience: e.target.value || undefined }) } },
      h('option', { value: '', selected: !w.audience }, tw('aud_all')),
      h('option', { value: 'admin', selected: w.audience === 'admin', disabled: me.role !== 'owner' && w.audience !== 'admin' }, tw('aud_admin')),
      w.audience && w.audience !== 'admin' ? h('option', { value: w.audience, selected: true }, w.audience) : null);
    const desc = h('textarea', { rows: 4, placeholder: tw('desc_ph'), on: { input: (e) => set({ description_nl: e.target.value }) } });
    desc.value = w.description_nl || '';
    return ro(h('div', {},
      h('div.grid.two.ocb-grid', {},
        field(tw('f_label'), label),
        field(tw('f_set'), setIn, tw('set_hint')),
        field(tw('f_answers'), kind),
        field(tw('f_returns'), returns),
        field(tw('f_who'), aud, me.role === 'owner' ? '' : tw('who_hint'))),
      h('div.field', {}, h('div.ocb-label', {}, tw('aliases_label')),
        valueEditor(w.aliases || [], (nv) => set({ aliases: nv }, ['about']), { type: 'list', lockType: true })),
      field(tw('f_desc'), desc, tw('desc_hint'))));
  };

  const knobsBuild = () => ro(paramsEditor(w.params || [], (np) => set({ params: np }, ['knobs', 'logic', 'tests'])));

  const tryNode = (node, as) => {
    const scen = S.cat.scenarios.find((s) => s.scenario_id === S.tryScenario);
    const facts = (scen && scen.facts) || {};
    // As a real run: the scenario's facts first, a knob's default only where the scenario says nothing.
    const args = Object.fromEntries((w.params || []).filter((p) => !(p.name in facts)).map((p) => [p.name, p.default]));
    return B.evalNode(node, as, S.tryScenario || undefined, args, [w]).catch((e) => ({ error: errText(e) }));
  };
  const ctx = {
    catalog: S.cat,
    names: () => (w.params || []).map((p) => ({ name: p.name, label: p.label, from: tw('knob') })),
    chipDetail: (cid) => chipDetail(cid),
    tryNode: can.test ? tryNode : undefined,
  };
  const logicBuild = () => {
    const pred = w.kind === 'predicate';
    const testShaped = ['test', 'chip', 'ref'].includes(nodeKind(w.expr));
    const parts = [];
    if (can.test) {
      parts.push(h('div.ocb-try', {}, h('span.ocb-label', {}, tw('try_on')),
        h('select', { 'aria-label': tw('try_aria'), on: { change: (e) => { S.tryScenario = e.target.value; } } },
          h('option', { value: '' }, tw('try_none')),
          S.cat.scenarios.map((s) => h('option', { value: s.scenario_id, selected: s.scenario_id === S.tryScenario }, `${s.label || s.scenario_id} (${s.scenario_id})`)))));
    }
    if (pred && w.expr !== undefined && !testShaped) {
      parts.push(noteNode('warn', tw('pred_value_warn')));
    }
    const shown = w.expr === undefined ? (pred ? { op: 'eq', left: '', right: '' } : '') : w.expr;
    if (editable) {
      parts.push(exprEditor(shown, (nx) => set({ expr: nx }, ['logic', 'used']), ctx, { asTest: pred && ['test', 'chip', 'ref'].includes(nodeKind(shown)) }));
    } else {
      parts.push(h('fieldset.ocb-ro', { disabled: true }, exprEditor(shown, noop, { ...ctx, tryNode: undefined }, { asTest: pred && testShaped })));
      if (can.test) {
        const out = h('span.small.ocb-tryout', { 'aria-live': 'polite' });
        const b = h('button.small', { type: 'button' }, ico('play'), tw('try_btn'));
        b.addEventListener('click', () => busy(b, async () => {
          const r = await tryNode(shown, pred ? 'test' : 'value');
          out.classList.toggle('bad-ink', !!r.error);
          out.textContent = r.error || `= ${short(r.result, 160)}`;
        }));
        parts.push(h('div.ocb-try', {}, b, out));
      }
    }
    return parts;
  };

  const testsBuild = () => ro(testsEditor(w.test_cases || [], (nt) => set({ test_cases: nt }, ['tests']), {
    mode: w.kind === 'accessor' ? 'accessor' : 'predicate', scenarios: S.cat.scenarios, argNames: (w.params || []).map((p) => p.name),
  }));
  const testsBadge = () => {
    const n = (w.test_cases || []).length;
    const res = (check && check.tests) || [];
    if (!n) return `<span class="tag warn">${tw('none_yet')}</span>`;
    const passed = res.filter((t) => t.ok).length;
    return `<span class="tag ${res.length && passed === res.length ? 'ok' : 'warn'}">${tw('n_pass', { passed, n: res.length || n })}</span>`;
  };

  const checkBuild = () => [checkPanel(check),
    can.test ? h('p.small.muted', {}, tw('rechecked')) : null];
  const checkBadge = () => (check ? (ready(check) ? `<span class="tag ok">${tw('ready_short')}</span>`
    : `<span class="tag warn">${tw((check.problems || []).length === 1 ? 'n_problem_one' : 'n_problem_many', { n: (check.problems || []).length })}</span>`) : '');

  const usedBuild = () => {
    const r = refsOf(w.expr);
    const chipBtn = (cid) => h('button.ocb-pill', { type: 'button', title: tw('open_id', { id: cid }), on: { click: () => go({ type: 'chip', id: cid }, { push: true }) } }, ico('chip', 13), cid);
    const opBtn = (o) => h('button.ocb-pill', { type: 'button', title: tw('open_op', { id: o }), on: { click: () => go({ type: 'op', id: o }, { push: true }) } }, ico('setup', 13), o);
    const ruleTag = (rid) => {
      const ru = S.cat.rules.find((x) => x.id === rid);
      return h('span.ocb-pill.static', { title: ru ? ru.label || '' : '' }, ico('shield', 13), rid, ru && ru.status !== 'published' ? ` (${ru.status})` : '');
    };
    return [
      h('div.ocb-refs', {}, h('div.ocb-label', {}, tw('uses_label')),
        r.chips.size || r.vops.size ? h('div.ocb-pills', {}, [...r.chips].sort().map(chipBtn), [...r.vops].sort().map(opBtn))
          : h('p.small.muted', {}, tw('uses_none'))),
      h('div.ocb-refs', {}, h('div.ocb-label', {}, tw('used_by_label')),
        usages.chips.length || usages.rules.length ? h('div.ocb-pills', {}, usages.chips.map(chipBtn), usages.rules.map(ruleTag))
          : h('p.small.muted', {}, tw('used_none'))),
    ];
  };

  const viewVersion = (r) => fire(async () => {
    const n = r.n ?? Number(r.file);
    const v = await B.version('chips', id, n);
    modal(tw('version_title', { id, v: r.version ?? n }), '', {
      wide: true, eyebrow: `${r.action || tw('saved')} · ${r.by || ''} · ${when(r.at)}`,
      onOpen: (body) => body.append(chipReadOnly(v.item, w)),
    });
  });
  const restoreVersion = (r) => confirmDialog(tw('restore_title', { v: r.version ?? r.n }),
    `${tw('restore_body')}${d.draft ? ` ${tw('restore_replaces')}` : ''}${dirty() ? ` ${tw('restore_unsaved')}` : ''}`,
    () => fire(async () => { await B.restore('chips', id, r.n ?? Number(r.file)); toast(tw('restored', { v: r.version ?? r.n })); await reloadAll(); }),
    tw('restore_yes'), { tone: 'warn' });
  const historyBuild = () => historyList(d.history || [], viewVersion, restoreVersion, !!can.restore);

  const extras = () => Object.fromEntries(Object.entries(w).filter(([k]) => !KNOWN.has(k)));
  const extraBuild = () => [
    h('p.small.muted', {}, tw('extra_lede')),
    ro(valueEditor(extras(), (nv) => {
      const clash = Object.keys(nv).filter((k) => KNOWN.has(k));
      if (clash.length) toast(tw('extra_clash', { names: clash.join(', ') }), 'warn');
      w = { ...Object.fromEntries(Object.entries(w).filter(([k]) => KNOWN.has(k))), ...Object.fromEntries(Object.entries(nv).filter(([k]) => !KNOWN.has(k))) };
      markChanged(['extra']);
    }, { type: 'record', lockType: true })),
  ];

  // ---- assemble ----
  drawTags();
  const bar = h('div.ocb-bar', {}, backBtn(),
    h('div.ocb-titlerow', {}, h('h2.ocb-title', {}, titleEl, dot), readyEl),
    h('div.ocb-sub', {}, h('code.ocb-code', {}, id), tagsEl),
    h('p.ocb-meta', {}, bits.join(' · ')),
    acts);
  box.replaceChildren(bar, ...notes.map(([k, t]) => noteNode(k, t)),
    kit.add('about', tw('sec_about'), aboutBuild, { hint: tw('about_hint') }),
    kit.add('knobs', tw('sec_knobs'), knobsBuild, { hint: tw('knobs_hint'), badge: () => `<span class="badge ${(w.params || []).length ? '' : 'zero'}">${(w.params || []).length}</span>` }),
    kit.add('logic', tw('sec_logic'), logicBuild, { hint: tw('logic_hint') }),
    kit.add('tests', tw('sec_tests'), testsBuild, { hint: tw('tests_hint'), badge: testsBadge }),
    kit.add('check', tw('check'), checkBuild, { hint: tw('check_hint'), badge: checkBadge }),
    kit.add('used', tw('sec_used'), usedBuild, { hint: tw('used_hint'), badge: () => `<span class="badge ${usages.chips.length + usages.rules.length ? '' : 'zero'}">${usages.chips.length + usages.rules.length}</span>` }),
    kit.add('history', tw('sec_history'), historyBuild, { hint: tw('history_hint'), badge: () => `<span class="badge ${(d.history || []).length ? '' : 'zero'}">${(d.history || []).length}</span>` }),
    kit.add('extra', tw('sec_extra'), extraBuild, { hint: tw('extra_hint'), badge: () => `<span class="badge ${Object.keys(extras()).length ? '' : 'zero'}">${Object.keys(extras()).length}</span>` }));
  drawActs();
  drawReady();
}

/** A version from history, shown with the same editors, locked. */
function chipReadOnly(item, compareTo) {
  const it = clone(item || {});
  const ignore = new Set(['status', 'version', 'updated_by', 'updated_at']);
  const changed = compareTo
    ? [...new Set([...Object.keys(it), ...Object.keys(compareTo)])].filter((k) => !ignore.has(k) && stable(it[k]) !== stable(compareTo[k]))
    : [];
  const pred = it.kind === 'predicate';
  const extra = Object.fromEntries(Object.entries(it).filter(([k]) => !KNOWN.has(k)));
  const ctx = {
    catalog: S.cat,
    names: () => (it.params || []).map((p) => ({ name: p.name, label: p.label, from: tw('knob') })),
    chipDetail: (cid) => chipDetail(cid),
  };
  return h('div.ocb-version', {},
    compareTo ? noteNode(changed.length ? 'info' : 'ok', changed.length
      ? tw('ver_diff', { fields: changed.join(', ') }) : tw('ver_same')) : null,
    h('dl.ocb-dl', {}, [[tw('f_label'), it.label], [tw('f_set'), it.set], [tw('f_answers'), tw(pred ? 'ans_pred' : 'ans_acc')], [tw('f_returns'), it.returns],
      [tw('f_who'), tw(it.audience === 'admin' ? 'who_owner' : 'who_all')], [tw('other_names'), (it.aliases || []).join(', ')],
      [tw('f_desc'), it.description_nl]].map(([k, v]) => [h('dt', {}, k), h('dd', {}, v || '—')])),
    h('fieldset.ocb-ro', { disabled: true },
      h('h3.ocb-h3', {}, tw('knobs_n', { n: (it.params || []).length })), paramsEditor(it.params || [], noop, { hint: '' }),
      h('h3.ocb-h3', {}, tw('sec_logic')), exprEditor(it.expr ?? '', noop, ctx, { asTest: pred && ['test', 'chip', 'ref'].includes(nodeKind(it.expr)) }),
      h('h3.ocb-h3', {}, tw('tests_n', { n: (it.test_cases || []).length })),
      testsEditor(it.test_cases || [], noop, { mode: pred ? 'predicate' : 'accessor', scenarios: S.cat.scenarios, argNames: [] }),
      Object.keys(extra).length ? [h('h3.ocb-h3', {}, tw('sec_extra')), valueEditor(extra, noop, { type: 'record', lockType: true })] : null));
}

/** Ask for a new chip id (and name), then make the draft. */
function chipIdModal({ title, eyebrow = '', lede, id = '', label = '', withKind = false, submit }) {
  modal(title, `<p class="small muted">${esc(lede)}</p>
    <div class="field"><label for="ocb-nid">${tw('chip_id')}</label>
      <input id="ocb-nid" value="${esc(id)}" placeholder="${esc(tw('id_ph'))}" autocomplete="off" spellcheck="false"/>
      <span class="small">${tw('id_rule')}</span></div>
    <div class="field"><label for="ocb-nlabel">${tw('what_answers')}</label>
      <input id="ocb-nlabel" value="${esc(label)}" placeholder="${esc(tw('answers_ph'))}"/></div>
    ${withKind ? `<div class="field"><label for="ocb-nkind">${tw('f_answers')}</label><select id="ocb-nkind">
      <option value="predicate">${tw('kind_pred')}</option><option value="accessor">${tw('kind_acc')}</option></select></div>` : ''}
    <div id="ocb-nsay"></div>`, {
    eyebrow,
    footer: `<button type="button" data-no>${tw('cancel')}</button><button type="button" class="primary" data-yes>${icon('plus', 15)} ${tw('make_draft')}</button>`,
    onOpen: (body, close) => {
      const card = body.closest('.modal');
      const idEl = body.querySelector('#ocb-nid');
      const sayEl = body.querySelector('#ocb-nsay');
      const yes = card.querySelector('[data-yes]');
      card.querySelector('[data-no]').onclick = () => close();
      const make = () => busy(yes, async () => {
        const nid = idEl.value.trim();
        if (!ID_RE.test(nid)) { say(sayEl, 'bad', tw('bad_id')); return; }
        if (S.cat.chips.some((c) => c.id === nid)) { say(sayEl, 'bad', tw('id_exists')); return; }
        try {
          await submit(nid, body.querySelector('#ocb-nlabel').value.trim(), withKind ? body.querySelector('#ocb-nkind').value : undefined);
          close();
        } catch (e) {
          say(sayEl, 'bad', esc(errText(e)));
        }
      });
      yes.onclick = make;
      body.addEventListener('keydown', (e) => { if (e.key === 'Enter' && e.target.tagName === 'INPUT') { e.preventDefault(); make(); } });
      idEl.focus();
      idEl.select();
    },
  });
}

function newChip() {
  chipIdModal({
    title: tw('new_chip'), eyebrow: tw('title'), withKind: true,
    lede: tw('new_lede'),
    submit: async (nid, label, kind) => {
      const chip = {
        chip_id: nid, kind, set: nid.split('.')[0], label, aliases: [], params: [],
        expr: kind === 'predicate' ? { op: 'eq', left: '', right: '' } : '',
        returns: kind === 'predicate' ? 'boolean' : '', description_nl: '', test_cases: [],
      };
      await B.draft('chips', nid, chip);
      toast(tw('draft_made_private', { id: nid }));
      await openNew({ type: 'chip', id: nid });
    },
  });
}

// --- an op -----------------------------------------------------------------------------------------

function drawOp(box, name) {
  const op = S.cat.ops.find((o) => o.op === name);
  if (!op) { box.replaceChildren(emptyNode('help', tw('no_op_title'), tw('no_op_line'))); return; }
  const me = S.cat.me;
  const kit = sectionKit();
  let wi = !!op.inactive;
  let wn = op.note || '';
  const dirty = () => wi !== !!op.inactive || wn !== (op.note || '');
  E = { dirty, kit };
  const used = op.used_by || 0;

  const acts = h('div.ocb-acts', { role: 'toolbar', 'aria-label': tw('acts_op') });
  if (mayCreate()) {
    acts.append(h('button.small.primary', {
      type: 'button', title: op.inactive ? tw('op_off_tip') : undefined,
      on: { click: () => (op.inactive ? toast(tw('op_off_tip'), 'info') : guard(() => makeFromOp(op))) },
    }, ico('plus'), tw('make_from_op')));
  }
  const bar = h('div.ocb-bar', {}, backBtn(),
    h('div.ocb-titlerow', {}, h('h2.ocb-title', {}, h('code', {}, op.op)),
      h('span', { html: op.inactive ? `<span class="tag bad">${tw('tag_off')}</span>` : `<span class="tag ok">${tw('tag_on')}</span>` })),
    h('p.ocb-meta', {}, tw(used === 1 ? 'op_meta_one' : 'op_meta_many', { n: used })),
    acts);

  const aboutBuild = () => [
    h('p.ocb-doc', {}, op.doc || tw('no_doc')),
    h('div.ocb-refs', {}, h('div.ocb-label', {}, tw('takes')),
      (op.params || []).length ? h('div.ocb-pills', {}, op.params.map((p) => h('span.ocb-pill.static', {}, p)))
        : h('p.small.muted', {}, tw('nothing'))),
    h('p.small.muted', {}, tw('op_rewrite')),
  ];

  const saveOp = (btn) => {
    const doIt = () => run(btn, async () => {
      const r = await B.op(name, { inactive: wi, note: wn });
      op.inactive = !!r.inactive;
      op.note = r.note || '';
      const u = r.used_by || { chips: [], rules: [] };
      S.scans[`op:${name}`] = { chips: (u.chips || []).map((cid) => ({ id: cid, live: true })), rules: u.rules || [], rulesBlocked: false };
      toast(tw(r.inactive ? 'op_now_off' : 'op_now_on', { name }));
      drawList();
      drawDetail();
    });
    if (wi && !op.inactive && used) {
      confirmDialog(tw('op_off_title'),
        tw(used === 1 ? 'op_off_body_one' : 'op_off_body_many', { n: used }),
        doIt, tw('switch_off'), { tone: 'warn' });
    } else doIt();
  };
  const switchBuild = () => {
    if (!me.can.op_override) {
      return [op.inactive ? noteNode('warn', op.note ? tw('op_off_note', { note: op.note }) : tw('op_off_plain'))
        : h('p.small.muted', {}, tw('op_on_owner'))];
    }
    const chk = h('input', { type: 'checkbox', checked: wi, on: { change: (e) => { wi = e.target.checked; } } });
    const note = h('textarea', { rows: 3, maxlength: 500, placeholder: tw('op_note_ph'), on: { input: (e) => { wn = e.target.value; } } });
    note.value = wn;
    const save = h('button.small.primary', { type: 'button' }, ico('save'), tw('save'));
    save.addEventListener('click', () => saveOp(save));
    return [h('label.check', {}, chk, h('span', {}, tw('op_off_tip'))), field(tw('note'), note), h('div.row.end', {}, save)];
  };
  const usedBuild = () => scanView(`op:${name}`,
    (item) => refsOf(item.expr).vops.has(name),
    (rule) => refsOf(rule).vops.has(name),
    tw(used === 1 ? 'op_scan_lede_one' : 'op_scan_lede_many', { n: used }),
    () => kit.all.opused.redraw());

  box.replaceChildren(bar,
    kit.add('opabout', tw('sec_op_about'), aboutBuild),
    kit.add('opswitch', tw('sec_op_switch'), switchBuild, { hint: op.note || '' }),
    kit.add('opused', tw('sec_used'), usedBuild, { badge: () => `<span class="badge ${used ? '' : 'zero'}">${used}</span>` }));
}

function makeFromOp(op) {
  const params = op.params || [];
  chipIdModal({
    title: tw('make_from_op'), eyebrow: op.op,
    lede: tw('from_op_lede', { op: op.op }),
    id: `my.${op.op}`, label: op.doc || op.op,
    submit: async (nid, label) => {
      const chip = {
        chip_id: nid, kind: 'accessor', set: nid.split('.')[0], label: label || op.op, aliases: [],
        params: params.map((p) => ({ name: p, type: 'text', label: '', default: '' })),
        expr: { vop: op.op, ...Object.fromEntries(params.map((p) => [p, `$${p}`])) },
        returns: '', description_nl: op.doc || '', test_cases: [],
      };
      await B.draft('chips', nid, chip);
      toast(tw('draft_from_op', { id: nid, op: op.op }));
      await openNew({ type: 'chip', id: nid });
    },
  });
}

/** "Who uses this?" across every chip (live and draft) and rule, fetched on request. */
function scanView(key, chipTest, ruleTest, lede, redraw) {
  const s = S.scans[key];
  const out = [h('p.small.muted', {}, lede)];
  const progress = h('span.small.muted', { 'aria-live': 'polite' });
  const btn = h('button.small', { type: 'button' }, ico('search'), tw(s ? 'look_again' : 'find_them'));
  btn.addEventListener('click', () => busy(btn, async () => {
    try {
      await runScan(key, chipTest, ruleTest, (done, total) => { progress.textContent = tw('scan_progress', { done, total }); });
    } catch (e) { toast(errText(e), 'bad'); }
    redraw();
  }));
  if (s) {
    if (!s.chips.length && !s.rules.length) out.push(h('p.small', {}, tw('scan_none')));
    else {
      out.push(h('div.ocb-pills', {},
        s.chips.map((c) => h('button.ocb-pill', { type: 'button', title: tw('open_id', { id: c.id }), on: { click: () => go({ type: 'chip', id: c.id }, { push: true }) } },
          ico('chip', 13), c.id, c.live ? null : h('span.ocb-draft', {}, ` ${tw('draft_only')}`))),
        s.rules.map((rid) => h('span.ocb-pill.static', {}, ico('shield', 13), rid))));
    }
    if (s.rulesBlocked) out.push(h('p.small.muted', {}, tw('rules_blocked')));
  }
  out.push(h('div.row.tight', {}, btn, progress));
  return out;
}

async function runScan(key, chipTest, ruleTest, onProgress) {
  const ids = S.cat.chips.map((c) => c.id);
  const total = ids.length;
  let done = 0;
  const chips = [];
  const worker = async () => {
    while (ids.length) {
      const cid = ids.shift();
      try {
        const d = await B.get('chips', cid);
        const inLive = !!d.live && chipTest(d.live);
        const inDraft = !!d.draft && chipTest(d.draft.item);
        if (inLive || inDraft) chips.push({ id: cid, live: inLive });
      } catch { /* a chip this person may not open is skipped */ }
      done += 1;
      onProgress(done, total);
    }
  };
  await Promise.all(Array.from({ length: Math.min(6, total) }, worker));
  const rules = [];
  let rulesBlocked = false;
  for (const r of S.cat.rules) {
    try {
      const d = await B.get('rules', r.id);
      if ((d.live && ruleTest(d.live)) || (d.draft && ruleTest(d.draft.item))) rules.push(r.id);
    } catch { rulesBlocked = true; break; }
  }
  chips.sort((a, b) => a.id.localeCompare(b.id));
  S.scans[key] = { chips, rules, rulesBlocked };
}

// --- a scenario ------------------------------------------------------------------------------------

function drawScenario(box, sel) {
  const me = S.cat.me;
  const isNew = !!sel.isNew;
  const orig = isNew ? null : S.cat.scenarios.find((s) => s.scenario_id === sel.id);
  if (!isNew && !orig) { box.replaceChildren(emptyNode('help', tw('no_scen_title'), tw('no_scen_line'))); return; }
  const from = isNew && sel.from ? S.cat.scenarios.find((s) => s.scenario_id === sel.from) : null;
  const src = orig || from;
  const base = {
    scenario_id: isNew ? '' : orig.scenario_id,
    subject: src ? src.subject || '' : (S.cat.subjects[0] || {}).name || '',
    label: src ? (from ? tw('copy_of', { name: src.label || src.scenario_id }) : src.label || '') : '',
    facts: clone(src ? src.facts || {} : {}),
  };
  let w = clone(base);
  const baseStr = stable(base);
  const dirty = () => stable(w) !== baseStr;
  const kit = sectionKit();
  E = { dirty, kit };
  const editable = !!me.can.scenario;
  const ro = (node) => (editable ? node : h('fieldset.ocb-ro', { disabled: true }, node));
  const subj = () => S.cat.subjects.find((s) => s.name === w.subject);
  const nameOf = () => w.label || w.scenario_id || tw('new_scenario');

  const titleEl = h('span', {}, nameOf());
  const dot = h('span.ocb-dot', { title: tw('unsaved'), role: 'img', 'aria-label': tw('unsaved') });
  dot.hidden = !dirty();
  const acts = h('div.ocb-acts', { role: 'toolbar', 'aria-label': tw('acts_scen') });

  const saveAct = async () => {
    const sid = (w.scenario_id || '').trim();
    if (!SCEN_RE.test(sid)) { toast(tw('scen_bad_id'), 'bad'); return; }
    if (isNew && S.cat.scenarios.some((s) => s.scenario_id === sid)) { toast(tw('scen_exists'), 'bad'); return; }
    if (!w.subject) { toast(tw('scen_pick_subject'), 'bad'); return; }
    await B.scenario(sid, { subject: w.subject, label: w.label || sid, facts: w.facts });
    toast(tw('scen_saved'));
    S.trail = [];
    S.sel = { type: 'scenario', id: sid };
    await reloadAll();
  };
  const deleteAct = () => confirmDialog(tw('scen_delete_title'),
    tw('scen_delete_body', { id: orig.scenario_id }),
    () => fire(async () => { await B.dropScenario(orig.scenario_id); toast(tw('scen_deleted')); await reloadAll(); }), tw('scen_delete_yes'), { tone: 'danger' });
  const drawActs = () => {
    const btns = [];
    if (editable) {
      const b = h(`button.small${dirty() || isNew ? '.primary' : ''}`, { type: 'button' }, ico('save'), tw('save_scen'));
      b.addEventListener('click', () => (!dirty() && !isNew ? toast(tw('nothing_changed'), 'info') : run(b, saveAct)));
      btns.push(b);
      if (!isNew) btns.push(h('button.small', { type: 'button', on: { click: () => go({ type: 'scenario', isNew: true, from: orig.scenario_id }) } }, ico('plus'), tw('copy_scen')));
    }
    if (!isNew && orig.source === 'data' && me.can.publish) btns.push(h('button.small.danger', { type: 'button', on: { click: deleteAct } }, ico('trash'), tw('delete')));
    acts.replaceChildren(...btns);
  };
  let wasDirty = dirty();
  const markChanged = (keys = []) => {
    kit.later(keys);
    const now = dirty();
    dot.hidden = !now;
    titleEl.textContent = nameOf();
    if (now !== wasDirty) { wasDirty = now; drawActs(); }
  };
  const set = (patch, keys = []) => { w = { ...w, ...patch }; markChanged(keys); };
  const setFacts = (facts) => set({ facts }, ['scfacts', 'scextra']);

  const aboutBuild = () => {
    const idIn = isNew
      ? h('input', { value: w.scenario_id, placeholder: tw('scen_id_ph'), autocomplete: 'off', spellcheck: 'false', on: { input: (e) => set({ scenario_id: e.target.value.trim() }) } })
      : h('input', { value: w.scenario_id, readonly: true });
    const subjSel = h('select', { on: { change: (e) => set({ subject: e.target.value }, ['scabout', 'scfacts', 'scextra']) } },
      subj() ? null : h('option', { value: w.subject, selected: true }, w.subject ? tw('subj_unknown', { name: w.subject }) : tw('pick_one')),
      S.cat.subjects.map((s) => h('option', { value: s.name, selected: s.name === w.subject }, s.label || s.name)));
    const label = h('input', { value: w.label, placeholder: tw('scen_label_ph'), on: { input: (e) => set({ label: e.target.value }) } });
    return ro(h('div.grid.two.ocb-grid', {},
      field(tw('f_id'), idIn, tw(isNew ? 'scen_id_hint' : 'scen_id_fixed')),
      field(tw('sec_about'), subjSel, (subj() || {}).doc || ''),
      field(tw('f_label'), label)));
  };
  const factsBuild = () => {
    const s = subj();
    if (!s) return h('p.small.muted', {}, tw('pick_subject_first'));
    return ro(h('div.ocb-facts', {}, (s.facts || []).map((f) => {
      const given = Object.prototype.hasOwnProperty.call(w.facts, f.name);
      const typed = TYPES.includes(f.type);
      const blank = { number: 0, text: '', boolean: false, list: [], record: {}, rows: [] }[f.type] ?? '';
      return h(`div.ocb-fact${given ? '' : '.unset'}`, {},
        h('div.ocb-factname', {}, h('b', {}, f.label || f.name), h('code', {}, `${f.name} · ${f.type || tw('any_type')}`)),
        given
          ? h('div.ocb-factval', {},
            valueEditor(w.facts[f.name], (nv) => setFacts({ ...w.facts, [f.name]: nv }), { type: typed ? f.type : undefined, lockType: typed }),
            h('button.link.small', { type: 'button', on: { click: () => { const c = { ...w.facts }; delete c[f.name]; setFacts(c); } } }, tw('leave_out_unknown')))
          : h('div.ocb-factval', {},
            h('span.small.muted', {}, tw('not_given')),
            h('button.link.small', { type: 'button', on: { click: () => setFacts({ ...w.facts, [f.name]: blank }) } }, tw('give', { name: f.name }))));
    })));
  };
  const known = () => new Set(((subj() || {}).facts || []).map((f) => f.name));
  const extraFacts = () => Object.fromEntries(Object.entries(w.facts).filter(([k]) => !known().has(k)));
  const extraBuild = () => [
    h('p.small.muted', {}, tw('more_facts_lede')),
    ro(valueEditor(extraFacts(), (nv) => {
      const k = known();
      setFacts({ ...Object.fromEntries(Object.entries(w.facts).filter(([n]) => k.has(n))), ...Object.fromEntries(Object.entries(nv).filter(([n]) => !k.has(n))) });
    }, { type: 'record', lockType: true })),
  ];

  const notes = [];
  if (!editable) notes.push(['info', tw('ro_scen')]);
  else if (!isNew && orig.source === 'shipped') notes.push(['info', tw('shipped_note')]);

  const bar = h('div.ocb-bar', {}, backBtn(),
    h('div.ocb-titlerow', {}, h('h2.ocb-title', {}, titleEl, dot)),
    h('div.ocb-sub', {}, isNew ? h('span.tag.warn', {}, tw('not_saved')) : h('code.ocb-code', {}, orig.scenario_id),
      !isNew ? h('span.tag', {}, tw(orig.source === 'data' ? 'edited_here' : 'ships_portal')) : null),
    h('p.ocb-meta', {}, isNew ? tw('scen_meta_new')
      : `${tw('about_subject', { name: (subj() || {}).label || orig.subject })}${orig.updated_by ? ` · ${tw('saved_by', { by: orig.updated_by, at: when(orig.updated_at) })}` : ''}`),
    acts);
  const sections = [
    kit.add('scabout', tw('sec_about'), aboutBuild),
    kit.add('scfacts', tw('sec_facts'), factsBuild, { hint: tw('facts_hint'), badge: () => `<span class="badge">${Object.keys(w.facts).length}</span>` }),
    kit.add('scextra', tw('sec_more_facts'), extraBuild, { badge: () => `<span class="badge ${Object.keys(extraFacts()).length ? '' : 'zero'}">${Object.keys(extraFacts()).length}</span>` }),
  ];
  if (!isNew) {
    const sid = orig.scenario_id;
    const usesIt = (item) => (item.test_cases || []).some((t) => t.scenario === sid);
    sections.push(kit.add('scused', tw('sec_used'), () => scanView(`scen:${sid}`, usesIt, usesIt,
      tw('scen_used_lede'), () => kit.all.scused.redraw())));
  }
  box.replaceChildren(bar, ...notes.map(([k, t]) => noteNode(k, t)), ...sections);
  drawActs();
}
