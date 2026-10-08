// The bottom bar - the studio's PortalDock + DockTools, ported one to one (2026-10-04 owner: "What it takes to just bring
// entire thing from the studio to SimplyFile"). On every screen, signed in: Chip Chat, Screen capture, Screen recording,
// Voice typing, Notes, Issues. Opens sideways (a row) or upwards (a column); folded, it keeps the Chip Chat mark with the
// arrows to open it again - the choice is remembered per browser. Refresh, theme, Guide me and search stay in the top bar
// (SimplyFile has them there); the studio's portal switcher and time zone are left out (owner).
//   Screen capture   - the screen is taken, drag over the part to keep (or Whole screen). NOTHING is kept by itself:
//                      Copy / Download / Add to a note / Report as an issue / Discard.
//   Screen recording - the screen with the microphone until stopped, then shown: Download or Discard.
//   Voice typing     - what is spoken is typed into the text box the cursor is in; a caption shows it listening, and
//                      words spoken before a box is chosen go into the next box clicked.
//   Notes / Issues   - notes-modal.js, issues-modal.js. Issues' badge = own issues answered and not opened yet.
// Settings: chip page.dock (the studio's ui.dock_tools). Words: chip ui.dock (the studio's ui.dock_words, word for word).
import { api, esc, toast, t, ps, loadWords, modal, confirmDialog, keep, kept } from './app.js';
import { icon, chipChatGlyph } from './icons.js';

export const w = (k, v) => t('dock', k.replace(/[.-]/g, '_'), v);
export const K = () => ps('dock');

const TEXT_INPUTS = new Set(['', 'text', 'search', 'url', 'tel']);
/** A box a person can type words into: a text input, a textarea, or a rich-text area. */
export function isEditable(el) {
  if (el instanceof HTMLTextAreaElement) return !el.readOnly && !el.disabled;
  if (el instanceof HTMLInputElement) return TEXT_INPUTS.has(el.getAttribute('type') || '') && !el.readOnly && !el.disabled;
  return el instanceof HTMLElement && (el.isContentEditable || el.matches('[contenteditable=""],[contenteditable="true"]'));
}
/** Type `text` where the cursor is in `el`, the way a keypress would. */
export function insertAtCaret(el, text) {
  el.focus();
  if (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement) {
    const start = el.selectionStart ?? el.value.length;
    const end = el.selectionEnd ?? start;
    el.value = el.value.slice(0, start) + text + el.value.slice(end);
    try { el.setSelectionRange(start + text.length, start + text.length); } catch { /* no caret */ }
    el.dispatchEvent(new Event('input', { bubbles: true }));
    return;
  }
  if (document.execCommand('insertText', false, text)) return;
  el.append(text);
  el.dispatchEvent(new Event('input', { bubbles: true }));
}
/** Start listening; every finished phrase goes to onText. Returns stop(), or null when this browser cannot. */
export function startListening(lang, onText, onStop, onHearing) {
  const R = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!R) return null;
  let wanted = true;
  let reason;
  const rec = new R();
  if (lang) rec.lang = lang;
  rec.continuous = true;
  rec.interimResults = !!onHearing;
  rec.onresult = (e) => {
    for (let i = e.resultIndex; i < e.results.length; i += 1) {
      const said = String(e.results[i][0]?.transcript || '').trim();
      if (!said) continue;
      if (e.results[i].isFinal) { if (onHearing) onHearing(''); onText(`${said} `); } else if (onHearing) onHearing(said);
    }
  };
  rec.onerror = (e) => { if (e.error !== 'no-speech' && e.error !== 'aborted') { wanted = false; reason = e.error; } };
  rec.onend = () => { if (wanted) { try { rec.start(); return; } catch { /* cannot restart */ } } onStop(reason); };
  rec.start();
  return () => { wanted = false; rec.stop(); };
}
/** A picture as a data: URL, shrunk so a note or an issue stays light (chip page.dock image_max_px, image_quality). */
export async function shrinkPicture(file) {
  const bmp = await createImageBitmap(file);
  const scale = Math.min(1, (K().image_max_px || 1600) / Math.max(bmp.width, bmp.height));
  const c = document.createElement('canvas');
  c.width = Math.round(bmp.width * scale); c.height = Math.round(bmp.height * scale);
  const ctx = c.getContext('2d');
  ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, c.width, c.height);
  ctx.drawImage(bmp, 0, 0, c.width, c.height);
  return c.toDataURL('image/jpeg', K().image_quality || 0.85);
}
export const asDataUrl = (blob) => new Promise((ok, bad) => { const r = new FileReader(); r.onload = () => ok(String(r.result || '')); r.onerror = () => bad(r.error); r.readAsDataURL(blob); });
const fileStamp = () => new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-');
function download(blob, name) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

