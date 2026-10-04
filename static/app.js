// Training & Video Portal: its own screens, its own landing pitch, and its own corner of the shell
// (project picker, AI-key chip). Everything else — sign-in, menu, people & access, activity, visitors,
// memory watch, How to Use — is the framework's: core/static/shell.js.
//
// The shape of this product, in one line: a person arrives, brings their OWN AI key, and turns a
// screen recording into a narrated video. Everything else — projects, manuals, How to Use links —
// is what you do AFTER you have something to show. catalog.json lists the screens in that order.
import { startPortal, state, render, refresh, passwordDialog, may, onMenu } from '../core-static/shell.js';
import { setupPage } from './page-setup.js';
import { howtoPage } from './page-howto.js';
import { manualPage } from './page-manual.js';
import { keysPage } from './page-keys.js';
import { buyKeyPage } from './page-buykey.js';
import { keySalesPage } from './page-keysales.js';
import { tourVideoPage } from './page-tourvideo.js';
import { guidemePage } from './page-guideme.js';
import { clientsPage } from './page-clients.js';
import { intakePage } from './page-intake.js';
import { reconPage } from './page-recon.js';
import { computePage } from './page-compute.js';
import { api, BASE, esc, t, ps, loadWords, keep, kept, uploadBox, confirmDialog, setCurrency, shownMoney } from '../core-static/ui.js';
import { icon, logo } from './icons.js';

// Every word here is chip ui.app (core/words.py) - none is written here. Fetched before anything is
// drawn: the pitch is shown before sign-in (the words endpoint needs none), and the menu foot and user
// menu below are built once, at start. A server that is down still gets the shell's own message.
await loadWords('app').catch(() => {});
const w = (k, v) => t('app', k, v);

export * from '../core-static/ui.js';

/** A book's cover in its hero - Audiobook and TeDBook (2026-09-29 owner: "use the audiobook's / TeDBook's cover too"):
 *  the picture (or the page's own art) and one Cover button; wireCover uploads it, warning first when one is there. */
export function coverSlot(src, fallback = '') {
  return `<div class="ab-cover">${src ? `<img src="${esc(src)}" alt=""/>` : fallback}
    <button type="button" class="small ghost" data-cover title="${esc(w('cover_tip'))}">${icon('image', 13)} ${w('cover_btn')}</button></div>`;
}

export function wireCover(host, { has, exts, url, done }) {
  const b = host.querySelector('[data-cover]');
  if (!b) return;
  const up = () => uploadBox(w('cover_title'), exts, url, done);
  b.onclick = () => (has ? confirmDialog(w('cover_redo_title'), w('cover_redo_body'), up, w('cover_btn'), { tone: 'warn' }) : up());
}
export { state, render, passwordDialog, may };

Object.assign(state, {
  productName: w('product_name'),
  hasKey: false,       // does THIS person have their own AI key yet
  // "a folder on this machine" means the SERVER's machine — these say which one that is.
  serverWindows: false, serverSample: '',
  // 2026-09-21: read once signed IN (keep/kept scope it to the person) - a bare key is the browser's, not theirs
  projects: [], projectId: '',
  // May this person name a folder on the SERVER for a project? Owner yes, everyone else only
  // within TV_SCAN_ROOTS — the server answers, and until it does, assume yes rather than nag.
  canScanLocal: true,
});

export const project = () => state.projects.find((p) => p.id === state.projectId) || null;
export const screensOf = () => (project() || {}).screens || [];

export const fmtTime = (s) => {
  const t = Math.max(0, Number(s) || 0);
  return `${String(Math.floor(t / 60)).padStart(2, '0')}:${String(Math.floor(t % 60)).padStart(2, '0')}`;
};
// Every amount on every screen goes through these two. The server books in US dollars; the person
// sees their own currency (chip money.currencies, picked on Account & key) — a cost with two more
// places than a budget, since one model call is fractions of a cent.
const cur = () => state.currency || { per_usd: 1 };
const shown = shownMoney;                                  // one formatter, in core/static/ui.js
export const money = (v) => (v === null || v === undefined ? w('unknown') : shown(v, 2));   // a model call
export const budget = (v) => (v === null || v === undefined ? '—' : shown(v, 0));           // what is loaded / left
export const toLocal = (usd) => Math.round(Number(usd || 0) * cur().per_usd * 100) / 100;   // a budget box shows the person's currency

