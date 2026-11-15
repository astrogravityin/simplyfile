// Screen kit - the one look of every work screen (first built for Shoperative) (owner 2026-11-02: "compact, attractive, intuitive, professional
// narration, elegant and pro, beautiful SVG"). A screen = a hero (a drawn picture, one line, the numbers that matter, its one
// main action), then named blocks, each with ONE action in its head. Adding something opens a form popup (the framework's
// modal: unsaved work is warned about on close) - never an empty form left standing on the page. Empty = a drawing, one line,
// one action. No words live here: every caller passes its words from its own chip.
import { esc, modal, busy, toast } from './ui.js';
import { icon } from './icons.js';

// Drawn pictures, 96 x 96, theme colours only (light and dark), decoration only (aria-hidden).
const ring = '<circle cx="48" cy="48" r="44" fill="var(--brand-soft)"/><circle cx="48" cy="48" r="44" fill="none" stroke="var(--brand-line)"/>';
export const ART = {
  truck: `${ring}<path d="M18 58h8M14 50h10M20 42h6" stroke="var(--brand-line)" stroke-width="3" stroke-linecap="round"/>
    <rect x="30" y="34" width="32" height="26" rx="4" fill="var(--panel)" stroke="var(--brand)" stroke-width="2.5"/>
    <path d="M62 42h10l8 9v9H62Z" fill="var(--brand)" opacity=".9"/><path d="M66 45h5l5 6h-10Z" fill="var(--panel)"/>
    <circle cx="40" cy="62" r="6" fill="var(--panel)" stroke="var(--ink-2)" stroke-width="3"/><circle cx="71" cy="62" r="6" fill="var(--panel)" stroke="var(--ink-2)" stroke-width="3"/>
    <path d="M37 44h18M37 50h12" stroke="var(--brand-line)" stroke-width="3" stroke-linecap="round"/>`,
  cart: `${ring}<path d="M20 28h9l7 30h32l6-21H33" fill="none" stroke="var(--brand)" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
    <rect x="40" y="27" width="11" height="12" rx="2" fill="var(--ok)" opacity=".85"/><rect x="53" y="22" width="12" height="17" rx="2" fill="var(--brand)" opacity=".75"/>
    <rect x="45" y="18" width="9" height="9" rx="2" fill="var(--warn)" opacity=".8"/>
    <path d="M37 48h33" stroke="var(--brand-line)" stroke-width="3" stroke-linecap="round"/>
    <circle cx="41" cy="67" r="5" fill="var(--panel)" stroke="var(--ink-2)" stroke-width="3"/><circle cx="64" cy="67" r="5" fill="var(--panel)" stroke="var(--ink-2)" stroke-width="3"/>`,
  tag: `${ring}<path d="M24 46 46 24h22v22L46 68Z" fill="var(--panel)" stroke="var(--brand)" stroke-width="2.5" stroke-linejoin="round"/>
    <circle cx="60" cy="32" r="4" fill="var(--brand)"/><rect x="36" y="48" width="6" height="8" rx="1.5" fill="var(--brand-line)"/>
    <rect x="44" y="42" width="6" height="14" rx="1.5" fill="var(--brand)" opacity=".7"/><rect x="52" y="36" width="6" height="20" rx="1.5" fill="var(--ok)" opacity=".8" transform="rotate(0)"/>`,
  ledger: `${ring}<rect x="26" y="20" width="36" height="50" rx="4" fill="var(--panel)" stroke="var(--brand)" stroke-width="2.5"/>
    <path d="M33 31h22M33 39h16M33 47h19M33 55h12" stroke="var(--brand-line)" stroke-width="3" stroke-linecap="round"/>
    <circle cx="64" cy="62" r="13" fill="var(--panel)" stroke="var(--warn)" stroke-width="3"/><path d="M64 55v7l5 3" stroke="var(--warn)" stroke-width="3" stroke-linecap="round" fill="none"/>`,
  wallet: `${ring}<rect x="20" y="32" width="52" height="34" rx="6" fill="var(--brand)" opacity=".9"/>
    <path d="M26 32l30-10 4 10" fill="var(--brand-line)"/><rect x="56" y="42" width="20" height="14" rx="4" fill="var(--panel)"/>
    <circle cx="64" cy="49" r="3" fill="var(--warn)"/><circle cx="34" cy="24" r="6" fill="var(--warn)" opacity=".9"/>`,
  box: `${ring}<path d="M48 18 74 30v30L48 74 22 60V30Z" fill="var(--panel)" stroke="var(--brand)" stroke-width="2.5" stroke-linejoin="round"/>
    <path d="M22 30 48 42l26-12M48 42v32" fill="none" stroke="var(--brand-line)" stroke-width="2.5"/><path d="M35 24l26 12v9" fill="none" stroke="var(--warn)" stroke-width="3"/>
    <circle cx="68" cy="66" r="10" fill="var(--ok)"/><path d="M63 66l4 4 6-7" stroke="var(--panel)" stroke-width="3" fill="none" stroke-linecap="round"/>`,
  sheet: `${ring}<rect x="24" y="22" width="40" height="50" rx="4" fill="var(--panel)" stroke="var(--brand)" stroke-width="2.5"/>
    <path d="M24 34h40M24 46h40M24 58h40M38 22v50M51 22v50" stroke="var(--brand-line)" stroke-width="2"/>
    <circle cx="66" cy="64" r="12" fill="var(--brand)"/><path d="M66 70V58m-5 5 5-5 5 5" stroke="var(--panel)" stroke-width="3" fill="none" stroke-linecap="round"/>`,
  people: `${ring}<circle cx="38" cy="38" r="9" fill="var(--brand)" opacity=".85"/><path d="M22 66c2-11 9-16 16-16s14 5 16 16Z" fill="var(--brand)" opacity=".85"/>
    <circle cx="60" cy="42" r="8" fill="var(--ok)" opacity=".8"/><path d="M48 68c2-10 7-14 12-14s11 4 13 14Z" fill="var(--ok)" opacity=".8"/>`,
  lock: `${ring}<rect x="28" y="44" width="40" height="30" rx="6" fill="var(--brand)" opacity=".9"/>
    <path d="M36 44v-8a12 12 0 0 1 24 0v8" fill="none" stroke="var(--brand-line)" stroke-width="5" stroke-linecap="round"/>
    <circle cx="48" cy="57" r="4.5" fill="var(--panel)"/><path d="M48 60v6" stroke="var(--panel)" stroke-width="3" stroke-linecap="round"/>
    <circle cx="70" cy="30" r="9" fill="var(--ok)"/><path d="M66 30l3 3 5-6" stroke="var(--panel)" stroke-width="2.5" fill="none" stroke-linecap="round"/>`,
  checks: `${ring}<rect x="26" y="20" width="44" height="56" rx="6" fill="var(--panel)" stroke="var(--brand)" stroke-width="2.5"/>
    <rect x="38" y="15" width="20" height="10" rx="3" fill="var(--brand)"/>
    <path d="M33 38l4 4 7-8M33 52l4 4 7-8" stroke="var(--ok)" stroke-width="3" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
    <path d="M50 39h12M50 53h12M50 66h12" stroke="var(--brand-line)" stroke-width="3" stroke-linecap="round"/>
    <circle cx="38" cy="66" r="3.5" fill="var(--warn)"/>`,
  records: `${ring}<rect x="22" y="26" width="46" height="34" rx="6" fill="var(--brand-line)"/><rect x="26" y="32" width="46" height="34" rx="6" fill="var(--panel)" stroke="var(--brand)" stroke-width="2.5"/>
    <path d="M34 43h22M34 51h30M34 58h16" stroke="var(--brand-line)" stroke-width="3" stroke-linecap="round"/><circle cx="66" cy="44" r="4" fill="var(--ok)"/>`,
  shelves: `${ring}<path d="M22 34h52M22 52h52M22 70h52" stroke="var(--brand)" stroke-width="3" stroke-linecap="round"/>
    <rect x="28" y="22" width="9" height="12" rx="2" fill="var(--warn)"/><rect x="40" y="18" width="11" height="16" rx="2" fill="var(--brand)" opacity=".8"/>
    <rect x="54" y="40" width="14" height="12" rx="2" fill="var(--ok)" opacity=".85"/><rect x="30" y="42" width="10" height="10" rx="2" fill="var(--brand-line)"/>
    <rect x="44" y="58" width="16" height="12" rx="2" fill="var(--warn)" opacity=".8"/>`,
  scale: `${ring}<path d="M48 22v44M30 30h36" stroke="var(--brand)" stroke-width="3" stroke-linecap="round"/>
    <path d="M24 50l6-20 6 20Z" fill="none" stroke="var(--ink-2)" stroke-width="2"/><path d="M60 50l6-20 6 20Z" fill="none" stroke="var(--ink-2)" stroke-width="2"/>
    <path d="M22 50a8 5 0 0 0 16 0Z" fill="var(--warn)"/><path d="M58 50a8 5 0 0 0 16 0Z" fill="var(--ok)"/><rect x="36" y="66" width="24" height="6" rx="3" fill="var(--brand)"/>`,
  sun: `${ring}<circle cx="48" cy="50" r="15" fill="var(--warn)" opacity=".9"/>
    <path d="M48 24v6M48 70v6M22 50h6M68 50h6M30 32l4 4M62 64l4 4M30 68l4-4M62 36l4-4" stroke="var(--warn)" stroke-width="3" stroke-linecap="round"/>
    <path d="M18 76h60" stroke="var(--brand-line)" stroke-width="3" stroke-linecap="round"/>`,
};
export const art = (k, px = 84) => `<svg class="sk-art" width="${px}" height="${px}" viewBox="0 0 96 96" aria-hidden="true">${ART[k] || ''}</svg>`;

