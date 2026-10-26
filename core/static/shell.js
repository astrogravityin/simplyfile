// The portal shell: the way in (first owner, sign in, sign up, the links that arrive by email), the
// frame every screen hangs in, the hash router, the How to Use button, and the page-view beacon.
//
// A portal hands startPortal() its own views and a few slots; the menu itself comes from the SERVER
// catalog filtered by what this person may open, so the menu and the API guard never disagree.
//
//   startPortal({
//     views: { things: thingsPage },              // id in catalog.json → (host) => render into host
//     screens: () => import('./screens.js').then((m) => m.views),   // optional: more views, loaded on first use (members-only code)
//     pitch: () => '<h2>…</h2>',                   // left half of the sign-in screen
//     brandSub, logo, landing: '#/things' (or a path of the host's own, e.g. '/'),
//     home: '/',                                   // optional: the logo + name link to the host's own home page
//     topbar: (route) => html, topbarEnd: (route) => html (top RIGHT), wireTopbar: (root, route) => {},
//     navFoot: html | () => html, userMenu: html | () => html,
//     onBoot: async (bootstrap) => {},             // copy the host's own bootstrap fields into state
//   })
import { api, BASE, esc, say, modal, toast, busy, wireSecrets, applyTheme, nextTheme, shownTheme, hooks, confirmDialog, t, loadWords, remembersFor, ps, BUILD, reportIssue, myReports, when, clockAt, setProduct } from './ui.js';
import { icon, logo as defaultLogo, spinner } from './icons.js';
import { guideButton, wireGuide } from './guide.js';

export const state = {
  user: null, productName: 'Portal', portalUrl: '', needsFirstAccount: false,
  reservedOwner: '',   // PORTAL_OWNER_EMAIL on the server: only this address may claim the portal
  canEmail: false, canSignup: false, verifyEmail: false, signupDomains: '',
  userLen: [],         // chip auth.username_problem [min, max] - shown in the user name box
  noMailPolicy: 'verify_later',     // chip auth.no_mail_policy: what sign-up does when no email can be sent
  code: { digits: 6, resend: 60 },  // chip auth.code_policy: code length, seconds before "Send a new code"
  authMode: 'signin',  // which tab the way-in card shows: signin | signup | forgot
  catalog: [],         // every screen: {id, label, group, icon, admin, functions}
  access: {},          // {screenId: {allowed, functions: {id: bool}}} for THIS person
  pendingRequests: [], // screens this person has already asked for
  howto: {},           // {pageId: [links]} — the How to Use button on each page
  guides: [],          // screens with a step-by-step guide (chips guide.<screen>) — Guide me in the top bar
  storageRequest: null, // the owner asked THIS person to clean up: shown as a banner on every page
  bellUnread: 0,       // notes waiting under the bell (core/bell.py): replies, new works from people you follow
  issuesOpen: 0,        // reported issues waiting (only for whoever may answer them): the menu's balloon
  issueReplies: [],     // answers to THIS person's reports: a banner until they close it
  banners: [],         // banners a rule put up for this person (core/rules.py): shown until dismissed or expired
  health: null,        // owners only: the Daily health check's answer (core/health.py) - replaced each check, never piled up
  find: null,          // chip find.messages: every word the top search says
};

// Every word the shell says is chip ui.shell (core/words.py) - none is written here. The top search's
// words are chip find.messages (state.find). startPortal loads ui.shell before the first draw: the
// sign-in card is drawn before anyone signs in, and the words endpoint needs no sign-in.
const w = (k, v) => t('shell', k, v);

let pageDirty = false;
/** The menu folded to icons (<<) or open (>>), remembered in this browser only. */
const signedInBefore = () => { try { return localStorage.getItem('portal.signed_in_before') === '1'; } catch { return false; } };
const sideCollapsed = () => { try { return localStorage.getItem('portal.side') === 'collapsed'; } catch { return false; } };   // something was typed on this page since it was drawn: Refresh asks first
let config = { views: {}, pitch: () => '', brandSub: '', logo: defaultLogo, landing: '',
  topbar: () => '', topbarEnd: () => '', wireTopbar: () => {}, navFoot: '', userMenu: '', onBoot: async () => {} };

// The framework's own admin screens, loaded only when someone opens one.
const CORE_VIEWS = {
  access: () => import('./page-access.js').then((m) => m.accessPage),
  activity: () => import('./page-activity.js').then((m) => m.activityPage),
  visitors: () => import('./page-visitors.js').then((m) => m.visitorsPage),
  storage: () => import('./page-storage.js').then((m) => m.storagePage),
  issues: () => import('./page-issues.js').then((m) => m.issuesPage),
  memory: () => import('./page-memory.js').then((m) => m.memoryPage),
  agents: () => import('./page-agents.js').then((m) => m.agentsPage),   // 2026-10-24 core/agents.py
  'connect-ai': () => import('./page-connect-ai.js').then((m) => m.connectAiPage),   // 2026-10-24 core/mcp.py
  'howto-config': () => import('./page-howto-config.js').then((m) => m.howtoConfigPage),
  menus: () => import('./page-menus.js').then((m) => m.menusPage),   // 2026-10-26 core/menus.py
  ocb: () => import('./page-ocb.js').then((m) => m.ocbPage),
  rcb: () => import('./page-rcb.js').then((m) => m.rcbPage),
};

/** A config slot: html, or a function giving html at draw time (e.g. only when a screen is in THIS host's menu). */
const slot = (x) => (typeof x === 'function' ? x() : x || '');
/** Is a screen in this host's menu? (the server filters state.catalog per door: chip edition.settings doors[].screens) */
export const onMenu = (screenId) => state.catalog.some((s) => s.id === screenId);

/** May this person use a screen, or one function inside it? The server enforces the same answer. */
export const may = (screenId, functionId = '') => {
  const a = state.access[screenId];
  if (!a || !a.allowed) return false;
  return functionId ? a.functions[functionId] !== false : true;
};

// --- page views ------------------------------------------------------------------------------------
// One beacon per screen shown, and a second one for the same view when the reader leaves it, carrying
// how long they stayed. Only the route goes: never a query string, never a token.

// 2026-09-21: the visit id is rotated on sign-out, so two people sharing a tab are two visits in Portal Activity,
// never one. It names no person and carries no token - only a route - but it must not straddle a sign-out.
let visitId = '';
const newVisit = () => {
  visitId = randomId();
  try { sessionStorage.setItem('portal.sid', visitId); } catch { /* a tab-long convenience */ }
  return visitId;
};
const sessionId = () => {
  if (visitId) return visitId;
  try {
    visitId = sessionStorage.getItem('portal.sid') || newVisit();
  } catch { visitId = randomId(); }
  return visitId;
};
let seen = null;

function randomId() {
  return Array.from(crypto.getRandomValues(new Uint8Array(12)), (b) => b.toString(16).padStart(2, '0')).join('');
}

function beacon(body) {
  const blob = new Blob([JSON.stringify(body)], { type: 'application/json' });
  if (!(navigator.sendBeacon && navigator.sendBeacon(`${BASE}/api/core/view`, blob))) {
    fetch(`${BASE}/api/core/view`, { method: 'POST', body: blob, keepalive: true,
      headers: { 'Content-Type': 'application/json' }, credentials: 'same-origin' }).catch(() => {});
  }
}

function leave() {
  if (seen) beacon({ view_id: seen.id, session_id: sessionId(), path: seen.path, dwell_ms: String(Date.now() - seen.t0) });
}

export function trackView(path, title = '') {
  path = String(path).split('?')[0];
  if (seen && seen.path === path) return;          // a re-render of the same screen is not a new visit
  leave();
  seen = { id: randomId(), path, t0: Date.now() };
  beacon({ view_id: seen.id, session_id: sessionId(), path, title, referrer: document.referrer,
    tz: Intl.DateTimeFormat().resolvedOptions().timeZone || '', lang: navigator.language || '',
    vw: String(window.innerWidth), vh: String(window.innerHeight) });
}
addEventListener('pagehide', leave);

// --- How to Use ------------------------------------------------------------------------------------

const KIND = new Proxy({}, { get: (_, k) => (ps('shell').howto_icons || {})[k] });   // 2026-09-26: chip page.shell

function howtoButton(pageId) {
  const links = state.howto[pageId] || [];
  if (!links.length) return '';
  const href = (u) => (u.startsWith('/') ? BASE + u : u);
  if (links.length === 1) {
    return `<a class="chipbtn" href="${esc(href(links[0].url))}" target="_blank" rel="noopener">
      ${icon('help', 14)} ${w('how_to_use')}</a>`;
  }
  return `<div class="usermenu howto">
    <button type="button" class="chipbtn" data-howto aria-haspopup="true">${icon('help', 14)} ${w('how_to_use')} ${icon('down', 13)}</button>
    <div class="pop" hidden>${links.map((l) => `<a href="${esc(href(l.url))}" target="_blank" rel="noopener">
      <span class="t-${esc(l.type)}">${icon(KIND[l.type] || 'link', 15)}</span> ${esc(l.label)}</a>`).join('')}</div></div>`;
}

function wireHowto(root) {
  root.querySelectorAll('[data-howto]').forEach((b) => {
    const pop = b.nextElementSibling;
    b.onclick = (e) => { e.stopPropagation(); pop.hidden = !pop.hidden; };
    document.addEventListener('click', () => { pop.hidden = true; });
  });
}

// --- the way in ------------------------------------------------------------------------------------
// One card, three tabs: Sign in · Sign up · Forgot password (.agents/skills/portal-builder/AUTH.md).
// Sign up and Forgot are short flows with a progress rail. Every step is a redraw of the same card
// from `flow`, so what was typed survives a step change, and whatever the server says about a field
// is shown beside that field. The server decides every rule; the page only carries the answers.
//
//   signin  form
//   signup  details ─send code─▶ code ─check─▶ password ─signup─▶ signed in
//           details ─send code, mail:false─▶ password            (no mail: the address is confirmed later)
//   forgot  account ─send code─▶ code ─check─▶ password ─reset─▶ done ─▶ signin (identity kept)
//           account ─send code, mail:false─▶ account + the owner-resets-it note

