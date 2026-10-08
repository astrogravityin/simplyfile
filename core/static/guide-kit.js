// Guide me kit: a step-by-step tour drawn over the live screen. A soft veil with a spotlight on the part
// being explained, one card with a picture, the step's narration, Back / Next, and the browser's own voice
// reading it aloud when asked (free: nothing leaves the machine).
//
// PORTABLE - the same file runs on every portal (core/static/guide.js is its adapter), on the studio and
// every family site, and in any site the Guide Me Builder exports it to. It needs only ./icons.js and
// guide-kit.css. It never fetches and it holds no words and no knobs of its own (chips and ops only): the host
// hands it the tour, `tour.settings` (chip guide.settings: voice, pace, padding, wait, phone width) and the
// card's words (chip ui.guide + the four road names of ui.shell). WORD_KEYS lists the words it asks for.
//
// A step: {title, say, target, open, art, place}.
//  target  selectors split by "|" - the first one on screen wins, so one tour works on an empty list and on
//          an open item. `sel:has-text('Words')` also works (the innermost `sel` whose text holds the words;
//          `*:has-text('Words')` = the element that shows those words).
//  open    same rule; pressed once when the target is not on screen (open the first item, go back Home),
//          then the kit waits up to ~5 s for the target and spotlights it.
//  art     {kind: hero|flow|roads|meter|stack|check, ...} - the picture on the card.
//  place   below|above|right|left|center (optional; default = the first side that fits).
import { icon } from './icons.js';

/** The words the card asks its host for (chip ui.guide, and rd_* from ui.shell). */
export const WORD_KEYS = ['step_of', 'minutes', 'begin', 'next', 'back', 'done', 'close', 'listen', 'mute',
  'not_on_screen', 'open_first', 'keys_hint', 'rd_portal', 'rd_bridge', 'rd_ai', 'rd_diy'];

let live = null;                       // the open tour: {tour, i, voice, els, off, words, opening}
let uid = 0;

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const store = {
  get(k, d = '') { try { const v = localStorage.getItem(k); return v === null ? d : v; } catch { return d; } },
  set(k, v) { try { if (v) localStorage.setItem(k, v); else localStorage.removeItem(k); } catch { /* private window */ } },
};
const say = (k, v = {}) => String(live?.words?.[k] ?? '').replace(/\{(\w+)\}/g, (_, x) => String(v[x] ?? ''));

/** Has this person taken the tour for `screen` (so a Guide me button may stop glowing)? */
export const seen = (screen) => store.get(`guide.seen.${screen}`) === '1';

/**
 * Open a tour over the page. `tour` = a Guide me script: {title, lede, icon, minutes, steps, settings}.
 * opts: {words, product, screen} - words = the host's chip words (WORD_KEYS); {product} in any text becomes `product`.
 */
export function openTour(tour, { words = {}, product = '', screen = '' } = {}) {
  closeTour();
  const fill = (s) => String(s || '').replace(/\{product\}/g, product);
  const st = { ...(tour.settings || {}) };
  tour = { ...tour, settings: st, title: fill(tour.title), lede: fill(tour.lede),
    steps: (tour.steps || []).filter((s) => s && (s.say || s.title)).map((s) => ({ ...s, title: fill(s.title), say: fill(s.say) })) };
  const voiceOn = store.get('guide.voice', st.speak_by_default ? '1' : '') === '1';
  const els = {
    hole: Object.assign(document.createElement('div'), { className: 'gd-hole' }),
    veil: Object.assign(document.createElement('div'), { className: 'gd-veil' }),
    card: Object.assign(document.createElement('section'), { className: 'gd-card' }),
  };
  els.card.setAttribute('role', 'dialog');
  els.card.setAttribute('aria-live', 'polite');
  els.card.setAttribute('aria-labelledby', 'gd-title');
  document.body.append(els.veil, els.hole, els.card);
  const onKey = (e) => {
    if (e.key === 'Escape') { e.preventDefault(); closeTour(); } else if (e.key === 'ArrowRight') go(live.i + 1);
    else if (e.key === 'ArrowLeft') go(live.i - 1);
  };
  let raf = 0;
  const onMove = () => { cancelAnimationFrame(raf); raf = requestAnimationFrame(() => live && place(false)); };
  addEventListener('keydown', onKey, true);
  addEventListener('resize', onMove);
  addEventListener('scroll', onMove, true);
  live = { tour, i: -1, voice: voiceOn, els, words: { ...words }, opening: false, off: () => {
    removeEventListener('keydown', onKey, true); removeEventListener('resize', onMove); removeEventListener('scroll', onMove, true);
  } };
  if (screen) store.set(`guide.seen.${screen}`, '1');
  go(-1);
}