/** Paise as rupees in the screen's own money words (chip ui.<screen> money = "₹{n}"). */
export const moneyIn = (w) => (p) => w('money', { n: (Number(p || 0) / 100).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) });

/** The hero: picture, title, one line, the numbers that matter (tone ok | warn | bad | brand), and its one main action. */
export function hero({ id = '', pic, title, line = '', stats = [], action = '' }) {
  return `<section class="card sk-hero" ${id ? `id="${esc(id)}"` : ''}>${art(pic)}
    <div class="sk-txt"><h2>${esc(title)}</h2>${line ? `<p>${esc(line)}</p>` : ''}${action ? `<div class="sk-act">${action}</div>` : ''}</div>
    ${stats.length ? `<dl class="sk-stats">${stats.map((s) => `<div class="sk-stat t-${esc(s.tone || '')}${String(s.value).length > 12 ? ' sk-wide' : ''}"${s.id ? ` id="${esc(s.id)}"` : ''}><dt>${esc(s.label)}</dt><dd>${esc(s.value)}</dd>${s.sub ? `<small>${esc(s.sub)}</small>` : ''}</div>`).join('')}</dl>` : ''}</section>`;
}

/** A named block: title, one short line, ONE action in the head, then its body. */
export function block({ id = '', title, sub = '', action = '', body = '', cls = '' }) {
  return `<section class="card sk-block ${esc(cls)}" ${id ? `id="${esc(id)}"` : ''}><header class="sk-head"><div><h3>${esc(title)}</h3>${sub ? `<p>${esc(sub)}</p>` : ''}</div>${action}</header>${body}</section>`;
}

