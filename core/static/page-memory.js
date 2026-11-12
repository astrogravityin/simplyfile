// Memory watch — the studio's screen, drawn without a chart library. What the portal weighs, the whole
// server around it (CPU, memory, disk, bandwidth: this portal against everything else), which request
// moved memory, and a verdict in words. Every judgement on this page comes from a `memory.*` chip on the
// server; the page only draws what it is given. Refresh is the shell's (top right); this page adds
// Auto (the server says when it took a new reading - push stream topic memory, no page timer) and Clear moves.
import { api, esc, toast, pageHead, confirmDialog, t, loadWords, clockAt, onEvent } from './ui.js';
import { icon } from './icons.js';

const gb = (mb) => (mb >= 1024 ? `${(mb / 1024).toFixed(1)} GB` : `${Math.round(mb || 0)} MB`);
const rate = (kbs) => (kbs >= 1024 ? `${(kbs / 1024).toFixed(1)} MB/s` : `${(kbs || 0).toFixed(1)} KB/s`);
const hhmm = (iso) => esc(clockAt(iso) || iso || '—');   // the time with its zone (core clockAt)
const uptime = (s) => (s < 3600 ? `${Math.floor(s / 60)} min` : s < 86400 ? `${(s / 3600).toFixed(1)} h` : `${(s / 86400).toFixed(1)} d`);
const signed = (n) => `${n > 0 ? '+' : ''}${n} MB`;
// Every word on this screen is chip ui.memory (core/words.py) - none is written here.
// (`w` is a chart width below, so the words go by `mw`.)
const mw = (k, v) => t('memory', k, v);
const LEVEL = {
  ok: ['ok', 'check', 'level_ok'], watch: ['warn', 'pulse', 'level_watch'],
  warn: ['warn', 'alert', 'level_warn'], kill: ['bad', 'alert', 'level_kill'],
};
let auto = true;
let stopLive = () => {};   // the open screen's stream listener (one at a time)

/** Lines over time in one SVG. series: [{key, cls}] read from rows; refs: [{value, cls, label}]. */
function lines(rows, series, { max, refs = [], fmt = String, h = 170 } = {}) {
  const pts = rows.filter((r) => series.some((s) => r[s.key] !== undefined));
  if (pts.length < 2) return `<p class="muted small chart-empty">${mw('collecting')}</p>`;
  const w = 720;
  const peak = Math.max(...pts.flatMap((r) => series.map((s) => r[s.key] || 0)));
  refs = refs.filter((r) => r.value && r.value <= Math.max(peak, 1) * 3);   // a 16 GB limit would flatten a 200 MB line
  const top = Math.max(max || 0, peak, ...refs.map((r) => r.value)) * 1.08 || 1;
  const x = (i) => (i / (pts.length - 1)) * w;
  const y = (v) => h - (h * (v || 0)) / top;
  const path = (key) => pts.map((r, i) => `${x(i).toFixed(1)},${y(r[key]).toFixed(1)}`).join(' ');
  return `<svg class="chart" viewBox="0 0 ${w} ${h + 18}" preserveAspectRatio="none" role="img">
    ${series.map((s) => (s.area ? `<polygon class="area" points="0,${h} ${path(s.key)} ${w},${h}"/>` : '')).join('')}
    ${series.map((s) => `<polyline class="${s.cls}" points="${path(s.key)}"><title>${esc(mw('line_now', { label: s.label, value: fmt(pts[pts.length - 1][s.key] || 0) }))}</title></polyline>`).join('')}
    ${refs.map((r) => `<line class="${r.cls}" x1="0" x2="${w}" y1="${y(r.value)}" y2="${y(r.value)}"/>
      <text x="${w}" y="${y(r.value) - 5}" text-anchor="end">${esc(r.label)}</text>`).join('')}
    <text x="0" y="${h + 14}">${hhmm(pts[0].t)}</text><text x="${w}" y="${h + 14}" text-anchor="end">${hhmm(pts[pts.length - 1].t)}</text></svg>`;
}

/** Stacked bar: this portal's share, then the rest, against capacity (max 0 = no capacity known). */
function usage(label, app, total, max, fmt, sub) {
  const other = Math.max(0, total - app);
  const scale = max || total || 1;
  const w = (n) => `${Math.min(100, (n * 100) / scale)}%`;
  return `<div class="usage"><div class="usage-top"><span>${label}</span><b>${max ? `${Math.round((total * 100) / max)}%` : fmt(total)}</b></div>
    <div class="usage-bar"><i class="app" style="width:${w(app)}"></i><i class="other" style="width:${w(other)}"></i></div>
    <p><span class="app-ink">${mw('usage_portal', { n: fmt(app) })}</span> · ${mw('usage_other', { n: fmt(other) })} · ${mw('usage_total', { n: fmt(total) })}</p>
    ${sub ? `<p class="muted" title="${esc(sub)}">${esc(sub)}</p>` : ''}</div>`;
}

