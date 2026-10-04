// Firm approvals - the portal admin's queue (2026-10-04 owner: "those documents will come to me for approval and I will
// approve manually; eventually DigiLocker"). Oldest waiting first, coloured by the review clock (chip firm.sla); open
// one to read its details and papers, then approve, return for a fix, reject, suspend or restore. The server decides
// every move (chip firm.move); the buttons per state are chip page.firm. Words: ui.firm.
import { api, BASE, esc, toast, busy, pageHead, t, loadWords, modal, when, ps, fileSize } from './app.js';
import { icon } from './icons.js';
import { hue, initials } from './page-clients.js';

const w = (k, v) => t('firm', k, v);
const P = () => ps('firm');
let STATE = 'submitted';

// The clock face of the promise: how much of review_hours has gone, as a ring.
function clock(f, hours) {
  if (f.waited_hours === undefined) return '';
  const r = 13, c = 2 * Math.PI * r, part = Math.min(1, f.waited_hours / hours);
  const col = (P().sla_color || {})[f.sla] || '--muted';
  return `<svg class="ap-clock" width="34" height="34" viewBox="0 0 34 34" role="img" aria-label="${esc(w(`sla_${f.sla}`))}">
    <circle cx="17" cy="17" r="${r}" fill="none" stroke="var(--line)" stroke-width="3.5"/>
    <circle cx="17" cy="17" r="${r}" fill="none" stroke="var(${col})" stroke-width="3.5" stroke-linecap="round"
      stroke-dasharray="${(part * c).toFixed(1)} ${c.toFixed(1)}" transform="rotate(-90 17 17)"/></svg>`;
}

function view(f, S, done) {
  const kind = S.kinds.find((k) => k.id === f.kind) || { fields: [], docs_required: [], docs_optional: [] };
  const docOf = (id) => S.docs.find((x) => x.id === id) || { label: id };
  const acts = (P().actions || {})[f.state] || [];
  const body = `<div class="ap-head"><span class="cl-av" style="--h:${hue(f.name || '?')}">${esc(initials(f.name || '?'))}</span>
      <div><b>${esc(f.name || w('unnamed'))}</b><div class="small muted">${esc(f.kind_label)} · ${esc(w('ap_members', { n: f.members }))}</div></div></div>
    <table class="ap-facts"><tbody>${kind.fields.map((k) => `<tr><th>${esc(w(`f_${k}`))}</th><td>${f[k] ? esc(f[k]) : '<span class="muted">-</span>'}</td></tr>`).join('')}
      <tr><th>${esc(w('ap_consent'))}</th><td>${f.consent_at ? esc(when(f.consent_at)) : `<span class="tag bad">${esc(w('ap_no'))}</span>`}</td></tr></tbody></table>
    <h3>${icon('folder', 14)} ${esc(w('papers'))}</h3>
    ${kind.docs_required.concat(kind.docs_optional).map((id) => {
      const have = f.docs.find((x) => x.kind === id);
      return `<div class="fi-doc ${have ? 'on' : ''}"><div class="fi-doc-main"><b>${esc(docOf(id).label)}</b>
        <div class="small muted">${have ? `${esc(have.name)} · ${fileSize(have.size)} · ${esc(when(have.at))}` : esc(w('ap_missing'))}</div></div>
        ${have ? `<a class="small button" target="_blank" rel="noopener" href="${BASE}/api/firm/${esc(f.id)}/docs/${esc(have.id)}">${icon('eye', 13)} ${esc(w('view'))}</a>` : ''}</div>`;
    }).join('')}
    <p class="small muted">${icon('shield', 12)} ${esc(w('ap_checklist'))}</p>
    <h3>${icon('clock', 14)} ${esc(w('ap_history'))}</h3>
    <ol class="ap-hist">${(f.history || []).slice().reverse().map((h) => `<li><b>${esc(w(`a_${h.action}`))}</b> · ${esc(h.who)} · ${esc(when(h.at))}${h.note ? `<div class="small">${esc(h.note)}</div>` : ''}</li>`).join('')}</ol>
    ${acts.length ? `<div class="field"><label for="ap-note">${esc(w('ap_note'))}</label><textarea id="ap-note" rows="2" placeholder="${esc(w('ap_note_hint'))}"></textarea></div>` : ''}`;
  const footer = acts.map((a) => `<button type="button" class="${esc((P().action_tone || {})[a] || '')}" data-act="${esc(a)}">${esc(w(`do_${a}`))}</button>`).join('');
  modal(f.name || w('unnamed'), body, { wide: true, footer, onOpen: (m, close) => {
    m.closest('.modal').querySelectorAll('[data-act]').forEach((b) => {
      b.onclick = () => busy(b, async () => {
        try {
          const r = await api(`/api/firm/${f.id}/move`, { method: 'POST', body: { action: b.dataset.act, note: m.querySelector('#ap-note').value } });
          toast(r.say, 'ok'); close(); done();
        } catch (err) { toast(err.message, 'bad', 8); }
      });
    });
  } });
}

export async function approvalsPage(host) {
  await loadWords('firm');
  const d = await api(`/api/approvals?state=${encodeURIComponent(STATE)}`);
  const S = d.settings;
  host.innerHTML = pageHead(w('ap_title'), esc(w('ap_lede', { hours: S.review_hours })))
    + `<section class="card cl-card"><div class="cl-bar"><div class="tabs ap-tabs" role="tablist">${S.states.map((s) =>
        `<button type="button" role="tab" data-st="${esc(s.id)}" class="${s.id === STATE ? 'on' : ''}" aria-selected="${s.id === STATE}" title="${esc(s.label)}">${esc(s.tab)}<span class="cl-count">${d.counts[s.id] || 0}</span></button>`).join('')}</div></div>
      <div class="ap-list">${d.rows.length ? d.rows.map((f) => `<div class="cl-row" data-id="${esc(f.id)}">
        <span class="cl-av" style="--h:${hue(f.name || '?')}" aria-hidden="true">${esc(initials(f.name || '?'))}</span>
        <div class="cl-main"><div class="cl-name">${esc(f.name || w('unnamed'))} <span class="tag">${esc(f.kind_label)}</span></div>
          <div class="cl-meta">${f.pan ? `<code>${esc(f.pan)}</code>` : ''}<span>${esc(f.email || '')}</span><span>${esc(w('ap_docs', { n: f.docs.length }))}</span>
            <span>${esc(when(f.submitted_at || f.created_at))}</span></div></div>
        <div class="cl-stage">${clock(f, S.review_hours)}${f.sla ? `<span>${esc(w(`sla_${f.sla}`, { h: Math.round(f.waited_hours) }))}</span>` : ''}</div>
        <div class="cl-acts"><button type="button" class="small" data-open>${icon('eye', 13)} ${esc(w('ap_open'))}</button></div></div>`).join('')
        : `<div class="empty">${icon('check', 22)}<div>${esc(w('ap_empty'))}</div></div>`}</div></section>`;
  host.querySelectorAll('[data-st]').forEach((b) => { b.onclick = () => { STATE = b.dataset.st; approvalsPage(host); }; });
  host.querySelectorAll('[data-id]').forEach((el) => {
    el.querySelector('[data-open]').onclick = () => view(d.rows.find((f) => f.id === el.dataset.id), S, () => approvalsPage(host));
  });
}
