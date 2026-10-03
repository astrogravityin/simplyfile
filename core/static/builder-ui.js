// The builders' shared parts — the Ops & Chips Builder and the Rule Chip Builder are made of these.
//
// The two-way rule (AstroStage): nothing in a chip's or a rule's JSON may exist that the author cannot
// see and edit here. So there is no raw-JSON box anywhere: every value has a typed editor (number, text,
// yes/no, list, record, rows of records), and every expression node has a form for its kind:
//   Value · Knob / fact ($name) · Chip {chip,args} · Op {vop,…} · Choose {cases,else} · Test {op,…}
//
// Built with DOM nodes (not HTML strings) so a nested editor keeps its own listeners; every editor calls
// onChange(newValue) and never mutates what it was given.
import { api, esc, t, loadWords, toast, when } from './ui.js';
import { icon } from './icons.js';

// Every word the builder editors show is chip ui.builder (core/words.py) - none is written here.
const bw = (k, v) => t('builder', k, v);
/** The builder editors' words. Every page that draws them awaits this first (page-ocb, page-rcb). */
export async function builderWords() { await loadWords('builder'); }

let cssLoaded = false;
export function loadBuilderCss() {
  if (cssLoaded) return;
  cssLoaded = true;
  const link = document.createElement('link');
  link.rel = 'stylesheet';
  link.href = new URL('./builder.css', import.meta.url).href;
  document.head.appendChild(link);
}

/** h('div.cls', {attrs, on: {click}}, children…) */
export function h(tag, props = {}, ...kids) {
  const [name, ...cls] = tag.split('.');
  const el = document.createElement(name || 'div');
  if (cls.length) el.className = cls.join(' ');
  for (const [k, v] of Object.entries(props || {})) {
    if (v === undefined || v === null || v === false) continue;
    if (k === 'on') Object.entries(v).forEach(([ev, fn]) => el.addEventListener(ev, fn));
    else if (k === 'html') el.innerHTML = v;
    else if (k === 'value') el.value = v;
    else if (k === 'checked') el.checked = !!v;
    else el.setAttribute(k, v === true ? '' : v);
  }
  kids.flat(9).forEach((c) => { if (c !== null && c !== undefined && c !== false) el.append(c instanceof Node ? c : document.createTextNode(String(c))); });
  return el;
}
const ico = (name, size = 14) => h('span', { html: icon(name, size) });
const clone = (v) => (v === undefined ? undefined : JSON.parse(JSON.stringify(v)));
export const TYPES = ['number', 'text', 'boolean', 'list', 'record', 'rows'];

export function typeOf(v) {
  if (Array.isArray(v)) return v.length && v.every((x) => x && typeof x === 'object' && !Array.isArray(x)) ? 'rows' : 'list';
  if (v === null || v === undefined) return 'text';
  if (typeof v === 'object') return 'record';
  if (typeof v === 'boolean') return 'boolean';
  if (typeof v === 'number') return 'number';
  return 'text';
}
const empty = (t) => ({ number: 0, text: '', boolean: false, list: [], record: {}, rows: [] }[t]);

function coerce(v, t) {
  if (t === 'number') { const n = Number(v); return Number.isFinite(n) ? n : 0; }
  if (t === 'boolean') return !!v;
  if (t === 'text') return v === null || v === undefined ? '' : (typeof v === 'object' ? '' : String(v));
  if (t === 'list') return Array.isArray(v) ? v : [];
  if (t === 'rows') return Array.isArray(v) ? v.filter((x) => x && typeof x === 'object') : [];
  if (t === 'record') return v && typeof v === 'object' && !Array.isArray(v) ? v : {};
  return v;
}

// --- values ---------------------------------------------------------------------------------------

