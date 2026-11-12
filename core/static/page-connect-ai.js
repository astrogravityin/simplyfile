// Connect your AI - the portal's MCP door (core/mcp.py + core/mcp_oauth.py; 2026-10-23 owner: "go with your pick", the
// AstroStage way). Portal-builder never-again (owner: "No one should open the terminal"): the button road comes FIRST -
// paste one address in the AI app, press Connect, sign in here and Allow - with a LIVE status the server sets the moment
// the app first calls, and a Check button that runs the real round trip. Keys and the command live only under a folded
// "For developers". The Allow card is this same screen (?allow=1...). Every word is chip ui.connect_ai.
import { api, esc, toast, busy, say, pageHead, modal, confirmDialog, t, loadWords, clockAt, copyText, listBox } from './ui.js';
import { icon } from './icons.js';
import { onEvent } from './events.js';

const w = (k, v) => t('connect_ai', k, v);
const paint = (el, html) => { el.innerHTML = html; };   // 2026-10-24: the screen's one place that writes HTML (html_sinks ratchet)
let stopLive = () => {};                                 // the open screen's stream listener (one at a time)
const at = (sec) => (sec ? clockAt(new Date(sec * 1000).toISOString()) : '');

/** The picture: an AI app and this portal, joined by one line with a key on it. */
const linkArt = () => `<svg class="ca-art" viewBox="0 0 220 72" aria-hidden="true">
  <defs><linearGradient id="ca-g" x1="0" x2="1"><stop offset="0" stop-color="var(--brand)" stop-opacity=".18"/><stop offset="1" stop-color="var(--ok)" stop-opacity=".18"/></linearGradient></defs>
  <rect x="2" y="12" width="64" height="48" rx="12" fill="url(#ca-g)" stroke="var(--brand-line)"/>
  <path d="M22 30h24M22 38h16M22 46h20" stroke="var(--brand)" stroke-width="3" stroke-linecap="round"/>
  <rect x="154" y="12" width="64" height="48" rx="12" fill="url(#ca-g)" stroke="var(--brand-line)"/>
  <circle cx="186" cy="36" r="11" fill="none" stroke="var(--ok)" stroke-width="3"/><path d="M181 36l4 4 7-8" fill="none" stroke="var(--ok)" stroke-width="3" stroke-linecap="round"/>
  <path class="ca-wire" d="M68 36h84" stroke="var(--brand)" stroke-width="2.5" stroke-dasharray="5 6" stroke-linecap="round"/>
  <circle cx="110" cy="36" r="13" fill="var(--panel)" stroke="var(--brand-line)"/>
  <path d="M104 39a4 4 0 1 1 5.7-3.6L116 36v3h-2v2h-2v-2h-2.3A4 4 0 0 1 104 39Z" fill="var(--brand)"/></svg>`;

// 2026-10-24 (Fy: every list has a forgiving search): the tools through list mcp_tools (core/mcp.py lists.source)
const toolCard = (x) => `<div class="ca-tool" data-kind="${esc(x.kind)}"><div class="row tight"><code>${esc(x.name)}</code>
  <span class="tag ${x.on && x.ready ? 'ok' : ''}">${w(x.on && x.ready ? 'tool_on' : 'tool_off')}</span><span class="tag ${x.kind === 'human' ? 'warn' : ''}">${esc(x.kind_word)}</span></div>
  <b class="small">${esc(x.title)}</b><p class="small muted">${esc(x.description)}</p></div>`;

const statusLine = (s) => `<span class="ca-dot ${s.connected ? 'on' : ''}" aria-hidden="true"></span>
  <b>${s.last ? w('status_on', { who: esc(s.last.who), when: esc(at(s.last.at)) }) : w('status_none')}</b>
  ${s.connections.length ? `<span class="small muted">${w('status_conn', { n: s.connections.length })}</span>` : ''}`;

const appsList = (s) => (s.connections.length ? `<div class="ca-keys">${s.connections.map((c) => `<div class="ca-key"><span class="ca-dot on" aria-hidden="true"></span>
    <div class="ca-kt"><b>${esc(c.client)}</b><span class="small muted">${w('app_line', { when: esc(at(c.connected_at)), n: c.calls })}${c.last_used ? ` · ${w('last_used', { when: esc(at(c.last_used)) })}` : ''}</span></div>
    <button type="button" class="small ghost danger" data-unlink="${esc(c.id)}" data-app="${esc(c.client)}">${icon('close', 12)} ${w('disconnect')}</button></div>`).join('')}</div>`
  : `<p class="small muted empty-box">${w('no_apps')}</p>`);