function table(head, rows, { hot, empty, mono = [] } = {}) {
  if (!rows.length) return `<p class="muted small empty-box">${empty}</p>`;
  return `<div class="scroll" style="max-height:320px"><table><thead><tr>${head.map((h) => `<th>${h}</th>`).join('')}</tr></thead>
    <tbody>${rows.map((r) => `<tr class="${hot && hot(r) ? 'hot' : ''}">${r.cells.map((c, j) =>
      `<td class="small${mono.includes(j) ? ' mono' : ''}" title="${esc(String(c))}">${esc(String(c))}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
}

export async function memoryPage(host) {
  stopLive();
  const d = await api('/api/core/memory');
  if (!host.isConnected) return;
  const v = d.verdict;
  await loadWords('memory');
  const [tone, ic, levelKey] = LEVEL[v.level] || LEVEL.watch;
  const word = mw(levelKey);
  const h = d.host;
  const samples = d.samples;
  const hostRows = samples.filter((s) => s.cpu !== undefined || s.net !== undefined);
  const last = hostRows[hostRows.length - 1] || {};
  const disk = h.disk || {};
  const pct = d.limit_mb ? Math.min(100, Math.round((d.rss_mb * 100) / d.limit_mb)) : 0;
  const spike = d.knobs.spike_mb;
  const tile = (label, value, sub) => `<div class="stat"><span>${label}</span><b>${value}</b><span title="${esc(sub)}">${esc(sub)}</span></div>`;

  host.innerHTML = `${pageHead(mw('title'), mw('lede'))}
    <div class="toolbar">
      <button type="button" class="small" id="mw-auto">${icon(auto ? 'pulse' : 'play', 14)} ${mw(auto ? 'auto_on' : 'auto_off')}</button>
      <button type="button" class="small" id="mw-clear" data-tip="${esc(mw('clear_tip'))}">${icon('trash', 14)} ${mw('clear_moves')}</button>
    </div>
    <div class="note ${tone} verdict">${icon(ic)}<div>
      <p class="eyebrow">${word}</p><h2>${esc(v.title)}</h2><p>${esc(v.message)}</p>
      ${v.hints.length ? `<ul>${v.hints.map((x) => `<li>${esc(x)}</li>`).join('')}</ul>` : ''}</div></div>
    <div class="stats">
      ${tile(mw('tile_resident'), `${d.rss_mb} MB`, mw('tile_resident_sub', { pct, limit: d.limit_mb, source: d.limit_source }))}
      ${tile(mw('tile_headroom'), `${Math.max(0, d.limit_mb - d.rss_mb)} MB`, mw('tile_headroom_sub'))}
      ${tile(mw('tile_peak'), `${d.peak.rss || 0} MB`, d.peak.path || (d.peak.at ? hhmm(d.peak.at) : '—'))}
      ${tile(mw('tile_up'), uptime(d.uptime_s), mw('tile_up_sub', { since: hhmm(d.started_at), pid: d.pid }))}
      ${tile(mw('tile_reader'), esc(d.reader), mw('tile_reader_sub', { s: d.sample_seconds, python: d.python }))}
    </div>
    <div class="card"><div class="head"><h2>${icon('chip', 16)} ${mw('server_title')}</h2>
      <span class="legend"><i class="app"></i> ${mw('legend_portal')} <i class="other"></i> ${mw('legend_other')}</span></div>
      <div class="usage-grid">
        ${usage(mw('cpu_usage'), last.cpu_app || 0, last.cpu || 0, 100, (n) => `${n.toFixed(1)}%`, mw('cores', { n: h.cpu_count }))}
        ${usage(mw('memory_usage'), last.mem_app || 0, last.mem || 0, h.mem_total_mb, gb, mw('of', { n: gb(h.mem_total_mb) }))}
        ${usage(mw('disk_usage'), disk.app_mb || 0, disk.used_mb || 0, disk.total_mb || 0, gb,
          disk.total_mb ? `${mw('of', { n: gb(disk.total_mb) })} · ${(disk.parts || []).map((p) => `${p.label} ${gb(p.mb)}`).join(' · ')}` : mw('disk_measuring'))}
        ${usage(mw('bandwidth'), last.net_app || 0, Math.max(last.net || 0, last.net_app || 0), 0, rate, mw('bandwidth_sub'))}
      </div>
      ${h.procs_supported ? '' : `<p class="small muted">${mw('needs_linux')}</p>`}
      <div class="split">
        <div><p class="eyebrow">${mw('cpu_pct')}</p>${lines(hostRows, [{ key: 'cpu', cls: 'line total', label: mw('total') }, { key: 'cpu_app', cls: 'line', label: mw('portal') }], { max: 100, fmt: (n) => `${n}%` })}</div>
        <div><p class="eyebrow">${mw('bandwidth')}</p>${lines(hostRows, [{ key: 'net', cls: 'line total', label: mw('total') }, { key: 'net_app', cls: 'line', label: mw('portal') }], { fmt: rate })}</div>
      </div>
      <div class="split">
        <div><p class="eyebrow">${mw('portal_procs')}</p>${table([mw('col_role'), mw('col_process'), mw('col_pid'), mw('col_cpu'), mw('col_memory')],
          h.procs_app.map((p) => ({ cells: [p.role, p.name, p.pid, `${p.cpu}%`, gb(p.mem)] })), { empty: mw('no_portal_procs') })}</div>
        <div><p class="eyebrow">${mw('other_procs')}</p>${table([mw('col_service'), mw('col_procs'), mw('col_cpu'), mw('col_memory')],
          h.procs_other.map((p) => ({ cells: [p.key, p.count, `${Number(p.cpu).toFixed(1)}%`, gb(p.mem)] })), { empty: mw('no_other_procs') })}</div>
      </div></div>
    <div class="card"><div class="head"><h2>${icon('pulse', 16)} ${mw('resident_title', { n: Math.round((samples.length * d.sample_seconds) / 60) })}</h2>
      <span class="small muted">${mw('resident_key')}</span></div>
      <div class="bar" title="${pct}%"><i style="width:${pct}%"></i></div>
      ${lines(samples, [{ key: 'rss', cls: 'line', label: mw('resident'), area: true }], {
        refs: [{ value: d.limit_mb, cls: 'limit', label: mw('limit_line', { n: gb(d.limit_mb) }) },
               { value: Math.round((d.limit_mb * d.knobs.warn_pct) / 100), cls: 'limit warnline', label: `${d.knobs.warn_pct}%` }],
        fmt: (n) => `${n} MB`, h: 220 })}</div>
    <div class="split">
      <div class="card"><h2>${icon('alert', 16)} ${mw('offenders_title')}</h2>
        ${table([mw('col_request'), mw('col_max_move'), mw('total'), mw('col_calls'), mw('col_last')], d.offenders.map((o) => ({ cells: [o.key, signed(o.max_delta), signed(o.total_delta), o.count, hhmm(o.last_at)], big: o.max_delta })),
          { hot: (r) => r.big >= spike, mono: [0], empty: mw('no_offenders') })}</div>
      <div class="card"><h2>${icon('clock', 16)} ${mw('recent_title')}</h2>
        ${table([mw('col_when'), mw('col_request'), mw('col_before_after'), mw('col_move'), mw('col_took')], d.events.map((e) => ({ cells: [hhmm(e.t), `${e.method} ${e.path}`, `${e.before} → ${e.after} MB`, signed(e.delta), `${e.ms} ms`], big: e.delta })),
          { hot: (r) => r.big >= spike, mono: [1], empty: mw('no_moves') })}
        <p class="small muted">${mw('moves_note')}</p></div>
    </div>`;

  host.querySelector('#mw-auto').onclick = () => { auto = !auto; memoryPage(host).catch(() => {}); };
  host.querySelector('#mw-clear').onclick = () => confirmDialog(mw('clear_title'),
    mw('clear_body'), async () => {
      try { await api('/api/core/memory/clear-events', { method: 'POST' }); toast(mw('cleared'), 'ok'); memoryPage(host); }
      catch (err) { toast(err.message, 'bad'); }
    }, mw('clear'), { tone: 'danger' });
  stopLive();
  stopLive = auto ? onEvent('memory', () => {           // pushed after each reading (core/memwatch.py) - no poll
    if (!host.isConnected || location.hash !== '#/memory') { stopLive(); return; }
    stopLive();
    memoryPage(host).catch(() => {});
  }) : () => {};
}
