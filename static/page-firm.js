// My firm - SimplyFile is many tenants (2026-10-04 owner). A CA firm (or a person filing their own return) picks its
// kind, gives its details and papers, submits, and waits for the portal admin; once approved the firm admin adds the
// team. The server decides everything (firms.py, chips firm.*): which fields, which papers, what is wrong, which steps
// are done, who may do what. This page draws it. Every word is chip ui.firm; colours are chip page.firm.
import { api, BASE, esc, toast, busy, pageHead, confirmDialog, t, loadWords, modal, uploadBox, when, ps, fileSize, listBox } from './app.js';
import { icon } from './icons.js';
import { historyButton, wireHistory } from './changes.js';

const w = (k, v) => t('firm', k, v);
const P = () => ps('firm');

// The road from sign-up to working: four dots on a line (done = filled), drawn from the server's d.firm.steps.
function road(steps, names) {
  const n = names.length, gap = 100 / (n - 1);
  const done = names.filter((s) => steps[s]).length;
  return `<svg class="fi-road" viewBox="0 0 100 14" preserveAspectRatio="none" aria-hidden="true">
      <line x1="2" y1="7" x2="98" y2="7" stroke="var(--line)" stroke-width="1.4" vector-effect="non-scaling-stroke"/>
      <line x1="2" y1="7" x2="${2 + Math.max(0, done - 1) * gap * 0.96}" y2="7" stroke="var(--ok)" stroke-width="2.4" vector-effect="non-scaling-stroke"/></svg>
    <ol class="fi-steps">${names.map((s, i) => `<li class="${steps[s] ? 'on' : ''}">
      <span class="fi-dot">${steps[s] ? icon('check', 12) : i + 1}</span><span>${esc(w(s))}</span></li>`).join('')}</ol>`;
}

// A shield with a tick (approved), a clock (waiting) or a pen (to do) - the hero's emblem.
function badge(state) {
  const mark = state === 'approved' ? '<path d="M17 25l5 5 10-11" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'
    : state === 'submitted' ? '<circle cx="24" cy="25" r="8" fill="none" stroke="#fff" stroke-width="2.4"/><path d="M24 20v5l3.5 2" stroke="#fff" stroke-width="2.4" stroke-linecap="round" fill="none"/>'
      : '<path d="M18 31l2-6 9-9 4 4-9 9z" fill="#fff"/>';
  const col = (P().state_color || {})[state] || '--brand';
  return `<svg class="fi-badge" width="52" height="56" viewBox="0 0 48 52" aria-hidden="true">
    <defs><linearGradient id="fi-g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="var(${col})"/><stop offset="1" stop-color="var(${col})" stop-opacity=".72"/></linearGradient></defs>
    <path d="M24 2l19 7v14c0 13-8 22-19 27C13 45 5 36 5 23V9z" fill="url(#fi-g)"/>${mark}</svg>`;
}

// Keep these ready: every number and paper a kind asks for (chip firm.settings kinds), each with where to find it.
// With a firm, what it already has is ticked - its saved details and uploaded papers.
function readyList(d, kind, f) {
  const item = (label, hint, req, done) => `<li class="${done ? 'on' : ''}"><span class="fi-tick">${done ? icon('check', 11) : ''}</span>
    <div><b>${esc(label)}</b>${req ? '' : ` <span class="tag">${esc(w('optional'))}</span>`}<div class="small muted">${esc(hint)}</div></div></li>`;
  const has = (k) => !!(f && String(f[k] || '').trim());
  const got = (id) => !!(f && f.docs.some((x) => x.kind === id));
  const docs = kind.docs_required.map((x) => [x, true]).concat(kind.docs_optional.map((x) => [x, false]));
  return `<div class="fi-ready-col"><h4>${icon('edit', 14)} ${esc(w('ready_numbers'))}</h4><ul class="fi-ready-list">
      ${kind.fields.map((k) => item(w(`f_${k}`), w(`h_${k}`), kind.required.includes(k), has(k))).join('')}</ul></div>
    <div class="fi-ready-col"><h4>${icon('folder', 14)} ${esc(w('ready_papers'))}</h4><ul class="fi-ready-list">
      ${docs.map(([x, req]) => item(docOf(d, x).label, docOf(d, x).hint, req, got(x))).join('')}</ul>
      <p class="small muted">${esc(w('ready_files', { exts: d.settings.doc_exts.join(' '), mb: d.settings.doc_max_mb }))}</p></div>`;
}