const flow = {
  step: 'details',   // where in the current tab's flow the card is (STEPS)
  values: {},        // what was typed, by input id — kept in memory across redraws, never stored
  proof: '',         // the single-use proof a right code bought
  noMail: false,     // sign-up on a portal that cannot send email: the code step is skipped
  note: null,        // {kind, text} shown at the top of the step
  error: null,       // an api error to show once the step is drawn (back a step with a reason)
  resendAt: 0,       // when "Send a new code" wakes up (ms since epoch)
  focus: false,      // put the cursor in the step's first empty box after the redraw
};
const STEPS = { signin: ['form'], signup: ['details', 'code', 'password'], forgot: ['account', 'code', 'password', 'done'], demo: ['details', 'code'] };
const dw = (k, v) => t('demo', k, v);   // demo mode's words (chip ui.demo, core/demo.py)
const SECRET_BOXES = ['au-pass', 'au-confirm', 'au-current', 'au-code'];
let resendTimer = 0;

/** Switch tab: back to that tab's first step. Names and addresses stay typed; secrets and codes do not. */
function setMode(mode) {
  state.authMode = STEPS[mode] ? mode : 'signin';
  Object.assign(flow, { step: STEPS[state.authMode][0], proof: '', noMail: false, note: null, error: null, resendAt: 0, focus: true });
  SECRET_BOXES.forEach((id) => { delete flow.values[id]; });
}

function goStep(step, extra = {}) {
  Object.assign(flow, { step, note: null, error: null, focus: true }, extra);
  render();
}

function currentStep() {
  const steps = STEPS[state.authMode] || STEPS.signin;
  if (!steps.includes(flow.step)) flow.step = steps[0];
  return flow.step;
}

/** The address a step is counted under in page views. Never a value, never a token. */
function authPath() {
  if (state.needsFirstAccount) return '#/first-account';
  if (state.authMode === 'signin') return '#/signin';
  const base = `#/${state.authMode}`;
  return { code: `${base}-code`, password: `${base}-password`, done: `${base}-done` }[flow.step] || base;
}

/** "Powered by ValueStream" with its logo (2026-10-07 owner: every portal is a valuestream.in sub-domain). Words: ui.shell. */
function poweredBy() {
  if (!w('powered_name') || w('powered_name') === 'powered_name') return '';
  return `<a class="powered" href="${esc(w('powered_href'))}" target="_blank" rel="noopener">
    <img src="${BASE}/core-static/valuestream.png" width="18" height="18" alt="">${esc(w('powered_by'))} <b>${esc(w('powered_name'))}</b></a>`;
}

function authShell(inner) {
  return `<div class="gate">
    <aside class="pitch">
      <div class="mark">${config.logo(40)}<span>${esc(state.productName)}</span></div>
      ${config.pitch()}
      ${poweredBy()}
    </aside>
    <div class="gateform"><form class="card" id="authform" novalidate>${inner}
      ${howtoButton('signin') ? `<p class="alt">${howtoButton('signin')}</p>` : ''}</form></div>
  </div>`;
}

/** One labelled box with room for its own error. `name` is the server's field name (name, username,
 *  email, password, confirm, code, current), so an answer {message, field} lands beside it. */
function authField(id, label, { name = '', type = 'text', placeholder = '', auto = 'off', hint = '', value,
  readonly = false, reveal = false, extra = '' } = {}) {
  const v = value !== undefined ? value : (flow.values[id] || '');
  const input = `<input id="${id}" name="${id}" type="${type}" autocomplete="${auto}" placeholder="${esc(placeholder)}"
      value="${esc(v)}" aria-describedby="${id}-err" ${readonly ? 'readonly' : ''} ${extra}/>`;
  return `<div class="field"${name ? ` data-for="${name}"` : ''}>
    <label for="${id}">${esc(label)}</label>
    ${reveal ? `<span class="withbtn">${input}<button type="button" data-reveal="${id}">${w('show')}</button></span>` : input}
    <span class="err" id="${id}-err" role="alert" hidden></span>
    ${hint ? `<span class="small muted">${hint}</span>` : ''}</div>`;
}

/** Hints only — the server decides what a good password is. */
const pwHints = () => `<p class="pwhints" aria-live="polite"><span data-hint="len">${w('pw_len', { n: state.passwordMin })}</span>
  <span aria-hidden="true">·</span><span data-hint="match">${w('pw_match')}</span></p>`;

function wirePwHints(scope, passId, confirmId) {
  const pass = scope.querySelector(`#${passId}`);
  const again = scope.querySelector(`#${confirmId}`);
  const len = scope.querySelector('[data-hint="len"]');
  const same = scope.querySelector('[data-hint="match"]');
  if (!pass || !again || !len || !same) return;
  const tick = () => {
    const long = pass.value.length >= state.passwordMin;
    const match = !!again.value && again.value === pass.value;
    len.textContent = `${w('pw_len', { n: state.passwordMin })}${long ? ' ✓' : ''}`;
    len.classList.toggle('ok', long);
    same.textContent = `${w('pw_match')}${match ? ' ✓' : ''}`;
    same.classList.toggle('ok', match);
  };
  pass.addEventListener('input', tick);
  again.addEventListener('input', tick);
  tick();
}

function clearOneError(f) {
  f.classList.remove('has-err');
  const out = f.querySelector('.err');
  if (out) { out.textContent = ''; out.hidden = true; }
  f.querySelectorAll('input,select,textarea').forEach((i) => i.removeAttribute('aria-invalid'));
}

export function clearFieldErrors(scope) {
  scope.querySelectorAll('.field.has-err').forEach(clearOneError);
}

/** An api error beside the field it is about ({field} from the server), or in `msgHost` when it is
 *  about no field. Returns true when it found its field. Text only, never HTML. */
export function showFieldError(scope, err, msgHost) {
  const field = err && err.data && err.data.field;
  const f = field ? scope.querySelector(`.field[data-for="${CSS.escape(String(field))}"]`) : null;
  if (!f) { say(msgHost, 'bad', esc(err && err.message)); return false; }
  clearOneError(f);
  f.classList.add('has-err');
  let out = f.querySelector('.err');
  if (!out) {
    out = Object.assign(document.createElement('span'), { className: 'err' });
    out.setAttribute('role', 'alert');
    f.appendChild(out);
  }
  out.textContent = err.message;
  out.hidden = false;
  const input = f.querySelector('input,select,textarea');
  if (input) { input.setAttribute('aria-invalid', 'true'); input.focus(); }
  say(msgHost, '', '');
  return true;
}

/** Typing into a box clears that box's error. */
export function wireFieldErrors(scope) {
  scope.addEventListener('input', (e) => {
    const f = e.target instanceof Element ? e.target.closest('.field.has-err') : null;
    if (f) clearOneError(f);
  });
}

function tabs() {
  const list = [...(state.demo ? [['demo', dw('tab')]] : []), ['signin', w('tab_signin')],
    ...(state.canSignup && !state.demo ? [['signup', w('tab_signup')]] : []), ['forgot', w('tab_forgot')]];
  return `<div class="tabs authtabs n${list.length}" role="tablist">${list.map(([m, label]) => `<button type="button" role="tab"
    data-mode="${m}" aria-selected="${state.authMode === m}" class="${state.authMode === m ? 'on' : ''}">${label}</button>`).join('')}</div>`;
}

/** 1 · Details › 2 · Code › 3 · Password — done steps green, the current one in the brand colour. */
function rail(steps, current) {
  const at = current === 'done' ? steps.length : steps.findIndex(([k]) => k === current);
  return `<ol class="authrail" aria-label="${esc(w('progress'))}">${steps.map(([, label], i) => `<li class="${i < at ? 'done' : ''}${i === at ? 'on' : ''}"
    ${i === at ? 'aria-current="step"' : ''}>${i + 1} · ${esc(label)}</li>`).join('')}</ol>`;
}

const resendButton = () => `<button type="button" class="link resend" data-act="resend" disabled>
    ${w('resend')} <span class="wait"></span></button>`;

function signinView() {
  if (state.needsFirstAccount) return firstAccountView();
  if (state.authMode === 'signup' && !state.canSignup) setMode('signin');
  const step = currentStep();
  const head = `${tabs()}<h1>${state.authMode === 'signup' ? w('tab_signup') : w('signin_title', { product: esc(state.productName) })}</h1>`;
  if (state.authMode === 'signup') return authShell(head + signupStep(step));
  if (state.authMode === 'forgot') return authShell(head + forgotStep(step));
  if (state.authMode === 'demo') return authShell(`${tabs()}<h1>${esc(dw('title', { product: state.productName }))}</h1>${demoStep(step)}`);
  return authShell(`${head}
    <p class="lede">${w('signin_lede')}</p>
    <div id="auth-msg"></div>
    ${authField('au-ident', w('ident'), { placeholder: w('ident_placeholder'), auto: 'username',
      extra: 'autocapitalize="off" spellcheck="false"' })}
    ${authField('au-pass', w('password'), { type: 'password', placeholder: w('password_placeholder'), auto: 'current-password', reveal: true })}
    <button class="primary" type="submit">${icon('right')} ${w('tab_signin')}</button>
    <p class="alt"><button type="button" class="link" data-mode="forgot">${w('forgot_link')}</button>
      ${state.canSignup ? '' : `<br/><span class="small muted">${w('signup_closed')}</span>`}</p>`);
}

/** Demo mode: name + email, then the emailed code - and the visitor is in, on a seat of their own (core/demo.py). */
function demoStep(step) {
  if (step === 'code') {
    return `<p class="lede">${esc(dw('lede'))}</p><div id="auth-msg"></div>
      ${authField('au-email', dw('email'), { readonly: true, auto: 'email' })}
      ${authField('au-code', dw('code'), { name: 'code', auto: 'one-time-code', placeholder: '0'.repeat(state.code.digits),
        extra: `inputmode="numeric" maxlength="${state.code.digits}" data-digits` })}
      <button class="primary" type="submit">${icon('right')} ${esc(dw('enter'))}</button>
      <p class="alt">${resendButton()} · <button type="button" class="link" data-act="details">${esc(dw('other_email'))}</button></p>`;
  }
  return `<p class="lede">${esc(dw('lede'))}</p><div id="auth-msg"></div>
    ${authField('au-name', dw('name'), { name: 'name', placeholder: dw('name_ph'), auto: 'name' })}
    ${authField('au-email', dw('email'), { name: 'email', type: 'email', placeholder: dw('email_ph'), auto: 'email',
      extra: 'autocapitalize="off" spellcheck="false" data-lower' })}
    <button class="primary" type="submit">${icon('mail')} ${esc(dw('send'))}</button>`;
}