export async function loadProjects() {
  try {
    const d = await api('/api/projects');
    state.projectId = state.projectId || kept('tv.project', '');
    state.projects = d.projects || [];
    state.canScanLocal = !!d.can_scan_local;
    if (!state.projects.some((p) => p.id === state.projectId)) {
      state.projectId = state.projects[0] ? state.projects[0].id : '';
      keep('tv.project', state.projectId);
    }
  } catch { state.projects = []; }
}

/** Whatever the shell needs to know about the person who is signed in right now. Called after
 *  anything that can change it — signing in, saving a key — so the AI chip is never stale. */
export const refreshMe = refresh;

// --- the landing pitch ------------------------------------------------------------------------------

// The cards and the tour video are the edition's (chip edition.settings selling / tour); before boot, tv's three.
const SELLING = () => (state.edition && state.edition.selling && state.edition.selling.length ? state.edition.selling
  : [['upload', 'sell_record', 'sell_record_line'], ['spark', 'sell_script', 'sell_script_line'], ['mic', 'sell_voice', 'sell_voice_line']]);

/** Record, script, voice, publish - drawn rather than listed, because the order IS the product. */
const RAIL = () => `<svg class="rail" viewBox="0 0 520 74" role="img" aria-hidden="true" focusable="false">
  <defs><linearGradient id="railline" x1="0" x2="1">
    <stop offset="0" stop-color="rgba(255,255,255,.18)"/><stop offset=".5" stop-color="rgba(255,255,255,.75)"/>
    <stop offset="1" stop-color="rgba(255,255,255,.18)"/></linearGradient></defs>
  <line x1="34" y1="27" x2="486" y2="27" stroke="url(#railline)" stroke-width="1.5" stroke-dasharray="4 5"/>
  ${[[pw('rail_record'), 34], [pw('rail_script'), 184], [pw('rail_voice'), 334], [pw('rail_publish'), 486]].map(([label, x], i) => `
    <circle cx="${x}" cy="27" r="13" fill="rgba(255,255,255,.14)" stroke="rgba(255,255,255,.5)"/>
    <text x="${x}" y="31.5" text-anchor="middle" font-size="12" font-weight="700" fill="#fff">${i + 1}</text>
    <text x="${x}" y="61" text-anchor="middle" font-size="12.5" fill="rgba(255,255,255,.88)">${esc(label)}</text>`).join('')}
</svg>`;

/** The tour of this portal, made BY this portal. Nothing sells the thing like the thing itself, and
 *  it is served from static/ - no YouTube, no third party watching whoever reads this page.
 *  preload="none" so a visitor on a phone pays for the poster and nothing else. */
const TOUR = (t) => `<figure class="tourbox">
  <video controls preload="none" playsinline poster="${BASE}/static/tour/${esc(t.poster)}">
    <source src="${BASE}/static/tour/${esc(t.video)}" type="video/mp4"/>
    <track kind="captions" srclang="en" label="${esc(w('captions_label'))}" default src="${BASE}/static/tour/${esc(t.captions)}"/>
  </video>
  <figcaption>${icon('play', 13)} ${pw('tour_caption')}</figcaption>
</figure>`;

// The edition's own pitch words (chip edition.settings words_prefix: SteadyMove's are sm_*); tv's tour only on tv.
const pfx = () => (state.edition && state.edition.words_prefix) || '';
const pw = (k, v) => w(pfx() + k, v);

// 2026-09-19 owner: on a phone the form sits below the whole pitch - a returning user gets a Sign in button up top.
const JUMP = () => (state.edition && state.edition.jump_signin ? `<button type="button" class="jump-signin" data-jump-signin>${icon('user', 14)} ${pw('jump_signin')}</button>` : '');
document.addEventListener('click', (e) => {
  if (!e.target.closest('[data-jump-signin]')) return;
  const tab = document.querySelector('.gateform [data-mode="signin"]');
  if (tab && !tab.classList.contains('on')) tab.click();
  setTimeout(() => (document.getElementById('authform') || document.querySelector('.gateform')).scrollIntoView({ behavior: 'smooth', block: 'start' }), 50);
});

