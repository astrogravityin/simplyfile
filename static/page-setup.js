// Setup — register a project folder, Scan it for screens, narration settings. Storage limits live on Admin -> Storage.
// People, sign-up, mail and the portal's own address are the framework's: People & access.
import { api, BASE, esc, when, say, state, project, loadProjects, render, confirmDialog, modal,
         secretField, wireSecrets, toast, busy, t, loadWords, keep } from './app.js';
import { icon, emptyState } from './icons.js';

// Every word on this screen is chip ui.setup (core/words.py) - none is written here.
const w = (k, v) => t('setup', k, v);

let scanned = null;      // the last scan's candidate rows, before they are saved

/** One row of the first-run checklist: done rows go quiet, the rest keep their number. */
const step = (isDone, n, title, line) => `<div class="step ${isDone ? 'done' : ''}">
    <span class="mark">${isDone ? icon('check', 13) : n}</span>
    <span class="body"><b>${title}</b><span>${line}</span></span></div>`;

export async function setupPage(host) {
  await loadWords('setup');
  const s = await api('/api/settings');
  const isOwner = state.user.role === 'owner';
  const p = project();
  const smtpReady = await api('/api/smtp').then((d) => d.configured).catch(() => false);
  const done = {
    address: !!s.settings.portal_url,
    project: state.projects.length > 0,
    screens: !!(p && (p.screens || []).length),
    email: smtpReady,
  };
  const left = Object.values(done).filter((x) => !x).length;

  host.innerHTML = `
    <h1>${w('title')}</h1>
    <p class="muted">${w('lede')}</p>
    <div id="setup-msg"></div>

    ${left ? `<div class="card" id="setup-start">
      <h2>${icon('check', 17)} ${w('getting_started')}</h2>
      <p class="muted small">${w('done_count', { done: Object.keys(done).length - left, total: Object.keys(done).length })}</p>
      <div class="steps">
        ${step(done.address, 1, w('step_address'), w('step_address_line'))}
        ${step(done.project, 2, w('step_project'), w('step_project_line'))}
        ${step(done.screens, 3, w('step_scan'), w('step_scan_line'))}
        ${step(done.email, 4, w('step_email'), w('step_email_line'))}
      </div>
    </div>` : ''}

    <div class="card" id="setup-projects">
      <h2>${icon('folder', 17)} ${w('projects')}</h2>
      <p class="muted small">${w('projects_note')}</p>
      <div class="scroll" style="max-height:none"><table><thead><tr>
        <th>${w('col_name')}</th><th>${w('col_key')}</th><th>${w('col_source')}</th><th>${w('col_screens')}</th><th>${w('col_live_at')}</th><th></th></tr></thead>
        <tbody id="proj-rows"></tbody></table></div>
      <div class="row" style="margin-top:14px"><button class="primary" id="new-proj" type="button">${icon('plus')} ${w('register')}</button></div>
    </div>

    ${p ? `<div class="card" id="setup-scan">
      <h2>${icon('search', 17)} ${w('scan_of', { project: esc(p.name) })}</h2>
      <p class="muted small">${p.source_kind === 'git'
          ? w('scan_reads', { source: `<code>${esc(p.git_url || w('no_repository'))}</code>` })
          : w('scan_reads_folder', { source: `<code>${esc(p.folder || w('no_folder'))}</code>` })}
        ${w('scan_note')}</p>
      <div class="row">
        <button class="primary" id="scan" type="button">${icon('search')} ${w('scan')}</button>
        <button id="add-screen" type="button">${icon('plus')} ${w('add_by_hand')}</button>
        <span class="small muted" id="scan-note">${p.scanned_at ? w('last_scanned', { at: esc(when(p.scanned_at)) }) : w('never_scanned')}</span>
      </div>
      <div id="scan-msg" style="margin-top:12px"></div>
      <div id="scan-out"></div>
    </div>` : `<div class="card" id="setup-scan"><p class="muted">${w('register_first')}</p></div>`}

    <div class="card" id="setup-narration">
      <h2>${icon('mic', 17)} ${w('narration')}</h2>
      <p class="muted small">${w('narration_note')}</p>
      <div class="grid two">
        <div class="field"><label for="set-help">${w('help_video')}</label>
          <input id="set-help" value="${esc(s.settings.help_video_url || '')}" placeholder="https://www.youtube.com/embed/…" ${isOwner ? '' : 'disabled'}/>
          <span class="small muted">${w('help_video_note', { guide: `${BASE}/help/gemini-key` })}</span></div>
      </div>
      <div class="field" style="margin-top:10px"><label for="set-lex">${w('lex_label')}</label>
        <textarea id="set-lex" ${isOwner ? '' : 'disabled'} placeholder="${esc(w('lex_placeholder'))}">${esc(Object.entries(s.lexicon || {}).map(([k, v]) => `${k} = ${v}`).join('\n'))}</textarea>
        <span class="small muted">${w('lex_hint')} · ${w('lex_note')}</span></div>
      ${isOwner
        ? `<div class="row" style="margin-top:14px"><button class="primary" id="save-set" type="button">${icon('save')} ${w('save')}</button></div>`
        : `<p class="small muted">${w('owner_only')}</p>`}
    </div>

    <div class="card" id="setup-wire">
      <h2>${icon('external', 17)} ${w('wire')}</h2>
      <p class="muted small">${w('wire_note')}</p>
      <pre>GET ${esc(state.portalUrl || '')}/api/public/howto/${esc((p && p.key) || 'your-project')}
→ { "screens": { "billing": [ { "label": "...", "url": "...", "type": "youtube" } ] } }</pre>
      <p class="muted small">${w('wire_or')}</p>
      <pre>&lt;script src="${esc(state.portalUrl || '')}/embed/howto.js"
        data-project="${esc((p && p.key) || 'your-project')}" data-screen="billing"&gt;&lt;/script&gt;</pre>
    </div>`;

  const msg = host.querySelector('#setup-msg');
  drawProjects(host);
  host.querySelector('#new-proj').onclick = () => projectDialog(null);

  if (p) {
    host.querySelector('#scan').onclick = (e) => busy(e.currentTarget, () => runScan(host, msg));
    host.querySelector('#add-screen').onclick = () => {
      scanned = scanned || (p.screens || []).map((x) => ({ ...x, selected: true, confidence: 'saved', why: 'saved' }));
      scanned.unshift({ key: '', label: '', route: '', file: '', group: '', why: w('why_by_hand'), confidence: 'saved', selected: true });
      drawScan(host, msg);
    };
    if (p.screens && p.screens.length) {
      scanned = p.screens.map((x) => ({ ...x, selected: true, confidence: 'saved', why: 'saved' }));
      drawScan(host, msg);
    }
  }

  if (isOwner) {
    host.querySelector('#save-set').onclick = async () => {
      const lexicon = {};
      host.querySelector('#set-lex').value.split('\n').forEach((line) => {
        const i = line.indexOf('=');
        if (i > 0) lexicon[line.slice(0, i).trim()] = line.slice(i + 1).trim();
      });
      try {
        const d = await api('/api/settings', { method: 'PUT', body: {
          help_video_url: host.querySelector('#set-help').value, lexicon } });
        say(msg, 'ok', w('saved'));
      } catch (e) { say(msg, 'bad', esc(e.message)); }
    };
  }
}

