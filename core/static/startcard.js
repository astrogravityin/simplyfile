// Start here (2026-10-09 owner): the first steps for someone who has just signed up - numbered, each with its screen's link
// and a tick when done. Steps, words and done tests are chips (start.steps, ui.start, start.done); what is done is worked out
// by the server (core/startcard.py). Hide is kept on the server per person; the name menu's Start here brings it back.
import { api, esc, t, loadWords, toast } from './ui.js';
import { icon } from './icons.js';

const w = (k, v) => t('start', k, v);

/** Draw the card into `host` for `screen` (the shell calls this after the screen itself is drawn). */
export async function startCard(host, screen, { force = false } = {}) {
  if (!host) return;
  let d;
  try {
    await loadWords('start');
    d = await api(`/api/start?screen=${encodeURIComponent(screen || '')}`);
  } catch { host.innerHTML = ''; return; }        // the card is a help, never a reason for a screen to fail
  if (!(d.show || (force && d.total))) { host.innerHTML = ''; return; }
  const next = (d.steps.find((s) => !s.done) || {}).id;      // the one to do now stands out
  host.innerHTML = `<section class="card startcard" aria-labelledby="sc-title">
    <div class="sc-head">
      <span class="sc-orb">${icon('flag', 18)}</span>
      <div class="sc-txt"><h2 id="sc-title">${esc(w('title'))}</h2>
        <p class="small muted">${esc(d.all_done ? w('all_done') : w('lede'))}</p></div>
      <span class="tag ${d.all_done ? 'ok' : 'brand'} sc-count">${esc(w('progress', { done: d.done, total: d.total }))}</span>
      <button type="button" class="ghost small" id="sc-hide" data-tip="${esc(w('hide_tip'))}" aria-label="${esc(w('hide_tip'))}">${icon('close', 14)} ${esc(w('hide'))}</button>
    </div>
    <div class="sc-bar" aria-hidden="true"><i style="width:${d.total ? Math.round((d.done / d.total) * 100) : 0}%"></i></div>
    <ol class="sc-steps">${d.steps.map((s) => `<li class="${s.done ? 'done' : ''}" data-step="${esc(s.id)}">
      <span class="sc-n" aria-hidden="true">${s.done ? icon('check', 14) : s.n}</span>
      <div class="sc-body"><b>${esc(s.label)}</b>${s.say ? `<span class="small muted">${esc(s.say)}</span>` : ''}</div>
      ${s.done ? `<span class="tag ok">${esc(w('done_tag'))}</span>`
        : s.href ? `<a class="sc-go" href="${esc(s.href)}" tabindex="-1"><button type="button" class="small ${s.id === next ? 'primary' : 'ghost'}">${esc(w('open'))} ${icon('right', 12)}</button></a>` : ''}
    </li>`).join('')}</ol>
  </section>`;
  host.querySelector('#sc-hide').onclick = async () => {
    try {
      const r = await api('/api/start/hide', { method: 'POST', body: {} });
      host.innerHTML = '';
      toast(r.message, 'ok', 7);
    } catch (e) { toast(e.message, 'bad'); }
  };
}

/** The name menu's Start here: un-hide on the server, then draw it on this screen. */
export async function reopenStartCard(host, screen) {
  await api('/api/start/show', { method: 'POST', body: {} });
  await startCard(host, screen, { force: true });
  if (host) host.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
}