/** A typed editor for any JSON value. type: fixed type, or omitted = the value's own type with a switch. */
export function valueEditor(value, onChange, { type, lockType = false, placeholder = '' } = {}) {
  const t = type || typeOf(value);
  const box = h('div.vb');
  const set = (v) => onChange(v);
  if (!lockType) {
    box.append(h('select.vb-type', {
      title: bw('value_type_tip'), 'aria-label': bw('value_type'),
      on: { change: (e) => set(coerce(value, e.target.value) ?? empty(e.target.value)) },
    }, TYPES.map((x) => h('option', { value: x, selected: x === t }, x))));
  }
  if (t === 'number') {
    box.append(h('input.vb-num', { type: 'number', step: 'any', value: value ?? 0, on: { change: (e) => set(Number(e.target.value)) } }));
  } else if (t === 'boolean') {
    box.append(h('label.vb-bool', {}, h('input', { type: 'checkbox', checked: !!value, on: { change: (e) => set(e.target.checked) } }), bw(value ? 'yes' : 'no')));
  } else if (t === 'text') {
    const long = String(value ?? '').length > 60 || String(value ?? '').includes('\n');
    const input = long
      ? h('textarea.vb-text', { rows: Math.min(8, 2 + Math.ceil(String(value).length / 90)), placeholder, on: { change: (e) => set(e.target.value) } })
      : h('input.vb-text', { value: value ?? '', placeholder, on: { change: (e) => set(e.target.value) } });
    if (long) input.value = value ?? '';
    box.append(input);
  } else if (t === 'list') {
    const items = coerce(value, 'list');
    box.append(h('div.vb-list', {},
      items.map((item, i) => h('div.vb-item', {},
        valueEditor(item, (nv) => { const c = clone(items); c[i] = nv; set(c); }, { type: typeOf(item) === 'record' ? 'record' : undefined }),
        h('button.ghost.icon.small', { type: 'button', title: bw('remove'), 'aria-label': bw('remove_item'), on: { click: () => set(items.filter((_, j) => j !== i)) } }, ico('close')))),
      h('button.link.small', { type: 'button', on: { click: () => set([...items, items.length ? empty(typeOf(items[items.length - 1])) : ''] ) } }, bw('add_item'))));
  } else if (t === 'record') {
    const rec = coerce(value, 'record');
    box.append(recordEditor(rec, set));
  } else if (t === 'rows') {
    box.append(rowsEditor(coerce(value, 'rows'), set));
  }
  return box;
}

function recordEditor(rec, set) {
  const keys = Object.keys(rec);
  return h('div.vb-rec', {},
    keys.map((k) => h('div.vb-kv', {},
      h('input.vb-key', { value: k, 'aria-label': bw('name'), on: { change: (e) => {
        const nk = e.target.value.trim(); if (!nk || nk === k || nk in rec) { e.target.value = k; return; }
        set(Object.fromEntries(Object.entries(rec).map(([a, b]) => [a === k ? nk : a, b])));
      } } }),
      valueEditor(rec[k], (nv) => set({ ...rec, [k]: nv })),
      h('button.ghost.icon.small', { type: 'button', title: bw('remove'), 'aria-label': bw('remove_named', { name: k }), on: { click: () => { const c = { ...rec }; delete c[k]; set(c); } } }, ico('close')))),
    h('button.link.small', { type: 'button', on: { click: () => { let n = 'name'; let i = 1; while (n in rec) n = `name${++i}`; set({ ...rec, [n]: '' }); } } }, bw('add_field')));
}

/** Rows of records as a grid: one column per field seen in any row. */
function rowsEditor(rows, set) {
  const cols = [...new Set(rows.flatMap((r) => Object.keys(r)))];
  const wrap = h('div.vb-rows');
  if (!rows.length) wrap.append(h('p.small.muted', {}, bw('no_rows')));
  rows.forEach((r, i) => {
    wrap.append(h('div.vb-row', {},
      h('span.vb-rown', {}, `${i + 1}`),
      h('div.vb-rowbody', {}, recordEditor(r, (nr) => { const c = clone(rows); c[i] = nr; set(c); })),
      h('div.vb-rowacts', {},
        h('button.ghost.icon.small', { type: 'button', title: bw('move_up'), 'aria-label': bw('move_row_up'), on: { click: () => { if (i === 0) return toast(bw('move_edge'), 'info'); const c = clone(rows); [c[i - 1], c[i]] = [c[i], c[i - 1]]; set(c); } } }, ico('up')),
        h('button.ghost.icon.small', { type: 'button', title: bw('move_down'), 'aria-label': bw('move_row_down'), on: { click: () => { if (i === rows.length - 1) return toast(bw('move_edge'), 'info'); const c = clone(rows); [c[i + 1], c[i]] = [c[i], c[i + 1]]; set(c); } } }, ico('down')),
        h('button.ghost.icon.small', { type: 'button', title: bw('remove_row'), 'aria-label': bw('remove_row'), on: { click: () => set(rows.filter((_, j) => j !== i)) } }, ico('close')))));
  });
  wrap.append(h('button.link.small', { type: 'button', on: { click: () => set([...rows, Object.fromEntries(cols.map((c) => [c, empty(typeOf(rows[0]?.[c]))]))]) } }, bw('add_row')));
  return wrap;
}