function readyCard(d, f) {
  const kind = d.settings.kinds.find((k) => k.id === f.kind);
  const req = kind.required.map((k) => !!String(f[k] || '').trim()).concat(kind.docs_required.map((x) => f.docs.some((y) => y.kind === x)));
  return `<section class="card fi-ready"><div class="fi-ready-h">${icon('info', 18)}<div><h3>${esc(w('ready_title'))}</h3>
      <div class="small muted">${esc(w('ready_lede'))}</div></div>
      <span class="tag ${req.every(Boolean) ? 'ok' : 'warn'}">${esc(w('ready_done', { done: req.filter(Boolean).length, n: req.length }))}</span></div>
    <div class="fi-ready-grid">${readyList(d, kind, f)}</div></section>`;
}

function chooseKind(host, d) {
  host.innerHTML = pageHead(w('title'), esc(w('lede_new')))
    + `<section class="card fi-ready"><div class="fi-ready-h">${icon('info', 18)}<div><h3>${esc(w('ready_title'))}</h3>
        <div class="small muted">${esc(w('ready_lede'))}</div></div></div>
      ${d.settings.kinds.map((k) => `<details class="fi-ready-kind" ${k === d.settings.kinds[0] ? 'open' : ''}><summary><b>${esc(k.label)}</b></summary>
        <div class="fi-ready-grid">${readyList(d, k, null)}</div></details>`).join('')}</section>`
    + `<section class="fi-kinds">${d.settings.kinds.map((k) => `<button type="button" class="fi-kind card" data-kind="${esc(k.id)}">
        <span class="fi-kind-ic">${icon((P().kind_icon || {})[k.id] || 'users', 26)}</span>
        <b>${esc(k.label)}</b><span class="muted">${esc(k.sub)}</span>
        <span class="fi-kind-docs">${k.docs_required.map((x) => `<span class="tag">${esc(docOf(d, x).label)}</span>`).join('')}</span>
        <span class="button primary small">${esc(w('start'))} ${icon('right', 13)}</span></button>`).join('')}</section>
      <p class="small muted fi-privacy">${icon('lock', 13)} ${esc(w('privacy'))}</p>`;
  host.querySelectorAll('[data-kind]').forEach((b) => {
    b.onclick = () => busy(b, async () => {
      await api('/api/firm/start', { method: 'POST', body: { kind: b.dataset.kind } });
      firmPage(host);
    });
  });
}

const docOf = (d, id) => d.settings.docs.find((x) => x.id === id) || { id, label: id, hint: '' };
const stateOf = (d, id) => d.settings.states.find((s) => s.id === id) || { label: id, tag: 'tag' };

function details(d) {
  const f = d.firm, kind = d.settings.kinds.find((k) => k.id === f.kind);
  const off = f.editable ? '' : 'disabled';
  const one = (k) => `<div class="field"><label for="fi-${k}">${esc(w(`f_${k}`))}${kind.required.includes(k) ? ' <span class="fi-req">*</span>' : ''}</label>
      ${k === 'address' ? `<textarea id="fi-${k}" rows="2" ${off}>${esc(f[k] || '')}</textarea>`
        : `<input id="fi-${k}" value="${esc(f[k] || '')}" ${off} ${d.settings.code_fields.includes(k) ? 'style="text-transform:uppercase"' : ''}/>`}
      <div class="small muted">${esc(w(`h_${k}`))}</div></div>`;
  return `<section class="card fi-card"><h3>${icon('edit', 15)} ${esc(w('details'))}</h3>
    <div class="grid two">${kind.fields.filter((k) => k !== 'address').map(one).join('')}</div>${kind.fields.includes('address') ? one('address') : ''}
    <label class="check fi-consent"><input type="checkbox" id="fi-consent" ${f.consent_at ? 'checked' : ''} ${off}/> <span>${esc(w('consent'))}</span></label>
    ${f.editable ? `<div class="row tight fi-save"><button type="button" class="primary" id="fi-save">${icon('save', 14)} ${esc(w('save'))}</button>
      <span class="small" id="fi-problem">${f.ready.say && f.ready.say !== 'need_docs' ? `${icon('alert', 13)} ${esc(w(f.ready.say))}` : ''}</span></div>` : ''}</section>`;
}