// --- the bar's state, kept for the page's life: a running recording and the microphone outlive a fold of the bar --------
const S = { recorder: null, stopListening: null, target: null, waiting: '', hearing: '', aimed: false, unseen: 0, user: null };
const liveBox = (el) => (el && el.isConnected && isEditable(el) ? el : null);

function caption() {
  let c = document.getElementById('pd-caption');
  if (!S.stopListening) { if (c) c.remove(); return; }
  if (!c) { c = document.createElement('div'); c.id = 'pd-caption'; c.setAttribute('role', 'status'); document.body.appendChild(c); }
  c.innerHTML = `<span class="pd-cap-on">${icon('mic', 14)}${esc(w('caption.listening'))}</span>${esc(S.hearing || w(S.aimed ? 'caption.aimed' : 'caption.unaimed'))}`;
}

export function listen(quiet = false) {   // quiet: started by Notes opening, not by a press - a refusal says nothing
  const stop = startListening(K().speech_lang, (text) => {
    const el = liveBox(S.target);
    if (el) { insertAtCaret(el, text); return; }
    S.waiting += text; S.hearing = S.waiting; caption();          // no text box yet: kept, typed into the next one clicked
  }, (reason) => {
    S.stopListening = null; S.hearing = ''; S.waiting = '';
    caption(); draw(); listeners.forEach((f) => f());
    if (reason && !quiet) {
      const k = `mic.error.${reason}`;
      toast(`${w('mic.stopped')} - ${w(k).startsWith('[') ? w('mic.error.other', { reason }) : w(k)}`, 'bad', 8);
    }
  }, (text) => { S.hearing = text || S.waiting; caption(); });
  if (!stop) { if (!quiet) toast(`${w('mic.none.title')} - ${w('mic.none.body')}`, 'bad', 8); return; }
  S.stopListening = stop;
  S.aimed = !!liveBox(S.target);
  caption(); draw(); listeners.forEach((f) => f());
}
export const toggleMic = () => (S.stopListening ? S.stopListening() : listen());
export const listening = () => !!S.stopListening;
const listeners = new Set();                                       // Notes / Issues redraw their microphone button
export const onMicChange = (f) => { listeners.add(f); return () => listeners.delete(f); };

// --- screen capture: the taken screen full size; drag over the part to keep ---------------------------------------------
async function capture() {
  let stream;
  try { stream = await navigator.mediaDevices.getDisplayMedia({ video: true, preferCurrentTab: true }); } catch { return; }
  let src = '';
  try {
    const v = document.createElement('video');
    v.srcObject = stream; v.muted = true;
    await v.play();
    await new Promise((r) => setTimeout(r, 300));               // the browser's picker is still fading on the first frame
    const c = document.createElement('canvas');
    c.width = v.videoWidth; c.height = v.videoHeight;
    c.getContext('2d').drawImage(v, 0, 0);
    src = c.toDataURL('image/png');
  } catch { toast(`${w('capture.failed.title')} - ${w('capture.failed.body')}`, 'bad'); }
  finally { stream.getTracks().forEach((tr) => tr.stop()); }
  if (src) snip(src);
}

