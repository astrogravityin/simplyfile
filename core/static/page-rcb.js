// Rule Chip Builder (RCB) — what the portal DOES when chips hold.
//
//   WHEN   a trigger fires            (Python registers triggers: server.sample, signup.submit, daily…)
//   GIVEN  the facts of its subject   (what the trigger hands over: rss_mb, domain, disk_free_mb…)
//   IF     its test holds             (chips and ops over the facts, the rule's knobs and named values)
//   THEN   outcomes                   (refuse · banner · email · value · flag — typed fields, never raw JSON)
//
// Master / detail: every rule on the left grouped by trigger, the chosen rule on the right as a vertical
// sentence of cards. Every key of a rule's JSON has a control here (the two-way rule); a key this screen
// has no dedicated place for is still shown and editable under "Other fields", and saved untouched.
// Drafts run only here, on scenarios, with no side effect.
import { esc, toast, busy, pageHead, modal, confirmDialog, hooks, t, loadWords, when } from './ui.js';
import { icon, spinner } from './icons.js';
import {
  loadBuilderCss, h, valueEditor, exprEditor, paramsEditor, testsEditor, checkPanel, statusTag, historyList,
  B, chipCache, short,
  builderWords,
} from './builder-ui.js';

// The id rule, tones and fallback words come from the server (chips rules.settings / rules.messages), never repeated here.
const serverUi = () => (cat && cat.rules_ui) || {};
const ID_RE = { test: (v) => new RegExp(serverUi().rule_id_pattern || '(?!)').test(v) };
const NAME_RE = /^[A-Za-z_][A-Za-z0-9_]*$/;
const TONES = { includes: (t) => (serverUi().tones || []).includes(t) };
// Every word on this screen is chip ui.rcb (core/words.py) - none is written here.
const wd = (k, v) => t('rcb', k, v);
const filters = () => [['all', wd('filter_all')], ['live', wd('filter_live')], ['draft', wd('filter_draft')], ['off', wd('filter_off')]];
// Keys with a dedicated control (or, for the server-written ones, a read-only line in the header).
const KNOWN = new Set(['rule_id', 'label', 'description', 'trigger', 'priority', 'stop', 'status', 'version', 'params',
  'values', 'when', 'then', 'test_cases', 'updated_by', 'updated_at']);
const sectionLabel = () => ({ about: wd('sec_about'), when: wd('sec_when'), knobs: wd('sec_knobs'), values: wd('sec_values'),
  if: wd('sec_if'), then: wd('sec_then'), dry: wd('sec_dry'), tests: wd('sec_tests'), check: wd('sec_check'),
  history: wd('sec_history'), other: wd('sec_other') });
const FOCUSABLE = 'input,select,textarea,button,summary,[tabindex]:not([tabindex="-1"])';
const sourceWord = () => ({ core: wd('source_core'), portal: wd('source_portal'), data: wd('source_data') });

const clone = (v) => (v === undefined ? undefined : JSON.parse(JSON.stringify(v)));
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const fmt = (at) => when(at);   // the time with its zone (core when)
const str = (v) => (typeof v === 'string' ? v : (v === undefined || v === null ? '' : short(v, 400)));

let cat = null;           // the builder catalog
let chipDetail = null;    // chip params for the expression editors, cached per visit
let root = null;          // the page host
let S = null;             // the rule on screen
let openSeq = 0;          // the latest openRule wins
const ui = { selected: '', filter: 'all', term: '' };

let cssLoaded = false;
function loadCss() {
  if (cssLoaded || document.querySelector('link[data-rcb-css]')) { cssLoaded = true; return; }
  cssLoaded = true;
  const link = document.createElement('link');
  link.rel = 'stylesheet';
  link.href = new URL('./page-rcb.css', import.meta.url).href;
  link.dataset.rcbCss = '';
  document.head.appendChild(link);
}

export async function rcbPage(host) {
  loadCss();
  loadBuilderCss();
  root = host;
  S = null;
  await Promise.all([loadWords('rcb'), builderWords()]);   // the shared editors read chip ui.builder
  cat = await B.catalog();
  chipDetail = chipCache();
  const canNew = !!cat.me.can.draft;
  host.innerHTML = `${pageHead(wd('title'), wd('lede'),
    canNew ? `<button type="button" class="primary" id="rcb-new">${icon('plus')} ${wd('new_rule')}</button>` : '')}
    <div class="panes rcb">
      <div class="pane rcb-master">
        <div class="top rcb-top">
          <span class="finder">${icon('search', 15)}<input id="rcb-find" placeholder="${esc(wd('find_placeholder'))}"
            aria-label="${esc(wd('find_label'))}" autocomplete="off" value="${esc(ui.term)}"/></span>
          <div class="tabs many rcb-filter" id="rcb-filter" role="group" aria-label="${esc(wd('filter_group'))}"></div>
        </div>
        <div class="scrollbody"><div class="list" id="rcb-list"></div></div>
      </div>
      <div class="pane rcb-pane"><div class="scrollbody pad rcb-detail" id="rcb-detail" aria-live="polite"></div></div>
    </div>`;
  // exprEditor puts the chip datalist inside the first editor that draws, and skips it while one exists;
  // a section redraw would then take it away from every editor. One page-level list survives redraws.
  document.getElementById('xb-chip-list')?.remove();
  host.append(h('datalist', { id: 'xb-chip-list' }, cat.chips.map((c) => h('option', { value: c.id }, c.label || c.id))));
  host.querySelector('#rcb-find').addEventListener('input', (e) => { ui.term = e.target.value; drawList(); });
  host.querySelector('#rcb-new')?.addEventListener('click', () => leaveThen(() => newRuleDialog()));
  host.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's' && S && document.querySelector('.backdrop') === null) {
      e.preventDefault();
      const a = document.activeElement;
      if (a && host.contains(a) && typeof a.blur === 'function') a.blur();   // let the field's change land first
      setTimeout(() => S?.headEl?.querySelector('[data-act="save"]:not([hidden])')?.click(), 0);
    }
  });
  hooks.isDirty = isDirty;   // the shell's leave guard (menu, Back, closing the tab) asks this page
  drawFilters();
  const first = cat.rules.some((r) => r.id === ui.selected) ? ui.selected : (cat.rules[0]?.id || '');
  drawList();
  if (first) await openRule(first);
  else drawEmpty();
}

// --- small helpers ------------------------------------------------------------------------------

const detailBox = () => root.querySelector('#rcb-detail');
const kindSpec = (name) => cat.kinds.find((k) => k.name === name) || null;
const kindLabel = (name) => kindSpec(name)?.label || name;
const scenarioById = (id) => cat.scenarios.find((s) => s.scenario_id === id) || null;
const trigOf = (rule) => cat.triggers.find((t) => t.name === rule?.trigger) || null;
const subjOf = (rule) => { const t = trigOf(rule); return t ? cat.subjects.find((s) => s.name === t.subject) || null : null; };
const trig = () => trigOf(S?.working);
const subj = () => subjOf(S?.working);
const isDirty = () => !!S && (S.isNew || !same(S.working, S.baseline));

// 2026-10-02 sweep: Move up / down were greyed at the ends of a list - a button is never greyed; at an end it says so
function iconBtn(name, label, atEnd, onClick) {
  return h('button.ghost.icon.small', { type: 'button', title: label, 'aria-label': label, html: icon(name, 15),
    on: { click: () => (atEnd ? toast(wd('move_edge'), 'info') : onClick()) } });
}

function stepHead(word, title, sub = '') {
  return h('header.rcb-step', {}, word ? h('span.rcb-word', {}, word) : '', h('h2', {}, title), sub ? h('p.small.muted', {}, sub) : '');
}

function noteEl(tone, iconName, ...kids) {
  return h(`div.note.${tone}`, {}, h('span', { html: icon(iconName) }), h('div', {}, ...kids));
}