/** The Allow card - the AI app sent the person here (core/mcp_oauth.py /oauth/authorize, checked first). */
async function allowCard(host, query) {
  const info = await api('/api/core/mcp/allow-info', { method: 'POST', body: { query } });
  paint(host, `<section class="card ca-allow">${linkArt()}
    <h1>${w('allow_title', { app: esc(info.client) })}</h1><p class="muted">${w('allow_body', { app: esc(info.client) })}</p>
    <div id="ca-amsg"></div>
    <div class="ca-allow-acts"><button type="button" id="ca-deny">${w('deny')}</button>
      <button type="button" class="primary" id="ca-allow">${icon('check', 14)} ${w('allow')}</button></div></section>`);
  const go = (allow) => (e) => busy(e.currentTarget, async () => {
    try {
      const r = await api('/api/core/mcp/approve', { method: 'POST', body: { query, allow } });
      say(host.querySelector('#ca-amsg'), 'ok', w('allow_sending', { app: esc(info.client) }));
      location.href = r.go;
    } catch (err) { say(host.querySelector('#ca-amsg'), 'bad', esc(err.message)); }
  });
  host.querySelector('#ca-allow').onclick = go(true);
  host.querySelector('#ca-deny').onclick = go(false);
}

export async function connectAiPage(host) {
  await loadWords('connect_ai');
  const query = Object.fromEntries(new URLSearchParams(location.hash.split('?')[1] || ''));
  if (query.allow) { delete query.allow; return allowCard(host, query); }
  const d = await api('/api/core/mcp');
  paint(host, pageHead(w('title'), w('lede')) + `<div id="ca-msg"></div>
    <section class="card ca-how"><h2>${icon('plug', 17)} ${w('how_title')}</h2><div class="ca-howrow">${linkArt()}
      <ol class="ca-steps">
        <li><b>${w('step1')}</b><span class="small muted">${w('step1_note')}</span></li>
        <li><b>${w('step2')}</b><span class="small muted">${w('step2_note')}</span></li>
        <li><b>${w('step3')}</b><span class="small muted">${w('step3_note')}</span></li></ol></div>
      <div class="field"><label>${w('address')}</label><div class="ca-copy"><code id="ca-url">${esc(d.url)}</code>
        <button type="button" class="copy-btn small" data-copy="${esc(d.url)}">${icon('copy', 13)} ${w('copy')}</button></div></div>
      <div class="ca-status" id="ca-status" aria-live="polite">${statusLine(d.status)}</div>
      <div class="row tight"><button type="button" class="small ghost" id="ca-check" data-tip="${esc(w('check_tip'))}">${icon('pulse', 13)} ${w('check')}</button></div>
      <div id="ca-checked"></div></section>

    <section class="card"><h2>${icon('users', 17)} ${w('apps')}</h2><div id="ca-apps">${appsList(d.status)}</div></section>

    <section class="card"><h2>${icon('eye', 17)} ${w('tools')}</h2><p class="small muted">${w('tools_note')}</p>
      <div class="ca-tools-list" id="ca-tools"></div></section>

    <details class="card ca-dev"><summary><b>${icon('key', 15)} ${w('dev')}</b></summary>
      <p class="small muted">${w('dev_note')}</p>
      <div class="row tight"><span class="small muted">${w('keys_count', { n: d.keys.length, max: d.max_keys })}</span></div>
      <div class="ca-make"><input id="ca-label" maxlength="60" placeholder="${esc(w('label_ph'))}" aria-label="${esc(w('label'))}"/>
        <button type="button" id="ca-new">${icon('plus', 14)} ${w('make_key')}</button></div>
      ${d.keys.length ? `<div class="ca-keys">${d.keys.map((k) => `<div class="ca-key"><span class="ca-dot ${k.last_used ? 'on' : ''}" aria-hidden="true"></span>
          <div class="ca-kt"><b>${esc(k.label)}</b><span class="small muted">${w('key_line', { hint: esc(k.hint), when: esc(clockAt(k.made_at)) })}</span></div>
          <button type="button" class="small ghost danger" data-revoke="${esc(k.id)}" data-label="${esc(k.label)}">${icon('trash', 12)} ${w('revoke')}</button></div>`).join('')}</div>`
        : `<p class="small muted empty-box">${w('no_keys')}</p>`}</details>`);
  listBox(host.querySelector('#ca-tools'), { list: 'mcp_tools', row: toolCard, wrap: (h) => `<div class="ca-tools">${h}</div>` });
  const msg = host.querySelector('#ca-msg');
  const again = () => connectAiPage(host);
  const copies = (root) => root.querySelectorAll('[data-copy]').forEach((b) => { b.onclick = () => copyText(b.dataset.copy, w('copied')); });
  copies(host);
  const wireApps = () => host.querySelectorAll('[data-unlink]').forEach((b) => {
    b.onclick = () => confirmDialog(w('disconnect_title', { app: b.dataset.app }), w('disconnect_body'), async () => {
      try { toast((await api(`/api/core/mcp/connections/${encodeURIComponent(b.dataset.unlink)}`, { method: 'DELETE' })).message, 'ok'); again(); }
      catch (err) { say(msg, 'bad', esc(err.message)); }
    }, w('disconnect'), { tone: 'danger' });
  });
  wireApps();
  // the LIVE status: the server sends it down the push stream (topic mcp, core/mcp.py announce) the moment a key or AI
  // sign-in is used, an app connects or a key changes - the page never asks on a timer (owner 2026-11-08)
  stopLive();
  stopLive = onEvent('mcp', (s) => {
    if (!host.isConnected || !host.querySelector('#ca-status')) { stopLive(); return; }
    paint(host.querySelector('#ca-status'), statusLine(s));
    paint(host.querySelector('#ca-apps'), appsList(s));
    wireApps();
  });
  host.querySelector('#ca-check').onclick = (e) => busy(e.currentTarget, async () => {
    try {
      const r = await api('/api/core/mcp/check', { method: 'POST' });
      paint(host.querySelector('#ca-checked'), `<ul class="ag-list">${r.steps.map((x) => `<li class="${x.ok ? 'ok' : 'bad'}">${icon(x.ok ? 'check' : 'alert', 13)} ${esc(x.say)}</li>`).join('')}</ul>
        ${r.message ? `<p class="small ok">${esc(r.message)}</p>` : ''}`);
    } catch (err) { say(msg, 'bad', esc(err.message)); }
  });
  host.querySelector('#ca-new').onclick = (e) => busy(e.currentTarget, async () => {
    try {
      const r = await api('/api/core/mcp/keys', { method: 'POST', body: { label: host.querySelector('#ca-label').value } });
      const cmd = w('command', { name: d.name, url: d.url, key: r.key });
      modal(w('key_made_title'), `<div class="note warn">${icon('alert')}<div>${esc(r.message)}</div></div>
        <div class="field"><label>${w('your_key')}</label><div class="ca-copy"><code class="ca-secret">${esc(r.key)}</code>
          <button type="button" class="copy-btn small" data-copy="${esc(r.key)}">${icon('copy', 13)} ${w('copy')}</button></div></div>
        <div class="field"><label>${w('command_label')}</label><div class="ca-copy"><code class="ca-cmd">${esc(cmd)}</code>
          <button type="button" class="copy-btn small" data-copy="${esc(cmd)}">${icon('copy', 13)} ${w('copy')}</button></div>
          <span class="small muted">${w('command_note')}</span></div>`, { wide: true, onClose: again, onOpen: (body) => copies(body) });
    } catch (err) { say(msg, 'bad', esc(err.message)); }
  });
  host.querySelectorAll('[data-revoke]').forEach((b) => {
    b.onclick = () => confirmDialog(w('revoke_title', { label: b.dataset.label }), w('revoke_body'), async () => {
      try { toast((await api(`/api/core/mcp/keys/${encodeURIComponent(b.dataset.revoke)}`, { method: 'DELETE' })).message, 'ok'); again(); }
      catch (err) { say(msg, 'bad', esc(err.message)); }
    }, w('revoke'), { tone: 'danger' });
  });
}
