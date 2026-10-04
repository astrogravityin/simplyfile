// Issues - AstroStage's IssuesModal, ported (2026-10-04 owner). Report an issue from any screen, and follow what became of
// it. Left pane = the person's own issues (flexi search + status filter, server chip issues.mine_view); right = a new issue
// (header, details, SEVERAL pictures pasted with Ctrl+V one after another or attached at once, voice notes with their words,
// the microphone for typing) or the chosen issue with its status and the portal admin's reply. A new issue lands in the
// portal admin's Reported issues. Status words and colours: chip page.dock; every other word: chip ui.dock.
import { api, esc, toast, modal, when } from './app.js';
import { icon } from './icons.js';
import { w, K, shrinkPicture, toggleMic, listening, onMicChange } from './dock.js';
import { voiceNoteButton, attachmentList } from './dock-attach.js';

const errorText = (e, fallback) => String((e && e.message) || fallback);

export function issuesModal({ shot = '', onClose = () => {}, onSeen = () => {} } = {}) {
  const st = { list: [], counts: {}, query: '', status: '', chosen: null, files: shot ? [{ kind: 'image', name: 'capture', data: shot }] : [], title: '', text: '' };
  let off = () => {};
  const statuses = () => K().issue_statuses || {};
  const tones = () => K().tones || {};
  const pill = (s) => `<span class="as-pill" style="--c:var(${tones()[(statuses()[s] || {}).tone] || '--muted'})">${esc((statuses()[s] || {}).label || s)}</span>`;
  const fileSrc = (r) => (f) => f.data || `/api/core/issues/${encodeURIComponent(r.id)}/files/${f.n}`;
  return modal(w('issues.title'), `<div class="as-split" data-issues>
      <aside class="as-side as-side-w">
        <div class="as-side-head"><label class="as-search">${icon('search', 14)}<input data-q placeholder="${esc(w('issues.search'))}" aria-label="${esc(w('issues.search_label'))}"/></label>
          <button type="button" class="as-sq as-dark" data-new title="${esc(w('issues.new'))}" aria-label="${esc(w('issues.new'))}">${icon('plus', 16)}</button></div>
        <div class="as-filters" data-filters></div>
        <div class="as-side-list" data-list></div></aside>
      <section class="as-main as-pad" data-main></section></div>`, {
    wide: true, stay: true, cls: 'as-modal-l',
    onClose: () => { off(); onClose(); },
    onOpen: (b) => {
      const main = b.querySelector('[data-main]');
      const drawSide = () => {
        const total = Object.values(st.counts).reduce((a, n) => a + n, 0);
        const f = (key, label, n) => `<button type="button" class="as-filter ${st.status === key ? 'on' : ''}" data-status="${esc(key)}" aria-pressed="${st.status === key}">${esc(label)} ${n}</button>`;
        b.querySelector('[data-filters]').innerHTML = f('', w('issues.all'), total) + Object.keys(statuses()).map((s) => f(s, statuses()[s].label || s, st.counts[s] || 0)).join('');
        b.querySelectorAll('[data-status]').forEach((x) => { x.onclick = () => { st.status = x.dataset.status; refresh(); }; });
        b.querySelector('[data-list]').innerHTML = st.list.length ? st.list.map((r) => `<button type="button" class="as-row as-row-btn ${st.chosen && st.chosen.id === r.id ? 'on' : ''}" data-open="${esc(r.id)}">
            <span class="as-row-top"><b>${esc(r.title)}</b>${pill(r.status)}</span><small>#${esc(r.id.slice(0, 6))} · ${esc(when(r.at))}</small></button>`).join('')
          : `<p class="as-empty">${esc(w(st.query || st.status ? 'issues.none_match' : 'issues.none_yet'))}</p>`;
        b.querySelectorAll('[data-open]').forEach((x) => { x.onclick = () => open(st.list.find((r) => r.id === x.dataset.open)); });
      };
      const refresh = async () => {
        try { const d = await api(`/api/dock/issues?q=${encodeURIComponent(st.query)}&status=${encodeURIComponent(st.status)}`); st.list = d.reports || []; st.counts = d.counts || {}; drawSide(); }
        catch (e) { toast(`${w('issues.load_failed')} - ${errorText(e, w('try_again'))}`, 'bad'); }
      };
      const open = async (row) => {
        st.chosen = row; drawSide(); drawMain();
        try { st.chosen = await api(`/api/dock/issues/${encodeURIComponent(row.id)}`); drawMain(); } catch (e) { toast(`${w('issues.open_failed')} - ${errorText(e, w('try_again'))}`, 'bad'); }
        api(`/api/core/issues/${encodeURIComponent(row.id)}/seen`, { method: 'POST' }).then(onSeen).catch(() => {});   // opened: off the badge
      };
      const takePicture = async (file) => {
        if (!file) return;
        if (!file.type.startsWith('image/')) { toast(`${w('issues.pictures_only.title')} - ${w('issues.pictures_only.body')}`); return; }
        try { st.files.push({ kind: 'image', name: file.name || 'picture', data: await shrinkPicture(file) }); drawFiles(); }
        catch { toast(`${w('issues.attach_failed.title')} - ${w('issues.attach_failed.body')}`, 'bad'); }
      };
      const drawFiles = () => {
        const box = main.querySelector('[data-files]');
        if (!box) return;
        main.querySelector('[data-hint]').textContent = `${w('attach.hint')}${st.files.length ? ` · ${w('attach.count', { n: st.files.length })}` : ''}`;
        box.innerHTML = attachmentList(st.files, { onRemove: true });
        box.querySelectorAll('[data-remove]').forEach((x) => { x.onclick = () => { st.files.splice(+x.dataset.remove, 1); drawFiles(); }; });
      };
      const drawMain = () => {
        off();
        const r = st.chosen;
        if (r) {
          main.innerHTML = `<div class="as-detail" data-issue-detail><div class="as-row-top"><h4>${esc(r.title)}</h4>${pill(r.status)}</div>
            <p class="as-meta">#${esc(r.id.slice(0, 6))} · ${esc(w('issues.reported'))} ${esc(when(r.at))}${r.context ? ` · ${esc(r.context)}` : ''}</p>
            <p class="as-body">${esc(r.text || '')}</p>
            ${r.shot ? `<img class="as-shot" src="/api/core/issues/${encodeURIComponent(r.id)}/shot" alt="${esc(w('issues.shot_alt'))}"/>` : ''}
            ${attachmentList(r.files || [], { src: fileSrc(r) })}
            ${r.reply ? `<div class="as-reply"><p class="as-label">${esc(w('issues.reply'))}${r.action_date ? ` · ${esc(r.action_date)}` : ''}</p><p class="as-body">${esc(r.reply)}</p></div>`
              : `<p class="as-noreply">${esc(w('issues.no_reply'))}</p>`}</div>`;
          return;
        }
        main.innerHTML = `<div class="as-new" data-issue-new>
            <p class="as-intro">${icon('flag', 16)}${esc(w('issues.intro'))}</p>
            <label class="as-field"><span class="as-label">${esc(w('issues.header'))}</span><input data-title maxlength="200" placeholder="${esc(w('issues.header_hint'))}" value="${esc(st.title)}"/></label>
            <label class="as-field as-grow"><span class="as-label">${esc(w('issues.details'))}</span><textarea data-text maxlength="20000" placeholder="${esc(w('issues.details_hint'))}">${esc(st.text)}</textarea></label>
            <p class="as-muted" data-hint></p><div class="as-files-box" data-files></div>
            <div class="as-acts"><input type="file" accept="image/*" multiple hidden data-pick/>
              <button type="button" class="as-btn" data-attach>${icon('clip', 14)}${esc(w('issues.attach'))}</button><span data-voice></span>
              <button type="button" class="as-btn" data-mic></button>
              <button type="button" class="as-btn as-dark as-push" data-send>${icon('send', 14)}${esc(w('issues.submit'))}</button></div></div>`;
        const title = main.querySelector('[data-title]');
        const text = main.querySelector('[data-text]');
        title.oninput = () => { st.title = title.value; };
        text.oninput = () => { st.text = text.value; };
        const pick = main.querySelector('[data-pick]');
        main.querySelector('[data-attach]').onclick = () => pick.click();
        pick.onchange = () => { [...pick.files].forEach((f) => { void takePicture(f); }); pick.value = ''; };
        main.querySelector('[data-voice]').replaceWith(voiceNoteButton((v) => { st.files.push({ kind: 'audio', name: 'voice note', data: v.data, transcript: v.transcript, transcript_status: v.transcript ? 'done' : 'unavailable' }); drawFiles(); }));
        const mic = main.querySelector('[data-mic]');
        const drawMic = () => { const on = listening(); mic.classList.toggle('as-on', on); mic.title = w(on ? 'issues.mic_on' : 'issues.mic_off'); mic.innerHTML = `${icon('mic', 14)}${esc(w(on ? 'issues.listening' : 'issues.speak'))}`; };
        mic.onmousedown = (e) => e.preventDefault();
        mic.onclick = toggleMic;
        drawMic();
        off = onMicChange(drawMic);
        const send = main.querySelector('[data-send]');
        send.onclick = async () => {
          if (send.disabled) return;
          if (!title.value.trim()) { toast(`${w('issues.need_header.title')} - ${w('issues.need_header.body')}`); title.focus(); return; }
          if (!text.value.trim()) { toast(`${w('issues.need_body.title')} - ${w('issues.need_body.body')}`); text.focus(); return; }
          send.disabled = true; send.innerHTML = `${icon('send', 14)}${esc(w('issues.sending'))}`;
          try {
            await api('/api/core/issues', { method: 'POST', body: { title: title.value.trim(), body: text.value.trim(), surface: 'dock',
              context: location.hash.slice(0, 300), attachments: st.files.map((f) => ({ data: f.data, name: f.name, transcript: f.transcript || '' })) } });
            st.title = ''; st.text = ''; st.files = [];
            await refresh(); drawMain();
            toast(`${w('issues.sent.title')} - ${w('issues.sent.body')}`);
          } catch (e) { toast(`${w('issues.send_failed')} - ${errorText(e, w('try_again'))}`, 'bad'); send.disabled = false; send.innerHTML = `${icon('send', 14)}${esc(w('issues.submit'))}`; }
        };
        drawFiles();
        title.focus();
      };
      b.querySelector('[data-issues]').addEventListener('paste', (e) => {
        if (st.chosen) return;
        const pictures = [...e.clipboardData.files].filter((f) => f.type.startsWith('image/'));
        if (!pictures.length) return;                              // words: the browser pastes them
        e.preventDefault();
        pictures.forEach((f) => { void takePicture(f); });         // each paste adds; nothing is replaced
      });
      let tq = 0;
      b.querySelector('[data-q]').oninput = (e) => { st.query = e.target.value; clearTimeout(tq); tq = setTimeout(refresh, 250); };
      b.querySelector('[data-new]').onclick = () => { st.chosen = null; drawSide(); drawMain(); };
      refresh();
      drawMain();
    } });
}
