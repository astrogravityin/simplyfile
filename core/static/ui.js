// The framework's small UI kit: fetch, escape, dialogs, toasts, busy buttons, secret and file fields,
// the theme switch. No framework and no build step — every portal on core/ shares these, so no two
// screens invent their own popup.
import { icon, spinner } from './icons.js';

// Where the portal lives, taken from this module's own URL (…/core-static/ui.js) — so it works at the
// site root, at /tv, or anywhere else, with nothing to configure.
export const BASE = new URL('..', import.meta.url).href.replace(/\/$/, '');

/** Filled in by the shell: what to do when the server says the session is gone. */
export const hooks = {
  unauthorized: () => {},
  /** The server was updated under this open page (BUILD). */
  stale: () => {},
  /** A page with its own idea of "unsaved" sets this (the builders do); the shell asks it before leaving. */
  isDirty: null,
  /** Called after a successful save; the shell forgets "something was typed". */
  saved: () => {},
};

// --- words: every word on a screen is chip ui.<screen> (core/words.py) --------------------------------
const WORDS = {};
// --- what a browser remembers, remembered per PERSON --------------------------------------------------------
// 2026-09-21 owner: a colleague signing in on the same browser saw the NAMES of another person's films in "Switch
// to". A preference kept under a bare key belongs to the BROWSER, not to the person: the next person to sign in
// reads it. Every such key now carries the signed-in person's id, and signing out leaves nothing to read.
let _whose = '';

export function remembersFor(userId) {
  _whose = String(userId || '');
}

export function myKey(key) {
  return `${key}.${_whose || 'anon'}`;
}

export function keep(key, value) {
  try { localStorage.setItem(myKey(key), value); } catch { /* a preference only */ }
}

export function kept(key, fallback = '') {
  try { return localStorage.getItem(myKey(key)) ?? fallback; } catch { return fallback; }
}

const lang = () => { try { return localStorage.getItem('portal.lang') || ''; } catch { return ''; } };

/** Fetch the words of these screens once (chips ui.<screen>, in the person's language where translated). */
export async function loadWords(...screens) {
  const need = screens.filter((s) => !WORDS[s]);
  if (!need.length) return;
  const d = await api(`/api/core/words?screens=${encodeURIComponent(need.join(','))}&lang=${encodeURIComponent(lang())}`);
  Object.assign(WORDS, d.words || {});
  Object.assign(PAGE, d.settings || {});
  (d.statements || []).forEach((x) => STATEMENTS.add(x));   // decided by chip work.statements on the server
  if ((d.settings || {}).shell) ROADS.splice(0, ROADS.length, ...(d.settings.shell.roads || []));
}

/** 2026-09-26: a page's own numbers, lists and maps - chip page.<screen>, loaded with its words. */
const PAGE = {};
const STATEMENTS = new Set();   // words that are statements, not work (chip work.statements) - looked up, never tested here
export function ps(screen) { return PAGE[screen] || {}; }

/** One word of a screen, {placeholders} filled. A missing key shows as [screen.key] - visible, never silent. */
export function t(screen, key, values = {}) {
  const text = (WORDS[screen] || {})[key];
  if (text === undefined) return `[${screen}.${key}]`;
  // `{n:person|people}` = the word for one or for any other count (2026-10-02 "1 people"); same rule as ops.template
  return String(text).replace(/\{(\w+):([^{}|]*)\|([^{}]*)\}/g, (_, k, one, many) => (Number(values[k]) === 1 ? one : many))
    .replace(/\{(\w+)\}/g, (_, k) => String(values[k] ?? ''));
}

// The kit's own words (dialog buttons, the key box, the file box) are chip ui.shell, which the shell loads
// before anything is drawn. `t` is a local name in confirmDialog, so they go by `sw`.
const sw = (k, v) => t('shell', k, v);

export function esc(v) {
  return String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

/** 2026-09-28 owner: after a restart an open tab ran the OLD page scripts against the NEW server and every screen
 *  broke ("Cannot read properties of undefined"). The server names its build on every answer; a new one marks this
 *  page stale, says so once, and the shell reloads on the next screen change (never mid-typing). */
export const BUILD = { seen: '', stale: false };
function noteBuild(b) {
  if (!b) return;
  if (!BUILD.seen) { BUILD.seen = b; return; }
  if (b !== BUILD.seen && !BUILD.stale) { BUILD.stale = true; hooks.stale(); }
}

export async function api(path, opts = {}) {
  const { saved, ...rest } = opts;
  const init = { credentials: 'same-origin', ...rest };
  if (init.body !== undefined && !(init.body instanceof FormData)) {
    init.headers = { 'Content-Type': 'application/json', ...(init.headers || {}) };
    init.body = typeof init.body === 'string' ? init.body : JSON.stringify(init.body);
  }
  const r = await fetch(BASE + path, init);
  noteBuild(r.headers.get('X-Portal-Build'));
  const text = await r.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = { detail: text }; }
  if (!r.ok) {
    if (r.status === 401) hooks.unauthorized();
    // `detail` is a sentence, or an object carrying one plus what it is about ({message, problems…}).
    // Never "[object Object]": the sentence is the message, and the whole answer rides along as `data`.
    const d = data && data.detail;
    const message = (d && typeof d === 'object' ? d.message : d) || (data && data.message) || `${r.status} ${r.statusText}`;
    throw Object.assign(new Error(String(message)), { status: r.status, data: d && typeof d === 'object' ? d : data });
  }
  // 2026-09-17: "Save script" and "Save key" succeeded and leaving still said "Leave without saving?".
  // PUT and DELETE are saves; so is a POST that CREATES something (a new comic, a new book, a group, an invite).
  // Only a POST that DOES something without keeping it - Test, Estimate, Preview, Parse, a job, a sample, a sign-out -
  // leaves the page dirty, since the typed field it was fired from is still unsaved. A caller may always say so
  // itself with { saved: true } (2026-09-22: adding a key still warned on the way out).
  const action = /\/(test|check|estimate|preview|parse|prompt|job|jobs|stop|sample|find|eval|signout|send|dismiss|clear|import-prompt)(\/|$|\?)/i.test(path);
  if (saved || /^(PUT|DELETE)$/i.test(init.method || '') || (/^POST$/i.test(init.method || '') && !action)) hooks.saved();
  return data;
}

// --- small UI helpers ---------------------------------------------------------------------------

const NOTE_ICON = { ok: 'check', bad: 'alert', warn: 'alert', info: 'info' };

export function say(host, kind, text) {
  if (!host) return;
  host.innerHTML = text
    ? `<div class="note ${kind}">${icon(NOTE_ICON[kind] || 'info')}<div>${text}</div></div>`
    : '';
}

/** Every server time on every screen (2026-09-28 owner: one standard, no duplicate code): the viewer's own clock, its
 *  zone named. ONE formatter - a page never keeps its own `const when`. Plain text, safe to put in HTML. */
/** A time of day only (no date), with its zone - "14:05 IST". `iso` blank = now. */
export function clockAt(iso = '', seconds = false) {
  const d = iso ? new Date(iso) : new Date();
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', ...(seconds ? { second: '2-digit' } : {}), timeZoneName: 'short' });
}

export function when(iso, seconds = false) {
  const d = new Date(iso || '');
  if (!iso || Number.isNaN(d.getTime())) return '';
  return d.toLocaleString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
    ...(seconds ? { second: '2-digit' } : {}), timeZoneName: 'short' });
}

/** The banner every page opens with: what this screen is, what it is for, and the one or two
 *  things you can do from here. One shape, so no two modules invent their own heading. */
export function pageHead(title, lede, actionsHtml = '', extraHtml = '') {
  return `<header class="pagehead">
    <div class="txt"><h1>${esc(title)}</h1>${lede ? `<p>${lede}</p>` : ''}</div>
    ${actionsHtml ? `<div class="acts">${actionsHtml}</div>` : ''}
    ${extraHtml}</header>`;
}

/** A modal that always obeys the same rules: Escape closes it, the Close button is pinned in view,
 *  and the panel scrolls inside rather than the page behind it. Backdrop clicks do NOT close a
 *  modal with a form in it — dragging a selection out of a field must never throw the work away. */
export function modal(title, bodyHtml, { onOpen, onClose, wide = false, footer = '', cls = '', eyebrow = '', stay = false } = {}) {
  const back = document.createElement('div');
  back.className = 'backdrop';
  back.innerHTML = `<div class="modal ${esc(cls)}" role="dialog" aria-modal="true" aria-label="${esc(title)}" ${wide ? 'style="width:min(1100px,100%)"' : ''}>
      <header><div class="ttl">${eyebrow ? `<span class="eyebrow">${esc(eyebrow)}</span>` : ''}<h2>${esc(title)}</h2></div>
        <button type="button" data-close class="ghost" aria-label="${esc(sw('close'))}">${icon('close', 18)}</button></header>
      <div class="body">${bodyHtml}</div>
      ${footer ? `<footer>${footer}</footer>` : ''}</div>`;
  // A dialog in the middle of something that cannot be interrupted (an upload writing to the
  // server) sets `back.dataset.busy`: the X, Escape and the backdrop all stop working, and the
  // dialog itself offers the way out. Nothing else can make a popup unclosable.
  const close = (force) => {
    if (back.dataset.busy && force !== true) return;
    back.remove();
    document.removeEventListener('keydown', onKey);
    if (onClose) onClose();
  };
  // 2026-09-30: dialogs stack (an upload box or an "are you sure" over the template gallery). Esc closes the TOP one only:
  // each dialog hears the key in the order it opened, so one that is not the last backdrop on the page leaves it alone
  const onKey = (e) => { if (e.key === 'Escape' && back === [...document.querySelectorAll('.backdrop')].pop()) { e.stopImmediatePropagation(); close(); } };
  // `stay`: a click outside never closes it (2026-09-24 owner: a stray click threw the work window away) - X / Escape do
  back.addEventListener('click', (e) => { if (e.target === back && !stay && !back.querySelector('input,textarea,select')) close(); });
  back.querySelector('[data-close]').onclick = () => close();
  document.addEventListener('keydown', onKey);
  document.body.appendChild(back);
  if (onOpen) onOpen(back.querySelector('.body'), close);
  close.hold = (busy) => {                        // true while something must not be cut in half
    if (busy) back.dataset.busy = '1';
    else delete back.dataset.busy;
    const x = back.querySelector('[data-close]');
    if (x) { x.disabled = !!busy; x.style.opacity = busy ? '.35' : ''; x.title = busy ? sw('finishing') : ''; }
  };
  return close;
}

/** "Are you sure?" — one look for the whole portal: a tinted top with a small label saying what kind
 *  of confirmation this is, the question, what happens, and two pill buttons. The tone follows the
 *  action, named by every caller: `tone: 'danger'` (delete, leave, remove, reject...) is red with a bin,
 *  'warn' amber, 'brand' a plain yes. 2026-10-02: the tone was guessed from English words in the button
 *  label - "Reject", "Take out" or any Telugu/Hindi label got a green tick; no guessing, red by default.
 *  Cancel has the focus, so Enter on a reflex never deletes anything. */
export function confirmDialog(title, message, onYes, yesLabel = sw('delete'), { tone = 'danger', eyebrow = '' } = {}) {
  const t = ['danger', 'warn', 'brand'].includes(tone) ? tone : 'brand';   // an unknown tone had no colour: a white Yes on white
  const label = eyebrow || { danger: sw('confirm_delete'), warn: sw('please_confirm'), brand: sw('confirm') }[t];
  const glyph = { danger: 'trash', warn: 'refresh', brand: 'check' }[t];
  modal(title, `<p class="confirm-msg">${esc(message)}</p>`, {
    cls: `confirm tone-${t}`, eyebrow: label,
    footer: `<button type="button" class="pill" data-no>${sw('cancel')}</button>
      <button type="button" class="pill solid" data-yes>${icon(glyph, 15)} ${esc(yesLabel)}</button>`,
    onOpen: (body, close) => {
      const card = body.closest('.modal');
      const no = card.querySelector('[data-no]');
      no.onclick = () => close();
      card.querySelector('[data-yes]').onclick = () => { close(); onYes(); };
      no.focus();
    } });
}

/** A toast: the answer to "did that work?" without a panel jumping into the layout.
 *  Used for the outcome of an action. Inline `say()` stays for things that belong beside a field. */
export function toast(text, kind = 'ok', seconds = 4.5) {
  let host = document.querySelector('.toasts');
  if (!host) {
    host = document.createElement('div');
    host.className = 'toasts';
    document.body.appendChild(host);
  }
  const el = document.createElement('div');
  el.className = `toast ${kind}`;
  el.setAttribute('role', kind === 'bad' ? 'alert' : 'status');
  el.innerHTML = `${icon(NOTE_ICON[kind] || 'info')}<div>${esc(text)}</div>`;
  host.appendChild(el);
  const kill = () => { el.remove(); if (!host.children.length) host.remove(); };
  el.onclick = kill;
  setTimeout(kill, seconds * 1000);
}

/** Run an async action with the button showing it: spinner in, label kept, disabled until done.
 *  Every await in this app goes through here, so no button can be pressed twice by accident. */
export async function busy(button, run) {
  if (!button || button.disabled) return undefined;
  // 2026-09-27: a <select>/<input> keeps its innards - a spinner in a select wipes its options and its value
  const swap = button.tagName !== 'SELECT' && button.tagName !== 'INPUT';
  const before = button.innerHTML;
  // 2026-09-27 owner "AIOne text call": a road button holds a bold name and a note span - textContent glued the two;
  // each piece of text is its own part of the name
  const words = [];
  if (swap) { const tw = document.createTreeWalker(button, NodeFilter.SHOW_TEXT); while (tw.nextNode()) { const x = tw.currentNode.nodeValue.trim(); if (x) words.push(x); } }
  const label = words.join(' · ') || button.title || '';
  // 2026-10-03 owner: the work window read "I checked it" - a button that SAYS something (a tick, a yes) names its
  // work in data-work; the window titles with that, the button keeps its own words.
  // A statement with no data-work (chip work.statements, served with the words) gets the plain title, never itself.
  const work = button.dataset?.work || (STATEMENTS.has(label) ? sw('ww_busy_title') : label);
  button.disabled = true;
  if (swap) button.innerHTML = spinner() + label;
  // 2026-09-24 owner: anything that takes time opens the work window - an action still running after 1.5 s gets it,
  // timed from this person's last run of the same action.
  const key = `ww.busy.${work.slice(0, 60)}`;
  const learned = Number(kept(key, '')) || null;
  const t0 = Date.now();
  let win = null;
  const show = setTimeout(() => {
    win = workWindow(work, { activity: work });
    win.set({ started_ms: t0, total_s: learned, basis: learned ? sw('dl_basis', { t: clk(learned) }) : sw('dl_first') });
  }, wk('busy_show_ms'));
  try {
    const out = await run();
    if (win) { win.end('finished'); setTimeout(() => win.isOpen && win.close(), wk('close_busy_ms')); }
    return out;
  } catch (err) {
    if (win) win.end('failed', err.message);
    throw err;
  } finally {
    clearTimeout(show);
    if (Date.now() - t0 > wk('busy_show_ms')) keep(key, String(Math.round((Date.now() - t0) / 1000)));
    button.disabled = false;
    if (swap) button.innerHTML = before;
  }
}

/** A box for a key or password.
 *
 *  Carries its own Paste button: Ctrl+V into the box fails on more setups than you would think
 *  (remote desktops, locked-down browsers), and a key you cannot get into the box is a dead portal.
 *
 *  Never prefilled with the mask: a masked value in the box means Ctrl+V lands AFTER it, and you end
 *  up saving `••••••••abcd` plus your key. Empty box, the stored one named in the placeholder, and a
 *  blank save keeps what is there.
 *
 *  Shows the character count as you type, because "is this 16 characters?" is the actual question
 *  people have, and Show reveals it so you can see what really arrived. */
export function secretField(id, label, { set = false, tail = '', hint = '' } = {}) {
  return `<div class="field"><label for="${id}">${esc(label)}</label>
    <span class="withbtn wide">
      <input id="${id}" type="password" autocomplete="off" spellcheck="false" autocapitalize="off"
        placeholder="${esc(set ? sw('secret_saved', { tail }) : sw('secret_empty'))}"/>
      <button type="button" data-paste="${id}">${sw('paste')}</button>
      <button type="button" data-reveal="${id}">${sw('show')}</button>
    </span>
    ${hint ? `<span class="small muted">${hint}</span>` : ''}
    <span class="small muted" data-count="${id}">${set ? sw('secret_keep') : ''}</span>
  </div>`;
}

/** A field whose value must be one of a known set. Free text is offered only where a new value can
 *  legitimately appear (a model released after this build), and never as the default path. */
export function choiceField(id, label, { choices = [], value = '', hint = '', otherOk = false } = {}) {
  const known = choices.includes(value);
  return `<div class="field"><label for="${id}">${esc(label)}</label>
    <select id="${id}">
      ${choices.map((c) => `<option ${c === value ? 'selected' : ''}>${esc(c)}</option>`).join('')}
      ${otherOk ? `<option value="__other" ${known ? '' : 'selected'}>${sw('something_else')}</option>` : ''}
    </select>
    ${otherOk ? `<input id="${id}-other" style="margin-top:8px;${known ? 'display:none' : ''}"
       value="${known ? '' : esc(value)}" placeholder="${esc(sw('exact_id'))}"/>` : ''}
    ${hint ? `<span class="small muted">${hint}</span>` : ''}
  </div>`;
}

/** Reads a choiceField: the picked option, or the typed one when "Something else…" is selected. */
export function choiceValue(host, id) {
  const sel = host.querySelector(`#${id}`);
  if (!sel) return '';
  const other = host.querySelector(`#${id}-other`);
  return sel.value === '__other' ? (other ? other.value.trim() : '') : sel.value;
}

/** Shows the free-text box only while "Something else…" is chosen. */
export function wireChoices(host) {
  host.querySelectorAll('select').forEach((sel) => {
    const other = host.querySelector(`#${sel.id}-other`);
    if (!other) return;
    sel.addEventListener('change', () => {
      other.style.display = sel.value === '__other' ? '' : 'none';
      if (sel.value === '__other') other.focus();
    });
  });
}