// --- projects ------------------------------------------------------------------------------------

function drawProjects(host) {
  const body = host.querySelector('#proj-rows');
  if (!state.projects.length) {
    body.innerHTML = `<tr><td colspan="6">${emptyState('projects', w('no_projects_title'),
      w('no_projects_body'))}</td></tr>`;
    return;
  }
  body.innerHTML = state.projects.map((p) => `<tr>
      <td><b>${esc(p.name)}</b></td><td><code>${esc(p.key)}</code></td>
      <td class="small muted">${p.source_kind === 'git'
        ? `<span class="tag brand">git</span> ${esc(p.git_url || '')}${p.git_branch ? ` <span class="tag">${esc(p.git_branch)}</span>` : ''}`
        : esc(p.folder || '—')}</td>
      <td>${(p.screens || []).length}</td>
      <td class="small">${p.site_url ? `<a href="${esc(p.site_url)}" target="_blank" rel="noopener">${w('open')}</a>` : '—'}</td>
      <td class="a"><button class="small" data-edit="${esc(p.id)}" type="button">${icon('edit', 14)} ${w('edit')}</button>
        ${state.user.role === 'owner' ? `<button class="small danger icon" data-del="${esc(p.id)}" type="button" title="${esc(w('delete'))}">${icon('trash', 15)}</button>` : ''}</td>
    </tr>`).join('');
  body.querySelectorAll('[data-edit]').forEach((b) => {
    b.onclick = () => projectDialog(state.projects.find((p) => p.id === b.dataset.edit));
  });
  body.querySelectorAll('[data-del]').forEach((b) => {
    b.onclick = () => confirmDialog(w('delete_title'),
      w('delete_body'),
      async () => { await api(`/api/projects/${b.dataset.del}`, { method: 'DELETE' }); await loadProjects(); render(); }, w('delete'), { tone: 'danger' });
  });
}

