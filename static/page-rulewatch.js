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
    case 'money_by_age': case 'money_by_regime': case 'money_map': case 'pct_by_regime':
      return Object.entries(v).map(([k, x]) => `<span class="tw-slab${other ? diff(x, other[k]) : ''}">${esc(named(k))} <b>${esc(kind === 'pct_by_regime' ? `${x}%` : L(x))}</b></span>`).join('');
    default: return `<code>${esc(JSON.stringify(v))}</code>`;
  }
}

export const rulewatchPage = (name) => async (host) => {
  w = (k, v) => t(name, k, v);
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
          <td>${S.edit === r.id ? `<textarea class="tw-json" rows="5">${esc(JSON.stringify(r.new ?? r.live, null, 1))}</textarea>
                <div class="tw-ed"><button class="btn sm primary" data-save="${esc(r.id)}">${esc(w('save'))}</button><button class="btn sm ghost" data-cancel>${esc(w('cancel'))}</button></div>`
            : `${show(r.kind, r.new, r.live)}<div class="tw-state"><span class="sv-pill" style="--c:var(${tone[r.state]})">${esc(w(r.state))}</span>${r.edited ? ` <span class="small muted">${esc(w('edited'))}</span>` : ''}
                ${can ? `<button class="link small" data-edit="${esc(r.id)}">${esc(w('edit'))}</button>` : ''}</div>${r.note ? `<div class="small muted">${esc(r.note)}</div>` : ''}`}</td>
          <td>${r.source ? `<a class="small" href="${esc(r.source)}" target="_blank" rel="noopener noreferrer">${esc(r.source.replace(/^https?:\/\//, '').slice(0, 40))}</a>` : ''}</td>
          <td class="num">${can && r.state === 'changed' ? `<input type="checkbox" data-pick="${esc(r.id)}" ${S.pick.has(r.id) ? 'checked' : ''} aria-label="${esc(r.label)}">` : ''}</td></tr>`).join('')}`).join('')}
        </tbody></table></div>
        ${can ? `<div class="tw-apply" id="tw-apply"><button class="btn primary" id="tw-do" ${picked.length ? '' : 'disabled'}>${icon('check', 14)} ${esc(picked.length ? w('apply', { n: picked.length, ay: d.ay }) : w('apply_none'))}</button></div>` : ''}</section>`
      + (d.fetched ? `<section class="card"><h3 class="rc-h">${icon('alert', 15)} ${esc(w('new_h'))}</h3><p class="small muted">${esc(w('new_p'))}</p>
          ${(d.new_rules || []).length ? `<ul class="tw-new">${d.new_rules.map((x) => `<li><b>${esc(x.what)}</b>${x.who ? ` <span class="small muted">${esc(w('new_who', { who: x.who }))}</span>` : ''}${/^https?:\/\//.test(x.source) ? ` <a class="small" href="${esc(x.source)}" target="_blank" rel="noopener noreferrer">${icon('external', 11)}</a>` : ''}</li>`).join('')}</ul>`
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