/** Wires every secretField inside `host`: the Show toggle and the live character count. */
export function wireSecrets(host, expected = {}) {
  host.querySelectorAll('[data-paste]').forEach((b) => {
    b.onclick = async () => {
      const el = host.querySelector(`#${b.dataset.paste}`);
      try {
        const text = await navigator.clipboard.readText();
        if (!text.trim()) { b.textContent = sw('clipboard_empty'); }
        else { el.value = text.trim(); el.dispatchEvent(new Event('input')); b.textContent = sw('pasted'); }
      } catch {
        // Denied, or the page is not on https/localhost, where the browser refuses to read the
        // clipboard at all. Show the box so Ctrl+V can be checked with your own eyes.
        el.type = 'text';
        el.focus();
        b.textContent = sw('press_ctrl_v');
      }
      setTimeout(() => { b.textContent = sw('paste'); }, 2500);
    };
  });
  host.querySelectorAll('[data-reveal]').forEach((b) => {
    b.onclick = () => {
      const el = host.querySelector(`#${b.dataset.reveal}`);
      el.type = el.type === 'password' ? 'text' : 'password';
      b.textContent = sw(el.type === 'password' ? 'show' : 'hide');
    };
  });
  host.querySelectorAll('[data-count]').forEach((out) => {
    const el = host.querySelector(`#${out.dataset.count}`);
    if (!el) return;
    const want = expected[out.dataset.count] || 0;
    const kept = out.textContent;
    el.oninput = () => {
      const n = el.value.replace(/\s/g, '').length;
      if (!n) { out.textContent = kept; out.className = 'small muted'; return; }
      out.textContent = want
        ? sw(n === want ? 'chars_right' : 'chars_expected', { n, want })
        : sw('chars', { n });
      out.className = want && n !== want ? 'small' : 'small muted';
      out.style.color = want && n !== want ? 'var(--warn)' : '';
    };
  });
}

/** A file picker you can drag onto. The native control is a grey browser button with a filename
 *  beside it; this is a target, and it says what it is holding. */
export function dropZone(id, { accept = '', title = sw('choose_file'), hint = '' } = {}) {
  return `<button type="button" class="drop" data-drop="${id}">
      ${icon('upload', 22)}
      <span class="txt"><b data-drop-title="${id}">${esc(title)}</b><span data-drop-hint="${id}">${esc(hint)}</span></span>
      <input type="file" id="${id}" aria-label="${esc(title)}" ${accept ? `accept="${accept}"` : ''}/>
    </button>`;
}

// 1024s, as a quota counts (2026-09-30: "1.1 GB of 1 GB" read as over); 0 bytes is 0 KB, a 60 KB portrait never "1 MB"
export const fileSize = (n) => (n >= 1024 ** 3 ? `${Number((n / 1024 ** 3).toFixed(1))} GB` : n >= 1024 ** 2 ? `${Math.round(n / 1024 ** 2)} MB` : `${n > 0 ? Math.max(1, Math.round(n / 1024)) : 0} KB`);

/** Wires every dropZone in `host`: drag-over styling, drop, and the chosen file's name and size. */
export function wireDrops(host, onPick = () => {}) {
  host.querySelectorAll('[data-drop]').forEach((zone) => {
    const id = zone.dataset.drop;
    const input = host.querySelector(`#${id}`);
    const titleEl = host.querySelector(`[data-drop-title="${id}"]`);
    const hintEl = host.querySelector(`[data-drop-hint="${id}"]`);
    const idle = { title: titleEl.textContent, hint: hintEl.textContent };
    let pasted = false;
    const show = () => {
      const f = input.files[0];
      zone.classList.toggle('filled', !!f);
      titleEl.textContent = f ? (pasted ? sw('file_pasted_title') : f.name) : idle.title;
      hintEl.textContent = f ? sw(pasted ? 'file_pasted' : 'file_chosen', { size: fileSize(f.size) }) : idle.hint;
      // 2026-09-26 owner: "I thought Ctrl+V should work here?" - it did, but "image.png" said nothing: show the picture itself
      let thumb = zone.querySelector('.drop-thumb');
      if (f && /^image\//.test(f.type)) {
        if (!thumb) { thumb = document.createElement('img'); thumb.className = 'drop-thumb'; thumb.alt = ''; zone.prepend(thumb); }
        if (thumb.src) URL.revokeObjectURL(thumb.src);
        thumb.src = URL.createObjectURL(f);
      } else if (thumb) thumb.remove();
      pasted = false;
      onPick(f || null, id);
    };
    input.onchange = show;
    zone.ondragover = (e) => { e.preventDefault(); zone.classList.add('over'); };
    zone.ondragleave = () => zone.classList.remove('over');
    zone.ondrop = (e) => {
      e.preventDefault();
      zone.classList.remove('over');
      if (e.dataTransfer.files.length) { input.files = e.dataTransfer.files; show(); }
    };
    zone.pasteInto = (files) => { input.files = files; pasted = true; show(); };
    zone.onpointerenter = () => { pasteZone = zone; };
    if (!hintEl.dataset.paste) { hintEl.dataset.paste = '1'; idle.hint = `${idle.hint} · ${sw('paste_hint')}`; hintEl.textContent = idle.hint; }
    pasteZone = zone;
  });
  if (!pasteWired) {
    pasteWired = true;
    document.addEventListener('paste', pasteFile);
  }
}

/** 2026-09-23 owner: "the right panel is static - it hides what is under it. Give it a handle so it can float and
 *  move, and give every panel a heading so we both speak the same language. True across the portal."
 *  panel: an element whose FIRST child becomes the named head (grip, title, Float/Dock, Collapse). Floating = fixed,
 *  dragged by its head, kept on screen; where it floats is remembered in this browser (per-viewer convenience). */
export function floatPanel(panel, key, title) {
  if (!panel || panel.querySelector(':scope > .fp-head')) return;
  const store = `portal.float.${key}`;
  const read = () => { try { return JSON.parse(localStorage.getItem(store) || '{}'); } catch { return {}; } };
  const save = (v) => { try { localStorage.setItem(store, JSON.stringify(v)); } catch { /* not remembered, still works */ } };
  panel.classList.add('fp');
  panel.insertAdjacentHTML('afterbegin', `<div class="fp-head" title="${esc(sw('fp_drag'))}">
      <span class="fp-grip" aria-hidden="true">⋮⋮</span><b class="fp-title">${esc(title)}</b>
      <button type="button" class="ghost small" data-fp-float>${esc(sw('fp_float'))}</button>
      <button type="button" class="ghost small" data-fp-fold aria-label="${esc(sw('fp_fold'))}">–</button></div>`);
  const head = panel.querySelector(':scope > .fp-head');
  const apply = () => {
    const st = read();
    panel.classList.toggle('fp-on', !!st.float);
    panel.classList.toggle('fp-folded', !!st.fold);
    head.querySelector('[data-fp-float]').textContent = st.float ? sw('fp_dock') : sw('fp_float');
    if (st.float) {
      const x = Math.max(0, Math.min(window.innerWidth - 120, st.x ?? window.innerWidth - 380));
      const y = Math.max(0, Math.min(window.innerHeight - 60, st.y ?? 80));
      Object.assign(panel.style, { left: `${x}px`, top: `${y}px` });
    } else Object.assign(panel.style, { left: '', top: '' });
  };
  head.querySelector('[data-fp-float]').onclick = () => { const st = read(); save({ ...st, float: !st.float }); apply(); };
  head.querySelector('[data-fp-fold]').onclick = () => { const st = read(); save({ ...st, fold: !st.fold }); apply(); };
  head.onpointerdown = (e) => {
    if (e.target.closest('button') || !read().float) return;
    const r = panel.getBoundingClientRect(); const dx = e.clientX - r.left; const dy = e.clientY - r.top;
    head.setPointerCapture(e.pointerId);
    head.onpointermove = (m) => Object.assign(panel.style, { left: `${Math.max(0, m.clientX - dx)}px`, top: `${Math.max(0, m.clientY - dy)}px` });
    head.onpointerup = () => {
      head.onpointermove = null; head.onpointerup = null;
      save({ ...read(), x: parseInt(panel.style.left, 10) || 0, y: parseInt(panel.style.top, 10) || 0 });
    };
  };
  apply();
}

/** 2026-09-23 owner: carry an Audiobook / a Comic (like a Studio film) from one portal to another. One dialog: pick
 *  the .zip, it streams up, the server checks it whole before writing anything, `onDone(answer)` opens what came in. */
export function importPack(title, tip, url, onDone) {
  modal(title, `<p class="small muted">${esc(tip)}</p>
      ${dropZone('pk-file', { accept: '.zip,application/zip', title: sw('pack_choose'), hint: sw('pack_hint') })}
      <div id="pk-msg"></div>`, {
    footer: `<button type="button" class="primary" id="pk-go">${icon('upload', 14)} ${esc(title)}</button>`,
    onOpen: (body, close) => {
      const box = body.closest('.modal');
      const go = box.querySelector('#pk-go');
      wireDrops(box);                                   // 2026-10-01: never greyed - an empty click says what to do
      go.onclick = () => busy(go, async () => {
        const f = box.querySelector('#pk-file').files[0];
        if (!f) { say(box.querySelector('#pk-msg'), 'warn', esc(sw('need_file'))); return; }
        const fd = new FormData();
        fd.append('file', f, f.name);
        say(box.querySelector('#pk-msg'), 'info', esc(sw('pack_importing', { name: f.name })));
        close.hold(true);                                // an upload writing to the server is not cut in half
        try {
          const got = await api(url, { method: 'POST', body: fd, saved: true });
          close.hold(false); close(true);
          toast(got.message, 'ok', 8);
          await onDone(got);
        } catch (err) { close.hold(false); say(box.querySelector('#pk-msg'), 'bad', esc(err.message)); }
      });
    },
  });
}

// 2026-09-23 owner: "user should be able to paste with Ctrl+V" - a picture copied anywhere (a screenshot, an image from
// a model's answer) lands in the drop zone: the one under the pointer, else the one in the topmost popup, else the
// last one wired. A paste into a text field stays a text paste.
let pasteZone = null;
let pasteWired = false;
function pasteFile(e) {
  const cd = e.clipboardData;
  // some copies (a picture copied from a web page) carry the image as an item, not in .files
  const file = (cd && cd.files && cd.files[0]) || (cd ? [...(cd.items || [])].filter((it) => it.kind === 'file').map((it) => it.getAsFile()).find(Boolean) : null);
  if (!file) return;
  const pops = document.querySelectorAll('.backdrop');
  const top = pops.length ? pops[pops.length - 1] : null;
  // 2026-09-26 owner: "Ctrl+V did not work" - a scene's text box BEHIND the popup still had the cursor, and a paste into
  // a text field was left alone. Only a writable text field inside the popup in front (or the page, with no popup) keeps it.
  const act = document.activeElement;
  const texty = act && /^(INPUT|TEXTAREA)$/.test(act.tagName) && act.type !== 'file' && !act.readOnly;
  if (texty && (!top || top.contains(act))) return;
  const zone = (pasteZone && pasteZone.isConnected && (!top || top.contains(pasteZone)) && pasteZone)
    || (top || document).querySelector('[data-drop]');
  if (!zone || !zone.pasteInto) return;
  e.preventDefault();
  const dt = new DataTransfer();
  dt.items.add(file);
  zone.pasteInto(dt.files);
}

// --- the work window: ONE popup for everything that takes time ------------------------------------------------------
// 2026-09-24 owner: "Offline HTML / TeDBook package take long and nothing engages the user. Across the board, any time
// a process takes time: a professional popup - the activity, elapsed + %, remaining + %, total estimate, and when money
// is involved the cost so far (which AI), the cost still to come and the total at completion." Every job window, every
// download from /api/, every paid batch paints through workWindow; no screen draws its own progress popup.
/** A length of time in the portal's own units (words ui.shell u_h / u_m / u_s) - one formatter for every page. */
export const clk = (sec) => {
  const s = Math.max(0, Math.round(Number(sec) || 0));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), r = s % 60;
  const [H, M, S] = [sw('u_h'), sw('u_m'), sw('u_s')];
  return h ? `${h}${H} ${String(m).padStart(2, '0')}${M} ${String(r).padStart(2, '0')}${S}` : m ? `${m}${M} ${String(r).padStart(2, '0')}${S}` : `${r}${S}`;
};
// 2026-10-02 audit: the work window and stats strip said "$" to everyone - every amount is in the person's currency
// (chip money.currencies, picked on Account & key; the portal sets it at bootstrap). The server books US dollars.
let currency = null;
export const setCurrency = (c) => { currency = c || null; };
export const shownMoney = (v, extra) => {
  const c = currency || { code: 'USD', symbol: '$', per_usd: 1, decimals: 2 }; const d = (c.decimals || 0) + extra;
  return `${c.symbol}${(Number(v) * c.per_usd).toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d })}`;
};
const usd = (v) => (v === null || v === undefined || Number.isNaN(Number(v)) ? '?' : shownMoney(v, Number(v) < 1 ? 1 : 0));
const RING = 2 * Math.PI * 50;
// every number of the work window is chip ui.work (served with the words): owner 2026-09-24 "only chips and ops"
const wk = (k) => Number(t('work', k));
let wwCount = 0;

/** Everything the window shows, from its state. Estimates: a given total wins until 15% is done, then the pace so far. */
function workHtml(s, canStop) {
  const gid = `ww-g-${s.id}`;
  const running = s.status === 'running';
  const el = ((s.ended || Date.now()) - s.started) / 1000;
  const pct = s.pct === null || s.pct === undefined ? null : Math.max(0, Math.min(100, Number(s.pct)));
  let total = s.total_s ? Number(s.total_s) : null;
  if (running && pct > 1 && pct < 100 && (!total || pct >= wk('pace_after_pct'))) total = (el * 100) / pct;
  if (!running) total = el;
  if (total !== null && total < el) total = el + 1;                   // late against the estimate: never a negative
  const left = total === null ? null : Math.max(0, total - el);
  const tPct = total ? Math.round((100 * el) / total) : null;
  const ring = s.status === 'finished' ? 100 : pct !== null ? pct : tPct !== null ? Math.min(99, tPct) : null;
  const tone = { finished: 'ok', failed: 'bad', stopped: 'warn' }[s.status] || 'run';
  const mid = s.status === 'finished' ? icon('check', 26) : s.status === 'failed' ? icon('alert', 26)
    : ring === null ? '<b>…</b>' : `<b>${Math.round(ring)}%</b><small>${esc(sw('ww_done_word'))}</small>`;
  const c = s.cost;
  let cost = '';
  if (c && !c.free) {
    const spent = Number(c.spent || 0);
    const ctotal = c.total !== null && c.total !== undefined ? Math.max(Number(c.total), spent) : pct > wk('cost_pace_after_pct') ? (spent * 100) / pct : null;
    cost = `<div class="ww-cost">
        <div><span>${esc(sw('ww_spent'))}</span><b>${usd(spent)}</b><em>${(c.models || []).filter(Boolean).map((m) => `<i>${icon('spark', 11)} ${esc(m)}</i>`).join('') || esc(sw('ww_ai_unknown'))}</em></div>
        <div><span>${esc(sw('ww_cost_left'))}</span><b>${running ? usd(ctotal === null ? null : ctotal - spent) : usd(0)}</b><em>${esc(sw('ww_estimate'))}</em></div>
        <div><span>${esc(sw('ww_cost_total'))}</span><b>${usd(running ? ctotal : spent)}</b><em>${esc(running ? sw('ww_at_complete') : sw('ww_final'))}</em></div></div>`;
  } else if (c && c.free) cost = `<p class="ww-free">${icon('check', 12)} ${esc(sw('ww_free'))}</p>`;
  return `
    <div class="ww-top tone-${tone}">
      <svg class="ww-ring${ring === null && running ? ' spin' : ''}" viewBox="0 0 120 120" aria-hidden="true">
        <defs><linearGradient id="${gid}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" style="stop-color:var(--brand)"/><stop offset="1" style="stop-color:var(--brand-2)"/></linearGradient></defs>
        <circle class="ww-ticks" cx="60" cy="60" r="57"/><circle class="ww-trk" cx="60" cy="60" r="50"/>
        <g class="ww-arcg"><circle class="ww-arc" cx="60" cy="60" r="50" transform="rotate(-90 60 60)" style="stroke:url(#${gid})"
          stroke-dasharray="${(RING * (ring === null ? 22 : ring)) / 100} ${RING}"/></g>
        ${running ? '<g class="ww-orbit"><circle cx="60" cy="3" r="3.2"/></g>' : ''}
      </svg>
      <div class="ww-mid">${mid}</div>
      <div class="ww-now"><span class="eyebrow">${esc(sw(running ? 'ww_working_on' : `ww_${s.status}`))}</span>
        <b>${esc(s.activity || '')}</b>${s.sub ? `<p>${esc(s.sub)}</p>` : ''}</div>
    </div>
    <div class="ww-bar"><i style="width:${ring === null ? 0 : ring}%"></i></div>
    <div class="ww-time">
      <div><span>${esc(sw('ww_elapsed'))}</span><b>${clk(el)}</b><em>${tPct === null ? '&nbsp;' : esc(sw('ww_pct_time', { pct: Math.min(100, tPct) }))}</em></div>
      <div><span>${esc(sw('ww_left'))}</span><b>${running ? (left === null ? esc(sw('ww_estimating')) : clk(left)) : clk(0)}</b><em>${tPct === null ? '&nbsp;' : esc(sw('ww_pct_left', { pct: Math.max(0, 100 - tPct) }))}</em></div>
      <div><span>${esc(sw('ww_total'))}</span><b>${total === null ? esc(sw('ww_estimating')) : clk(total)}</b><em>${esc(s.basis || '')}&nbsp;</em></div>
    </div>
    ${cost}
    ${(s.steps || []).length ? `<ol class="ww-steps">${s.steps.map((r) => `<li class="${esc(r.state || 'waiting')}">
        <span class="dot">${icon(r.state === 'done' ? 'check' : r.state === 'working' ? 'spark' : r.state === 'failed' ? 'alert' : 'clock', 11)}</span>
        <span class="grow">${esc(r.label || '')}</span><span class="small muted">${esc(r.note || '')}</span></li>`).join('')}</ol>` : ''}
    <div class="ww-foot"><span class="small muted grow">${esc(running ? s.note || sw('ww_note') : '')}</span>
      ${running && canStop ? `<button type="button" class="small" data-ww-stop>${icon('pause', 13)} ${esc(sw('ww_stop'))}</button>` : ''}</div>`;
}

/** Open the work window. `set(patch)` with any of {activity, sub, pct, total_s, started_ms, cost:{spent,total,models,free},
 *  steps:[{label,note,state}], basis, note}; `end(status, sub)` with finished|failed|stopped; `close()`. Closing it by
 *  hand never stops the work - Stop (when `onStop` is given) does. */