function namesFor(rule, uptoValue = Infinity) {
  const facts = (subjOf(rule)?.facts || []).map((f) => ({ name: f.name, label: f.label || '', from: 'fact' }));
  const knobs = (rule.params || []).map((p) => ({ name: p.name, label: p.label || '', from: 'knob' }));
  const vals = Object.keys(rule.values || {}).slice(0, uptoValue).map((n) => ({ name: n, label: '', from: 'value' }));
  return [...facts, ...knobs, ...vals];
}
const names = (upto) => namesFor(S.working, upto);
const namesKey = () => JSON.stringify(names().map((n) => [n.name, n.from, n.label]));

function ctx(upto = Infinity) {
  return { catalog: cat, names: () => names(upto), chipDetail, tryNode: (node, as) => tryNode(node, as) };
}

function emptyFor(f) {
  return { number: 0, boolean: false, choice: (f.choices || [])[0] ?? '', text: '', longtext: '' }[f.type] ?? '';
}

function newOutcome(kind) {
  const o = { kind };
  (kindSpec(kind)?.fields || []).forEach((f) => { o[f.name] = f.default !== undefined ? clone(f.default) : emptyFor(f); });
  return o;
}

function switchKind(o, kind) {
  const n = newOutcome(kind);
  Object.keys(n).forEach((k) => { if (k !== 'kind' && k in o) n[k] = clone(o[k]); });
  return n;
}

function makeState(o) {
  return { scenario: '', extra: {}, dry: null, check: null, checking: false, checkError: '', checkTimer: 0, token: 0,
    sections: {}, sectionEls: {}, headEl: null, actions: [], ...o };
}

/** Keep the scenario if it is about this rule's subject; otherwise the first one that is. */
function pickScenario() {
  const s = subj();
  const cur = scenarioById(S.scenario);
  if (cur && (!s || cur.subject === s.name)) return;
  S.scenario = (s && cat.scenarios.find((x) => x.subject === s.name)?.scenario_id) || '';
}

function subjectScenarios(rule) {
  const s = subjOf(rule);
  const mine = cat.scenarios.filter((x) => !s || x.subject === s.name);
  const used = (rule.test_cases || []).map((c) => c.scenario).filter((id) => id && !mine.some((m) => m.scenario_id === id));
  return [...mine, ...used.map(scenarioById).filter(Boolean)];
}

/** A live rule as the server shows it carries `source` (where it lives) — not part of the rule file. */
function withoutSource(live) {
  const c = clone(live);
  if (c) delete c.source;
  return c;
}

// --- leaving with unsaved changes -------------------------------------------------------------------

function leaveThen(go) {
  if (!isDirty()) { go(); return; }
  confirmDialog(wd('leave_title'), wd('leave_body', { id: S.working.rule_id }),
    go, wd('leave_yes'), { tone: 'warn', eyebrow: wd('unsaved') });
}


// --- the list -----------------------------------------------------------------------------------

function inFilter(r, f) {
  return f === 'all' || (f === 'live' && r.status === 'published') || (f === 'off' && r.status === 'inactive')
    || (f === 'draft' && (!!r.draft || r.status === 'unpublished'));
}

function drawFilters() {
  const box = root.querySelector('#rcb-filter');
  box.innerHTML = filters().map(([k, label]) => `<button type="button" data-filter="${k}" class="${ui.filter === k ? 'on' : ''}"
    aria-pressed="${ui.filter === k}">${esc(label)} <span class="badge">${cat.rules.filter((r) => inFilter(r, k)).length}</span></button>`).join('');
  box.querySelectorAll('[data-filter]').forEach((b) => {
    b.onclick = () => { ui.filter = b.dataset.filter; drawFilters(); drawList(); };
  });
}

function drawList() {
  const box = root.querySelector('#rcb-list');
  if (!box) return;
  const term = ui.term.trim().toLowerCase();
  const rows = cat.rules.filter((r) => inFilter(r, ui.filter)
    && (!term || `${r.id} ${r.label || ''} ${r.trigger || ''} ${trigOf(r)?.label || ''}`.toLowerCase().includes(term)));
  const groups = new Map();
  rows.forEach((r) => {
    const g = trigOf(r)?.label || r.trigger || wd('no_trigger_group');
    if (!groups.has(g)) groups.set(g, []);
    groups.get(g).push(r);
  });
  let html = '';
  if (S?.isNew) {
    html += `<div class="grp">${esc(wd('not_saved_group'))}</div><button type="button" class="stack-row on" data-newrow aria-current="true">
      <span class="nm"><b>${esc(S.working.label || S.working.rule_id)}</b><span class="rcb-id">${esc(S.working.rule_id)}</span></span>
      <span class="rcb-tags"><span class="tag brand">${esc(wd('tag_new'))}</span></span></button>`;
  }
  html += [...groups.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([g, rs]) => `<div class="grp">${esc(g)}</div>`
    + rs.sort((a, b) => (Number(b.priority) || 0) - (Number(a.priority) || 0) || a.id.localeCompare(b.id)).map((r) => {
      const on = !S?.isNew && r.id === ui.selected;
      return `<button type="button" class="stack-row ${on ? 'on' : ''}" data-rule="${esc(r.id)}" ${on ? 'aria-current="true"' : ''}>
        <span class="nm"><b>${esc(r.label || r.id)}</b><span class="rcb-id">${esc(r.id)}</span></span>
        <span class="rcb-tags">${statusTag(r)}</span></button>`;
    }).join('')).join('');
  box.innerHTML = html || `<div class="none">${esc(wd('no_match'))}</div>`;
  box.querySelectorAll('[data-rule]').forEach((b) => {
    b.onclick = () => {
      const id = b.dataset.rule;
      if (!S?.isNew && id === S?.id) return;
      leaveThen(() => openRule(id));
    };
  });
}

function drawEmpty() {
  const box = detailBox();
  box.innerHTML = `<div class="empty">${icon('pulse', 40)}<h3>${wd(cat.rules.length ? 'pick_rule' : 'no_rules')}</h3>
    <p>${wd('empty_body')}</p>
    ${cat.me.can.draft ? `<button type="button" class="primary" data-new>${icon('plus')} ${wd('new_rule')}</button>` : ''}</div>`;
  box.querySelector('[data-new]')?.addEventListener('click', () => newRuleDialog());
}

// --- opening, reloading -------------------------------------------------------------------------

async function openRule(id, { keep = false } = {}) {
  const seq = ++openSeq;
  const prev = keep && S && S.id === id ? S : null;
  const box = detailBox();
  const top = prev ? box.scrollTop : 0;
  ui.selected = id;
  if (!prev) box.innerHTML = `<div class="empty">${spinner(22)}<p>${wd('loading', { id: esc(id) })}</p></div>`;
  let d;
  try {
    d = await B.get('rules', id);
  } catch (e) {
    if (seq !== openSeq) return;
    S = null;
    drawList();
    box.innerHTML = `<div class="note bad">${icon('alert')}<div>${esc(e.message)}</div></div>`;
    return;
  }
  if (seq !== openSeq) return;
  const item = d.draft ? d.draft.item : withoutSource(d.live);
  S = makeState({ id, isNew: false, detail: d, working: clone(item), baseline: clone(item), check: d.check,
    scenario: prev?.scenario || S?.scenario || '', extra: prev?.extra || {} });
  pickScenario();
  drawList();
  drawDetail();
  box.scrollTop = top;
}

/** After an action: fresh catalog, fresh rule. `keepEdits` carries unsaved edits over (switch on/off). */
async function reload(id, { keepEdits = false } = {}) {
  const edits = keepEdits && S && S.id === id && isDirty() ? S.working : null;
  try { cat = await B.catalog(); } catch (e) { toast(e.message, 'bad'); }
  drawFilters();
  if (!cat.rules.some((r) => r.id === id)) {
    S = null;
    ui.selected = cat.rules[0]?.id || '';
    drawList();
    if (ui.selected) await openRule(ui.selected);
    else drawEmpty();
    return;
  }
  await openRule(id, { keep: true });
  if (edits && S && S.id === id) {
    const top = detailBox().scrollTop;
    S.working = edits;
    drawDetail();
    detailBox().scrollTop = top;
    scheduleCheck();
  }
}

