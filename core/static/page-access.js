// People & access — accounts, groups, allow/deny rules per screen and function, the "why can't they?"
// check, access requests, and the portal's sign-up and mail settings. One page, five tabs, one
// resolver on the server behind all of it.
import { api, esc, say, modal, confirmDialog, toast, busy, pageHead, secretField, wireSecrets, t, loadWords, listBox, when, offAttr } from './ui.js';
import { state, refresh, clearFieldErrors, showFieldError, wireFieldErrors } from './shell.js';
import { icon } from './icons.js';

let tab = 'people';
let subject = '';                  // the Rules tab's selected person or group ('' = Catch All)
let checkUser = '';
let checkLabel = '';
const picked = {};                 // the person rows this page has fetched (list access_people), by id
let d = null;                       // the last /api/core/access answer
// the "nothing found" picture: a page of rows under a lens (colours are the portal's own, so dark mode follows)
const FX_ART = `<svg class="fx-art" viewBox="0 0 132 96" aria-hidden="true">
  <defs><linearGradient id="fx-grad" x1="0" y1="0" x2="1" y2="1"><stop offset="0" style="stop-color:var(--brand)"/><stop offset="1" style="stop-color:var(--brand-2)"/></linearGradient></defs>
  <ellipse class="sh" cx="64" cy="88" rx="44" ry="5"/>
  <rect class="pg" x="16" y="12" width="66" height="70" rx="11"/>
  <rect class="ln" x="27" y="25" width="34" height="6" rx="3"/><rect class="ln2" x="27" y="39" width="44" height="6" rx="3"/>
  <rect class="ln2" x="27" y="53" width="26" height="6" rx="3"/><rect class="ln2" x="27" y="67" width="38" height="6" rx="3"/>
  <circle class="lens" cx="86" cy="50" r="19" stroke="url(#fx-grad)" stroke-width="5"/>
  <path d="M100 64l15 15" stroke="url(#fx-grad)" stroke-width="8" stroke-linecap="round"/>
  <path class="x" d="M80 44l12 12M92 44L80 56"/>
  <path class="spk" d="M110 14v9M105.5 18.5h9M22 4v6M19 7h6"/>
  <circle class="dot" cx="118" cy="36" r="2.5"/><circle class="dot" cx="8" cy="40" r="2"/>
</svg>`;
let ruleQ = '';                    // what the Rules tab's screen search holds (kept while rules are clicked)

// Every word on this screen is chip ui.access (core/words.py) - none is written here.
const w = (k, v) => t('access', k, v);

const TABS = () => [
  ['people', w('tab_people'), 'users'], ['rules', w('tab_rules'), 'shield'], ['check', w('tab_check'), 'search'],
  ['requests', w('tab_requests'), 'send'], ['portal', w('tab_portal'), 'setup'],
];
const isOwner = () => state.user.role === 'owner';

export async function accessPage(host) {
  [d] = await Promise.all([api('/api/core/access'), loadWords('access')]);
  const pending = d.requests.filter((r) => r.status === 'pending').length;
  host.innerHTML = `${pageHead(w('title'), w('lede'),
    `<button class="primary" type="button" id="add-person">${icon('plus')} ${w('add_person')}</button>`)}
    <div class="tabs many" role="tablist">${TABS().map(([id, label, ic]) => `<button type="button" role="tab" data-tab="${id}"
      class="${tab === id ? 'on' : ''}">${icon(ic, 14)} ${label}
      ${id === 'requests' && pending ? `<span class="badge">${pending}</span>` : ''}</button>`).join('')}</div>
    <div id="acc-msg"></div><div id="acc-body"></div>`;
  host.querySelectorAll('[data-tab]').forEach((b) => { b.onclick = () => { tab = b.dataset.tab; accessPage(host); }; });
  host.querySelector('#add-person').onclick = () => addPerson(host);
  const body = host.querySelector('#acc-body');
  ({ people, rules, check, requests, portal })[tab](body, host);
}

const reload = (host) => accessPage(host);
const groupName = (id) => (d.groups.find((g) => g.id === id) || {}).name || w('deleted_group');
// Catch All (built in, id from the server) = what every account in no group sees; always listed first
const isCatchAll = (g) => !!g && g.id === d.catch_all;
const groupsFirst = () => [...d.groups.filter(isCatchAll), ...d.groups.filter((g) => !isCatchAll(g))];

// --- people ----------------------------------------------------------------------------------------

// 2026-09-28 owner "tens of thousands": people are list access_people - one searched page at a time (listBox).
function personRow(p) {
  picked[p.id] = p;
  return `<tr>
      <td><b>${esc(p.name || p.email)}</b>${p.username ? `<span class="small muted handle">@${esc(p.username)}</span>` : ''}
        ${p.verified === false || p.must_change_password ? `<span class="persontags">
          ${p.verified === false ? `<span class="tag warn">${w('tag_unconfirmed')}</span>` : ''}
          ${p.must_change_password ? `<span class="tag warn">${w('tag_must_change')}</span>` : ''}</span>` : ''}</td>
      <td>${esc(p.email)}</td>
      <td>${isOwner() && p.id !== state.user.id
        ? `<select data-role="${esc(p.id)}" class="fit" aria-label="${esc(w('col_role'))}">${roleOptions(p.role)}</select>`
        : `<span class="tag ${p.role === 'owner' ? 'brand' : ''}">${esc((d.roles.find((r) => r.id === p.role) || {}).label || p.role)}</span>`}</td>
      <td>${p.groups.map((g) => `<span class="tag">${esc(groupName(g))}</span>`).join(' ') || '<span class="muted small">—</span>'}</td>
      <td class="small muted">${when(p.created_at)}</td>
      <td class="a"><button class="small" type="button" data-check="${esc(p.id)}">${icon('search', 13)} ${w('access_button')}</button>
        ${isOwner() && p.id !== state.user.id ? `<button class="small" type="button" data-reset="${esc(p.id)}">${icon('key', 13)} ${w('reset_password')}</button>` : ''}
        ${p.id === state.user.id ? '' : `<button class="small danger" type="button" data-del="${esc(p.id)}" data-name="${esc(p.email)}">${w('remove')}</button>`}</td>
    </tr>`;
}