export function workWindow(title, { activity = '', onStop = null, note = '' } = {}) {
  const s = { id: ++wwCount, activity, note, status: 'running', started: Date.now(), pct: null, total_s: null, cost: null, steps: null, sub: '', basis: '' };
  let box = null;
  const close = modal(title, '<div class="ww" aria-live="polite"></div>', { cls: 'ww-modal', eyebrow: sw('ww_eyebrow'), stay: true,
    onOpen: (b) => { box = b.querySelector('.ww'); } });
  let tick = null;
  const paint = () => {
    if (!box || !box.isConnected) { clearInterval(tick); return; }
    box.innerHTML = workHtml(s, !!onStop);
    const stop = box.querySelector('[data-ww-stop]');
    if (stop) stop.onclick = () => { stop.disabled = true; onStop(); };
  };
  tick = setInterval(paint, wk('tick_ms'));
  paint();
  return {
    set(patch) {
      const { started_ms: t0, ...rest } = patch || {};
      if (t0) s.started = Number(t0);
      Object.assign(s, rest);
      paint();
    },
    end(status, sub = '') {
      s.status = status;
      if (sub) { s.activity = sub; s.sub = ''; }                 // 2026-09-30: "DONE / done" - the job's last line says what was done
      s.ended = Date.now(); clearInterval(tick); paint();
      const eb = box && box.closest('.ww-modal') && box.closest('.ww-modal').querySelector('header .eyebrow');
      if (eb) eb.textContent = sw(`ww_${status}`);                // the header said "In progress" over a finished job
    },
    close() { clearInterval(tick); close(true); },
    get isOpen() { return !!box && box.isConnected; },
  };
}

/** A job manifest (core/jobs + usage) as a work-window patch: stage, %, cost with provider·model, steps. */
export function jobPatch(job, fallback = '') {
  const st = job.steps && typeof job.steps === 'object' && !Array.isArray(job.steps) ? job.steps : null;
  const u = job.usage || {};
  const est = job.estimate_usd !== undefined && job.estimate_usd !== null ? Number(job.estimate_usd)
    : st && (st.spent_usd || st.rest_usd) ? Number(st.spent_usd || 0) + Number(st.rest_usd || 0) : null;
  const pct = job.progress !== undefined && job.progress !== null ? Number(job.progress)
    : st && st.total ? (100 * st.done) / st.total : null;
  const paid = !u.free && (u.cost_usd || est || u.provider);
  return {
    activity: job.stage || fallback,
    pct,
    ...(job.started_ms ? { started_ms: job.started_ms } : {}),
    ...(job.estimate_seconds ? { total_s: job.estimate_seconds } : {}),
    cost: paid ? { spent: Number(u.cost_usd || (st && st.spent_usd) || 0), total: est, models: [u.provider && `${u.provider} · ${u.model || ''}`] }
      : u.free ? { free: true } : null,
    sub: st && st.total ? sw('ww_steps', { done: st.done, total: st.total }) : '',
  };
}

/** A running job's inline panel: its activity, a bar, its steps and Stop - read through jobPatch (time and money are the
 *  work window's). 2026-10-03: moved here from page-studio.js (page-comics imported it from there). */
export function jobPanel(job, { working, stopId = '' }) {
  const p = jobPatch(job, working);
  const st = job.steps;
  const pct = Math.round(Math.max(0, Math.min(100, Number(p.pct) || 0)));
  return `<div class="note info jobpanel">${icon('spark', 15)}<div>
      <b>${esc(p.activity)}</b>
      <div class="bar"><i style="width:${pct}%"></i></div>
      <span class="small">${esc(p.sub || sw('job_pct', { pct }))}</span>
      ${st ? `<div class="jobsteps">${(st.steps || []).map((s, i) => `<i class="${st.status === 'running' && s.status === 'pending' && i === st.done ? 'now' : s.status}" title="${esc(s.label || '')}"></i>`).join('')}</div>` : ''}
    </div>
    ${job.status === 'running' && stopId ? `<button type="button" class="small" data-stop>${icon('pause', 13)} ${esc(sw('job_stop'))}</button>` : ''}</div>`;
}

/** Follow a running job in `out` (the inline panel) and in the work window; `onDone(job)` once it ends. */
export function watchJob(out, url, { onDone, working, stopId = '' }) {
  const stopIt = stopId ? () => api(`/api/core/jobs/${stopId}/stop`, { method: 'POST' }).catch(() => {}) : null;
  const poll = setInterval(async () => {
    let job;
    try { job = await api(url); } catch { return; }
    followJob(url, working, job, stopIt);
    if (!out || !out.isConnected) { clearInterval(poll); return; }
    out.innerHTML = jobPanel(job, { working, stopId });
    const stop = out.querySelector('[data-stop]');
    if (stop) stop.onclick = stopIt;
    if (job.status === 'running') return;
    clearInterval(poll);
    onDone(job);
  }, Number(ps('shell').job_poll_ms));
}

/** Follow a running job (`url` answers its manifest) in a work window. One window per run (url + start): a page that
 *  redraws and follows again reuses it; closed by hand it stays closed. It polls on its own, so it keeps going while
 *  the page underneath redraws or is left. */
const JOB_WINDOWS = {};
export function followJob(url, title, job, onStop = null) {
  if (!job || job.status !== 'running') return null;
  const key = `${url}@${job.started_ms || ''}`;
  if (JOB_WINDOWS[key]) return JOB_WINDOWS[key];
  const win = workWindow(title, { activity: title, onStop });
  JOB_WINDOWS[key] = win;
  const paint = (j) => {
    win.set(jobPatch(j, title));
    if (j.status === 'running') return true;
    win.end(j.status === 'finished' ? 'finished' : j.status === 'stopped' ? 'stopped' : 'failed', (j.log || []).slice(-1)[0] || '');
    return false;
  };
  paint(job);
  const poll = setInterval(async () => {
    if (!win.isOpen) { clearInterval(poll); return; }
    let j;
    try { j = await api(url); } catch { return; }
    if (!paint(j)) clearInterval(poll);
  }, wk('poll_ms'));
  return win;
}

// --- one Final check and one status + stats strip for every module (2026-09-24 owner: "standardise status and stats -
// cost, time, AI used - for Studio, Comic Book Studio, TeDBook and Audiobook"). The rows come from chip quality.check,
// the numbers from chip quality.stats; a module only passes them in. -----------------------------------------------------
const Q_ICON = { pass: 'check', fail: 'alert', skip: 'clock' };

/** The mandatory steps and the Final check of one asset (quality.check), each row with a Fix button when it fails. */
export function finalCheck(q, { fixLabel = sw('qc_fix') } = {}) {
  if (!q) return '';
  const group = (kind) => (q.rows || []).filter((r) => r.kind === kind);
  const list = (rows) => rows.map((r) => `<li class="qc-${esc(r.state)}"><span class="qc-dot">${icon(Q_ICON[r.state] || 'info', 12)}</span>
      <span class="grow">${esc(r.state === 'fail' ? r.text : r.state === 'pass' ? r.done_text : sw('qc_skip', { what: r.done_text }))}</span>
      ${r.state === 'fail' && r.fix ? `<button type="button" class="small" data-qfix="${esc(r.fix)}" data-qstep="${esc(r.step || '')}">${esc(fixLabel)}</button>` : ''}</li>`).join('');
  const f = q.final || {};
  return `<div class="qc ${f.ok ? 'ok' : 'todo'}">
      <div class="qc-head">${icon(f.ok ? 'check' : 'alert', 16)}<b>${esc(sw(f.ok ? 'qc_ok' : 'qc_todo', { fail: f.fail || 0, pass: f.pass || 0 }))}</b></div>
      ${group('gate').length ? `<h4>${esc(sw('qc_gates'))}</h4><ol>${list(group('gate'))}</ol>` : ''}
      ${group('final').length ? `<h4>${esc(sw('qc_final'))}</h4><ol>${list(group('final'))}</ol>` : ''}
      ${group('info').length ? `<h4>${esc(sw('qc_info'))}</h4><ol>${list(group('info'))}</ol>` : ''}</div>`;
}

/** Is `action` held back by a failed gate? The first reason, or '' - the server's answer (chip quality.held via
 *  quality.check `blocked`), the same rule it refuses by; the page never works a gate out itself. */
export function blockedBy(q, action) {
  return ((q && q.blocked) || {})[action] || '';
}

/** The standard strip: done, spent, still to spend, final estimate, time, AI used - and "Where the money went". */
export function statsStrip(st, extra = '') {
  if (!st) return '';
  const pct = st.pct === null || st.pct === undefined ? '—' : `${st.pct}%`;
  const at = st.time_at ? when(st.time_at) : '';
  const work = st.work_s === null ? '—' : clk(st.work_s || 0);   // null = unknown (chip quality.booked), never 0s
  const time = sw(st.time_word, { first: at, last: at, work });   // which line: chip quality.booked
  return `<div class="qs">
      <div><span>${esc(sw('st_done'))}</span><b>${esc(pct)}</b><em>${st.total ? esc(sw('st_of', { done: st.done, total: st.total })) : '&nbsp;'}</em></div>
      <div><span>${esc(sw('st_spent'))}</span><b>${usd(st.spent_usd || 0)}</b><em>${esc(sw('st_runs', { n: st.runs || 0 }))}</em></div>
      <div><span>${esc(sw('st_left'))}</span><b>${usd(st.left_usd)}</b><em>${esc(sw('ww_estimate'))}</em></div>
      <div><span>${esc(sw('st_final'))}</span><b>${usd(st.final_usd)}</b><em>${esc(sw('ww_at_complete'))}</em></div>
      <div><span>${esc(sw('st_time'))}</span><b>${esc(work)}</b><em>${esc(time)}</em></div>
      <div class="qs-ai"><span>${esc(sw('ww_ai_used'))}</span>${(st.models || []).length ? st.models.map((m) => `<i><b>${esc(m.provider)} · ${esc(m.model)}</b> ${esc(sw('st_model_line', { runs: m.runs, cost: usd(m.cost_usd) }))}</i>`).join('') : `<em>${esc(sw('st_no_ai'))}</em>`}
        ${(st.receipts || []).length ? `<button type="button" class="small ghost" data-qs-money>${icon('money', 12)} ${esc(sw('st_money'))}</button>` : ''}</div>
      ${extra}</div>`;
}

/** "Where the money went": each provider·model, then every receipt of the asset, newest first. */
export function moneyWindow(st, title) {
  modal(title || sw('st_money'), `<table class="qs-table"><thead><tr><th>${esc(sw('st_m_model'))}</th><th>${esc(sw('st_m_runs'))}</th><th>${esc(sw('st_m_time'))}</th><th>${esc(sw('st_m_cost'))}</th></tr></thead>
      <tbody>${(st.models || []).map((m) => `<tr><td>${esc(m.provider)} · ${esc(m.model)}</td><td>${m.runs}</td><td>${esc(clk(m.elapsed_s || 0))}</td><td><b>${usd(m.cost_usd)}</b></td></tr>`).join('')}</tbody>
      <tfoot><tr><td colspan="3"><b>${esc(sw('st_m_total'))}</b></td><td><b>${usd(st.spent_usd || 0)}</b></td></tr></tfoot></table>
    <h4>${esc(sw('st_receipts'))}</h4>
    <table class="qs-table"><tbody>${(st.receipts || []).map((r) => `<tr><td class="small muted">${esc(when(r.at))}</td><td>${esc(r.what || '')}</td><td class="small muted">${esc(r.provider || '')} · ${esc(r.model || '')}</td><td>${usd(r.cost_usd)}</td></tr>`).join('')}</tbody></table>`, { wide: true });
}

/** Wire a strip's "Where the money went" button. */
export function wireStats(host, st, title) {
  host.querySelectorAll('[data-qs-money]').forEach((b) => { b.onclick = () => moneyWindow(st, title); });
}

// --- the four roads of every activity (2026-09-23 owner, CBS; 2026-09-24 "the 4-way mix and match is how every asset is
// built"): the portal does it (free), the LLM Bridge (copy the prompt, paste the answer), AI (priced first), or do it
// yourself. One activity card for every module; a road an activity does not have is not shown. Words: chip ui.shell rd_*.
// 2026-09-26: the four roads and their icons are chip page.shell (loaded with the shell's words)
export const ROADS = [];
export const roadIcon = (k) => (ps('shell').road_icons || {})[k];

/** One activity: title, where it stands, done?, roads[k] = { act, label?, note?, off? } or null, extra html under it. */
export function activityCard(title, state, done, roads, extra = '') {
  const have = ROADS.filter((k) => roads[k]);
  return `<div class="cb-activity ${done ? 'ok' : ''}">
    <div class="cb-acthead"><span class="cb-actdot">${done ? icon('check', 12) : icon('clock', 12)}</span><b>${esc(title)}</b><span class="small muted">${esc(state)}</span></div>
    <div class="cb-roads n${have.length}">${have.map((k) => {
      const r = roads[k];
      return `<button type="button" class="cb-rd ${k}" data-act="${esc(r.act)}" ${r.off ? `aria-disabled="true" data-off="${esc(r.off)}" title="${esc(r.off)}"` : ''}>${icon(roadIcon(k), 12)}<span><b>${esc(r.label || sw(`rd_${k}`))}</b><span class="small muted">${esc(r.off || r.note || '')}</span></span></button>`;
    }).join('')}</div>${extra}</div>`;
}

// 2026-09-30 owner rule "buttons are never greyed on first open": a road that cannot run yet stays a live button - a press
// says why (its own reason, the words the page gave) and runs nothing. 2026-10-01: the same for EVERY button of every
// screen (never `disabled` by state) - how it answers is chip page.shell off_buttons, its reason a word of its screen.
document.addEventListener('click', (e) => {
  const b = e.target.closest && e.target.closest('[data-off]');
  if (!b) return;
  e.preventDefault();
  e.stopImmediatePropagation();
  const k = ps('shell').off_buttons || {};
  toast(b.dataset.off || sw(k.fallback_word || 'off_default'), k.toast || 'warn', Number(k.seconds) || 6);
}, true);

/** A button that cannot act yet - the attributes that keep it live and make a press say why (`reason` = a chip word). */
export function offAttr(reason) {
  return reason ? ` aria-disabled="true" data-off="${esc(reason)}" title="${esc(reason)}"` : '';
}

/** The same for a button already on the page (instead of `.disabled = x`): `reason` falsy = it may act. */
export function setOff(el, reason) {
  if (!el) return;
  if (reason) { el.setAttribute('aria-disabled', 'true'); el.dataset.off = reason; el.title = reason; }
  else { el.removeAttribute('aria-disabled'); delete el.dataset.off; }
}

/** The four roads explained - the same help panel on every module. */
export function roadsHelp() {
  return `<h3>${icon('info', 15)} ${esc(sw('rd_h'))}</h3>${ROADS.map((k) => `<p class="small"><b>${icon(roadIcon(k), 12)} ${esc(sw(`rd_${k}`))}</b><br/><span class="muted">${esc(sw(`rd_${k}_how`))}</span></p>`).join('')}`;
}

/** The LLM Bridge in one popup: the prompt to copy, a box for the model's answer, `onPaste(text)` takes it in. */
/** The reference pictures a Bridge prompt names, numbered in its order: click one to save it, then attach them in order.
 *  refs = [{kind: face|prev|place, name, url}] (the same pictures the AI road sends). */
export function refsHtml(refs) {
  if (!(refs || []).length) return '';
  return `<div class="rd-refs"><b class="small">${esc(sw('rd_refs'))}</b><div class="rd-refrow">${refs.map((r, i) => `
    <a class="rd-ref" href="${BASE}${esc(r.url)}" title="${esc(sw('rd_ref_save'))}"><img src="${BASE}${esc(r.url)}" alt="" loading="lazy"/>
      <span class="small"><b>${i + 1}</b> ${esc(r.name || sw(`rd_ref_${r.kind}`))}</span></a>`).join('')}</div></div>`;
}

/** `upload` instead of `onPaste`: the answer is a picture - its button opens the upload box. */
export function bridgeBox(title, prompt, note, onPaste, { upload = null, refs = [], words = {} } = {}) {
  // `words` = the page's own labels, already said ({prompt, copy, upload}) - 2026-10-03 owner: the Audiobook's Bridge said
  // "copy it to your model" and "upload the picture" for a chapter's text and its audio. The defaults are the picture road's.
  modal(title, `<p class="small muted">${esc(note || sw('rd_bridge_how'))}</p>${refsHtml(refs)}
      <label class="as-lab wide">${esc(words.prompt || sw('rd_prompt'))}<textarea readonly rows="7" id="rb-prompt">${esc(prompt)}</textarea></label>
      <button type="button" class="small" id="rb-copy">${icon('link', 12)} ${esc(words.copy || sw('rd_copy'))}</button>
      ${onPaste ? `<label class="as-lab wide">${esc(sw('rd_answer'))}<textarea rows="7" id="rb-answer" placeholder="${esc(sw('rd_answer_ph'))}"></textarea></label>` : ''}`, {
    wide: true,
    footer: onPaste ? `<button type="button" class="primary" data-take>${icon('check', 13)} ${esc(sw('rd_take'))}</button>`
      : upload ? `<button type="button" class="primary" data-up>${icon('upload', 13)} ${esc(words.upload || sw('rd_paste_picture'))}</button>` : '',
    onOpen: (m, close) => {
      m.querySelector('#rb-copy').onclick = () => navigator.clipboard.writeText(prompt).then(() => toast(sw('rd_copied'), 'ok'));
      const upb = m.closest('.modal').querySelector('[data-up]');
      if (upb) upb.onclick = () => { close(true); upload(); };
      const bt = m.closest('.modal').querySelector('[data-take]');
      if (bt) bt.onclick = () => busy(bt, async () => {
        const text = m.querySelector('#rb-answer').value.trim();
        if (!text) { toast(sw('rd_answer_first'), 'warn'); return; }
        try { await onPaste(text); close(true); } catch (err) { toast(err.message, 'bad', 8); }
      });
    } });
}

/** The two model pickers (2026-09-25 owner: "you chose the model on your own - let the user decide"): the text model
 *  and the picture model a comic or a Doodly Video uses, picked by the person; a road only pre-fills them. `models`
 *  = {text: [...], image: [...]} (providers.offered); a model whose key is missing is named and cannot be picked. */
export function modelPickers(models, picked = {}, ai = true) {
  const opts = (kind) => (models[kind] || []).map((m) => `<option value="${esc(m.id)}" ${m.id === picked[`${kind}_model`] ? 'selected' : ''} ${m.have_key || m.id === picked[`${kind}_model`] ? '' : 'disabled'}>${esc(m.label)} · ${esc(m.provider)}${m.have_key ? '' : ` · ${esc(sw('mp_nokey'))}`}</option>`).join('');
  return `<div class="mp-models" ${ai ? '' : 'hidden'}>
    <label class="as-lab">${esc(sw('mp_text'))}<select id="mp-text">${opts('text')}</select></label>
    <label class="as-lab">${esc(sw('mp_image'))}<select id="mp-image">${opts('image')}</select></label></div>`;
}
/** Wire a road <select> to the pickers: a new road fills them with its own pair (the person can still change them),
 *  the free road hides them. Returns () => {road, text_model, image_model} for the save call. */
