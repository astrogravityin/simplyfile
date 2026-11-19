// Rule watch (boilerplate, 2026-10-07 - made from SimplyFile's Tax rules): a domain's yearly figures - Fetch (an AI searching
// official sources, in the portal's own shapes), Compare (live beside fetched, what changed, the source), Apply (the ticked
// ones, published through the Ops & chips builder layer with History). rulewatch.py decides and writes; this draws.
// A domain's page: `export const xPage = rulewatchPage('<name>')` - routes /api/<name>, words chip ui.<name>.
import { api, BASE, esc, toast, busy, pageHead, t, loadWords, confirmDialog } from './app.js';
import { icon } from './icons.js';
import { kpiTile } from './page-kit.js';

let w;
const L = (n) => (n == null ? '∞' : n >= 1e5 && n % 1e3 === 0 ? `${+(n / 1e5).toFixed(2)}${w('lakh')}` : `₹${Number(n).toLocaleString('en-IN')}`);
const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const named = (k) => { const x = w(k); return x === k ? k : x; };

/** A value as people read it, by the item's kind; `other` marks the parts that differ from it. */
function show(kind, v, other) {
  if (v == null) return `<span class="muted">-</span>`;
  const diff = (a, b) => (JSON.stringify(a) !== JSON.stringify(b) ? ' tw-diff' : '');
  const slabs = (rows, o) => rows.map((s, i) => `<span class="tw-slab${o ? diff(s, (o || [])[i]) : ''}">${esc(s.upto == null ? w('slab_above', { from: L(rows[i - 1] ? rows[i - 1].upto : 0) }) : w('slab_upto', { upto: L(s.upto) }))} <b>${esc(s.rate)}%</b></span>`).join('');
  switch (kind) {
    case 'slabs_by_age': return Object.keys(v).map((b) => `<div class="tw-band"><small>${esc(named(b))}</small>${slabs(v[b], other && other[b])}</div>`).join('');
    case 'steps': return v.map((s, i) => `<span class="tw-slab${other ? diff(s, other[i]) : ''}">${esc(w('slab_above', { from: L(s.above) }))} <b>${esc(s.rate)}%</b></span>`).join('');
    case 'money': return esc(L(v));
    case 'pct': return `${esc(v)}%`;
    case 'number': return esc(v);
    case 'mmdd': return esc(`${v % 100} ${MON[Math.floor(v / 100) - 1] || '?'}`);
    case 'date': { const [y, m, dd] = String(v).split('-'); return esc(`${+dd} ${MON[+m - 1] || '?'} ${y}`); }
    case 'dates': return v.map((x) => `<span class="tw-slab${other && !other.includes(x) ? ' tw-diff' : ''}">${show('date', x)}</span>`).join('')
      + (Array.isArray(other) ? other.filter((x) => !v.includes(x)).map((x) => `<span class="tw-slab tw-gone" title="${esc(w('t_gone'))}">${show('date', x)}</span>`).join('') : '');
    case 'money_by_age': case 'money_by_regime': case 'money_map': case 'pct_by_regime':
      return Object.entries(v).map(([k, x]) => `<span class="tw-slab${other ? diff(x, other[k]) : ''}">${esc(named(k))} <b>${esc(kind === 'pct_by_regime' ? `${x}%` : L(x))}</b></span>`).join('');
    default: return tree(v, Array.isArray(other) || (other && typeof other === 'object') ? other : undefined);
  }
}