function people(body, host) {
  body.innerHTML = `<div class="card flush" id="acc-people"></div>
    <div class="card"><h2>${icon('users', 16)} ${w('roles')}</h2><table class="rules"><tbody>
      ${d.roles.map((r) => `<tr><td><span class="tag ${r.id === 'owner' ? 'brand' : ''}">${esc(r.label)}</span></td><td class="small">${esc(r.doc)}</td></tr>`).join('')}
      </tbody></table>
      <p class="small muted">${w('roles_note', { role: esc(d.new_account_role) })}</p></div>`;
  listBox(body.querySelector('#acc-people'), { list: 'access_people', row: personRow,
    wrap: (html) => `<div class="scroll" style="max-height:none"><table>
      <thead><tr><th>${w('col_name')}</th><th>${w('col_email')}</th><th>${w('col_role')}</th><th>${w('col_groups')}</th><th>${w('col_joined')}</th><th></th></tr></thead>
      <tbody>${html}</tbody></table></div>`,
    wire: (rows, r, again) => {
      rows.querySelectorAll('[data-role]').forEach((sel) => {
        sel.onchange = async () => {
          try {
            await api(`/api/core/access/people/${sel.dataset.role}/role`, { method: 'PUT', body: { role: sel.value } });
            toast(w(/^[aeiou]/.test(sel.value) ? 'now_an' : 'now_a', { role: sel.value }), 'ok');
          } catch (e) { toast(e.message, 'bad'); }
          again();
        };
      });
      rows.querySelectorAll('[data-reset]').forEach((b) => { b.onclick = () => resetPassword(picked[b.dataset.reset], again); });
      rows.querySelectorAll('[data-check]').forEach((b) => {
        b.onclick = () => { checkUser = b.dataset.check; checkLabel = (picked[checkUser] || {}).email || ''; tab = 'check'; reload(host); };
      });
      rows.querySelectorAll('[data-del]').forEach((b) => {
        b.onclick = () => confirmDialog(w('remove_title'), w('remove_body', { who: b.dataset.name }), async () => {
          try { await api(`/api/users/${b.dataset.del}`, { method: 'DELETE' }); toast(w('removed'), 'ok'); again(); }
          catch (e) { toast(e.message, 'bad'); }
        }, w('remove'), { tone: 'danger' });
      });
    } });
}

/** Every role from the people.roles chip, most powerful first. */
function roleOptions(current, long = false) {
  return d.roles.map((r) => `<option value="${esc(r.id)}" ${r.id === current ? 'selected' : ''}>${esc(long ? `${r.label} — ${r.doc}` : r.label)}</option>`).join('');
}

/** A labelled box with room for the server's answer about it ({message, field}). */
const box = (id, label, name, attrs = '', hint = '') => `<div class="field" data-for="${name}"><label for="${id}">${esc(label)}</label>
    <input id="${id}" ${attrs} aria-describedby="${id}-err"/>
    <span class="err" id="${id}-err" role="alert" hidden></span>
    ${hint ? `<span class="small muted">${hint}</span>` : ''}</div>`;

/** Copy to the clipboard; where the browser refuses (plain http), select the text for Ctrl+C instead. */
async function copyText(text, button, selectEl) {
  try {
    await navigator.clipboard.writeText(text);
    button.textContent = w('copied');
  } catch {
    if (selectEl && selectEl.select) { selectEl.type = 'text'; selectEl.select(); }
    else if (selectEl) {
      const range = document.createRange();
      range.selectNodeContents(selectEl);
      getSelection().removeAllRanges();
      getSelection().addRange(range);
    }
    button.textContent = w('press_ctrl_c');
  }
  setTimeout(() => { button.textContent = w('copy'); }, 2200);
}

function addPerson(host) {
  modal(w('add_person'), `
    <div id="nu-msg"></div>
    <div class="grid two">
      ${box('nu-name', w('display_name'), 'name', `autocomplete="off" placeholder="${esc(w('display_name_placeholder'))}"`)}
      ${box('nu-user', w('user_name'), 'username', `autocomplete="off" autocapitalize="off" spellcheck="false" placeholder="${esc(w('user_name_placeholder'))}"`,
        w('user_name_hint'))}
    </div>
    <div style="margin-top:12px">${box('nu-email', w('col_email'), 'email', `type="email" autocomplete="off" inputmode="email" autocapitalize="off" spellcheck="false" placeholder="${esc(w('email_placeholder'))}"`)}</div>
    <div class="field" data-for="password" style="margin-top:12px"><label for="nu-pass">${w('first_password')}</label>
      <span class="withbtn"><input id="nu-pass" type="password" autocomplete="new-password" aria-describedby="nu-pass-err"/>
        <button type="button" data-reveal="nu-pass">${w('show')}</button></span>
      <span class="err" id="nu-pass-err" role="alert" hidden></span>
      <span class="small muted">${d.can_email
        ? w('first_password_invite')
        : w('first_password_no_email', { n: d.password_min_length })}</span></div>
    ${isOwner() ? `<div class="field" style="margin-top:12px"><label for="nu-role">${w('col_role')}</label>
      <select id="nu-role">${roleOptions(d.new_account_role, true)}</select></div>` : ''}`, {
    footer: `<button type="button" data-cancel>${w('cancel')}</button><button type="button" class="primary" id="nu-save">${w('add')}</button>`,
    onOpen: (b2, close) => {
      const card = b2.closest('.modal');
      wireSecrets(b2);
      wireFieldErrors(b2);
      const user = b2.querySelector('#nu-user');
      user.addEventListener('input', () => { if (user.value !== user.value.toLowerCase()) user.value = user.value.toLowerCase(); });
      card.querySelector('[data-cancel]').onclick = () => close();
      card.querySelector('#nu-save').onclick = (e) => busy(e.currentTarget, async () => {
        clearFieldErrors(b2);
        try {
          const r = await api('/api/users', { method: 'POST', body: {
            display_name: b2.querySelector('#nu-name').value.trim(), username: user.value.trim(),
            email: b2.querySelector('#nu-email').value.trim(), password: b2.querySelector('#nu-pass').value,
            role: (b2.querySelector('#nu-role') || {}).value || '' } });
          close();
          toast(r.invited ? w('invited', { email: r.user.email }) : w('can_sign_in', { email: r.user.email }), 'ok');
          reload(host);
        } catch (err) { showFieldError(b2, err, b2.querySelector('#nu-msg')); }
      });
      b2.querySelector('#nu-name').focus();
    } });
}