const pitch = () => `
  ${JUMP()}
  <h2>${pw('pitch_title')}</h2>
  <p class="sub">${pw('pitch_sub')}</p>
  ${state.edition && state.edition.tour ? TOUR(state.edition.tour) : ''}
  ${RAIL()}
  <ol class="pitchsteps n${SELLING().length}">${SELLING().map(([ic, title, line]) => `<li>
    <span class="i">${icon(ic, 17)}</span>
    <span><b>${esc(pw(title))}</b><span>${esc(pw(line))}</span></span></li>`).join('')}</ol>
  <p class="fine">${icon('shield', 14)} ${pw('pitch_fine')}</p>`;

// --- start ---------------------------------------------------------------------------------------

const NEEDS_PROJECT = new Set(['manuals', 'howto']);
const keyScreen = () => ps('shell').key_screen;          // the Account & key screen (chip page.shell key_screen)

startPortal({
  views: { clients: clientsPage, intake: intakePage, recon: reconPage, compute: computePage, manuals: manualPage, howto: howtoPage, guideme: guidemePage, setup: setupPage, keys: keysPage, buykey: buyKeyPage, keysales: keySalesPage, tourvideo: tourVideoPage },
  // The edition (tv or SteadyMove, chip edition.settings) names the line under the logo.
  pitch, logo, brandSub: () => (state.edition && state.edition.brand_sub) || '',
  landing: () => (state.edition && state.edition.landing) || '#/video',   // a door (chip edition.settings doors) has its own first screen
  // 2026-10-01 owner "In Katha we don't need key": the key link, the key menu row and AI READY show only where Account &
  // key is in THIS host's menu - a door without the keys screen (Katha, chip edition.settings doors[].screens) shows none
  navFoot: () => (onMenu(keyScreen()) ? `<a class="quiet" href="${BASE}/help/gemini-key" target="_blank" rel="noopener">
    ${icon('help', 15)} ${w('how_to_get_key')}</a>` : ''),
  userMenu: () => (onMenu(keyScreen()) ? `<a href="#/${esc(keyScreen())}">${icon('key', 15)} ${w('account_key')}</a>` : ''),
  onBoot: async (d) => {
    await loadWords('app');      // already there from the start; a no-op unless that first fetch failed
    state.edition = d.edition || null;
    document.title = state.productName;                 // SteadyMove's tab says SteadyMove, not the HTML's default
    const aside = document.querySelector('aside.pitch');   // signed out: the pitch was drawn before the edition was known
    if (aside) aside.innerHTML = (aside.querySelector('.mark') || { outerHTML: '' }).outerHTML + pitch();
    state.hasKey = !!d.has_key;
    state.currency = d.currency || null;
    setCurrency(state.currency);
    state.serverWindows = !!(d.server && d.server.windows);
    state.serverSample = (d.server && d.server.sample_path) || '';
    if (state.user) await loadProjects();
  },
  topbar: (route) => `
    ${NEEDS_PROJECT.has(route.id) && state.projects.length ? `<div class="picker">
        <label for="proj">${w('project')}</label>
        <select id="proj">${state.projects.map((p) => `<option value="${esc(p.id)}" ${p.id === state.projectId ? 'selected' : ''}>${esc(p.name)}</option>`).join('')}</select></div>` : ''}
    ${!may(keyScreen()) || !onMenu(keyScreen()) ? '' : state.hasKey
      ? `<span class="tag ok" title="${esc(w('ai_ready_tip'))}">${icon('spark', 12)} ${w('ai_ready')}</span>`
      : `<a href="#/${esc(keyScreen())}" class="chipbtn">${icon('key', 14)} ${w('add_key')}</a>`}`,
  // 2026-09-28 owner: "Launch -> Studio at top right" - a door (Katha) opens the workshop (SteadyMove) in a new tab
  topbarEnd: () => (state.edition && state.edition.launch ? `<a class="chipbtn" href="${esc(state.edition.launch)}" target="_blank" rel="noopener">
      ${icon('wand', 14)} ${w('launch_studio')}</a>` : ''),
  wireTopbar: (root) => {
    const picker = root.querySelector('#proj');
    if (picker) picker.onchange = () => {
      state.projectId = picker.value;
      keep('tv.project', state.projectId);
      render();
    };
  },
});
