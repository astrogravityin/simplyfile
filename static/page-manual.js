// User Manual Builder — a cover page plus ordered pages (Header · Background · Picture ·
// Picture Label · Description). Publishing puts it at /m/<slug> on this portal, and every page that
// names a screen becomes a How to Use link on that screen.
import { api, esc, say, state, project, screensOf, loadProjects, modal, listBox, confirmDialog, t, loadWords, ps, offAttr, dropZone, wireDrops, richEditor, when } from './app.js';
import { icon, emptyState } from './icons.js';

// Every word on this screen is chip ui.manual (core/words.py) - none is written here.
const w = (k, v) => t('manual', k, v);

const MAX_IMG = () => Number(ps('manual').max_image_bytes);   // 2026-09-26: chip page.manual
let current = null;      // { id, title, published, manual: {cover, pages} }
let backgrounds = [];

export async function manualPage(host) {
  await loadWords('manual');
  const p = project();
  const d = await api(`/api/manuals?project_id=${encodeURIComponent(p ? p.id : '')}`);
  backgrounds = d.backgrounds;
  if (current) return editor(host);

  host.innerHTML = `<h1>${w('title')}</h1>
    <p class="muted">${w('lede')}</p>
    <div id="mn-msg"></div>
    <div class="card" id="mn-list">
      <div class="row" style="justify-content:space-between">
        <h2>${icon('book', 17)} ${p ? w('manuals_of', { project: esc(p.name) }) : w('manuals')}</h2>
        <button class="primary" id="mn-new" type="button">${icon('plus')} ${w('new_manual')}</button></div>
      <div id="mn-rows" style="margin-top:12px">${d.rows_n ? '' : emptyState('manuals', w('no_manuals_title'), w('no_manuals_body'))}</div>
    </div>`;

  host.querySelector('#mn-new').onclick = () => {
    current = { id: null, project_id: p ? p.id : '', title: '', published: false, manual: emptyManual() };
    editor(host);
  };
  // 2026-10-01 (Phase 3): the manuals are list manuals - one searched page at a time
  const wireRows = (root) => {
  root.querySelectorAll('[data-open]').forEach((b) => {
    b.onclick = async () => {
      const row = await api(`/api/manuals/${b.dataset.open}`);
      current = row.row;
      editor(host);
    };
  });
  root.querySelectorAll('[data-del]').forEach((b) => {
    b.onclick = () => confirmDialog(w('delete_title'), w('delete_body'),
      async () => { await api(`/api/manuals/${b.dataset.del}`, { method: 'DELETE' }); await loadProjects(); manualPage(host); }, w('delete'), { tone: 'danger' });
  });
  };
  if (d.rows_n) listBox(host.querySelector('#mn-rows'), { list: 'manuals', args: { project_id: p ? p.id : '' },
    wrap: (html) => `      <div class="scroll"><table><thead><tr>
        <th>${w('col_title')}</th><th>${w('col_pages')}</th><th>${w('col_published')}</th><th>${w('col_updated')}</th><th></th></tr></thead>
        <tbody>${html}</tbody></table></div>`,
    row: (r) => `<tr>
          <td><b>${esc(r.title)}</b></td><td>${r.pages}</td>
          <td>${r.published ? `<span class="tag ok">${w('live')}</span> <code>/m/${esc(r.slug)}</code>` : `<span class="tag">${w('draft')}</span>`}</td>
          <td class="small muted">${esc(when(r.updated_at))}<br/>${esc(r.updated_by || '')}</td>
          <td class="a"><button class="small" data-open="${esc(r.id)}" type="button">${icon('edit', 14)} ${w('open')}</button>
            <button class="small danger icon" data-del="${esc(r.id)}" type="button" title="${esc(w('delete'))}">${icon('trash', 15)}</button></td></tr>`, wire: (rows) => wireRows(rows) });
}

function emptyManual() {
  const now = new Date();
  return { cover: { title: '', subtitle: '', author: state.user.name || '', version: 'V1.0',
    date_stamp: now.toISOString().slice(0, 10), time_stamp: now.toTimeString().slice(0, 5),
    image: '', background: 'indigo' }, pages: [newPage()] };
}
function newPage() {
  return { id: Math.random().toString(36).slice(2, 12), header: '', background: 'white', image: '', image_label: '', description: '', screen_key: '' };
}