/** People → Reset password (AUTH.md §6), owner only and never for yourself. The owner types a password
 *  or has the SERVER make one; the answer is shown once, in the same dialog. */
function resetPassword(p, redraw) {
  if (!p) return;
  let generate = false;
  const who = `<p class="rp-who small muted">${esc(p.email)}${p.username ? ` · @${esc(p.username)}` : ''}</p>`;
  modal(p.name || p.email, `${who}
    <div id="rp-msg"></div>
    <div class="field" data-for="password"><label for="rp-pass">${w('new_password')}</label>
      <span class="withbtn wide">
        <input id="rp-pass" type="password" autocomplete="new-password" spellcheck="false" autocapitalize="off"
          data-lpignore="true" placeholder="${esc(w('type_or_generate'))}" aria-describedby="rp-pass-err"/>
        <button type="button" data-copy="rp-pass">${w('copy')}</button>
        <button type="button" data-reveal="rp-pass">${w('show')}</button></span>
      <span class="err" id="rp-pass-err" role="alert" hidden></span>
      <div class="rp-gen"><button type="button" class="small" id="rp-gen">${icon('spark', 13)} ${w('auto_generate')}</button>
        <span class="small muted" id="rp-gen-note" aria-live="polite"></span></div></div>
    <label class="check rp-check"><input type="checkbox" id="rp-change" ${d.reset_defaults && d.reset_defaults.require_change_default === false ? '' : 'checked'}/>
      <span><b>${w('require_change')}</b>
        <span class="small muted">${w('must_choose')}</span></span></label>
    <label class="check rp-check"><input type="checkbox" id="rp-mail" ${d.can_email ? '' : 'disabled'}/>
      <span><b>${w('email_password')}</b>
        <span class="small muted">${w(d.can_email ? 'email_password_smtp' : 'email_password_none')}</span></span></label>
    <p class="small muted rp-foot">${w('signs_out')}</p>`, {
    eyebrow: w('reset_password'),
    footer: `<button type="button" data-cancel>${w('cancel')}</button>
      <button type="button" class="primary" id="rp-go">${icon('check', 15)} ${w('set_password')}</button>`,
    onOpen: (b2, close) => {
      const card = b2.closest('.modal');
      const input = b2.querySelector('#rp-pass');
      const copy = b2.querySelector('[data-copy]');
      const note = b2.querySelector('#rp-gen-note');
      wireSecrets(b2);
      wireFieldErrors(b2);
      input.addEventListener('input', () => {
        if (generate && input.value) {                // typing wins over a pending auto-generate
          generate = false;
          note.textContent = '';
          input.placeholder = w('type_or_generate');
        }
      });
      copy.onclick = () => (input.value ? copyText(input.value, copy, input) : toast(w('nothing_to_copy'), 'warn'));   // never greyed
      b2.querySelector('#rp-gen').onclick = () => {
        generate = true;
        input.value = '';
        copy.disabled = true;
        input.placeholder = w('made_by_server');
        note.textContent = w('server_will_make', { n: d.reset_defaults ? d.reset_defaults.length : 14 });
        clearFieldErrors(b2);
      };
      card.querySelector('[data-cancel]').onclick = () => close();
      const go = card.querySelector('#rp-go');
      const run = () => busy(go, async () => {
        clearFieldErrors(b2);
        const typed = input.value;
        const auto = generate || !typed;
        try {
          const r = await api(`/api/core/people/${encodeURIComponent(p.id)}/password`, { method: 'POST', body: {
            password: auto ? '' : typed, generate: auto,
            require_change: b2.querySelector('#rp-change').checked, send_email: b2.querySelector('#rp-mail').checked } });
          showResult(r);
          redraw();                                     // the table behind picks up "must change password"
        } catch (err) { showFieldError(b2, err, b2.querySelector('#rp-msg')); }
      });
      go.onclick = run;
      b2.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && e.target === input) { e.preventDefault(); run(); }
      });

      function showResult(r) {
        b2.innerHTML = `${who}
          ${r.password ? `<div class="rp-result"><span class="rp-label">${w('temporary_password')}</span>
            <div class="rp-row"><code id="rp-out">${esc(r.password)}</code>
              <button type="button" class="small" id="rp-copy">${w('copy')}</button></div></div>` : ''}
          <div id="rp-outcome"></div>
          <p class="small muted rp-foot">${w(r.require_change ? 'must_choose' : 'can_sign_in_now')} ${w('were_signed_out')}</p>`;
        say(b2.querySelector('#rp-outcome'), ...(r.emailed ? ['ok', w('emailed')]
          : r.email_error ? ['warn', esc(w('email_not_sent', { error: r.email_error }))]
            : ['info', w('share_securely')]));
        const again = b2.querySelector('#rp-copy');
        if (again) again.onclick = () => copyText(r.password, again, b2.querySelector('#rp-out'));
        card.querySelector('footer').innerHTML = `<button type="button" class="primary" id="rp-done">${icon('check', 15)} ${w('done')}</button>`;
        const done = card.querySelector('#rp-done');
        done.onclick = () => close();
        done.focus();
      }
      input.focus();
    } });
}

