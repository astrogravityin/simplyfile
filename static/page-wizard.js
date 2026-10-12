// New filing - #/wizard[?w=<filing>]. The guided way into every return (2026-10-11 owner: "it must be a wizard"; later: "it must
// cover every filing"): What you're filing (who - a person, an HUF, a firm, an LLP, an AOP / BOI, a company and a trust shown as
// not yet; what applies; what kind of work for a business; the likely form) -> Documents (needed / good to have / typed, each with
// where to get it) -> Upload (one drop zone; each file read, a card per file, the client made from them, a popup for only what is
// missing - a firm's partners from its deed - and the hints the documents imply) -> Review (into My return at the right step, or
// the firm screen that comes next). wizard.py decides (chips wizard.*); this draws. Pictures: wizard-art.js. Words: chip ui.wizard
// (and ui.myreturn for a person's form reason and step names). Worked examples: chip wizard.cases, each with its film.
import { api, esc, toast, busy, pageHead, t, loadWords, dropZone, wireDrops, modal, confirmDialog, when, BASE } from './app.js';
import { icon } from './icons.js';
import { docArt } from './myreturn-art.js';
import { askFirst } from './page-myreturn.js';
import { art, hero, rail } from './wizard-art.js';

const w = (k, v) => t('wizard', k, v);
const m = (k, v) => t('myreturn', k, v);
const money = (n) => `₹${Math.round(Number(n || 0)).toLocaleString('en-IN')}`;
const kindWord = (k) => w(`dk_${k || 'other'}`);
const film = (key, ext) => `${BASE}/static/showcase/${encodeURIComponent(key)}.${ext}`;

/** A filing's form reason: a business's from ui.wizard ({form} filled), a person's from ui.myreturn. */
const formWhy = (f) => (f.from === 'wizard' ? w(f.why, { form: f.form }) : m(f.why));

/** Start a filing for a who-card (and AY) and open it. */
async function begin(who, ay, btn) {
  await busy(btn, async () => {
    try { const v = await api('/api/wizard', { method: 'POST', body: { who, ay, picked: [], step: 'what' } }); location.hash = `#/wizard?w=${encodeURIComponent(v.id)}`; } catch (e) { toast(e.message, 'bad', 8); }
  });
}

/** Play a worked example's film in a popup (its captions too). */
export function playFilm(c) {
  modal(c.title, `<div class="wz-film"><video controls autoplay playsinline preload="metadata" poster="${film(c.film, 'jpg')}">
      <source src="${film(c.film, 'mp4')}" type="video/mp4"/><track kind="captions" srclang="en" default src="${film(c.film, 'vtt')}"/></video>
      <p class="small muted">${esc(c.line)}</p>
      <dl class="wz-film-dl"><dt>${esc(w('watch_form'))}</dt><dd>${esc(c.form)}</dd><dt>${esc(w('watch_opens'))}</dt><dd>${esc(w(`scr_${c.opens}`))}</dd></dl></div>`,
  { wide: true, cls: 'wz-film-modal', eyebrow: w('case_film') });
}

/** The "Watch how" list for one who-card: its worked examples, each played in place. */
function watchList(H, who) {
  const row = [...H.who, ...(H.not_yet || [])].find((x) => x.id === who) || {};
  const list = H.cases.filter((c) => c.who === who && c.has_film);
  modal(w('watch_h', { label: row.label || who }), list.length ? `<ul class="wz-watch">${list.map((c) => `<li><button type="button" class="wz-watch-b" data-film="${esc(c.id)}">
      <span class="wz-play" aria-hidden="true">${icon('play', 14)}</span><span><b>${esc(c.title)}</b><span class="small muted">${esc(c.line)}</span></span>
      <span class="tag">${esc(c.form)}</span></button></li>`).join('')}</ul>` : `<p class="small muted">${esc(w('watch_none'))}</p>`, {
    cls: 'wz-watch-modal', eyebrow: w('watch'),
    onOpen: (body, close) => body.querySelectorAll('[data-film]').forEach((b) => { b.onclick = () => { close(); playFilm(H.cases.find((c) => c.id === b.dataset.film)); }; }),
  });
}

/** A not-yet card (a company, a trust): the one-line note, and a way on - an individual's return, or back to the register. */
function notYet(H, row, ay) {
  modal(w('ny_h', { label: row.label }), `<div class="wz-ny">${art(row.art)}<p>${esc(w(row.note))}</p></div>`, {
    cls: 'wz-ny-modal', eyebrow: w('ny_tag'),
    footer: `<a class="pill" href="#/clients">${esc(w('ny_clients'))}</a>${row.instead && H.who.some((x) => x.id === row.instead)
      ? `<button type="button" class="pill solid" data-instead>${icon('user', 14)} ${esc(w('ny_instead'))}</button>` : ''}`,
    onOpen: (body, close) => {
      const b = body.closest('.modal').querySelector('[data-instead]');
      if (b) b.onclick = () => { close(); begin(row.instead, ay, b); };
      body.closest('.modal').querySelectorAll('a.pill').forEach((a) => { a.onclick = () => close(); });
    },
  });
}