// --- expressions ----------------------------------------------------------------------------------

// Each test and each kind of node, in the words of chip ui.builder (read when drawn, after they load).
export const TEST_OPS = () => ({
  all: bw('test_all'), any: bw('test_any'), not: bw('test_not'), at_least: bw('test_at_least'),
  eq: bw('test_eq'), ne: bw('test_ne'), gt: bw('test_gt'), ge: bw('test_ge'), lt: bw('test_lt'), le: bw('test_le'), in_set: bw('test_in_set'),
});
const KIND_LABEL = () => ({ value: bw('kind_value'), ref: bw('kind_ref'), chip: bw('kind_chip'), vop: bw('kind_vop'), choose: bw('kind_choose'), test: bw('kind_test') });

export function nodeKind(n) {
  if (typeof n === 'string' && n.startsWith('$')) return 'ref';
  if (n && typeof n === 'object' && !Array.isArray(n)) {
    if ('chip' in n) return 'chip';
    if ('op' in n) return 'test';
    if (n.vop === 'choose') return 'choose';
    if ('vop' in n) return 'vop';
  }
  return 'value';
}

function fresh(kind, ctx) {
  return {
    value: '', ref: `$${ctx.names()[0]?.name || 'name'}`,
    chip: { chip: ctx.catalog.chips[0]?.id || '', args: {} },
    vop: { vop: ctx.catalog.ops.find((o) => !o.inactive)?.op || 'literal' },
    choose: { vop: 'choose', cases: [{ when: { op: 'eq', left: '', right: '' }, then: '' }], else: '' },
    test: { op: 'eq', left: '', right: '' },
  }[kind];
}

/**
 * ctx = {
 *   catalog,            // /api/core/build/catalog
 *   names(): [{name, label, from}]   // knobs, facts and named values this expression may read
 *   chipDetail(id): Promise<chip>    // params of a chip (cached)
 *   tryNode(node, as): Promise<{result|error}>   // optional: run a node on the chosen scenario
 * }
 */