// --- groups & rules --------------------------------------------------------------------------------
// Master / detail: every group and person on the left with a count of their rules, and the selected
// one's rules on the right as a grid — one row per screen and per function, three choices each.

function rulesOf(subj) {
  if (subj.startsWith('user:')) return (picked[subj.slice(5)] || {}).grants || [];
  return d.grants.filter((g) => g.subject === subj);
}

function subjectItem(s, label, n, extra = '') {
  return `<button type="button" data-subj="${esc(s)}" class="${subject === s ? 'on' : ''}">
      ${icon(s.startsWith('group:') ? 'users' : 'user', 15)}<span class="nm">${esc(label)}</span>${extra}
      <span class="badge ${n ? '' : 'zero'}" title="${esc(w('rules_tip'))}">${n}</span></button>`;
}

function rules(body, host) {
  body.innerHTML = `<div class="panes">
    <div class="pane"><div class="top row between"><b>${w('groups_people')}</b>
        <button class="small" type="button" id="new-group">${icon('plus', 13)} ${w('group')}</button></div>
      <div class="scrollbody"><div class="list">
        <div class="grp">${w('groups')}</div>
        ${groupsFirst().map((g) => subjectItem(`group:${g.id}`, g.name, rulesOf(`group:${g.id}`).length,
          isCatchAll(g) ? `<span class="tag">${w('catch_all_tag')}</span>` : `<span class="small muted">${g.members_n || 0}</span>`)).join('')}
        <div class="grp">${w('tab_people')}</div></div>
        <div id="acc-subjects"></div></div></div>
    <div class="pane"><div class="scrollbody pad" id="rule-detail"></div></div></div>`;
  const pick = (root) => root.querySelectorAll('[data-subj]').forEach((b) => {
    b.onclick = () => {
      subject = b.dataset.subj;
      body.querySelectorAll('[data-subj]').forEach((x) => x.classList.toggle('on', x.dataset.subj === subject));
      ruleDetail(body.querySelector('#rule-detail'), host);
    };
  });
  pick(body.querySelector('.list'));
  listBox(body.querySelector('#acc-subjects'), { list: 'access_people', args: { not_owner: 1 }, empty: w('no_editors'),
    row: (p) => { picked[p.id] = p; return subjectItem(`user:${p.id}`, p.email, (p.grants || []).length); },
    wrap: (html) => `<div class="list">${html}</div>`, wire: (rows) => pick(rows) });
  body.querySelector('#new-group').onclick = () => groupDialog(null, host);
  ruleDetail(body.querySelector('#rule-detail'), host);
}

/** One person's row, fresh from list access_people (their groups and their own rules). */
async function personById(id) {
  const r = await api(`/api/lists/access_people?${new URLSearchParams({ id })}`);
  if (r.rows[0]) picked[id] = r.rows[0];
  return r.rows[0];
}