function projectDialog(row) {
  // Reading a folder lists its file names, so a hosted portal only lets its OWNER name a path
  // (or whatever TV_SCAN_ROOTS allows). Everyone else documents a Git repository, which the portal
  // clones into its own data folder. Say so here rather than at the Scan button.
  const isGit = (row && row.source_kind) === 'git' || !state.canScanLocal;
  modal(w(row ? 'edit_project' : 'register'), `
    <div id="pd-msg"></div>
    <div class="field"><label for="pd-name">${w('col_name')}</label><input id="pd-name" value="${esc(row ? row.name : '')}" placeholder="${esc(w('name_placeholder'))}"/></div>

    <div class="field" style="margin-top:12px"><label for="pd-kind">${w('where_code')}</label>
      <select id="pd-kind">
        <option value="local" ${isGit ? '' : 'selected'} ${state.canScanLocal ? '' : 'disabled'}>${w(state.canScanLocal ? 'kind_local' : 'kind_local_blocked')}</option>
        <option value="git" ${isGit ? 'selected' : ''}>${w('kind_git')}</option>
      </select></div>

    <div id="pd-local" style="${isGit || !state.canScanLocal ? 'display:none' : ''}">
      <div class="field" style="margin-top:10px"><label for="pd-folder">${w('folder_label')}</label>
        <input id="pd-folder" value="${esc(row ? row.folder || '' : '')}" placeholder="${esc(state.serverSample || '/srv/myapp')}"/>
        <span class="small muted">${w('folder_note', { where: state.portalUrl ? ` (${esc(state.portalUrl)})` : '' })}</span>
        <div id="pd-folder-warn"></div></div>
    </div>

    ${state.canScanLocal ? '' : `<p class="small muted" style="margin:-4px 0 4px">${w('clones_only')}</p>`}

    <div id="pd-git" style="${isGit ? '' : 'display:none'}">
      <div class="field" style="margin-top:10px"><label for="pd-url">${w('repo_label')}</label>
        <input id="pd-url" value="${esc(row ? row.git_url || '' : '')}" placeholder="https://github.com/owner/repo.git"/>
        <span class="small muted">${w('repo_note')}</span></div>
      <div class="grid two" style="margin-top:10px">
        <div class="field"><label for="pd-branch">${w('branch_label')}</label>
          <input id="pd-branch" value="${esc(row ? row.git_branch || '' : '')}" placeholder="${esc(w('branch_placeholder'))}"/></div>
        <div class="field"><label for="pd-token">${w('token_label')}</label>
          <input id="pd-token" type="password" autocomplete="off" placeholder="${esc(w(row && row.git_token_set ? 'token_saved' : 'token_public'))}"/>
          <span class="small muted">${w('token_note')}</span></div>
      </div>
    </div>

    <div class="field" style="margin-top:12px"><label for="pd-site">${w('site_label')}</label>
      <input id="pd-site" value="${esc(row ? row.site_url || '' : '')}" placeholder="https://myapp.example.com"/></div>
    <div class="row" style="margin-top:14px;justify-content:flex-end"><button class="primary" id="pd-save" type="button">${w('save')}</button></div>`,
    { onOpen: (body, close) => {
      const folderBox = body.querySelector('#pd-folder');
      const warnBox = body.querySelector('#pd-folder-warn');
      const checkFolder = () => {
        // A drive letter typed at a portal running on Linux can never resolve, however many times
        // Scan is pressed. Say so while it is being typed, not after the scan fails.
        const looksWindows = /^[A-Za-z]:[\\/]/.test(folderBox.value.trim());
        say(warnBox, 'warn', looksWindows && !state.serverWindows
          ? w('windows_path')
          : '');
      };
      folderBox.oninput = checkFolder;
      checkFolder();

      const kind = body.querySelector('#pd-kind');
      kind.onchange = () => {
        body.querySelector('#pd-local').style.display = kind.value === 'git' ? 'none' : '';
        body.querySelector('#pd-git').style.display = kind.value === 'git' ? '' : 'none';
      };
      body.querySelector('#pd-save').onclick = async () => {
        const token = body.querySelector('#pd-token').value;
        try {
          const d = await api('/api/projects', { method: 'POST', body: {
            id: row ? row.id : null, name: body.querySelector('#pd-name').value,
            source_kind: kind.value,
            folder: body.querySelector('#pd-folder').value,
            git_url: body.querySelector('#pd-url').value,
            git_branch: body.querySelector('#pd-branch').value,
            // Left blank means "keep whatever is stored" — the browser never received the real one.
            ...(token ? { git_token: token } : {}),
            site_url: body.querySelector('#pd-site').value } });
          await loadProjects();
          state.projectId = d.project.id;
          keep('tv.project', state.projectId);
          close(); render();
        } catch (e) { say(body.querySelector('#pd-msg'), 'bad', esc(e.message)); }
      };
    } });
}