export function closeTour() {
  if (!live) return;
  try { speechSynthesis.cancel(); } catch { /* no voice here */ }
  live.off();
  Object.values(live.els).forEach((e) => e.remove());
  live = null;
}

/** Step -1 is the cover (title, lede, how long); 0..n-1 are the steps. */
function go(i) {
  if (!live) return;
  const n = live.tour.steps.length;
  if (i >= n) { closeTour(); return; }
  live.i = Math.max(-1, i);
  const s = live.tour.steps[live.i];
  live.opening = !!(s?.open && !target(s) && press(s.open));
  draw();
  place(true);
  speak();
  if (live.opening) settle(live.i, 0);
}

/** Press the first `open` control on screen (never one inside the guide card). */
function press(sel) {
  const el = target({ target: sel });
  if (el) el.click();
  return !!el;
}

/** After a press the page redraws: wait (guide.settings open_wait_ms) for the step's part, then spotlight it. */
function settle(i, tries) {
  if (!live || live.i !== i) return;
  if (target(live.tour.steps[i]) || tries * 100 >= (Number(live.tour.settings.open_wait_ms) || 0)) {
    live.opening = false; draw(); place(true); return;
  }
  setTimeout(() => settle(i, tries + 1), 100);
}

const HAS_TEXT = /^(.*?):has-text\((['"])(.*?)\2\)\s*$/;

/** One selector -> the element on screen, or null. A bad selector is a missing part, never a broken tour. */
export function findTarget(sel) {
  const m = HAS_TEXT.exec(sel);
  let all = [];
  try { all = [...document.querySelectorAll(m ? (m[1] || '*') : sel)]; } catch { return null; }
  // has-text: the INNERMOST element holding the words (never <html> or a wrapper around the whole page)
  if (m) {
    const hits = all.filter((el) => (el.textContent || '').includes(m[3]));
    all = hits.filter((el) => !hits.some((o) => o !== el && el.contains(o)));
  }
  const shown = all.filter((el) => el.getClientRects().length && !el.closest('.gd-card'));
  // A popup open over the page: its own parts win over look-alikes on the page underneath (a "Run" in the dialog,
  // not the page's "Run"). The topmost = the last open dialog in the document.
  const dialogs = [...document.querySelectorAll('[role="dialog"],[aria-modal="true"],dialog[open]')]
    .filter((d) => !d.classList.contains('gd-card') && d.getClientRects().length);
  const top = dialogs[dialogs.length - 1];
  return (top && shown.find((el) => top.contains(el))) || shown[0] || null;
}

function target(step) {
  for (const sel of String(step?.target || '').split('|').map((s) => s.trim()).filter(Boolean)) {
    const el = findTarget(sel);
    if (el) return el;
  }
  return null;
}

function draw() {
  const { tour, i, voice, els } = live;
  const n = tour.steps.length;
  const cover = i < 0;
  const s = cover ? { title: tour.title, say: tour.lede, art: { kind: 'hero', icon: tour.icon || 'spark' } } : tour.steps[i];
  const missing = !cover && s.target && !target(s);
  const bar = tour.steps.map((_, j) => `<i class="${j < i ? 'past' : j === i ? 'now' : ''}"></i>`).join('');
  els.card.innerHTML = `
    <div class="gd-art">${art(s.art || { kind: 'hero', icon: 'spark' }, cover ? 0 : i + 1)}</div>
    <button type="button" class="gd-x" data-gd="close" aria-label="${esc(say('close'))}" title="${esc(say('close'))}">${icon('close', 16)}</button>
    <div class="gd-body">
      <div class="gd-eyebrow">${cover ? `${icon('clock', 13)} ${esc(say('minutes', { n: tour.minutes || Math.max(1, Math.round(n / 3)) }))}`
        : esc(say('step_of', { n: i + 1, total: n }))}</div>
      <h3 id="gd-title">${esc(s.title)}</h3>
      <p class="gd-say">${esc(s.say)}</p>
      ${missing && !live.opening ? `<p class="gd-miss">${icon('info', 13)} ${esc(say(s.open ? 'open_first' : 'not_on_screen'))}</p>` : ''}
      ${cover ? '' : `<div class="gd-bar" aria-hidden="true">${bar}</div>`}
    </div>
    <footer class="gd-foot">
      <button type="button" class="gd-b gh gd-voice ${voice ? 'on' : ''}" data-gd="voice" aria-pressed="${voice}">
        ${icon(voice ? 'speaker' : 'mic', 14)} ${esc(say(voice ? 'mute' : 'listen'))}</button>
      <span class="gd-sp"></span>
      ${cover ? '' : `<button type="button" class="gd-b gh" data-gd="back">${icon('left', 14)} ${esc(say('back'))}</button>`}
      <button type="button" class="gd-b pri" data-gd="next">${esc(say(cover ? 'begin' : i === n - 1 ? 'done' : 'next'))}
        ${icon(i === n - 1 ? 'check' : 'right', 14)}</button>
    </footer>
    <p class="gd-keys">${esc(say('keys_hint'))}</p>`;
  els.card.querySelector('[data-gd="close"]').onclick = closeTour;
  els.card.querySelector('[data-gd="next"]').onclick = () => go(live.i + 1);
  const back = els.card.querySelector('[data-gd="back"]');
  if (back) back.onclick = () => go(live.i - 1);
  els.card.querySelector('[data-gd="voice"]').onclick = () => {
    live.voice = !live.voice;
    store.set('guide.voice', live.voice ? '1' : '');
    draw(); place(false);
    if (live.voice) speak(); else try { speechSynthesis.cancel(); } catch { /* no voice */ }
  };
  els.card.querySelector('[data-gd="next"]').focus({ preventScroll: true });
}

/** Spotlight the step's part and set the card beside it (below, above, right, left - whichever fits). */
function place(scroll) {
  const { tour, i, els } = live;
  const s = i < 0 ? null : tour.steps[i];
  const el = s ? target(s) : null;
  const pad = Number(tour.settings?.pad) || 0;
  const card = els.card;
  const vw = innerWidth, vh = innerHeight, m = 16;
  const phone = vw < (Number(tour.settings?.sheet_below_px) || 0);
  card.classList.toggle('sheet', phone);
  card.classList.remove('top');
  card.style.maxHeight = '';
  els.veil.classList.toggle('dim', !el);
  if (!el) {
    els.hole.hidden = true;
    card.style.left = phone ? '' : `${Math.max(m, (vw - card.offsetWidth) / 2)}px`;
    card.style.top = phone ? '' : `${Math.max(m, (vh - card.offsetHeight) / 2)}px`;
    return;
  }
  if (scroll) el.scrollIntoView({ block: phone ? 'start' : 'center', inline: 'nearest', behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
  const r = el.getBoundingClientRect();
  const box = { x: r.left - pad, y: r.top - pad, w: r.width + pad * 2, h: r.height + pad * 2 };
  els.hole.hidden = false;
  Object.assign(els.hole.style, { left: `${box.x}px`, top: `${box.y}px`, width: `${box.w}px`, height: `${box.h}px` });
  // 2026-10-03 owner: on a short screen the sheet sat over a target at the bottom (the bottom bar's tools) - the
  // sheet goes to the side with more room and never grows over the target.
  if (phone) {
    const above = box.y - m, below = vh - (box.y + box.h) - m;
    card.classList.toggle('top', above > below);
    card.style.left = ''; card.style.top = '';
    const st = tour.settings || {};   // the sheet's floor and share of the screen are chip guide.settings
    card.style.maxHeight = `${Math.round(Math.max(Number(st.sheet_min_px) || 0, Math.min(vh * (Number(st.sheet_max_share) || 1), Math.max(above, below))))}px`;
    return;
  }
  const cw = card.offsetWidth, ch = card.offsetHeight, gap = 14;
  const fits = {
    below: box.y + box.h + gap + ch <= vh - m, above: box.y - gap - ch >= m,
    right: box.x + box.w + gap + cw <= vw - m, left: box.x - gap - cw >= m,
  };
  const side = (s.place && s.place !== 'center' && fits[s.place]) ? s.place
    : s.place === 'center' ? 'center' : ['below', 'above', 'right', 'left'].find((k) => fits[k]) || 'center';
  let x = box.x + box.w / 2 - cw / 2, y = box.y + box.h / 2 - ch / 2;
  if (side === 'below') y = box.y + box.h + gap;
  if (side === 'above') y = box.y - gap - ch;
  if (side === 'right') x = box.x + box.w + gap;
  if (side === 'left') x = box.x - gap - cw;
  if (side === 'center') { x = (vw - cw) / 2; y = box.y + box.h / 2 > vh / 2 ? m : vh - ch - m; }   // away from the target
  card.style.left = `${Math.min(vw - cw - m, Math.max(m, x))}px`;
  card.style.top = `${Math.min(vh - ch - m, Math.max(m, y))}px`;
}

// --- the voice: the browser's own speech, free and local --------------------------------------------

/** Every voice this browser has (for a voice picker). May be empty until the browser loads them. */
export function voices() {
  try { return speechSynthesis.getVoices(); } catch { return []; }
}

/** The voice a setting asks for: an exact name first, then the preferred languages (a name hint wins inside one). */
export function pickVoice(st = {}) {
  const all = voices();
  if (st.voice_name) { const exact = all.find((v) => v.name === st.voice_name); if (exact) return exact; }
  for (const lang of st.voice_prefer || []) {
    const of = all.filter((v) => v.lang && v.lang.replace('_', '-').toLowerCase().startsWith(String(lang).toLowerCase()));
    const fine = of.find((v) => (st.voice_name_hint || []).some((h) => v.name.includes(h)));
    if (fine || of[0]) return fine || of[0];
  }
  return all.find((v) => /^en/i.test(v.lang)) || null;
}

/** Say one line in a setting's voice (the Configure screen's "Try this voice"). */
export function speakLine(text, st = {}) {
  if (!('speechSynthesis' in window)) return false;
  try {
    speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    const v = pickVoice(st);
    if (v) { u.voice = v; u.lang = v.lang; }
    u.rate = Number(st.rate) || 1;
    u.pitch = Number(st.pitch) || 1;
    speechSynthesis.speak(u);
    return true;
  } catch { return false; }
}

function speak() {
  if (!live || !live.voice) return;
  const { tour, i } = live;
  const s = i < 0 ? { title: tour.title, say: tour.lede } : tour.steps[i];
  speakLine(`${s.title}. ${s.say}`, tour.settings);
}
if (typeof window !== 'undefined' && 'speechSynthesis' in window) try { speechSynthesis.onvoiceschanged = () => {}; } catch { /* voices load late */ }

// --- the pictures: six kinds, drawn from the step's own data (step.art) -----------------------------
// {kind:'hero', icon}                      the screen's emblem in rings of light
// {kind:'flow', items:[…], at:n}           a path of stages, stage n lit
// {kind:'roads', at:'ai'}                  the four roads every activity offers, one lit
// {kind:'meter', value:0-100, label, icon} a gauge (money, readiness, progress)
// {kind:'stack', items:[…], icon}          a fan of cards (recordings, chapters, parts)
// {kind:'check', items:[…], done:n}        a checklist, the first n ticked
const W = 360, H = 132;

function glyph(name, x, y, size, cls = '') {
  return (icon(name || 'spark', size) || icon('spark', size)).replace('<svg class="ico"', `<svg x="${x}" y="${y}" class="gd-g ${cls}"`);
}

function label(x, y, text, cls = '', anchor = 'middle') {
  const s = String(text ?? ''), max = anchor === 'start' ? 26 : 16;   // a centred label shares its width with neighbours
  return `<text x="${x}" y="${y}" text-anchor="${anchor}" class="gd-t ${cls}">${esc(s.length > max ? `${s.slice(0, max - 1)}…` : s)}</text>`;
}

const ART = {
  hero(a, id) {
    const dots = [[58, 34, 2.4], [300, 28, 3], [318, 96, 2], [44, 100, 3.2], [250, 112, 1.8], [104, 18, 1.6]];
    return `<circle cx="180" cy="66" r="92" style="fill:url(#${id}r)" opacity=".55"/>
      ${[30, 44, 58].map((r, k) => `<circle cx="180" cy="66" r="${r}" class="gd-ring" style="animation-delay:${k * 0.6}s"/>`).join('')}
      ${dots.map(([x, y, r], k) => `<circle cx="${x}" cy="${y}" r="${r}" class="gd-dot" style="animation-delay:${k * 0.4}s"/>`).join('')}
      <rect x="152" y="38" width="56" height="56" rx="16" style="fill:url(#${id}g)" class="gd-tile"/>
      ${glyph(a.icon, 164, 50, 32, 'on')}`;
  },
  flow(a) {
    const items = (a.items || []).slice(0, 5);
    const n = Math.max(1, items.length), at = Number(a.at ?? -1);
    const gap = (W - 60) / Math.max(1, n - 1), xs = items.map((_, k) => (n === 1 ? W / 2 : 30 + k * gap));
    return `<line x1="${xs[0]}" y1="56" x2="${xs[n - 1]}" y2="56" class="gd-path"/>
      <line x1="${xs[0]}" y1="56" x2="${xs[Math.max(0, Math.min(at, n - 1))]}" y2="56" class="gd-path lit"/>
      ${items.map((it, k) => `<g class="gd-node ${k === at ? 'now' : k < at ? 'past' : ''}">
        <circle cx="${xs[k]}" cy="56" r="${k === at ? 19 : 14}"/>
        ${k < at ? glyph('check', xs[k] - 8, 48, 16, 'on') : `<text x="${xs[k]}" y="61" text-anchor="middle" class="gd-n">${k + 1}</text>`}
        ${label(xs[k], 104, it, k === at ? 'strong' : '')}</g>`).join('')}`;
  },
  roads(a) {
    const roads = [['portal', 'shield', say('rd_portal')], ['bridge', 'link', say('rd_bridge')],
      ['ai', 'spark', say('rd_ai')], ['diy', 'edit', say('rd_diy')]];
    const on = [].concat(a.at || []);
    return roads.map(([k, ic, l], j) => {
      const x = 14 + j * 84, lit = !on.length || on.includes(k);
      return `<g class="gd-road ${k} ${lit ? 'lit' : ''} ${on.length && on.includes(k) ? 'now' : ''}">
        <rect x="${x}" y="18" width="76" height="96" rx="14"/>
        ${glyph(ic, x + 24, 34, 28, 'on')}
        ${label(x + 38, 90, l, 'strong')}</g>`;
    }).join('');
  },
  meter(a, id) {
    const v = Math.max(0, Math.min(100, Number(a.value ?? 70))), R = 52, cx = 180, cy = 104;
    const pt = (p) => { const ang = Math.PI * (1 - p / 100); return [cx + R * Math.cos(ang), cy - R * Math.sin(ang)]; };
    const [ex, ey] = pt(v), [nx, ny] = pt(v);
    return `<path d="M ${cx - R} ${cy} A ${R} ${R} 0 0 1 ${cx + R} ${cy}" class="gd-arc"/>
      <path d="M ${cx - R} ${cy} A ${R} ${R} 0 0 1 ${ex.toFixed(1)} ${ey.toFixed(1)}" class="gd-arc lit" style="stroke:url(#${id}g)"/>
      <line x1="${cx}" y1="${cy}" x2="${nx.toFixed(1)}" y2="${ny.toFixed(1)}" class="gd-needle"/>
      <circle cx="${cx}" cy="${cy}" r="6" class="gd-hub"/>
      ${glyph(a.icon || 'money', 52, 40, 36, 'soft')}${glyph(a.icon2 || 'pulse', 272, 40, 36, 'soft')}
      ${label(cx, 126, a.label || '', 'strong')}`;
  },
  stack(a, id) {
    const items = (a.items || []).slice(0, 4), n = items.length;
    const step = n > 1 ? Math.min(24, (H - 88) / (n - 1)) : 0;
    return items.map((it, k) => {
      const x = 84 + k * 22, y = 12 + k * step, top = k === n - 1;
      return `<g class="gd-sheet ${top ? 'top' : ''}"><rect x="${x}" y="${y}" width="170" height="${top ? 72 : 60}" rx="12" ${top ? `style="fill:url(#${id}g)"` : ''}/>
        ${glyph(a.icon || 'film', x + 12, y + 7, top ? 18 : 14, top ? 'on' : 'soft')}
        ${label(x + (top ? 38 : 34), y + (top ? 21 : 18), it, top ? 'on' : '', 'start')}
        ${top ? `<rect x="${x + 14}" y="${y + 38}" width="124" height="6" rx="3" class="gd-line"/><rect x="${x + 14}" y="${y + 52}" width="86" height="6" rx="3" class="gd-line"/>` : ''}</g>`;
    }).join('');
  },
  check(a) {
    const items = (a.items || []).slice(0, 4), done = Number(a.done ?? items.length - 1);
    return `<rect x="70" y="10" width="220" height="${items.length * 26 + 16}" rx="14" class="gd-panel"/>
      ${items.map((it, k) => `<g class="gd-tick ${k < done ? 'ok' : 'todo'}">
        <circle cx="96" cy="${30 + k * 26}" r="9"/>${k < done ? glyph('check', 89, 23 + k * 26, 14, 'on') : ''}
        ${label(116, 35 + k * 26, it, '', 'start')}</g>`).join('')}`;
  },
};

export function art(a, n = 0) {
  const id = `gd${++uid}`;
  const paint = ART[a?.kind] || ART.hero;
  return `<svg viewBox="0 0 ${W} ${H}" class="gd-svg" role="img" aria-hidden="true" preserveAspectRatio="xMidYMid meet">
    <defs>
      <linearGradient id="${id}g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" class="gd-s1"/><stop offset="1" class="gd-s2"/></linearGradient>
      <radialGradient id="${id}r"><stop offset="0" class="gd-s1"/><stop offset="1" class="gd-s0"/></radialGradient>
    </defs>
    <rect width="${W}" height="${H}" class="gd-sky"/>
    <path d="M0 ${H - 26} C 90 ${H - 50} 150 ${H - 6} 240 ${H - 30} S 330 ${H - 40} ${W} ${H - 22} V ${H} H 0 Z" class="gd-hill"/>
    ${paint(a || {}, id)}
    ${n ? `<text x="${W - 16}" y="26" text-anchor="end" class="gd-num">${String(n).padStart(2, '0')}</text>` : ''}
  </svg>`;
}