async function ruleDetail(box, host) {
  const [kind, id] = subject.split(':');
  const g = kind === 'group' ? d.groups.find((x) => x.id === id) : null;
  const p = kind === 'user' ? (picked[id] || await personById(id)) : null;
  if (!g && !p) { subject = `group:${d.catch_all}`; return ruleDetail(box, host); }
  const mine = rulesOf(subject);
  const effectOf = (screen, fn = '') => (mine.find((r) => r.screen === screen && (r.function || '') === fn) || {}).effect || '';
  const choice = (screen, fn, fallback, tip = w('no_rule_tip')) => {
    const e = effectOf(screen, fn);
    return `<div class="switch" data-screen="${esc(screen)}" data-fn="${esc(fn)}">
      <button type="button" data-eff="" class="${e ? '' : 'on'}" title="${esc(tip)}">${esc(fallback)}</button>
      <button type="button" data-eff="allow" class="${e === 'allow' ? 'on ok' : ''}">${icon('check', 13)} ${w('allow')}</button>
      <button type="button" data-eff="deny" class="${e === 'deny' ? 'on bad' : ''}">${icon('ban', 13)} ${w('deny')}</button></div>`;
  };
  box.innerHTML = `
    <div class="row between" style="margin-bottom:6px">
      <h2 style="margin:0">${icon(g ? 'users' : 'user', 17)} ${esc(g ? g.name : p.email)}</h2>
      ${g ? `<span class="row tight">
        <button class="small" type="button" id="edit-group">${icon('edit', 13)} ${w(isCatchAll(g) ? 'rename' : 'name_members')}</button>
        ${isCatchAll(g) ? '' : `<button class="small danger" type="button" id="del-group">${icon('trash', 13)} ${w('delete')}</button>`}</span>` : ''}
    </div>
    <p class="small muted">${g ? (isCatchAll(g)
        ? w('catch_all_note')
        : `${esc(g.description || '')} ${g.inherits ? w('group_inherits', { name: esc(groupName(g.inherits)) }) : w('group_inherits_none')}
          ${g.members_n ? '' : `<i>${w('no_members')}</i>`}`)
      : w('person_rules', { groups: p.groups.map((x) => `<span class="tag">${esc(groupName(x))}</span>`).join(' ') || esc(w('person_in_no_group')) })}</p>
    ${g && !isCatchAll(g) && g.members_n ? '<div id="grp-members" class="small" style="margin-bottom:10px"></div>' : ''}
    <div class="fx-find">${icon('search', 16)}
      <input type="search" id="rule-find" placeholder="${esc(w('find_screen'))}" aria-label="${esc(w('find_screen'))}" value="${esc(ruleQ)}" autocomplete="off">
      <span class="fx-tag" id="rule-tag">${icon('spark', 11)} ${w('typo_ok')}</span><span class="fx-n" id="rule-n" hidden></span>
      <button type="button" class="fx-clear" id="rule-clear" hidden aria-label="${esc(w('clear_search'))}" title="${esc(w('clear_search'))}">${icon('close', 14)}</button></div>
    <div class="fx-none" id="rule-none" hidden>${FX_ART}<b id="rule-none-q"></b><span class="small">${w('no_screen_hint')}</span></div>
    <table class="rules" id="rule-table"><thead><tr><th>${w('col_screen')}</th><th>${w('col_rule')}</th></tr></thead><tbody>
    ${d.catalog.filter((s) => !s.admin).map((s, i, all) => `${i && all[i - 1].group === s.group ? '' : `<tr class="rg" data-rg="${esc(s.group || '')}"><td colspan="2">${icon('folder', 13)} ${esc(s.group || w('no_group'))}</td></tr>`}
      <tr data-sid="${esc(s.id)}" data-g="${esc(s.group || '')}"><td><b>${esc(s.label)}</b></td><td>${choice(s.id, '', w('open'))}</td></tr>
      ${(s.functions || []).map((f) => `<tr class="fn" data-sid="${esc(s.id)}" data-g="${esc(s.group || '')}"><td>↳ ${esc(f.label)}</td><td>${choice(s.id, f.id, w('as_screen'), w('as_screen_tip'))}</td></tr>`).join('')}`).join('')}
    </tbody></table>
    <p class="small muted" style="margin-top:12px">${icon('lock', 13)} ${esc(d.catalog.filter((s) => s.admin).map((s) => s.label).join(', '))}
      ${w('owner_only_note')}</p>`;
  // 2026-10-19 owner "allow flexi search here": the server searches (list access_screens, op fuzzy_rows) - a typo or half
  // a word still finds the screen; the page only hides the rows that did not come back
  const find = box.querySelector('#rule-find');
  const showOnly = async () => {
    const q = find.value.trim(); ruleQ = find.value;
    let ids = null;
    if (q) {
      try { ids = new Set((await api(`/api/lists/access_screens?${new URLSearchParams({ q })}`)).rows.map((r) => r.id)); }
      catch (e) { toast(e.message, 'bad'); return; }
    }
    if (find.value !== ruleQ) return;                  // typed on meanwhile: the newer search answers
    box.querySelectorAll('tr[data-sid]').forEach((tr) => { tr.hidden = !!ids && !ids.has(tr.dataset.sid); });
    box.querySelectorAll('tr[data-rg]').forEach((tr) => {   // a folder heading shows while any of its screens does
      tr.hidden = !!ids && ![...box.querySelectorAll('tr[data-sid]')].some((x) => x.dataset.g === tr.dataset.rg && !x.hidden);
    });
    const total = d.catalog.filter((s) => !s.admin).length;
    const n = box.querySelector('#rule-n');
    n.hidden = !ids; n.textContent = ids ? w('matches_n', { n: ids.size, total }) : '';
    box.querySelector('#rule-tag').hidden = !!ids;
    box.querySelector('#rule-clear').hidden = !find.value;
    box.querySelector('#rule-none').hidden = !ids || ids.size > 0;
    box.querySelector('#rule-table').hidden = !!ids && !ids.size;
    box.querySelector('#rule-none-q').innerHTML = w('no_screen_match', { q: esc(q) });
  };
  let findTimer = 0;
  find.oninput = () => {
    box.querySelector('#rule-clear').hidden = !find.value;
    clearTimeout(findTimer); findTimer = setTimeout(showOnly, 300);   // ponytail: listBox's pause
  };
  box.querySelector('#rule-clear').onclick = () => { find.value = ''; showOnly(); find.focus(); };
  if (ruleQ.trim()) showOnly();
  const members = box.querySelector('#grp-members');
  if (members) listBox(members, { list: 'access_people', args: { group: g.id }, row: (m) => `<span class="tag">${esc(m.email)}</span> ` });
  box.querySelectorAll('.switch').forEach((sw) => {
    sw.querySelectorAll('[data-eff]').forEach((b) => {
      b.onclick = async () => {
        const screen = sw.dataset.screen; const fn = sw.dataset.fn; const eff = b.dataset.eff;
        const had = mine.find((r) => r.screen === screen && (r.function || '') === fn);
        try {
          if (!eff && had) await api(`/api/core/access/grants/${had.id}`, { method: 'DELETE' });
          if (eff) await api('/api/core/access/grants', { method: 'POST', body: { subject, screen, function: fn, effect: eff } });
          d = await api('/api/core/access');
          if (p) await personById(p.id);
          ruleDetail(box, host);
          const list = host.querySelector(`[data-subj="${CSS.escape(subject)}"] .badge`);
          if (list) { const n = rulesOf(subject).length; list.textContent = n; list.classList.toggle('zero', !n); }
          await refresh();                             // your own menu follows if you changed yourself
        } catch (e) { toast(e.message, 'bad'); }
      };
    });
  });
  const edit = box.querySelector('#edit-group');
  if (edit) edit.onclick = () => groupDialog(g, host);
  const del = box.querySelector('#del-group');
  if (del) del.onclick = () => confirmDialog(w('delete_group_title', { name: g.name }), w('delete_group_body'), async () => {
    try { await api(`/api/core/access/groups/${g.id}`, { method: 'DELETE' }); subject = ''; toast(w('group_deleted'), 'ok'); reload(host); }
    catch (e) { toast(e.message, 'bad'); }
  }, w('delete'), { tone: 'danger' });
}

