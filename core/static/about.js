// About us (2026-11-09 owner: "It is becoming extremely difficult to know if user is working on the latest version/build").
// One line in the profile menu opens this dialog: who we are (chip ui.about - the ValueStream block, or the AstroGravity block on
// an astrology portal) and the build the server runs, read live from GET /api/about/build (core/about.py). The build this page
// loaded with (ui.js BUILD.seen) is compared with the server's: an old tab says so and offers the reload.
import { api, BASE, esc, modal, t, loadWords, BUILD, when } from './ui.js';

const a = (k, v) => t('about', k, v);
const at = (iso) => when(iso) || a('unknown');

const CSS = `<style>
.about-who{display:flex;gap:16px;align-items:flex-start;padding:16px;border-radius:12px;border-left:4px solid #10a37f;background:var(--panel-2,rgba(0,0,0,.03))}
.about-who img{width:72px;height:72px;object-fit:contain;flex:none}
.about-who h3{margin:0 0 8px;font-size:1.25rem;line-height:1.25}
.about-who p{margin:0 0 6px}
.about-who .eb{font-size:.72rem;letter-spacing:.18em;text-transform:uppercase;color:#d4af6a;font-weight:700}
.about-who.astrogravity{background:#0b2a22;color:#efe9d8;border-left-color:#d4af6a}
.about-who.astrogravity h3{font-family:Georgia,serif;color:#f4ecd8}
.about-who.astrogravity .tg{font-style:italic;color:#3ccf9a}
.about-who.astrogravity .sb{font-weight:700;color:#d4af6a}
.about-build{margin-top:16px}
.about-build dl{display:grid;grid-template-columns:max-content 1fr;gap:4px 14px;margin:8px 0}
.about-build dt{opacity:.7}.about-build dd{margin:0;font-family:ui-monospace,monospace;overflow-wrap:anywhere}
.about-state{padding:8px 12px;border-radius:8px;margin-top:8px}
.about-state.ok{background:rgba(16,163,127,.12)}.about-state.stale{background:rgba(230,140,0,.16);font-weight:600}
.about-state{display:flex;flex-wrap:wrap;gap:8px;align-items:center;justify-content:space-between;margin:8px 0}
@media (max-width:640px){.about-who{flex-direction:column;gap:8px;padding:12px}.about-who img{width:48px;height:48px}.about-who h3{font-size:1.1rem}}
</style>`;

export async function aboutDialog() {
  await loadWords('about');
  const mine = BUILD.seen;                              // the build this tab was loaded with, before asking again
  let d;
  try { d = await api('/api/about/build'); } catch (e) { d = { error: e.message }; }
  const fam = a('family') === 'astrogravity' ? 'astrogravity' : 'valuestream';
  const stale = !d.error && mine && d.build && mine !== d.build;
  const who = `<section class="about-who ${fam}" data-about="who">
      <img src="${esc(BASE + '/' + a('logo'))}" alt="${esc(a('brand'))}">
      <div>${a('eyebrow') ? `<div class="eb">${esc(a('eyebrow'))}</div>` : ''}
        <h3>${esc(a('headline'))}</h3>
        ${a('tagline') ? `<p class="tg">${esc(a('tagline'))}</p>` : ''}
        ${a('subline') ? `<p class="sb">${esc(a('subline'))}</p>` : ''}
        <p>${esc(a('body'))}</p></div></section>`;
  const build = d.error ? `<p class="about-state stale">${esc(a('failed', { error: d.error }))}</p>`
    : `<p class="about-state ${stale ? 'stale' : 'ok'}" data-about="state">${esc(stale ? a('newer') : a('latest'))}
        ${stale ? ` <button type="button" class="primary" data-reload>${esc(a('reload'))}</button>` : ''}</p>
      <dl>
        <dt>${esc(a('commit'))}</dt><dd data-about="commit">${esc(d.commit || a('unknown'))}</dd>
        <dt>${esc(a('commit_date'))}</dt><dd>${esc(at(d.commit_date))}</dd>
        <dt>${esc(a('deployed'))}</dt><dd>${esc(at(d.deployed_at))}</dd>
        <dt>${esc(a('started'))}</dt><dd>${esc(at(d.started_at))}</dd>
        <dt>${esc(a('framework'))}</dt><dd data-about="framework">${esc(d.framework ? a('framework_line', d.framework) : a('unknown'))}</dd>
        <dt>${esc(a('server_build'))}</dt><dd>${esc(d.build || a('unknown'))}</dd>
        <dt>${esc(a('page_build'))}</dt><dd>${esc(mine || a('unknown'))}</dd></dl>`;
  modal(a('title'), `${CSS}<h4>${esc(a('who_title'))}</h4>${who}
      <section class="about-build" data-about="build"><h4>${esc(a('build_title'))}</h4>${build}</section>`, {
    onOpen: (body) => { const r = body.querySelector('[data-reload]'); if (r) r.onclick = () => location.reload(); } });
}
