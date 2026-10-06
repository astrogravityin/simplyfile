// My return's pictures - hand-drawn SVG, coloured only by the portal's tokens (light and dark follow on their own).
// stepper: the five steps as a path; docArt: a document with its kind's mark; waterfall: income to tax to refund;
// regimeBars: the two regimes side by side; tdsMap: each employer's TDS joined to the credit 26AS shows.
// Every word arrives as an argument (chip ui.myreturn); nothing here is text of its own.
import { esc } from './app.js';

const money = (n) => `₹${Math.round(Number(n || 0)).toLocaleString('en-IN')}`;
const short = (n) => { const a = Math.abs(n); const s = n < 0 ? '−' : ''; return a >= 1e7 ? `${s}₹${(a / 1e7).toFixed(2)} Cr` : a >= 1e5 ? `${s}₹${(a / 1e5).toFixed(2)} L` : `${s}${money(a)}`; };

/** steps: [{id, label}], now: id, done: {id: bool}. A path with a node per step; done nodes ticked, the current one ringed. */
export function stepper(steps, now, done, W = 720) { const gap = W / steps.length; const y = 30;
  const nodes = steps.map((s, i) => {
    const x = gap * i + gap / 2; const isDone = done[s.id] && s.id !== now; const isNow = s.id === now;
    return `<g class="mr-node ${isDone ? 'is-done' : ''} ${isNow ? 'is-now' : ''}" data-step="${esc(s.id)}" tabindex="0" role="button" aria-label="${esc(s.label)}">
      ${isNow ? `<circle cx="${x}" cy="${y}" r="21" class="mr-halo"/>` : ''}
      <circle cx="${x}" cy="${y}" r="15" class="mr-dot"/>
      ${isDone ? `<path d="M${x - 6} ${y} l4 4 l8 -9" class="mr-tick"/>` : `<text x="${x}" y="${y + 4.5}" class="mr-num">${i + 1}</text>`}
      <text x="${x}" y="${y + 40}" class="mr-lab">${esc(s.label)}</text></g>`;
  }).join('');
  const reached = Math.max(0, steps.findIndex((s) => s.id === now));
  return `<svg class="mr-stepper" viewBox="0 0 ${W} 82" role="list" aria-label="steps">
    <line x1="${gap / 2}" y1="${y}" x2="${W - gap / 2}" y2="${y}" class="mr-rail"/>
    <line x1="${gap / 2}" y1="${y}" x2="${gap / 2 + gap * reached}" y2="${y}" class="mr-rail-on"/>${nodes}</svg>`;
}

const MARKS = {
  prefill: '<path d="M30 40 h20 M30 47 h14 M30 54 h17" class="mr-ln"/><path d="M52 52 l5 5 l9 -11" class="mr-ok-ln"/>',
  ais: '<rect x="29" y="38" width="7" height="18" rx="1.5" class="mr-fill-2"/><rect x="39" y="44" width="7" height="12" rx="1.5" class="mr-fill"/><rect x="49" y="34" width="7" height="22" rx="1.5" class="mr-fill-2"/>',
  form16: '<text x="44" y="53" class="mr-glyph">16</text><path d="M30 60 h28" class="mr-ln"/>',
  '26as': '<circle cx="44" cy="46" r="10" class="mr-ring"/><path d="M39 46 l4 4 l7 -8" class="mr-ok-ln"/>',
  other: '<path d="M30 40 h26 M30 47 h26 M30 54 h18" class="mr-ln"/>',
};
/** A document, its corner folded, with its kind's mark - drawn lit when read. */
export function docArt(kind, lit) {
  return `<svg class="mr-doc ${lit ? 'is-lit' : ''}" viewBox="0 0 88 88" aria-hidden="true">
    <path d="M22 14 h32 l14 14 v46 a4 4 0 0 1 -4 4 h-42 a4 4 0 0 1 -4 -4 v-56 a4 4 0 0 1 4 -4z" class="mr-sheet"/>
    <path d="M54 14 v10 a4 4 0 0 0 4 4 h10" class="mr-fold"/>${MARKS[kind] || MARKS.other}</svg>`;
}