export function exprEditor(node, onChange, ctx, { asTest = false, depth = 0 } = {}) {
  const kind = nodeKind(node);
  const box = h(`div.xb.xb-${kind}${depth % 2 ? '.odd' : ''}`);
  const kinds = asTest ? ['test', 'chip', 'ref'] : ['value', 'ref', 'chip', 'vop', 'choose', 'test'];
  const head = h('div.xb-head', {},
    h('select.xb-kind', { 'aria-label': bw('kind_aria'), on: { change: (e) => onChange(fresh(e.target.value, ctx)) } },
      kinds.map((k) => h('option', { value: k, selected: k === kind }, KIND_LABEL()[k]))));
  box.append(head);
  const sub = (n, set, opts = {}) => exprEditor(n, set, ctx, { depth: depth + 1, ...opts });

  if (kind === 'value' && Array.isArray(node) && hasExpr(node)) {
    // a list whose items are expressions (merge rows, compact values, a choose per item): one editor each
    node.forEach((it, i) => box.append(h('div.xb-item', {},
      sub(it, (nv) => { const c = clone(node); c[i] = nv; onChange(c); }),
      h('button.ghost.icon.small', { type: 'button', title: bw('remove'), 'aria-label': bw('remove_item'), on: { click: () => onChange(node.filter((_, j) => j !== i)) } }, ico('close')))));
    box.append(h('button.link.small', { type: 'button', on: { click: () => onChange([...node, '']) } }, bw('add_item')));
  } else if (kind === 'value' && node && typeof node === 'object' && !Array.isArray(node) && hasExpr(node)) {
    // a record whose fields are expressions (record fields, group measures): name + an editor each
    Object.keys(node).forEach((k) => box.append(h('div.xb-arg', {},
      h('div.xb-argname', {}, h('b', {}, k),
        h('button.ghost.icon.small', { type: 'button', title: bw('remove_field'), 'aria-label': bw('remove_named', { name: k }), on: { click: () => { const c = { ...node }; delete c[k]; onChange(c); } } }, ico('close'))),
      h('div.xb-argval', {}, sub(node[k], (nv) => onChange({ ...node, [k]: nv }))))));
    box.append(h('button.link.small', { type: 'button', on: { click: () => { let n = 'field'; let i = 1; while (n in node) n = `field${++i}`; onChange({ ...node, [n]: '' }); } } }, bw('add_field')));
  } else if (kind === 'value') {
    box.append(valueEditor(node, onChange));
  } else if (kind === 'ref') {
    const names = ctx.names();
    const cur = node.slice(1);
    head.append(h('select.xb-ref', { 'aria-label': bw('ref_aria'), on: { change: (e) => onChange(`$${e.target.value}`) } },
      [...(names.some((x) => x.name === cur) ? [] : [h('option', { value: cur, selected: true }, bw('unknown_here', { name: cur }))])],
      names.map((x) => h('option', { value: x.name, selected: x.name === cur }, `${x.name} — ${x.from}${x.label ? `: ${x.label}` : ''}`))));
  } else if (kind === 'chip') {
    const chipSel = h('input.xb-chip', { list: 'xb-chip-list', value: node.chip, placeholder: 'set.name', 'aria-label': bw('kind_chip'),
      on: { change: (e) => onChange({ chip: e.target.value.trim(), args: {} }) } });
    head.append(chipSel, datalist('xb-chip-list', ctx.catalog.chips.map((c) => [c.id, c.label])));
    const args = h('div.xb-args', {}, h('p.small.muted', {}, bw('loading_chip')));
    box.append(args);
    ctx.chipDetail(node.chip).then((chip) => {
      args.innerHTML = '';
      if (!chip) { args.append(h('p.small.bad-ink', {}, bw('no_chip', { id: node.chip }))); return; }
      args.append(h('p.small.muted.xb-doc', {}, chip.description_nl || chip.label || ''));
      (chip.params || []).forEach((p) => {
        const given = node.args && p.name in node.args;
        args.append(h('div.xb-arg', {},
          h('div.xb-argname', {}, h('b', {}, p.name), h('span.muted.small', {}, given ? '' : ` ${bw('knob_default')}`)),
          given
            ? h('div.xb-argval', {}, sub(node.args[p.name], (nv) => onChange({ ...node, args: { ...node.args, [p.name]: nv } })),
              h('button.link.small', { type: 'button', on: { click: () => { const a = { ...node.args }; delete a[p.name]; onChange({ ...node, args: a }); } } }, bw('use_default')))
            : h('div.xb-argval', {}, h('code.small', {}, short(p.default)),
              h('button.link.small', { type: 'button', on: { click: () => onChange({ ...node, args: { ...(node.args || {}), [p.name]: clone(p.default) ?? '' } }) } }, bw('set_it')))));
      });
    });
  } else if (kind === 'vop') {
    const op = ctx.catalog.ops.find((o) => o.op === node.vop);
    head.append(h('select.xb-op', { 'aria-label': bw('kind_vop'), on: { change: (e) => onChange({ vop: e.target.value }) } },
      op ? [] : [h('option', { selected: true, value: node.vop }, bw('unknown_op', { name: node.vop }))],
      ctx.catalog.ops.map((o) => h('option', { value: o.op, selected: o.op === node.vop, disabled: o.inactive && o.op !== node.vop },
        o.inactive ? bw('op_off', { op: o.op }) : o.op))));
    if (op) box.append(h('p.small.muted.xb-doc', {}, op.doc));
    (op?.params || Object.keys(node).filter((k) => k !== 'vop')).forEach((pname) => {
      const given = pname in node;
      box.append(h('div.xb-arg', {},
        h('div.xb-argname', {}, h('b', {}, pname)),
        given
          ? h('div.xb-argval', {}, sub(node[pname], (nv) => onChange({ ...node, [pname]: nv })),
            h('button.link.small', { type: 'button', on: { click: () => { const c = { ...node }; delete c[pname]; onChange(c); } } }, bw('leave_out')))
          : h('div.xb-argval', {}, h('button.link.small', { type: 'button', on: { click: () => onChange({ ...node, [pname]: '' }) } }, bw('give', { name: pname })))));
    });
  } else if (kind === 'choose') {
    const cases = node.cases || [];
    cases.forEach((c, i) => {
      box.append(h('div.xb-case', {},
        h('div.xb-caseh', {}, h('b', {}, bw(i === 0 ? 'when' : 'else_when')),
          h('button.ghost.icon.small', { type: 'button', title: bw('remove_case'), 'aria-label': bw('remove_case'), on: { click: () => onChange({ ...node, cases: cases.filter((_, j) => j !== i) }) } }, ico('close'))),
        sub(c.when, (nv) => { const cc = clone(cases); cc[i].when = nv; onChange({ ...node, cases: cc }); }, { asTest: true }),
        h('b.xb-then', {}, bw('then')),
        sub(c.then, (nv) => { const cc = clone(cases); cc[i].then = nv; onChange({ ...node, cases: cc }); })));
    });
    box.append(h('button.link.small', { type: 'button', on: { click: () => onChange({ ...node, cases: [...cases, { when: { op: 'eq', left: '', right: '' }, then: '' }] }) } }, bw('add_case')),
      h('div.xb-case', {}, h('b', {}, bw('otherwise')), sub(node.else, (nv) => onChange({ ...node, else: nv }))));
  } else if (kind === 'test') {
    head.append(h('select.xb-test', { 'aria-label': bw('kind_test'), on: { change: (e) => onChange(reshapeTest(node, e.target.value)) } },
      Object.entries(TEST_OPS()).map(([k, label]) => h('option', { value: k, selected: k === node.op }, label))));
    if (['all', 'any', 'at_least'].includes(node.op)) {
      const items = node.items || [];
      if (node.op === 'at_least') box.append(h('div.xb-arg', {}, h('div.xb-argname', {}, h('b', {}, 'N')), sub(node.n ?? 1, (nv) => onChange({ ...node, n: nv }))));
      items.forEach((it, i) => box.append(h('div.xb-item', {},
        sub(it, (nv) => { const c = clone(items); c[i] = nv; onChange({ ...node, items: c }); }, { asTest: true }),
        h('button.ghost.icon.small', { type: 'button', title: bw('remove'), 'aria-label': bw('remove_condition'), on: { click: () => onChange({ ...node, items: items.filter((_, j) => j !== i) }) } }, ico('close')))));
      box.append(h('button.link.small', { type: 'button', on: { click: () => onChange({ ...node, items: [...items, { op: 'eq', left: '', right: '' }] }) } }, bw('add_condition')));
    } else if (node.op === 'not') {
      box.append(sub(node.item ?? { op: 'eq', left: '', right: '' }, (nv) => onChange({ ...node, item: nv }), { asTest: true }));
    } else if (node.op === 'in_set') {
      box.append(h('div.xb-pair', {}, sub(node.value ?? '', (nv) => onChange({ ...node, value: nv })),
        h('span.xb-word', {}, bw('test_in_set')), sub(node.set ?? [], (nv) => onChange({ ...node, set: nv }))));
    } else {
      box.append(h('div.xb-pair', {}, sub(node.left ?? '', (nv) => onChange({ ...node, left: nv })),
        h('span.xb-word', {}, TEST_OPS()[node.op]), sub(node.right ?? '', (nv) => onChange({ ...node, right: nv }))));
    }
  }
  if (ctx.tryNode && depth === 0) {
    const out = h('span.xb-try-out.small');
    box.append(h('div.xb-try', {},
      h('button.small', { type: 'button', on: { click: async () => {
        out.textContent = '…';
        const r = await ctx.tryNode(node, asTest || kind === 'test' ? 'test' : 'value');
        out.className = `xb-try-out small ${r.error ? 'bad-ink' : ''}`;
        out.textContent = r.error ? r.error : `= ${short(r.result, 160)}`;
      } } }, ico('play'), ` ${bw('try_scenario')}`), out));
  }
  return box;
}