function startNew(rule) {
  ++openSeq;
  const scenario = S?.scenario || '';
  S = makeState({ id: rule.rule_id, isNew: true, detail: null, working: rule, baseline: null, check: null, scenario });
  pickScenario();
  drawList();
  drawDetail();
  detailBox().scrollTop = 0;
  scheduleCheck();
}

function blankRule(id, label, trigger) {
  return { rule_id: id, label, description: '', trigger, priority: 50, status: 'published', version: 0,
    params: [], values: {}, when: { op: 'eq', left: '', right: '' }, then: [], test_cases: [] };
}

function copyOf(rule, id, label) {
  const c = clone(rule);
  c.rule_id = id;
  c.label = label;
  if ('status' in c) c.status = 'published';
  if ('version' in c) c.version = 0;
  delete c.updated_by;
  delete c.updated_at;
  return c;
}

// --- editing ------------------------------------------------------------------------------------

/** Change the working copy, redraw the named sections (and whatever reads names, when names changed). */
function edit(mutate, redraw = []) {
  const before = namesKey();
  const next = clone(S.working);
  mutate(next);
  S.working = next;
  const keys = new Set(redraw);
  if (namesKey() !== before) ['values', 'if', 'then'].forEach((k) => keys.add(k));
  keys.forEach((k) => S.sections[k]?.());
  refreshHead();
  scheduleCheck();
}

function scheduleCheck() {
  if (!S || !cat.me.can.test) return;
  const mine = S;
  clearTimeout(mine.checkTimer);
  const tok = ++mine.token;
  if (!mine.checking) { mine.checking = true; mine.sections.check?.(); }
  mine.checkTimer = setTimeout(async () => {
    try {
      const r = await B.check('rules', mine.working);
      if (S !== mine || tok !== mine.token) return;
      mine.check = r;
      mine.checkError = '';
    } catch (e) {
      if (S !== mine || tok !== mine.token) return;
      mine.checkError = e.message;
    }
    mine.checking = false;
    mine.sections.check?.();
  }, 600);
}

/** Run a node on the chosen scenario with the rule's knobs and named values in play — the server's
 *  node evaluation reads only facts + args, so the knob defaults and the worked-out values go in as args. */
async function tryNode(node, as) {
  if (!S.scenario) return { error: wd('pick_scenario_if') };
  try {
    const knobs = Object.fromEntries((S.working.params || []).map((p) => [p.name, p.default]));
    let vals = {};
    if (Object.keys(S.working.values || {}).length) {
      const r = await B.evalRule({ ...S.working, when: null, then: [] }, S.scenario, S.extra);
      if (r.error) return { error: wd('value_fails', { error: r.error }) };
      vals = r.values || {};
    }
    const facts = scenarioById(S.scenario)?.facts || {};
    return await B.evalNode(node, as, S.scenario, { ...knobs, ...facts, ...S.extra, ...vals });
  } catch (e) {
    return { error: e.message };
  }
}

// --- the detail -----------------------------------------------------------------------------------

function drawDetail() {
  const box = detailBox();
  box.replaceChildren();
  S.sections = {};
  S.sectionEls = {};
  box.append(buildHead());
  const flow = h('div.rcb-flow');
  box.append(flow);
  mount(flow, 'about', buildAbout);
  mount(flow, 'when', buildWhen);
  mount(flow, 'knobs', buildKnobs);
  mount(flow, 'values', buildValues);
  mount(flow, 'if', buildIf);
  mount(flow, 'then', buildThen);
  mount(flow, 'dry', buildDry);
  mount(flow, 'tests', buildTests);
  mount(flow, 'check', buildCheck);
  if (!S.isNew) mount(flow, 'history', buildHistory);
  mount(flow, 'other', buildOther);
}

/** One card that redraws itself from S.working. The shared editors are rebuilt on every change, so the
 *  field that had the focus gets it back (or the next one, when the change came from pressing Tab). */
function mount(parent, key, build) {
  const el = h('section.card.rcb-card', { 'data-sec': key, 'aria-label': sectionLabel()[key] || key });
  let tab = null;
  el.addEventListener('keydown', (e) => { if (e.key === 'Tab') tab = { dir: e.shiftKey ? -1 : 1, at: Date.now() }; }, true);
  const focusables = () => [...el.querySelectorAll(FOCUSABLE)].filter((x) => !x.disabled);
  const draw = () => {
    const act = document.activeElement;
    const before = act && el.contains(act) ? focusables().indexOf(act) : -1;
    const kids = [build()].flat(9).filter((x) => x !== null && x !== undefined && x !== false && x !== '');
    el.replaceChildren(...kids);
    el.hidden = !kids.length;
    if (before < 0) return;
    const step = tab && Date.now() - tab.at < 400 ? tab.dir : 0;
    setTimeout(() => {
      const now = document.activeElement;
      if (now && now !== document.body && now.isConnected) return;
      const list = focusables();
      list[Math.max(0, Math.min(list.length - 1, before + step))]?.focus({ preventScroll: true });
    }, 0);
  };
  S.sections[key] = draw;
  S.sectionEls[key] = el;
  parent.append(el);
  draw();
}

// header: title, state, the actions this person may take on THIS rule

function buildHead() {
  const d = S.detail;
  const can = S.isNew ? cat.me.can : (d?.can || {});
  const live = d?.live || null;
  const draft = d?.draft || null;
  const meta = draft?.meta || {};
  const own = !!draft && meta.author_id === cat.me.id;
  const summary = S.isNew ? null : cat.rules.find((r) => r.id === S.id);
  const tagHtml = S.isNew ? `<span class="tag brand">${esc(wd('tag_new'))}</span>`
    : statusTag(summary || { status: live?.status || 'unpublished', draft: draft ? { status: meta.status } : null });

  const title = h('h2.rcb-title', {}, S.working.label || S.working.rule_id);
  const dirty = h('span.rcb-dirty', { hidden: !isDirty() }, wd('unsaved'));
  const lines = [];
  if (S.isNew) {
    lines.push(h('p.rcb-meta', {}, wd('not_saved_meta')));
  } else {
    const bits = [];
    if (live) {
      bits.push(wd('meta_live_version', { v: live.version ?? '—' }), sourceWord()[live.source] || live.source || '');
      if (live.updated_by) bits.push(wd('meta_published_by', { by: live.updated_by, at: fmt(live.updated_at) }));
    } else {
      bits.push(wd('meta_never_published'));
    }
    if (draft) {
      const inReview = meta.status === 'review';
      bits.push(wd(inReview ? 'meta_in_review' : 'meta_draft', { by: meta.author_email || wd('someone'), at: fmt(meta.at) }));
      if (meta.last_by && meta.last_by !== meta.author_email) bits.push(wd('meta_last_edit', { by: meta.last_by }));
    }
    lines.push(h('p.rcb-meta', {}, bits.filter(Boolean).join(' · ')));
    if (draft && meta.note) {
      lines.push(meta.returned_by
        ? noteEl('warn', 'alert', h('b', {}, wd('returned_by', { by: meta.returned_by })), ' ', h('span.rcb-pre', {}, meta.note))
        : noteEl('info', 'info', h('span.rcb-pre', {}, meta.note)));
    }
    if (live?.status === 'inactive') lines.push(noteEl('warn', 'ban', wd('switched_off_note')));
  }

  const specs = [
    ['save', 'save', wd('act_save'), 'primary', () => !!can.draft, onSave],
    ['check', 'check', wd('act_check'), '', () => !!can.test, onCheck],
    ['submit', 'send', wd('act_submit'), '', () => !!can.submit && (!!draft || isDirty()) && meta.status !== 'review', onSubmit],
    ['publish', 'upload', wd('act_publish'), '', () => !!can.publish && (!!draft || isDirty()), onPublish],
    ['return', 'left', wd('act_return'), '', () => !!can.return && !!draft && meta.status === 'review', onReturn, true],
    ['discard', 'close', wd('act_discard'), 'danger', () => !!draft && (own || !!can.publish), onDiscard, true],
    ['off', 'ban', wd('act_off'), '', () => !!live && live.status !== 'inactive' && !!can.deactivate, onSwitchOff, true],
    ['on', 'check', wd('act_on'), '', () => !!live && live.status === 'inactive' && !!can.deactivate, onSwitchOn],
    ['delete', 'trash', wd('act_delete'), 'danger', () => !!live && !!can.delete && live.source === 'data' && !d?.shipped, onDelete, true],
    ['copy', 'plus', wd('act_copy'), 'ghost', () => !S.isNew && !!cat.me.can.draft, onCopy, true],
    ['cancel', 'close', wd('act_cancel'), 'ghost', () => S.isNew, onCancelNew, true],
  ];
  S.actions = specs.map(([key, ico, label, cls, show, run, noBusy]) => {
    const el = h(`button.small${cls ? `.${cls}` : ''}`, { type: 'button', 'data-act': key, html: `${icon(ico, 14)} ${esc(label)}` });
    el.addEventListener('click', () => (noBusy ? run(el) : busy(el, () => run(el))));
    return { el, show };
  });
  const bar = h('div.rcb-actions', { role: 'toolbar', 'aria-label': wd('actions_label') }, S.actions.map((a) => a.el));
  S.headEl = h('div.rcb-head', {},
    h('div.rcb-titlerow', {}, title, h('code', {}, S.working.rule_id), h('span.rcb-tags', { html: tagHtml }), dirty),
    lines, bar);
  S.headEl.titleEl = title;
  S.headEl.dirtyEl = dirty;
  refreshHead();
  return S.headEl;
}