function signupStep(step) {
  const digits = state.code.digits;
  const steps = flow.noMail ? [['details', w('step_details')], ['password', w('password')]]
    : [['details', w('step_details')], ['code', w('step_code')], ['password', w('password')]];
  if (step === 'code') {
    return `${rail(steps, step)}
      <p class="lede">${w('code_goes_to', { email: esc(flow.values['au-email'] || '') })}</p>
      <div id="auth-msg"></div>
      ${authField('au-code', w('verification_code'), { name: 'code', placeholder: w('code_placeholder', { n: digits }),
        auto: 'one-time-code', extra: `inputmode="numeric" maxlength="${digits}" data-digits` })}
      <button class="primary" type="submit">${icon('check')} ${w('confirm_email')}</button>
      <div class="authmore"><button type="button" data-act="details">${w('change_details')}</button>${resendButton()}</div>`;
  }
  if (step === 'password') {
    return `${rail(steps, step)}
      <p class="lede">${w('choose_for_user', { user: esc(flow.values['au-user'] || '') })}</p>
      <div id="auth-msg"></div>
      ${authField('au-pass', w('password'), { name: 'password', type: 'password', placeholder: w('at_least', { n: state.passwordMin }),
        auto: 'new-password', reveal: true })}
      ${authField('au-confirm', w('confirm_password'), { name: 'confirm', type: 'password', placeholder: w('repeat_password'),
        auto: 'new-password', reveal: true })}
      ${pwHints()}
      <button class="primary" type="submit">${icon('check')} ${w('create_account')}</button>
      <div class="authmore"><button type="button" class="link" data-act="details">${w('change_details')}</button></div>`;
  }
  return `${rail(steps, 'details')}
    <p class="lede">${state.signupDomains
      ? w('open_to_domains', { domains: esc(state.signupDomains) })
      : w('free_to_open')}</p>
    <div id="auth-msg"></div>
    ${authField('au-name', w('display_name'), { name: 'name', placeholder: w('display_name_placeholder'), auto: 'name' })}
    ${authField('au-user', w('user_name'), { name: 'username', placeholder: w('user_name_placeholder', { min: state.userLen[0], max: state.userLen[1] }), auto: 'username',
      extra: 'autocapitalize="off" spellcheck="false" data-lower' })}
    ${authField('au-email', w('email'), { name: 'email', type: 'email', placeholder: w('email_placeholder'), auto: 'email',
      extra: 'inputmode="email" autocapitalize="off" spellcheck="false"' })}
    <button class="primary" type="submit">${icon('mail')} ${w('send_verification')}</button>
    <p class="authfine">${w('we_email_code', { n: esc(digits) })}</p>`;
}

function forgotStep(step) {
  const steps = [['account', w('step_account')], ['code', w('step_code')], ['password', w('password')]];
  const who = esc(flow.values['au-ident'] || '');
  if (step === 'code') {
    return `${rail(steps, step)}
      <p class="lede">${w('for_who', { who })}</p>
      <div id="auth-msg"></div>
      ${authField('au-code', w('reset_code'), { name: 'code', placeholder: w('code_placeholder', { n: state.code.digits }),
        auto: 'one-time-code', extra: `inputmode="numeric" maxlength="${state.code.digits}" data-digits` })}
      <button class="primary" type="submit">${icon('right')} ${w('continue')}</button>
      <div class="authmore"><button type="button" data-act="account">${w('change_ident')}</button>${resendButton()}</div>`;
  }
  if (step === 'password') {
    return `${rail(steps, step)}
      <p class="lede">${w('choose_new_for', { who })}</p>
      <div id="auth-msg"></div>
      ${authField('au-pass', w('new_password'), { name: 'password', type: 'password', placeholder: w('at_least', { n: state.passwordMin }),
        auto: 'new-password', reveal: true })}
      ${authField('au-confirm', w('confirm_new_password'), { name: 'confirm', type: 'password', placeholder: w('repeat_password'),
        auto: 'new-password', reveal: true })}
      ${pwHints()}
      <button class="primary" type="submit">${icon('check')} ${w('set_new_password')}</button>`;
  }
  if (step === 'done') {
    return `${rail(steps, step)}
      <div id="auth-msg"></div>
      <button class="primary" type="submit">${icon('right')} ${w('back_to_signin')}</button>`;
  }
  return `${rail(steps, 'account')}
    <p class="lede">${w('forgot_lede')}</p>
    <div id="auth-msg"></div>
    ${authField('au-ident', w('ident'), { placeholder: w('ident_placeholder'), auto: 'username',
      extra: 'autocapitalize="off" spellcheck="false"' })}
    <button class="primary" type="submit">${icon('mail')} ${w('send_reset')}</button>
    <p class="alt"><button type="button" class="link" data-mode="signin">${w('back_to_signin')}</button></p>`;
}

function firstAccountView() {
  return authShell(`<h1>${w('first_title')}</h1>
    <p class="lede">${state.reservedOwner
      ? w('first_reserved', { owner: esc(state.reservedOwner) })
      : w('first_nobody')}</p>
    <div id="auth-msg"></div>
    ${authField('au-name', w('display_name'), { name: 'name', placeholder: w('display_name_placeholder'), auto: 'name' })}
    ${authField('au-user', w('user_name'), { name: 'username', placeholder: w('user_name_placeholder', { min: state.userLen[0], max: state.userLen[1] }), auto: 'username',
      hint: w('user_name_optional'), extra: 'autocapitalize="off" spellcheck="false" data-lower' })}
    ${authField('au-email', w('email'), { name: 'email', type: 'email', placeholder: w('email_placeholder'), auto: 'email',
      value: state.reservedOwner || undefined, readonly: !!state.reservedOwner,
      extra: 'inputmode="email" autocapitalize="off" spellcheck="false"' })}
    ${authField('au-pass', w('password'), { name: 'password', type: 'password', placeholder: w('at_least', { n: state.passwordMin }),
      auto: 'new-password', reveal: true })}
    ${authField('au-confirm', w('confirm_password'), { name: 'confirm', type: 'password', placeholder: w('repeat_password'),
      auto: 'new-password', reveal: true })}
    ${pwHints()}
    <button class="primary" type="submit">${icon('check')} ${w('create_owner')}</button>`);
}

async function landed(user) {
  state.user = user;
  try { localStorage.setItem('portal.signed_in_before', '1'); } catch { /* next visit opens Sign up: harmless */ }
  remembersFor(user && user.id);        // what this browser remembers from here on belongs to THIS person
  state.needsFirstAccount = false;
  await refresh();
  // a link that named a screen (a door's /k/<id> -> #/read?w=<id>) opens that screen after sign-in; else the landing
  toLanding();
  render();
}

/** No screen asked for (or one this person may not open): the landing (a door's first screen, e.g. #/read; a self-filer's
 *  My return) when granted, else the first screen this person may open. On sign-in, and on a page opened already signed in. */