/** rows: [{label, value, kind: 'start'|'minus'|'plus'|'total'|'end'}] - a bridge from gross income to the balance. */
export function waterfall(rows, W = 720) {
  if (!rows.length) return '';
  if (W < 520) return bridgeRows(rows, W);
  const H = 260; const top = 18; const base = 200; const bw = Math.min(64, (W - 40) / rows.length - 14);
  let run = 0; const pts = rows.map((r) => {
    const from = r.kind === 'minus' ? run : r.kind === 'plus' ? run : 0;
    const to = r.kind === 'minus' ? run - r.value : r.kind === 'plus' ? run + r.value : r.value;
    if (r.kind !== 'end') run = r.kind === 'total' || r.kind === 'start' ? r.value : to;
    return { ...r, from, to };
  });
  const hi = Math.max(1, ...pts.map((p) => Math.max(Math.abs(p.from), Math.abs(p.to))));
  const yOf = (v) => base - (Math.max(0, v) / hi) * (base - top);
  const step = (W - 40) / rows.length;
  const bars = pts.map((p, i) => {
    const x = 20 + step * i + (step - bw) / 2; const y1 = yOf(Math.max(p.from, p.to)); const y2 = yOf(Math.min(p.from, p.to));
    const h = Math.max(2, y2 - y1);
    const link = i < pts.length - 1 && p.kind !== 'end' ? `<line x1="${x + bw}" x2="${x + step}" y1="${yOf(p.to)}" y2="${yOf(p.to)}" class="mr-link"/>` : '';
    return `<g class="mr-bar k-${p.kind}"><rect x="${x}" y="${y1}" width="${bw}" height="${h}" rx="5"/>${link}
      <text x="${x + bw / 2}" y="${y1 - 6}" class="mr-val">${esc(p.kind === 'minus' ? `−${short(p.value).replace('−', '')}` : short(p.value))}</text>
      <text x="${x + bw / 2}" y="${base + 18}" class="mr-cap">${esc(p.label)}</text></g>`;
  }).join('');
  return `<svg class="mr-water" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(rows.map((r) => `${r.label} ${money(r.value)}`).join(', '))}">
    <line x1="14" x2="${W - 14}" y1="${base}" y2="${base}" class="mr-axis"/>${bars}</svg>`;
}

/** The same bridge for a narrow screen: one row per step, each bar floating from where the last one ended. */
function bridgeRows(rows, W) {
  let run = 0; const pts = rows.map((r) => {
    const from = r.kind === 'minus' || r.kind === 'plus' ? run : 0;
    const to = r.kind === 'minus' ? run - r.value : r.kind === 'plus' ? run + r.value : r.value;
    if (r.kind !== 'end') run = r.kind === 'total' || r.kind === 'start' ? r.value : to;
    return { ...r, from, to };
  });
  const hi = Math.max(1, ...pts.map((p) => Math.max(p.from, p.to))); const lab = 96; const room = W - lab - 8; const rh = 40;
  const xOf = (v) => lab + (Math.max(0, v) / hi) * room;
  const bars = pts.map((p, i) => {
    const y = 8 + i * rh; const x1 = xOf(Math.min(p.from, p.to)); const w = Math.max(3, xOf(Math.max(p.from, p.to)) - x1);
    return `<g class="mr-bar k-${p.kind}"><text x="0" y="${y + 15}" class="mr-cap mr-cap-l">${esc(p.label)}</text>
      <rect x="${x1}" y="${y + 2}" width="${w}" height="18" rx="5"/>
      <text x="0" y="${y + 31}" class="mr-val mr-val-l">${esc(p.kind === 'minus' ? `−${short(p.value).replace('−', '')}` : short(p.value))}</text></g>`;
  }).join('');
  return `<svg class="mr-water" viewBox="0 0 ${W} ${pts.length * rh + 12}" role="img" aria-label="${esc(rows.map((r) => `${r.label} ${money(r.value)}`).join(', '))}">${bars}</svg>`;
}

/** Two regimes: {new, old} each {label, tax}; better: 'new'|'old'. Horizontal bars, the cheaper one marked. */
export function regimeBars(a, b, better, words, W = 720) {
  const hi = Math.max(1, a.tax, b.tax); const narrow = W < 520;
  const lab = narrow ? 0 : 150; const room = W - lab - (narrow ? 96 : 260);
  const row = (r, id, y) => {
    const w = Math.max(6, (r.tax / hi) * room); const by = narrow ? y + 18 : y;
    return `<g class="mr-rg ${better === id ? 'is-best' : ''}"><text x="0" y="${narrow ? y + 12 : y + 21}" class="mr-rg-lab">${esc(r.label)}</text>
      <rect x="${lab}" y="${by}" width="${room}" height="${narrow ? 22 : 32}" rx="7" class="mr-rg-track"/>
      <rect x="${lab}" y="${by}" width="${w}" height="${narrow ? 22 : 32}" rx="7" class="mr-rg-fill"/>
      <text x="${lab + w + 8}" y="${by + (narrow ? 16 : 21)}" class="mr-rg-val">${esc(money(r.tax))}</text>
      ${better === id && !narrow ? `<g transform="translate(${W - 92} ${y + 4})"><rect width="88" height="24" rx="12" class="mr-pill"/><text x="44" y="16.5" class="mr-pill-t">${esc(words.best)}</text></g>` : ''}</g>`;
  };
  return `<svg class="mr-rgs" viewBox="0 0 ${W} ${narrow ? 110 : 96}" role="img" aria-label="${esc(`${a.label} ${money(a.tax)}, ${b.label} ${money(b.tax)}`)}">${row(a, 'new', 4)}${row(b, 'old', narrow ? 58 : 56)}</svg>`;
}