function refreshHead() {
  const head = S?.headEl;
  if (!head) return;
  head.titleEl.textContent = S.working.label || S.working.rule_id;
  head.dirtyEl.hidden = !isDirty();
  S.actions.forEach((a) => { a.el.hidden = !a.show(); });
  const save = head.querySelector('[data-act="save"]');
  if (save) save.classList.toggle('primary', isDirty() || S.isNew);
}

// about

function buildAbout() {
  const w = S.working;
  return [
    stepHead(wd('step_rule'), wd('sec_about')),
    h('div.rcb-about', {},
      h('div.field', {}, h('label', { for: 'rcb-label' }, wd('label_label')),
        h('input', { id: 'rcb-label', value: w.label || '', placeholder: wd('label_placeholder'),
          on: { change: (e) => edit((x) => { x.label = e.target.value; }) } })),
      h('div.field', {}, h('label', { for: 'rcb-desc' }, wd('desc_label')),
        h('textarea', { id: 'rcb-desc', rows: 3, value: w.description || '',
          placeholder: wd('desc_placeholder'),
          on: { change: (e) => edit((x) => { if (e.target.value || 'description' in x) x.description = e.target.value; }) } }))),
  ];
}

// WHEN + GIVEN

function buildWhen() {
  const t = trig();
  const s = subj();
  const sel = h('select', { id: 'rcb-trigger', on: { change: (e) => changeTrigger(e.target.value) } },
    t ? null : h('option', { value: S.working.trigger || '', selected: true },
      S.working.trigger ? wd('trigger_unregistered', { name: S.working.trigger }) : wd('pick_trigger_opt')),
    cat.triggers.map((x) => h('option', { value: x.name, selected: x.name === S.working.trigger }, `${x.label} — ${x.name}`)));
  return [
    stepHead(wd('step_when'), wd('when_title')),
    h('div.field', {}, h('label', { for: 'rcb-trigger' }, wd('trigger_label')), sel, t?.doc ? h('span.small', {}, t.doc) : ''),
    t ? h('p.small.muted', {}, wd('outcomes_here', { kinds: t.kinds.map(kindLabel).join(' · ') })) : '',
    h('div.rcb-sub', {},
      stepHead(wd('step_given'), s ? wd('given_title_of', { subject: `${s.label.charAt(0).toLowerCase()}${s.label.slice(1)}` }) : wd('given_title'),
        s?.doc || ''),
      s && s.facts.length
        ? h('div.rcb-facts', { role: 'list', 'aria-label': wd('facts_label') }, s.facts.map((f) => h('span.rcb-fact', { role: 'listitem' },
          h('code', {}, f.name), h('span', {}, f.label || ''), f.type ? h('span.rcb-ftype', {}, f.type) : '')))
        : h('p.small.muted', {}, wd(t ? 'no_facts' : 'pick_trigger_facts')),
      h('p.small.muted', { style: 'margin:10px 0 0' }, wd('read_fact_hint', { name: '{name}' }))),
  ];
}

function changeTrigger(name) {
  const nt = cat.triggers.find((t) => t.name === name);
  const bad = [...new Set((S.working.then || []).filter((o) => nt && !nt.kinds.includes(o.kind)).map((o) => kindLabel(o.kind)))];
  const apply = () => {
    edit((w) => { w.trigger = name; }, ['when', 'values', 'if', 'then', 'tests']);
    pickScenario();
    S.dry = null;
    S.sections.if?.();
    S.sections.dry?.();
    S.sections.tests?.();
  };
  if (!bad.length) { apply(); return; }
  S.sections.when?.();   // the select goes back until the answer is yes
  confirmDialog(wd('change_trigger_title'), wd('change_trigger_body', { trigger: nt.label, kinds: bad.join(', ') }),
    apply, wd('change_trigger_yes'), { tone: 'warn' });
}

// knobs

function buildKnobs() {
  return [
    stepHead(wd('sec_knobs'), wd('knobs_title'), wd('knobs_sub', { name: '{name}' })),
    paramsEditor(S.working.params || [], (v) => edit((w) => { w.params = v; }, ['knobs']),
      { hint: wd('knobs_hint') }),
  ];
}

// named values

function buildValues() {
  const entries = Object.entries(S.working.values || {});
  const setEntries = (list) => edit((w) => { w.values = Object.fromEntries(list); }, ['values']);
  const rename = (i, input) => {
    let v = input.value.trim().replace(/[^\w]/g, '_');
    if (/^\d/.test(v)) v = `v_${v}`;
    const old = entries[i][0];
    if (v === old) { input.value = old; return; }
    const clash = !NAME_RE.test(v) ? wd('name_rule')
      : entries.some(([n], j) => j !== i && n === v) ? wd('value_exists', { name: v })
        : names().some((n) => n.from !== 'value' && n.name === v) ? wd('name_taken', { name: v }) : '';
    if (clash) { toast(clash, 'warn'); input.value = old; return; }
    const list = clone(entries);
    list[i][0] = v;
    setEntries(list);
  };
  const move = (i, dir) => { const l = clone(entries); [l[i], l[i + dir]] = [l[i + dir], l[i]]; setEntries(l); };
  const add = () => {
    let k = entries.length + 1;
    while (entries.some(([n]) => n === `value${k}`) || names().some((n) => n.name === `value${k}`)) k += 1;
    setEntries([...clone(entries), [`value${k}`, '']]);
  };
  return [
    stepHead(wd('step_values'), wd('values_title'), wd('values_sub', { name: '{name}' })),
    entries.length
      ? h('div.rcb-values', {}, entries.map(([name, node], i) => h('div.rcb-value', {},
        h('div.rcb-value-head', {},
          h('span.rcb-dollar', { 'aria-hidden': 'true' }, '$'),
          h('input', { value: name, 'aria-label': wd('value_name_label', { n: i + 1 }), spellcheck: 'false', on: { change: (e) => rename(i, e.target) } }),
          h('span.spacer'),
          iconBtn('up', wd('move_up', { name }), i === 0, () => move(i, -1)),
          iconBtn('down', wd('move_down', { name }), i === entries.length - 1, () => move(i, 1)),
          iconBtn('trash', wd('remove_named', { name }), false, () => setEntries(clone(entries).filter((_, j) => j !== i)))),
        exprEditor(node, (nv) => { const l = clone(entries); l[i][1] = nv; setEntries(l); }, ctx(i)))))
      : h('p.small.muted', {}, wd('no_values')),
    h('div', { style: 'margin-top:10px' }, h('button.small', { type: 'button', html: `${icon('plus', 14)} ${esc(wd('add_value'))}`, on: { click: add } })),
  ];
}

