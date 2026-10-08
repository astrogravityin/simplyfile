// Pictures and VOICE NOTES on a note or an issue - the studio's DockAttachments, ported (2026-10-04 owner). The studio turns
// a voice note into text on its server; here the browser writes the words down while the voice note is being recorded
// (the same speech service as voice typing), so the text is there the moment it stops. While a voice note records, voice
// typing pauses (one microphone listener at a time) and comes back after. Words: chip ui.dock (voice.*, attach.*).
import { esc, toast } from './app.js';
import { icon } from './icons.js';
import { w, K, asDataUrl, startListening, listening, toggleMic } from './dock.js';

/** A Voice note button. onDone({data, transcript}) when it stops (by press, or after chip page.dock voice_max_seconds). */
export function voiceNoteButton(onDone, extra = '') {
  const b = document.createElement('button');
  b.type = 'button';
  b.className = `as-btn ${extra}`;
  b.dataset.voiceNote = '';
  let rec = null;
  let tick = null;
  let words = '';
  let stopWords = null;
  let wasOn = false;
  const idle = () => { b.classList.remove('as-on'); b.setAttribute('aria-pressed', 'false'); b.title = w('voice.record_title'); b.innerHTML = `${icon('mic', 14)}${esc(w('voice.record'))}`; };
  const live = (s) => { b.title = w('voice.stop_title', { s }); b.innerHTML = `${icon('square', 14)}${esc(w('voice.recording', { s }))}`; };
  const stop = () => { if (rec && rec.state === 'recording') rec.stop(); };
  b.onmousedown = (e) => e.preventDefault();
  b.onclick = async () => {
    if (rec) { stop(); return; }
    let stream;
    try { stream = await navigator.mediaDevices.getUserMedia({ audio: true }); } catch { toast(`${w('voice.refused.title')} - ${w('voice.refused.body')}`, 'bad', 8); return; }
    wasOn = listening();
    if (wasOn) toggleMic();
    words = '';
    stopWords = startListening(K().speech_lang, (t) => { words += t; }, () => { stopWords = null; });
    const chunks = [];
    rec = new MediaRecorder(stream);
    rec.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
    rec.onstop = async () => {
      clearInterval(tick);
      stream.getTracks().forEach((tr) => tr.stop());
      if (stopWords) stopWords();
      const type = rec.mimeType || 'audio/webm';
      rec = null; idle();
      if (wasOn && !listening()) toggleMic();
      setTimeout(async () => onDone({ data: await asDataUrl(new Blob(chunks, { type })), transcript: words.trim() }), 400);   // the last phrase arrives just after
    };
    rec.start();
    b.classList.add('as-on'); b.setAttribute('aria-pressed', 'true');
    const t0 = Date.now();
    live(0);
    tick = setInterval(() => {
      const s = Math.floor((Date.now() - t0) / 1000);
      live(s);
      if (K().voice_max_seconds && s >= K().voice_max_seconds) stop();
    }, 500);
  };
  idle();
  return b;
}

/** Pictures, voice-note players and the words of each. `src(f)` = where a file's bytes are; `onRemove(i)` = a remove button. */
export function attachmentList(items, { src = (f) => f.data, onRemove = null } = {}) {
  if (!items.length) return '';
  return `<ul class="as-files" data-attachments>${items.map((f, i) => `<li class="as-file" data-attachment="${esc(f.kind)}">
      ${onRemove ? `<button type="button" class="as-x" data-remove="${i}" title="${esc(w('attach.remove'))}" aria-label="${esc(w('attach.remove'))}">${icon('close', 14)}</button>` : ''}
      ${f.kind === 'image' ? `<img src="${esc(src(f))}" alt="${esc(f.name || w('attach.picture'))}"/>` : `<div class="as-voice">
        <p class="as-label">${esc(w('attach.voice'))}</p><audio src="${esc(src(f))}" controls></audio>
        ${f.transcript ? `<p class="as-words" data-transcript><span class="as-label">${esc(w('voice.transcript'))}</span>${esc(f.transcript)}</p>`
          : `<p class="as-muted">${esc(w(`voice.status.${f.transcript_status || 'new'}`))}</p>`}</div>`}</li>`).join('')}</ul>`;
}