function papers(d) {
  const f = d.firm, kind = d.settings.kinds.find((k) => k.id === f.kind);
  const slot = (id, required) => {
    const doc = docOf(d, id), have = f.docs.find((x) => x.kind === id);
    return `<div class="fi-doc ${have ? 'on' : ''}">
      <svg class="fi-sheet" width="30" height="36" viewBox="0 0 30 36" aria-hidden="true"><path d="M3 2h17l7 7v25H3z" fill="var(--panel)" stroke="var(${have ? '--ok' : '--line-2'})" stroke-width="1.6"/>
        <path d="M20 2v7h7" fill="none" stroke="var(${have ? '--ok' : '--line-2'})" stroke-width="1.6"/>
        ${have ? '<circle cx="21" cy="27" r="6.5" fill="var(--ok)"/><path d="M18 27l2 2 4-4" stroke="#fff" stroke-width="1.8" fill="none" stroke-linecap="round"/>'
          : '<path d="M8 15h12M8 20h12M8 25h8" stroke="var(--line-2)" stroke-width="1.6" stroke-linecap="round"/>'}</svg>
      <div class="fi-doc-main"><b>${esc(doc.label)}</b> ${required ? '<span class="fi-req">*</span>' : `<span class="tag">${esc(w('optional'))}</span>`}
        <div class="small muted">${have ? `${esc(have.name)} · ${fileSize(have.size)} · ${esc(when(have.at))}` : esc(doc.hint)}</div></div>
      <div class="fi-doc-acts">${have ? `<a class="small ghost button" target="_blank" rel="noopener" href="${BASE}/api/firm/${esc(f.id)}/docs/${esc(have.id)}">${icon('eye', 13)} ${esc(w('view'))}</a>` : ''}
        ${f.editable ? `<button type="button" class="small" data-up="${esc(id)}">${icon('upload', 13)} ${esc(w(have ? 'replace' : 'upload'))}</button>` : ''}</div></div>`;
  };
  return `<section class="card fi-card"><h3>${icon('folder', 15)} ${esc(w('papers'))}</h3>
    <p class="small muted">${esc(w('papers_hint', { exts: d.settings.doc_exts.join(' '), mb: d.settings.doc_max_mb }))}</p>
    ${kind.docs_required.map((x) => slot(x, true)).join('')}${kind.docs_optional.map((x) => slot(x, false)).join('')}</section>`;
}

function banner(d) {
  const f = d.firm, last = [...(f.history || [])].reverse().find((h) => h.note);
  const text = w(f.editable && !f.ready.say ? 'st_ready' : `st_${f.state}`, { hours: d.settings.review_hours, at: when(f.submitted_at || '') });
  return `<div class="fi-banner fi-${esc(f.state)}">${icon((P().state_icon || {})[f.state] || 'info', 16)}
    <div><b>${esc(stateOf(d, f.state).label)}</b><div class="small">${esc(text)}</div>
    ${last && (P().note_states || []).includes(f.state) ? `<div class="small fi-note">${icon('chat', 12)} ${esc(last.note)}</div>` : ''}</div>
    ${f.editable ? `<button type="button" class="primary" id="fi-submit" ${f.ready.say ? 'aria-disabled="true"' : ''}>${icon('send', 14)} ${esc(w('submit'))}</button>` : ''}</div>
    ${f.editable && f.ready.say ? `<div class="small muted fi-why">${esc(w(f.ready.say, { missing: f.ready.missing.map((x) => docOf(d, x).label).join(', ') }))}</div>` : ''}`;
}

