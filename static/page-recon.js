// Reconcile - SimplyFile phase 3. #/recon?c=<client>&ay=<AY>: the portal files (26AS / AIS / TIS) for the year, and every
// finding of books against portal - red first, then amber, then what agrees. Red and amber take an Explain note; an
// unexplained red keeps the year out of Review (chip recon.settings block_stages). Words: chip ui.recon; colours: page.recon.
import { api, esc, toast, busy, pageHead, confirmDialog, t, ps, loadWords, uploadBox, modal, when, may } from './app.js';
import { clientPicker } from './page-intake.js';
import { icon } from './icons.js';

const w = (k, v) => t('recon', k, v);

export async function reconPage(host) {
  await loadWords('recon', 'intake');
  const p = new URLSearchParams((location.hash.split('?')[1]) || '');
  if (!p.get('c')) return clientPicker(host, 'recon');
  const K = await api('/api/clients/settings');
  const cid = p.get('c');
  const ay = p.get('ay') || K.current_ay;
  const base = `/api/recon/${encodeURIComponent(cid)}/${encodeURIComponent(ay)}`;
  const client = await api(`/api/clients/${encodeURIComponent(cid)}`);
  host.innerHTML = pageHead(`${w('title')} · ${client.name}`, esc(w('lede')),
    `<select id="rc-ay" aria-label="${esc(w('ay'))}">${K.years.map((y) => `<option ${y === ay ? 'selected' : ''}>${esc(y)}</option>`).join('')}</select>
     <button type="button" id="rc-up">${icon('upload', 14)} ${esc(w('upload'))}</button>`)
    + '<section class="card" id="rc-files"></section><section class="card" id="rc-find"></section>';
  host.querySelector('#rc-ay').onchange = (e) => { location.hash = `#/recon?c=${encodeURIComponent(cid)}&ay=${encodeURIComponent(e.target.value)}`; };
  const draw = (d) => {
    const files = host.querySelector('#rc-files');
    files.innerHTML = d.files.length ? d.files.map((f) => `<div class="kw-row small" data-f="${esc(f.id)}" data-name="${esc(f.name)}">
        <div class="kw-info"><span class="tag brand">${esc(w(`src_${f.source}`))}</span> <b>${esc(f.name)}</b>
          <span class="muted">${esc(when(f.uploaded_at))} · ${esc(w('n_entries', { n: f.entries }))}</span>
          ${f.pan_seen ? '' : `<span class="tag warn">${icon('alert', 11)} ${esc(w('pan_missing'))}</span>`}</div>
        ${may('recon', 'delete') ? `<button type="button" class="small ghost" data-del aria-label="${esc(w('delete'))}">${icon('trash', 12)}</button>` : ''}</div>`).join('')
      : `<p class="small muted">${esc(w('no_files'))}</p>`;
    files.querySelectorAll('[data-f]').forEach((el) => {
      const del = el.querySelector('[data-del]');
      if (del) del.onclick = () => confirmDialog(w('delete_title', { name: el.dataset.name }), w('delete_body'), async () => {
        try { await api(`${base}/${el.dataset.f}`, { method: 'DELETE' }); toast(w('deleted'), 'ok'); load(); }
        catch (err) { toast(err.message, 'bad', 8); }
      }, w('delete'), { tone: 'danger' });
    });
    const find = host.querySelector('#rc-find');
    const tag = ps('recon').severity_tag;
    find.innerHTML = d.findings.length ? `<p class="small muted">${esc(w('counts', d.summary))} · ${esc(w('books_portal', d))}</p>`
      + d.findings.map((f) => `<div class="kw-row small" data-id="${esc(f.id)}">
          <div class="kw-info"><span class="${esc(tag[f.severity])}">${esc(w(`sev_${f.severity}`))}</span> ${esc(f.title)}
            ${f.note ? `<div class="muted">${icon('check', 11)} ${esc(w('explained', f.note))}</div>` : ''}</div>
          ${f.severity !== 'ok' ? `<button type="button" class="small ghost" data-explain>${icon('edit', 12)} ${esc(w('explain'))}</button>` : ''}</div>`).join('')
      : `<p class="small muted">${esc(w('nothing'))}</p>`;
    find.querySelectorAll('[data-explain]').forEach((b) => {
      const f = d.findings.find((x) => x.id === b.closest('[data-id]').dataset.id);
      b.onclick = () => modal(w('explain_title'), `<p class="small">${esc(f.title)}</p><div class="field"><label for="rc-note">${esc(w('explain_hint'))}</label>
          <textarea id="rc-note" rows="3">${esc(f.note ? f.note.text : '')}</textarea></div>`, {
        footer: `<button type="button" class="primary" data-save>${icon('save', 14)} ${esc(w('save'))}</button>`,
        onOpen: (m, close) => {
          m.closest('.modal').querySelector('[data-save]').onclick = (e) => busy(e.currentTarget, async () => {
            try {
              draw(await api(`${base}/notes/${f.id}`, { method: 'PUT', body: { note: m.querySelector('#rc-note').value } }));
              toast(w('saved'), 'ok'); close(true);
            } catch (err) { toast(err.message, 'bad', 8); }
          });
        } });
    });
  };
  const load = async () => draw(await api(base));
  host.querySelector('#rc-up').onclick = () => uploadBox(w('upload'), ps('recon').exts, base, load);
  load();
}