/** Empty, designed: a drawing, a title, one line, one action. */
export const empty = (pic, title, line = '', action = '') => `<div class="sk-empty">${art(pic, 72)}<b>${esc(title)}</b>${line ? `<span>${esc(line)}</span>` : ''}${action}</div>`;

/** A head button that opens a form (the block's one action). */
export const addBtn = (id, label, ico = 'plus') => `<button type="button" class="small primary" id="${esc(id)}">${icon(ico, 13)} ${esc(label)}</button>`;

/** A labelled field for a form popup. `unit` sits inside the box (₹, km, days), so a label never carries it. */
export function field(id, label, { type = 'text', value = '', unit = '', hint = '', attrs = '', options = null } = {}) {
  const box = options
    ? `<select id="${esc(id)}">${options.map((o) => `<option value="${esc(o.value)}" ${String(o.value) === String(value) ? 'selected' : ''}>${esc(o.label)}</option>`).join('')}</select>`
    : `<input id="${esc(id)}" type="${esc(type)}" value="${esc(value)}" ${attrs}/>`;
  return `<div class="field"><label for="${esc(id)}">${esc(label)}</label>${unit ? `<span class="sk-unit">${box}<i>${esc(unit)}</i></span>` : box}${hint ? `<span class="small muted">${esc(hint)}</span>` : ''}</div>`;
}

