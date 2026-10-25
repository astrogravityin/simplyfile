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
          <b class="is-title">${esc(r.title)}</b><span class="muted">${esc(w('from', { name: r.name, email: r.email }))}</span>
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

// The road an issue takes, drawn: this issue (lit) -> request -> build machine -> pull request. Lucide-style glyphs, theme colours.
const FLOW = [
  ['push_flow_issue', '<circle cx="12" cy="12" r="9"/><path d="M12 7.5v5"/><path d="M12 16.2h.01"/>'],
  ['push_flow_request', '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="M9 13h6M9 17h4"/>'],
  ['push_flow_build', '<rect x="5" y="5" width="14" height="14" rx="2"/><rect x="9.5" y="9.5" width="5" height="5" rx="1"/><path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3"/>'],
  ['push_flow_pr', '<circle cx="6" cy="6" r="2.5"/><circle cx="18" cy="18" r="2.5"/><path d="M6 8.5V21"/><path d="M13 6h3a2 2 0 0 1 2 2v7.5"/><path d="m15.5 3.5-2.5 2.5 2.5 2.5"/>'],
];

function flow(target) {
  const x = (i) => 50 + i * 100;
  return `<figure class="push-flow" role="img" aria-label="${esc(w('push_flow_label', { target }))}">
    <svg viewBox="0 0 400 56" aria-hidden="true">
      ${FLOW.slice(1).map((_f, i) => `<path class="wire" d="M${x(i) + 26} 28H${x(i + 1) - 29}"/><path class="tip" d="m${x(i + 1) - 33} 24 4 4-4 4"/>`).join('')}
      ${FLOW.map(([_k, g], i) => `<g class="node${i ? '' : ' here'}">${i ? '' : `<circle class="halo" cx="${x(i)}" cy="28" r="25"/>`}
        <circle class="dot" cx="${x(i)}" cy="28" r="20"/><g class="glyph" transform="translate(${x(i) - 10.8} 17.2) scale(.9)">${g}</g></g>`).join('')}
    </svg>
    <figcaption>${FLOW.map(([k], i) => `<span class="${i ? '' : 'here'}">${esc(w(k))}</span>`).join('')}</figcaption></figure>`;
}

