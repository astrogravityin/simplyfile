// Chip Chat - the studio's ChipChat + chipChatShared, ported (2026-10-04 owner: "Surprise me gone ... bring entire thing from
// the studio"). Ask in plain words; SimplyFile's own rules and the firm's data answer (chipchat.py - the screen evaluates
// nothing). Chat: your questions right (with ↻ to ask again), the chips' answers left - the answer, its lines (each opens
// its client), the screen it lives on, choices when the question was unclear, and Ask next. The ask box: a rotating hint,
// a fresh set of example questions on every open and after every ask, and Surprise me. Train (the firm admin, the portal
// owner): every question asked, to review - teach the right answer or write the firm's own, skip, the taught phrases, the
// firm's own answers, Export JSONL and the Unanswered report. Words: chip ui.chipchat.
import { api, esc, toast, t, loadWords, modal, confirmDialog, when, listBox } from './app.js';
import { icon, chipChatGlyph, spinner } from './icons.js';

const w = (k, v) => t('chipchat', k, v);

function replyHtml(r) {
  const a = r.answer;
  let h = '';
  if (r.route !== 'answer' || !a) h += `<p class="cx-say">${esc(r.say || '')}</p>`;
  if (a) {
    h += `<p class="cx-q">${esc(a.q)}</p>${a.text ? `<p class="cx-text">${esc(a.text)}</p>` : ''}`;
    if ((a.rows || []).length) h += `<ul class="cx-rows">${a.rows.map((x) => `<li>${x.go ? `<a href="${esc(x.go)}" data-go>${esc(x.text)}</a>` : esc(x.text)}</li>`).join('')}</ul>`;
    if (a.go) h += `<a class="cx-open" href="${esc(a.go)}" data-go>${icon('right', 13)} ${esc(w('open'))}</a>`;
  }
  if ((r.options || []).length) h += `<div class="cx-options">${r.options.map((o) => `<button type="button" class="cx-option" data-eid="${esc(o.id)}">${esc(o.q)}</button>`).join('')}</div>`;
  if ((r.next || []).length) h += `<div class="cx-next" data-chat-next><span class="as-label">${esc(w('ask_next'))}</span>${r.next.map((q) => `<button type="button" class="cx-next-q" data-ask="${esc(q)}">${esc(q)}</button>`).join('')}</div>`;
  return h;
}