function snip(src) {
  const ov = document.createElement('div');
  ov.className = 'pd-snip';
  ov.innerHTML = `<div class="pd-snip-card" role="dialog" aria-modal="true" aria-label="${esc(w('snip.label'))}">
      <div class="pd-snip-head"><h3>${esc(w('snip.heading'))}</h3><div class="pd-snip-acts">
        <button type="button" class="as-btn as-dark" data-whole>${esc(w('snip.whole'))}</button>
        <button type="button" class="as-btn" data-cancel title="${esc(w('snip.cancel_title'))}">${esc(w('snip.cancel'))}</button></div></div>
      <div class="pd-snip-body"><div class="pd-snip-pic"><img alt="${esc(w('snip.alt'))}" draggable="false"/><div class="pd-snip-box" hidden></div></div></div></div>`;
  document.body.appendChild(ov);
  const img = ov.querySelector('img');
  const box = ov.querySelector('.pd-snip-box');
  img.src = src;
  let from = null;
  let b = null;
  const done = () => { ov.remove(); document.removeEventListener('keydown', onKey); };
  const onKey = (e) => { if (e.key === 'Escape') done(); };
  document.addEventListener('keydown', onKey);
  const at = (e) => { const r = img.getBoundingClientRect(); return { x: Math.min(Math.max(e.clientX - r.left, 0), r.width), y: Math.min(Math.max(e.clientY - r.top, 0), r.height) }; };
  const cut = (part) => {
    const k = img.naturalWidth / img.getBoundingClientRect().width;     // shown size -> real pixels
    const p = part && part.w > 4 && part.h > 4 ? part : { x: 0, y: 0, w: img.naturalWidth / k, h: img.naturalHeight / k };
    const c = document.createElement('canvas');
    c.width = Math.round(p.w * k); c.height = Math.round(p.h * k);
    c.getContext('2d').drawImage(img, p.x * k, p.y * k, p.w * k, p.h * k, 0, 0, c.width, c.height);
    c.toBlob((blob) => { done(); if (blob) grabResult({ kind: 'image', blob }); }, 'image/png');
  };
  img.onpointerdown = (e) => { img.setPointerCapture(e.pointerId); from = at(e); b = null; box.hidden = true; };
  img.onpointermove = (e) => {
    if (!from) return;
    const p = at(e);
    b = { x: Math.min(p.x, from.x), y: Math.min(p.y, from.y), w: Math.abs(p.x - from.x), h: Math.abs(p.y - from.y) };
    Object.assign(box.style, { left: `${b.x}px`, top: `${b.y}px`, width: `${b.w}px`, height: `${b.h}px` });
    box.hidden = false;
  };
  img.onpointerup = () => { if (from) { from = null; if (b && b.w > 4 && b.h > 4) cut(b); } };
  ov.querySelector('[data-whole]').onclick = () => cut(null);
  ov.querySelector('[data-cancel]').onclick = done;
}

/** What was captured or recorded, shown BEFORE anything is kept: the person decides where it goes, or discards it. */
function grabResult(grab) {
  const url = URL.createObjectURL(grab.blob);
  const picture = grab.kind === 'image';
  let keptIt = false;
  modal(w(picture ? 'grab.title.image' : 'grab.title.video'), `<div class="pd-grab" data-grab-result="${grab.kind}">
      ${picture ? `<img src="${url}" alt="${esc(w('grab.alt'))}"/>` : `<video src="${url}" controls></video>`}
      <div class="pd-grab-acts">
        ${picture ? `<button type="button" class="as-btn" data-a="copy">${icon('copy', 14)}${esc(w('grab.copy'))}</button>` : ''}
        <button type="button" class="as-btn" data-a="download">${icon('download', 14)}${esc(w('grab.download'))}</button>
        ${picture ? `<button type="button" class="as-btn" data-a="note">${icon('notebook', 14)}${esc(w('grab.note'))}</button>
          <button type="button" class="as-btn" data-a="issue">${icon('flag', 14)}${esc(w('grab.issue'))}</button>` : ''}
        <button type="button" class="as-btn as-danger" data-a="discard">${icon('trash', 14)}${esc(w('grab.discard'))}</button></div></div>`, {
    wide: true, stay: true,
    onClose: () => URL.revokeObjectURL(url),
    onOpen: (b, closeIt) => {
      const ask = () => confirmDialog(w(picture ? 'grab.discard_shot_confirm.title' : 'grab.discard_confirm.title'), w('grab.discard_confirm.body'), () => closeIt(), w('grab.discard'));
      b.querySelectorAll('[data-a]').forEach((btn) => {
        btn.onclick = async () => {
          const a = btn.dataset.a;
          if (a === 'copy') {
            try { await navigator.clipboard.write([new ClipboardItem({ 'image/png': grab.blob })]); keptIt = true; toast(`${w('grab.copied.title')} - ${w('grab.copied.body')}`); }
            catch { toast(`${w('grab.copy_refused.title')} - ${w('grab.copy_refused.body')}`, 'bad'); }
          } else if (a === 'download') { download(grab.blob, `screen-${fileStamp()}.${picture ? 'png' : 'webm'}`); keptIt = true; }
          else if (a === 'discard') { if (keptIt) closeIt(); else ask(); }
          else {
            try {
              const pic = await shrinkPicture(grab.blob);
              closeIt();
              if (a === 'note') openNotes(pic); else openIssues(pic);
            } catch { toast(`${w('handon.failed.title')} - ${w('handon.failed.body')}`, 'bad'); }
          }
        };
      });
    } });
}