// 2026-10-09 owner: a list of dates or rows (court calendars: holidays, vacations) and a slab table (court fees) read as a
// compact table / chips, never raw JSON; with the live value beside it (Compare) each row says added, changed (old -> new)
// or removed. Any shape: a list of plain values = chips, a list of records = a table, a record of lists = one block each.
const plain = (x) => x == null || typeof x !== 'object';
const isRec = (x) => x != null && typeof x === 'object' && !Array.isArray(x);
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const head = (k) => { const x = w(`c_${k}`); return x === `c_${k}` ? String(k).replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase()) : x; };
function cell(k, x) {
  if (x == null) return /^(upto|to|till|max)$/.test(k) ? '∞' : '<span class="muted">-</span>';
  if (typeof x === 'boolean') return esc(w(x ? 't_yes' : 't_no'));
  if (typeof x === 'number') return esc(x.toLocaleString('en-IN'));
  if (typeof x === 'string') return /^\d{4}-\d{2}-\d{2}$/.test(x) ? show('date', x) : esc(x);
  if (Array.isArray(x) && x.every(plain)) return x.map((y) => cell(k, y)).join(', ');
  return `<code>${esc(JSON.stringify(x))}</code>`;
}
/** The field that names a row in both lists (id, date, from, label, name) - else rows pair by place. */
function rowKey(a, b) {
  const all = [...a, ...(b || [])];
  const uniq = (l, f) => new Set(l.map((r) => JSON.stringify(r[f]))).size === l.length;
  const k = ['id', 'date', 'from', 'label', 'name'].find((f) => all.every((r) => r[f] != null) && uniq(a, f) && uniq(b || [], f));
  return k ? (r) => JSON.stringify(r[k]) : null;
}
function rowsTable(v, o) {
  const cols = [...new Set([...v, ...(o || [])].flatMap((r) => Object.keys(r)))];
  const key = rowKey(v, o);
  const was = o ? new Map(o.map((r, i) => [key ? key(r) : i, r])) : null;
  const n = { add: 0, chg: 0, del: 0 };
  const seen = new Set();
  const tr = v.map((r, i) => {
    const id = key ? key(r) : i;
    seen.add(id);
    const old = was ? was.get(id) : undefined;
    const st = !was ? '' : old === undefined ? 'add' : same(old, r) ? '' : 'chg';
    if (st) n[st] += 1;
    return `<tr class="${st ? `tw-r-${st}` : ''}">${cols.map((c) => `<td>${st === 'chg' && !same(old[c], r[c])
      ? `<s class="muted">${cell(c, old[c])}</s> → <b>${cell(c, r[c])}</b>` : cell(c, r[c])}</td>`).join('')}${was ? `<td>${st ? `<span class="tw-tag">${esc(w(`t_${st}`))}</span>` : ''}</td>` : ''}</tr>`;
  });
  const gone = was ? [...was].filter(([id]) => !seen.has(id)).map(([, r]) => r) : [];
  n.del = gone.length;
  gone.forEach((r) => tr.push(`<tr class="tw-r-del">${cols.map((c) => `<td><s>${cell(c, r[c])}</s></td>`).join('')}<td><span class="tw-tag">${esc(w('t_del'))}</span></td></tr>`));
  const sum = was && (n.add + n.chg + n.del) ? `<div class="tw-sum">${['add', 'chg', 'del'].filter((x) => n[x]).map((x) => `<span class="tw-slab tw-diff">${esc(w(`t_${x}_n`, { n: n[x] }))}</span>`).join('')}</div>` : '';
  return `${sum}<div class="tw-mini"><table><thead><tr>${cols.map((c) => `<th>${esc(head(c))}</th>`).join('')}${was ? '<th></th>' : ''}</tr></thead><tbody>${tr.join('')}</tbody></table></div>`;
}
/** Any value as people read it; `o` (the live value, on Compare) marks what differs. */
function tree(v, o) {
  if (plain(v)) return o !== undefined && !same(v, o) ? `<s class="muted">${cell('', o)}</s> → <b>${cell('', v)}</b>` : cell('', v);
  if (Array.isArray(v)) {
    const ol = Array.isArray(o) ? o : undefined;
    if (!v.length) return `<span class="muted">${esc(w('t_empty'))}</span>`;
    if (v.every(plain)) {
      const has = (l, x) => l.some((y) => same(x, y));
      return v.map((x) => `<span class="tw-slab${ol && !has(ol, x) ? ' tw-diff' : ''}">${cell('', x)}</span>`).join('')
        + (ol ? ol.filter((x) => !has(v, x)).map((x) => `<span class="tw-slab tw-gone" title="${esc(w('t_gone'))}">${cell('', x)}</span>`).join('') : '');
    }
    if (v.every(isRec) && (!ol || ol.every(isRec))) return rowsTable(v, ol);
    return `<code>${esc(JSON.stringify(v))}</code>`;
  }
  const or = isRec(o) ? o : undefined;
  const keys = [...new Set([...Object.keys(v), ...Object.keys(or || {})])];
  if (keys.every((k) => plain(v[k]) && (!or || plain(or[k])))) {
    return keys.map((k) => (!(k in v) ? `<span class="tw-slab tw-gone">${esc(head(k))} <b>${cell(k, or[k])}</b></span>`
      : `<span class="tw-slab${or && !same(v[k], or[k]) ? ' tw-diff' : ''}">${esc(head(k))} <b>${or && k in or && !same(v[k], or[k]) ? `<s>${cell(k, or[k])}</s> → ` : ''}${cell(k, v[k])}</b></span>`)).join('');
  }
  return keys.map((k) => `<div class="tw-sub"><small>${esc(head(k))}</small>${k in v ? tree(v[k], or ? (k in or ? or[k] : []) : undefined) : `<s class="muted">${esc(w('t_del'))}</s>`}</div>`).join('');
}
// The page's own few styles (page-rulewatch.js is boilerplate; app.css is each portal's own)
const CSS = `.tw-mini{max-height:260px;overflow:auto;margin:2px 0;border:1px solid var(--line);border-radius:8px}
.tw-mini table{border-collapse:collapse;width:100%;font-size:12px}
.tw-mini th{position:sticky;top:0;background:var(--panel-2);text-align:left;font-weight:600;color:var(--muted);padding:3px 6px}
.tw-mini td{padding:3px 6px;border-top:1px solid var(--line);vertical-align:top}
.tw-mini tr.tw-r-add td,.tw-mini tr.tw-r-chg td{background:color-mix(in srgb,var(--warn) 14%,transparent)}
.tw-mini tr.tw-r-del td{color:var(--muted)}
.tw-tag{font-size:11px;padding:1px 6px;border-radius:999px;background:var(--panel-2);white-space:nowrap}
.tw-slab.tw-gone{text-decoration:line-through;color:var(--muted)}
.tw-sub{margin:4px 0}.tw-sub>small{display:block;color:var(--muted);margin-bottom:2px}
.tw-sum{display:flex;flex-wrap:wrap;gap:4px;margin:2px 0 4px}`;
const addCss = () => { if (!document.getElementById('tw-mini-css')) document.head.insertAdjacentHTML('beforeend', `<style id="tw-mini-css">${CSS}</style>`); };