/** The who-cards, grouped (people / businesses, then the not-yet ones) - the start screen's and Clients & years' hero. */
export function whoCards(H, { ay = H.current_ay, compact = false } = {}) {
  const n = (id) => H.cases.filter((c) => c.who === id && c.has_film).length;
  const card = (x, off = false) => `<div class="wz-pick ${off ? 'is-ny' : ''}">
      <button type="button" class="wz-chip" ${off ? `data-ny="${esc(x.id)}"` : `data-start="${esc(x.id)}"`}>${art(x.art)}
        <span class="wz-chip-t"><b>${esc(x.label)}</b>${compact ? '' : `<span class="small muted">${esc(x.sub)}</span>`}</span>
        ${off ? `<span class="tag">${esc(w('ny_tag'))}</span>` : `<span class="wz-go-ic" aria-hidden="true">${icon('right', 14)}</span>`}</button>
      ${!off && n(x.id) ? `<button type="button" class="wz-watch-l small" data-watch="${esc(x.id)}">${icon('play', 11)} ${esc(w('watch'))}</button>` : ''}</div>`;
  const group = (key, rows, off) => (rows.length ? `<div class="wz-wgroup"><h4 class="wz-wh">${esc(w(key))}</h4><div class="wz-start-who">${rows.map((x) => card(x, off)).join('')}</div></div>` : '');
  const people = H.who.filter((x) => x.group !== 'business');
  const biz = H.who.filter((x) => x.group === 'business');
  return `<div class="wz-who-groups" data-ay="${esc(ay)}">${group(people.length > 1 || biz.length ? 'who_people' : 'who_h', people, false)}
    ${biz.length || (H.not_yet || []).length ? `<div class="wz-wgroup"><h4 class="wz-wh">${esc(w('who_business'))}</h4><div class="wz-start-who">${biz.map((x) => card(x)).join('')}${(H.not_yet || []).map((x) => card(x, true)).join('')}</div></div>` : ''}</div>`;
}

/** Wire the who-cards drawn by whoCards inside `root`. */
export function wireWho(root, H, ayOf = () => H.current_ay) {
  root.querySelectorAll('[data-start]').forEach((b) => { b.onclick = () => begin(b.dataset.start, ayOf(), b); });
  root.querySelectorAll('[data-ny]').forEach((b) => { b.onclick = () => notYet(H, H.not_yet.find((x) => x.id === b.dataset.ny), ayOf()); });
  root.querySelectorAll('[data-watch]').forEach((b) => { b.onclick = () => watchList(H, b.dataset.watch); });
}