// 2026-09-28 a group of thousands: its members are a searched list of ticks; what changed is sent (add / remove)
function groupDialog(g, host) {
  const add = new Set();
  const remove = new Set();
  const inGroup = (p) => (add.has(p.id) || (g && p.groups.includes(g.id))) && !remove.has(p.id);
  const ca = isCatchAll(g);
  // INHERIT: one parent or none; a group cannot pick itself (the server refuses a loop and says why)
  const parent = g ? (g.inherits || '') : (d.new_group_inherits || '');
  const parents = groupsFirst().filter((x) => !g || x.id !== g.id);
  modal(g ? w('edit_group', { name: g.name }) : w('new_group'), `
    <div id="g-msg"></div>
    <div class="field"><label for="g-name">${w('col_name')}</label><input id="g-name" value="${esc(g ? g.name : '')}" placeholder="${esc(w('group_name_placeholder'))}"/></div>
    <div class="field" style="margin-top:12px"><label for="g-desc">${w('group_for')}</label>
      <input id="g-desc" value="${esc(g ? g.description || '' : '')}" placeholder="${esc(w('group_for_placeholder'))}"/></div>
    ${ca ? `<p class="small muted" style="margin-top:12px">${w('catch_all_note')}</p>` : `
    <div class="field" style="margin-top:12px"><label for="g-parent">${w('inherits_label')}</label>
      <select id="g-parent"><option value="">${esc(w('inherits_none'))}</option>
        ${parents.map((x) => `<option value="${esc(x.id)}" ${x.id === parent ? 'selected' : ''}>${esc(x.name)}</option>`).join('')}</select>
      <span class="small muted">${w('inherits_note')}</span></div>
    <div class="field" style="margin-top:12px"><label>${w('members')}</label><div id="g-people"></div></div>`}`, {
    footer: `<button type="button" data-cancel>${w('cancel')}</button><button type="button" class="primary" id="g-save">${w('save_group')}</button>`,
    onOpen: (b2, close) => {
      const card = b2.closest('.modal');
      if (!ca) listBox(b2.querySelector('#g-people'), { list: 'access_people', args: { not_owner: 1 }, empty: w('no_editors_group'),
        row: (p) => `<label class="check"><input type="checkbox" value="${esc(p.id)}" data-in="${g && p.groups.includes(g.id) ? 1 : 0}" ${inGroup(p) ? 'checked' : ''}/>
          ${esc(p.name)} <span class="muted">${esc(p.email)}</span></label>`,
        wrap: (html) => `<div class="checks">${html}</div>`,
        wire: (rows) => rows.querySelectorAll('input[type=checkbox]').forEach((i) => {
          i.onchange = () => {
            const was = i.dataset.in === '1';
            add.delete(i.value); remove.delete(i.value);
            if (i.checked && !was) add.add(i.value);
            if (!i.checked && was) remove.add(i.value);
          };
        }) });
      card.querySelector('[data-cancel]').onclick = close;
      card.querySelector('#g-save').onclick = (e) => busy(e.currentTarget, async () => {
        try {
          const r = await api('/api/core/access/groups', { method: 'POST', body: {
            id: g ? g.id : undefined, name: b2.querySelector('#g-name').value, description: b2.querySelector('#g-desc').value,
            ...(ca ? {} : { inherits: b2.querySelector('#g-parent').value, add: [...add], remove: [...remove] }) } });
          close();
          subject = `group:${r.group.id}`;
          toast(w('group_saved'), 'ok');
          reload(host);
        } catch (err) { say(b2.querySelector('#g-msg'), 'bad', esc(err.message)); }
      });
    } });
}

// --- check a person --------------------------------------------------------------------------------

async function check(body) {
  body.innerHTML = `<div class="card">
    <div class="field" style="max-width:520px"><label>${w('person')}</label>
      ${checkLabel ? `<p><b>${esc(checkLabel)}</b></p>` : ''}<div id="chk-pick"></div></div>
    <div id="chk-out" style="margin-top:14px"></div></div>`;
  listBox(body.querySelector('#chk-pick'), { list: 'access_people',
    row: (p) => `<button type="button" class="small ${p.id === checkUser ? 'primary' : 'ghost'}" data-chk="${esc(p.id)}" data-email="${esc(p.email)}">
      ${esc(p.email)} (${esc(p.role)})</button> `,
    wire: (rows) => rows.querySelectorAll('[data-chk]').forEach((b) => {
      b.onclick = () => { checkUser = b.dataset.chk; checkLabel = b.dataset.email; check(body); };
    }) });
  if (!checkUser) return;
  const r = await api(`/api/core/access/check/${checkUser}`);
  const why = r.chains.length
    ? w('check_groups', { groups: r.chains.map((c) => `<span class="tag">${c.map(esc).join(' ← ')}</span>`).join(' ') })
    : w('check_catch_all');
  const yes = (v) => (v.allowed ? `<span class="tag ok">${icon('check', 11)} ${w('opens')}</span>` : `<span class="tag bad">${icon('ban', 11)} ${w('shut')}</span>`);
  body.querySelector('#chk-out').innerHTML = `<p class="small muted">${icon('info', 13)} ${why}</p><div class="scroll" style="max-height:none"><table class="rules">
    <thead><tr><th>${w('col_screen')}</th><th>${w('col_result')}</th><th>${w('col_why')}</th></tr></thead><tbody>
    ${r.screens.map((s) => `<tr><td><b>${esc(s.label)}</b></td><td>${yes(s)}</td><td class="small">${esc(s.why)}</td></tr>
      ${s.functions.map((f) => `<tr class="fn"><td>↳ ${esc(f.label)}</td><td>${yes(f)}</td><td class="small">${esc(f.why)}</td></tr>`).join('')}`).join('')}
    </tbody></table></div>`;
}

