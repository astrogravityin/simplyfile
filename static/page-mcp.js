// Admin > Agent & MCP (2026-10-23 owner, core/mcp_door.py): the Portal Admin's key for Claude Code on their laptop - made here, shown
// once inside the one line to paste (claude mcp add ...), kept by the server as a fingerprint only - and the tools Claude may use
// (chip mcp.tools: each one of this portal's own routes; the person's steps marked as such). Words: chip ui.mcp.
import { api, esc, toast, busy, pageHead, t, loadWords, when, confirmDialog, modal, copyText, listBox } from './app.js';
import { icon } from './icons.js';

const w = (k, v) => t('mcp', k, v);
const KIND_ICON = { read: 'eye', change: 'edit', human: 'user' };

// One picture of the road: Claude Code on the laptop -> the owner key -> the door -> the portal's own screens; a person's lane under it.
const GLYPH = {
  laptop: `<rect x="12" y="14" width="40" height="27" rx="4" fill="var(--panel-2)" stroke="var(--brand)" stroke-width="2.4"/>
    <path d="M6 47h52" stroke="var(--brand)" stroke-width="3.2" stroke-linecap="round"/>
    <path d="M32 21l2.6 6.4L41 30l-6.4 2.6L32 39l-2.6-6.4L23 30l6.4-2.6z" fill="var(--brand)"/>`,
  key: `<circle cx="22" cy="32" r="9" fill="none" stroke="var(--warn)" stroke-width="3"/><circle cx="22" cy="32" r="3" fill="var(--warn)"/>
    <path d="M31 32h22M46 32v7M52 32v5" stroke="var(--warn)" stroke-width="3" stroke-linecap="round"/>`,
  door: `<path d="M32 8l20 7v15c0 13-9 22-20 26C21 52 12 43 12 30V15z" fill="var(--brand-soft)" stroke="var(--brand)" stroke-width="2.4" stroke-linejoin="round"/>
    <path d="M23 31l6 6 12-13" fill="none" stroke="var(--ok)" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"/>`,
  screens: `<rect x="18" y="10" width="34" height="24" rx="4" fill="var(--panel-2)" stroke="var(--line)" stroke-width="2"/>
    <rect x="12" y="18" width="34" height="24" rx="4" fill="var(--panel-2)" stroke="var(--line-2)" stroke-width="2"/>
    <rect x="6" y="26" width="34" height="24" rx="4" fill="var(--panel)" stroke="var(--brand)" stroke-width="2.4"/>
    <path d="M12 34h18M12 40h12" stroke="var(--ink-2)" stroke-width="2.4" stroke-linecap="round"/><circle cx="48" cy="50" r="7" fill="var(--ok)"/>
    <path d="M45 50l2 2 4-4" fill="none" stroke="var(--panel)" stroke-width="2" stroke-linecap="round"/>`,
  person: `<circle cx="32" cy="22" r="9" fill="var(--panel-2)" stroke="var(--ink-2)" stroke-width="2.4"/>
    <path d="M14 52c2-11 9-17 18-17s16 6 18 17" fill="var(--panel-2)" stroke="var(--ink-2)" stroke-width="2.4" stroke-linecap="round"/>`,
};
const glyph = (k) => `<svg viewBox="0 0 64 64" aria-hidden="true">${GLYPH[k]}</svg>`;
const flow = `<svg class="mcp-flow" viewBox="0 0 80 12" preserveAspectRatio="none" aria-hidden="true"><path d="M2 6H78" stroke="var(--brand)" stroke-width="2.4"
  stroke-dasharray="6 5" fill="none"><animate attributeName="stroke-dashoffset" from="22" to="0" dur="1.2s" repeatCount="indefinite"/></path></svg>`;
const node = (k, title, sub, cls = '') => `<div class="mcp-node ${cls}"><span class="mcp-glyph">${glyph(k)}</span><span class="mcp-nt"><b>${esc(title)}</b><span class="small muted">${esc(sub)}</span></span></div>`;

function art() {
  return `<section class="card mcp-art" id="mcp-art" aria-label="${esc(w('title'))}"><div class="mcp-road">
      ${node('laptop', w('art_you'), w('art_you_sub'))}${flow}${node('key', w('art_key'), w('art_key_sub'), 'mcp-keynode')}${flow}
      ${node('door', w('art_door'), w('art_door_sub'), 'mcp-door')}${flow}${node('screens', w('art_screens'), w('art_screens_sub'))}</div>
    <div class="mcp-human">${glyph('person')}<div><b>${esc(w('art_human'))}</b><p class="small muted">${esc(w('art_human_sub'))}</p></div></div></section>`;
}