export const rulewatchPage = (name) => async (host) => {
  w = (k, v) => t(name, k, v);
  addCss();
  const A = `/api/${name}`;
  await loadWords(name);
  const q = new URLSearchParams((location.hash.split('?')[1]) || '');
  let d = await api(`${A}${q.get('ay') ? `?ay=${encodeURIComponent(q.get('ay'))}` : ''}`);
  const S = { only: false, pick: new Set(d.rows.filter((r) => r.state === 'changed').map((r) => r.id)), edit: '' };

  const draw = () => {
    const tone = { changed: '--warn', same: '--ok', unknown: '--muted' };
    const years = d.years;   // the live period first: check it again
    const rows = d.rows.filter((r) => !S.only || r.state === 'changed');
    const groups = Object.keys(d.groups).filter((g) => rows.some((r) => r.group === g));
    const picked = [...S.pick].filter((id) => d.rows.some((r) => r.id === id && r.state === 'changed'));
    if (d.can_change !== undefined) S.can = d.can_change === true;   // Fetch / Apply answers carry no can_change: keep the first
    if (d.ais) S.ais = d.ais;
    const can = S.can;
    host.innerHTML = pageHead(w('title'), esc(w('lede')))
      + `<section class="card tw-head" id="tw-head"><div class="tw-live">${icon('check', 15)} <b>${esc(w('live', { ay: d.live_ay }))}</b></div>
        ${can && d.check_due ? `<p class="small" style="color:var(--warn)">${icon('alert', 13)} ${esc(d.last_check ? w('check_due', { days: d.check_every_days }) : w('check_never'))}</p>` : ''}
        <div class="tw-fetch" id="tw-fetch"><label>${esc(w('target'))} <select id="tw-ay">${years.map((y) => `<option value="${esc(y)}"${y === d.ay ? ' selected' : ''}>${esc(y === d.live_ay ? w('recheck', { ay: y }) : y)}</option>`).join('')}</select></label>
          ${can ? `<label>${esc(w('ai_pick'))} <select id="tw-ai"><option value="">${esc(w('ai_auto'))}</option>${(S.ais || []).map((a) => `<option value="${esc(a.provider)}" ${S.ai === a.provider ? 'selected' : ''}>${esc(a.label)} · ${esc(w(a.ready ? 'ai_ready' : 'ai_resting'))}</option>`).join('')}</select></label>` : ''}
          ${can ? `<button class="btn primary" id="tw-go" data-work="${esc(w('fetching'))}">${icon('refresh', 14)} ${esc(w('fetch'))}</button>` : `<span class="sv-pill" style="--c:var(--muted)">${icon('lock', 12)} ${esc(w('ro_tag'))}</span>`}
          ${d.at ? `<span class="small muted">${esc(w('fetched_at', { when: `${d.at.slice(0, 16).replace('T', ' ')} · ${d.model}` }))}</span>` : ''}</div>
        <p class="small muted">${icon('lock', 13)} ${esc(can ? w('rule') : w('ro_note', { ay: d.live_ay }))}</p>
        ${w('rulebook_url') && w('rulebook_url') !== 'rulebook_url' ? `<p class="small"><a class="btn ghost sm" href="${BASE}${esc(w('rulebook_url'))}" target="_blank" rel="noopener">${icon('book', 13)} ${esc(w('rulebook'))}</a> <span class="muted">${esc(w('rulebook_sub'))}</span></p>` : ''}</section>`
      + `<section class="sf-kpis">${kpiTile('list', '--brand', w('k_items'), d.rows.length, w('h_live', { ay: d.live_ay }))}
          ${kpiTile('pulse', '--warn', w('k_changed'), d.count.changed, w('h_new', { ay: d.ay }))}
          ${kpiTile('check', '--ok', w('k_same'), d.count.same, '')}${kpiTile('info', '--muted', w('k_unknown'), d.count.unknown, '')}</section>`
      + (!d.fetched ? `<div class="card"><p>${icon('info', 14)} ${esc(w('none_yet', { ay: d.ay }))}</p></div>` : '')
      + `<section class="card an-card" id="tw-table"><div class="tw-bar"><button class="btn ghost sm" id="tw-only">${esc(S.only ? w('show_all') : w('only_changed'))}</button></div>
        <div class="an-scroll"><table class="cc-tbl an-tbl tw-tbl"><thead><tr><th>${esc(w('h_item'))}</th><th>${esc(w('h_live', { ay: d.live_ay }))}</th>
          <th>${esc(w('h_new', { ay: d.ay }))}</th><th>${esc(w('h_source'))}</th><th class="num">${esc(w('h_pick'))}</th></tr></thead><tbody>
        ${groups.map((g) => `<tr class="tw-group"><td colspan="5">${esc(w(`g_${g}`))}</td></tr>${rows.filter((r) => r.group === g).map((r) => `<tr class="tw-row s-${r.state}">
          <td><b>${esc(r.label)}</b><div class="small muted">${esc(w('where'))}: ${r.where.map((x) => `<code>${esc(x)}</code>`).join(' ')}</div></td>
          <td>${show(r.kind, r.live)}</td>
          <td>${S.edit === r.id ? `<textarea class="tw-json" rows="5" aria-label="${esc(r.label)}">${esc(JSON.stringify(r.new ?? r.live, null, 1))}</textarea>
                <div class="tw-ed"><button class="btn sm primary" data-save="${esc(r.id)}">${esc(w('save'))}</button><button class="btn sm ghost" data-cancel>${esc(w('cancel'))}</button></div>`
            : `${show(r.kind, r.new, r.live)}<div class="tw-state"><span class="sv-pill" style="--c:var(${tone[r.state]})">${esc(w(r.state))}</span>${r.edited ? ` <span class="small muted">${esc(w('edited'))}</span>` : ''}
                ${can ? `<button class="link small" data-edit="${esc(r.id)}">${esc(w('edit'))}</button>` : ''}</div>${r.note ? `<div class="small muted">${esc(r.note)}</div>` : ''}`}</td>
          <td>${r.source ? `<a class="small" href="${esc(r.source)}" target="_blank" rel="noopener noreferrer">${esc(r.source.replace(/^https?:\/\//, '').slice(0, 40))}</a>` : ''}</td>
          <td class="num">${can && r.state === 'changed' ? `<input type="checkbox" data-pick="${esc(r.id)}" ${S.pick.has(r.id) ? 'checked' : ''} aria-label="${esc(r.label)}">` : ''}</td></tr>`).join('')}`).join('')}
        </tbody></table></div>
        ${can ? `<div class="tw-apply" id="tw-apply"><button class="btn primary" id="tw-do" ${picked.length ? '' : 'disabled'}>${icon('check', 14)} ${esc(picked.length ? w('apply', { n: picked.length, ay: d.ay }) : w('apply_none'))}</button></div>` : ''}</section>`
      + (d.fetched ? `<section class="card"><h3 class="rc-h">${icon('alert', 15)} ${esc(w('new_h'))}</h3><p class="small muted">${esc(w('new_p'))}</p>
          ${(d.new_rules || []).length ? `<ul class="tw-new">${d.new_rules.map((x) => `<li><b>${esc(x.what)}</b>${x.who ? ` <span class="small muted">${esc(w('new_who', { who: x.who }))}</span>` : ''}${/^https?:\/\//.test(x.source) ? ` <a class="small" href="${esc(x.source)}" target="_blank" rel="noopener noreferrer" aria-label="${esc(x.source)}">${icon('external', 11)}</a>` : ''}</li>`).join('')}</ul>`
            : `<p class="small">${esc(w('new_none'))}</p>`}</section>` : '')
      + (d.pages.length ? `<section class="card"><h3 class="rc-h">${icon('globe', 15)} ${esc(w('sources'))}</h3><ul class="tw-pages">${d.pages.map((p) => `<li><a href="${esc(p.uri)}" target="_blank" rel="noopener noreferrer">${esc(p.title || p.uri)}</a></li>`).join('')}</ul></section>` : '');
    wire();
  };

  const wire = () => {
    host.querySelector('#tw-ay').onchange = async (e) => { d = await api(`${A}?ay=${encodeURIComponent(e.target.value)}`); S.pick = new Set(d.rows.filter((r) => r.state === 'changed').map((r) => r.id)); draw(); };
    if (host.querySelector('#tw-go')) host.querySelector('#tw-go').onclick = async (e) => {
      const btn = e.currentTarget;
      const ay = host.querySelector('#tw-ay').value;
      S.ai = host.querySelector('#tw-ai') ? host.querySelector('#tw-ai').value : '';
      const pick = (S.ais || []).find((a) => a.provider === S.ai) || (S.ais || []).find((a) => a.ready) || {};
      btn.dataset.work = w('fetching', { ai: pick.label || w('ai_auto') });   // the AI actually asked
      try { d = await busy(btn, () => api(`${A}/${encodeURIComponent(ay)}/fetch`, { method: 'POST', body: { provider: S.ai } })); }
      catch (x) { toast(x.message, 'bad', 10); return; }
      S.pick = new Set(d.rows.filter((r) => r.state === 'changed').map((r) => r.id)); draw();
    };
    host.querySelector('#tw-only').onclick = () => { S.only = !S.only; draw(); };
    if (host.querySelector('#tw-do')) host.querySelector('#tw-do').onclick = async (e) => {
      const ids = [...S.pick].filter((id) => d.rows.some((r) => r.id === id && r.state === 'changed'));
      if (!ids.length) return;
      const btn = e.currentTarget;
      confirmDialog(w('title'), w('confirm', { n: ids.length, ay: d.ay }), async () => {
        try {
          const r = await busy(btn, () => api(`${A}/${encodeURIComponent(d.ay)}/apply`, { method: 'POST', body: { ids } }));
          toast(r.done, 'ok', 8);
          if (r.rebased) toast(r.rebased, 'info', 12);
          d = await api(A); S.pick = new Set(); draw();
        } catch (x) { toast(x.message, 'bad', 10); }
      }, w('apply', { n: ids.length, ay: d.ay }), { tone: 'warn' });
    };
    host.querySelectorAll('[data-pick]').forEach((b) => { b.onchange = () => { if (b.checked) S.pick.add(b.dataset.pick); else S.pick.delete(b.dataset.pick); draw(); }; });
    host.querySelectorAll('[data-edit]').forEach((b) => { b.onclick = () => { S.edit = b.dataset.edit; draw(); }; });
    host.querySelectorAll('[data-cancel]').forEach((b) => { b.onclick = () => { S.edit = ''; draw(); }; });
    host.querySelectorAll('[data-save]').forEach((b) => { b.onclick = async () => {
      let value;
      try { value = JSON.parse(host.querySelector('.tw-json').value); } catch { toast(w('bad_json'), 'bad'); return; }
      try { d = await api(`${A}/${encodeURIComponent(d.ay)}/${encodeURIComponent(b.dataset.save)}`, { method: 'PUT', body: { value } }); S.edit = ''; S.pick.add(b.dataset.save); draw(); }
      catch (x) { toast(x.message, 'bad', 8); }
    }; });
  };
  draw();
};
