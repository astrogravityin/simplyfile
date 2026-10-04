// Reconcile - SimplyFile phase 3. #/recon?c=<client>&ay=<AY>: the portal files (26AS / AIS / TIS) for the year, and every
// finding of books against portal - red first, then amber, then what agrees. Red and amber take an Explain note; an
// unexplained red keeps the year out of Review (chip recon.settings block_stages; the server counts open_red).
// Words: chip ui.recon. Checks, colours, which findings count as cleared, the source slots: chip page.recon.
import { api, esc, toast, busy, pageHead, confirmDialog, t, ps, loadWords, uploadBox, modal, when, may } from './app.js';
import { clientPicker } from './page-intake.js';
import { icon } from './icons.js';
import { historyButton, wireHistory } from './changes.js';

const w = (k, v) => t('recon', k, v);
const P = () => ps('recon');
const money = (n) => Number(n || 0).toLocaleString(ps('intake').money_locale, { maximumFractionDigits: 0 });
const cleared = (f) => P().cleared_severities.includes(f.severity) || (P().explained_clears && !!f.note);
const checkOf = (f) => P().checks.find((c) => c.kinds.includes(f.kind)) || { id: f.kind, icon: 'info' };
let SEV = '';       // the findings filter: '' = all, else one severity

// The readiness ring: one arc per severity (chip colours), the share cleared in the middle.
function ring(d) {
  const R = 34, L = 2 * Math.PI * R, n = d.findings.length || 1;
  let at = 0;
  const arcs = Object.keys(P().severity_color).filter((s) => d.summary[s]).map((s) => {
    const len = (d.summary[s] / n) * L;
    const a = `<circle r="${R}" cx="44" cy="44" fill="none" stroke="var(${P().severity_color[s]})" stroke-width="10"
      stroke-dasharray="${len.toFixed(2)} ${(L - len).toFixed(2)}" stroke-dashoffset="${(-at).toFixed(2)}"/>`;
    at += len;
    return a;
  }).join('');
  const pct = d.findings.length ? Math.round((d.findings.filter(cleared).length / d.findings.length) * 100) : 0;
  return `<svg class="rc-ring" viewBox="0 0 88 88" role="img" aria-label="${pct}% ${esc(w('cleared'))}">
    <circle r="${R}" cx="44" cy="44" fill="none" stroke="var(--line)" stroke-width="10"/>
    <g transform="rotate(-90 44 44)">${arcs}</g>
    <text x="44" y="44" text-anchor="middle" class="rc-ring-pct">${pct}%</text>
    <text x="44" y="58" text-anchor="middle" class="rc-ring-sub">${esc(w('cleared'))}</text></svg>`;
}

// A stacked severity bar for one check (each bar clips its own rounded ends).
let clipN = 0;
function sevBar(list) {
  if (!list.length) return '<svg class="rc-sevbar" width="100%" height="6"><rect width="100%" height="6" rx="3" fill="var(--line)"/></svg>';
  let x = 0;
  const segs = Object.keys(P().severity_color).map((s) => {
    const k = list.filter((f) => f.severity === s).length;
    if (!k) return '';
    const wd = (k / list.length) * 100;
    const r = `<rect x="${x}%" width="${wd}%" height="6" fill="var(${P().severity_color[s]})"/>`;
    x += wd;
    return r;
  }).join('');
  const id = `rc-clip-${++clipN}`;
  return `<svg class="rc-sevbar" width="100%" height="6"><defs><clipPath id="${id}"><rect width="100%" height="6" rx="3"/></clipPath></defs>
    <g clip-path="url(#${id})">${segs}</g></svg>`;
}

// Books against portal as two bars on one scale - the gap is what the finding is about.
function compare(f) {
  const a = f.amounts || {};
  if (!('books' in a) && !('portal' in a)) return '<div></div>';
  const top = Math.max(a.books || 0, a.portal || 0) || 1;
  const bar = (label, v, tone) => `<div class="rc-cmp-row"><span>${esc(label)}</span>
    <svg width="100%" height="8" preserveAspectRatio="none"><rect width="100%" height="8" rx="4" fill="var(--panel-2)"/>
      ${v ? `<rect width="${Math.max(1.5, (v / top) * 100)}%" height="8" rx="4" fill="var(${tone})"/>` : ''}</svg>
    <b>${money(v)}</b></div>`;
  return `<div class="rc-cmp">${bar(w('books'), a.books, '--brand')}${bar(w('portal'), a.portal, P().severity_color[f.severity])}</div>`;
}