// --- the editor -----------------------------------------------------------------------------------

function editor(host) {
  const m = current.manual;
  const bgOptions = (sel) => backgrounds.map((b) => `<option value="${b.id}" ${b.id === sel ? 'selected' : ''}>${esc(b.label)}</option>`).join('');
  const screenOptions = (sel) => `<option value="">${w('no_screen_option')}</option>` + screensOf()
    .map((s) => `<option value="${esc(s.key)}" ${s.key === sel ? 'selected' : ''}>${esc(s.label)}</option>`).join('');

  host.innerHTML = `<div class="row" style="justify-content:space-between;align-items:flex-start">
      <div><h1 style="margin-bottom:2px">${w(current.id ? 'edit_manual' : 'new_manual')}</h1>
        <p class="muted small" style="margin:0">${w(current.published ? 'state_published' : 'state_draft')}</p></div>
      <button id="mn-back" type="button">${icon('left', 15)} ${w('all_manuals')}</button></div>
    <div id="mn-msg" style="margin-top:12px"></div>

    <div class="split">
      <div>
        <div class="card" id="mn-cover"><h2>${w('cover')}</h2>
          <div class="grid two">
            <div class="field"><label for="c-title">${w('col_title')}</label><input id="c-title" value="${esc(m.cover.title)}"/></div>
            <div class="field"><label for="c-sub">${w('subtitle')}</label><input id="c-sub" value="${esc(m.cover.subtitle)}"/></div>
            <div class="field"><label for="c-author">${w('author')}</label><input id="c-author" value="${esc(m.cover.author)}"/></div>
            <div class="field"><label for="c-ver">${w('version')}</label><input id="c-ver" value="${esc(m.cover.version)}"/></div>
            <div class="field"><label for="c-date">${w('date')}</label><input id="c-date" value="${esc(m.cover.date_stamp)}"/></div>
            <div class="field"><label for="c-time">${w('time')}</label><input id="c-time" value="${esc(m.cover.time_stamp)}"/></div>
            <div class="field"><label for="c-bg">${w('background')}</label><select id="c-bg">${bgOptions(m.cover.background)}</select></div>
            <div class="field"><label for="c-img">${w('cover_picture')}</label>
              <input id="c-img" type="file" accept="image/*"/>
              ${m.cover.image ? `<button class="small ghost" id="c-img-clear" type="button">${w('remove_picture')}</button>` : ''}</div>
          </div>
        </div>

        <div id="mn-pages"></div>
        <div class="row"><button id="mn-addpage" type="button">${icon('plus')} ${w('add_page')}</button></div>
      </div>

      <div>
        <div class="card" id="mn-side" style="position:sticky;top:16px">
          <div class="row" style="justify-content:space-between">
            <h2 style="margin:0">${w('preview')}</h2>
            <div class="row tight">
              <button class="small" id="mn-refresh" type="button">${icon('refresh', 14)} ${w('refresh')}</button>
              <button class="small" id="mn-print" type="button">${icon('book', 14)} ${w('print')}</button>
            </div></div>
          <iframe class="preview" id="mn-preview" title="${esc(w('preview_title'))}"></iframe>
          <div class="row" style="margin-top:12px">
            <button class="primary" id="mn-save" type="button">${icon('save')} ${w('save')}</button>
            <button id="mn-publish" type="button" title="${esc(w(current.published ? 'unpublish_tip' : 'publish_tip'))}">${w(current.published ? 'unpublish' : 'publish')}</button>
            ${current.id ? `<button id="mn-download" type="button">${icon('download')} ${w('download')}</button>` : ''}
          </div>
          <div id="mn-link" class="small muted" style="margin-top:8px"></div>
        </div>
      </div>
    </div>`;

  const msg = host.querySelector('#mn-msg');
  host.querySelector('#mn-back').onclick = () => { current = null; manualPage(host); };

  // cover
  // Typing anywhere redraws the preview a moment later — a preview that lags the words is worse
  // than none, and a render per keystroke is a render per keystroke.
  let pending = null;
  const soon = () => { clearTimeout(pending); pending = setTimeout(refresh, 400); };
  const bind = (id, set) => { const el = host.querySelector(id); if (el) el.oninput = el.onchange = () => { set(el.value); soon(); }; };
  bind('#c-title', (v) => { m.cover.title = v; });
  bind('#c-sub', (v) => { m.cover.subtitle = v; });
  bind('#c-author', (v) => { m.cover.author = v; });
  bind('#c-ver', (v) => { m.cover.version = v; });
  bind('#c-date', (v) => { m.cover.date_stamp = v; });
  bind('#c-time', (v) => { m.cover.time_stamp = v; });
  bind('#c-bg', (v) => { m.cover.background = v; });
  host.querySelector('#c-img').onchange = (e) => readImage(e.target.files[0], msg, (data) => { m.cover.image = data; editor(host); });
  const clear = host.querySelector('#c-img-clear');
  if (clear) clear.onclick = () => { m.cover.image = ''; editor(host); };

  drawPages(host, msg);
  host.querySelector('#mn-addpage').onclick = () => { m.pages.push(newPage()); drawPages(host, msg); refresh(); };
  host.querySelector('#mn-refresh').onclick = refresh;
  host.querySelector('#mn-print').onclick = () => {
    const frame = host.querySelector('#mn-preview');
    frame.contentWindow.focus();
    frame.contentWindow.print();
  };
  host.querySelector('#mn-save').onclick = () => save(host, msg, null);
  host.querySelector('#mn-publish').onclick = () => confirmDialog(w(current.published ? 'unpublish' : 'publish'),
    w(current.published ? 'unpublish_tip' : 'publish_tip'), () => save(host, msg, !current.published), w(current.published ? 'unpublish' : 'publish'), { tone: 'brand' });
  const dl = host.querySelector('#mn-download');
  if (dl) dl.onclick = () => window.open(`${new URL('..', import.meta.url).href.replace(/\/$/, '')}/api/manuals/${current.id}/download`, '_blank');

  showLink(host);
  refresh();

  function refresh() {
    api('/api/manuals/render', { method: 'POST', body: { manual: m } })
      .then((d) => { host.querySelector('#mn-preview').srcdoc = `<!doctype html><meta charset="utf-8"><style>body{margin:0;background:#e2e8f0}</style>${d.html}`; })
      .catch((e) => say(msg, 'bad', esc(e.message)));
  }

  function drawPages(root, m2) {
    const wrap = root.querySelector('#mn-pages');
    wrap.innerHTML = m.pages.map((pg, i) => `<div class="card" data-page="${i}">
        <div class="row" style="justify-content:space-between">
          <h2 style="margin:0">${w('page_n', { n: i + 1 })}</h2>
          <div class="row tight">
            <button class="small" data-up="${i}" type="button" aria-label="${esc(w('move_up'))}" ${offAttr(i === 0 ? t('shell', 'off_top') : '')}>↑</button>
            <button class="small" data-down="${i}" type="button" aria-label="${esc(w('move_down'))}" ${offAttr(i === m.pages.length - 1 ? t('shell', 'off_bottom') : '')}>↓</button>
            <button class="small danger" data-rm="${i}" type="button" ${offAttr(m.pages.length === 1 ? w('last_page_stays') : '')}>${w('remove')}</button>
          </div></div>
        <div class="grid two" style="margin-top:8px">
          <div class="field"><label>${w('header')}</label><input data-p="${i}" data-f="header" aria-label="${esc(w('header'))}" value="${esc(pg.header)}"/></div>
          <div class="field"><label>${w('background')}</label><select data-p="${i}" data-f="background" aria-label="${esc(w('background'))}">${bgOptions(pg.background)}</select></div>
          <div class="field"><label>${w('documents_screen')}</label><select data-p="${i}" data-f="screen_key" aria-label="${esc(w('documents_screen'))}">${screenOptions(pg.screen_key)}</select></div>
          <div class="field"><label>${w('picture_label')}</label><input data-p="${i}" data-f="image_label" aria-label="${esc(w('picture_label'))}" value="${esc(pg.image_label)}"/></div>
        </div>
        <div class="field" style="margin-top:8px"><label>${w('picture')}</label>
          <div class="row tight">${dropZone(`mi-${i}`, { accept: 'image/*', title: w('picture') })}
            ${pg.image ? `<button class="small ghost" data-imgclear="${i}" type="button">${w('remove_picture')}</button>
              <img src="${esc(pg.image)}" alt="" style="height:38px;border-radius:6px"/>` : ''}</div></div>
        <div class="field" style="margin-top:10px"><label>${w('description')}</label>
          <div data-rich="${i}"></div>
        </div>
      </div>`).join('');

    wrap.querySelectorAll('[data-f]').forEach((el) => {
      el.oninput = el.onchange = () => {
        m.pages[Number(el.dataset.p)][el.dataset.f] = el.value;
        soon();
      };
    });
    // 2026-10-02 owner "yes do both": a page's description is the ONE rich-text editor (core ui.js richEditor) - no
    // toolbar of its own here; a picture rides inside as a data: address (what a manual keeps), within chip max_image_bytes
    wrap.querySelectorAll('[data-rich]').forEach((el) => {
      const i = Number(el.dataset.rich);
      richEditor(el, { html: m.pages[i].description, skip: ps('manual').rich_skip || [],
        upload: (f) => new Promise((done, fail) => readImage(f, msg, done, fail)),
        onChange: (h) => { m.pages[i].description = h; soon(); }, onSave: () => save(root, msg, null) });
    });
    wireDrops(wrap, (f, id) => f && readImage(f, msg, (data) => { m.pages[Number(id.slice(3))].image = data; drawPages(root, m2); refresh(); }));
    wrap.querySelectorAll('[data-imgclear]').forEach((b) => {
      b.onclick = () => { m.pages[Number(b.dataset.imgclear)].image = ''; drawPages(root, m2); refresh(); };
    });
    wrap.querySelectorAll('[data-up]').forEach((b) => {
      b.onclick = () => { const i = Number(b.dataset.up); [m.pages[i - 1], m.pages[i]] = [m.pages[i], m.pages[i - 1]]; drawPages(root, m2); refresh(); };
    });
    wrap.querySelectorAll('[data-down]').forEach((b) => {
      b.onclick = () => { const i = Number(b.dataset.down); [m.pages[i + 1], m.pages[i]] = [m.pages[i], m.pages[i + 1]]; drawPages(root, m2); refresh(); };
    });
    wrap.querySelectorAll('[data-rm]').forEach((b) => {
      b.onclick = () => confirmDialog(w('remove_page_title'), w('remove_page_body'),
        () => { m.pages.splice(Number(b.dataset.rm), 1); drawPages(root, m2); refresh(); }, w('delete'), { tone: 'danger' });
    });
  }

  async function save(root, out, publish) {
    try {
      const d = await api('/api/manuals', { method: 'POST', saved: true, body: {
        id: current.id, project_id: current.project_id || (project() || {}).id || '',
        title: m.cover.title || w('untitled'), manual: m,
        published: publish === null ? undefined : publish } });
      current = d.row;
      await loadProjects();
      const wired = d.wired_screens
        ? w(d.wired_screens === 1 ? 'wired_one' : 'wired_many', { n: d.wired_screens }) : '';
      say(out, 'ok', w(current.published ? 'saved_published' : 'saved') + wired);
      showLink(root);
      root.querySelector('#mn-publish').textContent = w(current.published ? 'unpublish' : 'publish');
    } catch (e) { say(out, 'bad', esc(e.message)); }
  }

  function showLink(root) {
    const box = root.querySelector('#mn-link');
    if (!box) return;
    if (!current.published) {
      box.innerHTML = w('publish_hint');
      return;
    }
    const url = (state.portalUrl || location.origin) + `/m/${current.slug}`;
    box.innerHTML = `${w('public_link', { url: esc(url) })}
      ${state.portalUrl ? '' : ` <span class="tag warn">${w('set_address')}</span>`}`;
  }
}

function readImage(file, msg, done, fail = () => {}) {
  if (!file) return;
  if (file.size > MAX_IMG()) { const why = w('too_big', { mb: (file.size / 1e6).toFixed(1) }); say(msg, 'bad', why); fail(new Error(why)); return; }
  const fr = new FileReader();
  fr.onload = () => done(String(fr.result));
  fr.readAsDataURL(file);
}