// IF

function scenarioPicker(key) {
  const s = subj();
  const list = [...cat.scenarios].sort((a, b) => Number(!!s && b.subject === s.name) - Number(!!s && a.subject === s.name));
  const id = `rcb-scen-${key}`;
  return h('div.field.rcb-scen', {},
    h('label', { for: id }, wd('scenario_label')),
    h('select', { id, 'data-scen': '', on: { change: (e) => {
      S.scenario = e.target.value;
      detailBox().querySelectorAll('[data-scen]').forEach((x) => { x.value = S.scenario; });
    } } },
    h('option', { value: '', selected: !S.scenario }, wd(list.length ? 'pick_scenario_opt' : 'no_scenarios')),
    list.map((sc) => {
      const other = !!s && sc.subject !== s.name;
      return h('option', { value: sc.scenario_id, selected: sc.scenario_id === S.scenario, disabled: other },
        `${sc.label} — ${sc.scenario_id}${other ? wd('about_subject', { subject: sc.subject }) : ''}`);
    })),
    h('span.small', {}, s ? wd('scen_hint_of', { subject: `${s.label.charAt(0).toLowerCase()}${s.label.slice(1)}` })
      : wd('pick_trigger_first')));
}

function buildIf() {
  const when = S.working.when ?? { op: 'eq', left: '', right: '' };
  return [
    stepHead(wd('sec_if'), wd('if_title'), wd('if_sub')),
    scenarioPicker('if'),
    exprEditor(when, (nv) => edit((w) => { w.when = nv; }, ['if']), ctx(), { asTest: true }),
  ];
}

// THEN

function buildThen() {
  const t = trig();
  const list = S.working.then || [];
  const setList = (l) => edit((w) => { w.then = l; }, ['then']);
  const w = S.working;
  return [
    stepHead(wd('sec_then'), wd('then_title'), wd('then_sub')),
    h('p.small.muted.rcb-hint', { html: wd('then_hint', { fact: '{fact}', knob: '{knob}', rss_mb: '{rss_mb}' }) }),
    list.length
      ? h('div.rcb-outs', {}, list.map((o, i) => outcomeCard(o, i, list, setList, t)))
      : h('div.empty-box.small.muted', { style: 'margin:0 0 12px' }, wd('no_outcome')),
    t
      ? h('div.rcb-add', {}, h('span.small.muted', {}, wd('add_outcome')),
        t.kinds.map((k) => h('button.small', { type: 'button', html: `${icon('plus', 13)} ${esc(kindLabel(k))}`,
          title: kindSpec(k)?.doc || '', on: { click: () => setList([...clone(list), newOutcome(k)]) } })))
      : h('p.small.muted', {}, wd('pick_trigger_outcomes')),
    h('div.rcb-order', {},
      h('div.field', {}, h('label', { for: 'rcb-priority' }, wd('priority_label')),
        h('input', { id: 'rcb-priority', type: 'number', step: '1', value: w.priority ?? 0,
          on: { change: (e) => edit((x) => { x.priority = e.target.value === '' ? 0 : Number(e.target.value); }) } }),
        h('span.small', {}, wd('priority_hint'))),
      h('label.check', {},
        h('input', { type: 'checkbox', checked: !!w.stop, on: { change: (e) => edit((x) => {
          if (e.target.checked) x.stop = true;
          else if (S.baseline && 'stop' in S.baseline) x.stop = false;
          else delete x.stop;
        }) } }),
        h('span', {}, h('b', {}, wd('stop_label')),
          h('span.small.muted', {}, wd('stop_hint'))))),
  ];
}

function outcomeCard(o, i, list, setList, t) {
  const spec = kindSpec(o.kind);
  const put = (fn) => { const l = clone(list); fn(l); setList(l); };
  const known = new Set((spec?.fields || []).map((f) => f.name));
  const kindSel = h('select.rcb-kind', { 'aria-label': wd('outcome_kind_label', { n: i + 1 }),
    on: { change: (e) => put((l) => { l[i] = switchKind(o, e.target.value); }) } },
  spec ? null : h('option', { value: o.kind ?? '', selected: true }, wd('unknown_kind', { kind: o.kind ?? wd('no_kind') })),
  cat.kinds.map((k) => {
    const ok = !t || t.kinds.includes(k.name);
    return h('option', { value: k.name, selected: k.name === o.kind, disabled: !ok && k.name !== o.kind },
      `${k.label}${ok ? '' : wd('not_at_trigger')}`);
  }));
  const extra = Object.keys(o).filter((k) => k !== 'kind' && !known.has(k));
  const guess = (v) => (typeof v === 'number' ? 'number' : typeof v === 'boolean' ? 'boolean' : 'text');
  return h('div.rcb-out', {},
    h('div.rcb-out-head', {},
      h('span.rcb-out-n', { 'aria-hidden': 'true' }, String(i + 1)), kindSel, h('span.spacer'),
      iconBtn('up', wd('move_outcome_up', { n: i + 1 }), i === 0, () => put((l) => { [l[i - 1], l[i]] = [l[i], l[i - 1]]; })),
      iconBtn('down', wd('move_outcome_down', { n: i + 1 }), i === list.length - 1, () => put((l) => { [l[i + 1], l[i]] = [l[i], l[i + 1]]; })),
      iconBtn('trash', wd('remove_outcome', { n: i + 1 }), false, () => put((l) => { l.splice(i, 1); }))),
    spec?.doc ? h('p.small.muted.rcb-out-doc', {}, spec.doc) : '',
    t && !t.kinds.includes(o.kind)
      ? noteEl('warn', 'alert', wd('kind_not_here', { kind: kindLabel(o.kind), trigger: t.label })) : '',
    (spec?.fields || []).map((f) => fieldRow(f, o, i, put)),
    extra.map((k) => fieldRow({ name: k, label: k, type: guess(o[k]), extra: true }, o, i, put)));
}

function fieldRow(f, o, i, put) {
  const id = `rcb-o${i}-${f.name}`;
  const has = Object.prototype.hasOwnProperty.call(o, f.name);
  const v = o[f.name];
  const set = (nv) => put((l) => { l[i][f.name] = nv; });
  const drop = () => put((l) => { delete l[i][f.name]; });
  const isRef = typeof v === 'string' && v.startsWith('$');
  const isExpr = v !== null && typeof v === 'object';
  let ctl;
  if (isRef) ctl = refPick(v, set, id);
  else if (isExpr) ctl = exprEditor(v, set, ctx());
  else ctl = typedInput(f, v, has, set, drop, id);
  const ns = names();
  const firstKnob = (S.working.params || [])[0]?.name || ns[0]?.name;
  const acts = [];
  if (isRef || isExpr) {
    acts.push(h('button.link.small', { type: 'button',
      on: { click: () => set(f.default !== undefined ? clone(f.default) : emptyFor(f)) } }, wd('type_value')));
  } else {
    acts.push(h('button.link.small', { type: 'button', title: firstKnob ? '' : wd('add_knob_first'),
      on: { click: () => (firstKnob ? set(`$${firstKnob}`) : toast(wd('add_knob_first'), 'info')) } }, wd('use_knob')));
  }
  if (f.extra) {
    acts.push(h('span.muted', {}, '·'), h('button.link.small', { type: 'button', on: { click: drop } }, wd('remove_field')),
      h('span.small.muted', {}, wd('not_field')));
  }
  return h('div.rcb-field', {},
    h('label', { for: id, title: f.label || f.name }, f.label || f.name),
    h('div.rcb-field-ctl', {}, ctl, h('div.rcb-field-acts', {}, acts)));
}