export function wireModelPickers(root, roadSel, roads) {
  const box = root.querySelector('.mp-models');
  const set = () => {
    const r = roads.find((x) => x.id === roadSel.value) || {};
    box.hidden = !r.ai;
    if (r.ai) { root.querySelector('#mp-text').value = r.text_model; root.querySelector('#mp-image').value = r.image_model; }
  };
  roadSel.addEventListener('change', set);
  return () => ({ road: roadSel.value, ...(box.hidden ? {} : { text_model: root.querySelector('#mp-text').value, image_model: root.querySelector('#mp-image').value }) });
}

/** 2026-09-26 owner: "when I click AI let me select - by the job, every model that can do it, with price and quality".
 *  `opt` = {kind, n, current, models:[{id,label,provider,have_key,cost_usd,quality,good_for,recommended}]} from the
 *  page's ai-options call. Pre-selects the model in use, else the Recommended one; a model without a key is shown and
 *  cannot be picked. Resolves the picked id, or null when closed. The price shown IS the confirmation. */
/** A model's quality as stars (the one drawing every picker uses; the scale is chip page.shell quality_stars). */
export function qualityStars(q) {
  const most = Number(ps('shell').quality_stars) || 5;
  return '★'.repeat(Math.min(most, q)) + '☆'.repeat(Math.max(0, most - q));
}

export function aiPick(opt) {
  const ms = opt.models || [];
  const pre = (ms.find((m) => m.id === opt.current && m.have_key) || ms.find((m) => m.recommended) || ms.find((m) => m.have_key) || {}).id;
  const stars = (q) => (q ? qualityStars(q) : sw('ap_q_unknown'));
  const cost = (m) => (m.cost_usd === null || m.cost_usd === undefined ? sw('ap_price_unknown') : m.cost_usd === 0 ? sw('ap_free') : usd(m.cost_usd));
  return new Promise((done) => {
    let picked = null;
    modal(sw(`ap_title_${opt.kind}`), `<p class="small muted">${esc(sw(`ap_lede_${opt.kind}`, { n: opt.n }))}</p>
      <div class="ap-list">${ms.map((m) => `<label class="ap-row ${m.have_key ? '' : 'off'}" title="${esc(m.good_for || '')}">
        <input type="radio" name="ap" value="${esc(m.id)}" ${m.id === pre ? 'checked' : ''} ${m.have_key ? '' : 'disabled'}>
        <span class="ap-name"><b>${esc(m.label)}</b> <span class="muted small">${esc(m.provider)}</span>${m.recommended ? ` <span class="tag ok">${esc(sw('ap_rec'))}</span>` : ''}
          <span class="small muted ap-use">${esc(m.good_for || '')}${m.have_key ? '' : ` · ${esc(sw('mp_nokey'))}`}</span></span>
        <span class="ap-q" title="${esc(sw('ap_q_tip'))}">${stars(m.quality)}</span><b class="ap-cost">${esc(cost(m))}</b></label>`).join('')}</div>
      ${opt.check ? `<label class="ap-check"><input type="checkbox" id="ap-verify" ${opt.check.wanted ? 'checked' : ''}/>
        <span><b>${esc(sw(`ap_check_${opt.kind}`))}</b> <span class="small muted">${esc(sw(opt.kind === 'video' ? 'ap_check_video_note' : 'ap_check_note', { each: cost({ cost_usd: opt.check.each_usd }) }))}</span></span></label>` : ''}`, {
      wide: true, stay: true, eyebrow: sw('ap_paid'), onClose: () => done(picked),   // every paid confirm says paid
      footer: `<button type="button" class="primary" data-save>${icon('spark', 13)} ${esc(sw('ap_go'))}</button>`,
      onOpen: (m, close) => {
        const b = m.closest('.modal').querySelector('[data-save]');
        b.onclick = async () => {
          const r = m.querySelector('input[name=ap]:checked'); if (!r) return;
          const vb = m.querySelector('#ap-verify');          // 2026-09-27: the picture check, remembered per person and kind
          if (vb && vb.checked !== !!opt.check.wanted) { try { await api('/api/ai/verify', { method: 'POST', body: { kind: opt.kind, on: vb.checked } }); } catch (err) { toast(err.message, 'bad', 8); return; } }
          picked = r.value; close(true);
        };
      } });
  });
}

/** 2026-09-27 owner: "across the portal". Every AI button: the picker (every model of that kind, priced for THIS job,
 *  with its quality), then the pick is saved (`save(id)` - a comic's own models; else the person's own model for that
 *  kind), then `run(id)`. The price in the picker is the confirmation. `job`: tokens_in/out, n, seconds, or
 *  ref_model + ref_cost (the page's own estimate, scaled per model). */
export async function aiRun(kind, job, save, run) {
  let opt;
  try { opt = await api('/api/ai/options', { method: 'POST', body: { kind, ...job } }); } catch (err) { toast(err.message, 'bad', 8); return; }
  if (!(opt.models || []).some((m) => m.have_key)) { toast(sw('ap_no_keys'), 'warn', 8); return; }
  const id = await aiPick(opt);
  if (!id) return;
  try { await (save ? save(id) : api('/api/ai/choose', { method: 'POST', body: { kind, model: id } })); } catch (err) { toast(err.message, 'bad', 8); return; }
  await run(id);
}

/** The prompt icon (2026-09-24 owner: "for any asset and its components - clicking it shows the prompt used to create
 *  it, be it the LLM Bridge or AI"). kind + ids name the output (GET /api/prompt); one click handler for every page. */
export function promptIcon(kind, a, b = '') {
  return `<button type="button" class="small ghost pr-ico" data-prompt-of="${esc(kind)}" data-pa="${esc(a)}" data-pb="${esc(b)}" title="${esc(sw('pr_title'))}" aria-label="${esc(sw('pr_title'))}">${icon('clock', 12)} ${esc(sw('pr_short'))}</button>`;   // 2026-09-26 owner could not find a bare ">_" icon
}
async function showPrompt(kind, a, b) {
  // 2026-09-26 owner: "let me re-make anything; I can download the old one and put it back". The same icon shows the
  // prompt AND every earlier version keep_aside() kept: download it, or put it back (the current one is kept in turn).
  const q = `kind=${encodeURIComponent(kind)}&a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`;
  let d;
  let vs;
  try { [d, vs] = await Promise.all([api(`/api/prompt?${q}`), api(`/api/versions?${q}`).catch(() => ({ versions: [] }))]); } catch (err) { toast(err.message, 'bad', 8); return; }
  const list = vs.versions || [];
  const prompt = d.none ? '' : `<p class="small"><b>${esc(sw(`pr_road_${d.road}`, { provider: d.provider || '', model: d.model || '' }))}</b>${d.at ? ` <span class="muted">· ${esc(when(d.at))}</span>` : ''}</p>
      ${(d.refs || []).length ? `<p class="small muted">${esc(sw('pr_refs', { list: d.refs.map((r, i) => `${i + 1}. ${r}`).join('  ') }))}</p>` : ''}
      <label class="as-lab wide">${esc(sw('rd_prompt'))}<textarea readonly rows="12" id="pr-text">${esc(d.prompt)}</textarea></label>
      <button type="button" class="small" id="pr-copy">${icon('link', 12)} ${esc(sw('rd_copy'))}</button>`;
  const ck = d.check;                                 // 2026-09-27: the picture check's verdict
  const verdict = ck ? `<div class="note ${ck.ok ? 'ok' : 'warn'}" style="margin:8px 0">${icon(ck.ok ? 'check' : 'alert', 15)}<div><b>${esc(sw(ck.ok ? 'ck_ok' : 'ck_bad', { tries: ck.tries || 1 }))}</b>
      ${(ck.problems || []).length ? `<ul class="small">${ck.problems.map((x) => `<li>${esc(x)}</li>`).join('')}</ul>` : ''}<span class="small muted">${esc(sw('ck_by', { model: ck.model || '' }))}</span></div></div>` : '';
  const earlier = list.length ? `<h3 class="sw-h3" style="margin-top:14px">${icon('clock', 14)} ${esc(sw('vr_title', { n: list.length }))}</h3>
      <p class="small muted">${esc(sw('vr_note'))}</p>
      <div class="vr-list">${list.map((r) => `<div class="row between vr-row"><span class="small">${esc(when(r.at))} · ${esc((r.size / 1024).toFixed(0))} KB</span>
        <span class="row" style="gap:6px"><a class="small" href="${BASE}/api/versions/file?${q}&v=${encodeURIComponent(r.v)}" download>${icon('download', 12)} ${esc(sw('vr_download'))}</a>
        <button type="button" class="small" data-vr="${esc(r.v)}">${icon('refresh', 12)} ${esc(sw('vr_restore'))}</button></span></div>`).join('')}</div>` : '';
  if (!prompt && !earlier && !verdict) { modal(sw('pr_title'), `<p class="muted">${esc(sw('pr_none'))}</p>`); return; }
  modal(sw('pr_title'), verdict + prompt + earlier, {
    wide: true,
    onOpen: (m, close) => {
      const cp = m.querySelector('#pr-copy');
      if (cp) cp.onclick = () => navigator.clipboard.writeText(d.prompt).then(() => toast(sw('rd_copied'), 'ok'));
      m.querySelectorAll('[data-vr]').forEach((btn) => {
        btn.onclick = () => confirmDialog(sw('vr_ask_title'), sw('vr_ask_body'), async () => {
          try {
            await api('/api/versions/restore', { method: 'POST', body: { kind, a, b, v: btn.dataset.vr } });
            close(true); toast(sw('vr_done'), 'ok');
            window.dispatchEvent(new HashChangeEvent('hashchange'));   // the screen redraws with the version put back
          } catch (err) { toast(err.message, 'bad', 8); }
        }, sw('vr_restore'), { tone: 'warn' });
      });
    } });
}
document.addEventListener('click', (e) => {
  const b = e.target.closest && e.target.closest('[data-prompt-of]');
  if (!b) return;
  e.preventDefault();
  e.stopPropagation();
  showPrompt(b.dataset.promptOf, b.dataset.pa, b.dataset.pb || '');
}, true);

/** Do it yourself / Bridge answer as a file: one drop zone (Ctrl+V pastes a picture), POSTed as `file` to `url`. */
export function uploadBox(title, exts, url, then) {
  modal(title, dropZone('rb-up-file', { accept: exts.join(','), title, hint: exts.join(' ') }), {
    footer: `<button type="button" class="primary" data-save>${icon('upload', 13)} ${esc(sw('as_save'))}</button>`,
    onOpen: (m, close) => {
      wireDrops(m);
      m.closest('.modal').querySelector('[data-save]').onclick = (ev) => {
        const f = m.querySelector('#rb-up-file').files[0];
        if (!f) { toast(sw('as_file_first'), 'warn'); return; }
        busy(ev.currentTarget, async () => {
          const fd = new FormData(); fd.append('file', f);
          try { await api(url, { method: 'POST', body: fd }); close(); toast(sw('rd_saved'), 'ok'); await then(); } catch (err) {
            // 2026-10-04: the server may offer to replace what is there ({replace, ask, yes}) - ask, then send it again
            const o = err.data || {};
            if (err.status === 409 && o.replace) {
              close();
              confirmDialog(err.message, o.ask || err.message, async () => {
                const again = new FormData(); again.append('file', f);
                try { await api(`${url}${url.includes('?') ? '&' : '?'}replace=${encodeURIComponent(o.replace)}`, { method: 'POST', body: again }); toast(sw('rd_saved'), 'ok'); await then(); }
                catch (e2) { toast(e2.message, 'bad', 8); }
              }, o.yes || sw('rd_saved'), { tone: 'warn' });
            } else toast(err.message, 'bad', 8);
          }
        });
      };
    } });
}

// --- one way to create, open, rename, inspect, export and delete ANY asset (2026-09-24 owner: "who knows Excel knows
// Word and PowerPoint - product and standardisation"). Chip assets.types describes every type; these two pieces are the
// whole of it on every screen: assetHome (the Home: New, Import, search, the cards) and assetBar (the file bar on top of
// an open asset: Home, its name, Rename, Info, Export, Delete). A screen keeps only its own editor. ---------------------
let ASSET_TYPES = null;
export async function assetType(kind) {
  if (!ASSET_TYPES) ASSET_TYPES = (await api('/api/assets/types')).types;
  return ASSET_TYPES.find((x) => x.id === kind);
}

/** The asset's Info: what it is, when, by whom, from what - its Final check and its stats. */
export async function assetInfo(kind, id) {
  const d = await api(`/api/assets/${kind}/${encodeURIComponent(id)}/info`);
  const row = (k, v) => `<div><span>${esc(sw(k))}</span><b>${esc(v || '—')}</b></div>`;
  modal(sw('as_info_title', { name: d.name }), `<div class="as-infogrid">
      ${row('as_type', sw(`as_t_${kind}`))}${row('as_created', when(d.created))}
      ${row('as_updated', when(d.updated))}${row('as_by', d.created_by)}
      ${row('as_source', d.source_detail || sw(`as_src_${d.source}`))}
      ${d.provenance && d.provenance.original_author ? `${row('as_author', d.provenance.original_author)}${row('as_origin', d.provenance.original_portal)}
        ${row('as_cost_before', d.provenance.cost_usd ? usd(d.provenance.cost_usd) : sw('as_cost_none'))}
        ${row('as_cost_total', usd(d.provenance.cost_total_usd || 0))}` : ''}</div>
    ${d.provenance && (d.provenance.breakup || []).length ? `<h4>${esc(sw('as_cost_breakup'))}</h4><table class="qs-table"><thead><tr><th>${esc(sw('as_m_portal'))}</th>
        <th>${esc(sw('st_m_model'))}</th><th>${esc(sw('st_m_runs'))}</th><th>${esc(sw('st_m_time'))}</th><th>${esc(sw('st_m_cost'))}</th></tr></thead>
      <tbody>${d.provenance.breakup.map((m) => `<tr><td>${esc(m.portal || '')}</td><td>${esc(m.provider || '')} · ${esc(m.model || '')}</td><td>${Number(m.runs || 0)}</td>
        <td>${esc(clk(m.elapsed_s || 0))}</td><td><b>${usd(m.cost_usd)}</b></td></tr>`).join('')}</tbody>
      <tfoot><tr><td colspan="4"><b>${esc(sw('as_cost_total'))}</b></td><td><b>${usd(d.provenance.cost_total_usd || 0)}</b></td></tr></tfoot></table>` : ''}
    ${statsStrip(d.stats)}${finalCheck(d.check)}`, { wide: true });
}

/** Delete - always the app's own warning (never the browser's), naming what goes; the server refuses what is in use. */
export function assetDelete(t, w, id, name, onDone, blocked = '') {
  // 2026-09-22 owner: something in use is never deleted - say so BEFORE asking (the server refuses it too)
  if (blocked) { modal(sw('as_cannot_delete'), `<p class="confirm-msg">${esc(blocked)}</p>`, { cls: 'confirm tone-warn', eyebrow: sw('please_confirm') }); return; }
  confirmDialog(w(t.words.delete_title), w(t.words.delete_body, { name, title: name }), async () => {
    try { const r = await api(`/api/assets/${t.id}/${encodeURIComponent(id)}`, { method: 'DELETE' }); toast(r.message || sw('as_deleted'), 'ok'); await onDone(); }
    catch (err) { modal(sw('as_cannot_delete'), `<p class="confirm-msg">${esc(err.message)}</p>`, { cls: 'confirm tone-warn', eyebrow: sw('please_confirm') }); }
  }, w(t.words.delete_yes), { tone: 'danger' });
}

export function assetRename(t, id, name, onDone) {
  modal(sw('as_rename_title'), `<label class="as-lab">${esc(sw('as_rename_label'))}<input id="as-rn" maxlength="${Number(t.name_max) || 160}" value="${esc(name)}"/></label>`, {
    footer: `<button type="button" class="primary" data-save>${icon('save', 13)} ${esc(sw('as_save'))}</button>`,
    onOpen: (m, close) => {
      const inp = m.querySelector('#as-rn'); inp.focus(); inp.select();
      const bt = m.closest('.modal').querySelector('[data-save]');
      const go = () => busy(bt, async () => {
        try { await api(`/api/assets/${t.id}/${encodeURIComponent(id)}`, { method: 'PUT', body: { name: inp.value } }); close(); await onDone(inp.value.trim()); }
        catch (err) { toast(err.message, 'bad'); }
      });
      bt.onclick = go; inp.onkeydown = (e) => { if (e.key === 'Enter') go(); };
    } });
}

/** The New dialog, the same for every type: its fields (chip) and the file it takes. `options` = {name: [{value,label}]}. */
function assetNew(t, w, { options = {}, accept = [] } = {}, onMade) {
  const f = t.file || null;
  const field = (x) => {
    const lab = `${esc(w(x.word))}${x.required ? ' *' : ''}`;
    if (x.kind === 'textarea') return `<label class="as-lab wide">${lab}<textarea name="${esc(x.name)}" rows="2" maxlength="${Number(x.max) || 500}"></textarea></label>`;
    if (x.kind === 'check') return `<label class="as-lab wide as-check"><input type="checkbox" name="${esc(x.name)}" value="1"/> <span>${lab}</span></label>`;
    if (x.kind === 'select') return `<label class="as-lab">${lab}<select name="${esc(x.name)}">${(options[x.options] || []).map((o) => `<option value="${esc(o.value)}" ${o.selected ? 'selected' : ''} ${o.disabled ? 'disabled' : ''}>${esc(o.label)}</option>`).join('')}</select></label>`;
    // a template (chip assets.types: kind `template` + the type's `templates`): shown as the one in use, picked in the ONE gallery
    if (x.kind === 'template') return `<div class="as-lab wide" data-tplfield><input type="hidden" name="${esc(x.name)}"/><span data-tplslot></span></div>`;
    return `<label class="as-lab">${lab}<input name="${esc(x.name)}" maxlength="${Number(x.max) || 200}"/></label>`;
  };
  modal(w(t.words.new), `<form id="as-newform" class="as-newgrid" novalidate>
      ${f ? `<div class="wide">${dropZone('as-file', { accept: accept.join(','), title: w(f.word), hint: w(f.hint) })}</div>` : ''}
      ${t.fields.map(field).join('')}</form>`, {
    footer: `<button type="button" class="primary" data-make>${icon('spark', 14)} ${esc(w(t.words.make))}</button>`,
    onOpen: (m, close) => {
      wireDrops(m);
      m.querySelectorAll('[data-tplfield]').forEach(async (el) => {
        const d = await deckTemplates(t.templates);
        const show = (id) => {
          el.querySelector('input').value = id;
          el.querySelector('[data-tplslot]').innerHTML = deckTemplateButton(d, id, t.templates);
          el.querySelector('[data-tpl-open]').onclick = () => deckGallery(id, show, () => {}, t.templates);
        };
        show(d.default);
      });
      const form = m.querySelector('#as-newform');
      const bt = m.closest('.modal').querySelector('[data-make]');
      bt.onclick = () => {
        const need = t.fields.find((x) => x.required && !String(form.elements[x.name].value || '').trim());
        if (need) { toast(sw('as_fill', { field: w(need.word) }), 'warn'); form.elements[need.name].focus(); return; }
        const file = f ? m.querySelector('#as-file').files[0] : null;
        if (f && f.required && !file) { toast(sw('as_file_first'), 'warn'); return; }
        busy(bt, async () => {
          const fd = new FormData(form);
          if (file) fd.append('file', file);
          close.hold(true);
          try { const got = await api(`/api/assets/${t.id}`, { method: 'POST', body: fd }); close.hold(false); close(true); await onMade(got.id); }
          catch (err) { close.hold(false); toast(err.message, 'bad', 8); }
        });
      };
    } });
}