// --- scan ----------------------------------------------------------------------------------------

async function runScan(host, msg) {
  const out = host.querySelector('#scan-out');
  // The outcome belongs in the scan card, under the button that was pressed. It used to be written
  // into the page-top message box, which on a long Setup page is off screen — so a failed scan
  // looked like a button that did nothing at all.
  out.innerHTML = `<p class="muted row tight">${icon('refresh', 15)} ${w('reading')}</p>`;
  try {
    const d = await api(`/api/projects/${project().id}/scan`, { method: 'POST', body: {} });
    scanned = d.screens;
    const fetched = d.source && d.source.note ? w('repo_note_line', { note: d.source.note }) : '';
    const line = fetched + (d.note
      || w('scan_result', { n: d.screens.length, files: d.files_read }));
    drawScan(host, msg);
    say(host.querySelector('#scan-msg'), d.screens.length ? 'info' : 'warn', line);
    toast(d.screens.length ? w('screens_found', { n: d.screens.length }) : w('nothing_found_toast'),
          d.screens.length ? 'ok' : 'warn');
  } catch (e) {
    const p = project();
    const git = (p || {}).source_kind === 'git';
    out.innerHTML = `<div class="note bad">${icon('alert')}<div>${esc(e.message)}</div></div>
      <div class="card" style="margin:0;background:var(--panel-2);box-shadow:none">
        <h3 style="margin-top:0">${w('three_ways')}</h3>
        <ol style="margin:0;padding-left:20px" class="small muted">
          <li>${w('way_git')} <button class="link" type="button" id="scan-git">${w('edit_this')}</button></li>
          <li>${w('way_path')}${state.serverSample
            ? w('way_path_like', { sample: esc(state.serverSample) }) : ''}.</li>
          <li>${w('way_hand')}</li>
        </ol></div>`;
    const edit = out.querySelector('#scan-git');
    if (edit) edit.onclick = () => projectDialog(state.projects.find((x) => x.id === (project() || {}).id));
    toast(w(git ? 'fetch_failed' : 'cannot_see'), 'bad', 7);
  }
}