function keyCard(d) {
  const k = d.key;
  const state = k ? `<p class="mcp-hint">${icon('key', 15)} ${esc(w('key_has', { hint: `…${k.hint}`, made: when(k.made_at) }))}</p>
      <p class="small muted">${icon('clock', 12)} ${esc(k.used_at ? w('key_used', { when: when(k.used_at), n: k.uses }) : w('key_unused'))}</p>`
    : `<p class="muted">${esc(w('key_none'))}</p>`;
  return `<section class="card mcp-key" id="mcp-key"><h3>${icon('shield', 16)} ${esc(w('key_title'))}</h3>${state}
    <div class="row tight"><button type="button" class="primary" id="mcp-make">${icon(k ? 'refresh' : 'key', 14)} ${esc(w(k ? 'remake' : 'make'))}</button>
      ${k ? `<button type="button" class="danger ghost" id="mcp-del">${icon('trash', 14)} ${esc(w('delete'))}</button>` : ''}</div></section>`;
}

function stepsCard(d) {
  return `<section class="card mcp-steps" id="mcp-steps"><h3>${icon('olist', 16)} ${esc(w('steps_title'))}</h3>
    <ol class="mcp-ol">${[1, 2, 3].map((n) => `<li>${esc(w(`step${n}`))}</li>`).join('')}</ol>
    <p class="small muted">${esc(w('cmd_label', { key_here: w('key_here') }))}</p>
    <div class="mcp-cmd"><code id="mcp-cmd">${esc(d.command)}</code><button type="button" class="ghost small" id="mcp-copy">${icon('copy', 13)} ${esc(w('copy'))}</button></div></section>`;
}

const toolRow = (r) => `<div class="mcp-tool k-${esc(r.kind)}" data-kind="${esc(r.kind)}"><span class="mcp-ti" aria-hidden="true">${icon(KIND_ICON[r.kind] || 'info', 15)}</span>
  <div class="grow"><div class="mcp-tn"><code>${esc(r.name)}</code> <b>${esc(r.title)}</b> <span class="tag ${r.kind === 'human' ? 'warn' : r.kind === 'change' ? '' : 'ok'}">${esc(r.kind_word)}</span></div>
    <p class="small">${esc(r.say)}</p>${r.calls.length ? `<p class="small muted mcp-calls">${r.calls.map((c) => `<code>${esc(c)}</code>`).join(' ')}</p>` : ''}</div></div>`;

function shownOnce(line) {
  modal(w('made_title'), `<p>${esc(w('made_lede'))}</p><div class="mcp-cmd mcp-once"><code>${esc(line)}</code></div>
    <p class="note warn small">${icon('alert', 13)} ${esc(w('made_warn'))}</p>`, {
    // 2026-10-23: plain buttons - a pill takes its colour from --tone, set only in a confirm dialog (here "I copied it" was white on white)
    footer: `<button type="button" data-copy-once>${icon('copy', 14)} ${esc(w('copy'))}</button><button type="button" class="primary" data-done>${icon('check', 14)} ${esc(w('made_done'))}</button>`,
    onOpen: (body, close) => {
      const card = body.closest('.modal');
      card.querySelector('[data-copy-once]').onclick = () => copyText(line);
      card.querySelector('[data-done]').onclick = () => close();
    },
  });
}

export async function mcpPage(host) {
  await loadWords('mcp');
  const d = await api('/api/mcp');
  const c = d.counts;
  host.innerHTML = pageHead(w('title'), esc(w('lede'))) + art()      // the screen's one place that draws (ratchet: html_sinks)
    + `<div class="mcp-grid">${keyCard(d)}${stepsCard(d)}</div>
    <section class="card mcp-tools" id="mcp-tools"><h3>${icon('list', 16)} ${esc(w('tools_title'))}</h3>
      <p class="small muted">${esc(w('tools_lede'))} ${esc(w('tools_count', c))}</p><div class="mcp-list"></div></section>`;
  listBox(host.querySelector('.mcp-list'), { list: 'mcp_tools', row: toolRow });
  host.querySelector('#mcp-copy').onclick = () => copyText(d.command);
  const make = (b) => busy(b, async () => {
    try { const r = await api('/api/mcp/key', { method: 'POST', body: {} }); await mcpPage(host); shownOnce(r.once); } catch (err) { toast(err.message, 'bad', 8); }
  });
  host.querySelector('#mcp-make').onclick = (e) => {
    const b = e.currentTarget;
    if (d.key) confirmDialog(w('remake_title'), w('remake_msg'), () => make(b), w('remake_yes'), { tone: 'warn' });
    else make(b);
  };
  const del = host.querySelector('#mcp-del');
  if (del) del.onclick = () => confirmDialog(w('del_title'), w('del_msg'), async () => {
    try { await api('/api/mcp/key', { method: 'DELETE' }); toast(w('deleted')); mcpPage(host); } catch (err) { toast(err.message, 'bad', 8); }
  });
}