/** The Home of a screen: New, Import, search and one card per asset, the same on every screen.
 *  opts: w (the screen's words), onOpen(id), options/accept (for New), extra = [{label, icon, run}] more ways in,
 *  onNew() = the type's own New (a streamed upload), acts = [{label, icon, run(id)}] more buttons on each card,
 *  lead = html above the cards (a start-here or storage strip). */
// 2026-09-26: the final check's Fix button (data-qfix) jumps to the part of the page that fixes it - the section a page
// marks data-fix="<fix> ..." (fix names come from chip quality.rules). A page with its own Fix handler (onclick) keeps it.
document.addEventListener('click', (e) => {
  const bt = e.target.closest && e.target.closest('[data-qfix]');
  if (!bt || bt.onclick) return;
  const to = [...document.querySelectorAll('[data-fix]')].find((el) => el.dataset.fix.split(/\s+/).includes(bt.dataset.qfix));
  if (!to) { toast(sw('fix_where'), 'info', 6); return; }
  to.scrollIntoView({ behavior: 'smooth', block: 'center' });
  to.classList.add('fix-flash');
  setTimeout(() => to.classList.remove('fix-flash'), 1800);
  const field = to.matches('input,select,textarea,button') ? to : to.querySelector('input,select,textarea,button');
  if (field) field.focus({ preventScroll: true });
});

/** 2026-09-28 owner: "We will not have email - we will have Report the way we have in TeDBook". The ONE Report-an-issue
 *  form (AstroStage.in's ReportIssue.tsx): header, what is wrong, an optional screenshot; the signed-in account rides
 *  along. `surface`/`context` say where it came from; `url` + `extra` let a screen add its own tick (Katha's
 *  "copies my work"); `extraBody(root)` reads it. Lands in core Reported issues (core/issues.py). */
export function reportIssue({ surface = '', context = '', url = '/api/core/issues', extra = '', extraBody = () => ({}), onSent = () => {}, shot: preShot = '' } = {}) {
  let shot = preShot;   // 2026-10-04: the dock's Screen capture hands its picture over
  modal(sw('report_title'), `<p class="small muted">${esc(sw('report_lede'))}</p>
    <div class="field"><label for="ri-title">${esc(sw('report_header'))}</label><input id="ri-title" maxlength="200"/></div>
    <div class="field"><label for="ri-body">${esc(sw('report_body'))}</label><textarea id="ri-body" rows="5"></textarea></div>
    <div class="field"><label>${esc(sw('report_shot'))}</label>${preShot ? `<img class="dk-shot" src="${preShot}" alt=""/>` : dropZone('ri-shot', { accept: 'image/*' })}</div>
    ${extra}<div id="ri-msg"></div>`, {
    footer: `<button type="button" data-cancel>${esc(sw('cancel_report'))}</button><button type="button" class="primary" id="ri-go">${esc(sw('report_go'))}</button>`,
    onOpen: (body, close) => {
      const card = body.closest('.modal');
      card.querySelector('[data-cancel]').onclick = close;
      // the ONE file box of the portal (dropZone: browse, drop or paste), never a bare file input
      wireDrops(body, (f) => {
        shot = '';
        if (!f) return;
        if (f.size > 2 * 1024 * 1024) { say(body.querySelector('#ri-msg'), 'bad', esc(sw('report_shot_big'))); return; }
        const rd = new FileReader();
        rd.onload = () => { shot = String(rd.result || ''); };
        rd.readAsDataURL(f);
      });
      card.querySelector('#ri-go').onclick = (e) => busy(e.currentTarget, async () => {
        try {
          const r = await api(url, { method: 'POST', body: { title: body.querySelector('#ri-title').value, body: body.querySelector('#ri-body').value,
            screenshot: shot, surface, context, ...extraBody(body) } });
          close(); toast(r.message, 'ok', 8); onSent(r);
        } catch (err) { say(body.querySelector('#ri-msg'), 'bad', esc(err.message)); }
      });
    } });
}

/** 2026-10-03 owner: "Where I as reader can see all my feedbacks?" - every note this person sent, of every kind (Report an
 *  issue, feedback on a work), with its status and the answer: list my_reports (core/issues.py). A row with a link opens it. */
export function myReports() {
  modal(sw('my_reports'), `<p class="small muted">${esc(sw('my_reports_lede'))}</p><div id="mr-list"></div>`, {
    wide: true,
    onOpen: (body, close) => listBox(body.querySelector('#mr-list'), { list: 'my_reports', empty: sw('my_reports_none'),
      row: (r) => `<div class="lent-row" style="display:block;padding:8px 0">
        <div class="row tight small"><span class="tag">${esc(r.status_label)}</span><b>${esc(r.about || r.title)}</b>
          <span class="muted">${esc(r.kind_label)} · ${when(r.at)}</span><span class="spacer"></span>
          ${r.link ? `<a class="small" href="${esc(r.link)}" data-mr-open>${esc(sw('my_reports_open'))}</a>` : ''}</div>
        <p class="small" style="margin:4px 0;white-space:pre-wrap">${esc(r.title && r.about ? `${r.title} - ${r.text}` : r.text)}</p>
        ${r.reply || r.action_date ? `<div class="small k-replies"><b>${esc(sw('my_reports_answer'))}</b> ${esc(r.reply)} <span class="muted">${esc(r.action_date)}</span></div>` : ''}
      </div>`,
      wire: (rows) => rows.querySelectorAll('[data-mr-open]').forEach((a) => { a.addEventListener('click', () => close()); }) }) });
}

/** 2026-09-28 owner: "it goes beyond 10 we are gone" - the ONE way a screen shows a list that grows with people.
 * The server searches, sorts and pages it (core/lists.py, chip list.<list>); one page is drawn here, with a search box
 * and a pager. `row(r)` draws one row; `wrap(html)` puts the rows in their table; `wire(rowsHost, page, reload)` wires
 * their buttons; `args` = the list's filters; `url` = a route of its own for a list anyone may read; `q` = a search to start
 * with; `suggest` = a route answering ?q= with {suggestions} for the search box.
 * Returns reload(). */
export function listBox(host, { list, args = {}, row, wire = () => {}, empty = '', wrap = (html) => html, url = '', q = '', suggest = '' }) {
  const st = { q, page: 1 };
  const dl = `lb-dl-${Math.random().toString(36).slice(2, 8)}`;
  host.innerHTML = `<div class="row tight lb-bar"><input type="search" class="lb-q" placeholder="${esc(sw('list_search'))}" aria-label="${esc(sw('list_search'))}" style="max-width:280px"
      value="${esc(q)}" ${suggest ? `list="${dl}" autocomplete="off"` : ''}/>${suggest ? `<datalist id="${dl}"></datalist>` : ''}
    <span class="small muted lb-count"></span></div><div class="lb-rows"></div><div class="row tight lb-pager"></div>`;
  const rows = host.querySelector('.lb-rows');
  const pager = host.querySelector('.lb-pager');
  const load = async () => {
    let r;
    // `url`: a list anyone may read (the public Katha shelf) is served by its own route, paged the same way
    try { r = await api(`${url || `/api/lists/${encodeURIComponent(list)}`}?${new URLSearchParams({ ...args, q: st.q, page: st.page })}`); }
    catch (err) { rows.innerHTML = `<p class="small bad">${esc(err.message)}</p>`; return; }
    st.page = r.page;
    const from = r.total ? (r.page - 1) * r.page_size + 1 : 0;
    host.querySelector('.lb-count').textContent = r.total ? sw('list_page', { from, to: Math.min(r.total, r.page * r.page_size), total: r.total }) : '';
    rows.innerHTML = r.rows.length ? wrap(r.rows.map(row).join('')) : `<p class="small muted">${esc(st.q ? sw('list_no_match') : (empty || sw('list_none')))}</p>`;
    // no greyed buttons: a pager button is simply not there at either end
    pager.innerHTML = `${r.page > 1 ? `<button type="button" class="small ghost" data-lb-page="${r.page - 1}">${icon('left', 12)} ${esc(sw('list_prev'))}</button>` : ''}
      ${r.page < r.pages ? `<button type="button" class="small ghost" data-lb-page="${r.page + 1}">${esc(sw('list_next'))} ${icon('right', 12)}</button>` : ''}`;
    pager.querySelectorAll('[data-lb-page]').forEach((b) => { b.onclick = () => { st.page = Number(b.dataset.lbPage); load(); }; });
    wire(rows, r, load);
  };
  let timer = 0;
  host.querySelector('.lb-q').oninput = (e) => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      st.q = e.target.value; st.page = 1; load();
      // `suggest`: a route answering ?q= with {suggestions} - what the box offers under it as you type
      if (suggest && st.q.trim()) api(`${suggest}?q=${encodeURIComponent(st.q)}`).then((r) => {
        host.querySelector(`#${dl}`).innerHTML = (r.suggestions || []).map((x) => `<option value="${esc(x)}"></option>`).join('');
      }).catch(() => {});
    }, 300);
  };
  load();
  return load;
}

/** ONE way to choose from a collection that grows (2026-10-01 owner "1000s of cards ... 20 or 50 groups"): a search box
 *  that offers the first page of a server list (core/lists.py, chip list.<id>) as you type - never a <select> or a tab
 *  bar holding every row. `name(row)` is what the box shows, `tag(row)` an optional label after it; `onPick(row)` runs on
 *  a choice. `value` = the row chosen at start. Returns { value() } - the chosen row (or null). Guard: tv/selfcheck.py. */
export function pickList(host, { list, args = {}, url = '', name = (r) => r.name || r.title || r.id, tag = () => '', value = null, onPick = () => {}, placeholder = '', onAdd = null }) {
  const st = { chosen: value, timer: 0, rows: [] };
  host.classList.add('pk-host');
  host.innerHTML = `<input type="search" class="pk-q" role="combobox" aria-expanded="false" autocomplete="off"
      placeholder="${esc(placeholder || sw('pick_search'))}" aria-label="${esc(placeholder || sw('pick_search'))}" value="${esc(value ? name(value) : '')}"/>
    <div class="pk-list" role="listbox" hidden></div>`;
  const q = host.querySelector('.pk-q');
  const box = host.querySelector('.pk-list');
  const shut = () => { box.hidden = true; q.setAttribute('aria-expanded', 'false'); };
  const choose = (r) => { st.chosen = r; q.value = name(r); shut(); onPick(r); };
  const load = async () => {
    let r;
    const typed = st.chosen && q.value === name(st.chosen) ? '' : q.value;
    try { r = await api(`${url || `/api/lists/${encodeURIComponent(list)}`}?${new URLSearchParams({ ...args, q: typed, page: 1 })}`); }
    catch (err) { box.innerHTML = `<p class="small bad">${esc(err.message)}</p>`; box.hidden = false; return; }
    st.rows = r.rows;
    const more = Math.max(0, (r.total || 0) - r.rows.length);
    box.innerHTML = (r.rows.length ? r.rows.map((x, i) => `<button type="button" class="pk-row" role="option" data-pk="${i}">
        <span>${esc(name(x))}</span>${tag(x) ? `<span class="tag">${esc(tag(x))}</span>` : ''}</button>`).join('')
      : `<p class="small muted pk-note">${esc(typed ? sw('pick_none') : sw('pick_empty'))}</p>`)
      + (more ? `<p class="small muted pk-note">${esc(sw('pick_more', { n: more }))}</p>` : '')
      // 2026-10-02 owner ("book launch event" -> "Nothing by that name" and no way on): `onAdd(typed)` - what was typed and
      // is not there yet can be added from the same box, when the caller can make one
      + (onAdd && typed.trim() && !r.rows.some((x) => String(name(x)).toLowerCase() === typed.trim().toLowerCase())
        ? `<button type="button" class="pk-row pk-add" data-pk-add>${icon('plus', 12)} <span>${esc(sw('pick_add', { q: typed.trim() }))}</span></button>` : '');
    box.querySelectorAll('[data-pk]').forEach((b) => { b.onmousedown = (e) => e.preventDefault(); b.onclick = () => choose(st.rows[Number(b.dataset.pk)]); });
    const add = box.querySelector('[data-pk-add]');
    if (add) { add.onmousedown = (e) => e.preventDefault(); add.onclick = () => { shut(); onAdd(typed.trim(), (row) => { if (row) choose(row); }); }; }
    box.hidden = false;
    q.setAttribute('aria-expanded', 'true');
  };
  q.onfocus = () => load();
  q.oninput = () => { clearTimeout(st.timer); st.timer = setTimeout(load, 250); };
  q.onkeydown = (e) => {
    if (e.key === 'Escape' && !box.hidden) { e.stopPropagation(); shut(); }
    if (e.key === 'Enter' && !box.hidden && st.rows.length) { e.preventDefault(); choose(st.rows[0]); }
  };
  q.onblur = () => setTimeout(shut, 150);
  return { value: () => st.chosen };
}

/** pickList's sibling for choosing SEVERAL (2026-10-01 owner: "instead of a list box, a searchable multi dropdown - saves
 *  space"): one box shows the chosen as removable tags; typing or focusing opens a dropdown of tick rows (a heading per
 *  `group`), filtered as you type; Esc / a click away closes it. items = [{id, name, group?}] already on the page;
 *  `groups` = {key: label}; `value` = ids chosen at start; `id` = the input's id, for the field's <label for>. Returns { values() } - the chosen ids, in pick order. */
export function pickMany(host, { items, groups = {}, value = [], placeholder = '', id = '', onChange = () => {} }) {
  const st = { on: new Set(value), order: [...value] };
  const byId = new Map(items.map((x) => [String(x.id), x]));
  host.classList.add('pk-host', 'pm-host');
  host.innerHTML = `<div class="pm-box"><span class="pm-tags"></span><input type="search" class="pk-q pm-q" ${id ? `id="${esc(id)}"` : ''} role="combobox" aria-expanded="false"
      autocomplete="off" placeholder="${esc(placeholder || sw('pick_search'))}" aria-label="${esc(placeholder || sw('pick_search'))}"/>
      <span class="small muted pm-n"></span></div><div class="pk-list" role="listbox" aria-multiselectable="true" hidden></div>`;
  const q = host.querySelector('.pm-q');
  const box = host.querySelector('.pk-list');
  const shut = () => { box.hidden = true; q.setAttribute('aria-expanded', 'false'); };
  const tags = () => {
    host.querySelector('.pm-tags').innerHTML = st.order.filter((id) => byId.has(id)).map((id) => `<span class="pm-tag">${esc(byId.get(id).name)}
      <button type="button" class="pm-x" data-pm-x="${esc(id)}" aria-label="${esc(sw('pick_remove', { name: byId.get(id).name }))}">${icon('close', 11)}</button></span>`).join('');
    host.querySelector('.pm-n').textContent = st.on.size ? sw('pick_chosen', { n: st.on.size }) : '';
    host.querySelectorAll('[data-pm-x]').forEach((b) => { b.onclick = () => flip(b.dataset.pmX); });
  };
  const draw = () => {
    const s = q.value.trim().toLowerCase();
    const all = items.filter((x) => !s || String(x.name || '').toLowerCase().includes(s));
    const most = (ps('shell').pick_many || {}).rows || all.length;   // never every row at once: a page, then type to narrow
    const hit = all.slice(0, most);
    const keys = [...new Set(hit.map((x) => x.group || ''))];
    box.innerHTML = hit.length ? keys.map((g) => `${g && groups[g] ? `<b class="small pk-note pm-head">${esc(groups[g])}</b>` : ''}${hit.filter((x) => (x.group || '') === g)
      .map((x) => `<label class="check small pk-row pm-row"><input type="checkbox" data-pm="${esc(String(x.id))}" ${st.on.has(String(x.id)) ? 'checked' : ''}/><span>${esc(x.name)}</span></label>`).join('')}`).join('')
      : `<p class="small muted pk-note">${esc(sw('pick_none'))}</p>`;
    if (all.length > hit.length) box.innerHTML += `<p class="small muted pk-note">${esc(sw('pick_more', { n: all.length - hit.length }))}</p>`;
    box.querySelectorAll('[data-pm]').forEach((c) => { c.onchange = () => flip(c.dataset.pm, false); });
    box.hidden = false;
    q.setAttribute('aria-expanded', 'true');
  };
  const flip = (id, redraw = true) => {
    if (st.on.has(id)) { st.on.delete(id); st.order = st.order.filter((x) => x !== id); } else { st.on.add(id); st.order.push(id); }
    tags();
    if (redraw && !box.hidden) draw();
    onChange([...st.order]);
  };
  q.onfocus = draw;
  q.oninput = draw;
  q.onkeydown = (e) => {
    if (e.key === 'Escape' && !box.hidden) { e.stopPropagation(); shut(); }
    if (e.key === 'Backspace' && !q.value && st.order.length) flip(st.order[st.order.length - 1]);
  };
  host.addEventListener('focusout', () => setTimeout(() => { if (!host.contains(document.activeElement)) shut(); }, 150));
  host.querySelector('.pm-box').onclick = (e) => { if (!e.target.closest('[data-pm-x]')) q.focus(); };
  tags();
  return { values: () => [...st.order] };
}

