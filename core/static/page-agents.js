// Agents - helpers that do routine work (core/agents.py; 2026-10-23 owner: "go with your pick", the AstroStage way).
// Each card: what the agent does, its steps as a little flow (what each touches), its trigger switch, the last run, and
// Dry run / Approve / History. Every word is chip ui.agents; every decision (what runs, what is only previewed, what
// waits for approval) is the server's chips - this page only draws what it is given.
import { api, esc, toast, busy, say, pageHead, modal, t, loadWords, clockAt } from './ui.js';
import { icon } from './icons.js';

const w = (k, v) => t('agents', k, v);
const at = (sec) => (sec ? clockAt(new Date(sec * 1000).toISOString()) : '');
const STATE = { done: 'ok', failed: 'bad', running: 'warn' };

/** The card's picture: the agent's icon in a soft ring, with a small pulse when it runs by itself. */
const art = (a, live) => `<div class="ag-art" aria-hidden="true"><svg viewBox="0 0 64 64">
    <defs><linearGradient id="ag-g-${esc(a.id)}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="var(--brand)" stop-opacity=".24"/>
      <stop offset="1" stop-color="var(--brand)" stop-opacity=".05"/></linearGradient></defs>
    <circle cx="32" cy="32" r="30" fill="url(#ag-g-${esc(a.id)})" stroke="var(--brand-line)"/>
    <circle cx="32" cy="32" r="20" fill="var(--panel)" stroke="var(--brand-line)"/>
    <path d="M32 4a28 28 0 0 1 24.2 14" fill="none" stroke="var(--brand)" stroke-width="2.5" stroke-linecap="round"/>
    ${live ? '<circle class="ag-pulse" cx="53" cy="13" r="5" fill="var(--ok)"/>' : ''}</svg>
    <span class="ag-ico">${icon(a.icon, 22)}</span></div>`;

/** A schedule's clock time is kept in UTC; the person reads it in their own zone (core clockAt names the zone). */
function localAt(hhmm) {
  const [h, m] = String(hhmm || '00:00').split(':').map(Number);
  const d = new Date();
  d.setUTCHours(h, m, 0, 0);
  return clockAt(d.toISOString());
}

function when(tg) {
  if (tg.kind === 'event') {   // a trigger may name itself (event_<event>_<key>) when one agent listens for one event twice
    const own = `event_${tg.event.replace('.', '_')}_${tg.key}`;
    return w('on_event', { event: w(w(own).startsWith('[agents.') ? `event_${tg.event.replace('.', '_')}` : own) });
  }
  const days = w('days').split(',');
  if (tg.every === 'tick') return w('every_tick', { min: Math.round((tg.seconds || 60) / 60) });   // 2026-10-24: every few minutes
  if (tg.every === 'month') return w('every_month', { day: tg.day || 1, at: localAt(tg.at) });
  return tg.every === 'hour' ? w('every_hour') : tg.every === 'week' ? w('every_week', { day: days[tg.weekday || 0], at: localAt(tg.at) })
    : w('every_day', { at: localAt(tg.at) });
}

function lastLine(r) {
  if (!r) return `<span class="small muted">${w('no_runs')}</span>`;
  const st = r.waiting ? 'waiting' : r.phase === 'preview_approved' ? 'approved' : r.status;
  return `<span class="tag ${r.waiting ? 'warn' : STATE[r.status] || ''}">${w(`state_${st}`)}</span>
    <span class="small muted">${w('last_run', { when: esc(at(r.made)) })} · ${w(r.by_id ? 'by_you' : 'by_itself')}</span>`;
}

/** What a step found, in plain rows: a list of {name, say} (health problems) reads as a list; any other answer as
 *  label: value pairs. Nothing the server marked private ("_" keys) ever reaches here. */
function found(out) {
  const rows = [];
  const has = (k) => !w(k).startsWith('[agents.');          // only answers that have words of their own are shown
  Object.entries(out || {}).forEach(([k, v]) => {
    if (Array.isArray(v) && v.length && typeof v[0] === 'object') {
      rows.push(`<ul class="ag-list">${v.map((x) => `<li class="${x.ok === false ? 'bad' : x.ok ? 'ok' : ''}">${icon(x.ok === false ? 'alert' : 'check', 13)}
        <b>${esc(x.name || x.id || '')}</b> <span class="muted">${esc(x.say || '')}</span></li>`).join('')}</ul>`);
    } else if (!Array.isArray(v) && typeof v !== 'object' && has(`out_${k}`) && v !== '') {
      rows.push(`<div class="small"><span class="muted">${esc(w(`out_${k}`))}:</span> ${esc(typeof v === 'boolean' ? w(v ? 'yes' : 'no') : String(v))}</div>`);
    }
  });
  return rows.join('');
}