export async function openChipChat() {
  await loadWords('chipchat');
  const screen = (location.hash.match(/^#\/([^?]+)/) || [])[1] || '';
  const first = await api(`/api/chat/examples?screen=${encodeURIComponent(screen)}`);
  const st = { msgs: [], busy: false, presses: 0, tab: 'chat' };
  modal(w('title'), `<div class="cx" data-chip-chat>
      <div class="cx-head">${chipChatGlyph(36)}<div><h3>${esc(w('head_title'))}</h3><p>${esc(w('head_sub'))}</p></div></div>
      <div class="cx-bar"><div class="tabs cx-tabs" role="tablist"><button type="button" class="on" data-tab="chat">${esc(w('chat_tab'))}</button>
        ${first.teach ? `<button type="button" data-tab="train">${esc(w('train_tab'))}</button>` : ''}</div>
        <button type="button" class="as-btn" data-reset>${icon('rotccw', 14)}${esc(w('new_chat'))}</button></div>
      <p class="cx-err" data-err hidden></p>
      <div class="cx-card" data-chat>
        <div class="cx-log" data-log></div>
        <div class="cx-ask" data-ask-bar>
          <div class="cx-ask-row"><input data-q autocomplete="off" placeholder="${esc(first.placeholder || w('ask_own'))}"/>
            <button type="button" class="cx-send" data-send>${icon('send', 15)} ${esc(w('ask'))}</button>
            <button type="button" class="cx-surprise" data-surprise title="${esc(w('surprise_tip'))}">${icon('sparkles', 15)}<span>${esc(w('surprise'))}</span></button></div>
          <p class="cx-hint" data-hint hidden></p>
          <div class="cx-examples" data-examples></div></div></div>
      <div data-train hidden></div></div>`, {
    wide: true, cls: 'as-modal-l',
    onOpen: (b) => {
      const log = b.querySelector('[data-log]');
      const box = b.querySelector('[data-q]');
      const err = (m) => { const e = b.querySelector('[data-err]'); e.hidden = !m; e.textContent = m || ''; };
      const hint = (m) => { const e = b.querySelector('[data-hint]'); e.hidden = !m; e.textContent = m || ''; };
      const examples = (d) => {
        if (d.placeholder) box.placeholder = d.placeholder;
        b.querySelector('[data-examples]').innerHTML = (d.examples || []).map((q) => `<button type="button" class="cx-ex" data-example="${esc(q)}">${esc(q)}</button>`).join('');
      };
      const fresh = () => api(`/api/chat/examples?screen=${encodeURIComponent(screen)}`).then(examples).catch(() => {});
      const draw = () => {
        log.innerHTML = st.msgs.map((m) => (m.who === 'you'
          ? `<div class="cx-you"><p>${esc(m.text)}<button type="button" class="cx-reuse" data-reuse="${esc(m.text)}" title="${esc(w('reuse'))}" aria-label="${esc(w('reuse'))}">${icon('rotcw', 15)}</button></p></div>`
          : `<div class="cx-chips">${replyHtml(m.reply)}</div>`)).join('') + (st.busy ? `<p class="cx-busy">${spinner(15)} ${esc(w('asking'))}</p>` : '');
        log.scrollTop = log.scrollHeight;
      };
      const ask = async (path, shown, body) => {
        if (st.busy) return;
        st.busy = true; err('');
        st.msgs.push({ who: 'you', text: shown }); draw();
        try { const r = await api(path, body ? { method: 'POST', body } : {}); st.msgs.push({ who: 'chips', reply: r }); }
        catch (e) { err(String(e.message || e)); }
        finally { st.busy = false; draw(); fresh(); }
      };
      const send = () => {
        const q = box.value.trim();
        if (!q) { hint(w('type_first')); return; }
        hint(''); box.value = '';
        ask('/api/chat/ask', q, { q });
      };
      b.querySelector('[data-send]').onclick = send;
      box.onkeydown = (e) => {
        if (e.key === 'Enter') send();
        // Tab (or → at the end) on an empty box takes the gray example question, as the studio's Chip Chat does
        else if ((e.key === 'Tab' || e.key === 'ArrowRight') && !box.value && box.placeholder && box.placeholder !== w('ask_own')) {
          e.preventDefault(); box.value = box.placeholder; hint('');
        }
      };
      b.querySelector('[data-surprise]').onclick = async () => {
        if (st.busy) return;
        try { const d = await api(`/api/chat/surprise?n=${st.presses}`); st.presses += 1; if (d.question) { hint(''); ask('/api/chat/ask', d.question, { q: d.question }); } }
        catch { hint(w('surprise_none')); }
      };
      b.querySelector('[data-reset]').onclick = () => (st.msgs.length
        ? confirmDialog(w('new_chat_q'), w('new_chat_body'), () => { st.msgs = []; err(''); draw(); fresh(); }, w('new_chat'), { tone: 'brand' })
        : err(w('already_empty')));
      b.addEventListener('click', (e) => {
        const x = e.target.closest('[data-example],[data-reuse],[data-eid],[data-ask],[data-go],[data-tab]');
        if (!x) return;
        if (x.dataset.example !== undefined) { box.value = x.dataset.example; hint(''); box.focus(); }
        else if (x.dataset.reuse !== undefined) { box.value = x.dataset.reuse; box.focus(); }
        else if (x.dataset.eid !== undefined) ask(`/api/chat/answer/${encodeURIComponent(x.dataset.eid)}`, x.textContent);
        else if (x.dataset.ask !== undefined) ask('/api/chat/ask', x.dataset.ask, { q: x.dataset.ask });
        else if (x.dataset.go !== undefined) b.closest('.backdrop').querySelector('[data-close]').click();
        else if (x.dataset.tab !== undefined) {
          b.querySelectorAll('[data-tab]').forEach((y) => y.classList.toggle('on', y === x));
          b.querySelector('[data-chat]').hidden = x.dataset.tab !== 'chat';
          b.querySelector('[data-reset]').hidden = x.dataset.tab !== 'chat';
          b.querySelector('[data-train]').hidden = x.dataset.tab !== 'train';
          if (x.dataset.tab === 'train') train(b.querySelector('[data-train]'), 'open');
        }
      });
      examples(first);
      draw();
      box.focus();
    } });
}

async function train(host, filter) {
  let d;
  try { d = await api('/api/chat/train'); } catch (e) { host.innerHTML = `<p class="cx-err">${esc(e.message)}</p>`; return; }
  const s = d.stats;
  const qOf = Object.fromEntries(d.entries.map((e) => [e.id, e.q]));
  const said = (r) => w(`r_${r}`).startsWith('[') ? r : w(`r_${r}`);
  host.innerHTML = `<div class="cx-train">
    <div class="cx-card cx-tbar">${icon('cap', 18)}<span>${esc(w('stats', { total: s.total, answered: s.answered, taught: s.taught }))}</span><span class="cx-fill"></span>
      <select data-filter>${d.filters.map((f) => `<option value="${f}" ${f === filter ? 'selected' : ''}>${esc(w(`f_${f}`))}</option>`).join('')}</select>
      <button type="button" class="as-btn" data-refresh>${icon('refresh', 14)}${esc(w('refresh'))}</button>
      <button type="button" class="as-btn" data-export>${icon('download', 14)}${esc(w('export_jsonl'))}</button>
      <button type="button" class="as-btn cx-amber" data-csv title="${esc(w('unanswered_tip'))}">${icon('download', 14)}${esc(w('unanswered_csv'))}</button></div>
    <datalist id="cx-answers">${d.entries.map((e) => `<option value="${esc(e.id)}">${esc(e.q)}</option>`).join('')}</datalist>
    <div class="cx-card cx-scroll" data-turns></div>
    <div class="cx-card"><h4>${esc(w('taught_head'))}</h4><p class="as-muted">${esc(w('taught_lede'))}</p><div data-taught></div></div>
    <div class="cx-card"><h4>${esc(w('own_title'))}</h4><div data-custom></div>
      <div class="cx-own"><input data-oq placeholder="${esc(w('own_q'))}" maxlength="300"/><input data-oa placeholder="${esc(w('own_a'))}" maxlength="3000"/>
        ${d.portal ? `<label class="cx-check"><input type="checkbox" data-portal/> ${esc(w('own_scope_all'))}</label>` : ''}
        <button type="button" class="as-btn as-dark" data-add-own>${icon('plus', 14)}${esc(w('own_add'))}</button></div></div></div>`;
  const again = () => train(host, host.querySelector('[data-filter]').value);
  const file = async (path, name, type) => {
    const r = await fetch(path, { credentials: 'same-origin' });
    const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([await r.text()], { type })); a.download = name; a.click();
  };
  host.querySelector('[data-filter]').onchange = again;
  host.querySelector('[data-refresh]').onclick = again;
  host.querySelector('[data-export]').onclick = () => file('/api/chat/export', 'chip_chat_pairs.jsonl', 'application/jsonl');
  host.querySelector('[data-csv]').onclick = () => file('/api/chat/unanswered.csv', 'chip_chat_unanswered.csv', 'text/csv');
  // the three lists, a searched page at a time: list.chat_turns (by filter), list.chat_taught, list.chat_custom
  listBox(host.querySelector('[data-turns]'), { list: 'chat_turns', args: { review: filter }, empty: w('nothing_to_review'),
    wrap: (html) => `<table class="cx-table"><thead><tr><th>${esc(w('h_question'))}</th><th>${esc(w('h_said'))}</th><th>${esc(w('h_answer'))}</th>
      <th>${esc(w('h_teach'))}</th><th>${esc(w('h_when'))}</th></tr></thead><tbody>${html}</tbody></table>`,
    row: (tn) => `<tr data-turn="${esc(tn.id)}" data-answer="${esc(tn.answer || '')}"><td><b>${esc(tn.q)}</b><span class="cx-sub">${esc(tn.role_label)}</span></td>
        <td><span class="cx-route cx-${esc(tn.route)}">${esc(said(tn.route))}</span>${tn.method ? `<span class="cx-sub">${esc(w(`m_${tn.method}`))}</span>` : ''}</td>
        <td>${tn.answer ? `<span class="cx-mono">${esc(qOf[tn.answer] || tn.answer)}</span>` : '-'}</td>
        <td><div class="cx-teach">${tn.answer && !tn.answer.startsWith('fam:') ? `<button type="button" class="cx-ok" data-right>${icon('okcircle', 14)} ${esc(w('right_answer'))}</button>` : ''}
          <input list="cx-answers" data-pick placeholder="${esc(w('or_answer_ph'))}"/><input data-own placeholder="${esc(w('own_answer_ph'))}"/>
          <button type="button" class="as-btn" data-teach>${esc(w('teach_btn'))}</button>
          <button type="button" class="as-btn" data-skip title="${esc(w('skip_tip'))}">${icon('skip', 14)}</button></div></td>
        <td class="cx-when">${esc(when(tn.at))}</td></tr>`,
    wire: (rows) => rows.querySelectorAll('[data-turn]').forEach((row) => {
      const id = row.dataset.turn;
      const teach = async (entry, answer) => {
        try { toast((await api(`/api/chat/train/${id}/teach`, { method: 'POST', body: { entry, answer, portal: !!(host.querySelector('[data-portal]') || {}).checked } })).say); again(); }
        catch (e) { toast(e.message, 'bad'); }
      };
      const right = row.querySelector('[data-right]');
      if (right) right.onclick = () => teach(row.dataset.answer, '');
      row.querySelector('[data-teach]').onclick = () => teach(row.querySelector('[data-pick]').value.trim(), row.querySelector('[data-own]').value.trim());
      row.querySelector('[data-skip]').onclick = async () => { await api(`/api/chat/train/${id}/skip`, { method: 'POST' }); again(); };
    }) });
  listBox(host.querySelector('[data-taught]'), { list: 'chat_taught', empty: w('taught_none'), wrap: (html) => `<ul class="cx-list">${html}</ul>`,
    row: (a) => `<li><span>${esc(a.phrase)}</span><span class="cx-mono">${esc(qOf[a.entry] || a.entry)}</span>
        <button type="button" class="as-row-x" data-del-taught="${esc(a.id)}" data-phrase="${esc(a.phrase)}">${icon('trash', 15)}</button></li>`,
    wire: (rows) => rows.querySelectorAll('[data-del-taught]').forEach((x) => { x.onclick = () => confirmDialog(w('delete_taught_q'), w('delete_taught_body', { phrase: x.dataset.phrase }), async () => { await api(`/api/chat/taught/${x.dataset.delTaught}`, { method: 'DELETE' }); again(); }, w('delete')); }) });
  listBox(host.querySelector('[data-custom]'), { list: 'chat_custom', empty: w('own_none'), wrap: (html) => `<ul class="cx-list">${html}</ul>`,
    row: (c) => `<li><span><b>${esc(c.q)}</b> - ${esc(c.a)}</span>
        <button type="button" class="as-row-x" data-del-own="${esc(c.id)}" data-phrase="${esc(c.q)}">${icon('trash', 15)}</button></li>`,
    wire: (rows) => rows.querySelectorAll('[data-del-own]').forEach((x) => { x.onclick = () => confirmDialog(w('delete'), x.dataset.phrase, async () => { await api(`/api/chat/custom/${x.dataset.delOwn}`, { method: 'DELETE' }); again(); }, w('delete')); }) });
  host.querySelector('[data-add-own]').onclick = async () => {
    try { await api('/api/chat/custom', { method: 'POST', body: { q: host.querySelector('[data-oq]').value, a: host.querySelector('[data-oa]').value, portal: !!(host.querySelector('[data-portal]') || {}).checked } }); again(); }
    catch (e) { toast(e.message, 'bad'); }
  };
}