const hash = (s) => [...String(s || '')].reduce((h, c) => (Math.imul(h, 31) + c.charCodeAt(0)) >>> 0, 7);
const MOTIF = {
  comic: (n) => `<g fill="none" stroke="#fff" stroke-opacity=".32" stroke-width="3"><rect x="186" y="22" width="58" height="46" rx="4"/><rect x="250" y="22" width="48" height="96" rx="4"/><rect x="186" y="74" width="58" height="44" rx="4"/></g>
    <g fill="#fff" fill-opacity=".14">${Array.from({ length: 36 }, (_, i) => `<circle cx="${196 + (i % 9) * 12}" cy="${132 + Math.floor(i / 9) * 12}" r="${1.2 + ((n >> (i % 8)) & 1) * 1.6}"/>`).join('')}</g>`,
  doodle: (n) => `<path d="M178 ${70 + (n % 18)} C 205 20, 238 120, 262 60 S 300 30, 306 ${90 - (n % 14)}" fill="none" stroke="#fff" stroke-opacity=".4" stroke-width="4" stroke-linecap="round"/>
    <path d="M196 118 q 18 -26 36 0 t 36 0" fill="none" stroke="#fff" stroke-opacity=".25" stroke-width="3" stroke-linecap="round"/>
    <path d="M280 108 l6 14 15 1 -12 9 5 15 -14 -9 -13 9 4 -15 -12 -9 15 -1z" fill="#fff" fill-opacity=".3"/>`,
  film: () => `<g fill="#fff" fill-opacity=".22">${Array.from({ length: 12 }, (_, i) => `<rect x="${8 + i * 26}" y="6" width="14" height="9" rx="2"/><rect x="${8 + i * 26}" y="185" width="14" height="9" rx="2"/>`).join('')}</g>
    <circle cx="258" cy="78" r="34" fill="#fff" fill-opacity=".16"/><path d="M248 60 L276 78 L248 96 Z" fill="#fff" fill-opacity=".55"/>`,
  audiobook: (n) => `<g fill="#fff" fill-opacity=".34">${Array.from({ length: 13 }, (_, i) => { const h = 14 + ((n >> (i % 16)) & 7) * 9 + (i % 3) * 5; return `<rect x="${184 + i * 9}" y="${80 - h / 2}" width="5" height="${h}" rx="2.5"/>`; }).join('')}</g>`,
  tedbook: () => `<g fill="none" stroke="#fff" stroke-opacity=".36" stroke-width="3"><path d="M244 36 C 222 28, 200 30, 186 38 V 124 C 200 116, 222 114, 244 122 Z"/><path d="M244 36 C 266 28, 288 30, 302 38 V 124 C 288 116, 266 114, 244 122 Z"/></g>
    <g stroke="#fff" stroke-opacity=".2" stroke-width="2">${[52, 64, 76, 88, 100].map((y) => `<line x1="196" y1="${y}" x2="234" y2="${y - 3}"/><line x1="254" y1="${y - 3}" x2="292" y2="${y}"/>`).join('')}</g>`,
  avatar: () => `<circle cx="248" cy="62" r="26" fill="#fff" fill-opacity=".3"/><path d="M200 132 C 204 100, 292 100, 296 132 Z" fill="#fff" fill-opacity=".24"/>
    <g fill="#fff" fill-opacity=".4">${[0, 1, 2].map((i) => `<rect x="${226 + i * 16}" y="${144 - (i % 2) * 6}" width="8" height="${10 + (i % 2) * 12}" rx="4"/>`).join('')}</g>`,
  deck: (n) => `<g fill="none" stroke="#fff" stroke-width="3"><rect x="206" y="30" width="96" height="60" rx="6" stroke-opacity=".2"/><rect x="194" y="44" width="96" height="60" rx="6" stroke-opacity=".32"/></g>
    <rect x="182" y="58" width="96" height="60" rx="6" fill="#fff" fill-opacity=".14" stroke="#fff" stroke-opacity=".55" stroke-width="3"/>
    <path d="M196 106 l18 -18 12 12 16 -20 20 26" fill="none" stroke="#fff" stroke-opacity=".55" stroke-width="3" stroke-linejoin="round"/>
    <circle cx="${258 - (n % 14)}" cy="76" r="5" fill="#fff" fill-opacity=".6"/>`,
  assessment: (n) => `<g fill="#fff" fill-opacity=".3">${[0, 1, 2, 3, 4].map((i) => { const h = 24 + ((n >> (i * 3)) & 7) * 11; return `<rect x="${196 + i * 22}" y="${128 - h}" width="14" height="${h}" rx="3"/>`; }).join('')}</g>
    <line x1="188" y1="130" x2="304" y2="130" stroke="#fff" stroke-opacity=".35" stroke-width="2"/>`,
};

/** The words of a title in at most `lines` rows of `chars` letters (the last one ends in … when cut). */
function rows(text, chars, lines) {
  const out = [];
  for (const word of String(text || '').split(/\s+/).filter(Boolean)) {
    const last = out[out.length - 1];
    if (last !== undefined && `${last} ${word}`.length <= chars) out[out.length - 1] = `${last} ${word}`;
    else out.push(word.length > chars ? `${word.slice(0, chars - 1)}…` : word);
  }
  if (out.length > lines) { out.length = lines; out[lines - 1] = `${out[lines - 1].slice(0, chars - 1)}…`; }
  return out;
}

/** x.bare (2026-09-30, Katha face lift): the picture or the drawn motif only - no shade, label or title inside; the card
 *  around it carries the words (a real picture often has its own text, and a title on top of it could not be read). */
/** An asset's cover (2026-09-29): its own picture when it has one (`img`), else colours from its id, its kind's motif
 *  and its title - drawn the same on Katha's cards and every Home card. x = {id, title, kind, label, line, img}; the
 *  palettes, fonts and how a title wraps are chip page.shell `cover`. */
let coverSeq = 0;
export function coverArt(x) {
  const k = ps('shell').cover || {};
  const pal = k.palettes || [['#1e1b4b', '#7c3aed']];
  const n = hash(x.id || x.title);
  const [a, b] = pal[n % pal.length];
  // one id per DRAWING, never per work: the same work on two rails (or in hidden search results first) shared its
  // gradient ids, and a url(#id) that lands in a display:none svg paints nothing - a white card (2026-09-30 Katha)
  coverSeq += 1;
  const id = `kc${n.toString(36)}_${coverSeq}`;
  const lines = rows(x.title, k.title_chars || 18, k.title_lines || 3);
  const size = lines.length > 2 ? (k.title_small || 21) : (k.title_big || 25);
  const y0 = 152 - (lines.length - 1) * size * 1.12;
  const label = String(x.label || '');
  return `<svg class="cover-art" viewBox="0 0 320 200" role="img" aria-label="${esc(x.title)}" xmlns="http://www.w3.org/2000/svg">
    <defs><linearGradient id="${id}g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="${esc(a)}"/><stop offset="1" stop-color="${esc(b)}"/></linearGradient>
      <radialGradient id="${id}r" cx=".85" cy=".15" r=".7"><stop offset="0" stop-color="#fff" stop-opacity=".28"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>
      <linearGradient id="${id}s" x1="0" y1="0" x2="0" y2="1"><stop offset=".4" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".55"/></linearGradient></defs>
    <rect width="320" height="200" fill="url(#${id}g)"/>${x.img
    ? `<image href="${esc(x.img)}" width="320" height="200" preserveAspectRatio="xMidYMid slice"/>`
    : `<rect width="320" height="200" fill="url(#${id}r)"/>${(MOTIF[(k.motif_of || {})[x.kind] || x.kind] || MOTIF[k.motif_default || 'film'])(n)}`}
    ${x.bare ? '' : `<rect width="320" height="200" fill="url(#${id}s)"/>
    ${label ? `<rect x="14" y="14" rx="9" height="18" width="${14 + label.length * 7.4}" fill="#000" fill-opacity=".3"/>
    <text x="21" y="27" fill="#fff" font-family="${esc(k.text_font)}" font-size="10" font-weight="700" letter-spacing="1.2">${esc(label.toUpperCase())}</text>` : ''}
    <text x="18" y="${y0}" fill="#fff" font-family="${esc(k.title_font)}" font-size="${size}" font-weight="700">${lines.map((l, i) => `<tspan x="18" dy="${i ? size * 1.12 : 0}">${esc(l)}</tspan>`).join('')}</text>
    ${x.line ? `<text x="18" y="182" fill="#fff" fill-opacity=".85" font-family="${esc(k.text_font)}" font-size="11.5">${esc(x.line)}</text>` : ''}`}
  </svg>`;
}