// --- requests --------------------------------------------------------------------------------------

function requests(body, host) {
  const label = (r) => { const s = d.catalog.find((x) => x.id === r.screen); return s ? s.label : r.screen; };
  const pending = d.requests.filter((r) => r.status === 'pending');
  const done = d.requests.filter((r) => r.status !== 'pending');
  body.innerHTML = `<div class="card flush">${pending.length ? `<table><thead><tr><th>${w('col_who')}</th><th>${w('col_wants')}</th><th>${w('col_why')}</th><th>${w('col_asked')}</th><th></th></tr></thead>
    <tbody>${pending.map((r) => `<tr><td>${esc(r.email)}</td><td><b>${esc(label(r))}</b></td>
      <td class="small">${esc(r.reason) || '<span class="muted">—</span>'}</td><td class="small muted">${when(r.at)}</td>
      <td class="a"><button class="small primary" type="button" data-ok="${esc(r.id)}">${icon('check', 13)} ${w('approve')}</button>
        <button class="small danger" type="button" data-no="${esc(r.id)}" data-email="${esc(r.email)}" data-screen="${esc(label(r))}">${w('reject')}</button></td></tr>`).join('')}</tbody></table>`
    : `<div class="empty">${icon('send', 36)}<h3>${w('no_requests')}</h3><p>${w('no_requests_hint')}</p></div>`}</div>
    ${done.length ? `<div class="card flush"><table><thead><tr><th>${w('col_who')}</th><th>${w('col_screen')}</th><th>${w('col_answer')}</th><th>${w('col_by')}</th><th>${w('col_when')}</th></tr></thead>
      <tbody>${done.slice(0, 50).map((r) => `<tr><td>${esc(r.email)}</td><td>${esc(label(r))}</td>
        <td><span class="tag ${r.status === 'approved' ? 'ok' : 'bad'}">${esc(r.status)}</span></td>
        <td class="small">${esc(r.reviewed_by || '')}</td><td class="small muted">${when(r.reviewed_at)}</td></tr>`).join('')}</tbody></table></div>` : ''}`;
  const answer = (id, verdict) => async (e) => busy(e.currentTarget, async () => {
    try {
      const r = await api(`/api/core/access/requests/${id}/${verdict}`, { method: 'POST' });
      if (verdict === 'reject') toast(w('rejected'), 'ok');
      else if (r.allowed) toast(w('approved'), 'ok');
      else toast(w('approved_still_shut', { why: r.why }), 'warn', 9);
      reload(host);
    } catch (err) { toast(err.message, 'bad'); }
  });
  body.querySelectorAll('[data-ok]').forEach((b) => { b.onclick = answer(b.dataset.ok, 'approve'); });
  body.querySelectorAll('[data-no]').forEach((b) => {
    b.onclick = () => { const go = answer(b.dataset.no, 'reject'); confirmDialog(w('reject_title', { email: b.dataset.email }), w('reject_body', { screen: b.dataset.screen }),
      () => go({ currentTarget: b }), w('reject'), { tone: 'danger' }); };
  });
}

// --- portal & sign-up ------------------------------------------------------------------------------

function portal(body) {
  if (!isOwner()) {
    body.innerHTML = `<div class="note info">${icon('info')}<div>${w('owners_only')}</div></div>`;
    return;
  }
  const s = d.settings;
  body.innerHTML = `
    <div class="card"><h2>${icon('link', 17)} ${w('this_portal')}</h2>
      <p class="muted small">${w('this_portal_note')}</p>
      <div class="grid two">
        <div class="field"><label for="set-url">${w('portal_address')}</label>
          <input id="set-url" value="${esc(s.portal_url)}" placeholder="https://portal.example.com"/></div>
        <div class="field"><label for="set-name">${w('portal_name')}</label><input id="set-name" value="${esc(s.product_name)}"/></div>
      </div>
      <div class="row" style="margin-top:12px"><button class="primary" id="save-portal" type="button">${icon('save')} ${w('save')}</button></div></div>

    <div class="card"><h2>${icon('users', 17)} ${w('who_signs_up')}</h2>
      <p class="muted small">${w('who_signs_up_note')}</p>
      <div class="grid two">
        <div class="field"><label for="set-signup">${w('signup')}</label>
          <select id="set-signup">
            <option value="open" ${s.signup_mode === 'open' ? 'selected' : ''}>${w('signup_open')}</option>
            <option value="domain" ${s.signup_mode === 'domain' ? 'selected' : ''}>${w('signup_domain')}</option>
            <option value="closed" ${s.signup_mode === 'closed' ? 'selected' : ''}>${w('signup_closed')}</option>
          </select></div>
        <div class="field"><label for="set-domains">${w('allowed_domains')}</label>
          <input id="set-domains" value="${esc(s.signup_domains || '')}" placeholder="example.com, example.org"/>
          <span class="small muted">${w('allowed_domains_hint')}</span></div>
      </div>
      <div class="row" style="margin-top:12px"><button class="primary" id="save-signup" type="button">${icon('save')} ${w('save')}</button></div></div>

    <div class="card"><h2>${icon('mail', 17)} ${w('smtp_title')}</h2>
      <p class="muted small">${w('smtp_note')}</p>
      <div id="smtp-box"><p class="muted small">${w('loading')}</p></div>
      <details style="margin-top:12px"><summary class="small" style="cursor:pointer"><b>${w('gmail_title')}</b></summary>
        <ol class="small muted" style="padding-left:20px;margin:8px 0 0">
          <li>${w('gmail_1')}</li>
          <li>${w('gmail_2')}</li>
          <li>${w('gmail_3')}</li>
          <li>${w('gmail_4')}</li>
          <li>${w('gmail_5')}</li>
        </ol></details></div>`;
  const save = (id, pick, done) => { body.querySelector(id).onclick = (e) => busy(e.currentTarget, async () => {
    try { await api('/api/core/settings', { method: 'PUT', body: pick() }); toast(done, 'ok'); await refresh(); }
    catch (err) { toast(err.message, 'bad'); }
  }); };
  save('#save-portal', () => ({ portal_url: body.querySelector('#set-url').value, product_name: body.querySelector('#set-name').value }), w('saved'));
  save('#save-signup', () => ({ signup_mode: body.querySelector('#set-signup').value, signup_domains: body.querySelector('#set-domains').value }),
    w('saved_signup'));
  drawSmtp(body.querySelector('#smtp-box'));
}