/** A form popup: fields in a two-column grid, Save in the footer. `send(card)` returns the API promise; a closed popup with
 *  typed work asks first (the framework modal). */
export function formPopup(title, fieldsHtml, saveLabel, send, { done = '', lede = '' } = {}) {
  modal(title, `${lede ? `<p class="muted small">${esc(lede)}</p>` : ''}<div class="grid two sk-form">${fieldsHtml}</div>`, {
    footer: `<button type="button" class="primary" data-save>${icon('save', 14)} ${esc(saveLabel)}</button>`,
    onOpen: (b, close) => {
      const card = b.closest('.modal');
      const first = card.querySelector('input,select');
      if (first) first.focus();
      card.querySelector('[data-save]').onclick = (e) => busy(e.currentTarget, () => send(card)
        .then(() => { if (done) toast(done, 'ok'); close(true); })
        .catch((err) => toast(err.message, 'bad', 8)));
    },
  });
}

/** Days from today to an ISO day (negative = past). */
export const daysTo = (iso) => Math.round((new Date(`${iso}T00:00:00`) - new Date(new Date().toDateString())) / 864e5);

/** Initials in a soft disc, for a person or a firm. */
export const badge = (name) => `<span class="sk-badge" aria-hidden="true">${esc(String(name || '?').split(/\s+/).slice(0, 2).map((x) => x[0]).join('').toUpperCase() || '?')}</span>`;

/** An icon in the soft disc (an order, a payment, a distance band). */
export const iconBadge = (ico, tone = '') => `<span class="sk-badge${tone ? ` t-${esc(tone)}` : ''}" aria-hidden="true">${icon(ico, 15)}</span>`;

/** An ISO day as people say it: "5 Nov" (this year) or "5 Nov 2027". */
export function day(iso) {
  if (!iso) return '';
  const d = new Date(`${String(iso).slice(0, 10)}T00:00:00`);
  if (Number.isNaN(d.getTime())) return String(iso);
  return d.toLocaleDateString('en-IN', d.getFullYear() === new Date().getFullYear() ? { day: 'numeric', month: 'short' } : { day: 'numeric', month: 'short', year: 'numeric' });
}

/** "1 item" / "3 items": the words chip holds `<key>_one` for one and `<key>` for the rest. */
export const count = (w, key, n) => w(Number(n) === 1 ? `${key}_one` : key, { n });

/** When, as people say it: "just now", "5 min ago", "2 h ago", then "5 Nov". Words from the caller's chip: ago_now, ago_min, ago_h. */
export function ago(w, iso) {
  if (!iso) return '';
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (Number.isNaN(s)) return String(iso);
  return s < 60 ? w('ago_now') : s < 3600 ? w('ago_min', { n: Math.floor(s / 60) }) : s < 86400 ? w('ago_h', { n: Math.floor(s / 3600) }) : day(iso);
}

/** A family tree of rows [{id, parent, label, sub, tag, muted}] as one SVG (2026-11-15 Access Control groups; any
 * parent/child list may use it). Indented rows with elbow lines, built for a phone's width and scaled up to `max` on a
 * laptop; colours are the shared wt-s0..6 palette by depth, so dark mode follows. A row whose parent is missing (or a
 * loop) starts at the top level. Words are escaped and shortened to fit their row. */