export async function assetHome(host, kind, opts) {
  const t = await assetType(kind);
  const w = opts.w;
  const st = { q: '', page: 1, rows: [], total: 0, pages: 1 };
  host.innerHTML = pageHead(w(t.words.title), w(t.words.lede), `
      <button type="button" class="primary" id="as-new">${icon('plus', 14)} ${esc(w(t.words.new))}</button>
      ${(opts.extra || []).map((x, i) => `<button type="button" class="ghost" data-extra="${i}"${x.id ? ` id="${esc(x.id)}"` : ''}>${icon(x.icon || 'plus', 14)} ${esc(x.label)}</button>`).join('')}
      ${t.import ? `<button type="button" class="ghost" id="as-import" title="${esc(w(t.words.import_tip))}">${icon('upload', 14)} ${esc(w(t.words.import))}</button>` : ''}`) + `
    ${opts.lead || ''}
    <section class="card as-home">
      <div class="row tight as-homebar"><h3>${icon(t.icon, 16)} ${esc(w(t.words.mine))} <span class="badge" id="as-total">0</span></h3><span class="grow"></span>
        ${t.deck ? `<button type="button" class="small ghost" id="as-select" title="${esc(sw('as_select_tip'))}">${icon('check', 13)} ${esc(sw('as_select'))}</button>` : ''}
        <input type="search" id="as-q" placeholder="${esc(w(t.words.search))}" aria-label="${esc(w(t.words.search))}"/></div>
      <div id="as-cards" class="as-cards"></div><div class="st-pager" id="as-pager"></div>
      ${t.deck ? `<div class="as-selbar" id="as-selbar" hidden><ol class="as-selorder" id="as-selorder" aria-label="${esc(sw('as_order_tip'))}"></ol>
        <b id="as-selcount"></b><span class="grow"></span>
        ${((ps('shell').deck || {}).formats || []).map((f) => `<button type="button" class="small" data-selfmt="${esc(f)}">${icon('download', 13)} ${esc(sw(`as_deck_${f}`))}</button>`).join('')}
        <button type="button" class="small ghost" data-seltpl title="${esc(sw('as_tpl_change'))}">${icon('image', 13)} <span>${esc(sw('as_tpl'))}</span></button>
        <button type="button" class="small primary" data-selsave>${icon('deck', 13)} ${esc(sw('as_deck_save'))}</button>
        <button type="button" class="small ghost" data-seldone>${icon('close', 13)} ${esc(sw('as_select_done'))}</button></div>` : ''}</section>`;
  // 2026-09-30 owner (Decks): "select multiple cards of the same module and download, or save into another module called
  // Decks" - Select puts a tick on every card (chip assets.types `deck`); ticked works stay ticked across pages, in the
  // order they were ticked; the bar's buttons are never greyed - with nothing ticked they say what to do.
  const picked = new Map();
  let moved = false;
  const home = host.querySelector('.as-home');
  const selbar = host.querySelector('#as-selbar');
  // 2026-09-30 owner: "with multi select there should be a way to rearrange the cards before download" - the ticked works
  // as numbered chips in the bar, in deck order: drag one, or use its arrows (not there at either end), or take it out.
  // The number is on the card's tick too. One strip in the shared Home, so every module that makes decks has it.
  const order = () => {
    const ol = host.querySelector('#as-selorder');
    const ids = [...picked.keys()];
    ol.innerHTML = ids.map((id, i) => `<li draggable="true" data-ord="${esc(id)}" title="${esc(sw('as_order_tip'))}"><b>${i + 1}</b><span>${esc(picked.get(id))}</span>
        ${i ? `<button type="button" class="ghost icon small" data-ordmove="-1" aria-label="${esc(sw('as_move_earlier'))}" data-tip="${esc(sw('as_move_earlier'))}">${icon('left', 12)}</button>` : ''}
        ${i < ids.length - 1 ? `<button type="button" class="ghost icon small" data-ordmove="1" aria-label="${esc(sw('as_move_later'))}" data-tip="${esc(sw('as_move_later'))}">${icon('right', 12)}</button>` : ''}
        <button type="button" class="ghost icon small" data-ordout aria-label="${esc(sw('as_unpick'))}" data-tip="${esc(sw('as_unpick'))}">${icon('close', 12)}</button></li>`).join('');
    const place = (id, at) => {                            // the work `id` to position `at`; the rest keep their order
      const rest = ids.filter((x) => x !== id);
      rest.splice(Math.max(0, Math.min(rest.length, at)), 0, id);
      const names = new Map(picked);
      picked.clear();
      rest.forEach((x) => picked.set(x, names.get(x)));
      moved = true;                                        // the person's own order from here on
      count();
    };
    let dragged = '';
    ol.querySelectorAll('li').forEach((li, i) => {
      const id = li.dataset.ord;
      li.querySelectorAll('[data-ordmove]').forEach((b) => { b.onclick = () => place(id, i + Number(b.dataset.ordmove)); });
      li.querySelector('[data-ordout]').onclick = () => {
        picked.delete(id);
        const cb = host.querySelector(`[data-pick="${CSS.escape(id)}"]`);
        if (cb) { cb.checked = false; cb.closest('.as-card-asset').classList.remove('picked'); }
        count();
      };
      li.ondragstart = (e) => { dragged = id; li.classList.add('dragging'); e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', id); };
      li.ondragend = () => li.classList.remove('dragging');
      li.ondragover = (e) => { e.preventDefault(); };
      li.ondrop = (e) => { e.preventDefault(); if (dragged && dragged !== id) place(dragged, i); };
    });
    host.querySelectorAll('[data-pickn]').forEach((n) => { const at = ids.indexOf(n.dataset.pickn); n.textContent = at < 0 ? '' : String(at + 1); });
  };
  const count = () => { if (selbar) { host.querySelector('#as-selcount').textContent = sw('as_selected', { n: picked.size }); order(); } };
  const pick = (cb) => {
    if (cb.checked) picked.set(cb.dataset.pick, cb.dataset.name); else picked.delete(cb.dataset.pick);
    // 2026-09-30 owner: six chapters ticked from a newest-first Home came out 1 2 3 6 5 4 - "it should have been in
    // sequence". Until a person moves one, the ticked works line up as chip page.shell deck.order says (by name, numbers counted).
    if (!picked.size) moved = false;
    if (!moved && (ps('shell').deck || {}).order === 'name') {
      const byName = [...picked].sort((a, b) => a[1].localeCompare(b[1], undefined, { numeric: true, sensitivity: 'base' }));
      picked.clear();
      byName.forEach(([id, name]) => picked.set(id, name));
    }
    cb.closest('.as-card-asset').classList.toggle('picked', cb.checked);
    count();
  };
  const chosen = () => [...picked.keys()].map((id) => ({ kind: t.id, id }));
  const chosenName = () => (picked.size === 1 ? [...picked.values()][0] : sw('as_select_many', { n: picked.size }));
  let selTheme = '';                                       // the template the bar's downloads and Save to Decks carry ('' = the default)
  if (selbar) {
    const tplBt = selbar.querySelector('[data-seltpl]');
    const showTpl = (id) => { selTheme = id; tplBt.querySelector('span').textContent = sw('as_tpl_now', { name: tplName(id) }); };
    tplBt.onclick = () => deckGallery(selTheme, showTpl);
    host.querySelector('#as-select').onclick = () => {
      const on = !home.classList.contains('selecting'); home.classList.toggle('selecting', on); selbar.hidden = !on; count();
      if (on && !selTheme) deckTemplates().then((d) => showTpl(deckTheme(d))).catch(() => {});
    };
    selbar.querySelectorAll('[data-selfmt]').forEach((b) => { b.onclick = () => (picked.size ? deckDownload(chosen(), b.dataset.selfmt, chosenName(), selTheme) : toast(sw('as_select_first'), 'warn')); });
    const sv = selbar.querySelector('[data-selsave]');
    sv.onclick = () => (picked.size ? deckSave(chosen(), sv, selTheme) : toast(sw('as_select_first'), 'warn'));
    selbar.querySelector('[data-seldone]').onclick = () => { home.classList.remove('selecting'); selbar.hidden = true; };
  }
  const cards = host.querySelector('#as-cards');
  const card = (r) => {
    const s = r.stats || {};
    const f = r.quality;
    return `<div class="as-card-asset${picked.has(r.id) ? ' picked' : ''}">
      ${t.deck ? `<label class="as-pick" title="${esc(sw('as_select_tip'))}"><input type="checkbox" data-pick="${esc(r.id)}" data-name="${esc(r.name)}" ${picked.has(r.id) ? 'checked' : ''}/><b data-pickn="${esc(r.id)}"></b></label>` : ''}
      <button type="button" class="as-cardmain" data-open="${esc(r.id)}">
        ${coverArt({ id: r.id, title: r.name || sw('as_untitled'), kind: t.id, label: w(t.words.one || t.words.title),
    img: r.cover_url ? (r.cover_url.startsWith('/') ? `${BASE}${r.cover_url}` : r.cover_url) : '' })}
        <b>${esc(r.name || sw('as_untitled'))}</b>
        <span class="small muted">${esc(r.source_detail || sw(`as_src_${r.source}`))}</span>
        <span class="as-cardline small">${f ? (f.ok ? `<span class="tag ok">${icon('check', 10)} ${esc(sw('as_status_ok'))}</span>` : `<span class="tag warn">${esc(sw('as_status_todo', { n: f.fail }))}</span>`) : ''}
          <span class="muted">${esc(sw('as_updated_line', { when: String(r.updated || '').slice(0, 10) }))}</span></span>
        <span class="cb-bar"><i style="width:${Number(s.pct) || 0}%"></i></span>
        <span class="small muted">${esc(s.pct === null || s.pct === undefined ? sw('as_card_spent', { spent: usd(s.spent_usd || 0) }) : sw('as_card_stats', { pct: s.pct, spent: usd(s.spent_usd || 0) }))}</span>
      </button>
      <div class="as-cardacts">
        ${publishButton(t, r.id, false)}${deckButton(t, r.id, r.name, false)}<span class="grow"></span>
        <button type="button" class="small ghost" data-act="rename" data-id="${esc(r.id)}" data-name="${esc(r.name)}" title="${esc(sw('as_rename'))}">${icon('edit', 12)}</button>
        <button type="button" class="small ghost" data-act="info" data-id="${esc(r.id)}" title="${esc(sw('as_info'))}">${icon('info', 12)}</button>
        ${(opts.acts || []).map((x, i) => `<button type="button" class="small ghost" data-cardact="${i}" data-id="${esc(r.id)}" title="${esc(x.label)}">${icon(x.icon || 'right', 12)}</button>`).join('')}
        ${(t.makes || []).length ? `<button type="button" class="small ghost" data-act="make" data-id="${esc(r.id)}" data-name="${esc(r.name)}" title="${esc(sw('as_make'))}">${icon('wand', 12)}</button>` : ''}
        ${t.export ? `<a class="small ghost" href="${BASE}${t.export.replace('{id}', encodeURIComponent(r.id))}" title="${esc(sw('as_export'))}">${icon('download', 12)}</a>` : ''}
        <button type="button" class="small ghost danger" data-act="delete" data-id="${esc(r.id)}" data-name="${esc(r.name)}" data-blocked="${esc(r.blocked || '')}" title="${esc(sw('as_delete'))}">${icon('trash', 12)}</button>
      </div></div>`;
  };
  const load = async (append) => {
    const d = await api(`/api/assets/${kind}?${new URLSearchParams({ q: st.q, page: st.page })}`);
    st.rows = append ? st.rows.concat(d.rows) : d.rows; st.total = d.total; st.pages = d.pages;
    host.querySelector('#as-total').textContent = String(st.total);
    cards.innerHTML = st.rows.length ? st.rows.map(card).join('') : st.q ? `<p class="small muted">${esc(sw('as_no_match'))}</p>` : emptyStateOf(t, w);
    const pager = host.querySelector('#as-pager');
    pager.innerHTML = st.page < st.pages ? `<button type="button" class="small ghost" id="as-more">${esc(sw('as_more', { n: st.rows.length, total: st.total }))}</button>` : '';
    const more = pager.querySelector('#as-more');
    if (more) {
      more.onclick = () => { st.page += 1; load(true); };
      // scroll to load (2026-09-23 owner: "not scalable for 1000 books"): the next page joins as the end comes into view
      new IntersectionObserver((es, io) => { if (es.some((e) => e.isIntersecting)) { io.disconnect(); more.click(); } }).observe(more);
    }
    // 2026-09-26 owner: "clicking the card takes time - show an hourglass": the card says Opening at once, the pointer
    // waits, and a second click does nothing until the asset is open (every module's home is this one)
    cards.querySelectorAll('[data-open]').forEach((b) => {
      b.onclick = async () => {
        const card = b.closest('.as-card-asset') || b;
        const tick = home.classList.contains('selecting') && card.querySelector('[data-pick]');
        if (tick) { tick.checked = !tick.checked; pick(tick); return; }        // Select: a press ticks the card, never opens it
        if (card.classList.contains('opening')) return;
        card.classList.add('opening');
        b.setAttribute('aria-busy', 'true');
        b.insertAdjacentHTML('beforeend', `<span class="as-opening">${spinner()} ${esc(sw('as_opening'))}</span>`);
        document.body.classList.add('waiting');
        try { await opts.onOpen(b.dataset.open); } finally {
          document.body.classList.remove('waiting');
          card.classList.remove('opening');
          b.removeAttribute('aria-busy');
          b.querySelector('.as-opening')?.remove();
        }
      };
    });
    cards.querySelectorAll('[data-act]').forEach((b) => {
      const again = () => { st.page = 1; return load(false); };
      b.onclick = () => ({ rename: () => assetRename(t, b.dataset.id, b.dataset.name, again), info: () => assetInfo(kind, b.dataset.id),
        delete: () => assetDelete(t, w, b.dataset.id, b.dataset.name, again, b.dataset.blocked),
        make: () => assetMake(t, b.dataset.id, b.dataset.name) })[b.dataset.act]();
    });
    cards.querySelectorAll('[data-cardact]').forEach((b) => { b.onclick = () => opts.acts[Number(b.dataset.cardact)].run(b.dataset.id); });
    cards.querySelectorAll('[data-pick]').forEach((cb) => { cb.onchange = () => pick(cb); });
    count();                                               // a page just drawn: each ticked card shows its place in the deck
  };
  let timer = 0;
  host.querySelector('#as-q').oninput = (e) => { clearTimeout(timer); timer = setTimeout(() => { st.q = e.target.value.trim(); st.page = 1; load(false); }, 250); };
  host.querySelector('#as-new').onclick = () => (opts.onNew ? opts.onNew() : assetNew(t, w, opts, (id) => opts.onOpen(id)));
  host.querySelectorAll('[data-extra]').forEach((b) => { b.onclick = () => opts.extra[Number(b.dataset.extra)].run(); });
  if (host.querySelector('#as-import')) host.querySelector('#as-import').onclick = () => importPack(w(t.words.import), w(t.words.import_tip), t.import, (got) => opts.onOpen(got.id));
  await load(false);
}

/** 2026-09-28 owner: "browse a Doodle to create a comic book or film ... a TeDBook or audiobook to create any of them".
 *  Make into: the types this one can become (chip assets.types `makes`); the new asset starts from this one's story
 *  (free) and its own screen opens on it. */
async function assetMake(t, id, name) {
  const all = await Promise.all((t.makes || []).map((k) => assetType(k)));
  modal(sw('as_make_title', { name: name || sw('as_untitled') }), `<p class="small muted">${esc(sw('as_make_body'))}</p>
    <div class="row wrap">${all.map((x) => `<button type="button" class="pill" data-to="${esc(x.id)}">${icon(x.icon, 14)} ${esc(sw(`as_t_${x.id}`))}</button>`).join('')}</div>`, {
    onOpen: (body, close) => body.querySelectorAll('[data-to]').forEach((b) => {
      b.onclick = () => busy(b, async () => {
        const got = await api(`/api/assets/${t.id}/${encodeURIComponent(id)}/make`, { method: 'POST', body: { to: b.dataset.to } });
        close();
        toast(sw('as_made'));
        keep(got.keep, got.id);
        location.hash = `#/${got.screen}`;
      });
    }) });
}

function emptyStateOf(t, w) {
  return `<div class="as-empty">${icon(t.icon, 30)}<b>${esc(w(t.words.empty_title))}</b><p class="small muted">${esc(w(t.words.empty_body))}</p></div>`;
}

/** Publish & Circles for one asset (2026-09-30 owner: on every module's card and file bar): chip assets.types `publish` =
 *  the Katha kind it publishes as; the press opens that screen (chip page.shell publish_screen) with the asset chosen. */
function publishButton(t, id, label) {
  return t.publish ? `<button type="button" class="small ghost" data-pub="${esc(t.publish)}:${esc(id)}" title="${esc(sw('as_publish'))}">${icon('upload', 12)}${label ? ` ${esc(sw('as_publish'))}` : ''}</button>` : '';
}
document.addEventListener('click', (e) => {
  const b = e.target.closest && e.target.closest('[data-pub]');
  if (!b) return;
  e.preventDefault();
  e.stopImmediatePropagation();
  keep('publish.pick', b.dataset.pub);
  location.hash = `#/${ps('shell').publish_screen}`;
}, true);

/** PDF & PowerPoint for one work (2026-09-30 owner: "convert Comic, Doodle and Avatar as pdf and power point deck ... from
 *  inside (the file bar of an open asset), individually on a card at the home screen of each module"): chip assets.types
 *  `deck`; beside Publish & Circles on the card, right after it in the file bar. Routes + screen: chip page.shell deck. */
function deckButton(t, id, name, label) {
  return t.deck ? `<button type="button" class="small ghost" data-deck="${esc(t.id)}:${esc(id)}" data-name="${esc(name || '')}" title="${esc(sw('as_deck_tip'))}">${icon('deck', 12)}${label ? ` ${esc(sw('as_deck'))}` : ''}</button>` : '';
}
document.addEventListener('click', (e) => {
  const b = e.target.closest && e.target.closest('[data-deck]');
  if (!b) return;
  e.preventDefault();
  e.stopImmediatePropagation();
  const [kind, id] = b.dataset.deck.split(':');
  deckDialog([{ kind, id }], b.dataset.name);
}, true);

/** The deck templates (2026-09-30 owner: "give 10 various templates ... preview the template before selecting"): asked
 *  once - each one's REAL cover and content-slide drawing with sample words on it, made by the server from chip
 *  deck.layout. No drawing, colour or template name is written here; names are the words chip page.shell deck names. */
let DECK_TPL = null;
export async function deckTemplates(cfg = ps('shell').deck || {}) {
  // `fresh` (another module's templates, drawn for ONE record - an Avatar Video's own presenter): asked each time, never kept
  if (cfg.fresh) { await loadWords(cfg.words); return api(`${cfg.api}/templates`); }
  if (!DECK_TPL) { await loadWords(cfg.words); DECK_TPL = await api(`${cfg.api}/templates`); }
  return DECK_TPL;
}
const tplWord = (id, tail = '', cfg = ps('shell').deck || {}) => t(cfg.words, `${cfg.word_prefix || 'theme_'}${id}${tail}`);
/** Every template this person may use: their own first, then the built-in ones. */
const tplAll = (d) => [...(d.mine || []), ...d.templates];
const tplOf = (id) => (DECK_TPL ? tplAll(DECK_TPL).find((x) => x.id === id) : null);
/** A template's name: a person's own is what they called it; a built-in one's is a word (chip page.shell deck words). */
const tplName = (id) => { const x = tplOf(id); return x && x.name ? x.name : tplWord(id); };
/** The template this person chose last (kept per person) while it still exists, else the portal's default. */
const deckTheme = (d) => { const k = kept((ps('shell').deck || {}).theme_keep, ''); return tplAll(d).some((x) => x.id === k) ? k : d.default; };
/** The button that shows the template in use (its real cover, its name) and opens the gallery. */
export const deckTemplateButton = (d, id, cfg) => { const x = tplAll(d).find((r) => r.id === id) || d.templates[0]; return `<button type="button" class="tpl-now" data-tpl-open title="${esc(sw('as_tpl_change'))}">
    <span class="tpl-art">${x.tile_svg || x.cover_svg}</span><span class="tpl-nowtxt"><span class="small muted">${esc(sw('as_tpl'))}</span><b>${esc(x.name || tplWord(x.id, '', cfg))}</b>
      <span class="small">${icon('edit', 12)} ${esc(sw('as_tpl_change'))}</span></span></button>`; };

/** The ONE template gallery, wherever a deck is made (a card, a file bar, the Select bar, the Decks editor): My templates
 *  (a person's own - 2026-09-30 owner: "allow user to upload their own template ... keep branding and their logo intact";
 *  Upload is the portal's one uploadBox) above the ready-made ones; pressing one shows it large - its title slide and a
 *  content slide - with Use this template; their own can be renamed, given its pictures, and deleted (never while a deck
 *  uses it). Esc and the X close it; the choice is kept for this person. onPick(id); onCancel() when nothing was chosen. */
export async function deckGallery(current, onPick, onCancel = () => {}, cfg = ps('shell').deck || {}) {
  let d = await deckTemplates(cfg);
  // this gallery's own set (Decks - or another module's templates, through templateGallery): rows from `d`, names from `cfg`
  const tplOf = (id) => tplAll(d).find((x) => x.id === id);
  const tplWord = (id, tail = '') => t(cfg.words, `${cfg.word_prefix || 'theme_'}${id}${tail}`);
  const tplName = (id) => { const x = tplOf(id); return x && x.name ? x.name : tplWord(id); };
  let used = false;
  modal(sw('as_tpl_title'), '<div class="tpl"></div>', { wide: true, cls: 'tpl-modal', onClose: () => { if (!used) onCancel(); },
    footer: `<button type="button" class="ghost" data-tpl-cancel>${esc(sw('as_tpl_cancel'))}</button>
      <button type="button" class="ghost" data-tpl-back hidden>${icon('left', 13)} ${esc(sw('as_tpl_back'))}</button>
      <button type="button" class="primary" data-tpl-use hidden>${icon('check', 14)} ${esc(sw('as_tpl_use'))}</button>`,
    onOpen: (body, close) => {
      const box = body.querySelector('.tpl');
      const foot = body.closest('.modal');
      const [back, use] = [foot.querySelector('[data-tpl-back]'), foot.querySelector('[data-tpl-use]')];
      const warn = (text) => modal(sw('as_tpl_cannot_delete'), `<p class="confirm-msg">${esc(text)}</p>`, { cls: 'confirm tone-warn', eyebrow: sw('please_confirm') });
      const tile = (x) => `<button type="button" class="tpl-tile${x.id === current ? ' on' : ''}" data-tpl="${esc(x.id)}" aria-pressed="${x.id === current}">
          <span class="tpl-art">${x.tile_svg || x.cover_svg}</span><b>${esc(tplName(x.id))}${x.id === current ? ` <span class="tag ok">${esc(sw('as_tpl_current'))}</span>` : ''}</b>
          ${x.name ? '' : `<span class="small muted">${esc(tplWord(x.id, '_line'))}</span>`}</button>`;
      // after an upload, a rename, a picture or a delete: the templates are asked again (the previews are the server's)
      const again = async (open = '') => { DECK_TPL = null; d = await deckTemplates(cfg); if (open && tplOf(open)) one(open); else grid(); };
      const grid = () => {
        back.hidden = true; use.hidden = true;
        // My templates + Upload only where the server offers uploads (`d.upload`); the opening line may be the module's own word
        box.innerHTML = `<p class="small muted">${esc(cfg.lede_word ? t(cfg.words, cfg.lede_word) : sw('as_tpl_lede'))}</p>
          ${d.upload ? `<h3 class="tpl-group">${esc(sw('as_tpl_mine'))}</h3><div class="tpl-grid">${(d.mine || []).map(tile).join('')}
            <button type="button" class="tpl-tile tpl-up" data-tpl-up>${icon('upload', 22)}<b>${esc(sw('as_tpl_upload'))}</b><span class="small muted">${esc(sw('as_tpl_upload_hint'))}</span></button></div>
          <h3 class="tpl-group">${esc(sw('as_tpl_builtin'))}</h3>` : ''}<div class="tpl-grid">${d.templates.map(tile).join('')}</div>`;
        box.querySelectorAll('[data-tpl]').forEach((b) => { b.onclick = () => one(b.dataset.tpl); });
        if (d.upload) box.querySelector('[data-tpl-up]').onclick = () => uploadBox(sw('as_tpl_upload'), d.upload.extensions, `${cfg.api}/templates`, () => again());
      };
      const one = (id) => {
        const x = tplOf(id);
        const at = `${cfg.api}/templates/${encodeURIComponent(id)}`;
        back.hidden = false; use.hidden = false;
        box.innerHTML = `<h3 class="tpl-name">${esc(tplName(x.id))}</h3>${x.name ? `<div class="tpl-tools">
            <input data-tpl-name value="${esc(x.name)}" aria-label="${esc(sw('as_tpl_rename_label'))}"/>
            <button type="button" class="small" data-tpl-rename>${icon('edit', 12)} ${esc(sw('as_tpl_rename'))}</button>
            ${(x.slots || []).map((sl) => `<button type="button" class="small ghost" data-tpl-slot="${esc(sl)}">${icon('image', 12)} ${esc(sw(`as_tpl_add_${sl}`))}</button>`).join('')}
            <button type="button" class="small ghost danger" data-tpl-del>${icon('trash', 12)} ${esc(sw('as_tpl_delete'))}</button></div>`
    : `<p class="small muted">${esc(tplWord(x.id, '_line'))}</p>`}
          ${(x.notes || []).map((n) => `<p class="small muted tpl-note">${icon('info', 12)} ${esc(n)}</p>`).join('')}
          <div class="tpl-pair"><figure><div class="tpl-art">${x.cover_svg}</div><figcaption class="small muted">${esc(cfg.pair_words ? t(cfg.words, cfg.pair_words[0]) : sw('as_tpl_cover'))}</figcaption></figure>
            <figure><div class="tpl-art">${x.scene_svg}</div><figcaption class="small muted">${esc(cfg.pair_words ? t(cfg.words, cfg.pair_words[1]) : sw('as_tpl_scene'))}</figcaption></figure></div>`;
        use.onclick = () => { used = true; if (cfg.theme_keep) keep(cfg.theme_keep, id); close(); onPick(id); };
        use.focus();
        if (!x.name) return;
        const rn = box.querySelector('[data-tpl-rename]');
        rn.onclick = () => busy(rn, async () => {
          try { await api(at, { method: 'PUT', body: { name: box.querySelector('[data-tpl-name]').value } }); await again(id); } catch (err) { toast(err.message, 'bad'); }
        });
        box.querySelectorAll('[data-tpl-slot]').forEach((b) => {
          b.onclick = () => uploadBox(sw(`as_tpl_add_${b.dataset.tplSlot}`), d.upload.backgrounds.includes(b.dataset.tplSlot) ? d.upload.pictures : d.upload.logos,
            `${at}/picture/${b.dataset.tplSlot}`, () => again(id));
        });
        // in use = never deleted: said before asking (the server refuses it too, naming the decks)
        box.querySelector('[data-tpl-del]').onclick = () => (x.in_use.length ? warn(sw('as_tpl_in_use', { decks: x.in_use.join(', ') }))
          : confirmDialog(sw('as_tpl_delete_title'), sw('as_tpl_delete_body', { name: x.name }), async () => {
            try { toast((await api(at, { method: 'DELETE' })).message, 'ok'); await again(); } catch (err) { warn(err.message); }
          }, sw('as_tpl_delete'), { tone: 'danger' }));
      };
      back.onclick = grid;
      foot.querySelector('[data-tpl-cancel]').onclick = () => close();
      grid();
    } });
}

/** The same ONE gallery for another module's templates (2026-09-30 Avatar Videos, chip avatar.templates): `cfg` is a chip's
 *  record {api, words, word_prefix, lede_word, pair_words, fresh} (chip page.<screen> / assets.types `templates`) - the
 *  server answers GET <api>/templates in the Decks gallery's shape. Never a second gallery, never a list of its own. */
export const templateGallery = (cfg, current, onPick, onCancel = () => {}) => deckGallery(current, onPick, onCancel, cfg);
export const templateButton = (cfg, d, id) => deckTemplateButton(d, id, cfg);

/** The deck choices for one or more works: the template (the gallery), then Download PDF / PowerPoint (made now, not
 *  kept) or Save to Decks - each carries the template chosen. */
export async function deckDialog(items, name, theme = '') {
  if (!items.length) { toast(sw('as_select_first'), 'warn'); return; }
  const cfg = ps('shell').deck || {};
  const d = await deckTemplates();
  const th = theme || deckTheme(d);
  modal(sw('as_deck_title', { name: name || sw('as_untitled') }), `<p class="small muted">${esc(sw('as_deck_body'))}</p>${deckTemplateButton(d, th)}
    <div class="row wrap as-deckgo">${(cfg.formats || []).map((f) => `<button type="button" class="pill" data-fmt="${esc(f)}">${icon('download', 14)} ${esc(sw(`as_deck_${f}`))}</button>`).join('')}
      <button type="button" class="pill" data-save>${icon('deck', 14)} ${esc(sw('as_deck_save'))}</button></div>`, {
    onOpen: (body, close) => {
      body.querySelector('[data-tpl-open]').onclick = () => { close(); deckGallery(th, (id) => deckDialog(items, name, id), () => deckDialog(items, name, th)); };
      body.querySelectorAll('[data-fmt]').forEach((b) => { b.onclick = () => { close(); deckDownload(items, b.dataset.fmt, name, th); }; });
      const sv = body.querySelector('[data-save]');
      sv.onclick = () => deckSave(items, sv, th, close);
    } });
}

/** A one-off deck file in the chosen template, through the portal's one download window (every /api link is followed). */
export function deckDownload(items, fmt, name, theme = '') {
  const a = document.createElement('a');
  a.href = `${BASE}${(ps('shell').deck || {}).api}/export?${new URLSearchParams({ items: items.map((x) => `${x.kind}:${x.id}`).join(','), format: fmt, theme })}`;
  a.textContent = `${name || sw('as_untitled')} · ${sw(`as_deck_${fmt}`)}`;
  a.hidden = true;
  document.body.appendChild(a);
  a.click();
  a.remove();
}

/** Save to Decks: a new deck of these works in the chosen template (its files are made in the background); the Decks
 *  screen opens on it. */
export function deckSave(items, button, theme = '', done = () => {}) {
  const cfg = ps('shell').deck || {};
  return busy(button, async () => {
    try {
      const got = await api(cfg.api, { method: 'POST', body: { items, theme } });
      done();
      toast(got.message, 'ok', 6);
      keep(got.keep, got.id);
      location.hash = `#/${got.screen}`;
    } catch (err) { toast(err.message, 'bad', 8); }
  });
}

/** The file bar on top of an open asset - the same on every screen: Home, the name, Rename, Info, Export, Delete, Publish. */
export async function assetBar(kind, id, name, { w, onHome, onRenamed, extra = '', blocked = '' }) {
  const t = await assetType(kind);
  const html = `<div class="as-filebar">
      <button type="button" class="small ghost" data-fb="home">${icon('left', 13)} ${esc(sw('as_home'))}</button>
      <span class="as-filename">${icon(t.icon, 14)} <b>${esc(name)}</b></span><span class="grow"></span>${extra}
      <button type="button" class="small ghost" data-fb="rename">${icon('edit', 12)} ${esc(sw('as_rename'))}</button>
      <button type="button" class="small ghost" data-fb="info">${icon('info', 12)} ${esc(sw('as_info'))}</button>
      ${t.export ? `<a class="small ghost" href="${BASE}${t.export.replace('{id}', encodeURIComponent(id))}">${icon('download', 12)} ${esc(sw('as_export'))}</a>` : ''}
      <button type="button" class="small ghost danger" data-fb="delete">${icon('trash', 12)} ${esc(sw('as_delete'))}</button>
      ${publishButton(t, id, true)}${deckButton(t, id, name, true)}</div>`;
  const wire = (root) => {
    root.querySelectorAll('[data-fb]').forEach((b) => {
      b.onclick = () => ({ home: onHome, rename: () => assetRename(t, id, name, onRenamed), info: () => assetInfo(kind, id),
        delete: () => assetDelete(t, w, id, name, onHome, blocked) })[b.dataset.fb]();
    });
  };
  return { html, wire };
}

// Every same-origin link into /api/ is a download (a package, a pack, a file). It is fetched here so the work window can
// say what is happening: first the server BUILDING it (timed from this person's last run of the same kind), then the
// bytes arriving (%, speed, time left). A quick one never opens the window at all.
const mb = (n) => (n / 1048576).toFixed(n > 10485760 ? 0 : 1);
async function fetchDownload(a) {
  const url = new URL(a.href, location.href);
  const what = (a.textContent || '').trim() || url.pathname.split('/').pop();
  const key = `ww.dl.${url.pathname.replace(/\/[0-9a-f-]{6,}(?=\/|$)/gi, '/*')}`;
  const learned = Number(kept(key, '')) || null;
  const t0 = Date.now();
  let win = null;
  const show = setTimeout(() => {
    win = workWindow(sw('dl_title', { what }), { activity: sw('dl_building', { what }), note: sw('dl_note') });
    win.set({ started_ms: t0, total_s: learned, basis: learned ? sw('dl_basis', { t: clk(learned) }) : sw('dl_first') });
  }, wk('download_show_ms'));
  try {
    const r = await fetch(url, { credentials: 'same-origin' });
    if (!r.ok) {
      if (r.status === 401) hooks.unauthorized();
      let msg = `${r.status} ${r.statusText}`;
      try { const d = await r.json(); msg = (d.detail && (d.detail.message || d.detail)) || msg; } catch { /* not JSON */ }
      throw new Error(String(msg));
    }
    const cd = r.headers.get('Content-Disposition') || '';
    const m = /filename\*=UTF-8''([^;]+)/i.exec(cd) || /filename="?([^";]+)"?/i.exec(cd);
    const name = (m && decodeURIComponent(m[1])) || a.getAttribute('download') || decodeURIComponent(url.pathname.split('/').pop());
    const size = Number(r.headers.get('Content-Length')) || 0;
    const parts = [];
    let got = 0;
    const t1 = Date.now();
    if (r.body && r.body.getReader) {
      const rd = r.body.getReader();
      for (;;) {
        const { done, value } = await rd.read();
        if (done) break;
        parts.push(value);
        got += value.length;
        if (win) {
          const secs = (Date.now() - t1) / 1000;
          const rate = secs > wk('rate_after_s') ? got / secs : 0;
          win.set({ activity: sw('dl_downloading', { name }), pct: size ? (100 * got) / size : null,
            total_s: size && rate ? (Date.now() - t0) / 1000 + (size - got) / rate : null,
            sub: size ? sw('dl_size', { got: mb(got), size: mb(size) }) : sw('dl_got', { got: mb(got) }), basis: rate ? sw('dl_rate', { mb: mb(rate) }) : '' });
        }
      }
    } else parts.push(new Uint8Array(await r.arrayBuffer()));
    const link = document.createElement('a');
    link.href = URL.createObjectURL(new Blob(parts, { type: r.headers.get('Content-Type') || 'application/octet-stream' }));
    link.download = name;
    document.body.appendChild(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(link.href), 60000);
    keep(key, String(Math.max(1, Math.round((t1 - t0) / 1000))));   // next time: the server's build time of this kind
    clearTimeout(show);
    if (win) { win.end('finished', sw('dl_saved', { name })); setTimeout(() => win.isOpen && win.close(), wk('close_done_ms')); }
    a.dispatchEvent(new CustomEvent('downloaded', { bubbles: true, detail: { name, bytes: got } }));
  } catch (err) {
    clearTimeout(show);
    if (win) win.end('failed', err.message); else toast(err.message, 'bad', 8);
  }
}
document.addEventListener('click', (e) => {
  if (e.defaultPrevented || e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
  const a = e.target.closest && e.target.closest('a[href]');
  if (!a || a.target || a.hasAttribute('data-plain')) return;
  const u = new URL(a.href, location.href);
  if (u.origin !== location.origin || !u.pathname.startsWith(`${new URL(BASE, location.href).pathname.replace(/\/$/, '')}/api/`)) return;
  e.preventDefault();
  fetchDownload(a);
});

// --- light or dark ---------------------------------------------------------------------------------
// Until someone chooses, the portal follows what this machine prefers. One click always flips what
// you SEE: light to dark, dark to light. (2026-09-17: it cycled system → light → dark, so on a light
// machine the first click changed nothing visible and dark mode took two clicks.)
// Kept in this browser, because it is a preference about this screen and nobody else's.

function storedTheme() {
  try { return localStorage.getItem('portal.theme') || localStorage.getItem('tv.theme') || 'system'; } catch { return 'system'; }
}

/** 'light' or 'dark' — what is on screen right now, whether chosen or inherited from the machine. */
export function shownTheme() {
  const t = storedTheme();
  if (t === 'light' || t === 'dark') return t;
  return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export function applyTheme() {
  const t = storedTheme();
  if (t === 'light' || t === 'dark') document.documentElement.setAttribute('data-theme', t);
  else document.documentElement.removeAttribute('data-theme');
  return shownTheme();
}

export function nextTheme() {
  const next = shownTheme() === 'dark' ? 'light' : 'dark';
  try { localStorage.setItem('portal.theme', next); } catch { /* not remembered, but still switched */ }
  document.documentElement.setAttribute('data-theme', next);
  return next;
}

// --- one text box with a line asked of the person (the editor's link and video addresses) ----------------------------
/** A small dialog that asks for one line of text; `done(value)` gets it (nothing when empty or cancelled). */
// 2026-10-02 owner (the "What should it say?" box): "Tab should make the grey to black". In ANY empty box whose grey
// example starts with the shell word eg_prefix ("e.g. "), or that names its own data-suggest, Tab puts that example in as
// real text - one listener for every page; a box with no example keeps Tab as moving on.
document.addEventListener('keydown', (e) => {
  const el = e.target;
  if (e.key !== 'Tab' || e.shiftKey || !el || !/^(INPUT|TEXTAREA)$/.test(el.tagName) || el.value) return;
  const pre = sw('eg_prefix');
  const ph = el.getAttribute('placeholder') || '';
  const got = el.dataset.suggest || (pre && ph.startsWith(pre) ? ph.slice(pre.length) : '');
  if (!got) return;
  e.preventDefault();
  el.value = got;
  el.dispatchEvent(new Event('input', { bubbles: true }));
}, true);

export function askText(title, label, okWord, done, placeholder = '') {
  modal(title, `<div class="field"><label for="ask-text">${esc(label)}</label><input id="ask-text" placeholder="${esc(placeholder)}"/></div>
    <div class="row end"><button class="primary" id="ask-ok" type="button">${esc(okWord)}</button></div>`,
  { onOpen: (b, close) => {
    const inp = b.querySelector('#ask-text');
    const go = () => { const v = inp.value.trim(); close(); if (v) done(v); };
    b.querySelector('#ask-ok').onclick = go;
    inp.onkeydown = (e) => { if (e.key === 'Enter') { e.preventDefault(); go(); } };
    inp.focus();
  } });
}

// --- the rich-text editor (2026-10-02 owner: Articles + Books from AstroStage's Study Article "with Rich Text Format
// control"). ONE editor for every screen that writes rich text: its buttons, colours, table size, the video address it
// takes and what a paste keeps are chip page.shell `rich`; its words are ui.shell rt_*. What it holds is cleaned AGAIN
// on the server on every save (chip rich.allow_list) - the browser's cleaning is only a courtesy.
// ponytail: document.execCommand is deprecated but every browser still runs it; a model-based editor when it is gone.
/** richEditor(host, {html, upload(file) -> src, onChange(html), onSave(), skip: [toolbar `do`s a screen leaves out]}) -> {html(), set(html)} */
export function richEditor(host, { html = '', upload = null, onChange = () => {}, onSave = () => {}, skip = [] } = {}) {
  const k = ps('shell').rich || {};
  const bar = (k.toolbar || []).map((b, i) => (skip.includes(b.do) ? '' : (b.do === 'sep' ? '<span class="rt-sep" aria-hidden="true"></span>'
    : b.do === 'colour' ? `<select class="rt-colour" data-rt="${i}" aria-label="${esc(sw(b.tip))}" title="${esc(sw(b.tip))}">${(k.colours || [])
      .map((c) => `<option value="${esc(c.value)}">${esc(sw(c.word))}</option>`).join('')}</select>`
    : `<button type="button" class="rt-b" data-rt="${i}" title="${esc(sw(b.tip))}" aria-label="${esc(sw(b.tip))}">${b.icon ? icon(b.icon, 14) : esc(sw(b.label))}</button>`))).join('');
  host.innerHTML = `<div class="rt"><div class="rt-bar" role="toolbar" aria-label="${esc(sw('rt_toolbar'))}">${bar}</div>
    <div class="rt-body" contenteditable="true" role="textbox" aria-multiline="true" aria-label="${esc(sw('rt_body'))}"></div>
    <textarea class="rt-src" hidden aria-label="${esc(sw('rt_source_box'))}"></textarea></div>`;
  const body = host.querySelector('.rt-body');
  const src = host.querySelector('.rt-src');
  body.innerHTML = html;
  let range = null;
  const keep = () => { const s = getSelection(); if (s.rangeCount && body.contains(s.anchorNode)) range = s.getRangeAt(0).cloneRange(); };
  const back = () => { body.focus(); if (range) { const s = getSelection(); s.removeAllRanges(); s.addRange(range); } };
  const changed = () => onChange(body.innerHTML);
  const put = (h) => { back(); document.execCommand('insertHTML', false, h); changed(); };
  const cell = () => { const n = getSelection().anchorNode; const el = n && (n.nodeType === 1 ? n : n.parentElement); return el && body.contains(el) ? el.closest('td,th') : null; };
  const inTable = (fn) => { const c = cell(); if (!c) { toast(sw('rt_need_table'), 'info'); return; } fn(c, c.parentElement, [...c.parentElement.children].indexOf(c)); changed(); };
  const ACTIONS = {
    exec: (b) => { back(); document.execCommand(b.arg, false, null); changed(); },
    block: (b) => { back(); document.execCommand('formatBlock', false, b.arg); changed(); },
    link: () => { keep(); if (!range || range.collapsed) { toast(sw('rt_need_text'), 'info'); return; }
      askText(sw('rt_link_title'), sw('rt_link_label'), sw('rt_ok'), (url) => { back(); document.execCommand('createLink', false, url); changed(); }, 'https://'); },
    image: () => { keep(); if (!upload) return;   // the ONE file box (dropZone: browse, drop, paste), never a raw input
      modal(sw('rt_tip_image'), dropZone('rt-file', { accept: 'image/*', title: sw('rt_tip_image') }), { onOpen: (m, close) => wireDrops(m, async (f) => {
        if (!f) return;
        try { const got = await upload(f); close(); put(`<img src="${esc(got)}" alt="">`); } catch (e) { toast(e.message, 'bad'); }
      }) }); },
    youtube: () => { keep(); askText(sw('rt_video_title'), sw('rt_video_label'), sw('rt_ok'), (url) => {
      const m = url.match(new RegExp(k.youtube || '$^'));
      if (!m) { toast(sw('rt_bad_video'), 'bad'); return; }
      put(`<p><iframe src="${esc(String(k.youtube_embed || '').replace('{id}', m[1]))}" allowfullscreen loading="lazy" width="${Number(k.video_w) || ''}" height="${Number(k.video_h) || ''}"></iframe></p>`);
    }); },
    table: () => { const t = k.table || {}; const row = (tag) => `<tr>${`<${tag}><br></${tag}>`.repeat(t.cols || 1)}</tr>`;
      put(`<table><thead>${row('th')}</thead><tbody>${row('td').repeat(Math.max((t.rows || 1) - 1, 1))}</tbody></table><p><br></p>`); },
    row: () => inTable((c, tr) => { const n = tr.cloneNode(true); n.querySelectorAll('th,td').forEach((x) => { x.innerHTML = '<br>'; }); tr.after(n); }),
    col: () => inTable((c, tr, i) => c.closest('table').querySelectorAll('tr').forEach((r) => { const x = r.children[i]; if (x) { const n = x.cloneNode(false); n.innerHTML = '<br>'; x.after(n); } })),
    unrow: () => inTable((c, tr) => tr.remove()),
    uncol: () => inTable((c, tr, i) => c.closest('table').querySelectorAll('tr').forEach((r) => { if (r.children[i]) r.children[i].remove(); })),
    source: () => { const showing = !src.hidden;
      if (showing) { body.innerHTML = src.value; changed(); } else { src.value = body.innerHTML; }
      src.hidden = showing; body.hidden = !showing; },
  };
  host.querySelectorAll('.rt-b').forEach((btn) => {
    btn.onmousedown = (e) => { e.preventDefault(); keep(); };      // the selection stays where the person put it
    btn.onclick = () => { const b = k.toolbar[Number(btn.dataset.rt)]; (ACTIONS[b.do] || (() => {}))(b); };
  });
  host.querySelectorAll('.rt-colour').forEach((sel) => {
    sel.onmousedown = keep;
    sel.onchange = () => { back(); document.execCommand(sel.value ? 'foreColor' : 'removeFormat', false, sel.value || null); sel.value = ''; changed(); };
  });
  body.addEventListener('input', changed);
  src.addEventListener('input', () => onChange(src.value));
  body.addEventListener('keyup', keep);
  body.addEventListener('mouseup', keep);
  host.addEventListener('keydown', (e) => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') { e.preventDefault(); onSave(); } });
  // a paste keeps only chip page.shell rich paste_tags / paste_attrs (the server cleans again on save)
  body.addEventListener('paste', (e) => {
    const h = e.clipboardData && e.clipboardData.getData('text/html');
    e.preventDefault();
    if (!h) { document.execCommand('insertText', false, e.clipboardData.getData('text/plain')); changed(); return; }
    const doc = new DOMParser().parseFromString(h, 'text/html');
    const tags = new Set(k.paste_tags || []), attrs = new Set(k.paste_attrs || []);
    [...doc.body.querySelectorAll('*')].reverse().forEach((el) => {
      if (!tags.has(el.tagName.toLowerCase())) { el.replaceWith(...el.childNodes); return; }
      [...el.attributes].forEach((a) => { if (!attrs.has(a.name)) el.removeAttribute(a.name); });
    });
    document.execCommand('insertHTML', false, doc.body.innerHTML);
    changed();
  });
  // set() counts as an edit (the page saves it); focus() puts the caret in the text - pages never reach into the editor
  return { html: () => (src.hidden ? body.innerHTML : src.value), set: (h) => { body.innerHTML = h; src.value = h; changed(); }, focus: () => body.focus() };
}

/** 2026-10-02 owner: "have a handle to rearrange easily" - the ONE drag-to-reorder: every child of `list` with a
 *  `[data-grip]` handle and a `data-id`; drag the handle above / below another row (Alt+Up / Alt+Down on the focused
 *  handle does the same); `onDone(ids)` gets the new order once, when the drag ends and only if it changed. */
export function dragRows(list, onDone) {
  const ids = () => [...list.children].map((r) => r.dataset.id);
  let dragged = null;
  let before = '';
  const done = () => { const now = ids(); if (now.join() !== before) onDone(now); };
  [...list.children].forEach((row) => {
    const grip = row.querySelector('[data-grip]');
    if (!grip) return;
    grip.draggable = true;
    grip.ondragstart = (e) => { dragged = row; before = ids().join(); row.classList.add('dragging'); e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', row.dataset.id); e.dataTransfer.setDragImage(row, 20, 20); };
    grip.ondragend = () => { row.classList.remove('dragging'); dragged = null; done(); };
    grip.onkeydown = (e) => {
      if (!e.altKey || !['ArrowUp', 'ArrowDown'].includes(e.key)) return;
      e.preventDefault();
      before = ids().join();
      const to = e.key === 'ArrowUp' ? row.previousElementSibling : row.nextElementSibling;
      if (!to) return;
      if (e.key === 'ArrowUp') to.before(row); else to.after(row);
      grip.focus();
      done();
    };
    row.ondragover = (e) => {
      if (!dragged || dragged === row) return;
      e.preventDefault();
      const r = row.getBoundingClientRect();
      if (e.clientY < r.top + r.height / 2) row.before(dragged); else row.after(dragged);
    };
  });
}
