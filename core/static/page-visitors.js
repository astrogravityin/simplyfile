// Visitors — every screen shown in a browser, signed in or not: how many, which pages, from where, on
// what, and for how long. Places come from the CDN in front of the portal, else from the local IP
// database on the server (core/geo.py) — no address is sent anywhere to be looked up.
import { api, esc, pageHead, t, loadWords, when } from './ui.js';
import { icon } from './icons.js';
import { choropleth, regionKey } from './geo-map.js';

// ~240 KB of shapes: fetched when this screen first opens, never by the rest of the portal.
let shapes = null;
const loadShapes = () => shapes || (shapes = Promise.all([import('./geo/world.js'), import('./geo/india.js')])
  .then(([w, i]) => ({
    world: { viewBox: w.WORLD_VIEWBOX, shapes: w.WORLD_COUNTRIES.map((s) => ({ key: s.code, name: s.name, d: s.d })) },
    india: { viewBox: i.INDIA_VIEWBOX, shapes: i.INDIA_STATES.map((s) => ({ key: regionKey(s.name), name: s.name, d: s.d })) },
  })));

// Every word on this screen is chip ui.visitors (core/words.py) - none is written here.
// (`w` is a chart width in series(), so the words go by `word`.)
const word = (k, v) => t('visitors', k, v);

/** Why places may be missing, in one sentence a person can act on. Empty when all is well. */
function geoNote(g, anyPlace) {
  if (anyPlace && g.source !== 'missing') return '';
  const say = {
    loading: word('geo_loading'),
    missing: word('geo_missing', { error: esc(g.error || '') }),
    off: word('geo_off'),
  }[g.source];
  return say ? `<div class="note ${g.source === 'missing' ? 'warn' : 'info'}">${icon('globe')}<div>${say}</div></div>` : '';
}

function maps(d, geo) {
  const world = Object.fromEntries(d.map_countries.map((r) => [r.name, r.views]));
  const india = {};
  const known = new Set(geo.india.shapes.map((s) => s.key));
  const offMap = [];
  d.india_regions.forEach((r) => {
    const k = regionKey(r.name);
    if (known.has(k)) india[k] = (india[k] || 0) + r.views; else offMap.push(r);
  });
  const ranked = geo.india.shapes.filter((s) => india[s.key]).map((s) => ({ name: s.name, views: india[s.key] }))
    .sort((a, b) => b.views - a.views);
  const credit = d.geo.source === 'dbip' ? ` · ${word('dbip_credit')}` : '';
  const max = ranked[0]?.views || 1;
  return `<div class="card"><h2>${icon('globe', 16)} ${word('world')}</h2>
      ${choropleth({ ...geo.world, values: world, unit: word('unit_views'), attribution: word('world_credit', { credit }) })}</div>
    <div class="card"><h2>${icon('globe', 16)} ${word('india')}</h2>
      <div class="india">
        ${choropleth({ ...geo.india, values: india, unit: word('unit_views'), attribution: word('india_credit', { credit }) })}
        <div>${ranked.length ? `<div class="hbars">${ranked.map((r) => `<div class="hbar">
            <span>${esc(r.name)}</span><i style="width:${(100 * r.views) / max}%"></i><b>${r.views}</b></div>`).join('')}</div>`
          : `<p class="muted small">${word('no_india')}</p>`}
          ${offMap.length ? `<p class="muted small" style="margin-top:10px">${word('off_map', { places: offMap.map((r) => `${esc(r.name)} (${r.views})`).join(', ') })}</p>` : ''}
        </div></div></div>`;
}

let range = '7d';
const RANGES = () => [['24h', word('range_24h')], ['7d', word('range_7d')], ['30d', word('range_30d')], ['90d', word('range_90d')], ['all', word('range_all')]];

const secs = (ms) => (ms ? (ms >= 60000 ? word('minutes', { n: Math.round(ms / 60000) }) : word('seconds', { n: Math.round(ms / 1000) })) : '—');

/** Views over time as columns. Drawn, not charted: one SVG, no library. */
function series(rows) {
  if (!rows.length) return `<p class="muted small">${word('no_visits')}</p>`;
  const w = 720; const h = 140; const max = Math.max(1, ...rows.map((r) => r.views));
  const bw = Math.min(w / rows.length, 56);        // one day of data is a column, not a wall
  return `<svg class="chart" viewBox="0 0 ${w} ${h + 18}" role="img" aria-label="${esc(word('views_over_time'))}" preserveAspectRatio="none">
    ${rows.map((r, i) => {
      const bh = Math.max(2, (h * r.views) / max);
      return `<rect x="${i * bw + bw * 0.15}" y="${h - bh}" width="${bw * 0.7}" height="${bh}" rx="2"><title>${esc(word('bar_tip', { bucket: r.bucket, views: r.views, sessions: r.sessions }))}</title></rect>`;
    }).join('')}
    <text x="0" y="${h + 14}">${esc(rows[0].bucket)}</text>
    <text x="${w}" y="${h + 14}" text-anchor="end">${esc(rows[rows.length - 1].bucket)}</text></svg>`;
}

