// Reported issues - what people reported from any screen (Report an issue, core/issues.py), answered in the portal.
// 2026-09-28 owner: "We will not have email - we will have Report the way we have in TeDBook, notified back to the
// Portal Admin". 2026-10-03: one framework with reader feedback (kind `issue` of core/issues.py). The queue is list issues (core/lists.py): searched and paged; a reply reaches the reporter as a banner.
import { api, BASE, esc, say, modal, toast, busy, pageHead, t, loadWords, listBox, when } from './ui.js';
import { refresh } from './shell.js';
import { icon } from './icons.js';

const w = (k, v) => t('issues', k, v);
let status = 'open';

export async function issuesPage(host) {
  await loadWords('issues');
  host.innerHTML = `${pageHead(w('title'), w('lede'))}
    <div class="tabs" role="tablist">${[['open', w('open')], ['resolved', w('resolved')], ['', w('all')]].map(([id, label]) =>
      `<button type="button" role="tab" data-st="${id}" class="${status === id ? 'on' : ''}">${esc(label)}</button>`).join('')}</div>
    <div class="card" id="is-list"></div>`;
  host.querySelectorAll('[data-st]').forEach((b) => { b.onclick = () => { status = b.dataset.st; issuesPage(host); }; });
  listBox(host.querySelector('#is-list'), { list: 'issues', args: { status }, empty: w('none'),
    row: (r) => `<div class="lent-row" style="display:block;padding:8px 0">
        <div class="row tight small"><span class="tag ${r.status === 'open' ? 'warn' : 'ok'}">${esc(r.status === 'open' ? w('open') : w('resolved'))}</span>
          <b>${esc(r.title)}</b><span class="muted">${esc(w('from', { name: r.name, email: r.email }))}</span>
          <span class="spacer"></span><span class="small muted">${esc(w('filed', { at: when(r.at) }))}</span>
          <button type="button" class="small" data-open="${esc(r.id)}">${icon('right', 12)} ${esc(r.status === 'open' ? w('resolve') : w('reopen'))}</button></div>
        <p class="small" style="margin:4px 0">${esc(r.text).slice(0, 400)}</p>
        <div class="small muted">${esc(w('where', { surface: r.surface, context: r.context }))}</div>
        ${r.reply ? `<div class="small muted">${esc(w('answered', { by: r.answered_by, at: when(r.updated), reply: r.reply }))}</div>` : ''}
      </div>`,
    wire: (rows, page, reload) => rows.querySelectorAll('[data-open]').forEach((b) => {
      b.onclick = () => answer(page.rows.find((x) => x.id === b.dataset.open), () => { reload(); refresh(); });
    }) });
}

function answer(r, done) {
  const reopen = r.status !== 'open';
  modal(r.title, `<p class="small muted">${esc(w('from', { name: r.name, email: r.email }))} · ${esc(w('where', { surface: r.surface, context: r.context }))}</p>
    <p style="white-space:pre-wrap">${esc(r.text)}</p>
    ${r.shot ? `<p class="small"><b>${esc(w('shot'))}</b></p><img src="${BASE}/api/core/issues/${encodeURIComponent(r.id)}/shot" alt="" style="max-width:100%;border-radius:8px"/>` : ''}
    ${reopen ? '' : `<div class="field"><label for="is-reply">${esc(w('reply'))}</label><textarea id="is-reply" rows="4"></textarea></div>`}
    <div id="is-msg"></div>`, {
    wide: true,
    footer: `<button type="button" data-cancel>${esc(t('shell', 'cancel_report'))}</button>
      <button type="button" class="primary" id="is-go">${esc(reopen ? w('reopen') : w('resolve'))}</button>`,
    onOpen: (body, close) => {
      const card = body.closest('.modal');
      card.querySelector('[data-cancel]').onclick = close;
      card.querySelector('#is-go').onclick = (e) => busy(e.currentTarget, async () => {
        try {
          const x = await api(`/api/core/issues/${encodeURIComponent(r.id)}`, { method: 'POST', body: {
            status: reopen ? 'open' : 'resolved', reply: reopen ? '' : body.querySelector('#is-reply').value } });
          close(); toast(x.message, 'ok', 8); done();
        } catch (err) { say(body.querySelector('#is-msg'), 'bad', esc(err.message)); }
      });
    } });
}