function drawScan(host, msg) {
  const out = host.querySelector('#scan-out');
  if (!scanned || !scanned.length) { out.innerHTML = `<p class="muted">${w('nothing_yet')}</p>`; return; }
  out.innerHTML = `<div class="row" style="margin-bottom:8px">
      <button class="small" id="all-on" type="button">${icon('check', 14)} ${w('tick_all')}</button>
      <button class="small" id="all-off" type="button">${icon('close', 14)} ${w('untick_all')}</button>
      <span class="small muted">${w('ticked', { n: scanned.filter((s) => s.selected).length, total: scanned.length })}</span></div>
    <div class="scroll"><table class="seg fixed"><colgroup><col style="width:34px"/><col style="width:24%"/>
        <col style="width:18%"/><col style="width:11%"/><col style="width:15%"/><col/><col style="width:86px"/></colgroup>
      <thead><tr>
      <th></th><th>${w('col_label')}</th><th>${w('col_key')}</th><th>${w('col_group')}</th><th>${w('col_route')}</th><th>${w('col_why')}</th><th></th>
    </tr></thead><tbody>${scanned.map((s, i) => `<tr class="${s.selected ? '' : 'off'}">
      <td><input type="checkbox" data-i="${i}" data-f="selected" ${s.selected ? 'checked' : ''}/></td>
      <td><input data-i="${i}" data-f="label" value="${esc(s.label)}"/></td>
      <td><input data-i="${i}" data-f="key" value="${esc(s.key)}"/></td>
      <td><input data-i="${i}" data-f="group" value="${esc(s.group || '')}" placeholder="—"/></td>
      <td><input data-i="${i}" data-f="route" value="${esc(s.route || '')}" placeholder="—"/></td>
      <td class="small muted">${esc(s.why)}<br/><span class="tag ${s.confidence === 'maybe' ? 'warn' : s.confidence === 'saved' ? 'ok' : ''}">${esc(s.confidence)}</span>
        ${s.file ? `<div class="small muted">${esc(s.file)}</div>` : ''}</td>
      <td class="a"><button class="small danger icon" data-drop="${i}" type="button" title="${esc(w('remove'))}">${icon('close', 15)}</button></td></tr>`).join('')}</tbody></table></div>
    <div class="row" style="margin-top:14px"><button class="primary" id="save-screens" type="button">${icon('save')} ${w('save_screens')}</button>
      <span class="small muted">${w('save_screens_note')}</span></div>`;

  out.querySelectorAll('input[data-i]').forEach((inp) => {
    inp.oninput = inp.onchange = () => {
      const row = scanned[Number(inp.dataset.i)];
      row[inp.dataset.f] = inp.type === 'checkbox' ? inp.checked : inp.value;
      if (inp.dataset.f === 'selected') inp.closest('tr').className = inp.checked ? '' : 'off';
    };
  });
  out.querySelectorAll('[data-drop]').forEach((b) => {
    b.onclick = () => confirmDialog(w('row_remove_title'), w('row_remove_body'), () => { scanned.splice(Number(b.dataset.drop), 1); drawScan(host, msg); }, w('remove'), { tone: 'danger' });
  });
  out.querySelector('#all-on').onclick = () => { scanned.forEach((s) => { s.selected = true; }); drawScan(host, msg); };
  out.querySelector('#all-off').onclick = () => { scanned.forEach((s) => { s.selected = false; }); drawScan(host, msg); };
  out.querySelector('#save-screens').onclick = async () => {
    try {
      await api(`/api/projects/${project().id}/screens`, { method: 'PUT', body: { screens: scanned.filter((s) => s.selected) } });
      await loadProjects();
      scanned = null;
      await setupPage(host);   // redraw from what was saved, then say so on the fresh page
      say(host.querySelector('#setup-msg'), 'ok', w('screens_saved'));
    } catch (e) { say(msg, 'bad', esc(e.message)); }
  };
}
