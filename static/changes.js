// History - the change log (2026-10-05 owner: "field name, old value, new value, when, who did - for both information and
// documents ... even earlier versions of a document"). One client's log (optionally one year) or the firm's own, searched and
// paged on the server (list.changes); a document's earlier version downloads from its row. Words: ui.changes.
import { esc, t, loadWords, modal, listBox, when, BASE } from './app.js';
import { icon } from './icons.js';

const w = (k, v) => t('changes', k, v);

/** The History button for a screen's header. */
export const historyButton = () => `<button type="button" class="small ghost" data-history>${icon('clock', 13)} ${esc(t('changes', 'open'))}</button>`;

/** Wire every History button in `host` to open the log of client `cid` (year `ay`, or every year), or the firm's (`firm`). */
export async function wireHistory(host, { cid = '', ay = '', name = '', firm = false } = {}) {
  await loadWords('changes');
  host.querySelectorAll('[data-history]').forEach((b) => { b.onclick = () => openHistory({ cid, ay, name, firm }); });
}

export async function openHistory({ cid = '', ay = '', name = '', firm = false } = {}) {
  await loadWords('changes');
  const title = firm ? w('title_firm') : name ? w('title_client', { name }) : w('title');
  let kind = '';
  modal(title, `<p class="small muted">${esc(w('lede'))}</p>
    <div class="tabs ch-tabs" role="tablist">${[['', w('all')], ['info', w('info')], ['doc', w('doc')]].map(([k, l]) =>
      `<button type="button" role="tab" data-kind="${k}" class="${k ? '' : 'on'}">${esc(l)}</button>`).join('')}</div><div data-log></div>`, {
    wide: true,
    onOpen: (m) => {
      const draw = () => listBox(m.querySelector('[data-log]'), {
        list: 'changes', args: { ...(firm ? { firm: 1 } : { cid, ay }), kind }, empty: w('none'),
        wrap: (html) => `<div class="an-scroll"><table class="cc-tbl an-tbl ch-tbl"><thead><tr><th>${esc(w('h_when'))}</th><th>${esc(w('h_who'))}</th>
          <th>${esc(w('h_area'))}</th><th>${esc(w('h_field'))}</th><th>${esc(w('h_old'))}</th><th>${esc(w('h_new'))}</th></tr></thead><tbody>${html}</tbody></table></div>`,
        row: (r) => `<tr class="ch-${esc(r.kind)}"><td class="small">${esc(when(r.at))}</td><td class="small">${esc(r.by)}</td>
          <td class="small">${esc(r.area_label)}${r.ay ? ` <span class="muted">${esc(r.ay)}</span>` : ''}</td><td><b>${esc(r.field)}</b></td>
          <td class="ch-old">${r.old ? esc(r.old) : `<span class="muted">${esc(w('empty'))}</span>`}
            ${r.file ? `<a class="ch-dl" href="${BASE}/api/changes/file/${encodeURIComponent(r.cid)}/${encodeURIComponent(r.ay)}/${encodeURIComponent(r.file.kept_in)}/${encodeURIComponent(r.file.fid)}/${r.file.v}?name=${encodeURIComponent(r.old)}"
              title="${esc(w('download'))}">${icon('download', 13)}</a>` : ''}</td>
          <td class="ch-new">${r.new ? esc(r.new) : `<span class="muted">${esc(w('empty'))}</span>`}</td></tr>`,
      });
      m.querySelectorAll('[data-kind]').forEach((b) => {
        b.onclick = () => { kind = b.dataset.kind; m.querySelectorAll('[data-kind]').forEach((x) => x.classList.toggle('on', x === b)); draw(); };
      });
      draw();
    },
  });
}
