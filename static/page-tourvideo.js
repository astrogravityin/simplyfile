// Tour Video - owner only (2026-10-02 owner: "Tour Video card we have in the studio - bring that to sm,
// visible to portal admin"). One row per tour script (list.tour_videos): its state (chip tourvideo.state - no video /
// script changed since / up to date), Check steps, Record video, and the MP4, subtitles and YouTube description.
// The runner is the studio's own (chip tourvideo.settings); one job at a time, followed in the ONE work window.
// Every word is chip ui.tourvideo.
import { api, BASE, esc, toast, busy, pageHead, confirmDialog, t, loadWords, listBox, followJob, when, ps, onEvent } from './app.js';
import { icon } from './icons.js';

const w = (k, v) => t('tourvideo', k, v);

export async function tourVideoPage(host) {
  await loadWords('tourvideo');
  host.innerHTML = pageHead(w('title'), w('lede'))   // 2026-11-14: Record signs in as you - no Sign in once
    + '<section class="card" id="tv-list"></section>';
  let reload = () => {};
  const run = async (what, key, title) => {
    const j = await api(`/api/tourvideo/${what}`, { method: 'POST', body: { key } });
    followJob('/api/tourvideo/job', w(`working_${what}`, { title }), j, null);
    const off = onEvent('job', (d) => {          // the server tells when the run ends (core/events.py) - no poll
      if (d.url !== '/api/tourvideo/job' || d.job.status === 'running') return;
      off();
      reload();
    });
  };
  listBox(host.querySelector('#tv-list'), {
    list: 'tour_videos',
    empty: w('empty'),
    row: (r) => {
      const file = (fid) => `${BASE}/api/tourvideo/${encodeURIComponent(r.key)}/file/${fid}`;
      return `<div class="kw-row small" data-key="${esc(r.key)}" data-title="${esc(r.title)}">
        <div class="kw-info"><b>${esc(r.title)}</b> <span class="muted">${esc(w('steps_n', { n: r.steps }))}</span>
          <span class="${esc(ps('tourvideo').state_tag[r.state])}">${esc(w(`state_${r.state}`))}</span>
          ${r.video_at ? `<span class="muted">${esc(w('made_at', { when: when(new Date(r.video_at * 1000).toISOString()) }))}</span>` : ''}</div>
        <div class="row tight">
          <button type="button" class="small ghost" data-check data-tip="${esc(w('tip_check'))}">${icon('check', 12)} ${esc(w('check'))}</button>
          <button type="button" class="small" data-record data-tip="${esc(w('tip_record'))}">${icon('film', 12)} ${esc(w(r.video_at ? 'record_again' : 'record'))}</button>
          ${r.video_at ? `<a class="small ghost button" href="${file('mp4')}">${icon('download', 12)} ${esc(w('dl_mp4'))}</a>
            <a class="small ghost button" href="${file('srt')}">${icon('download', 12)} ${esc(w('dl_srt'))}</a>
            <button type="button" class="small ghost" data-desc>${icon('share', 12)} ${esc(w('copy_desc'))}</button>` : ''}</div></div>`;
    },
    wire: (rows, _r, load) => {
      reload = load;
      rows.querySelectorAll('[data-key]').forEach((el) => {
        const { key, title } = el.dataset;
        const go = (what) => (e) => busy(e.currentTarget, async () => { try { await run(what, key, title); } catch (err) { toast(err.message, 'bad', 8); } });
        el.querySelector('[data-check]').onclick = go('check');
        el.querySelector('[data-record]').onclick = (e) => confirmDialog(w('rec_title', { title }), w('rec_body'), () => go('record')(e), w('rec_yes'), { tone: 'brand' });
        const d = el.querySelector('[data-desc]');
        if (d) d.onclick = () => busy(d, async () => {
          const txt = await fetch(`${BASE}/api/tourvideo/${encodeURIComponent(key)}/file/txt`, { credentials: 'include' }).then((x) => x.text());
          await navigator.clipboard.writeText(txt);
          toast(w('copied'), 'ok');
        });
      });
    },
  });
}