export async function wizardPage(host) {
  await loadWords('wizard', 'myreturn');
  const q = new URLSearchParams((location.hash.split('?')[1]) || '');
  const H = await api('/api/wizard');
  const wid = q.get('w');
  if (!wid) { startScreen(host, H); return; }
  const S = { v: await api(`/api/wizard/${encodeURIComponent(wid)}`), asked: false, reading: [] };
  const url = (p = '') => `/api/wizard/${encodeURIComponent(wid)}${p}`;
  const put = async (body, quiet = true) => {
    try { S.v = await api(url(), { method: 'PUT', body }); if (!quiet) toast(w('saved'), 'ok'); draw(); } catch (e) { toast(e.message, 'bad', 8); }
  };
  const go = (step) => { put({ step }); window.scrollTo({ top: 0, behavior: 'smooth' }); };
  const whoRow = (id) => H.who.find((x) => x.id === id) || {};
  const firm = () => S.v.flow === 'firm';

  const draw = () => {
    const v = S.v;
    const had = document.activeElement && host.contains(document.activeElement) ? document.activeElement : null;   // a toggled card keeps the focus
    const back = had && (had.dataset.pick ? `[data-pick="${had.dataset.pick}"]` : had.dataset.who ? `[data-who="${had.dataset.who}"]` : '');
    const steps = v.steps.map((id) => ({ id, label: w(`s_${id}`) }));
    const reach = v.client ? v.steps[v.steps.length - 1] : v.steps[2];
    host.innerHTML = pageHead(w('title'), esc(w('lede')), `<span class="tag" style="--t:var(--brand)">${esc(w('ay'))} ${esc(v.ay)}</span>`)
      + `<div class="card wz-rail-card">${rail(steps, v.step, reach)}</div>`
      + `<div class="wz-panel">${({ what, docs, upload, review })[v.step](v)}</div>`;
    wire(v.step);
    if (back && host.querySelector(back)) host.querySelector(back).focus({ preventScroll: true });
  };

  // --- 1 What you're filing --------------------------------------------------------------------------------------------
  const pickCard = (r, on) => `<button type="button" class="wz-card ${on.has(r.id) ? 'is-on' : ''}" aria-pressed="${on.has(r.id)}" data-pick="${esc(r.id)}">
        ${art(r.art)}<span class="wz-txt"><b>${esc(r.label)}</b><span>${esc(r.sub)}</span><em class="wz-sec">${esc(r.sec)}</em></span>
        <span class="wz-tick" aria-hidden="true">${icon('check', 12)}</span></button>`;
  const what = (v) => {
    const on = new Set(v.picked);
    const sameFlow = H.who.filter((x) => (x.flow || 'myreturn') === v.flow || !v.cards.length);
    const who = `<section class="card wz-who"><h3 class="rc-h">${icon('user', 15)} ${esc(w('who_h'))}</h3>
      <div class="wz-grid wz-grid-who" role="radiogroup" aria-label="${esc(w('who_h'))}">${sameFlow.map((x) => `<button type="button" role="radio" aria-checked="${x.id === v.who}"
        class="wz-card ${x.id === v.who ? 'is-on' : ''}" data-who="${esc(x.id)}" ${v.client && x.id !== v.who ? 'disabled' : ''}>
        ${art(x.art)}<span class="wz-txt"><b>${esc(x.label)}</b><span>${esc(x.sub)}</span></span><span class="wz-tick" aria-hidden="true">${icon('check', 12)}</span></button>`).join('')}</div></section>`;
    const rows = H.scenarios.filter((r) => v.offered.includes(r.id));
    const income = rows.filter((r) => r.group !== 'work');
    const work = rows.filter((r) => r.group === 'work');
    const cards = income.length ? `<section class="card wz-what"><h3 class="rc-h">${icon('notebook', 15)} ${esc(w('what_h'))}
        <span class="tag ${on.size ? 'ok' : ''}">${esc(w('picked_n', { n: on.size }))}</span></h3><p class="small muted">${esc(w('what_p'))}</p>
      <div class="wz-grid">${income.map((r) => pickCard(r, on)).join('')}</div></section>` : '';
    const works = v.work_open && work.length ? `<section class="card wz-work"><h3 class="rc-h">${icon('folder', 15)} ${esc(w('work_h'))}</h3>
        <p class="small muted">${esc(w('work_p'))}</p><div class="wz-grid">${work.map((r) => pickCard(r, on)).join('')}</div></section>` : '';
    return who + (firm() ? works + cards : cards + works) + formLine(v) + nav('', 'docs');
  };
  const formLine = (v) => `<section class="card wz-form"><div class="wz-form-badge"><span>${esc(w('form_h'))}</span><b>${esc(v.form.form)}</b></div>
      <div><p class="wz-form-why">${esc(formWhy(v.form))}</p><p class="small muted">${esc(w(firm() ? 'form_note_firm' : 'form_note'))}</p></div></section>`;

  // --- 2 Documents you'll need -----------------------------------------------------------------------------------------
  const docs = (v) => {
    const group = (key, rows) => (rows.length ? `<section class="wz-dgroup"><h4>${esc(w(key))}</h4>${rows.map((d) => `<article class="wz-doc ${d.have ? 'is-in' : ''}">
        ${docArt(d.kind || 'other', d.have > 0)}<div class="wz-doc-b"><div class="wz-doc-h"><b>${esc(d.label)}</b>
          ${d.typed ? `<span class="tag">${icon('edit', 11)} ${esc(w('typed_tag'))}</span>` : d.have ? `<span class="tag ok">${icon('check', 11)} ${esc(w('have_n', { n: d.have }))}</span>`
            : d.need === 'required' ? `<span class="tag warn">${esc(w('missing'))}</span>` : ''}</div>
          <p class="small">${esc(d.what)}</p>
          <details class="wz-where"><summary class="small">${icon('link', 12)} ${esc(w('where'))}</summary><p class="small muted">${esc(d.where)}</p></details></div></article>`).join('')}</section>` : '');
    return `<section class="card wz-docs"><h3 class="rc-h">${icon('folder', 15)} ${esc(w('docs_h'))}</h3><p class="small muted">${esc(w('docs_p'))}</p>
        ${group('g_required', v.docs.filter((d) => d.need === 'required' && !d.typed))}
        ${group('g_optional', v.docs.filter((d) => d.need === 'optional' && !d.typed))}
        ${group('g_typed', v.docs.filter((d) => d.typed))}</section>${formLine(v)}${nav('what', 'upload')}`;
  };

  // --- 3 Upload ----------------------------------------------------------------------------------------------------------
  const STATE = { in: ['ok', 'check', 'st_in'], held: ['', 'clock', 'st_held'], kept: ['', 'folder', 'st_kept'], other: ['warn', 'alert', 'st_other'], other_pan: ['warn', 'alert', 'st_other_pan'], locked: ['warn', 'lock', 'st_locked'] };
  const fileCard = (c, v) => {
    const [tone, ic, word] = c.already ? ['ok', 'check', 'st_already'] : STATE[c.state] || STATE.other;
    const facts = [c.who.pan ? [w('f_pan'), c.who.pan] : null, c.who.name ? [w('f_name'), c.who.name] : null, c.who.gstin ? [w('f_gstin'), c.who.gstin] : null,
      c.who.ay ? [w('f_ay'), c.who.ay] : null].filter(Boolean);
    const found = (c.found || []).filter((f) => !(f.key && ['f_pan', 'f_name', 'f_gstin'].includes(f.label)));
    const note = c.state === 'other' ? (c.problems || [])[0] || w('other_p') : c.state === 'other_pan' ? w('other_pan_p', { pan: c.who.pan, mine: v.client ? v.client.pan : '' })
      : c.state === 'locked' ? w('locked_p') : c.already ? w('already_p') : '';
    return `<article class="wz-file st-${esc(c.state)}">${docArt(c.kind, c.state === 'in' || c.state === 'held' || c.state === 'kept')}
      <div class="wz-file-b"><div class="wz-doc-h"><b>${esc(c.kind === 'other' ? w('st_other') : kindWord(c.kind))}</b><span class="tag ${tone}">${icon(ic, 11)} ${esc(w(word))}</span></div>
        <div class="small muted wz-fname" title="${esc(c.name)}">${esc(c.name)}</div>
        ${c.dest && (c.state === 'in' || c.state === 'kept') ? `<span class="wz-dest small">${icon('right', 11)} ${esc(w(`to_${c.dest}`))}</span>` : ''}
        ${facts.length ? `<dl class="wz-who-dl">${facts.map(([a, b]) => `<dt>${esc(a)}</dt><dd>${esc(b)}</dd>`).join('')}</dl>` : ''}
        ${found.length ? `<ul class="mr-found">${found.slice(0, 6).map((f) => `<li>${esc(f.key ? w(f.label) : f.label)} <b>${esc(f.value)}</b></li>`).join('')}</ul>` : ''}
        ${note ? `<p class="small mr-warn">${icon('alert', 12)} ${esc(note)}</p>` : (c.problems || []).slice(0, 2).map((p) => `<p class="small muted">${icon('info', 12)} ${esc(p)}</p>`).join('')}</div>
      <button type="button" class="small ghost wz-rm" data-rm="${esc(c.id)}" aria-label="${esc(w('remove'))} ${esc(c.name)}" title="${esc(w('remove'))}">${icon('trash', 13)}</button></article>`;
  };
  const clientCard = (v) => {
    const c = v.client;
    const pic = whoRow(v.who).art || (v.self ? 'self' : 'person');
    return `<section class="card wz-client"><h3 class="rc-h">${icon('users', 15)} ${esc(w('client_h'))}</h3>
      ${c ? `<div class="wz-client-b">${art(pic)}<div><b>${esc(c.name)}</b>
          <div class="small muted">${esc(c.pan)}${c.dob ? ` · ${esc(c.dob)}` : ''}${c.gst ? ` · ${esc(c.gst)}` : ''}${c.partners ? ` · ${esc(w('client_partners', { n: c.partners }))}` : ''}</div>
          <span class="tag ${c.made ? 'ok' : ''}">${esc(w(v.self ? 'client_self' : c.made ? 'client_new' : 'client_found'))}</span></div></div>`
        : `<p class="small muted">${esc(w('client_wait'))}</p>`}
      ${v.asks.length ? `<button type="button" class="small" id="wz-ask">${icon('edit', 12)} ${esc(w('ask_h'))}</button>` : ''}</section>`;
  };
  const promptLink = (p, v) => (p.screen === 'myreturn' ? `#/myreturn?c=${encodeURIComponent(v.client.id)}&ay=${encodeURIComponent(v.ay)}&step=${encodeURIComponent(p.step)}`
    : `#/${p.screen}?c=${encodeURIComponent(v.client.id)}&ay=${encodeURIComponent(v.ay)}`);
  const promptWords = (p) => w(`pr_${p.id}`, { amount: money(p.amount), tans: p.tans, sections: p.sections });
  const prompts = (v) => `<section class="card wz-prompts"><h3 class="rc-h">${icon('spark', 15)} ${esc(w('prompts_h'))}</h3>
      ${v.prompts.length ? `<ul class="wz-plist">${v.prompts.map((p) => `<li class="wz-prompt"><span class="wz-pdot" aria-hidden="true">${icon(p.kind ? 'upload' : 'edit', 13)}</span>
        <div><p class="small">${esc(promptWords(p))}</p>
        ${p.kind ? `<button type="button" class="small ghost" data-browse>${icon('upload', 12)} ${esc(w('pr_upload'))}</button>`
          : v.client ? `<a class="small ghost button" href="${promptLink(p, v)}">${icon('right', 12)} ${esc(p.screen === 'myreturn' ? w('pr_enter') : w('pr_open', { screen: w(`scr_${p.screen}`) }))}</a>` : ''}</div></li>`).join('')}</ul>`
        : `<p class="small muted">${esc(w('prompts_none'))}</p>`}</section>`;
  const upload = (v) => `<div class="wz-up"><div class="wz-up-main"><section class="card wz-drop"><h3 class="rc-h">${icon('upload', 15)} ${esc(w('up_h'))}</h3>
        <p class="small muted">${esc(w('up_p'))}</p>
        ${dropZone('wz-file', { accept: '.pdf,.json,.csv,.txt,.xlsx,.xls,.zip', title: w('drop'), hint: w(firm() ? 'drop_hint_firm' : 'drop_hint') })}
        <div class="field wz-pw"><label for="wz-pw">${esc(w('pw'))}</label><input id="wz-pw" type="password" autocomplete="new-password" data-lpignore="true" data-1p-ignore placeholder="${esc(w('pw_ph'))}"/></div></section>
      <section class="card wz-cards"><h3 class="rc-h">${icon('eye', 15)} ${esc(w('cards_h'))} ${v.cards.length ? `<span class="tag">${esc(w('read_n', { n: v.cards.length }))}</span>` : ''}</h3>
        <div class="wz-files" aria-live="polite">${S.reading.map((n) => `<article class="wz-file is-reading"><span class="wz-spin" aria-hidden="true"></span><div class="wz-file-b"><b>${esc(w('reading', { name: n }))}</b></div></article>`).join('')}
        ${v.cards.slice().reverse().map((c) => fileCard(c, v)).join('') || (S.reading.length ? '' : `<p class="small muted">${esc(w('cards_none'))}</p>`)}</div></section></div>
      <aside class="wz-up-side">${clientCard(v)}${prompts(v)}</aside></div>${nav('docs', 'review')}`;

  // --- 4 Review ----------------------------------------------------------------------------------------------------------
  const review = (v) => {
    const gaps = v.docs.filter((d) => d.need === 'required' && !d.typed && !d.have);
    const c = v.client;
    const tile = (k, label, value, sub = '', raw = false) => `<div class="wz-tile k-${k}"><span>${esc(label)}</span><b>${raw ? value : esc(value)}</b>${sub ? `<em>${esc(sub)}</em>` : ''}</div>`;
    const inN = v.cards.filter((x) => x.state === 'in' || x.state === 'kept').length;
    const goLine = c ? (firm() ? `<div class="wz-go-row"><button type="button" class="primary wz-go" id="wz-go">${esc(w('rv_open_firm', { screen: w(`scr_${v.next}`) }))} ${icon('right', 15)}</button>
            <span class="small muted">${esc(w('rv_opens_firm'))}</span></div>`
      : `<div class="wz-go-row"><button type="button" class="primary wz-go" id="wz-go">${esc(w('rv_open'))} ${icon('right', 15)}</button>
            <span class="small muted">${esc(w('rv_opens_at', { step: m(`s_${v.next}`) }))}</span></div>`)
      : `<p class="small mr-warn">${icon('info', 12)} ${esc(w('rv_need_client'))}</p>`;
    return `<section class="card wz-review"><h3 class="rc-h">${icon('check', 15)} ${esc(w('rv_h'))}</h3>
        <div class="wz-tiles">${tile('who', w('rv_who'), c ? c.name : whoRow(v.who).label || v.who, c ? c.pan : '')}
          ${tile('form', w('rv_form'), v.form.form, '')}
          ${tile('docs', w('rv_docs'), w('read_n', { n: inN }), '')}
          ${v.checks ? tile('checks', m('s_check'), v.checks.red + v.checks.amber ? w('rv_checks', { n: v.checks.red + v.checks.amber }) : icon('okcircle', 20), v.checks.red + v.checks.amber ? '' : w('rv_checks_none'), !(v.checks.red + v.checks.amber)) : ''}</div>
        <p class="wz-form-why">${esc(formWhy(v.form))}</p>
        <div class="wz-rv-cols"><div><h4>${esc(w('rv_gaps_h'))}</h4>${gaps.length ? `<ul class="wz-gaps">${gaps.map((d) => `<li>${icon('alert', 12)} ${esc(d.label)}</li>`).join('')}</ul>`
          : `<p class="small mr-ok">${icon('check', 12)} ${esc(w('rv_gaps_none'))}</p>`}</div>
          <div><h4>${esc(w('rv_prompts', { n: v.prompts.length }))}</h4>${v.prompts.length ? `<ul class="wz-gaps">${v.prompts.map((p) => `<li>${icon('spark', 12)} ${esc(promptWords(p))}</li>`).join('')}</ul>`
          : `<p class="small muted">${esc(w('prompts_none'))}</p>`}</div></div>
        ${goLine}</section>${nav('upload', '')}`;
  };

  const nav = (back, next) => `<div class="row tight wz-nav">${back ? `<button type="button" class="mr-back" data-go="${back}">${icon('left', 14)} ${esc(w('back'))}</button>` : '<span></span>'}
      ${next ? `<button type="button" class="primary" data-go="${next}">${esc(w(`go_${next}`))} ${icon('right', 14)}</button>` : ''}</div>`;

  // --- the popup: only what the documents did not give -------------------------------------------------------------------
  const partnerRow = (p = {}, i = 0) => `<div class="wz-prow" data-prow>
      <input aria-label="${esc(w('a_p_name'))}" placeholder="${esc(w('a_p_name'))}" data-p="name" maxlength="120" value="${esc(p.name || '')}"/>
      <input aria-label="${esc(w('a_p_pan'))}" placeholder="${esc(w('a_p_pan'))}" data-p="pan" maxlength="10" autocapitalize="characters" style="text-transform:uppercase" value="${esc(p.pan || '')}"/>
      <input aria-label="${esc(w('a_p_share'))}" placeholder="${esc(w('a_p_share'))}" data-p="share" maxlength="6" inputmode="decimal" value="${esc(p.share || '')}"/>
      <button type="button" class="ghost small" data-prm="${i}" aria-label="${esc(w('a_p_remove'))}" title="${esc(w('a_p_remove'))}">${icon('close', 12)}</button></div>`;
  const askPopup = () => {
    const v = S.v;
    if (!v.asks.length || document.querySelector('.wz-ask-modal')) return;      // one popup at a time
    const field = (a) => {
      const id = `wz-a-${a.id}`;
      if (a.id === 'status') {
        return `<div class="field wz-ask-f"><label>${esc(w('a_status'))}</label><p class="small muted">${esc(w('a_status_hint', { pan: a.pan, kind: w(`k_${a.kind}`), chosen: w(`k_${a.chosen}`) }))}</p>
          <label class="check"><input type="checkbox" data-ask="status" value="switch"/> <span>${esc(w('a_status_switch', { kind: w(`k_${a.kind}`) }))}</span></label></div>`;
      }
      if (a.input === 'company') {                     // a company: what its certificate said, the option, manufacturing, the directors
        const co = a.company || {};
        const dirs = (co.directors || []).length ? co.directors : [{}];
        return `<fieldset class="field wz-ask-f wz-company" data-ask-co="company"><legend>${esc(w('a_company'))}</legend><p class="small muted">${esc(w('a_company_hint'))}</p>
          <div class="wz-co-grid"><label class="field"><span>${esc(w('a_cin'))}</span><input data-co="cin" maxlength="21" style="text-transform:uppercase" autocapitalize="characters" value="${esc(co.cin || '')}"/></label>
          <label class="field"><span>${esc(w('a_incorporated'))}</span><input data-co="incorporated" type="date" value="${esc(co.incorporated || '')}"/></label>
          <label class="field"><span>${esc(w('a_option'))}</span><select data-co="option">${(a.co_options || []).map((o) => `<option value="${esc(o.id)}" ${o.id === co.option ? 'selected' : ''}>${esc(o.label)}</option>`).join('')}</select></label>
          <label class="check wz-co-mfg"><input type="checkbox" data-co="manufacturing" ${co.manufacturing ? 'checked' : ''}/> <span>${esc(w('a_manufacturing'))}</span></label></div>
          <h5 class="wz-co-h">${esc(w('a_directors'))}</h5><div class="wz-dlist">${dirs.map((d) => `<div class="wz-prow" data-drow>
            <input aria-label="${esc(w('a_d_name'))}" placeholder="${esc(w('a_d_name'))}" data-d="name" maxlength="125" value="${esc(d.name || '')}"/>
            <input aria-label="${esc(w('a_d_din'))}" placeholder="${esc(w('a_d_din'))}" data-d="din" maxlength="8" inputmode="numeric" value="${esc(d.din || '')}"/>
            <input aria-label="${esc(w('a_d_pan'))}" placeholder="${esc(w('a_d_pan'))}" data-d="pan" maxlength="10" style="text-transform:uppercase" value="${esc(d.pan || '')}"/>
            <span></span></div>`).join('')}</div></fieldset>`;
      }
      if (a.input === 'partners') {
        const rows = (a.partners || []).length ? a.partners : [{}];
        return `<fieldset class="field wz-ask-f wz-partners" data-ask-list="partners"><legend>${esc(w('a_partners'))}</legend><p class="small muted">${esc(w('a_partners_hint'))}</p>
          <div class="wz-plist2">${rows.map(partnerRow).join('')}</div><button type="button" class="small ghost" data-padd>${icon('plus', 12)} ${esc(w('a_p_add'))}</button></fieldset>`;
      }
      if (a.input === 'choice') {
        const opts = a.options.map((o) => [o, a.id === 'residence' ? w(`res_${o}`) : o]);
        return `<fieldset class="field wz-ask-f"><legend>${esc(w(`a_${a.id}`, { fy: fyOf(v.ay) }))}</legend>${a.id === 'pan_pick' ? `<p class="small muted">${esc(w('a_pan_pick_hint'))}</p>` : ''}
          <div class="wz-choices">${opts.map(([o, l], i) => `<label class="wz-choice"><input type="radio" name="${id}" data-ask="${esc(a.id)}" value="${esc(o)}" ${i === 0 ? 'checked' : ''}/><span>${esc(l)}</span></label>`).join('')}</div></fieldset>`;
      }
      const hint = { pan: 'a_pan_hint', huf_name: 'a_huf_name_hint', dob: 'a_dob_hint', karta_pan: 'a_karta_pan_hint', gstin: 'a_gstin_hint' }[a.id];
      const caps = a.input === 'pan' || a.input === 'gstin';
      return `<div class="field wz-ask-f"><label for="${id}">${esc(w(`a_${a.id}`))}</label>
        <input id="${id}" data-ask="${esc(a.id)}" ${a.input === 'date' ? 'type="date"' : 'autocomplete="off"'} ${caps ? `maxlength="${a.input === 'pan' ? 10 : 15}" style="text-transform:uppercase" autocapitalize="characters"` : 'maxlength="125"'}
          ${a.id === 'name' || a.id === 'huf_name' ? `value="${esc(v.found.name || '')}"` : ''}/>${hint ? `<span class="small muted">${esc(w(hint))}</span>` : ''}</div>`;
    };
    modal(w('ask_h'), `<div class="wz-ask">${art(whoRow(v.who).art || 'person')}<p class="ask-lede">${esc(w('ask_p'))}</p></div>
        <form class="wz-ask-form" novalidate>${v.asks.map(field).join('')}</form>`, {
      cls: 'wz-ask-modal tone-brand', eyebrow: w('ask_eyebrow'),
      footer: `<button type="button" class="pill" data-later>${esc(w('ask_later'))}</button><button type="button" class="pill solid" data-save>${icon('check', 14)} ${esc(w('ask_save'))}</button>`,
      onOpen: (body, close) => {
        const card = body.closest('.modal');
        card.querySelector('[data-later]').onclick = () => close();
        const first = body.querySelector('input:not([type=radio]):not([type=checkbox])') || body.querySelector('input');
        if (first) first.focus();
        const wirePartners = () => body.querySelectorAll('[data-prm]').forEach((b) => { b.onclick = () => { b.closest('[data-prow]').remove(); }; });
        const add = body.querySelector('[data-padd]');
        if (add) add.onclick = () => { body.querySelector('.wz-plist2').insertAdjacentHTML('beforeend', partnerRow({}, body.querySelectorAll('[data-prow]').length)); wirePartners(); };
        wirePartners();
        const save = async (e) => {
          const answers = {};
          body.querySelectorAll('[data-ask]').forEach((x) => {
            if ((x.type === 'radio' || x.type === 'checkbox') && !x.checked) return;
            if (x.value.trim()) answers[x.dataset.ask] = x.value.trim();
          });
          body.querySelectorAll('[data-ask-co]').forEach((fs) => {
            const v = Object.fromEntries([...fs.querySelectorAll('[data-co]')].map((i) => [i.dataset.co, i.type === 'checkbox' ? i.checked : i.value.trim()]));
            v.directors = [...fs.querySelectorAll('[data-drow]')].map((r) => Object.fromEntries([...r.querySelectorAll('[data-d]')].map((i) => [i.dataset.d, i.value.trim()])))
              .filter((d) => d.name);
            answers[fs.dataset.askCo] = v;
          });
          body.querySelectorAll('[data-ask-list]').forEach((fs) => {
            answers[fs.dataset.askList] = [...fs.querySelectorAll('[data-prow]')].map((r) => Object.fromEntries([...r.querySelectorAll('[data-p]')].map((i) => [i.dataset.p, i.value.trim()])))
              .filter((p) => p.name);
          });
          await busy(e.currentTarget, async () => {
            const had = !!S.v.client;
            try { S.v = await api(url(), { method: 'PUT', body: { answers } }); close(); toast(S.v.client && !had ? w(S.v.client.made ? 'made_client' : 'found_client', { name: S.v.client.name }) : w('saved'), 'ok', 6); draw(); if (S.v.asks.length) askPopup(); } catch (err) { toast(err.message, 'bad', 8); }
          });
        };
        card.querySelector('[data-save]').onclick = save;
        body.querySelector('form').onsubmit = (e) => { e.preventDefault(); card.querySelector('[data-save]').click(); };
      } });
  };

  // --- uploads, one after another: each read, its card drawn; the "already here?" question as My return asks it ---------------
  const sendAll = async (files) => {
    const pw = (host.querySelector('#wz-pw') || {}).value || '';
    const hadClient = !!S.v.client;
    S.reading = [...files].map((f) => f.name); draw();
    for (const f of files) {
      let onSame = '';
      for (let i = 0; i < 3; i += 1) {
        const fd = new FormData(); fd.append('file', f); fd.append('password', pw); if (onSame) fd.append('on_same', onSame);
        try {
          const r = await api(url('/files'), { method: 'POST', body: fd });
          S.v = r;
          if (r.ask) { onSame = await askFirst(r.ask, f.name, S.v.ay); if (onSame) continue; }
        } catch (err) { toast(`${f.name}: ${err.message}`, 'bad', 10); }
        break;
      }
      S.reading = S.reading.filter((n) => n !== f.name); draw();
    }
    if (!hadClient && S.v.client) toast(w(S.v.client.made ? 'made_client' : 'found_client', { name: S.v.client.name }), 'ok', 7);
    if (S.v.asks.length) askPopup();
  };

  const wire = (step) => {
    const $ = (s) => host.querySelector(s);
    host.querySelectorAll('.wz-node').forEach((n) => { n.onclick = () => go(n.dataset.step); });
    host.querySelectorAll('[data-go]').forEach((b) => { b.onclick = () => go(b.dataset.go); });
    host.querySelectorAll('[data-who]').forEach((b) => { b.onclick = () => { if (b.dataset.who !== S.v.who) put({ who: b.dataset.who }); }; });
    host.querySelectorAll('[data-pick]').forEach((b) => { b.onclick = () => {
      const on = new Set(S.v.picked); const id = b.dataset.pick;
      const row = H.scenarios.find((r) => r.id === id) || {};
      if (on.has(id)) on.delete(id); else { on.add(id); (row.excludes || []).forEach((x) => on.delete(x)); }   // presumptive or books: one of the two
      put({ picked: [...on] });
    }; });
    if (step === 'upload') {
      const input = $('#wz-file'); input.multiple = true;
      wireDrops(host, () => { const fs = [...input.files]; if (fs.length) sendAll(fs).finally(() => { input.value = ''; }); });
      host.querySelectorAll('[data-browse]').forEach((b) => { b.onclick = () => input.click(); });
      host.querySelectorAll('[data-rm]').forEach((b) => { b.onclick = () => confirmDialog(w('remove_title'), w('remove_body'), async () => {
        try { S.v = await api(url(`/files/${b.dataset.rm}`), { method: 'DELETE' }); draw(); } catch (e) { toast(e.message, 'bad', 8); }
      }, w('remove')); });
      if ($('#wz-ask')) $('#wz-ask').onclick = askPopup;
      if (!S.asked && !S.reading.length && S.v.asks.length && S.v.cards.length) { S.asked = true; askPopup(); }
    }
    if ($('#wz-go')) $('#wz-go').onclick = (e) => busy(e.currentTarget, async () => {
      try { const r = await api(url('/finish'), { method: 'POST', body: {} }); toast(r.said, 'ok'); location.hash = r.link; } catch (err) { toast(err.message, 'bad', 8); }
    });
  };
  draw();
}