function bars(title, ic, rows) {
  const max = Math.max(1, ...rows.map((r) => r.views));
  return `<div class="card"><h2>${icon(ic, 16)} ${title}</h2>
    ${rows.length ? `<div class="hbars">${rows.map((r) => `<div class="hbar" title="${esc(word('sessions_tip', { n: r.sessions }))}">
      <span>${esc(r.name)}</span><i style="width:${(100 * r.views) / max}%"></i><b>${r.views}</b></div>`).join('')}</div>`
      : `<p class="muted small">${word('nothing_yet')}</p>`}</div>`;
}

export async function visitorsPage(host) {
  const [d, geo] = await Promise.all([api(`/api/core/visitors?range=${range}`), loadShapes(), loadWords('visitors')]);
  const t = d.totals;
  const tile = (n, label) => `<div class="stat"><b>${n}</b><span>${label}</span></div>`;
  host.innerHTML = `${pageHead(word('title'), word('lede'))}
    <div class="toolbar"><div class="switch">${RANGES().map(([id, l]) =>
      `<button type="button" data-range="${id}" class="${range === id ? 'on' : ''}">${l}</button>`).join('')}</div></div>
    <div class="stats">${tile((t.views || 0).toLocaleString(), word('unit_views'))}${tile((t.sessions || 0).toLocaleString(), word('tile_visits'))}
      ${tile(t.people || 0, word('tile_people'))}${tile((t.anonymous || 0).toLocaleString(), word('tile_anonymous'))}${tile(secs(t.avg_dwell_ms), word('tile_dwell'))}</div>
    <div class="card"><h2>${icon('pulse', 16)} ${word('views_over_time')}</h2>${series(d.series)}</div>
    <div class="card flush"><div class="head" style="padding:14px 16px 0"><h2>${icon('film', 16)} ${word('pages')}</h2></div>
      ${d.pages.length ? `<table><thead><tr><th>${word('col_page')}</th><th>${word('col_views')}</th><th>${word('col_visits')}</th><th>${word('col_avg')}</th></tr></thead>
      <tbody>${d.pages.map((p) => `<tr><td><code>${esc(p.name)}</code></td><td>${p.views}</td><td>${p.sessions}</td>
        <td class="small muted">${secs(p.avg_dwell_ms)}</td></tr>`).join('')}</tbody></table>`
        : `<p class="muted small" style="padding:0 16px 16px">${word('no_pages')}</p>`}</div>
    ${geoNote(d.geo, d.map_countries.length > 0)}
    ${maps(d, geo)}
    <div class="grid three">
      ${bars(word('countries'), 'globe', d.countries)}${bars(word('cities'), 'globe', d.cities)}${bars(word('referrers'), 'external', d.referrers)}
      ${bars(word('devices'), 'chip', d.devices)}${bars(word('browsers'), 'eye', d.browsers)}${bars(word('systems'), 'setup', d.systems)}
    </div>
    <div class="card flush"><div class="head" style="padding:14px 16px 0"><h2>${icon('clock', 16)} ${word('latest')}</h2></div>
      <div class="scroll"><table class="fixed"><colgroup><col style="width:140px"/><col/><col style="width:22%"/><col style="width:16%"/><col style="width:18%"/><col style="width:80px"/></colgroup>
      <thead><tr><th>${word('col_when')}</th><th>${word('col_page')}</th><th>${word('col_who')}</th><th>${word('col_where')}</th><th>${word('col_on')}</th><th>${word('col_stayed')}</th></tr></thead>
      <tbody>${d.latest.map((v) => `<tr><td class="small">${when(v.at)}</td><td class="small"><code>${esc(v.path)}</code></td>
        <td class="small">${v.email ? esc(v.email) : `<span class="muted">${word('signed_out')}</span>`}</td>
        <td class="small">${esc([v.city, v.region, v.country].filter(Boolean).join(', ') || word('unknown'))}</td>
        <td class="small muted">${esc([v.device, v.browser, v.os].filter(Boolean).join(' · '))}</td>
        <td class="small muted">${secs(v.dwell_ms)}</td></tr>`).join('')}</tbody></table></div></div>`;
  host.querySelectorAll('[data-range]').forEach((b) => { b.onclick = () => { range = b.dataset.range; visitorsPage(host); }; });
}
