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