function teamCard(d) {
  if (!d.team) return '';
  const roles = d.roles.filter((r) => r.assignable);
  return `<section class="card fi-card"><div class="row tight" style="justify-content:space-between"><h3>${icon('users', 15)} ${esc(w('team'))}</h3>
      ${d.firm.state === d.settings.working_state ? `<button type="button" class="primary small" id="fi-add">${icon('plus', 13)} ${esc(w('add_person'))}</button>` : ''}</div>
    ${d.firm.state === d.settings.working_state ? '' : `<p class="small muted">${esc(w('team_after'))}</p>`}
    <div id="fi-team"></div>
    <details class="fi-roles"><summary class="small">${esc(w('what_roles'))}</summary>${roles.map((r) => `<div class="small"><b>${esc(r.label)}</b> - ${esc(r.sub)}</div>`).join('')}</details></section>`;
}

// list.firm_team: one searched page of the team at a time
function teamRow(d) {
  const roles = d.roles.filter((r) => r.assignable);
  const roleOf = (id) => d.roles.find((r) => r.id === id) || { label: id };
  return (m) => `<tr data-uid="${esc(m.id)}"><td><b>${esc(m.name)}</b><div class="small muted">${esc(m.email)}${m.must_change ? ` · ${esc(w('t_first'))}` : ''}</div></td>
      <td><select data-role aria-label="${esc(w('t_role'))}">${roles.concat(roles.some((r) => r.id === m.role) ? [] : [roleOf(m.role)]).map((r) =>
        `<option value="${esc(r.id)}" ${r.id === m.role ? 'selected' : ''}>${esc(r.label)}</option>`).join('')}</select></td>
      <td><button type="button" class="small ghost" data-rm title="${esc(w('remove'))}">${icon('close', 12)}</button></td></tr>`;
}

function addPerson(d, host) {
  const roles = d.roles.filter((r) => r.assignable);
  modal(w('add_person'), `<div class="grid two">
      <div class="field"><label for="tp-name">${esc(w('t_name'))}</label><input id="tp-name"/></div>
      <div class="field"><label for="tp-email">${esc(w('t_email'))}</label><input id="tp-email" type="email"/></div>
      <div class="field"><label for="tp-role">${esc(w('t_role'))}</label><select id="tp-role">${roles.map((r) => `<option value="${esc(r.id)}">${esc(r.label)}</option>`).join('')}</select></div></div>
    <p class="small muted">${esc(w('add_hint'))}</p>`, {
    footer: `<button type="button" class="primary" data-save>${icon('plus', 14)} ${esc(w('add'))}</button>`,
    onOpen: (m, close) => {
      m.closest('.modal').querySelector('[data-save]').onclick = (ev) => busy(ev.currentTarget, async () => {
        try {
          const r = await api('/api/firm/team', { method: 'POST', body: { name: m.querySelector('#tp-name').value, email: m.querySelector('#tp-email').value, role: m.querySelector('#tp-role').value } });
          close();
          if (r.password) modal(w('added'), `<p>${esc(w('added_pw', { email: r.member.email }))}</p><p class="fi-pw"><code>${esc(r.password)}</code></p>`);
          else toast(w('added_mail', { email: r.member.email }), 'ok');
          firmPage(host);
        } catch (err) { toast(err.message, 'bad', 8); }
      });
    } });
}