const fyOf = (ay) => `${Number(String(ay).slice(0, 4)) - 1}-${String(ay).slice(2, 4)}`;

// --- the start screen: the hero with every who-card (people, businesses, the not-yet ones), the AY, the worked examples, and the
// filings waiting to be carried on ---------------------------------------------------------------------------------------------
function startScreen(host, H) {
  const points = w('start_points').split('|');
  const films = H.cases.filter((c) => c.has_film);
  host.innerHTML = pageHead(w('title'), esc(w('lede')),
    `<label class="cl-ay" for="wz-ay">${icon('clock', 14)}<span>${esc(w('start_ay'))}</span>
       <select id="wz-ay">${H.years.map((y) => `<option ${y === H.current_ay ? 'selected' : ''}>${esc(y)}</option>`).join('')}</select></label>`)
    + `<section class="card wz-start"><div class="wz-start-top"><div class="wz-start-b"><span class="eyebrow">${esc(w('eyebrow'))}</span>
        <h2>${esc(w('start_h'))}</h2><p class="muted">${esc(w('start_p'))}</p>
        <ol class="wz-points">${points.map((p, i) => `<li><span class="wz-num">${i + 1}</span>${esc(p)}</li>`).join('')}</ol></div>
        <div class="wz-start-art">${hero()}</div></div>
        ${H.who.length > 1 || (H.not_yet || []).length ? whoCards(H) : `<button type="button" class="primary wz-cta" data-start="${esc((H.who[0] || {}).id || '')}">${icon('spark', 16)} ${esc(w('start_cta'))}</button>`}</section>`
    + (films.length ? `<section class="card wz-examples"><h3 class="rc-h">${icon('play', 15)} ${esc(w('examples_h'))} <span class="tag">${esc(w('watch_n', { n: films.length }))}</span></h3>
        <p class="small muted">${esc(w('examples_p'))}</p><div class="wz-ex-row">${films.map((c) => `<button type="button" class="wz-ex" data-film="${esc(c.id)}">
          <span class="wz-ex-pic"><img alt="" loading="lazy" src="${film(c.film, 'jpg')}" onerror="this.remove()"/><span class="wz-play" aria-hidden="true">${icon('play', 14)}</span></span>
          <span class="wz-ex-t"><b>${esc(c.title)}</b><span class="tag">${esc(c.form)}</span></span></button>`).join('')}</div></section>` : '')
    + `<section class="card wz-resume"><h3 class="rc-h">${icon('clock', 15)} ${esc(w('resume_h'))}</h3>
        ${H.sessions.length ? `<ul class="wz-res-list">${H.sessions.map((s) => { const who = H.who.find((x) => x.id === s.who) || {};
          return `<li class="wz-res">${art(who.art || 'person')}<div class="wz-res-b"><b>${esc(s.client || who.label || s.who)}</b>
            <span class="small muted">${esc(w(`s_${s.step}`))} · ${esc(s.ay)} · ${esc(w('resume_row', { n: s.files, when: when(s.updated_at) }))}</span></div>
            <button type="button" class="small" data-open="${esc(s.id)}">${esc(w('resume_open'))} ${icon('right', 12)}</button>
            <button type="button" class="small ghost" data-discard="${esc(s.id)}" aria-label="${esc(w('discard'))}" title="${esc(w('discard'))}">${icon('trash', 13)}</button></li>`; }).join('')}</ul>`
          : `<p class="small muted">${esc(w('resume_none'))}</p>`}</section>`;
  const ay = () => (host.querySelector('#wz-ay') || {}).value || H.current_ay;
  wireWho(host, H, ay);
  host.querySelectorAll('.wz-ex[data-film]').forEach((b) => { b.onclick = () => playFilm(H.cases.find((c) => c.id === b.dataset.film)); });
  host.querySelectorAll('[data-open]').forEach((b) => { b.onclick = () => { location.hash = `#/wizard?w=${encodeURIComponent(b.dataset.open)}`; }; });
  host.querySelectorAll('[data-discard]').forEach((b) => { b.onclick = () => confirmDialog(w('discard_title'), w('discard_body'), async () => {
    try { const h = await api(`/api/wizard/${encodeURIComponent(b.dataset.discard)}`, { method: 'DELETE' }); startScreen(host, { ...H, sessions: h.sessions }); } catch (e) { toast(e.message, 'bad', 8); }
  }, w('discard'), { tone: 'warn' }); });
}