function runBox(r) {
  if (!r) return '';
  return `<div class="ag-run">
    ${r.why && r.status === 'failed' ? `<div class="note bad">${icon('alert')}<div>${esc(r.why)}</div></div>` : ''}
    ${r.steps.map((s) => `<div class="ag-runstep"><div class="row tight"><span class="tag ${s.gate === 'run' ? 'ok' : s.gate === 'preview' ? 'warn' : ''}">${w(`gate_${s.gate}`)}</span>
      <b class="small">${w(`act_${s.action.replace('.', '_')}`)}</b></div>${s.error ? `<div class="small bad">${esc(s.error)}</div>` : found(s.out)}</div>`).join('')}
  </div>`;
}

function agentCard(a) {
  const live = a.triggers.some((tg) => tg.on);
  const r = a.last;
  return `<section class="card ag-card" data-agent="${esc(a.id)}">
    <div class="ag-head">${art(a, live)}
      <div class="ag-txt"><h2>${w(`name_${a.id}`)}</h2><p class="small muted">${w(`about_${a.id}`)}</p></div></div>
    ${a.problems.length ? `<div class="note warn">${icon('alert')}<div>${w('needs')}: ${esc(a.problems.join(' '))}</div></div>` : ''}
    <ol class="ag-flow" aria-label="${esc(w('steps'))}">${a.steps.map((s, i) => `<li class="ag-step"><span class="ag-n" aria-hidden="true">${i + 1}</span>
      <b>${w(`act_${s.action.replace('.', '_')}`)}</b>
        <span class="tag ${s.side_effect === 'read' ? '' : s.side_effect === 'paid' ? 'bad' : 'warn'}">${w(`side_${s.side_effect}`)}</span>
        ${s.trusted ? `<span class="tag ok" data-tip="${esc(w('trusted_tip'))}">${w('trusted')}</span>` : ''}</li>`).join('')}</ol>
    <div class="ag-trig">${a.triggers.map((tg) => `<label class="check small" data-tip="${esc(w('auto_tip'))}">
        <input type="checkbox" data-trig="${esc(tg.key)}" ${tg.on ? 'checked' : ''}/><span><b>${w('auto')}</b> · ${esc(when(tg))}</span></label>`).join('')}</div>
    <div class="ag-foot"><div class="ag-last">${lastLine(r)}</div>
      <div class="ag-acts">
        <button type="button" class="small ghost" data-history data-tip="${esc(w('history'))}">${icon('clock', 13)} ${w('history')}</button>
        <button type="button" class="small" data-dry data-tip="${esc(w('dry_tip'))}">${icon('eye', 13)} ${w('dry_run')}</button>
        ${r && r.waiting ? `<button type="button" class="small primary" data-approve="${esc(r.ref)}" data-seal="${esc(r.seal || '')}" data-tip="${esc(w('approve_tip'))}">${icon('check', 13)} ${w('approve')}</button>` : ''}
      </div></div>
    <div class="ag-out">${r ? runBox(r) : ''}</div>
  </section>`;
}

export async function agentsPage(host) {
  await loadWords('agents');
  const d = await api('/api/core/agents');
  host.innerHTML = pageHead(w('title'), w('lede')) + `<div id="ag-msg"></div>
    ${d.agents.length ? `<div class="ag-grid">${d.agents.map(agentCard).join('')}</div>`
    : `<section class="card"><h2>${w('empty_title')}</h2><p class="muted">${w('empty_body')}</p></section>`}`;
  const msg = host.querySelector('#ag-msg');
  const again = () => agentsPage(host);
  host.querySelectorAll('.ag-card').forEach((card) => {
    const id = card.dataset.agent;
    card.querySelectorAll('[data-trig]').forEach((c) => {
      c.onchange = async () => {
        try { toast((await api(`/api/core/agents/${id}/triggers/${c.dataset.trig}`, { method: 'PUT', body: { on: c.checked } })).message, 'ok'); again(); }
        catch (err) { c.checked = !c.checked; say(msg, 'bad', esc(err.message)); }
      };
    });
    card.querySelector('[data-dry]').onclick = (e) => busy(e.currentTarget, async () => {
      try { toast((await api(`/api/core/agents/${id}/run`, { method: 'POST', body: {} })).message, 'ok', 8); again(); }
      catch (err) { say(msg, 'bad', esc(err.message)); }
    });
    const ok = card.querySelector('[data-approve]');
    if (ok) ok.onclick = (e) => busy(e.currentTarget, async () => {
      try { toast((await api(`/api/core/agents/${id}/run`, { method: 'POST', body: { approve: true, ref: ok.dataset.approve, seal: ok.dataset.seal } })).message, 'ok', 8); again(); }
      catch (err) { toast(err.message, 'bad', 10); again(); }   // a changed effect: the fresh dry run is shown to read again
    });
    card.querySelector('[data-history]').onclick = async () => {
      const h = await api(`/api/core/agents/${id}/runs`);
      modal(`${w(`name_${id}`)} · ${w('history')}`, h.runs.length ? h.runs.map((r) => `<details class="ag-hist"><summary>${lastLine(r)}</summary>${runBox(r)}</details>`).join('')
        : `<p class="muted">${w('no_runs')}</p>`, { wide: true });
    };
  });
}