function typedInput(f, v, has, set, drop, id) {
  if (f.type === 'longtext') {
    return h('textarea', { id, rows: Math.min(10, Math.max(3, str(v).split('\n').length + 1)), value: str(v),
      on: { change: (e) => set(e.target.value) } });
  }
  if (f.type === 'number') {
    return h('input.rcb-num', { id, type: 'number', step: 'any', value: typeof v === 'number' ? v : (has ? str(v) : ''),
      placeholder: f.default !== undefined ? wd('default_value', { v: f.default }) : '',
      on: { change: (e) => (e.target.value === '' ? drop() : set(Number(e.target.value))) } });
  }
  if (f.type === 'choice') {
    const choices = f.choices || [];
    return h('select', { id, on: { change: (e) => (e.target.value === '__unset' ? drop() : set(e.target.value)) } },
      has ? null : h('option', { value: '__unset', selected: true }, f.default !== undefined ? wd('not_set_default', { v: f.default }) : wd('not_set')),
      has && !choices.includes(v) ? h('option', { value: str(v), selected: true }, wd('not_choice', { v: str(v) })) : null,
      choices.map((c) => h('option', { value: c, selected: has && c === v }, c)));
  }
  if (f.type === 'boolean') {
    return h('label.check.rcb-bool', {},
      h('input', { id, type: 'checkbox', checked: v === true || v === 'true', on: { change: (e) => set(e.target.checked) } }), wd('yes'));
  }
  const long = typeof v === 'string' && (v.length > 80 || v.includes('\n'));
  return long
    ? h('textarea', { id, rows: 3, value: v, on: { change: (e) => set(e.target.value) } })
    : h('input', { id, value: str(v), on: { change: (e) => set(e.target.value) } });
}

function refPick(v, set, id) {
  const cur = v.slice(1);
  const ns = names();
  const groups = [['knob', wd('sec_knobs')], ['value', wd('sec_values')], ['fact', wd('facts')]];
  const sel = h('select', { id, on: { change: (e) => set(`$${e.target.value}`) } },
    ns.some((n) => n.name === cur) ? null : h('option', { value: cur, selected: true }, wd('not_known', { name: cur })),
    groups.map(([from, label]) => {
      const g = ns.filter((n) => n.from === from);
      return g.length ? h('optgroup', { label }, g.map((n) => h('option', { value: n.name, selected: n.name === cur },
        n.label ? `${n.name} — ${n.label}` : n.name))) : null;
    }));
  const knob = (S.working.params || []).find((p) => p.name === cur);
  return h('div.rcb-ref', {}, sel, knob ? h('span.small.muted', {}, wd('now_value', { v: short(knob.default, 60) })) : '');
}

// dry run

function buildDry() {
  const factNames = (subj()?.facts || []).map((f) => f.name);
  const n = Object.keys(S.extra || {}).length;
  const sig = JSON.stringify([S.working, S.scenario, S.extra]);
  return [
    stepHead(wd('step_try'), wd('dry_title'), wd('dry_sub')),
    h('div.rcb-dry-top', {}, scenarioPicker('dry'),
      h('button.primary', { type: 'button', html: `${icon('play', 14)} ${esc(wd('run'))}`, on: { click: (e) => busy(e.currentTarget, runDry) } })),
    h('details.rcb-extra', { open: n ? true : undefined },
      h('summary', {}, wd(n ? 'extra_facts_n' : 'extra_facts', { n })),
      valueEditor(S.extra || {}, (nv) => { S.extra = nv; S.sections.dry(); }, { type: 'record', lockType: true }),
      factNames.length ? h('p.small.muted', { style: 'margin:6px 0 0' }, wd('facts_known', { names: factNames.join(', ') })) : ''),
    S.dry
      ? [S.dry.sig !== sig ? h('p.small.muted.rcb-stale', {}, wd('dry_stale')) : '',
        dryResult(S.dry)]
      : h('p.small.muted', {}, wd('dry_idle')),
  ];
}

async function runDry() {
  if (!S.scenario) { toast(wd('pick_scenario_first'), 'warn'); return; }
  const mine = S;
  const sig = JSON.stringify([S.working, S.scenario, S.extra]);
  let res;
  try { res = await B.evalRule(S.working, S.scenario, S.extra); } catch (e) { res = { matched: null, values: {}, outcomes: [], error: e.message }; }
  if (S !== mine) return;
  S.dry = { sig, scenario: S.scenario, res };
  S.sections.dry?.();
}

function dryResult({ res, scenario }) {
  const sc = scenarioById(scenario);
  const where = sc ? wd('on_scenario', { label: sc.label }) : '';
  const [tone, ico, verdict] = res.error ? ['bad', 'alert', wd('failed', { error: res.error })]
    : res.matched === true ? ['ok', 'check', wd('fires')]
      : res.matched === false ? ['info', 'info', wd('not_fires')]
        : ['warn', 'alert', wd('unknown')];
  const vals = Object.entries(res.values || {});
  return h('div.rcb-dry', {},
    noteEl(tone, ico, h('b', {}, verdict), ` ${wd('preview_note', { where })}`),
    vals.length ? h('table.rcb-vals', {}, h('thead', {}, h('tr', {}, h('th', {}, wd('named_value')), h('th', {}, wd('worked_out')))),
      h('tbody', {}, vals.map(([k, v]) => h('tr', {}, h('td', {}, h('code', {}, `$${k}`)), h('td', {}, h('code', {}, short(v, 200))))))) : '',
    (res.outcomes || []).length ? h('div.rcb-previews', {}, res.outcomes.map(previewOutcome))
      : (res.matched === true ? h('p.small.muted', {}, wd('fires_no_outcome')) : ''));
}

function previewOutcome(o) {
  const spec = kindSpec(o.kind);
  const every = Number(o.cooldown_minutes) ? wd('every_min', { n: o.cooldown_minutes }) : '';
  const card = (title, sub, ...body) => h('div.rcb-prev', {},
    h('div.rcb-prev-head', {}, h('b', {}, `${Number(o.n ?? 0) + 1}. ${title}`), sub ? h('span.small.muted', {}, sub) : ''), ...body);
  if (o.kind === 'banner') {
    const tone = TONES.includes(o.tone) ? o.tone : 'info';
    return card(wd('out_banner'), [wd('shown_to', { who: str(o.audience) || wd('owner') }), wd('for_min', { n: str(o.expires_minutes) || 60 }), every].filter(Boolean).join(' · '),
      noteEl(tone, tone === 'ok' ? 'check' : tone === 'info' ? 'info' : 'alert', h('span.rcb-pre', {}, str(o.text))));
  }
  if (o.kind === 'notify') {
    return card(wd('out_email'), [wd('to_who', { who: str(o.to) || wd('owner') }), every, wd('no_mail_banner')].filter(Boolean).join(' · '),
      h('div.rcb-mail', {}, h('div.rcb-mail-subj', {}, h('span.small.muted', {}, `${wd('subject_label')}  `), h('b', {}, str(o.subject) || serverUi().notice_subject || '')),
        h('div.rcb-mail-body', {}, str(o.text))));
  }
  if (o.kind === 'refuse') {
    return card(wd('out_refuse'), wd('refuse_sub'),
      noteEl('bad', 'ban', h('span.rcb-pre', {}, str(o.message) || serverUi().refused || '')));
  }
  if (o.kind === 'value' || o.kind === 'flag') {
    return card(spec?.label || o.kind, spec?.doc || '',
      h('div.rcb-kv', {}, h('code', {}, str(o.name) || wd('no_name')), h('span', {}, '='), h('code', {}, short(o.value, 200))));
  }
  return card(spec?.label || String(o.kind), every,
    Object.entries(o).filter(([k]) => !['kind', 'n'].includes(k)).map(([k, v]) => h('div.rcb-kv', {}, h('b', {}, k), h('span.rcb-pre', {}, str(v)))));
}