/** rows: [{left, right, a, b, level}] - each employer's TDS (Form 16) joined to the credit in 26AS / AIS. */
export function tdsMap(rows, words, W = 720) {
  if (!rows.length) return '';
  if (W < 520) W = 520;                  // ponytail: below this the two boxes are scaled - the list under it says the same in words
  const rh = 58; const H = rows.length * rh + 34;
  const items = rows.map((r, i) => {
    const y = 34 + i * rh;
    return `<g class="mr-tm lv-${esc(r.level)}">
      <rect x="0" y="${y}" width="250" height="44" rx="10" class="mr-tm-box"/><text x="14" y="${y + 18}" class="mr-tm-t">${esc(r.left)}</text><text x="14" y="${y + 35}" class="mr-tm-v">${esc(money(r.a))}</text>
      <path d="M250 ${y + 22} C 360 ${y + 22}, 360 ${y + 22}, 470 ${y + 22}" class="mr-tm-ln"/>
      <circle cx="360" cy="${y + 22}" r="11" class="mr-tm-dot"/>${r.level === 'ok' ? `<path d="M355 ${y + 22} l3.5 3.5 l6 -7" class="mr-tm-tick"/>` : `<text x="360" y="${y + 26.5}" class="mr-tm-x">!</text>`}
      <rect x="470" y="${y}" width="250" height="44" rx="10" class="mr-tm-box"/><text x="484" y="${y + 18}" class="mr-tm-t">${esc(r.right)}</text><text x="484" y="${y + 35}" class="mr-tm-v">${esc(money(r.b))}</text></g>`;
  }).join('');
  return `<svg class="mr-tmap" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(words.title)}">
    <text x="0" y="16" class="mr-tm-h">${esc(words.left)}</text><text x="470" y="16" class="mr-tm-h">${esc(words.right)}</text>${items}</svg>`;
}

/** The picture on a "before we go on" question. why 'start': a return already under way - its folder of papers and the
 *  new sheet arriving; why 'same': the paper already there and the new one beside it, a clock on the old one (kept in History). */
export function askArt(why) {
  const sheet = (x, y, cls, r = 0) => `<g transform="translate(${x} ${y}) rotate(${r})" class="${cls}">
      <path d="M0 0 h30 l12 12 v44 a4 4 0 0 1 -4 4 h-38 a4 4 0 0 1 -4 -4 v-52 a4 4 0 0 1 4 -4z" class="ask-sheet"/>
      <path d="M30 0 v8 a4 4 0 0 0 4 4 h8" class="ask-fold"/>
      <path d="M6 22 h26 M6 30 h30 M6 38 h22 M6 46 h28" class="ask-ln"/></g>`;
  const defs = `<defs><radialGradient id="ask-glow" cx="50%" cy="50%" r="50%"><stop offset="0" class="ask-g0"/><stop offset="1" class="ask-g1"/></radialGradient>
      <marker id="ask-head" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M1 1 L8 5 L1 9" class="ask-headp"/></marker></defs>`;
  if (why === 'start') {
    return `<svg class="ask-art" viewBox="0 0 260 150" role="img" aria-hidden="true">${defs}
      <ellipse cx="130" cy="78" rx="118" ry="66" fill="url(#ask-glow)"/>
      <path d="M44 66 h40 l10 10 h66 a6 6 0 0 1 6 6 v50 a6 6 0 0 1 -6 6 h-116 a6 6 0 0 1 -6 -6 v-60 a6 6 0 0 1 6 -6z" class="ask-folder-back"/>
      ${sheet(62, 32, 'ask-dim', -7)}${sheet(86, 26, 'ask-dim', 4)}
      <path d="M38 92 h132 a6 6 0 0 1 6 7 l-6 34 a6 6 0 0 1 -6 5 h-118 a6 6 0 0 1 -6 -5 l-8 -34 a6 6 0 0 1 6 -7z" class="ask-folder"/>
      <path d="M196 34 C 176 14, 150 18, 142 44" class="ask-arc" marker-end="url(#ask-head)"/>
      ${sheet(192, 30, 'ask-new', 8)}
      <circle cx="236" cy="30" r="11" class="ask-badge"/><path d="M231 30 h10 M236 25 v10" class="ask-badge-mark"/></svg>`;
  }
  return `<svg class="ask-art" viewBox="0 0 260 150" role="img" aria-hidden="true">${defs}
      <ellipse cx="130" cy="78" rx="118" ry="66" fill="url(#ask-glow)"/>
      ${sheet(52, 44, 'ask-dim', -5)}
      <circle cx="98" cy="106" r="13" class="ask-clock"/><path d="M98 99 v7 l5 4" class="ask-clock-hand"/>
      <path d="M112 52 C 124 36, 140 36, 152 52" class="ask-arc" marker-end="url(#ask-head)"/>
      <path d="M152 112 C 140 128, 124 128, 112 112" class="ask-arc ask-arc-back" marker-end="url(#ask-head)"/>
      ${sheet(162, 40, 'ask-new', 4)}
      <circle cx="212" cy="40" r="11" class="ask-badge"/><path d="M207 40 l3.5 3.5 l6.5 -7" class="ask-badge-mark"/></svg>`;
}