export async function firmPage(host) {
  await loadWords('firm', 'changes');
  const d = await api('/api/firm');
  if (!d.firm && d.is_owner && !d.settings.owner_may_start) {
    host.innerHTML = pageHead(w('title'), esc(w('owner_lede')))
      + `<section class="card fi-banner">${icon('shield', 16)}<div><b>${esc(w('owner_title'))}</b><div class="small">${esc(w('owner_body'))}</div></div>
        <a class="button primary" href="#/approvals">${icon('check', 14)} ${esc(w('go_approvals'))}</a></section>`;
    return;
  }
  if (!d.firm) { chooseKind(host, d); return; }
  const f = d.firm;
  host.innerHTML = pageHead(w('title'), esc(w('lede')), historyButton())
    + `<section class="card fi-hero">${badge(f.state)}<div class="fi-hero-main"><div class="fi-name">${esc(f.name || w('unnamed'))}</div>
        <div class="fi-meta"><span class="${esc(stateOf(d, f.state).tag)}">${esc(stateOf(d, f.state).label)}</span><span>${esc(f.kind_label)}</span>
          ${f.pan ? `<code>${esc(f.pan)}</code>` : ''}<span>${esc(w('you_are', { role: d.role.label }))}</span></div>
        ${road(f.steps, d.settings.steps)}</div></section>`
    + banner(d)                                  // what to do next (Send for approval) sits right under the road, above the checklist
    + (f.editable ? readyCard(d, f) : '') + (f.state === d.settings.working_state ? teamCard(d) + details(d) + papers(d) : details(d) + papers(d) + teamCard(d))
    + `<p class="small muted fi-privacy">${icon('lock', 13)} ${esc(w('privacy'))}</p>`;
  const $ = (s) => host.querySelector(s);
  const values = () => {
    const kind = d.settings.kinds.find((k) => k.id === f.kind);
    return Object.fromEntries(kind.fields.map((k) => [k, ($(`#fi-${k}`) || {}).value || '']).concat([['consent', $('#fi-consent').checked]]));
  };
  if ($('#fi-save')) $('#fi-save').onclick = (ev) => busy(ev.currentTarget, async () => {
    try { await api('/api/firm', { method: 'PUT', body: values() }); toast(w('saved'), 'ok'); } catch (err) { toast(err.message, 'bad', 8); }
  }).then(() => firmPage(host));
  host.querySelectorAll('[data-up]').forEach((b) => {
    b.onclick = async () => {
      if (f.editable) await api('/api/firm', { method: 'PUT', body: values() }).catch(() => {});   // typed details are never lost to an upload
      uploadBox(docOf(d, b.dataset.up).label, d.settings.doc_exts, `/api/firm/docs/${b.dataset.up}`, () => firmPage(host));
    };
  });
  if ($('#fi-submit')) $('#fi-submit').onclick = (ev) => {
    const btn = ev.currentTarget;   // read now: once the click is over currentTarget is null, and busy(null) did nothing at all
    if (f.ready.say) { toast(w(f.ready.say, { missing: f.ready.missing.map((x) => docOf(d, x).label).join(', ') }), 'warn', 8); return; }
    confirmDialog(w('submit_title'), w('submit_body', { hours: d.settings.review_hours }), () => busy(btn, async () => {
      try {
        await api('/api/firm', { method: 'PUT', body: values() });
        const r = await api(`/api/firm/${f.id}/move`, { method: 'POST', body: { action: 'submit' } });
        toast(r.say, 'ok'); firmPage(host);
      } catch (err) { toast(err.message, 'bad', 8); }
    }), w('submit'), { tone: 'brand' });
  };
  wireHistory(host, { firm: true, name: f.name });
  if ($('#fi-add')) $('#fi-add').onclick = () => addPerson(d, host);
  if ($('#fi-team')) listBox($('#fi-team'), { list: 'firm_team', row: teamRow(d),
    wrap: (html) => `<table class="fi-team"><thead><tr><th>${esc(w('t_name'))}</th><th>${esc(w('t_role'))}</th><th></th></tr></thead><tbody>${html}</tbody></table>`,
    wire: (rows, r, reload) => rows.querySelectorAll('[data-uid]').forEach((tr) => {
      tr.querySelector('[data-role]').onchange = async (e) => {
        try { await api(`/api/firm/team/${tr.dataset.uid}`, { method: 'PUT', body: { role: e.target.value } }); toast(w('saved'), 'ok'); } catch (err) { toast(err.message, 'bad', 8); }
        reload();
      };
      tr.querySelector('[data-rm]').onclick = () => confirmDialog(w('remove_title'), w('remove_body'), async () => {
        try { await api(`/api/firm/team/${tr.dataset.uid}`, { method: 'DELETE' }); reload(); } catch (err) { toast(err.message, 'bad', 8); }
      }, w('remove'));
    }) });
}