/** Does this plain value hold an expression anywhere inside (a chip, an op, a test or a $knob)? */
export function hasExpr(v) {
  if (typeof v === 'string') return v.startsWith('$');
  if (Array.isArray(v)) return v.some(hasExpr);
  if (v && typeof v === 'object') return nodeKind(v) !== 'value' || Object.values(v).some(hasExpr);
  return false;
}

function reshapeTest(node, op) {
  const pair = { left: node.left ?? node.value ?? '', right: node.right ?? node.set ?? '' };
  if (['all', 'any'].includes(op)) return { op, items: node.items || [node.op && !['all', 'any', 'at_least'].includes(node.op) ? node : { op: 'eq', left: '', right: '' }] };
  if (op === 'at_least') return { op, n: node.n ?? 1, items: node.items || [] };
  if (op === 'not') return { op, item: node.item || (['all', 'any'].includes(node.op) ? node : { op: 'eq', ...pair }) };
  if (op === 'in_set') return { op, value: pair.left, set: Array.isArray(pair.right) ? pair.right : [] };
  return { op, ...pair };
}

/** One page-level datalist per id, refreshed in place — never owned by an editor that a redraw removes. */
function datalist(id, rows) {
  let list = document.getElementById(id);
  if (!list) {
    list = h('datalist', { id });
    document.body.appendChild(list);
  }
  list.replaceChildren(...rows.map(([v, l]) => h('option', { value: v }, l)));
  return h('span');
}