export function treeSvg(rows, { max = 440, rowH = 40, indent = 22, width = 380, label = '' } = {}) {
  const ids = new Set(rows.map((r) => r.id));
  const kids = (pid) => rows.filter((r) => (ids.has(r.parent) ? r.parent : '') === pid);
  const out = [];
  const walk = (pid, depth, seen) => kids(pid).forEach((r) => {
    if (seen.has(r.id)) return;
    out.push({ ...r, depth });
    walk(r.id, depth + 1, new Set([...seen, r.id]));
  });
  walk('', 0, new Set());
  const at = Object.fromEntries(out.map((r, i) => [r.id, i]));
  const fit = (s, px) => { const n = Math.max(4, Math.floor(px / 7.2)); s = String(s || ''); return s.length > n ? `${s.slice(0, n - 1)}…` : s; };
  const h = out.length * rowH + 8;
  const lines = out.filter((r) => r.depth).map((r) => {
    const px = 14 + (r.depth - 1) * indent; const py = at[r.parent] * rowH + rowH / 2 + 4;
    const y = at[r.id] * rowH + rowH / 2 + 4; const x = 8 + r.depth * indent;
    return `<path d="M${px} ${py + 9}V${y - 6}q0 6 6 6H${x}" fill="none" stroke="var(--line-2)" stroke-width="1.5"/>`;
  }).join('');
  const nodes = out.map((r, i) => {
    const x = 8 + r.depth * indent; const y = i * rowH + 4; const w = width - x - 4; const cy = y + rowH / 2;
    const tag = r.tag ? fit(r.tag, 90) : '';
    const tagW = tag ? tag.length * 6.4 + 14 : 0;
    const sub = fit(r.sub, Math.max(0, w - 40 - tagW - Math.min(String(r.label || '').length, 22) * 7.6));
    return `<g class="tr-row${r.muted ? ' tr-muted' : ''}"><rect x="${x}" y="${y + 4}" width="${w}" height="${rowH - 8}" rx="9" fill="var(--panel)" stroke="var(--line)"/>
      <circle cx="${x + 14}" cy="${cy}" r="5" fill="none" stroke-width="3" class="wt-s${r.depth % 7}"/>
      <text x="${x + 27}" y="${cy + 4.5}" font-size="13" font-weight="650" fill="var(--ink)">${esc(fit(r.label, w - 40 - tagW))}<tspan dx="8" font-size="11.5" font-weight="400" fill="var(--muted)">${esc(sub)}</tspan></text>
      ${tag ? `<rect x="${x + w - tagW - 8}" y="${cy - 9}" width="${tagW}" height="18" rx="9" fill="var(--brand-soft)" stroke="var(--brand-line)"/>
      <text x="${x + w - tagW / 2 - 8}" y="${cy + 3.8}" font-size="10.5" font-weight="600" text-anchor="middle" fill="var(--brand)">${esc(tag)}</text>` : ''}</g>`;
  }).join('');
  return `<svg class="tr-svg" viewBox="0 0 ${width} ${h}" style="width:100%;max-width:${max}px" role="img" aria-label="${esc(label)}">${lines}${nodes}</svg>`;
}

/** A donut of slices (pct of the whole); colours wt-s0..6 from the stylesheet. */
export const donut = (slices) => {
  let at = 0;
  return `<svg viewBox="0 0 42 42" class="wt-donut" aria-hidden="true"><circle cx="21" cy="21" r="15.9" fill="none" stroke="var(--line)" stroke-width="6"/>${slices.map((x, i) => {
    const arc = `<circle cx="21" cy="21" r="15.9" fill="none" class="wt-s${i % 7}" stroke-width="6" stroke-dasharray="${x.pct} ${100 - x.pct}" stroke-dashoffset="${-at}" transform="rotate(-90 21 21)"/>`;
    at += x.pct;
    return arc;
  }).join('')}</svg>`;
};
