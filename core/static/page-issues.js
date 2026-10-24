// Reported issues - what people reported from any screen (Report an issue, core/issues.py), answered in the portal.
// 2026-09-28 owner: "We will not have email - we will have Report the way we have in TeDBook, notified back to the
// Portal Admin". 2026-10-03: one framework with reader feedback (kind `issue` of core/issues.py). The queue is list issues (core/lists.py): searched and paged; a reply reaches the reporter as a banner.
import { api, BASE, esc, say, modal, toast, busy, pageHead, t, loadWords, listBox, when, secretField, wireSecrets } from './ui.js';
import { refresh, state } from './shell.js';
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
          ${admin() && r.status === 'open' ? `<button type="button" class="small" data-push-open="${esc(r.id)}">${icon('share', 12)} ${esc(w('push'))}</button>` : ''}
          <button type="button" class="small" data-open="${esc(r.id)}">${icon('right', 12)} ${esc(r.status === 'open' ? w('resolve') : w('reopen'))}</button></div>
        <p class="small" style="margin:4px 0">${esc(r.text).slice(0, 400)}</p>
        <div class="small muted">${esc(w('where', { surface: r.surface, context: r.context }))}</div>
        ${r.reply ? `<div class="small muted">${esc(w('answered', { by: r.answered_by, at: when(r.updated), reply: r.reply }))}</div>` : ''}
        <div class="row tight small" data-pushed="${esc(r.id)}">${badges(r.pushed || [])}</div>
      </div>`,
    wire: (rows, page, reload) => {
      rows.querySelectorAll('[data-open]').forEach((b) => {
        b.onclick = () => answer(page.rows.find((x) => x.id === b.dataset.open), () => { reload(); refresh(); });
      });
      rows.querySelectorAll('[data-push-open]').forEach((b) => { b.onclick = () => pushTo(page.rows.find((x) => x.id === b.dataset.pushOpen), reload); });
      if (admin()) page.rows.filter((r) => (r.pushed || []).length).forEach((r) => follow(rows, r.id));
    } });
}

// --- Push to (2026-10-24 owner): the Portal Admin sends an issue to CodyFy as a request (core/push.py, chip issues.push) ---
const admin = () => (state.user || {}).role === 'owner';

function badges(items) {
  return items.map((p, i) => `<span class="tag brand" data-issue-pushed>${icon('share', 11)} ${esc(w('pushed', { target: p.label, ref: p.ref }))}<span data-push-stage="${i}">${p.stage ? ` · ${esc(p.stage)}` : ''}</span>
    ${p.link ? `<a href="${esc(p.link)}" target="_blank" rel="noopener" title="${esc(w('push_open', { target: p.label }))}">${icon('right', 11)}</a>` : ''}</span>`).join(' ');
}

async function follow(rows, iid) {
  try {
    const d = await api(`/api/core/issues/${encodeURIComponent(iid)}/push`);
    const box = rows.querySelector(`[data-pushed="${CSS.escape(iid)}"]`);
    d.pushed.forEach((p, i) => {   // text only - the badge itself stays as listed
      const at = box && box.querySelector(`[data-push-stage="${i}"]`);
      if (at) at.textContent = ` · ${p.why || p.stage || ''}`;
    });
  } catch { /* the stored stage stays shown */ }
}

async function pushTo(r, done, tid = '') {
  const m = await api('/api/core/issues/push');
  const pick = m.targets.find((x) => x.id === tid) || m.targets[0];
  const again = (tid) => (r.pushed || []).filter((p) => p.target === tid).slice(-1)[0];
  const before = again(pick.id);
  modal(w('push_title'), `<p class="small muted">${esc(w('push_lede'))}</p>
    <div class="field"><label>${esc(w('push_to'))}</label><div class="row tight" role="radiogroup">${m.targets.map((x) =>
      `<button type="button" role="radio" aria-checked="${x.id === pick.id}" data-push-target="${esc(x.id)}" class="${x.id === pick.id ? 'primary' : ''}">${esc(x.label)}</button>`).join('')}</div>
      <span class="small muted">${esc(pick.hint)} ${esc(w('push_company', { company: pick.company, project: pick.project }))}</span></div>
    ${pick.ready ? '' : `<p class="small" data-push-why>${esc(w('push_no_key', { target: pick.label }))}</p>
      ${secretField('push-key', w('push_key', { target: pick.label }), { hint: esc(w('push_key_hint', { target: pick.label })) })}
      <div class="row tight" style="margin:0 0 14px"><button type="button" id="push-key-save">${esc(w('push_key_save'))}</button></div>`}
    ${before ? `<p class="small" data-push-again>${esc(w('push_again', { target: before.label, ref: before.ref, at: when(before.at) }))}</p>` : ''}
    <div class="field"><label for="push-type">${esc(w('push_type'))}</label><select id="push-type" data-push-type>${pick.types.map((v) =>
      `<option value="${esc(v)}" ${v === pick.type ? 'selected' : ''}>${esc(w(`type_${v}`))}</option>`).join('')}</select></div>
    <div class="field"><label for="push-title">${esc(w('push_req_title'))}</label><input id="push-title" data-push-title value="${esc(r.title)}"/></div>
    <div class="field"><label for="push-text">${esc(w('push_text'))}</label><textarea id="push-text" rows="5" data-push-text>${esc(r.text)}</textarea></div>
    <div id="push-msg"></div>`, {
    wide: true,
    footer: `<button type="button" data-cancel>${esc(w('push_cancel'))}</button>
      <button type="button" class="primary" id="push-go" data-push-send>${icon('share', 13)} ${esc(w('push_send'))}</button>`,
    onOpen: (host, close) => {
      const card = host.closest('.modal');
      card.querySelector('[data-cancel]').onclick = close;
      wireSecrets(host);   // another target, or a key just kept: the dialog opens again on it (no page HTML rewritten)
      host.querySelectorAll('[data-push-target]').forEach((b) => { b.onclick = () => { close(); pushTo(r, done, b.dataset.pushTarget); }; });
      const keep = host.querySelector('#push-key-save');
      if (keep) keep.onclick = (e) => busy(e.currentTarget, async () => {
        try {
          const x = await api('/api/core/issues/push/key', { method: 'POST', body: { target: pick.id, key: host.querySelector('#push-key').value } });
          toast(x.message, 'ok', 6); close(); pushTo(r, done, pick.id);
        } catch (err) { say(host.querySelector('#push-msg'), 'bad', esc(err.message)); }
      });
      card.querySelector('#push-go').onclick = (e) => busy(e.currentTarget, async () => {
        try {
          const x = await api(`/api/core/issues/${encodeURIComponent(r.id)}/push`, { method: 'POST', body: {
            target: pick.id, type: host.querySelector('#push-type').value, title: host.querySelector('#push-title').value, text: host.querySelector('#push-text').value } });
          close(); toast(x.message, 'ok', 8); done();
        } catch (err) { say(host.querySelector('#push-msg'), 'bad', esc(err.message)); }
      });
    } });
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