export function short(v, n = 60) {
  const s = v === undefined ? '' : (typeof v === 'string' ? JSON.stringify(v) : JSON.stringify(v));
  return s.length > n ? `${s.slice(0, n - 1)}…` : s;
}

// --- knobs, test cases, results -------------------------------------------------------------------

/** params: [{name, type, label?, default}] */
export function paramsEditor(params, onChange, { hint = bw('knobs_hint') } = {}) {
  const list = params || [];
  const box = h('div.pe', {}, h('p.small.muted', {}, hint));
  list.forEach((p, i) => {
    const t = p.type && TYPES.includes(p.type) ? p.type : typeOf(p.default);
    const upd = (patch) => { const c = clone(list); c[i] = { ...c[i], ...patch }; onChange(c); };
    box.append(h('div.pe-row', {},
      h('div.pe-top', {},
        h('input.pe-name', { value: p.name, placeholder: bw('knob_name_ph'), 'aria-label': bw('knob_name'), on: { change: (e) => upd({ name: e.target.value.trim().replace(/[^\w]/g, '_') }) } }),
        h('select.pe-type', { 'aria-label': bw('knob_type'), on: { change: (e) => upd({ type: e.target.value, default: coerce(p.default, e.target.value) ?? empty(e.target.value) }) } },
          TYPES.map((x) => h('option', { value: x, selected: x === t }, x))),
        h('input.pe-label', { value: p.label || '', placeholder: bw('knob_label_ph'), 'aria-label': bw('knob_label'), on: { change: (e) => upd({ label: e.target.value }) } }),
        h('button.ghost.icon.small', { type: 'button', title: bw('remove_knob'), 'aria-label': bw('remove_knob_named', { name: p.name }), on: { click: () => onChange(list.filter((_, j) => j !== i)) } }, ico('trash'))),
      h('div.pe-default', {}, h('span.small.muted', {}, bw('default')), valueEditor(p.default, (nv) => upd({ default: nv }), { type: t, lockType: true }))));
  });
  box.append(h('button.small', { type: 'button', on: { click: () => onChange([...list, { name: `knob${list.length + 1}`, type: 'number', label: '', default: 0 }]) } }, ico('plus'), ` ${bw('add_knob')}`));
  return box;
}