// --- screen recording: the screen and the microphone until stopped ------------------------------------------------------
async function record() {
  if (S.recorder) { S.recorder.stop(); return; }
  let screen;
  try { screen = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: true }); } catch { return; }
  let mic = null;
  try { mic = await navigator.mediaDevices.getUserMedia({ audio: true }); } catch { /* no microphone: the screen's own sound */ }
  const sound = (mic && mic.getAudioTracks()[0]) || screen.getAudioTracks()[0];   // ponytail: one sound track; a mix needs an AudioContext
  const chunks = [];
  const rec = new MediaRecorder(new MediaStream([screen.getVideoTracks()[0], ...(sound ? [sound] : [])]));
  rec.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
  const stopAt = setTimeout(() => rec.state !== 'inactive' && rec.stop(), (K().record_max_minutes || 30) * 60000);
  rec.onstop = () => {
    clearTimeout(stopAt);
    [screen, mic].forEach((s) => s && s.getTracks().forEach((tr) => tr.stop()));
    S.recorder = null; draw();
    grabResult({ kind: 'video', blob: new Blob(chunks, { type: rec.mimeType || 'video/webm' }) });
  };
  screen.getVideoTracks()[0].onended = () => { if (rec.state !== 'inactive') rec.stop(); };   // the browser's own Stop sharing
  rec.start();
  S.recorder = rec; draw();
  toast(`${w('record.started.title')} - ${w('record.started.body')}`, 'ok', 8);
}

// --- notes and issues: their own modules, loaded on first use -----------------------------------------------------------
export async function openNotes(picture) {
  S.target = null; S.aimed = false;                              // words spoken before the note is up must not land behind it
  const m = await import('./notes-modal.js');
  m.notesModal({ picture, onClose: () => { if (S.stopListening) S.stopListening(); } });
  if (!S.stopListening) listen(true);                             // the studio: the microphone is on as Notes opens
}
export async function openIssues(shot) {
  const m = await import('./issues-modal.js');
  m.issuesModal({ shot, onClose: countUnseen, onSeen: countUnseen });
}
export async function countUnseen() {
  try { S.unseen = (await api('/api/dock/issues/unseen')).n || 0; } catch { S.unseen = 0; }
  draw();
}

// --- the bar -----------------------------------------------------------------------------------------------------------
const canScreen = () => !!(navigator.mediaDevices && navigator.mediaDevices.getDisplayMedia);
const TOOLS = {
  capture: () => canScreen() && `<button type="button" class="pd-b pd-sky" data-dock-tool="capture" title="${esc(w('tool.capture.title'))}" aria-label="${esc(w('tool.capture.label'))}">${icon('crop', 20)}</button>`,
  record: () => canScreen() && `<button type="button" class="pd-b ${S.recorder ? 'pd-on' : 'pd-violet'}" data-dock-tool="record" aria-pressed="${!!S.recorder}"
      title="${esc(w(S.recorder ? 'tool.record.title_on' : 'tool.record.title'))}" aria-label="${esc(w(S.recorder ? 'tool.record.label_on' : 'tool.record.label'))}">${icon('video', 20)}</button>`,
  voice: () => `<button type="button" class="pd-b ${S.stopListening ? 'pd-on' : 'pd-emerald'}" data-dock-tool="voice" aria-pressed="${!!S.stopListening}"
      title="${esc(w(S.stopListening ? 'tool.voice.title_on' : 'tool.voice.title'))}" aria-label="${esc(w(S.stopListening ? 'tool.voice.label_on' : 'tool.voice.label'))}">${icon('mic', 20)}</button>`,
  notes: () => `<button type="button" class="pd-b pd-amber" data-dock-tool="notes" title="${esc(w('tool.notes.title'))}" aria-label="${esc(w('tool.notes.label'))}">${icon('notebook', 20)}</button>`,
  issue: () => `<button type="button" class="pd-b pd-rose" data-dock-tool="issue" title="${esc(w(S.unseen ? 'tool.issue.title_badge' : 'tool.issue.title', { n: S.unseen }))}"
      aria-label="${esc(w(S.unseen ? 'tool.issue.label_badge' : 'tool.issue.label', { n: S.unseen }))}">${icon('flag', 20)}${S.unseen ? `<span class="pd-badge" data-issue-badge>${S.unseen}</span>` : ''}</button>`,
};
const chatBtn = () => `<button type="button" class="pd-b" data-dock-chip-chat title="${esc(w('bar.chat_tip'))}" aria-label="${esc(w('bar.chat_label'))}">${chipChatGlyph(24)}</button>`;