// A file's mark: a page with a folded corner and the source name on it.
const docMark = (label, tone) => `<svg class="rc-doc" width="34" height="40" viewBox="0 0 34 40" aria-hidden="true">
  <path d="M4 2h18l10 10v24a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2Z" fill="var(--panel)" stroke="var(${tone})" stroke-width="1.6"/>
  <path d="M22 2v8a2 2 0 0 0 2 2h8" fill="none" stroke="var(${tone})" stroke-width="1.6"/>
  <rect x="5" y="24" width="24" height="10" rx="3" fill="var(${tone})"/>
  <text x="17" y="31.6" text-anchor="middle" class="rc-doc-t">${esc(label)}</text></svg>`;

export async function reconPage(host) {
  await loadWords('recon', 'intake', 'changes');
  const p = new URLSearchParams((location.hash.split('?')[1]) || '');
  if (!p.get('c')) return clientPicker(host, 'recon');
  const K = await api('/api/clients/settings');
  const cid = p.get('c');
  const ay = p.get('ay') || K.current_ay;
  const base = `/api/recon/${encodeURIComponent(cid)}/${encodeURIComponent(ay)}`;
  const client = await api(`/api/clients/${encodeURIComponent(cid)}`);
  host.innerHTML = pageHead(`${w('title')} · ${client.name}`, esc(w('lede')),
    `<label class="cl-ay" for="rc-ay">${icon('clock', 14)}<span>${esc(w('ay'))}</span>
       <select id="rc-ay">${K.years.map((y) => `<option ${y === ay ? 'selected' : ''}>${esc(y)}</option>`).join('')}</select></label>
     ${historyButton()}<button type="button" class="primary" id="rc-up">${icon('upload', 15)} ${esc(w('upload'))}</button>`)
    + `<section class="card rc-hero" id="rc-hero"></section>
       <section class="card"><h3 class="rc-h">${icon('folder', 15)} ${esc(w('sources'))}</h3><div class="rc-src" id="rc-files"></div></section>
       <section class="card"><div class="rc-find-head"><h3 class="rc-h">${icon('check', 15)} ${esc(w('findings'))}</h3><div class="tabs rc-tabs" role="tablist" id="rc-tabs"></div></div>
         <input type="search" id="rc-q" class="mp-find" placeholder="${esc(w('find_findings'))}" aria-label="${esc(w('find_findings'))}"/>
         <div id="rc-find"></div></section>`;
  wireHistory(host, { cid, ay, name: client.name });
  host.querySelector('#rc-ay').onchange = (e) => { location.hash = `#/recon?c=${encodeURIComponent(cid)}&ay=${encodeURIComponent(e.target.value)}`; };

  const draw = (d) => {
    const S = P();
    // Hero: the ring, the verdict the server's open_red gives, one tile per check.
    const verdict = !d.findings.length ? ['', w('verdict_none'), 'info']
      : d.open_red ? ['is-bad', w('verdict_block', { n: d.open_red }), 'alert'] : ['is-ok', w('verdict_ready'), 'shield'];
    host.querySelector('#rc-hero').innerHTML = `${ring(d)}
      <div class="rc-verdict ${verdict[0]}"><span class="rc-v-ic">${icon(verdict[2], 18)}</span><div><b>${esc(verdict[1])}</b>
        <div class="small muted">${esc(w('verdict_sub', d))}</div></div></div>
      <div class="rc-checks">${S.checks.map((c) => {
        const list = d.findings.filter((f) => c.kinds.includes(f.kind));
        const red = list.filter((f) => f.severity === 'red' && !f.note).length;
        return `<div class="rc-check"><div class="rc-check-top">${icon(c.icon, 15)}<span>${esc(w(`check_${c.id}`))}</span>
          <b class="${red ? 'rc-n-bad' : ''}">${list.length}</b></div>${sevBar(list)}</div>`;
      }).join('')}</div>`;

    // Portal files: one slot per source in the chip, each with its files or an empty slot saying where to get it.
    const files = host.querySelector('#rc-files');
    const slot = (src, list) => `<div class="rc-slot ${list.length ? '' : 'is-empty'}">${docMark(w(`src_${src}`), list.length ? '--brand' : '--line-2')}
      <div class="rc-slot-body"><b>${esc(w(`src_${src}`))}</b>${list.length ? list.map((f) => `<div class="rc-file" data-f="${esc(f.id)}" data-name="${esc(f.name)}">
          <span class="rc-file-name" title="${esc(f.name)}">${esc(f.name)}</span>
          <span class="small muted">${esc(w('n_entries', { n: f.entries }))} · ${esc(when(f.uploaded_at))}</span>
          ${f.pan_seen ? '' : `<span class="tag warn">${icon('alert', 11)} ${esc(w('pan_missing'))}</span>`}
          ${may('recon', 'delete') ? `<button type="button" class="small ghost" data-del aria-label="${esc(w('delete'))}">${icon('trash', 12)}</button>` : ''}</div>`).join('')
        : `<div class="small muted">${esc(w('not_uploaded'))}</div><div class="rc-hint">${esc(w(`hint_${src}`))}</div>`}</div></div>`;
    const known = new Set(S.sources);
    const other = d.files.filter((f) => !known.has(f.source));
    files.innerHTML = S.sources.map((s) => slot(s, d.files.filter((f) => f.source === s))).join('')
      + (other.length ? slot('other', other) : '');
    files.querySelectorAll('[data-f]').forEach((el) => {
      const del = el.querySelector('[data-del]');
      if (del) del.onclick = () => confirmDialog(w('delete_title', { name: el.dataset.name }), w('delete_body'), async () => {
        try { await api(`${base}/${el.dataset.f}`, { method: 'DELETE' }); toast(w('deleted'), 'ok'); load(); }
        catch (err) { toast(err.message, 'bad', 8); }
      }, w('delete'), { tone: 'danger' });
    });

    // Findings: a severity filter, then one group per check.
    host.querySelector('#rc-tabs').innerHTML = [['', w('f_all'), d.findings.length], ...Object.keys(S.severity_color).map((s) => [s, w(`sev_${s}`), d.summary[s] || 0])]
      .map(([id, label, n]) => `<button type="button" role="tab" data-sev="${id}" class="${SEV === id ? 'on' : ''}">${id ? `<i class="rc-dot" style="background:var(${S.severity_color[id]})"></i>` : ''}${esc(label)}<span class="cl-count">${n}</span></button>`).join('');
    host.querySelectorAll('[data-sev]').forEach((b) => { b.onclick = () => { SEV = b.dataset.sev; draw(d); }; });
    host.querySelector('#rc-q').oninput = () => draw(d);
    // the find box: every word typed must be in the finding - its title, note, kind or an amount
    const words = host.querySelector('#rc-q').value.toLowerCase().split(/\s+/).filter(Boolean);
    const hay = (f) => `${f.title} ${f.note || ''} ${f.kind} ${Object.values(f.amounts || {}).join(' ')}`.toLowerCase();
    const shown = d.findings.filter((f) => (!SEV || f.severity === SEV) && words.every((t) => hay(f).includes(t)));
    const find = host.querySelector('#rc-find');
    find.innerHTML = !d.findings.length ? `<div class="rc-empty">${icon('upload', 22)}<p>${esc(w('nothing'))}</p></div>`
      : !shown.length ? `<div class="rc-empty">${icon('check', 22)}<p>${esc(w(words.length ? 'no_findings_match' : 'none_here'))}</p></div>`
      : S.checks.map((c) => {
        const list = shown.filter((f) => checkOf(f).id === c.id);
        return list.length ? `<div class="rc-group"><div class="rc-group-h">${icon(c.icon, 13)} ${esc(w(`check_${c.id}`))}<span>${list.length}</span></div>
          ${list.map((f) => `<div class="rc-f sev-${esc(f.severity)}" data-id="${esc(f.id)}" style="--sev:var(${S.severity_color[f.severity]})">
            <div class="rc-f-main"><div class="rc-f-title"><span class="${esc(S.severity_tag[f.severity])}">${esc(w(`sev_${f.severity}`))}</span>
              ${f.note ? `<span class="tag ok">${icon('check', 11)} ${esc(w('explained_tag'))}</span>` : ''}<span>${esc(f.title)}</span></div>
              ${f.note ? `<div class="rc-note">${icon('chat', 12)} ${esc(w('explained', f.note))}</div>` : ''}</div>
            ${compare(f)}
            <div class="rc-f-act">${f.severity !== 'ok' ? `<button type="button" class="small" data-explain>${icon('edit', 12)} ${esc(w('explain'))}</button>` : ''}</div></div>`).join('')}</div>` : '';
      }).join('');
    find.querySelectorAll('[data-explain]').forEach((b) => {
      const f = d.findings.find((x) => x.id === b.closest('[data-id]').dataset.id);
      b.onclick = () => modal(w('explain_title'), `<p class="small">${esc(f.title)}</p><div class="field"><label for="rc-note">${esc(w('explain_hint'))}</label>
          <textarea id="rc-note" rows="3">${esc(f.note ? f.note.text : '')}</textarea></div>`, {
        footer: `<button type="button" class="primary" data-save>${icon('save', 14)} ${esc(w('save'))}</button>`,
        onOpen: (m, close) => {
          m.closest('.modal').querySelector('[data-save]').onclick = (e) => busy(e.currentTarget, async () => {
            try {
              draw(await api(`${base}/notes/${f.id}`, { method: 'PUT', body: { note: m.querySelector('#rc-note').value } }));
              toast(w('saved'), 'ok'); close(true);
            } catch (err) { toast(err.message, 'bad', 8); }
          });
        } });
    });
  };
  const load = async () => draw(await api(base));
  host.querySelector('#rc-up').onclick = () => uploadBox(w('upload'), P().exts, base, load);
  load();
}