/** cases: [{scenario?, args?|facts?, expect|expect_value}]  mode: 'predicate' | 'accessor' | 'rule' */
export function testsEditor(cases, onChange, { mode, scenarios, argNames = [] }) {
  const list = cases || [];
  const box = h('div.te');
  list.forEach((c, i) => {
    const upd = (patch) => { const cc = clone(list); cc[i] = { ...cc[i], ...patch }; Object.keys(cc[i]).forEach((k) => cc[i][k] === undefined && delete cc[i][k]); onChange(cc); };
    const argsKey = mode === 'rule' ? 'facts' : 'args';
    const exp = mode === 'accessor' ? 'expect_value' : 'expect';
    box.append(h('div.te-case', {},
      h('div.te-head', {}, h('b', {}, bw('test_n', { n: i + 1 })),
        h('select', { 'aria-label': bw('scenario'), on: { change: (e) => upd({ scenario: e.target.value || undefined }) } },
          h('option', { value: '' }, bw('no_scenario')), scenarios.map((s) => h('option', { value: s.scenario_id, selected: s.scenario_id === c.scenario }, `${s.scenario_id} — ${s.label}`))),
        h('button.ghost.icon.small', { type: 'button', title: bw('remove_test'), 'aria-label': bw('remove_test_n', { n: i + 1 }), on: { click: () => onChange(list.filter((_, j) => j !== i)) } }, ico('trash'))),
      h('div.te-body', {},
        h('div', {}, h('span.small.muted', {}, bw(mode === 'rule' ? 'facts_over' : 'args_over')),
          valueEditor(c[argsKey] || {}, (nv) => upd({ [argsKey]: Object.keys(nv).length ? nv : undefined }), { type: 'record', lockType: true }),
          argNames.length ? h('p.small.muted', {}, bw('known', { names: argNames.join(', ') })) : ''),
        h('div', {}, h('span.small.muted', {}, bw(mode === 'accessor' ? 'expected_value' : 'expected')),
          mode === 'accessor'
            ? valueEditor(c.expect_value, (nv) => upd({ expect_value: nv }))
            : h('select', { on: { change: (e) => upd({ expect: e.target.value === 'true' ? true : e.target.value === 'false' ? false : null }) } },
              [['true', bw(mode === 'rule' ? 'fires' : 'word_true')], ['false', bw(mode === 'rule' ? 'does_not_fire' : 'word_false')], ['null', bw('unknown')]]
                .map(([v, l]) => h('option', { value: v, selected: String(c.expect) === v }, l)))))));
  });
  box.append(h('button.small', { type: 'button', on: { click: () => onChange([...list, mode === 'accessor' ? { args: {}, expect_value: null } : { [mode === 'rule' ? 'facts' : 'args']: {}, expect: true }]) } }, ico('plus'), ` ${bw('add_test')}`));
  return box;
}

/** check = {problems: [..], tests: [{n, scenario, want, got, ok, error, outcomes?}]} */
export function checkPanel(check) {
  if (!check) return h('p.small.muted', {}, bw('not_checked'));
  const tests = check.tests || [];
  const passed = tests.filter((t) => t.ok).length;
  const good = !check.problems.length && tests.length && passed === tests.length;
  return h('div.cp', {},
    h(`div.note.${good ? 'ok' : 'warn'}`, { html: `${icon(good ? 'check' : 'alert')}<div><b>${bw(good ? 'ready' : 'not_ready')}</b> ${bw(check.problems.length === 1 ? 'problems_one' : 'problems_many', { n: check.problems.length })} · ${bw(tests.length === 1 ? 'tests_pass_one' : 'tests_pass_many', { passed, n: tests.length })}</div>` }),
    check.problems.length ? h('ul.cp-problems', {}, check.problems.map((p) => h('li', {}, p))) : '',
    tests.length ? h('table.cp-tests', {},
      h('thead', {}, h('tr', {}, ['', bw('kind_test'), bw('scenario'), bw('expected'), bw('got')].map((x) => h('th', {}, x)))),
      h('tbody', {}, tests.map((t) => h(`tr.${t.ok ? 'ok' : 'bad'}`, {},
        h('td', { html: icon(t.ok ? 'check' : 'close', 14) }), h('td', {}, t.n), h('td', {}, t.scenario || '—'),
        h('td', {}, h('code', {}, short(t.want, 80))),
        h('td', {}, t.error ? h('span.bad-ink', {}, t.error) : h('code', {}, short(t.got, 80)),
          t.outcomes && t.outcomes.length ? h('div.small.muted', {}, t.outcomes.map((o) => `${o.kind}: ${o.text || o.message || o.subject || o.value || ''}`).join(' · ')) : ''))))) : '');
}