// tests, check, history, other fields

function buildTests() {
  return [
    stepHead(wd('step_prove'), wd('tests_title'), wd('tests_sub')),
    testsEditor(S.working.test_cases || [], (v) => edit((w) => { w.test_cases = v; }, ['tests']),
      { mode: 'rule', scenarios: subjectScenarios(S.working), argNames: (subj()?.facts || []).map((f) => f.name) }),
  ];
}

function buildCheck() {
  return [
    stepHead(wd('sec_check'), wd('check_title'), cat.me.can.test ? wd('check_sub') : ''),
    S.checking ? h('p.small.muted.rcb-live', { html: `${spinner(13)} ${esc(wd('checking'))}` }) : '',
    S.checkError ? noteEl('bad', 'alert', wd('check_failed', { error: S.checkError })) : '',
    checkPanel(S.check),
  ];
}

function buildHistory() {
  const rows = S.detail?.history || [];
  return [
    stepHead(wd('sec_history'), wd('history_title'), wd('history_sub')),
    historyList(rows, viewVersion, restoreVersion, !!S.detail?.can?.restore),
  ];
}

function buildOther() {
  const extras = Object.keys(S.working).filter((k) => !KNOWN.has(k));
  if (!extras.length) return [];
  return [
    stepHead('', wd('sec_other'), wd('other_sub')),
    extras.map((k) => h('div.rcb-field', {},
      h('label', { title: k }, k),
      h('div.rcb-field-ctl', {},
        valueEditor(S.working[k], (nv) => edit((w) => { w[k] = nv; }, ['other'])),
        h('div.rcb-field-acts', {}, h('button.link.small', { type: 'button', on: { click: () => edit((w) => { delete w[k]; }, ['other']) } }, wd('remove_field')))))),
  ];
}

const versionNo = (row) => row.n ?? Number(row.file);

async function viewVersion(row) {
  const id = S.id;
  let snap;
  try { snap = await B.version('rules', id, versionNo(row)); } catch (e) { toast(e.message, 'bad'); return; }
  const canRestore = !!S?.detail?.can?.restore;
  const m = snap.meta || {};
  modal(wd('version_title', { id, v: m.version ?? '—' }),
    `<p class="small muted">${wd('version_meta', { action: esc(m.action || ''), by: esc(m.by || '—'), at: esc(fmt(m.at)) })}</p>`, {
      wide: true, eyebrow: wd('sec_history'),
      footer: `<button type="button" data-cancel>${wd('close')}</button>${canRestore
        ? `<button type="button" class="primary" data-restore>${icon('refresh')} ${wd('restore')}</button>` : ''}`,
      onOpen: (body, close) => {
        body.append(readOnlyRule(snap.item || {}));
        const card = body.closest('.modal');
        card.querySelector('[data-cancel]').onclick = () => close();
        const r = card.querySelector('[data-restore]');
        if (r) r.onclick = () => { close(); restoreVersion(row); };
      },
    });
}

function restoreVersion(row) {
  const id = S.id;
  const lose = !!S.detail?.draft || isDirty();
  const run = async () => {
    try {
      await B.restore('rules', id, versionNo(row));
      toast(wd('restored', { v: row.version ?? versionNo(row) }));
      await reload(id);
    } catch (e) { toast(e.message, 'bad'); }
  };
  confirmDialog(wd('restore_title'),
    `${lose ? `${wd('restore_lose')} ` : ''}${wd('restore_body')}`,
    run, wd('restore'), { tone: lose ? 'warn' : 'brand' });
}

/** A past version, drawn with the same editors inside a disabled fieldset: nothing can be changed. */
function readOnlyRule(item) {
  const t = trigOf(item);
  const c = { catalog: cat, names: () => namesFor(item), chipDetail };
  const noop = () => {};
  const block = (word, title, ...kids) => h('section.rcb-ro-block', {}, stepHead(word, title), ...kids);
  const vals = Object.entries(item.values || {});
  return h('fieldset.rcb-ro', { disabled: true },
    block(wd('step_rule'), item.label || item.rule_id || '',
      item.description ? h('p.rcb-pre.small', {}, item.description) : '',
      h('p.small.muted', { style: 'margin:0' }, [wd('ro_priority', { n: item.priority ?? 0 }), item.stop ? wd('ro_stops') : '',
        wd('ro_status', { s: item.status || '—' })].filter(Boolean).join(' · '))),
    block(wd('step_when'), t ? `${t.label} — ${t.name}` : (item.trigger || wd('no_trigger'))),
    (item.params || []).length ? block(wd('sec_knobs'), wd('ro_knobs'), paramsEditor(item.params, noop, { hint: '' })) : '',
    vals.length ? block(wd('step_values'), wd('ro_values'), vals.map(([n, node]) => h('div.rcb-value', {},
      h('div.rcb-value-head', {}, h('code', {}, `$${n}`)), exprEditor(node, noop, c)))) : '',
    block(wd('sec_if'), wd('if_title'), exprEditor(item.when ?? '', noop, c, { asTest: true })),
    block(wd('sec_then'), wd('then_title'), (item.then || []).map((o, i) => h('div.rcb-out', {},
      h('div.rcb-out-head', {}, h('span.rcb-out-n', {}, String(i + 1)), h('b', {}, kindLabel(o.kind))),
      Object.entries(o).filter(([k]) => k !== 'kind').map(([k, v]) => h('div.rcb-field', {},
        h('label', {}, kindSpec(o.kind)?.fields.find((f) => f.name === k)?.label || k),
        h('div.rcb-pre.small', { style: 'padding-top:8px' }, str(v))))))),
    (item.test_cases || []).length ? block(wd('step_prove'), wd('tests_title'), testsEditor(item.test_cases, noop,
      { mode: 'rule', scenarios: subjectScenarios(item), argNames: [] })) : '');
}

// --- actions ------------------------------------------------------------------------------------

/** Submit and publish act on the saved draft: save first when there is something unsaved (or no draft). */
async function ensureSaved() {
  if (S.isNew || isDirty() || !S.detail?.draft) await B.draft('rules', S.working.rule_id, S.working);
}

async function onSave() {
  const id = S.working.rule_id;
  try {
    await B.draft('rules', id, S.working);
    toast(wd('draft_saved'));
    await reload(id);
  } catch (e) { toast(e.message, 'bad'); }
}

async function onCheck() {
  const mine = S;
  try {
    clearTimeout(mine.checkTimer);
    mine.token += 1;
    const r = await B.check('rules', mine.working);
    if (S !== mine) return;
    mine.check = r;
    mine.checking = false;
    mine.checkError = '';
    mine.sections.check?.();
    mine.sectionEls.check?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    const failing = (r.tests || []).filter((x) => !x.ok).length;
    const good = !r.problems.length && (r.tests || []).length && !failing;
    toast(good ? wd('ready') : wd('problems_count', { p: r.problems.length, f: failing }), good ? 'ok' : 'warn');
  } catch (e) { toast(e.message, 'bad'); }
}

async function onSubmit() {
  const id = S.working.rule_id;
  let saved = false;
  try {
    await ensureSaved();
    saved = true;
    await B.submit('rules', id);
    toast(wd('submitted'));
    await reload(id);
  } catch (e) {
    toast(e.message, 'bad');
    if (saved) await reload(id).catch(() => {});   // never reload over edits that did not save
  }
}

