// History - the change log (2026-10-05 owner: "field name, old value, new value, when, who did - for both information and
// documents ... even earlier versions of a document"; "looks very unprofessional ... no empathy for the user").
// One client's log (any one year, or all) or the firm's own, searched and paged on the server (list.changes). Each save is one
// event - who, where, when - with every field it changed: what it was (struck through) and what it became; a replaced or
// removed document offers its earlier version. Days are grouped. Words: ui.changes. Look: page.changes.
import { api, esc, t, ps, loadWords, modal, BASE } from './app.js';
import { icon } from './icons.js';

const w = (k, v) => t('changes', k, v);
const initials = (s) => String(s || '?').split(/[\s@.]+/).filter(Boolean).slice(0, 2).map((x) => x[0]).join('').toUpperCase();

/** The History button for a screen's header. */
export const historyButton = () => `<button type="button" class="small ghost" data-history>${icon('clock', 13)} ${esc(t('changes', 'open'))}</button>`;

/** Wire every History button in `host` to open the log of client `cid` (year `ay`), or the firm's (`firm`, named `name`). */
export async function wireHistory(host, { cid = '', ay = '', name = '', firm = false } = {}) {
  await loadWords('changes');
  host.querySelectorAll('[data-history]').forEach((b) => { b.onclick = () => openHistory({ cid, ay, name, firm }); });
}

const dayOf = (iso) => new Date(iso).toDateString();
function dayLabel(iso) {
  const d = new Date(iso), today = new Date(), y = new Date(Date.now() - 864e5);
  if (d.toDateString() === today.toDateString()) return w('today');
  if (d.toDateString() === y.toDateString()) return w('yesterday');
  return d.toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
}
const timeOf = (iso) => new Date(iso).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
const val = (v) => (v ? esc(v) : `<span class="ch-blank">${esc(w('blank'))}</span>`);

// one save = one event: the rows sharing a batch, in the order the server gave them
function events(rows) {
  const out = [];
  rows.forEach((r) => {
    const last = out[out.length - 1];
    if (last && r.batch && last.batch === r.batch) last.rows.push(r);
    else out.push({ batch: r.batch, at: r.at, by: r.by, area: r.area_label, ay: r.ay, kind: r.kind, rows: [r] });
  });
  return out;
}

function eventHtml(e) {
  const doc = e.kind === 'doc';
  const r0 = e.rows[0];
  const head = doc ? w(!r0.old ? 'ev_doc_added' : !r0.new ? 'ev_doc_removed' : 'ev_doc_replaced', { who: e.by })
    : w(e.rows.length === 1 ? 'ev_info_one' : 'ev_info', { who: e.by, n: e.rows.length });
  const lines = e.rows.map((r) => {
    const dl = r.file ? `<a class="ch-dl" href="${BASE}/api/changes/file/${encodeURIComponent(r.cid)}/${encodeURIComponent(r.ay)}/${encodeURIComponent(r.file.kept_in)}/${encodeURIComponent(r.file.fid)}/${r.file.v}?name=${encodeURIComponent(r.old)}">
        ${icon('download', 13)} ${esc(w('download', { name: r.old }))}</a>` : '';
    return `<div class="ch-line"><div class="ch-field">${doc ? icon('folder', 14) : ''}${esc(r.field)}</div>
      <div class="ch-vals"><span class="ch-old" title="${esc(w('was'))}">${val(r.old)}</span><span class="ch-arrow" aria-hidden="true">${icon('right', 13)}</span>
        <span class="ch-new" title="${esc(w('now'))}">${val(r.new)}</span></div>${dl}</div>`;
  }).join('');
  return `<article class="ch-ev ch-${esc(e.kind)}"><span class="ch-av" aria-hidden="true">${esc(initials(e.by))}</span>
    <div class="ch-body"><header><b>${esc(head)}</b><span class="ch-meta">${esc(e.area)}${e.ay ? ` · ${esc(e.ay)}` : ''} · ${esc(timeOf(e.at))}</span></header>
      <div class="ch-lines">${lines}</div></div></article>`;
}