export function statusTag(s) {
  if (!s) return '';
  const draft = s.draft ? `<span class="tag ${s.draft.status === 'review' ? 'warn' : ''}">${bw(s.draft.status === 'review' ? 'in_review' : 'draft')}</span>` : '';
  const live = { published: `<span class="tag ok">${bw('live')}</span>`, inactive: `<span class="tag bad">${bw('off')}</span>`, unpublished: '' }[s.status] || '';
  return `${live}${draft}`;
}

export function historyList(rows, onView, onRestore, canRestore) {
  if (!rows.length) return h('p.small.muted', {}, bw('no_history'));
  return h('table.hist', {},
    h('thead', {}, h('tr', {}, [bw('version'), bw('what'), bw('by'), bw('when'), ''].map((x) => h('th', {}, x)))),
    h('tbody', {}, rows.map((r) => h('tr', {},
      h('td', {}, r.version ?? '—'), h('td', {}, r.action), h('td.small', {}, r.by), h('td.small', {}, when(r.at)),
      h('td', {}, h('button.link.small', { type: 'button', on: { click: () => onView(r) } }, bw('view')),
        canRestore ? [' · ', h('button.link.small', { type: 'button', on: { click: () => onRestore(r) } }, bw('restore_as_draft'))] : '')))));
}

/** Where the builder API lives, in one place. */
export const B = {
  catalog: () => api('/api/core/build/catalog'),
  get: (kind, id) => api(`/api/core/build/${kind}/${encodeURIComponent(id)}`),
  draft: (kind, id, item, withDrafts) => api(`/api/core/build/${kind}/${encodeURIComponent(id)}/draft`, { method: 'PUT', body: { item, with_drafts: withDrafts } }),
  check: (kind, item, withDrafts) => api(`/api/core/build/check/${kind}`, { method: 'POST', body: { item, with_drafts: withDrafts } }),
  submit: (kind, id) => api(`/api/core/build/${kind}/${encodeURIComponent(id)}/submit`, { method: 'POST' }),
  publish: (kind, id) => api(`/api/core/build/${kind}/${encodeURIComponent(id)}/publish`, { method: 'POST' }),
  sendBack: (kind, id, note) => api(`/api/core/build/${kind}/${encodeURIComponent(id)}/return`, { method: 'POST', body: { note } }),
  discard: (kind, id) => api(`/api/core/build/${kind}/${encodeURIComponent(id)}/draft`, { method: 'DELETE' }),
  status: (kind, id, status) => api(`/api/core/build/${kind}/${encodeURIComponent(id)}/status`, { method: 'POST', body: { status } }),
  remove: (kind, id) => api(`/api/core/build/${kind}/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  restore: (kind, id, n) => api(`/api/core/build/${kind}/${encodeURIComponent(id)}/restore/${n}`, { method: 'POST' }),
  version: (kind, id, n) => api(`/api/core/build/${kind}/${encodeURIComponent(id)}/history/${n}`),
  evalNode: (node, as, scenario, args, withDrafts) => api('/api/core/build/eval', { method: 'POST', body: { node, as, scenario, args, with_drafts: withDrafts } }),
  evalRule: (rule, scenario, facts, withDrafts) => api('/api/core/build/eval', { method: 'POST', body: { rule, scenario, args: facts, with_drafts: withDrafts } }),
  scenario: (id, body) => api(`/api/core/build/scenario/${encodeURIComponent(id)}`, { method: 'PUT', body }),
  dropScenario: (id) => api(`/api/core/build/scenario/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  usages: (what, name) => api(`/api/core/build/usages/${what}/${encodeURIComponent(name)}`),
  op: (op, body) => api(`/api/core/build/ops/${encodeURIComponent(op)}`, { method: 'PUT', body }),
};

/** Chip details for expression editors, fetched once per page visit. */
export function chipCache() {
  const seen = new Map();
  return (id) => {
    if (!id) return Promise.resolve(null);
    if (!seen.has(id)) seen.set(id, B.get('chips', id).then((d) => (d.draft ? d.draft.item : d.live)).catch(() => null));
    return seen.get(id);
  };
}

export { esc };