async function onPublish() {
  const id = S.working.rule_id;
  let saved = false;
  try {
    await ensureSaved();
    saved = true;
    await B.publish('rules', id);
    toast(wd('published'));
    await reload(id);
  } catch (e) {
    // A 422 carries {message, problems, tests}, which ui.api turns into "[object Object]": say it in words,
    // and show the check panel, which holds the same problems and tests.
    const msg = /object Object/.test(e.message) ? wd('not_published') : e.message;
    toast(msg, 'bad', 7);
    if (saved || S.detail?.draft) {
      await reload(id).catch(() => {});
      S?.sectionEls.check?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }
}

function onReturn() {
  const id = S.id;
  const dirty = isDirty();
  modal(wd('return_title'),
    `<p class="small muted">${wd('return_body', { who: esc(S.detail?.draft?.meta?.author_email || wd('its_author')) })}${dirty ? ` ${wd('return_dropped')}` : ''}</p>
    <div class="field"><label for="rcb-note">${wd('note_label')}</label>
      <textarea id="rcb-note" rows="5" maxlength="1000" placeholder="${esc(wd('note_placeholder'))}"></textarea></div>`, {
      eyebrow: wd('review'),
      footer: `<button type="button" data-cancel>${wd('cancel')}</button><button type="button" class="primary" data-go>${icon('send')} ${wd('return_go')}</button>`,
      onOpen: (body, close) => {
        const card = body.closest('.modal');
        const ta = body.querySelector('#rcb-note');
        ta.focus();
        card.querySelector('[data-cancel]').onclick = () => close();
        card.querySelector('[data-go]').onclick = (e) => busy(e.currentTarget, async () => {
          if (!ta.value.trim()) { toast(wd('write_note'), 'warn'); ta.focus(); return; }
          try {
            await B.sendBack('rules', id, ta.value.trim());
            close();
            toast(wd('returned'));
            await reload(id);
          } catch (err) { toast(err.message, 'bad'); }
        });
      },
    });
}

function onDiscard() {
  const id = S.id;
  const live = !!S.detail?.live;
  const dirty = isDirty();
  confirmDialog(wd('discard_title'),
    `${wd(dirty ? 'discard_body_dirty' : 'discard_body')} ${wd(live ? 'discard_live' : 'discard_never')}`,
    async () => {
      try { await B.discard('rules', id); toast(wd('discarded')); await reload(id); } catch (e) { toast(e.message, 'bad'); }
    }, wd('act_discard'), { tone: 'danger' });
}

function onSwitchOff() {
  const id = S.id;
  confirmDialog(wd('off_title'), wd('off_body'),
    async () => {
      try { await B.status('rules', id, 'inactive'); toast(wd('switched_off')); await reload(id, { keepEdits: true }); } catch (e) { toast(e.message, 'bad'); }
    }, wd('act_off'), { tone: 'warn' });
}

async function onSwitchOn() {
  const id = S.id;
  try { await B.status('rules', id, 'published'); toast(wd('switched_on')); await reload(id, { keepEdits: true }); } catch (e) { toast(e.message, 'bad'); }
}

function onDelete() {
  const id = S.id;
  const hasDraft = !!S.detail?.draft;
  confirmDialog(wd('delete_title'),
    `${wd('delete_body', { id })} ${wd(hasDraft ? 'delete_draft_stays' : 'delete_history')}`,
    async () => {
      try { await B.remove('rules', id); toast(wd('deleted')); await reload(id); } catch (e) { toast(e.message, 'bad'); }
    }, wd('delete_yes'), { tone: 'danger' });   // tone given: confirmDialog guesses it from English words otherwise
}

function onCopy() { newRuleDialog(S.working); }

function onCancelNew() {
  confirmDialog(wd('cancel_new_title'), wd('cancel_new_body'), () => {
    S = null;
    const next = cat.rules.some((r) => r.id === ui.selected) ? ui.selected : (cat.rules[0]?.id || '');
    drawList();
    if (next) openRule(next); else drawEmpty();
  }, wd('act_cancel'), { tone: 'danger' });
}

function newRuleDialog(from = null) {
  const taken = (id) => cat.rules.some((r) => r.id === id);
  let suggestion = '';
  if (from) {
    const base = `${from.rule_id}_copy`.slice(0, 56);
    suggestion = base;
    for (let k = 2; taken(suggestion); k += 1) suggestion = `${base}${k}`;
  }
  const trigOptions = cat.triggers.map((t) => `<option value="${esc(t.name)}">${esc(t.label)} — ${esc(t.name)}</option>`).join('');
  const body = `${from ? `<p class="small muted">${wd('copy_intro', { id: esc(from.rule_id) })}</p>` : ''}
    <div class="field"><label for="rcb-nid">${wd('id_label')}</label>
      <input id="rcb-nid" autocomplete="off" spellcheck="false" autocapitalize="off" placeholder="${esc(wd('id_placeholder'))}" value="${esc(suggestion)}"/>
      <span class="small" id="rcb-nid-hint">${wd('id_hint')}</span></div>
    <div class="field"><label for="rcb-nlabel">${wd('label_label')}</label>
      <input id="rcb-nlabel" placeholder="${esc(wd('new_label_placeholder'))}" value="${esc(from ? wd('copy_label', { label: from.label || from.rule_id }) : '')}"/></div>
    ${from ? '' : `<div class="field"><label for="rcb-ntrig">${wd('trigger_when')}</label>
      ${cat.triggers.length ? `<select id="rcb-ntrig">${trigOptions}</select>` : `<p class="small muted">${wd('no_triggers')}</p>`}
      <span class="small" id="rcb-ntrig-doc"></span></div>`}`;
  modal(wd(from ? 'copy_title' : 'new_rule'), body, {
    eyebrow: wd('title'),
    footer: `<button type="button" data-cancel>${wd('cancel')}</button><button type="button" class="primary" data-make>${icon('plus')} ${wd(from ? 'make_copy' : 'create')}</button>`,
    onOpen: (b, close) => {
      const card = b.closest('.modal');
      const idEl = b.querySelector('#rcb-nid');
      const hint = b.querySelector('#rcb-nid-hint');
      const lab = b.querySelector('#rcb-nlabel');
      const trg = b.querySelector('#rcb-ntrig');
      const doc = b.querySelector('#rcb-ntrig-doc');
      const showDoc = () => {
        if (!trg || !doc) return;
        const t = cat.triggers.find((x) => x.name === trg.value);
        doc.textContent = t ? `${t.doc ? `${t.doc} ` : ''}${wd('outcomes_list', { kinds: t.kinds.map(kindLabel).join(', ') })}` : '';
      };
      if (trg) trg.onchange = showDoc;
      showDoc();
      const validate = () => {
        const v = idEl.value.trim();
        const msg = !v ? wd('id_missing') : !ID_RE.test(v) ? wd('id_bad')
          : taken(v) ? wd('id_taken') : '';
        hint.textContent = msg || wd('id_good');
        hint.classList.toggle('rcb-err', !!msg);
        return !msg;
      };
      idEl.addEventListener('input', () => {
        const fixed = idEl.value.toLowerCase().replace(/[\s-]+/g, '_');
        if (fixed !== idEl.value) idEl.value = fixed;
        validate();
      });
      const go = () => {
        if (!validate()) { idEl.focus(); return; }
        if (!lab.value.trim()) { toast(wd('need_label'), 'warn'); lab.focus(); return; }
        const id = idEl.value.trim();
        const label = lab.value.trim();
        close();
        startNew(from ? copyOf(from, id, label) : blankRule(id, label, trg ? trg.value : ''));
      };
      card.querySelector('[data-make]').onclick = go;
      card.querySelector('[data-cancel]').onclick = () => close();
      b.addEventListener('keydown', (e) => { if (e.key === 'Enter' && e.target.tagName === 'INPUT') { e.preventDefault(); go(); } });
      idEl.focus();
      if (from) idEl.select();
    },
  });
}