export async function openHistory({ cid = '', ay = '', name = '', firm = false } = {}) {
  await loadWords('changes');
  const years = firm ? [] : (await api('/api/clients/settings').catch(() => ({ years: [] }))).years || [];
  const st = { kind: '', ay, q: '', page: 1 };
  const title = firm ? w('title_firm', { firm: name || w('the_firm') }) : w('title_client', { name });
  modal(title, `<p class="ch-lede">${esc(w('lede'))}</p>
    <div class="ch-bar">
      <div class="tabs ch-tabs" role="tablist">${[['', w('all')], ...ps('changes').kinds.map((k) => [k, w(k)])].map(([k, l]) =>
        `<button type="button" role="tab" data-kind="${k}" class="${k ? '' : 'on'}" aria-selected="${!k}">${esc(l)}</button>`).join('')}</div>
      ${years.length ? `<select data-ay aria-label="${esc(w('all_years'))}"><option value="">${esc(w('all_years'))}</option>${years.map((y) =>
        `<option ${y === ay ? 'selected' : ''}>${esc(y)}</option>`).join('')}</select>` : ''}
      <label class="ch-search">${icon('search', 14)}<input type="search" data-q placeholder="${esc(w('search'))}" aria-label="${esc(w('search'))}"/></label>
    </div>
    <div class="ch-count small muted" data-count></div><div data-log class="ch-log"></div><div class="ch-pager" data-pager></div>`, {
    wide: true,
    onOpen: (m) => {
      const log = m.querySelector('[data-log]');
      const load = async () => {
        log.innerHTML = `<div class="ch-state"><span class="spinner"></span></div>`;
        let r;
        try {
          r = await api(`/api/lists/changes?${new URLSearchParams({ ...(firm ? { firm: 1 } : { cid, ay: st.ay }), kind: st.kind, q: st.q, page: st.page })}`);
        } catch (e) {
          log.innerHTML = `<div class="ch-state ch-fail">${icon('alert', 22)}<b>${esc(w('fail_title'))}</b>
            <p>${esc(e.status === 404 ? w('fail_old_server') : w('fail_body', { why: e.message }))}</p>
            <button type="button" class="small" data-retry>${icon('refresh', 13)} ${esc(w('retry'))}</button></div>`;
          m.querySelector('[data-count]').textContent = '';
          m.querySelector('[data-pager]').innerHTML = '';
          log.querySelector('[data-retry]').onclick = load;
          return;
        }
        m.querySelector('[data-count]').textContent = r.total ? w(r.total === 1 ? 'count_one' : 'count', { n: r.total }) : '';
        if (!r.rows.length) {
          log.innerHTML = st.q ? `<div class="ch-state">${icon('search', 22)}<p>${esc(w('no_match'))}</p></div>`
            : `<div class="ch-state ch-empty"><span class="ch-empty-ic">${icon('clock', 26)}</span><b>${esc(w('empty_title'))}</b>
               <p>${esc(w('empty_body', { what: w(firm ? 'empty_firm' : 'empty_client') }))}</p></div>`;
          m.querySelector('[data-pager]').innerHTML = '';
          return;
        }
        let day = '';
        log.innerHTML = events(r.rows).map((e) => {
          const d = dayOf(e.at);
          const sep = d !== day ? `<h4 class="ch-day">${esc(dayLabel(e.at))}</h4>` : '';
          day = d;
          return sep + eventHtml(e);
        }).join('');
        const from = (r.page - 1) * r.page_size + 1;
        m.querySelector('[data-pager]').innerHTML = r.pages > 1 ? `<span class="small muted">${esc(w('showing', { from, to: Math.min(r.total, r.page * r.page_size), total: r.total }))}</span>
          ${r.page > 1 ? `<button type="button" class="small ghost" data-pg="${r.page - 1}">${icon('left', 12)} ${esc(w('prev'))}</button>` : ''}
          ${r.page < r.pages ? `<button type="button" class="small ghost" data-pg="${r.page + 1}">${esc(w('next'))} ${icon('right', 12)}</button>` : ''}` : '';
        m.querySelectorAll('[data-pg]').forEach((b) => { b.onclick = () => { st.page = Number(b.dataset.pg); load(); log.scrollIntoView({ block: 'nearest' }); }; });
      };
      m.querySelectorAll('[data-kind]').forEach((b) => {
        b.onclick = () => {
          st.kind = b.dataset.kind; st.page = 1;
          m.querySelectorAll('[data-kind]').forEach((x) => { x.classList.toggle('on', x === b); x.setAttribute('aria-selected', String(x === b)); });
          load();
        };
      });
      const ys = m.querySelector('[data-ay]');
      if (ys) ys.onchange = () => { st.ay = ys.value; st.page = 1; load(); };
      let timer = 0;
      m.querySelector('[data-q]').oninput = (e) => { clearTimeout(timer); timer = setTimeout(() => { st.q = e.target.value.trim(); st.page = 1; load(); }, 250); };
      load();
    },
  });
}