async function pushTo(r, done, tid = '') {
  const m = await api('/api/core/issues/push');
  const pick = m.targets.find((x) => x.id === tid) || m.targets[0];
  const before = (r.pushed || []).filter((p) => p.target === pick.id).slice(-1)[0];
  const T = { target: pick.label };
  const pill = (ready) => `<span class="tag ${ready ? 'ok' : 'warn'}" data-push-state>${icon(ready ? 'check' : 'plug', 11)} ${esc(w(ready ? 'push_ready' : 'push_not_ready'))}</span>`;
  const paste = `${secretField('push-key', w('push_key', T), { hint: esc(w('push_key_hint', T)) })}
      <button type="button" id="push-key-save">${icon('key', 13)} ${esc(w('push_key_save'))}</button>`;
  modal(w('push_title', T), `<p class="push-lede">${esc(w('push_lede', T))}</p>
    ${flow(pick.label)}
    <div class="push-dests" role="radiogroup" aria-label="${esc(w('push_to'))}">${m.targets.map((x) => `
      <button type="button" role="radio" class="push-dest${x.id === pick.id ? ' on' : ''}" aria-checked="${x.id === pick.id}" data-push-target="${esc(x.id)}">
        <span class="mark" aria-hidden="true">${esc(x.label.slice(0, 1))}</span>
        <span class="who"><b>${esc(x.label)}</b><span>${esc(w('push_company', { company: x.company, project: x.project }))}</span></span>
        ${x.id === pick.id ? pill(x.ready) : ''}</button>`).join('')}</div>
    ${pick.ready ? '' : `<section class="push-connect" data-push-connect>
      ${pick.connect ? `<div class="push-connect-row"><span class="ico">${icon('plug', 18)}</span><p>${esc(w('push_connect_lede', T))}</p>
        <button type="button" class="primary" id="push-connect" data-push-connect-go>${esc(w('push_connect', T))}</button></div>
        <details><summary>${esc(w('push_paste_instead'))}</summary>${paste}</details>` : paste}
      <div id="push-connect-msg"></div></section>`}
    ${before ? `<div id="push-again" data-push-again></div>` : ''}
    <div class="field"><label>${esc(w('push_type'))}</label><div class="tabs push-kinds" role="radiogroup" aria-label="${esc(w('push_type'))}">${pick.types.map((v) =>
      `<button type="button" role="radio" aria-checked="${v === pick.type}" class="${v === pick.type ? 'on' : ''}" data-push-type="${esc(v)}">${esc(w(`type_${v}`))}</button>`).join('')}</div></div>
    <div class="field"><label for="push-title">${esc(w('push_req_title'))}</label><input id="push-title" data-push-title value="${esc(r.title)}"/></div>
    <div class="field"><label for="push-text">${esc(w('push_text'))}</label><textarea id="push-text" rows="4" data-push-text>${esc(r.text)}</textarea></div>
    <div id="push-msg"></div>`, {
    cls: 'push-modal', stay: true,
    footer: `<button type="button" class="ghost" data-cancel>${esc(w('push_cancel'))}</button>
      <button type="button" class="primary" id="push-go" data-push-send>${icon('send', 14)} ${esc(w('push_send'))}</button>`,
    onOpen: (host, close) => {
      const card = host.closest('.modal');
      let kind = pick.type;
      const tell = (el, kind2, text) => { say(el, kind2, text); el.scrollIntoView({ block: 'nearest' }); };   // never below the fold
      card.querySelector('[data-cancel]').onclick = close;
      wireSecrets(host);
      if (before) say(host.querySelector('#push-again'), 'warn', esc(w('push_again', { target: before.label, ref: before.ref, at: when(before.at) })));
      host.querySelectorAll('[data-push-target]').forEach((b) => { if (b.dataset.pushTarget !== pick.id) b.onclick = () => { close(); pushTo(r, done, b.dataset.pushTarget); }; });
      host.querySelectorAll('[data-push-type]').forEach((b) => { b.onclick = () => {
        kind = b.dataset.pushType;
        host.querySelectorAll('[data-push-type]').forEach((o) => { o.classList.toggle('on', o === b); o.setAttribute('aria-checked', String(o === b)); });
      }; });
      const ready = (message) => {   // a key kept or Connect allowed: the step folds away, the rest of the form stays as typed
        pick.ready = true;
        host.querySelector('[data-push-connect]')?.remove();
        host.querySelector('[data-push-state]').outerHTML = pill(true);
        say(host.querySelector('#push-msg'), '', '');
        toast(message, 'ok', 6);
      };
      const go = host.querySelector('#push-connect');
      if (go) go.onclick = async () => {
        const win = window.open('about:blank', 'push-connect', 'width=520,height=720');
        const msg = host.querySelector('#push-connect-msg');
        if (!win) { tell(msg, 'bad', esc(w('push_popup_blocked'))); return; }
        try {
          const x = await api('/api/core/issues/push/connect', { method: 'POST', body: { target: pick.id } });
          win.location = x.url;
          tell(msg, 'info', esc(w('push_connect_wait', T)));
          const ch = new BroadcastChannel('push-connect');   // the window's last page is on this site: it says how it went
          ch.onmessage = (e) => { ch.close(); if (e.data.push_connect) ready(w('push_connect_done', T)); else tell(msg, 'bad', esc(e.data.message)); };
        } catch (err) { win.close(); tell(msg, 'bad', esc(err.message)); }
      };
      const keep = host.querySelector('#push-key-save');
      if (keep) keep.onclick = (e) => busy(e.currentTarget, async () => {
        try {
          const x = await api('/api/core/issues/push/key', { method: 'POST', body: { target: pick.id, key: host.querySelector('#push-key').value } });
          ready(x.message);
        } catch (err) { tell(host.querySelector('#push-connect-msg'), 'bad', esc(err.message)); }
      });
      card.querySelector('#push-go').onclick = (e) => {
        if (!pick.ready) {   // never greyed: a press before Connect says what to do and points at it
          tell(host.querySelector('#push-connect-msg'), 'bad', esc(w('push_no_key', T)));   // said inside the step it points at
          (go || host.querySelector('#push-key'))?.focus();
          return;
        }
        busy(e.currentTarget, async () => {
          try {
            const x = await api(`/api/core/issues/${encodeURIComponent(r.id)}/push`, { method: 'POST', body: {
              target: pick.id, type: kind, title: host.querySelector('#push-title').value, text: host.querySelector('#push-text').value } });
            close(); toast(x.message, 'ok', 8); done();
          } catch (err) { tell(host.querySelector('#push-msg'), 'bad', esc(err.message)); }
        });
      };
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
