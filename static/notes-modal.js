// Notes - the studio's NotesModal, ported (2026-10-04 owner). A person's own notes about any screen, opened from the bottom
// bar. Left pane = every saved note with flexi search (server, chip notes.list_view), New and Delete; right = the note, with
// Bold / Italic / Underline, numbered and bullet lists, highlighter and text colours (chip page.dock), pictures pasted with
// Ctrl+V (or handed over from Screen capture), voice notes with their words, and the microphone already on as it opens
// (what is spoken is typed in). The server keeps only the tags and styles chip notes.settings allows. Words: chip ui.dock.
import { api, esc, toast, modal, confirmDialog, when } from './app.js';
import { icon } from './icons.js';
import { w, K, shrinkPicture, toggleMic, listening, onMicChange } from './dock.js';
import { voiceNoteButton, attachmentList } from './dock-attach.js';

const errorText = (e, fallback) => String((e && e.message) || fallback);

export function notesModal({ picture = '', onClose = () => {} } = {}) {
  const st = { list: [], query: '', id: null, name: '', dirty: false, voices: [] };
  let body;
  let off = () => {};
  const guard = (run) => { if (!st.dirty) { run(); return; } confirmDialog(w('notes.leave.title'), w('notes.leave.body'), run, w('yes'), { tone: 'warn' }); };
  const close = modal(w('notes.title'), `<div class="as-split" data-notes>
      <aside class="as-side">
        <div class="as-side-head"><label class="as-search">${icon('search', 14)}<input data-q placeholder="${esc(w('notes.search'))}" aria-label="${esc(w('notes.search_label'))}"/></label>
          <button type="button" class="as-sq as-dark" data-new title="${esc(w('notes.new'))}" aria-label="${esc(w('notes.new'))}">${icon('plus', 16)}</button></div>
        <div class="as-side-list" data-list></div></aside>
      <section class="as-main">
        <div class="as-main-head"><input class="as-name" data-name placeholder="${esc(w('notes.name'))}" aria-label="${esc(w('notes.name'))}"/>
          <button type="button" class="as-btn as-dark" data-save>${icon('save', 14)}<span data-save-word>${esc(w('notes.save'))}</span></button></div>
        <div class="as-toolbar" data-tools></div>
        <div class="as-editor" data-editor contenteditable="true" role="textbox" aria-multiline="true" aria-label="${esc(w('notes.paper'))}"></div>
        <div class="as-voices" data-voices hidden></div>
      </section></div>`, {
    wide: true, stay: true, cls: 'as-modal-xl',
    onClose: () => { off(); onClose(); },
    onOpen: (b) => {
      body = b;
      const ed = b.querySelector('[data-editor]');
      const nameBox = b.querySelector('[data-name]');
      const saveWord = () => { b.querySelector('[data-save-word]').textContent = w(st.dirty ? 'notes.save_dirty' : 'notes.save'); };
      const dirty = () => { st.dirty = true; saveWord(); };
      const drawList = () => {
        b.querySelector('[data-list]').innerHTML = st.list.length ? st.list.map((n) => `<div class="as-row ${n.id === st.id ? 'on' : ''}">
            <button type="button" class="as-row-open" data-open="${esc(n.id)}"><b>${esc(n.name)}</b><span>${esc(n.preview)}</span><small>${esc(when(n.updated_at))}</small></button>
            <button type="button" class="as-row-x" data-del="${esc(n.id)}" title="${esc(w('notes.delete_row'))}" aria-label="${esc(w('notes.delete_row_label', { name: n.name }))}">${icon('trash', 14)}</button></div>`).join('')
          : `<p class="as-empty">${esc(w(st.query ? 'notes.none_match' : 'notes.none_yet'))}</p>`;
        b.querySelectorAll('[data-open]').forEach((x) => { x.onclick = () => open(x.dataset.open); });
        b.querySelectorAll('[data-del]').forEach((x) => { x.onclick = () => remove(st.list.find((n) => n.id === x.dataset.del)); });
      };
      const drawVoices = () => {
        const v = b.querySelector('[data-voices]');
        v.hidden = !st.voices.length;
        v.innerHTML = `<p class="as-label">${esc(w('notes.voices'))}</p>${attachmentList(st.voices, { onRemove: true })}`;
        v.querySelectorAll('[data-remove]').forEach((x) => { x.onclick = () => dropVoice(+x.dataset.remove); });
      };
      const refresh = async () => {
        try { st.list = (await api(`/api/notes?q=${encodeURIComponent(st.query)}`)).notes; drawList(); }
        catch (e) { toast(`${w('notes.load_failed')} - ${errorText(e, w('try_again'))}`, 'bad'); }
      };
      const show = (n) => {
        st.id = n ? n.id : null; st.name = n ? n.name : ''; st.dirty = false; st.voices = n ? n.attachments || [] : [];
        nameBox.value = st.name; ed.innerHTML = n ? n.content : ''; saveWord(); drawVoices(); drawList(); ed.focus();
      };
      const open = (id) => guard(async () => {
        try { show(await api(`/api/notes/${encodeURIComponent(id)}`)); } catch (e) { toast(`${w('notes.open_failed')} - ${errorText(e, w('try_again'))}`, 'bad'); }
      });
      const save = async () => {
        if (!nameBox.value.trim() && !ed.textContent.trim() && !ed.querySelector('img')) { toast(`${w('notes.empty.title')} - ${w('notes.empty.body')}`); ed.focus(); return null; }
        try {
          const n = await api(st.id ? `/api/notes/${st.id}` : '/api/notes', { method: st.id ? 'PUT' : 'POST', body: { name: nameBox.value, content: ed.innerHTML } });
          st.id = n.id; st.name = n.name; nameBox.value = n.name; st.dirty = false; saveWord();
          await refresh();
          toast(`${w('notes.saved')} - ${n.name}`);
          return n.id;
        } catch (e) { toast(`${w('notes.save_failed')} - ${errorText(e, w('try_again'))}`, 'bad'); return null; }
      };
      const remove = (n) => confirmDialog(w('notes.delete.title'), w('notes.delete.body', { name: n.name }), async () => {
        try { await api(`/api/notes/${n.id}`, { method: 'DELETE' }); if (n.id === st.id) show(null); await refresh(); }
        catch (e) { toast(`${w('notes.delete_failed')} - ${errorText(e, w('try_again'))}`, 'bad'); }
      }, w('yes'));
      // A voice note belongs to a saved note: an unsaved one with something in it is saved first.
      const addVoice = async (v) => {
        let id = st.id;
        if (!id) {
          if (!nameBox.value.trim() && !ed.textContent.trim()) { toast(`${w('notes.voices')} - ${w('notes.voice_first_save')}`); return; }
          id = await save();
          if (!id) return;
        }
        try { st.voices = (await api(`/api/notes/${id}/voice`, { method: 'POST', body: v })).attachments || []; drawVoices(); toast(`${w('notes.voice_saved.title')} - ${w('notes.voice_saved.body')}`); }
        catch (e) { toast(`${w('notes.voice_failed')} - ${errorText(e, w('try_again'))}`, 'bad'); }
      };
      const dropVoice = (i) => {
        const f = st.voices[i];
        if (!st.id || !f) return;
        confirmDialog(w('notes.voice_delete.title'), w('notes.voice_delete.body'), async () => {
          try { st.voices = (await api(`/api/notes/${st.id}/files/${f.id}`, { method: 'DELETE' })).attachments || []; drawVoices(); }
          catch (e) { toast(`${w('notes.delete_failed')} - ${errorText(e, w('try_again'))}`, 'bad'); }
        }, w('yes'));
      };
      const format = (cmd, value) => {
        ed.focus();
        try { document.execCommand('styleWithCSS', false, 'true'); } catch { /* older engines */ }
        document.execCommand(cmd, false, value);
        dirty();
      };
      // the toolbar: microphone, voice note | B I U, numbered, bullets | highlight colours, clear | text colours
      const tools = b.querySelector('[data-tools]');
      const tool = (label, run, html, cls = '') => { const x = document.createElement('button'); x.type = 'button'; x.className = `as-tool ${cls}`; x.title = label; x.setAttribute('aria-label', label); x.innerHTML = html; x.onmousedown = (e) => e.preventDefault(); x.onclick = run; return x; };
      const swatch = (label, color, cmd) => { const x = tool(`${label} ${color}`, () => format(cmd, color), '', 'as-swatch'); x.style.background = color; return x; };
      const bar = () => { const s = document.createElement('span'); s.className = 'as-sep'; return s; };
      const tag = (text) => { const s = document.createElement('span'); s.className = 'as-label'; s.textContent = text; return s; };
      const mic = tool('', toggleMic, '');
      const drawMic = () => { const on = listening(); mic.title = w(on ? 'notes.mic_on' : 'notes.mic_off'); mic.classList.toggle('as-on', on); mic.innerHTML = `${icon('mic', 16)}${on ? `<span class="as-label">${esc(w('notes.listening'))}</span>` : ''}`; };
      drawMic();
      off = onMicChange(drawMic);
      tools.append(mic, voiceNoteButton((v) => { void addVoice(v); }, 'as-btn-sm'), bar(),
        tool(w('notes.bold'), () => format('bold'), icon('bold', 16)), tool(w('notes.italic'), () => format('italic'), icon('italic', 16)),
        tool(w('notes.underline'), () => format('underline'), icon('underline', 16)), tool(w('notes.numbered'), () => format('insertOrderedList'), icon('olist', 16)),
        tool(w('notes.bullets'), () => format('insertUnorderedList'), icon('list', 16)), bar(), tag(w('notes.highlight')),
        ...(K().highlight_colors || []).map((c) => swatch(w('notes.highlight'), c, 'hiliteColor')), tool(w('notes.clear'), () => format('removeFormat'), icon('eraser', 16)),
        bar(), tag(w('notes.text')), ...(K().text_colors || []).map((c) => swatch(w('notes.text_colour'), c, 'foreColor')));
      ed.oninput = dirty;
      nameBox.oninput = dirty;
      ed.onpaste = async (e) => {
        const file = [...e.clipboardData.files].find((f) => f.type.startsWith('image/'));
        if (!file) return;                                         // words: the browser pastes them
        e.preventDefault();
        try { format('insertImage', await shrinkPicture(file)); } catch { toast(`${w('notes.paste_failed.title')} - ${w('notes.paste_failed.body')}`, 'bad'); }
      };
      let tq = 0;
      b.querySelector('[data-q]').oninput = (e) => { st.query = e.target.value; clearTimeout(tq); tq = setTimeout(refresh, 250); };
      b.querySelector('[data-new]').onclick = () => guard(() => show(null));
      b.querySelector('[data-save]').onclick = () => { void save(); };
      refresh();
      ed.focus();                                                  // cursor in the note: the microphone types here
      if (picture) { const img = document.createElement('img'); img.src = picture; ed.append(img, document.createElement('br')); dirty(); }
    } });
  return close;
}