let leaving = false;   // 2026-10-26: going to the host's own page - draw nothing on the way (a 'No view' flashed)
function toLanding() {
  const asked = (location.hash || '').replace(/^#\//, '').split('?')[0];
  if (!asked || !([...screens(), ...askable()].some((s) => s.id === asked) || ((state.elsewhere || {}).screens || []).includes(asked))) {
    const land = (typeof config.landing === 'function' ? config.landing() : config.landing) || '';
    if (land.startsWith('/')) { leaving = true; location.replace(land); return; }   // a page of the host's own (AstroFy: its home page)
    const first = screens().find((s) => !s.hidden && !s.no_menu);
    const to = may(land.replace(/^#\//, '')) || !first ? land : `#/${first.id}`;
    if (to) history.replaceState(null, '', to);
  }
}

/** Signed in (or out): nothing typed on the card is kept in memory. */
function forgetFlow() {
  setMode('signin');
  flow.values = {};
  flow.focus = false;
}

/** Shape only: a box left empty is named before a code is spent on it. The server decides the rest. */
function missing(form, ids) {
  const empty = ids.map((id) => form.querySelector(`#${id}`)).filter((el) => el && !el.value.trim());
  empty.forEach((el) => {
    const f = el.closest('.field');
    f.classList.add('has-err');
    const out = f.querySelector('.err');
    out.textContent = w('fill_this_in');
    out.hidden = false;
    el.setAttribute('aria-invalid', 'true');
  });
  if (empty.length) empty[0].focus();
  return empty.length > 0;
}

const waitMs = (d) => (Number(d && d.resend_after_seconds) || state.code.resend) * 1000;

async function submitStep(form, msg) {
  const v = (id) => flow.values[id] || '';
  const post = (path, body) => api(path, { method: 'POST', body });

  if (state.needsFirstAccount) {
    const d = await post('/api/auth/first-account', { display_name: v('au-name').trim(), username: v('au-user').trim(),
      email: v('au-email').trim(), password: v('au-pass'), confirm: v('au-confirm') });
    forgetFlow();
    await landed(d.user);
    return;
  }
  const step = currentStep();

  if (state.authMode === 'demo') {
    if (step === 'details') {
      if (missing(form, ['au-name', 'au-email'])) return;
      const d = await post('/api/demo/code/send', { name: v('au-name').trim(), email: v('au-email').trim() });
      delete flow.values['au-code'];
      goStep('code', { resendAt: Date.now() + waitMs(d), note: { kind: 'ok', text: d.message } });
      return;
    }
    const d = await post('/api/demo/code/check', { name: v('au-name').trim(), email: v('au-email').trim(), code: v('au-code').trim() });
    forgetFlow();
    await landed(d.user);
    return;
  }

  if (state.authMode === 'signin') {
    const d = await post('/api/auth/signin', { identity: v('au-ident').trim(), password: v('au-pass') });
    forgetFlow();
    await landed(d.user);
    return;
  }

  if (state.authMode === 'signup') {
    if (step === 'details') {
      if (missing(form, ['au-name', 'au-user', 'au-email'])) return;
      const d = await post('/api/auth/code/send', { purpose: 'signup', identity: v('au-email').trim(),
        display_name: v('au-name').trim(), username: v('au-user').trim() });   // every detail checked before a code is mailed
      if (d.mail === false) {
        goStep('password', { noMail: true, proof: '',
          note: { kind: 'info', text: w('no_mail_signup') } });
        return;
      }
      delete flow.values['au-code'];
      goStep('code', { noMail: false, proof: '', resendAt: Date.now() + waitMs(d),
        note: d.message ? { kind: 'ok', text: d.message } : null });
      return;
    }
    if (step === 'code') {
      const d = await post('/api/auth/code/check', { purpose: 'signup', identity: v('au-email').trim(), code: v('au-code').trim() });
      delete flow.values['au-code'];
      goStep('password', { proof: d.proof, note: { kind: 'ok', text: w('email_confirmed') } });
      return;
    }
    const d = await post('/api/auth/signup', { display_name: v('au-name').trim(), username: v('au-user').trim(),
      email: v('au-email').trim(), password: v('au-pass'), confirm: v('au-confirm'), proof: flow.proof });
    forgetFlow();
    toast(w('welcome'), 'ok');
    await landed(d.user);
    return;
  }

  // forgot password
  if (step === 'account') {
    if (missing(form, ['au-ident'])) return;
    const d = await post('/api/auth/code/send', { purpose: 'reset', identity: v('au-ident').trim() });
    if (d.mail === false) { say(msg, 'info', esc(d.message)); return; }       // stay: the owner resets it
    delete flow.values['au-code'];
    goStep('code', { proof: '', resendAt: Date.now() + waitMs(d), note: d.message ? { kind: 'ok', text: d.message } : null });
    return;
  }
  if (step === 'code') {
    const d = await post('/api/auth/code/check', { purpose: 'reset', identity: v('au-ident').trim(), code: v('au-code').trim() });
    delete flow.values['au-code'];
    goStep('password', { proof: d.proof });
    return;
  }
  if (step === 'password') {
    const d = await post('/api/auth/reset', { identity: v('au-ident').trim(), proof: flow.proof,
      password: v('au-pass'), confirm: v('au-confirm') });
    delete flow.values['au-pass'];
    delete flow.values['au-confirm'];
    goStep('done', { proof: '', note: { kind: 'ok', text: d.message || w('password_updated') } });
    return;
  }
  const identity = v('au-ident');                // done → the sign-in tab, identity already typed
  setMode('signin');
  flow.values['au-ident'] = identity;
  render();
}

/** An error at the last step can be about an earlier one: a taken user name goes back to the details,
 *  an expired proof back to the code. Everything else stays where it is, beside its field. */
function stepError(err, form, msg) {
  const field = err && err.data && err.data.field;
  if (!state.needsFirstAccount && flow.step === 'password') {
    if (state.authMode === 'signup' && ['name', 'username', 'email'].includes(field)) {
      goStep('details', { error: err, proof: '', noMail: false });
      return;
    }
    if (field === 'code') {
      goStep('code', { error: err, proof: '', noMail: false, resendAt: 0 });
      return;
    }
  }
  showFieldError(form, err, msg);
}

function wireSignin(root) {
  wireSecrets(root);
  wireHowto(root);
  clearInterval(resendTimer);
  root.querySelectorAll('[data-mode]').forEach((b) => {
    b.onclick = () => { setMode(b.dataset.mode); render(); };
  });
  const form = root.querySelector('#authform');
  if (!form) return;
  const msg = root.querySelector('#auth-msg');
  wireFieldErrors(form);
  wirePwHints(form, 'au-pass', 'au-confirm');
  form.querySelectorAll('input[id]').forEach((el) => {
    el.addEventListener('input', () => {
      if (el.hasAttribute('data-lower') && el.value !== el.value.toLowerCase()) {
        const at = el.selectionStart;
        el.value = el.value.toLowerCase();
        try { el.setSelectionRange(at, at); } catch { /* not every input type has a caret */ }
      }
      if (el.hasAttribute('data-digits')) el.value = el.value.replace(/\D/g, '');
      flow.values[el.id] = el.value;
    });
  });
  root.querySelectorAll('[data-act="details"],[data-act="account"]').forEach((b) => {
    b.onclick = () => goStep(b.dataset.act, { proof: '', noMail: false, resendAt: 0 });
  });

  const resend = form.querySelector('[data-act="resend"]');
  if (resend) {
    const tick = () => {
      const left = Math.ceil((flow.resendAt - Date.now()) / 1000);
      const wait = resend.querySelector('.wait');
      resend.disabled = left > 0;
      if (wait) wait.textContent = left > 0 ? w('resend_in', { at: `${Math.floor(left / 60)}:${String(left % 60).padStart(2, '0')}` }) : '';
      if (left <= 0) clearInterval(resendTimer);
    };
    resendTimer = setInterval(tick, 1000);
    tick();
    resend.onclick = () => busy(resend, async () => {
      const signup = state.authMode === 'signup';
      try {
        const d = state.authMode === 'demo'
          ? await api('/api/demo/code/send', { method: 'POST', body: { name: (flow.values['au-name'] || '').trim(), email: (flow.values['au-email'] || '').trim() } })
          : await api('/api/auth/code/send', { method: 'POST', body: { purpose: signup ? 'signup' : 'reset',
            identity: ((signup ? flow.values['au-email'] : flow.values['au-ident']) || '').trim() } });
        flow.resendAt = Date.now() + waitMs(d);
        clearFieldErrors(form);
        say(msg, d.mail === false ? 'info' : 'ok', esc(d.message));
      } catch (err) { showFieldError(form, err, msg); }
    }).then(() => {
      clearInterval(resendTimer);
      resendTimer = setInterval(tick, 1000);
      tick();
    });
  }

  if (flow.note) say(msg, flow.note.kind, esc(flow.note.text));
  if (flow.focus) {
    flow.focus = false;
    const boxes = [...form.querySelectorAll('input:not([readonly]):not([type=hidden])')];
    (boxes.find((i) => !i.value) || form.querySelector('button[type=submit]'))?.focus();
  }
  if (flow.error) { showFieldError(form, flow.error, msg); flow.error = null; }

  form.onsubmit = async (e) => {
    e.preventDefault();
    form.querySelectorAll('input[id]').forEach((i) => { flow.values[i.id] = i.value; });   // autofill fires no input event
    clearFieldErrors(form);
    try {
      await busy(form.querySelector('button[type=submit]'), () => submitStep(form, msg));
    } catch (err) { stepError(err, form, msg); }
  };
}

/** #/invite?token=… arrives by email. The older #/verify and #/reset links are answered, not followed:
 *  the portal sends a code now. */
function emailLink() {
  const m = (location.hash || '').match(/^#\/(verify|reset|invite)\?token=([\w-]+)/);
  return m ? { kind: m[1], token: m[2] } : null;
}

/** Drop the link from the address bar without a hashchange, so a redraw does not open it again. */
function leaveLink() {
  history.replaceState(null, '', location.pathname + location.search);
}

async function showEmailLink(root, link) {
  root.className = '';
  trackView(`#/${link.kind}`);
  const oneButton = (html, label) => {
    root.innerHTML = authShell(`${html}<button class="primary" type="submit">${icon('right')} ${label}</button>`);
    wireHowto(root);
  };
  if (link.kind !== 'invite') {
    oneButton(`<h1>${w('link_changed_title')}</h1>
      <div class="note info">${icon('info')}<div>${w('link_changed_body')}</div></div>`, w(state.user ? 'open_portal' : 'go_to_forgot'));
    root.querySelector('#authform').onsubmit = (e) => {
      e.preventDefault();
      leaveLink();
      if (!state.user) setMode('forgot');
      render();
    };
    return;
  }
  let forWhom = '';
  try {
    forWhom = (await api(`/api/auth/token/invite/${encodeURIComponent(link.token)}`)).email;
  } catch (e) {
    oneButton(`<h1>${w('link_failed_title')}</h1>
      <div class="note bad">${icon('alert')}<div>${esc(e.message)}</div></div>`, w('back_to_signin'));
    root.querySelector('#authform').onsubmit = (ev) => { ev.preventDefault(); leaveLink(); render(); };
    return;
  }
  root.innerHTML = authShell(`<h1>${w('invited_title')}</h1>
    <p class="lede">${forWhom ? w('invited_for', { email: esc(forWhom) }) : w('invited_lede')}</p>
    <div id="auth-msg"></div>
    ${authField('au-pass', w('new_password'), { name: 'password', type: 'password', placeholder: w('at_least', { n: state.passwordMin }),
      auto: 'new-password', reveal: true, value: '' })}
    ${authField('au-confirm', w('confirm_password'), { name: 'confirm', type: 'password', placeholder: w('repeat_password'),
      auto: 'new-password', reveal: true, value: '' })}
    ${pwHints()}
    <button class="primary" type="submit">${icon('check')} ${w('save_and_signin')}</button>`);
  const form = root.querySelector('#authform');
  const msg = root.querySelector('#auth-msg');
  wireSecrets(root);
  wireHowto(root);
  wireFieldErrors(form);
  wirePwHints(form, 'au-pass', 'au-confirm');
  form.onsubmit = async (e) => {
    e.preventDefault();
    clearFieldErrors(form);
    try {
      await busy(form.querySelector('button[type=submit]'), async () => {
        const d = await api('/api/auth/invite', { method: 'POST', body: { token: link.token,
          password: form.querySelector('#au-pass').value, confirm: form.querySelector('#au-confirm').value } });
        leaveLink();
        await landed(d.user);
      });
    } catch (err) { showFieldError(form, err, msg); }
  };
}

/** After an owner's reset with "require change": only this, until the person has their own password.
 *  The server refuses everything else meanwhile (403 must_change_password). */
function mustChangeView() {
  const u = state.user;
  return authShell(`<span class="eyebrow authbrow">${w('reset_eyebrow')}</span>
    <h1>${w('must_change_title')}</h1>
    <p class="lede">${w('must_change_lede', { who: esc(u.name || u.email), email: u.name && u.email ? ` (${esc(u.email)})` : '' })}</p>
    <div id="auth-msg"></div>
    ${authField('au-current', w('temporary_password'), { name: 'current', type: 'password', auto: 'current-password',
      reveal: true, value: '' })}
    ${authField('au-pass', w('new_password'), { name: 'password', type: 'password', placeholder: w('at_least', { n: state.passwordMin }),
      auto: 'new-password', reveal: true, value: '' })}
    ${authField('au-confirm', w('confirm_new_password'), { name: 'confirm', type: 'password', placeholder: w('repeat_password'),
      auto: 'new-password', reveal: true, value: '' })}
    ${pwHints()}
    <button class="primary" type="submit">${icon('check')} ${w('update_password')}</button>
    <p class="alt"><button type="button" class="link" id="mc-out">${w('signout_instead')}</button></p>`);
}

function wireMustChange(root) {
  const form = root.querySelector('#authform');
  const msg = root.querySelector('#auth-msg');
  wireSecrets(root);
  wireHowto(root);
  wireFieldErrors(form);
  wirePwHints(form, 'au-pass', 'au-confirm');
  root.querySelector('#mc-out').onclick = signOut;
  form.onsubmit = async (e) => {
    e.preventDefault();
    clearFieldErrors(form);
    const val = (id) => form.querySelector(`#${id}`).value;
    try {
      await busy(form.querySelector('button[type=submit]'), async () => {
        await api('/api/auth/password', { method: 'POST', body: {
          current: val('au-current'), password: val('au-pass'), confirm: val('au-confirm') } });
        state.user = { ...state.user, must_change_password: false };
        await refresh();
        toast(w('password_changed'), 'ok');
        render();
      });
    } catch (err) { showFieldError(form, err, msg); }
  };
}

async function signOut() {
  await api('/api/auth/signout', { method: 'POST' }).catch(() => {});
  state.user = null;
  remembersFor('');                     // the next person on this browser reads none of this one's preferences
  newVisit();                           // and their page views are a visit of their own
  forgetFlow();
  render();
}

// --- shell ---------------------------------------------------------------------------------------

// 2026-10-03 owner: "why load menu when you don't have access". The menu shows ONLY what this person
// may open — same rule as the Studio and Individual portals. A screen a rule shut is no longer a locked
// menu row: it is reachable by its link (#/<id> shows the ask card) and from user menu -> Ask for more access.
function screens() {
  return state.catalog.filter((s) => may(s.id));
}

/** Screens this person may ask for: an ordinary screen a rule shut. Never an admin screen nobody opened
 *  for them, nor one marked `hide_when_denied` (nothing on it yet: Buy a key before anyone sells one). */
function askable() {
  return state.catalog.filter((s) => !may(s.id) && !(s.admin || s.hide_when_denied));
}

function currentScreen() {
  const id = (location.hash || '').replace(/^#\//, '').split('?')[0];
  const list = screens();
  return list.find((s) => s.id === id) || askable().find((s) => s.id === id)
    || list.find((s) => !s.hidden && !s.no_menu) || null;   // no screen named: the first MENU screen, never a no_menu subject (the bottom bar)
}

function shellView(route) {
  const list = screens().filter((s) => !s.hidden && !s.no_menu);   // Menu builder took it off the menu: the page still opens by its link
  const groups = [...new Set(list.map((s) => s.group || ''))];
  const folded = sideCollapsed();
  const nav = groups.map((g) => `${g ? `<div class="sep">${esc(g)}</div>` : ''}` + list.filter((s) => (s.group || '') === g)
    .map((s) => `<a href="#/${esc(s.id)}" class="${route && s.id === route.id ? 'on' : ''}"
        ${folded ? `data-tip="${esc(s.label)}"` : ''} aria-label="${esc(s.label)}">
        ${icon(s.icon || 'right', 17)} <span class="lbl">${esc(s.label)}</span>
        ${s.id === 'issues' && state.issuesOpen ? `<span class="badge">${state.issuesOpen}</span>` : ''}</a>`).join('')).join('');
  const theme = shownTheme();
  const themeTip = w(theme === 'dark' ? 'to_light' : 'to_dark');
  const initials = (state.user.name || state.user.email || '?').trim()[0].toUpperCase();

  return `<div class="shell ${folded ? 'collapsed' : ''}">
    <nav class="side" id="side">
      <div class="brand">${config.home ? `<a class="brand-home" href="${esc(config.home)}" aria-label="${esc(state.productName)}">` : ''}${config.logo(30)}
        <div class="name">${esc(state.productName)}${brandSub() ? `<span>${esc(brandSub())}</span>` : ''}</div>${config.home ? '</a>' : ''}
        <button type="button" class="ghost icon fold" id="fold" data-tip="${esc(w(folded ? 'expand_menu' : 'collapse_menu'))}"
          aria-label="${esc(w(folded ? 'expand_menu' : 'collapse_menu'))}" aria-expanded="${folded ? 'false' : 'true'}">${icon(folded ? 'dright' : 'dleft', 17)}</button></div>
      <div class="nav">${nav}</div>
      ${slot(config.navFoot) ? `<div class="foot">${slot(config.navFoot)}</div>` : ''}
      ${poweredBy()}
    </nav>
    <main class="main">
      <div class="topbar">
        <button class="ghost icon only-narrow" id="burger" type="button" aria-label="${esc(w('menu'))}">${icon('menu', 18)}</button>
        ${route ? config.topbar(route) : ''}
        ${omniPill()}
        <span class="spacer"></span>
        ${route ? config.topbarEnd(route) : ''}
        ${route && state.guides.includes(route.id) ? guideButton(route.id) : ''}
        ${route ? howtoButton(route.id) : ''}
        <button class="ghost icon refresher" id="refresh" type="button" data-tip="${esc(w('refresh_page'))}"
          aria-label="${esc(w('refresh_page'))}">${icon('refresh', 18)}</button>
        <button class="ghost icon bellbtn" id="bell" type="button" data-tip="${esc(w('bell'))}" aria-label="${esc(w('bell'))}">${icon('bell', 17)}${state.bellUnread ? `<span class="badge">${state.bellUnread > 99 ? '99+' : state.bellUnread}</span>` : ''}</button>
        <button class="ghost icon" id="theme" type="button" data-tip="${esc(themeTip)}"
          aria-label="${esc(themeTip)}">${icon(theme === 'dark' ? 'sun' : 'moon', 17)}</button>
        <div class="usermenu">
          <button type="button" id="whoami" class="who" aria-haspopup="true" aria-expanded="false">
            <span class="av">${esc(initials)}</span>
            <span class="nm">${esc(state.user.name || state.user.email)}</span>
            ${icon('down', 15)}</button>
          <div class="pop" id="userpop" hidden>
            <div class="head"><b>${esc(state.user.name || state.user.email)}</b>
              <span>${esc(state.user.email)}</span>
              <span class="tag ${state.user.role === 'owner' ? 'brand' : ''}">${esc(state.user.role)}</span></div>
            ${slot(config.userMenu)}
            ${askable().length ? `<button type="button" id="ask-more">${icon('lock', 15)} ${w('ask_more_access')}</button>` : ''}
            ${state.startCard ? `<button type="button" id="start-here">${icon('flag', 15)} ${esc(state.startCard.menu)}</button>` : ''}
            <button type="button" id="report-issue">${icon('alert', 15)} ${w('report_issue')}</button>
            <button type="button" id="my-reports">${icon('chat', 15)} ${w('my_reports')}</button>
            <button type="button" id="chpass">${icon('shield', 15)} ${w('change_password')}</button>
            <button type="button" id="signout">${icon('right', 15)} ${w('sign_out')}</button>
          </div>
        </div>
      </div>
      ${storageBanner()}
      ${healthBanner()}
      ${replyBanners()}
      ${ruleBanners()}
      ${backBar(route)}
      <div id="startcard"></div>
      <div id="page"></div>
    </main></div>`;
}

// 2026-10-02 owner: "when I go from the Assessment Builder to any module there should be a Back to Assessment Builder
// button - only where you came from the assessment". ONE way for every screen: a link marked data-from="<screen>"
// remembers where it was pressed; only the screen it opened shows "Back to <that screen>", and going anywhere else forgets it.
const BACK = 'portal.back';
const backOf = () => { try { return JSON.parse(sessionStorage.getItem(BACK) || 'null'); } catch { return null; } };
function backBar(route) {
  const b = backOf();
  if (!b || !route) return '';
  const from = state.catalog.find((s) => s.id === b.from);
  if (b.to !== route.id || !from) {
    try { sessionStorage.removeItem(BACK); } catch { /* nothing kept */ }
    return '';
  }
  return `<div class="backbar"><a class="small ghost button" href="#/${esc(from.id)}">${icon('left', 13)} ${esc(w('back_to', { name: from.label }))}</a></div>`;
}
document.addEventListener('click', (e) => {
  const a = e.target.closest && e.target.closest('a[data-from]');
  if (!a) return;
  const to = (a.getAttribute('href') || '').replace(/^#\//, '').split('?')[0];
  try { sessionStorage.setItem(BACK, JSON.stringify({ from: a.dataset.from, to })); } catch { /* the button just does not show */ }
}, true);

// --- the top search ------------------------------------------------------------------------------
/** One box that reaches every screen and every action this person may open. The rows, the ranking and
 *  every word come from the server (core/find.py, chips find.*): nothing here knows a screen by name,
 *  so a screen added tomorrow is searchable with no change to this file. */
const findText = (key, values = {}) => String(((state.find || {})[key]) || '')
  .replace(/\{(\w+)\}/g, (_, k) => String(values[k] ?? ''));
const onMac = () => /mac|iphone|ipad/i.test(navigator.platform || navigator.userAgent || '');

/** The mark on the search box: a magnifier drawn once, in the brand's own gradient, with the spark
 *  that says "this looks everywhere". Two paths, no library, crisp at every size. */
function omniMark(size = 17) {
  const id = `og${Math.random().toString(36).slice(2, 7)}`;
  return `<svg class="omni-mark" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <defs><linearGradient id="${id}" x1="3" y1="3" x2="21" y2="21" gradientUnits="userSpaceOnUse">
      <stop stop-color="var(--brand)"/><stop offset="1" stop-color="var(--brand-2, var(--brand))"/></linearGradient></defs>
    <circle cx="10.5" cy="10.5" r="6.5" stroke="url(#${id})" stroke-width="1.9"/>
    <path d="M15.4 15.4 21 21" stroke="url(#${id})" stroke-width="1.9" stroke-linecap="round"/>
    <path d="M10.5 6.6l.85 2.05L13.4 9.5l-2.05.85L10.5 12.4l-.85-2.05L7.6 9.5l2.05-.85L10.5 6.6Z"
      fill="url(#${id})" opacity=".85"/></svg>`;
}

function omniPill() {
  if (!state.find) return '';
  return `<button type="button" class="omni-pill" id="omni-open" aria-haspopup="dialog"
      aria-label="${esc(findText('placeholder'))}">
      ${omniMark(16)}<span class="omni-pill-text">${esc(findText('placeholder'))}</span>
      <kbd>${esc(findText(onMac() ? 'shortcut_mac' : 'shortcut'))}</kbd></button>`;
}

let omniOpen = false;
function openOmni() {
  if (omniOpen || !state.user || mustChange() || !state.find) return;
  omniOpen = true;
  const host = document.createElement('div');
  host.className = 'omni-wrap';
  host.innerHTML = `<div class="omni-veil"></div>
    <div class="omni" role="dialog" aria-modal="true" aria-label="${esc(findText('title'))}">
      <div class="omni-head">${omniMark(20)}
        <input id="omni-q" type="search" autocomplete="off" spellcheck="false" enterkeyhint="go"
          placeholder="${esc(findText('placeholder'))}" aria-label="${esc(findText('placeholder'))}"/>
        <kbd class="omni-esc">Esc</kbd></div>
      <div class="omni-list" id="omni-list" role="listbox" aria-label="${esc(findText('title'))}"></div>
      <div class="omni-foot"><span>${esc(findText('keys_hint'))}</span><span>${esc(findText('hint'))}</span></div>
    </div>`;
  document.body.appendChild(host);
  const input = host.querySelector('#omni-q');
  const list = host.querySelector('#omni-list');
  let rows = [];
  let at = 0;
  let seq = 0;

  const close = () => {
    if (!omniOpen) return;
    omniOpen = false;
    host.remove();
    document.removeEventListener('keydown', onKey, true);
  };
  const go = () => {
    const row = rows[at];
    if (!row) return;
    close();
    if (location.hash === row.href) render(); else location.hash = row.href;
  };
  const draw = (searched) => {
    if (!rows.length) {
      list.innerHTML = `<div class="omni-none">${icon('search', 22)}
        <b>${esc(findText('nothing', { q: input.value.trim() }))}</b>
        <span>${esc(findText('nothing_hint'))}</span></div>`;
      return;
    }
    list.innerHTML = `<div class="omni-cap">${esc(findText(searched ? 'results' : 'suggested'))}</div>` + rows.map((r, i) => `
      <button type="button" class="omni-row ${i === at ? 'on' : ''}" data-i="${i}" role="option"
        aria-selected="${i === at}">
        <span class="omni-ico">${icon(r.icon || 'right', 16)}</span>
        <span class="omni-txt"><b>${esc(r.label)}</b>
          <span>${esc(r.kind === 'screen' ? r.group : findText('in_menu', { menu: r.menu || '', screen: r.group }))}</span></span>
        <span class="omni-go">${esc(findText('open_label'))} ${icon('right', 14)}</span></button>`).join('');
    list.querySelectorAll('.omni-row').forEach((b) => {
      b.onmouseenter = () => { at = Number(b.dataset.i); paint(); };
      b.onclick = () => { at = Number(b.dataset.i); go(); };
    });
  };
  const paint = () => list.querySelectorAll('.omni-row').forEach((b, i) => {
    b.classList.toggle('on', i === at);
    b.setAttribute('aria-selected', String(i === at));
    if (i === at) b.scrollIntoView({ block: 'nearest' });
  });
  const look = async () => {
    const mine = ++seq;
    try {
      const d = await api(`/api/core/find?q=${encodeURIComponent(input.value)}`);
      if (mine !== seq || !omniOpen) return;             // an older answer never overwrites a newer one
      if (d.texts) state.find = d.texts;
      rows = d.results || [];
      at = 0;
      draw(d.searched);
    } catch { /* the page keeps working; the box simply shows what it had */ }
  };
  function onKey(e) {
    if (e.key === 'Escape') { e.preventDefault(); close(); return; }
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      if (!rows.length) return;
      at = (at + (e.key === 'ArrowDown' ? 1 : rows.length - 1)) % rows.length;
      paint();
      return;
    }
    if (e.key === 'Enter') { e.preventDefault(); go(); }
  }
  document.addEventListener('keydown', onKey, true);
  host.querySelector('.omni-veil').onclick = close;      // a search box loses nothing when it closes
  let timer = 0;
  input.oninput = () => { clearTimeout(timer); timer = setTimeout(look, 120); };
  requestAnimationFrame(() => input.focus());
  look();
}

/** Ctrl/Cmd+K anywhere, or "/" when the person is not typing into something. */
function installOmniKeys() {
  document.addEventListener('keydown', (e) => {
    const typing = e.target instanceof Element
      && e.target.closest('input, textarea, select, [contenteditable="true"]');
    if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K')) { e.preventDefault(); openOmni(); return; }
    if (e.key === '/' && !typing && !e.ctrlKey && !e.metaKey && !e.altKey) { e.preventDefault(); openOmni(); }
  });
}

/** The line under the product name: a portal may pass a function, so an edition can set it from the server. */
const brandSub = () => (typeof config.brandSub === 'function' ? config.brandSub() : config.brandSub) || '';

/** The demo banner's countdown to the nightly reset (core/demo.py next_reset); ticked every second below. */
function demoLeft() {
  const left = Math.max(0, Math.floor(state.demoResetAt - Date.now() / 1000));
  if (!left) return dw('resetting');
  return dw('left', { h: Math.floor(left / 3600), m: Math.floor(left / 60) % 60, s: left % 60 });
}
setInterval(() => { if (state.demo) document.querySelectorAll('.demo-left').forEach((el) => { el.textContent = demoLeft(); }); }, 1000);

/** Banners a rule put up (a Rule Chip Builder outcome). The text is the rule's, escaped; × hides it for this person. */
function ruleBanners() {
  return (state.demo ? `<div class="note warn rulebanner demobanner">${icon('clock')}<div>${esc(dw('banner', { when: new Date(state.demoResetAt * 1000).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }) }))}
    <b class="demo-left">${esc(demoLeft())}</b></div></div>` : '') + state.banners.map((b) => `<div class="note ${esc(b.tone)} rulebanner" data-banner="${esc(b.id)}">${icon(b.tone === 'ok' ? 'check' : 'alert')}
    <div>${esc(b.text).replace(/\n/g, '<br/>')}</div>
    <button type="button" class="ghost icon small" data-dismiss="${esc(b.id)}" aria-label="${esc(w('dismiss'))}" data-tip="${esc(w('dismiss'))}">${icon('close', 15)}</button></div>`).join('');
}

/** 2026-09-28 Report an issue: the portal admin's answer reaches the reporter HERE, not by email (core/issues.py). */
function replyBanners() {
  return state.issueReplies.map((r) => `<div class="note ok">${icon('check')}<div>${esc(w('report_reply', { title: r.title, reply: r.reply }))}</div>
    <button type="button" class="ghost icon small" data-reply-seen="${esc(r.id)}" aria-label="${esc(w('dismiss'))}" data-tip="${esc(w('dismiss'))}">${icon('close', 15)}</button></div>`).join('');
}

/** The owner asked this person to clean up. Shown on every page until the owner closes it, because
 *  an email can go to spam and a portal with no mail server has no other way to reach them. */
/** 2026-10-23 owner ("a warning in the portal that replaces the message, not add to the list"): what the Daily health
 *  check found, for owners, on every page. The next check replaces it; a fixed problem leaves by itself. */
function healthBanner() {
  const h = state.health;
  if (!h || !h.problems.length) return '';
  return `<div class="note warn healthbar">${icon('alert')}<div><b>${w('health_title', { n: h.problems.length })}</b>
    <ul class="small">${h.problems.map((p) => `<li><b>${esc(p.name)}</b> - ${esc(p.say)}</li>`).join('')}</ul>
    <span class="small muted">${w('health_checked', { when: esc(clockAt(h.at)) })}</span> <a href="#/agents">${w('health_open')}</a></div></div>`;
}

function storageBanner() {
  const r = state.storageRequest;
  if (!r) return '';
  const mb = r.bytes >= 1024 ** 3 ? `${(r.bytes / 1024 ** 3).toFixed(2)} GB` : `${Math.round(r.bytes / 1024 ** 2)} MB`;
  return `<div class="note ${r.requests >= r.max ? 'bad' : 'warn'}">${icon('alert')}<div>
    <b>${w(r.requests > 1 ? 'storage_asked_reminder' : 'storage_asked', { n: r.requests, max: r.max })}</b>
    ${w('storage_hold', { size: mb, files: r.files, date: esc(r.delete_from) })}
    ${r.note ? `<br/><i>“${esc(r.note)}”</i>` : ''}
    ${r.href ? ` <a href="${esc(r.href)}">${w('manage_files')}</a>` : ''}</div></div>`;
}

/** Re-read who you are and what you may open, then redraw the current page from the server. No full
 *  reload: the menu, theme and your place stay put. The icon turns while it works — at least a
 *  moment, so a fast answer still reads as "done" rather than as a click that did nothing. */
async function refreshPage() {
  const btn = document.getElementById('refresh');
  if (!btn || btn.classList.contains('spinning')) return;
  btn.classList.add('spinning');
  btn.setAttribute('aria-busy', 'true');
  const started = Date.now();
  await refresh();
  await new Promise((r) => setTimeout(r, Math.max(0, 550 - (Date.now() - started))));
  render();
  const fresh = document.getElementById('refresh');
  if (!fresh) return;
  const at = clockAt('', true);
  fresh.dataset.tip = w('refreshed_at', { at });
  fresh.classList.add('done');
  setTimeout(() => { fresh.classList.remove('done'); }, 1400);
}

function wireShell(root, route) {
  const pop = root.querySelector('#userpop');
  const btn = root.querySelector('#whoami');
  btn.onclick = (e) => {
    e.stopPropagation();
    pop.hidden = !pop.hidden;
    btn.setAttribute('aria-expanded', String(!pop.hidden));
  };
  document.addEventListener('click', (e) => {
    if (!pop.hidden && !root.querySelector('.usermenu').contains(e.target)) pop.hidden = true;
  });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') pop.hidden = true; });

  // One click, one visible change — and no redraw of the page, so nothing half-typed is lost.
  const pill = root.querySelector('#omni-open');
  if (pill) pill.onclick = () => openOmni();
  // the bell (core/bell.py): open = read; each note links to the screen it is about
  root.querySelector('#bell').onclick = async () => {
    let rows = [];
    try { rows = (await api('/api/core/bell')).rows; } catch (err) { toast(err.message, 'bad'); return; }
    const close = modal(w('bell_title'), rows.length ? `<ul class="bell-list">${rows.map((r) => `<li class="${r.seen ? '' : 'new'}">
        ${r.href ? `<a href="${esc(r.href)}" data-bell-go>${esc(r.text)}</a>` : esc(r.text)}<span class="small muted">${when(r.at)}</span></li>`).join('')}</ul>`
      : `<p class="muted">${esc(w('bell_empty'))}</p>`, {
      onOpen: (body) => body.querySelectorAll('[data-bell-go]').forEach((a) => { a.addEventListener('click', () => close()); }) });
    if (state.bellUnread) {
      api('/api/core/bell/seen', { method: 'POST' }).catch(() => {});
      state.bellUnread = 0;
      root.querySelector('#bell .badge')?.remove();
    }
  };
  root.querySelector('#theme').onclick = (e) => {
    const now = nextTheme();
    const b = e.currentTarget;
    b.innerHTML = icon(now === 'dark' ? 'sun' : 'moon', 17);
    b.dataset.tip = w(now === 'dark' ? 'to_light' : 'to_dark');
    b.setAttribute('aria-label', b.dataset.tip);
  };
  root.querySelectorAll('[data-dismiss]').forEach((b) => {
    b.onclick = async () => {
      const id = b.dataset.dismiss;
      state.banners = state.banners.filter((x) => x.id !== id);
      b.closest('.rulebanner')?.remove();
      try { await api(`/api/core/banners/${encodeURIComponent(id)}/dismiss`, { method: 'POST' }); } catch { /* shown again next visit */ }
    };
  });
  // Folding changes the MENU only. It must not redraw the page: a half-edited script would be lost.
  root.querySelector('#fold').onclick = (e) => {
    const folded = !sideCollapsed();
    try { localStorage.setItem('portal.side', folded ? 'collapsed' : 'open'); } catch { /* per-browser nicety */ }
    root.querySelector('.shell').classList.toggle('collapsed', folded);
    const b = e.currentTarget;
    b.innerHTML = icon(folded ? 'dright' : 'dleft', 17);
    b.dataset.tip = w(folded ? 'expand_menu' : 'collapse_menu');
    b.setAttribute('aria-label', b.dataset.tip);
    b.setAttribute('aria-expanded', String(!folded));
    root.querySelectorAll('.nav a').forEach((a) => {
      if (folded) a.dataset.tip = a.getAttribute('aria-label');
      else delete a.dataset.tip;
    });
  };
  root.querySelector('#refresh').onclick = () => {
    if (!dirtyNow()) { refreshPage(); return; }
    confirmDialog(w('refresh_title'),
      w('refresh_body'),
      refreshPage, w('refresh_anyway'), { tone: 'warn' });
  };
  const burger = root.querySelector('#burger');
  if (burger) burger.onclick = () => root.querySelector('#side').classList.toggle('open');

  root.querySelector('#signout').onclick = signOut;
  const askMore = root.querySelector('#ask-more');
  if (askMore) askMore.onclick = () => modal(w('ask_more_access'), `<p>${esc(w('ask_more_lede'))}</p>
      <div class="nav">${askable().map((s) => `<a href="#/${esc(s.id)}" data-close>${icon('lock', 17)} <span class="lbl">${esc(s.label)}</span></a>`).join('')}</div>`, {
    onOpen: (body, close) => body.querySelectorAll('[data-close]').forEach((a) => { a.onclick = close; }) });
  root.querySelector('#chpass').onclick = () => { pop.hidden = true; passwordDialog(); };
  const startHere = root.querySelector('#start-here');     // Start here, brought back after Hide (core/startcard.py)
  if (startHere) startHere.onclick = () => { pop.hidden = true; import('./startcard.js').then((m) => m.reopenStartCard(root.querySelector('#startcard'), route && route.id)).catch((e) => toast(e.message, 'bad')); };
  root.querySelector('#report-issue').onclick = () => { pop.hidden = true; reportIssue({ surface: route ? route.id : '', context: location.hash }); };
  root.querySelector('#my-reports').onclick = () => { pop.hidden = true; myReports(); };   // 2026-10-03 owner: "where can I see all my feedback"
  root.querySelectorAll('[data-reply-seen]').forEach((b) => {
    b.onclick = async () => {
      state.issueReplies = state.issueReplies.filter((r) => r.id !== b.dataset.replySeen);
      b.closest('.note').remove();
      try { await api(`/api/core/issues/${encodeURIComponent(b.dataset.replySeen)}/seen`, { method: 'POST', body: {} }); } catch { /* shown again next time */ }
    };
  });
  wireHowto(root);
  wireGuide(root, state.productName);
  if (route) config.wireTopbar(root, route);
}

/** The page a person sees when a rule shut a screen: what it is, and one button to ask for it. */
function lockedView(host, s) {
  const asked = state.pendingRequests.includes(s.id);
  host.innerHTML = `<div class="card"><div class="empty">
    ${icon('lock', 40)}
    <h3>${w('locked_title', { screen: esc(s.label) })}</h3>
    <p>${w(asked ? 'locked_asked' : 'locked_ask')}</p>
    ${asked ? '' : `<button class="primary" type="button" id="ask">${icon('send')} ${w('request_access')}</button>`}
  </div></div>`;
  const ask = host.querySelector('#ask');
  if (ask) ask.onclick = () => modal(w('request_title', { screen: s.label }), `
      <div id="rq-msg"></div>
      <div class="field"><label for="rq-why">${w('why_need')}</label>
        <textarea id="rq-why" maxlength="500" placeholder="${esc(w('why_placeholder'))}"></textarea></div>`, {
    footer: `<button type="button" data-cancel>${w('cancel')}</button><button type="button" class="primary" id="rq-go">${w('send_request')}</button>`,
    onOpen: (body, close) => {
      const card = body.closest('.modal');
      card.querySelector('[data-cancel]').onclick = close;
      card.querySelector('#rq-go').onclick = (e) => busy(e.currentTarget, async () => {
        try {
          await api('/api/core/access/requests', { method: 'POST', body: { screen: s.id, reason: body.querySelector('#rq-why').value } });
          state.pendingRequests.push(s.id);
          close();
          toast(w('request_sent'), 'ok');
          lockedView(host, s);
        } catch (err) { say(body.querySelector('#rq-msg'), 'bad', esc(err.message)); }
      });
    } });
}

/** User menu → Change password. Also what the forced change posts to, from its own gate card. */
export function passwordDialog() {
  modal(w('change_title'), `
    <div id="pw-msg"></div>
    ${authField('pw-now', w('current_password'), { name: 'current', type: 'password', auto: 'current-password',
      reveal: true, value: '' })}
    ${authField('pw-new', w('new_password'), { name: 'password', type: 'password', placeholder: w('at_least', { n: state.passwordMin }),
      auto: 'new-password', reveal: true, value: '' })}
    ${authField('pw-confirm', w('confirm_new_password'), { name: 'confirm', type: 'password', placeholder: w('repeat_password'),
      auto: 'new-password', reveal: true, value: '' })}
    ${pwHints()}`,
    { eyebrow: w('your_account'),
      footer: `<button type="button" data-cancel>${w('cancel')}</button>
               <button type="button" class="primary" id="pw-go">${icon('check', 15)} ${w('save_password')}</button>`,
      onOpen: (body, close) => {
        const card = body.closest('.modal');
        wireSecrets(body);
        wireFieldErrors(body);
        wirePwHints(body, 'pw-new', 'pw-confirm');
        card.querySelector('[data-cancel]').onclick = () => close();
        const go = card.querySelector('#pw-go');
        const save = () => busy(go, async () => {
          clearFieldErrors(body);
          try {
            await api('/api/auth/password', { method: 'POST', body: { current: body.querySelector('#pw-now').value,
              password: body.querySelector('#pw-new').value, confirm: body.querySelector('#pw-confirm').value } });
            close();
            toast(w('password_changed'), 'ok');
          } catch (err) { showFieldError(body, err, body.querySelector('#pw-msg')); }
        });
        go.onclick = save;
        body.addEventListener('keydown', (e) => {
          if (e.key === 'Enter' && e.target instanceof HTMLInputElement) { e.preventDefault(); save(); }
        });
        body.querySelector('#pw-now').focus();
      } });
}

function take(d) {
  state.user = d.user;
  remembersFor(d.user && d.user.id);    // every load binds this browser's memory to whoever is signed in now
  state.needsFirstAccount = d.needs_first_account;
  state.reservedOwner = d.reserved_owner || '';
  state.canEmail = !!d.can_email;
  state.canSignup = !!d.can_signup;
  state.demo = !!d.demo;                           // a demo copy (core/demo.py): the card leads with Try the demo
  state.demoResetAt = Number(d.demo_reset_at) || 0;
  state.verifyEmail = !!d.verify_email;
  state.signupDomains = d.signup_domains || '';
  state.noMailPolicy = d.no_mail_policy || 'verify_later';
  state.passwordMin = Number(d.password_min_length) || 8;
  state.userLen = d.username_length || [];               // chip auth.username_problem min / max: shown in the box
  state.code = { digits: Number(d.code && d.code.digits) || 6, resend: Number(d.code && d.code.resend_after_seconds) || 60 };
  state.productName = d.product_name || state.productName;
  setProduct(state.productName);
  state.guides = d.guides || [];
  state.startCard = d.start_card || null;          // Start here (core/startcard.py): where it is drawn, the name menu's word
  state.portalUrl = d.portal_url || '';
  state.catalog = d.catalog || [];
  state.elsewhere = d.elsewhere || null;           // screens this address sends to another (a portal's door) - core/static/shell.js render()
  state.access = d.access || {};
  state.pendingRequests = d.pending_requests || [];
  state.storageRequest = d.storage_request || null;
  state.bellUnread = d.bell_unread || 0;
  state.issuesOpen = d.issues_open || 0;
  state.issueReplies = d.issue_replies || [];
  state.banners = d.banners || [];
  state.health = d.health || null;
  state.find = d.find || state.find;
}

/** An owner reset this person's password with "require change": nothing but the gate card until they do. */
const mustChange = () => !!(state.user && state.user.must_change_password);

/** Re-read who is signed in and what they may open. Call after anything that can change either. */
export async function refresh() {
  try {
    const [d, h] = await Promise.all([api('/api/bootstrap'), api('/api/core/howto').catch(() => ({ pages: {} }))]);
    take(d);
    state.howto = h.pages || {};
    if (!mustChange()) await config.onBoot(d);     // the host's own calls would only be refused meanwhile
  } catch { /* the shell is still usable without it */ }
}

/** The menu scrolls on its own (a short window, a long catalog). A redraw keeps its place and brings the
 *  open screen into view; the folded menu's tooltips float above the page, since a scroll box clips
 *  anything drawn outside it. */
function wireMenuScroll(root, scrolled) {
  const nav = root.querySelector('.nav');
  if (!nav) return;
  nav.scrollTop = scrolled;
  nav.querySelector('a.on')?.scrollIntoView({ block: 'nearest' });
  let tip = document.querySelector('.floattip');
  if (!tip) {
    tip = Object.assign(document.createElement('div'), { className: 'floattip', hidden: true });
    document.body.appendChild(tip);
  }
  const show = (e) => {
    const a = e.target.closest('a[data-tip]');
    if (!a || !root.querySelector('.shell.collapsed')) { tip.hidden = true; return; }
    const r = a.getBoundingClientRect();
    tip.textContent = a.dataset.tip;
    tip.style.left = `${r.right + 12}px`;
    tip.style.top = `${r.top + r.height / 2}px`;
    tip.hidden = false;
  };
  const hide = () => { tip.hidden = true; };
  nav.addEventListener('mouseover', show);
  nav.addEventListener('focusin', show);
  nav.addEventListener('mouseleave', hide);
  nav.addEventListener('focusout', hide);
  nav.addEventListener('scroll', hide);
}

export function render() {
  if (leaving) return;
  const root = document.getElementById('root');
  shownHash = location.hash;
  hooks.isDirty = null;
  document.querySelector('.floattip')?.setAttribute('hidden', '');
  root.className = '';
  clearInterval(resendTimer);                      // a code countdown never outlives its card
  // 2026-10-01 owner "send door links to the door's address": a screen this address leaves to another (bootstrap
  // `elsewhere`, chip edition.settings site_sends) opens THERE - the same screen and query, before anything is drawn
  const away = state.elsewhere;
  const here = (location.hash || '').replace(/^#\//, '').split('?')[0];
  if (away && away.url && (away.screens || []).includes(here)) { location.replace(`${away.url}/${location.hash}`); return; }
  // A link from an email beats everything: it may arrive while signed in as somebody else.
  const link = emailLink();
  if (link) { showEmailLink(root, link); return; }
  if (!state.user || mustChange()) pageDirty = false;   // typing on the way in is never "unsaved work"
  if (!state.user) {
    root.innerHTML = signinView();
    wireSignin(root);
    trackView(authPath());
    return;
  }
  if (mustChange()) {
    root.innerHTML = mustChangeView();
    wireMustChange(root);
    trackView('#/must-change');
    return;
  }
  const route = currentScreen();
  if (BUILD.stale) { location.reload(); return; }      // the server was updated: the next screen comes fresh (ui.js BUILD)
  const scrolled = root.querySelector('.nav')?.scrollTop || 0;
  root.innerHTML = shellView(route);
  wireShell(root, route);
  wireMenuScroll(root, scrolled);
  const page = root.querySelector('#page');
  pageDirty = false;
  // 2026-09-18: typing a YouTube link or a search is not "unsaved work". Only fields that hold something to
  // save count; a search box, or anything inside [data-nodirty] (a page with nothing to save), never does.
  // 2026-09-22 (owner: "why am I getting this message every time"): a TICK, a dropdown pick or a chosen file
  // is not typed work either - those save the moment they change, and they were raising a leave warning on
  // pages with nothing at all to lose. Only fields that HOLD TEXT count.
  // 2026-10-06 (owner: "I did not edit anything"): the browser's own autofill of a saved password or key fires `input`
  // too - only a field the person has touched (a key, a paste, a drop) counts as edited.
  const touched = new WeakSet();
  ['keydown', 'paste', 'drop', 'cut'].forEach((t) => page.addEventListener(t, (e) => { if (e.target instanceof Element) touched.add(e.target); }, true));
  page.addEventListener('input', (e) => {
    const el = e.target instanceof Element ? e.target : null;
    if (!el || el.closest('[data-nodirty]') || !touched.has(el)) return;
    if (el.matches('input[type="search"], input[type="checkbox"], input[type="radio"], input[type="file"], input[type="range"], select')) return;
    pageDirty = true;
  });
  if (!route) {
    page.innerHTML = `<div class="card"><div class="empty">${icon('lock', 40)}<h3>${w('nothing_title')}</h3>
      <p>${w('nothing_body')}</p></div></div>`;
    return;
  }
  trackView(`#/${route.id}`, route.label);
  if (!may(route.id)) { lockedView(page, route); return; }
  page.innerHTML = `<div class="empty">${spinner(22)}<p>${w('loading')}</p></div>`;
  // config.screens (2026-10-16): a portal whose screen code is members-only (core/private_static.py) loads it here, on first use
  const view = config.views[route.id] || (CORE_VIEWS[route.id] && ((h) => CORE_VIEWS[route.id]().then((v) => v(h))))
    || (config.screens && ((h) => config.screens().then((vs) => {
      if (!vs || !vs[route.id]) throw new Error(w('no_view', { id: route.id }));
      return vs[route.id](h);
    })));
  if (!view) { say(page, 'bad', w('no_view', { id: esc(route.id) })); return; }
  Promise.resolve(view(page)).then(() => {
    jumpTo(page, route);
    // Start here: the first steps for a newcomer, on the screens chip start.steps names (core/startcard.py)
    if (state.startCard && (state.startCard.screens || []).includes(route.id)) {
      import('./startcard.js').then((m) => m.startCard(root.querySelector('#startcard'), route.id)).catch(() => {});
    }
  }).catch((e) => {
    if (BUILD.stale) { location.reload(); return; }    // old page code met the new server: reload, never show its crash
    // The owner reset this password while the page was open: the server now refuses until it is changed.
    if (e && e.data && e.data.must_change_password && state.user) {
      state.user = { ...state.user, must_change_password: true };
      render();
      return;
    }
    say(page, 'bad', esc(e.message));
  });
}

/** A top-search hit names the part of the page that answers it (#/storage?at=%23st-limits, core/find.py): scroll
 *  there and mark it a moment, then drop it from the address bar so a later redraw stays where the person is. */
function jumpTo(page, route) {
  const at = new URLSearchParams(location.hash.split('?')[1] || '').get('at');
  if (!at) return;
  history.replaceState(null, '', `${location.pathname}${location.search}#/${route.id}`);
  shownHash = location.hash;
  let el = null;
  try { el = page.querySelector(at); } catch { /* not a selector this page reads: it stays at the top */ }
  if (!el) return;
  el.scrollIntoView({ block: 'start', behavior: 'smooth' });
  el.classList.add('find-hit');
  el.addEventListener('animationend', () => el.classList.remove('find-hit'), { once: true });
}

/** Unsaved work is never lost to a menu click, the Back button or closing the tab (2026-09-17). A page
 *  that knows better than "something was typed" sets hooks.isDirty; render() clears it for the next page. */
const dirtyNow = () => (hooks.isDirty ? !!hooks.isDirty() : pageDirty);
let shownHash = location.hash;
function installLeaveGuard() {
  const leave = (go) => confirmDialog(w('leave_title'),
    w('leave_body'), () => {
      hooks.isDirty = null;
      pageDirty = false;
      go();
    }, w('leave_yes'), { tone: 'warn', eyebrow: w('leave_eyebrow') });
  document.addEventListener('click', (e) => {
    const a = e.target instanceof Element ? e.target.closest('a[href^="#/"]') : null;
    const page = document.getElementById('page');
    if (!a || !dirtyNow() || (page && page.contains(a))) return;
    e.preventDefault();
    e.stopPropagation();
    const href = a.getAttribute('href');
    leave(() => { if (location.hash === href) render(); else location.hash = href; });
  }, true);
  window.addEventListener('hashchange', () => {
    const to = location.hash;
    if (to === shownHash || !dirtyNow()) { render(); return; }
    history.replaceState(null, '', shownHash || '#/');          // Back/Forward: stay until they choose
    leave(() => { location.hash = to; });
  });
  // Closing or reloading the TAB is the one warning the portal cannot draw itself: the browser owns that box and
  // allows no wording, no buttons and no App Message. So it is asked for ONLY where a page says, in its own words,
  // that it holds unsaved edits (hooks.isDirty - the builders and the Studio). "Something was typed somewhere"
  // never raises it again (owner 2026-09-22: every message must be an App Message).
  window.addEventListener('beforeunload', (e) => {
    if (state.user && hooks.isDirty && hooks.isDirty()) { e.preventDefault(); e.returnValue = ''; }
  });
}

/** 2026-10-02 sweep: a tooltip near the screen's edge ran off it (CSS cannot see the edge). On hover, the bubble's own
 *  width (what portal.css gave it) decides: past the right edge it lines up with the control's right side, past the
 *  left edge with its left side. Sizes stay in CSS; this only reads them. */
function installTipEdges() {
  document.addEventListener('mouseover', (e) => {
    const t = e.target.closest && e.target.closest('[data-tip]');
    if (!t) return;
    const r = t.getBoundingClientRect();
    const half = (parseFloat(getComputedStyle(t, '::after').width) || 0) / 2;
    const mid = r.left + r.width / 2;
    t.classList.toggle('tip-end', mid + half > document.documentElement.clientWidth);
    t.classList.toggle('tip-start', mid - half < 0);
  }, true);
}

export async function startPortal(options) {
  config = { ...config, ...options };
  installTipEdges();
  hooks.unauthorized = () => { if (state.user) { state.user = null; remembersFor(''); render(); } };
  hooks.stale = () => toast(w('portal_updated'), 'info', 12);
  hooks.saved = () => { pageDirty = false; };
  installLeaveGuard();
  installOmniKeys();
  applyTheme();
  try {
    // The shell's words (chip ui.shell) come with the bootstrap: the sign-in card needs them before anyone
    // signs in. A words failure is not a dead portal - a missing word shows as [shell.key], never silently.
    const [d, h] = await Promise.all([api('/api/bootstrap'), api('/api/core/howto').catch(() => ({ pages: {} })),
      loadWords('shell', 'work', 'guide', 'demo').catch(() => {})]);
    take(d);
    if (state.demo && !state.user && !state.needsFirstAccount) setMode('demo');
    state.howto = h.pages || {};
    // Somebody arriving with no account should land on the half of the screen that makes them one.
    if (state.user) { try { localStorage.setItem('portal.signed_in_before', '1'); } catch { /* nicety */ } }   // already signed in counts too
    // 2026-09-28 owner: "always opens with Create account - remember, and open the Sign in tab next time". A browser
    // that has signed in here before gets Sign in; a first visit still lands on Sign up (per-browser nicety, not state).
    if (!state.user && state.canSignup && !state.demo && !state.needsFirstAccount && !signedInBefore()) setMode('signup');
    flow.focus = false;
    if (!mustChange()) await config.onBoot(d);
    if (state.user && !mustChange() && !(location.hash || '').replace(/^#\/?/, '')) toLanding();   // 2026-10-06: opened signed in, no screen named
  } catch (e) {
    // The one card drawn when the server cannot be reached: then its words cannot be fetched either, so
    // they are the chip's where they did arrive and this fallback where they did not.
    const say2 = (k, fallback) => { const s = w(k); return s.startsWith('[shell.') ? fallback : s; };
    document.getElementById('root').innerHTML = `<div class="gate"><div class="gateform"><div class="card">
      <h1>${say2('down_title', 'Portal not answering')}</h1>
      <p class="muted">${esc(e.message)}</p>
      <p class="small muted">${say2('down_body', 'Start the server, then reload.')}</p></div></div></div>`;
    return;
  }
  render();
}