function draw() {
  const el = document.getElementById('sf-dock');
  if (!el) return;
  const open = kept('sf.dock.open', '1') !== '0';
  const col = kept('sf.dock.dir', 'row') === 'col';
  el.dataset.dir = open ? (col ? 'col' : 'row') : 'folded';
  el.innerHTML = !open
    ? `<button type="button" class="pd-arrow" data-open="row" title="${esc(w('bar.open_row'))}" aria-label="${esc(w('bar.open_row_label'))}">${icon('left', 16)}</button>
       <div class="pd-stack"><button type="button" class="pd-arrow pd-up" data-open="col" title="${esc(w('bar.open_col'))}" aria-label="${esc(w('bar.open_col_label'))}">${icon('up', 16)}</button>${chatBtn()}</div>`
    : `<button type="button" class="pd-arrow ${col ? 'pd-up' : ''}" data-hide title="${esc(w('bar.hide'))}" aria-label="${esc(w('bar.hide_label'))}">${icon(col ? 'down' : 'right', 16)}</button>
       ${chatBtn()}${(K().tools || Object.keys(TOOLS)).map((id) => (TOOLS[id] ? TOOLS[id]() || '' : '')).join('')}`;
  el.querySelectorAll('[data-open]').forEach((b) => { b.onclick = () => { keep('sf.dock.open', '1'); keep('sf.dock.dir', b.dataset.open); draw(); }; });
  const hide = el.querySelector('[data-hide]');
  if (hide) hide.onclick = () => { keep('sf.dock.open', '0'); draw(); };
  el.querySelector('[data-dock-chip-chat]').onclick = () => import('./chipchat.js').then((m) => m.openChipChat());
  const on = (sel, fn) => { const b = el.querySelector(sel); if (b) b.onclick = fn; };
  on('[data-dock-tool=capture]', capture);
  on('[data-dock-tool=record]', record);
  on('[data-dock-tool=notes]', () => openNotes());
  on('[data-dock-tool=issue]', () => openIssues());
  const v = el.querySelector('[data-dock-tool=voice]');
  if (v) { v.onmousedown = (e) => e.preventDefault(); v.onclick = toggleMic; }   // the press never takes focus: the cursor stays in the box
}

let wired = false;
export async function syncDock(user) {
  let el = document.getElementById('sf-dock');
  S.user = user;
  if (!user) { if (el) el.remove(); return; }
  if (!wired) {
    wired = true;
    document.addEventListener('focusin', (e) => {
      if (!isEditable(e.target)) return;
      S.target = e.target; S.aimed = true;
      if (S.waiting) {   // after the click has placed the cursor: the words go where the person clicked
        const text = S.waiting; S.waiting = '';
        setTimeout(() => { const box = liveBox(S.target); if (box) { insertAtCaret(box, text); S.hearing = ''; } else S.waiting = text; caption(); }, 0);
      }
      caption();
    });
    window.addEventListener('focus', () => S.user && countUnseen());
    // signed out = the shell draws the sign-in page and never calls wireTopbar again: take the bar away
    new MutationObserver(() => { if (document.querySelector('aside.pitch')) { const d = document.getElementById('sf-dock'); if (d) d.remove(); } })
      .observe(document.body, { childList: true });
  }
  if (el) return;
  await loadWords('dock');
  el = document.createElement('div');
  el.id = 'sf-dock';
  el.className = 'pd';
  document.body.appendChild(el);
  draw();
  countUnseen();
}