async function drawSmtp(box) {
  const m = await api('/api/smtp').catch(() => null);
  if (!m) { box.innerHTML = `<p class="muted small">${w('smtp_unreadable')}</p>`; return; }
  const field = (f, meta) => (meta.secret
    ? secretField(`sm-${f}`, meta.label, { set: !!m.values[f], tail: m.values[f], hint: esc(meta.hint) })
    : `<div class="field"><label for="sm-${f}">${esc(meta.label)}</label>
      ${f === 'security'
        ? `<select id="sm-security">${['starttls', 'ssl', 'none'].map((o) => `<option ${m.values.security === o ? 'selected' : ''}>${o}</option>`).join('')}</select>`
        : `<input id="sm-${f}" value="${esc(m.values[f])}"/>`}
      <span class="small muted">${esc(meta.hint)}</span></div>`);
  box.innerHTML = `<div class="grid two">${Object.entries(m.fields).map(([f, meta]) => field(f, meta)).join('')}</div>
    <div class="row" style="margin-top:12px">
      <button class="primary" id="sm-save" type="button">${icon('save')} ${w('smtp_save')}</button>
      <button id="sm-test" type="button"${offAttr(m.configured ? '' : w('smtp_need'))}>${icon('send')} ${w('smtp_test')}</button>
      ${m.configured ? `<span class="tag ok">${w('set_up')}</span>` : `<span class="tag warn">${w('not_set_up')}</span>`}</div>
    <div id="sm-msg" style="margin-top:10px"></div>
    <div id="sm-log" style="margin-top:18px"></div>`;
  drawMailLog(box.querySelector('#sm-log'));
  wireSecrets(box, { 'sm-password': 16 });       // Gmail App Passwords are always 16 characters
  const out = box.querySelector('#sm-msg');
  box.querySelector('#sm-save').onclick = (e) => busy(e.currentTarget, async () => {
    const values = {};
    Object.keys(m.fields).forEach((f) => { values[f] = box.querySelector(`#sm-${f}`).value.trim(); });
    try { await api('/api/smtp', { method: 'PUT', body: { values } }); toast(w('smtp_saved'), 'ok'); drawSmtp(box); }
    catch (err) { say(out, 'bad', esc(err.message)); }
  });
  box.querySelector('#sm-test').onclick = (e) => busy(e.currentTarget, async () => {
    try { const r = await api('/api/smtp/test', { method: 'POST', body: {} }); say(out, 'ok', w('smtp_sent', { to: esc(r.sent_to) })); }
    catch (err) { say(out, 'bad', esc(err.message)); }
  });
}

// 2026-10-06 owner "Can we have this process of trouble shooting in UI": a reset code that never arrived took an SSH
// session to explain. Recent mail shows every code and notice the portal tried to send and what became of it.
async function drawMailLog(el) {
  const d = await api('/api/smtp/log').catch(() => null);
  if (!d) { el.innerHTML = ''; return; }
  const rows = d.rows.map((r) => {
    const hint = w(`ml_h_${r.outcome}`, { sender: esc(d.sender), error: esc(r.error || ''), per_hour: d.per_hour,
      next: esc(when(r.next_at)), to: esc(r.to) });
    return `<tr><td class="small">${esc(when(r.at))}</td><td>${w(`ml_p_${r.purpose}`)}</td><td>${esc(r.to)}</td>
      <td><span class="tag ${esc(d.tones[r.outcome] || '')}">${w(`ml_o_${r.outcome}`)}</span>
      <div class="small muted">${hint}</div></td></tr>`;
  }).join('');
  el.innerHTML = `<div class="row" style="justify-content:space-between;align-items:center">
      <h3 style="margin:0">${icon('send', 14)} ${w('ml_title')}</h3>
      <button type="button" class="small" id="ml-refresh">${icon('refresh', 12)} ${w('ml_refresh')}</button></div>
    <p class="muted small">${w('ml_note')}</p>
    ${rows ? `<table class="rules"><thead><tr><th>${w('ml_col_when')}</th><th>${w('ml_col_what')}</th><th>${w('ml_col_to')}</th>
      <th>${w('ml_col_result')}</th></tr></thead><tbody>${rows}</tbody></table>`
    : `<p class="muted small">${w('ml_empty')}</p>`}`;
  el.querySelector('#ml-refresh').onclick = (e) => busy(e.currentTarget, () => drawMailLog(el));
}
