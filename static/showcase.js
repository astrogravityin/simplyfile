// Showcase - the public page linked from the landing (2026-10-05 owner: "open all this in another
// page ... auto run video by video or the user can select from the left pane ... the most beautiful page ... every
// module, one stop shop, standards as a framework with unlimited freedom ... all age groups"). Every word, module,
// feature and chapter is chip showcase.page (GET api/showcase); this file only draws it. Films stream from
// showcase/media/<key>.mp4 (seekable), posters .jpg, captions .vtt.
// The family copy uses neutral keys (foot.maker / foot.maker_href, section and icon `shelf`) - it no longer matches the studio's copy, by design.
import { icon } from '../core-static/icons.js';

const root = document.getElementById('sc-root');
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const media = (key, ext) => `showcase/media/${encodeURIComponent(key)}.${ext}`;
const store = {                                           // per-viewer conveniences only; the page works without them
  get(k, d) { try { const v = localStorage.getItem(`sc.${k}`); return v === null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem(`sc.${k}`, JSON.stringify(v)); } catch { /* private window */ } },
};

// ------------------------------------------------------------------------------------------------- the pictures (SVG)

const LOGO = `<svg viewBox="0 0 32 32" aria-hidden="true"><defs><linearGradient id="lg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#8f84ff"/><stop offset="1" stop-color="#6d5efc"/></linearGradient></defs>
  <rect width="32" height="32" rx="9" fill="url(#lg)"/><path d="M12 9.5v13l11-6.5z" fill="#fff"/></svg>`;
// a page with a tick on it (chip nav.logo "ledger" - SimplyFile)
const LEDGER_LOGO = `<svg viewBox="0 0 32 32" aria-hidden="true"><defs><linearGradient id="llg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#34d399"/><stop offset="1" stop-color="#059669"/></linearGradient></defs>
  <rect width="32" height="32" rx="8" fill="url(#llg)"/><path d="M10 7h9l4 4v14H10z" fill="#fff"/><path d="M13.5 18l2.6 2.6 5-5.2" fill="none" stroke="#059669" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/><path d="M13 11.5h5M13 14.5h7" stroke="#a7f3d0" stroke-width="1.8" stroke-linecap="round"/></svg>`;
// the scales of justice (chip nav.logo "scales" - Justify)
const SCALES_LOGO = `<svg viewBox="0 0 32 32" aria-hidden="true"><defs><linearGradient id="slg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#3b5bdb"/><stop offset="1" stop-color="#1e2a78"/></linearGradient></defs>
  <rect width="32" height="32" rx="8" fill="url(#slg)"/><path d="M16 7v17M11 25h10" stroke="#fff" stroke-width="2" stroke-linecap="round"/><path d="M8 11h16" stroke="#f6c453" stroke-width="2.2" stroke-linecap="round"/>
  <path d="M10 11l-3 6h6zM22 11l-3 6h6z" fill="none" stroke="#f6c453" stroke-width="1.6" stroke-linejoin="round"/><path d="M7 17a3 2 0 0 0 6 0M19 17a3 2 0 0 0 6 0" fill="#f6c453"/></svg>`;
const LOGOS = { play: LOGO, ledger: LEDGER_LOGO, scales: SCALES_LOGO };

const HERO_ART = `<svg viewBox="0 0 560 500" role="img" aria-label="A kite in the wind, carrying a book, a comic, a film and a sound wave">
  <defs>
    <linearGradient id="kg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ff8a5c"/><stop offset=".55" stop-color="#e9573f"/><stop offset="1" stop-color="#c2364f"/></linearGradient>
    <linearGradient id="kg2" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ffd27a"/><stop offset="1" stop-color="#f4a524"/></linearGradient>
    <radialGradient id="glow" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#8f84ff" stop-opacity=".45"/><stop offset="1" stop-color="#8f84ff" stop-opacity="0"/></radialGradient>
    <filter id="soft" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="12" stdDeviation="14" flood-color="#000" flood-opacity=".35"/></filter>
  </defs>
  <circle cx="300" cy="200" r="210" fill="url(#glow)"/>
  <g class="wind" fill="none" stroke="#b9b4dd" stroke-opacity=".45" stroke-width="2" stroke-linecap="round">
    <path d="M10 120 C 120 90, 200 150, 330 110 S 520 80, 560 100"/>
    <path d="M0 210 C 140 180, 230 240, 380 200 S 520 170, 560 190"/>
    <path d="M30 300 C 150 280, 250 330, 400 290"/>
  </g>
  <path d="M352 236 C 300 300, 240 330, 170 360 C 120 380, 80 420, 60 480" fill="none" stroke="#f4f1ff" stroke-opacity=".55" stroke-width="1.6"/>
  <g class="kite" filter="url(#soft)">
    <path d="M352 60 L 432 150 L 352 236 L 292 150 Z" fill="url(#kg)"/>
    <path d="M352 60 L 352 236 M 292 150 L 432 150" stroke="#fff" stroke-opacity=".55" stroke-width="2"/>
    <path d="M352 60 L 432 150 L 352 150 Z" fill="url(#kg2)" opacity=".9"/>
    <path d="M352 236 q -10 18 4 30 q 14 12 -2 28 q -14 14 4 30" fill="none" stroke="#f4a524" stroke-width="3" stroke-linecap="round"/>
    <path d="M354 266 l -10 -6 l 2 12 z M 356 294 l 10 -6 l -2 12 z" fill="#ff7aa8"/>
  </g>
  <g transform="translate(40 92)"><g class="float" filter="url(#soft)">
    <rect width="132" height="96" rx="14" fill="#f4f1ff"/><rect x="12" y="12" width="50" height="72" rx="6" fill="#6d5efc"/>
    <rect x="70" y="16" width="50" height="7" rx="3" fill="#c4c0e0"/><rect x="70" y="30" width="44" height="7" rx="3" fill="#c4c0e0"/><rect x="70" y="44" width="48" height="7" rx="3" fill="#c4c0e0"/><rect x="70" y="58" width="30" height="7" rx="3" fill="#c4c0e0"/>
    <path d="M25 30 h24 M25 42 h24 M25 54 h16" stroke="#fff" stroke-width="3" stroke-linecap="round"/>
  </g></g>
  <g transform="translate(404 250)"><g class="float b" filter="url(#soft)">
    <rect width="128" height="104" rx="14" fill="#f4f1ff"/><rect x="10" y="10" width="52" height="40" rx="5" fill="#24a89a"/><rect x="66" y="10" width="52" height="40" rx="5" fill="#4b9fe8"/>
    <rect x="10" y="54" width="108" height="40" rx="5" fill="#f4a524"/><ellipse cx="44" cy="30" rx="18" ry="10" fill="#fff"/><path d="M36 38 l -4 8 l 10 -6z" fill="#fff"/>
  </g></g>
  <g transform="translate(120 330)"><g class="float c" filter="url(#soft)">
    <rect width="150" height="70" rx="12" fill="#1a1838" stroke="#f4f1ff" stroke-opacity=".25"/>
    <g fill="#f4f1ff" opacity=".7"><rect x="10" y="8" width="10" height="8" rx="2"/><rect x="30" y="8" width="10" height="8" rx="2"/><rect x="50" y="8" width="10" height="8" rx="2"/><rect x="70" y="8" width="10" height="8" rx="2"/><rect x="90" y="8" width="10" height="8" rx="2"/><rect x="110" y="8" width="10" height="8" rx="2"/><rect x="130" y="8" width="10" height="8" rx="2"/>
    <rect x="10" y="54" width="10" height="8" rx="2"/><rect x="30" y="54" width="10" height="8" rx="2"/><rect x="50" y="54" width="10" height="8" rx="2"/><rect x="70" y="54" width="10" height="8" rx="2"/><rect x="90" y="54" width="10" height="8" rx="2"/><rect x="110" y="54" width="10" height="8" rx="2"/><rect x="130" y="54" width="10" height="8" rx="2"/></g>
    <rect x="10" y="22" width="40" height="26" rx="4" fill="#e9573f"/><rect x="55" y="22" width="40" height="26" rx="4" fill="#6d5efc"/><rect x="100" y="22" width="40" height="26" rx="4" fill="#24a89a"/>
  </g></g>
  <g transform="translate(410 120)"><g class="float d" filter="url(#soft)">
    <rect width="120" height="64" rx="32" fill="#f4f1ff"/>
    <g stroke="#6d5efc" stroke-width="5" stroke-linecap="round"><path d="M28 32 v0"/><path d="M40 24 v16"/><path d="M52 16 v32"/><path d="M64 22 v20"/><path d="M76 12 v40"/><path d="M88 24 v16"/></g>
  </g></g>
</svg>`;

// a spreadsheet's rows, through three checks, into a filed return (SimplyFile - chip hero.art "ledger"); shapes only
const LEDGER_ART = `<svg viewBox="0 0 560 500" role="img" aria-label="Spreadsheet rows flowing through three checks into a filed return">
  <defs>
    <radialGradient id="lglow" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#10b981" stop-opacity=".4"/><stop offset="1" stop-color="#10b981" stop-opacity="0"/></radialGradient>
    <linearGradient id="lok" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f4a524"/><stop offset="1" stop-color="#e9573f"/></linearGradient>
    <filter id="lsoft" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="12" stdDeviation="14" flood-color="#000" flood-opacity=".35"/></filter>
  </defs>
  <circle cx="290" cy="230" r="220" fill="url(#lglow)"/>
  <g class="wind" fill="none" stroke="#b9b4dd" stroke-opacity=".45" stroke-width="2" stroke-linecap="round">
    <path d="M190 150 C 250 150, 260 230, 300 230"/><path d="M190 230 C 240 230, 260 230, 300 230"/><path d="M190 310 C 250 310, 260 230, 300 230"/>
  </g>
  <g transform="translate(30 70)"><g class="float" filter="url(#lsoft)">
    <rect width="170" height="230" rx="14" fill="#f4f1ff"/>
    <rect x="12" y="14" width="146" height="18" rx="4" fill="#24a89a"/>
    ${[0, 1, 2, 3, 4, 5, 6, 7].map((i) => `<rect x="12" y="${42 + i * 22}" width="70" height="12" rx="3" fill="#c4c0e0"/><rect x="90" y="${42 + i * 22}" width="40" height="12" rx="3" fill="#d9d5f0"/><rect x="136" y="${42 + i * 22}" width="22" height="12" rx="3" fill="${['#6d5efc', '#e9573f', '#24a89a', '#f4a524'][i % 4]}"/>`).join('')}
  </g></g>
  <g transform="translate(230 112)"><g class="float b" filter="url(#lsoft)"><rect width="104" height="44" rx="22" fill="#24a89a"/><path d="M26 22 l8 8 l16 -16" fill="none" stroke="#fff" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/><rect x="58" y="17" width="34" height="10" rx="5" fill="#fff" opacity=".8"/></g></g>
  <g transform="translate(250 206)"><g class="float c" filter="url(#lsoft)"><rect width="104" height="44" rx="22" fill="#4b9fe8"/><path d="M26 22 l8 8 l16 -16" fill="none" stroke="#fff" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/><rect x="58" y="17" width="34" height="10" rx="5" fill="#fff" opacity=".8"/></g></g>
  <g transform="translate(230 300)"><g class="float d" filter="url(#lsoft)"><rect width="104" height="44" rx="22" fill="#6d5efc"/><path d="M26 22 l8 8 l16 -16" fill="none" stroke="#fff" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/><rect x="58" y="17" width="34" height="10" rx="5" fill="#fff" opacity=".8"/></g></g>
  <path d="M360 230 C 390 230, 395 230, 410 230" fill="none" stroke="#f4f1ff" stroke-opacity=".6" stroke-width="2"/>
  <g transform="translate(410 120)"><g class="kite" filter="url(#lsoft)">
    <path d="M0 0 h96 l34 34 v186 H0z" fill="#f4f1ff"/><path d="M96 0 v34 h34" fill="#c4c0e0"/>
    <rect x="16" y="50" width="80" height="10" rx="4" fill="#c4c0e0"/><rect x="16" y="70" width="98" height="10" rx="4" fill="#c4c0e0"/><rect x="16" y="90" width="64" height="10" rx="4" fill="#c4c0e0"/>
    <circle cx="65" cy="160" r="34" fill="url(#lok)"/><path d="M50 160 l11 11 l21 -23" fill="none" stroke="#fff" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>
  </g></g>
</svg>`;
// a court diary, the scales and two deadline chips - one met, one running (Justify - chip hero.art "scales"); shapes only
const SCALES_ART = `<svg viewBox="0 0 560 500" role="img" aria-label="A court diary, the scales of justice and a deadline met">
  <defs>
    <radialGradient id="sglow" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#4c6ef5" stop-opacity=".45"/><stop offset="1" stop-color="#4c6ef5" stop-opacity="0"/></radialGradient>
    <linearGradient id="sgold" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ffd875"/><stop offset="1" stop-color="#e8a917"/></linearGradient>
    <filter id="ssoft" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="12" stdDeviation="14" flood-color="#000" flood-opacity=".35"/></filter>
  </defs>
  <circle cx="290" cy="240" r="225" fill="url(#sglow)"/>
  <g transform="translate(36 86)"><g class="float" filter="url(#ssoft)">
    <rect width="190" height="230" rx="14" fill="#f3f5ff"/><rect width="190" height="44" rx="14" fill="#3b5bdb"/><rect y="30" width="190" height="14" fill="#3b5bdb"/>
    <rect x="16" y="14" width="78" height="14" rx="5" fill="#fff" opacity=".9"/>
    ${[0, 1, 2, 3, 4].map((r) => [0, 1, 2, 3, 4, 5].map((c) => `<rect x="${14 + c * 28}" y="${58 + r * 32}" width="22" height="22" rx="5" fill="${r === 2 && c === 3 ? '#e8a917' : r === 1 && c === 1 ? '#3b5bdb' : '#dfe4fb'}"/>`).join('')).join('')}
  </g></g>
  <g transform="translate(262 70)"><g class="kite" filter="url(#ssoft)">
    <path d="M110 30v190M70 230h80" stroke="#f3f5ff" stroke-width="10" stroke-linecap="round"/>
    <path d="M30 70h160" stroke="url(#sgold)" stroke-width="10" stroke-linecap="round"/><circle cx="110" cy="30" r="12" fill="url(#sgold)"/>
    <path d="M44 70l-26 62h52zM176 70l-26 62h52z" fill="none" stroke="url(#sgold)" stroke-width="6" stroke-linejoin="round"/>
    <path d="M14 132a30 16 0 0 0 60 0zM146 132a30 16 0 0 0 60 0z" fill="url(#sgold)"/>
  </g></g>
  <g transform="translate(300 330)"><g class="float c" filter="url(#ssoft)"><rect width="200" height="58" rx="29" fill="#2b8a3e"/>
    <path d="M30 29 l9 9 l18 -19" fill="none" stroke="#fff" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>
    <rect x="70" y="18" width="104" height="9" rx="4.5" fill="#fff" opacity=".9"/><rect x="70" y="33" width="70" height="8" rx="4" fill="#fff" opacity=".6"/></g></g>
  <g transform="translate(70 360)"><g class="float d" filter="url(#ssoft)"><rect width="170" height="52" rx="26" fill="#c92a2a"/>
    <circle cx="28" cy="26" r="11" fill="none" stroke="#fff" stroke-width="3.5"/><path d="M28 19v8l5 3" stroke="#fff" stroke-width="3.5" stroke-linecap="round"/>
    <rect x="52" y="17" width="94" height="9" rx="4.5" fill="#fff" opacity=".9"/><rect x="52" y="30" width="60" height="7" rx="3.5" fill="#fff" opacity=".6"/></g></g>
</svg>`;
const HERO = { kite: HERO_ART, ledger: LEDGER_ART, scales: SCALES_ART };

// one step splitting into four roads that meet again at "done"
const ROADS_ART = (rows) => {
  const col = ['#24a89a', '#4b9fe8', '#e9573f', '#6d5efc'];
  const ys = [70, 150, 230, 310];
  return `<svg viewBox="0 0 520 380" role="img" aria-label="${esc(rows.map((r) => r.title).join(', '))}">
  <defs><filter id="rs" x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx="0" dy="8" stdDeviation="10" flood-color="#17162b" flood-opacity=".18"/></filter></defs>
  ${ys.map((y, i) => `<path d="M96 190 C 150 190, 150 ${y}, 220 ${y} L 320 ${y} C 390 ${y}, 390 190, 430 190" fill="none" stroke="${col[i]}" stroke-width="6" stroke-linecap="round" opacity=".9"/>`).join('')}
  <g filter="url(#rs)"><circle cx="70" cy="190" r="40" fill="#6d5efc"/><circle cx="452" cy="190" r="40" fill="url(#doneg)"/></g>
  <defs><linearGradient id="doneg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f4a524"/><stop offset="1" stop-color="#e9573f"/></linearGradient></defs>
  <path d="M60 176 v28 l 24 -14 z" fill="#fff"/>
  <path d="M436 190 l 11 11 l 21 -23" fill="none" stroke="#fff" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>
  ${ys.map((y, i) => `<g filter="url(#rs)"><rect x="180" y="${y - 22}" width="180" height="44" rx="22" fill="#fff"/><circle cx="202" cy="${y}" r="10" fill="${col[i]}"/>
    <text x="220" y="${y + 5}" font-family="system-ui, sans-serif" font-size="14" font-weight="700" fill="#17162b">${esc(rows[i].title)}</text></g>`).join('')}
</svg>`;
};

// the five ages, drawn simply (no faces, no skin tone - everyone)
const AGE_ART = {
  kids: '<path d="M48 18 L 66 40 L 48 62 L 34 40 Z" fill="#e9573f"/><path d="M48 18 L 66 40 L 48 40 Z" fill="#f4a524"/><path d="M48 62 q -6 10 2 16 q 8 6 -2 14" fill="none" stroke="#f4a524" stroke-width="3" stroke-linecap="round"/>',
  students: '<path d="M14 40 L 48 24 L 82 40 L 48 56 Z" fill="#6d5efc"/><path d="M28 47 v14 q 20 12 40 0 v-14" fill="#8f84ff"/><path d="M80 41 v18" stroke="#f4a524" stroke-width="3"/><circle cx="80" cy="62" r="4" fill="#f4a524"/>',
  makers: '<rect x="20" y="22" width="44" height="56" rx="6" fill="#24a89a"/><path d="M30 36 h24 M30 46 h24 M30 56 h14" stroke="#fff" stroke-width="3" stroke-linecap="round"/><path d="M58 70 L 80 28 l 8 4 L 66 74 l -10 4 z" fill="#f4a524"/>',
  business: '<rect x="18" y="34" width="60" height="42" rx="8" fill="#4b9fe8"/><path d="M38 34 v-8 q 0 -4 4 -4 h12 q 4 0 4 4 v8" fill="none" stroke="#4b9fe8" stroke-width="5"/><path d="M18 50 h60" stroke="#fff" stroke-opacity=".7" stroke-width="3"/><rect x="42" y="45" width="12" height="10" rx="2" fill="#f4a524"/>',
  elders: '<circle cx="32" cy="48" r="14" fill="none" stroke="#f4a524" stroke-width="5"/><circle cx="64" cy="48" r="14" fill="none" stroke="#f4a524" stroke-width="5"/><path d="M46 46 q 2 -4 4 0" fill="none" stroke="#f4a524" stroke-width="4"/><path d="M18 44 L 10 36 M 78 44 L 86 36" stroke="#f4a524" stroke-width="4" stroke-linecap="round"/><path d="M26 70 q 22 12 44 0" fill="none" stroke="#e9573f" stroke-width="4" stroke-linecap="round"/>',
};
const ageArt = (id) => `<svg viewBox="0 0 96 96" aria-hidden="true"><circle cx="48" cy="48" r="46" fill="#ffffff" fill-opacity=".06"/>${AGE_ART[id] || ''}</svg>`;

// where a work goes - drawn as plain things (a shelf, an upright phone, a wide screen, a chat, a page, headphones), never a brand's mark
const SHARE_ART = {
  shelf: '<rect x="12" y="14" width="10" height="34" rx="2" fill="#6d5efc"/><rect x="25" y="10" width="10" height="38" rx="2" fill="#e9573f"/><rect x="38" y="16" width="10" height="32" rx="2" fill="#24a89a" transform="rotate(8 43 32)"/><rect x="8" y="48" width="48" height="5" rx="2" fill="#f4a524"/>',
  reels: '<rect x="20" y="6" width="24" height="52" rx="6" fill="#e9573f"/><rect x="23" y="12" width="18" height="38" rx="3" fill="#fff"/><path d="M29 24 v14 l 11 -7 z" fill="#e9573f"/>',
  youtube: '<rect x="6" y="10" width="52" height="34" rx="4" fill="#26234d"/><rect x="10" y="14" width="44" height="26" rx="2" fill="#4b9fe8"/><path d="M28 21 v12 l 10 -6 z" fill="#fff"/><path d="M24 52 h16 M32 44 v8" stroke="#26234d" stroke-width="4" stroke-linecap="round"/>',
  chat: '<path d="M10 14 h44 a6 6 0 0 1 6 6 v20 a6 6 0 0 1 -6 6 H26 l -12 10 v-10 h-4 a6 6 0 0 1 -6 -6 V20 a6 6 0 0 1 6 -6z" fill="#24a89a"/><circle cx="22" cy="30" r="3.5" fill="#fff"/><circle cx="32" cy="30" r="3.5" fill="#fff"/><circle cx="42" cy="30" r="3.5" fill="#fff"/>',
  docs: '<path d="M16 6 h22 l 12 12 v40 H16z" fill="#4b9fe8"/><path d="M38 6 v12 h12" fill="#9cc8f2"/><path d="M22 30 h22 M22 38 h22 M22 46 h14" stroke="#fff" stroke-width="3" stroke-linecap="round"/>',
  audio: '<path d="M12 38 v-6 a20 20 0 0 1 40 0 v6" fill="none" stroke="#6d5efc" stroke-width="5" stroke-linecap="round"/><rect x="8" y="36" width="12" height="18" rx="5" fill="#6d5efc"/><rect x="44" y="36" width="12" height="18" rx="5" fill="#6d5efc"/>',
};
const shareArt = (id) => `<svg viewBox="0 0 64 64" aria-hidden="true">${SHARE_ART[id] || ''}</svg>`;

const SKY = `<svg class="sky" viewBox="0 0 1200 160" preserveAspectRatio="none" aria-hidden="true">
  <path d="M0 120 C 200 80, 400 150, 600 110 S 1000 70, 1200 110 L 1200 160 L 0 160 Z" fill="#6d5efc" opacity=".25"/>
  <path d="M0 140 C 250 110, 450 160, 700 130 S 1050 110, 1200 135 L 1200 160 L 0 160 Z" fill="#e9573f" opacity=".2"/></svg>`;

// ------------------------------------------------------------------------------------------------------------ the page

const badge = (name, i) => `<span class="badge b${i % 4}">${icon(name, 22)}</span>`;
const head = (x, center = false) => `<div class="head${center ? ' center' : ''} reveal"><span class="eyebrow">${esc(x.eyebrow)}</span><h2>${esc(x.title)}</h2>${x.sub ? `<p class="lede">${esc(x.sub)}</p>` : ''}</div>`;
const headline = (t) => { const parts = String(t).split(/(?<=\.)\s+/); return parts.length > 1 ? `${esc(parts.slice(0, -1).join(' '))} <em>${esc(parts[parts.length - 1])}</em>` : esc(t); };

function draw(d) {
  document.title = d.meta.title;
  if (d.skin) document.documentElement.dataset.skin = d.skin;   // a site's own look (showcase.css [data-skin=...])
  const md = document.querySelector('meta[name="description"]'); if (md) md.content = d.meta.description;
  const films = !!(d.theatre && (d.chapters || []).length);   // 2026-10-05: a new domain may have no films yet - its page still draws
  const groups = films ? d.theatre.groups : [];
  const chs = d.chapters || [];
  const firstOf = (mod) => chs.findIndex((c) => c.module === mod);
  root.innerHTML = `
  <header class="top" id="top"><div class="wrap">
    <a class="brand" href="#">${LOGOS[d.nav.logo] || LOGO}<span>${esc(d.nav.brand)}${d.nav.tag ? `<small>${esc(d.nav.tag)}</small>` : ''}</span></a>
    <button type="button" class="menu-btn" id="sc-menu" aria-expanded="false" aria-controls="sc-nav" aria-label="${esc(d.nav.menu || '')}">${icon('menu', 22)}</button>
    <nav id="sc-nav" aria-label="${esc(d.nav.menu || '')}">${d.nav.links.map(([id, label]) => `<a href="#${esc(id)}">${esc(label)}</a>`).join('')}</nav>
    <a class="btn primary" href="${esc(d.hero.start_href)}">${esc(d.nav.start)}</a>
  </div></header>

  <section class="hero"><div class="wrap">
    <div>
      <span class="eyebrow">${esc(d.hero.eyebrow)}</span>
      <h1>${headline(d.hero.title)}</h1>
      <p class="lede">${esc(d.hero.sub)}</p>
      <div class="acts">
        ${films ? `<button class="btn primary" type="button" data-play-all>${icon('play', 18)} ${esc(d.hero.play)}</button>` : ''}
        <a class="btn ghost" href="${esc(d.hero.start_href)}">${esc(d.hero.start)} ${icon('right', 16)}</a>
      </div>
      <p class="note">${icon('shield', 16)} <span>${esc(d.hero.note)}</span></p>
    </div>
    <div class="art">${HERO[d.hero.art] || HERO_ART}</div>
  </div>
  <div class="wrap"><div class="stats">${d.stats.map((s) => `<div class="stat"><b>${esc(s.n)}</b><span>${esc(s.label)}</span></div>`).join('')}</div></div>
  ${d.trust ? `<div class="wrap"><div class="trust"><span>${esc(d.trust.title)}</span>${d.trust.rows.map((r) => `<b>${esc(r)}</b>`).join('')}</div></div>` : ''}
  </section>

${d.steps ? `  <section class="steps" id="how"><div class="wrap">
    ${head(d.steps, true)}
    <ol class="steprow">${d.steps.rows.map((r, i) => `<li class="reveal">${badge(r.icon, i)}<span class="n">${i + 1}</span><h3>${esc(r.title)}</h3><p>${esc(r.line)}</p></li>`).join('')}</ol>
  </div></section>` : ''}

  ${films ? `  <section class="theatre" id="watch"><div class="wrap">
    ${head(d.theatre)}
    ${d.theatre.search ? `<div class="wfind" role="search">
      <label class="sr" for="sc-wq">${esc(d.theatre.search)}</label>
      <input id="sc-wq" type="search" placeholder="${esc(d.theatre.search)}" autocomplete="off" enterkeyhint="search"/>
      <span class="wcount" id="sc-wcount" aria-live="polite"></span>
      <div class="wtags">${(d.theatre.topics || []).map((t) => `<button type="button" class="wtag" data-tag="${esc(t)}">${esc(t)}</button>`).join('')}</div>
    </div>` : ''}
    <div class="stage">
      <div class="list" role="listbox" aria-label="${esc(d.theatre.playlist)}">
        ${groups.map((g) => `<h3 data-g="${esc(g.id)}">${esc(g.title)}</h3><p class="gl" data-g="${esc(g.id)}">${esc(g.line)}</p>
          ${chs.map((c, i) => (c.group !== g.id ? '' : `<button type="button" class="ch" role="option" data-ch="${i}">
            <span class="th"><img loading="lazy" src="${media(c.key, 'jpg')}" alt=""/><span class="n">${i + 1}</span><i></i></span>
            <span><b>${esc(c.title)}</b><small>${esc(c.module)}</small></span></button>`)).join('')}`).join('')}
        <p class="wnone" id="sc-wnone" hidden>${esc(d.theatre.none || '')}</p>
      </div>
      <div class="player">
        <div class="screen">
          <video id="sc-video" playsinline preload="metadata" controls crossorigin="anonymous"></video>
          <button type="button" class="cover" id="sc-cover" aria-label="${esc(d.hero.play)}"><span>${icon('play', 40)}</span><em></em></button>
        </div>
        <div class="bar" aria-hidden="true"><i id="sc-bar"></i></div>
        <div class="now">
          <div><span class="k" id="sc-of"></span><h3 id="sc-title"></h3><p id="sc-line"></p><span class="mod" id="sc-mod"></span><span class="wtags now-tags" id="sc-tags"></span></div>
          <div class="ctrl">
            <button type="button" class="ic" data-step="-1" aria-label="${esc(d.theatre.prev)}">${icon('dleft', 16)} ${esc(d.theatre.prev)}</button>
            <button type="button" class="ic" data-step="1" aria-label="${esc(d.theatre.next)}">${esc(d.theatre.next)} ${icon('dright', 16)}</button>
            <label class="toggle"><input type="checkbox" id="sc-auto"/> ${esc(d.theatre.autoplay)}</label>
          </div>
        </div>
        <ol class="marks" id="sc-marks"></ol>
        <p class="next" id="sc-next"></p>
      </div>
    </div>
  </div></section>` : ''}

${d.play ? `  <section class="play" id="play"><div class="wrap">
    <div class="playgrid">
      <div class="playtext reveal">
        <span class="eyebrow">${esc(d.play.eyebrow)}</span>
        <h2>${headline(d.play.title)}</h2>
        <p class="lede">${esc(d.play.sub)}</p>
        <ol class="playsteps">${d.play.steps.map((r, i) => `<li>${badge(r.icon, i)}<span><b>${esc(r.title)}</b><span>${esc(r.line)}</span></span></li>`).join('')}</ol>
        <div class="acts">
          <a class="btn primary" href="${esc(d.play.href)}" target="_blank" rel="noopener">${icon('play', 17)} ${esc(d.play.button)} ${icon('external', 14)}</a>
          ${films ? `<button type="button" class="btn ghost" data-play-all>${esc(d.play.watch)}</button>` : ''}
        </div>
        <p class="fine">${icon('shield', 14)} <span>${esc(d.play.fine)}</span></p>
      </div>
      <div class="playside reveal">
        <figure class="sandbox" aria-label="${esc(d.play.window.address)}">
          <div class="bar3"><i></i><i></i><i></i><span>${icon('lock', 12)} ${esc(d.play.window.address)}</span></div>
          <div class="sbody">
            <div class="who">${LOGOS[d.nav.logo] || LOGO}<span><b>${esc(d.play.window.firm)}</b><small>${esc(d.play.window.role)}</small></span></div>
            <div class="tiles">${d.play.window.rows.map(([k, v], i) => `<div class="tile t${i % 4}"><b>${esc(v)}</b><span>${esc(k)}</span></div>`).join('')}</div>
            <p class="reset">${icon('refresh', 14)} ${esc(d.play.window.reset)}</p>
          </div>
        </figure>
        <div class="tries"><h3>${esc(d.play.try_title)}</h3><ul>${d.play.tries.map((t) => `<li>${icon('check', 15)}<span>${esc(t)}</span></li>`).join('')}</ul></div>
      </div>
    </div>
  </div></section>` : ''}

${d.pillars ? `  <section class="pillars" id="why"><div class="wrap">
    ${head(d.pillars, true)}
    <div class="grid3">${d.pillars.rows.map((r, i) => `<article class="card reveal">${badge(r.icon, i)}<h3>${esc(r.title)}</h3><p>${esc(r.line)}</p></article>`).join('')}</div>
  </div></section>` : ''}

${d.share ? `  <section class="share" id="share"><div class="wrap">
    ${head(d.share, true)}
    <div class="sharerow">${d.share.rows.map((r) => `<article class="sh reveal">${shareArt(r.id)}<h3>${esc(r.title)}</h3><p>${esc(r.line)}</p></article>`).join('')}</div>
  </div></section>` : ''}

${d.roads ? `  <section class="roads" id="roads"><div class="wrap">
    ${head(d.roads)}
    <div class="roadmap">
      <div class="reveal">${ROADS_ART(d.roads.rows)}</div>
      <div class="roadlist">${d.roads.rows.map((r, i) => `<article class="road reveal">${badge(['shield', 'link', 'spark', 'edit'][i], [2, 2, 1, 0][i])}
        <div><h3>${esc(r.title)} <small>${esc(r.tag)}</small></h3><p>${esc(r.line)}</p></div></article>`).join('')}</div>
    </div>
  </div></section>` : ''}

${d.checks ? `  <section class="checks"><div class="wrap">
    ${head(d.checks, true)}
    <div class="grid4">${d.checks.rows.map((r, i) => `<article class="card reveal">${badge(r.icon, i)}<h3>${esc(r.title)}</h3><p>${esc(r.line)}</p></article>`).join('')}</div>
  </div></section>` : ''}

${d.desks ? `  <section class="desks" id="who"><div class="wrap">
    ${head(d.desks, true)}
    <div class="grid3">${d.desks.rows.map((r, i) => `<article class="card desk reveal${r.pick ? ' pick' : ''}">${r.pick ? `<span class="ribbon">${esc(r.pick)}</span>` : ''}${badge(r.icon, i)}
      <h3>${esc(r.title)}</h3><p>${esc(r.line)}</p><ul>${r.gets.map((g) => `<li>${icon('check', 16)}<span>${esc(g)}</span></li>`).join('')}</ul>
      <a class="btn ${r.pick ? 'primary' : 'dark'}" href="${esc(d.hero.start_href)}">${esc(d.desks.start)} ${icon('right', 16)}</a></article>`).join('')}</div>
  </div></section>` : ''}

${d.modules ? `  <section class="mods" id="modules"><div class="wrap">
    ${head(d.modules)}
    ${d.modules.groups.map((g, gi) => `<div class="modgroup"><h3>${esc(g.title)}</h3><div class="grid4">
      ${g.rows.map((m, i) => { const at = firstOf(m.name); return `<article class="card mod reveal"><div class="top2">${badge(m.icon, gi + i)}<div><h4>${esc(m.name)}</h4><span class="for">${esc(m.for)}</span></div></div>
        <p>${esc(m.line)}</p>${at >= 0 ? `<button type="button" class="watch" data-ch="${at}">${icon('play', 13)} ${esc(d.theatre.watch)}${chs[at].title === m.name ? '' : `: ${esc(chs[at].title)}`}</button>` : ''}</article>`; }).join('')}
    </div></div>`).join('')}
  </div></section>` : ''}

${d.shelf ? `  <section class="shelf"><div class="wrap">
    ${head(d.shelf)}
    <div class="grid3">${d.shelf.rows.map((r, i) => `<article class="card reveal">${badge(r.icon, i + 1)}<div><h3>${r.href ? `<a href="${esc(r.href)}" target="_blank" rel="noopener">${esc(r.title)}</a>` : esc(r.title)}</h3><p>${esc(r.line)}</p></div></article>`).join('')}</div>
  </div></section>` : ''}

${d.ages ? `  <section class="ages" id="ages"><div class="wrap">
    ${head(d.ages, true)}
    <div class="agerow">${d.ages.rows.map((r) => `<article class="age reveal">${ageArt(r.id)}<h3>${esc(r.title)}</h3><p>${esc(r.line)}</p></article>`).join('')}</div>
  </div></section>` : ''}

${d.features ? `  <section class="features" id="features"><div class="wrap">
    ${head(d.features)}
    <div class="ftools">
      <button type="button" class="chip on" data-fg="">${esc(d.features.filter_all)}</button>
      ${d.features.groups.map((g, i) => `<button type="button" class="chip" data-fg="${i}">${esc(g.title)}</button>`).join('')}
      <label class="sr" for="sc-fq">${esc(d.features.search)}</label>
      <input id="sc-fq" type="search" placeholder="${esc(d.features.search)}" autocomplete="off"/>
    </div>
    <div class="fcols" id="sc-fcols"></div>
  </div></section>` : ''}

${d.faq ? `  <section class="faq" id="faq"><div class="wrap">
    ${head(d.faq, true)}
    <div class="qs">${d.faq.rows.map((r) => `<details class="reveal"><summary>${esc(r.q)}${icon('down', 18)}</summary><p>${esc(r.a)}</p></details>`).join('')}</div>
  </div></section>` : ''}

  <section class="cta"><div class="wrap">
    <h2>${esc(d.cta.title)}</h2>
    <p class="lede">${esc(d.cta.sub)}</p>
    <div class="acts">
      <a class="btn primary" href="${esc(d.hero.start_href)}">${esc(d.cta.start)} ${icon('right', 16)}</a>
      ${d.play ? `<a class="btn ghost" href="${esc(d.play.href)}" target="_blank" rel="noopener">${esc(d.cta.demo || d.play.button)} ${icon('external', 14)}</a>` : ''}
      ${films ? `<button type="button" class="btn ghost" data-play-all>${icon('play', 16)} ${esc(d.cta.watch)}</button>` : ''}
    </div>
    <p class="fine">${esc(d.cta.fine)}</p>
  </div>${SKY}</section>

  <footer><div class="wrap"><span>${esc(d.foot.line)}</span><a href="${esc(d.foot.maker_href)}" target="_blank" rel="noopener">${esc(d.foot.maker)} ${icon('external', 13)}</a></div></footer>`;
  root.removeAttribute('aria-busy');
  if (d.theatre && (d.chapters || []).length) wirePlayer(d);
  wireFeatures(d);
  wireChrome();
  // a link to a section (/#features) arrives before the sections exist - the browser found nothing to scroll to; go there now
  const there = location.hash.length > 1 && document.getElementById(decodeURIComponent(location.hash.slice(1)));
  if (there) requestAnimationFrame(() => there.scrollIntoView());
}

// ------------------------------------------------------------------------------------------- the player and its list

// Flexible find (2026-10-07 owner: "people want to find" a film like a short): every word typed must meet some word of
// the film - its title, line, module, group, tags or moments - inside it, or one letter off (a typo, a plural).
// ponytail: a linear scan over the chapters, fine to a few hundred films; an index if a site ever has thousands.
const norm = (s) => String(s ?? '').toLowerCase().normalize('NFKD').replace(/\p{M}/gu, '').replace(/[^\p{L}\p{N}]+/gu, ' ').trim();
const nearWord = (a, b) => {                                // one letter added, dropped or changed
  if (Math.abs(a.length - b.length) > 1) return false;
  let i = 0; let j = 0; let miss = 0;
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) { i += 1; j += 1; continue; }
    miss += 1;
    if (miss > 1) return false;
    if (a.length > b.length) i += 1; else if (b.length > a.length) j += 1; else { i += 1; j += 1; }
  }
  return miss + (a.length - i) + (b.length - j) <= 1;
};
const filmWords = (c, g) => norm([c.title, c.line, c.module, g && g.title, ...(c.tags || []), ...(c.marks || []).map((m) => m.title)].join(' ')).split(' ');
const findsFilm = (words, q) => norm(q).split(' ').filter(Boolean).every((t) => words.some((w) => w.includes(t) || (t.length > 4 && nearWord(w, t))));

function wirePlayer(d) {
  const chs = d.chapters;
  const video = document.getElementById('sc-video');
  const cover = document.getElementById('sc-cover');
  const auto = document.getElementById('sc-auto');
  const items = [...document.querySelectorAll('.ch')];
  const seen = new Set(store.get('seen', []));
  let at = Math.min(Math.max(0, store.get('at', 0)), chs.length - 1);
  auto.checked = store.get('auto', true);
  // the films a find left (all of them with no find); Next, Previous, N/P and play-the-next step through these only
  const q = document.getElementById('sc-wq');
  const hay = chs.map((c) => filmWords(c, d.theatre.groups.find((g) => g.id === c.group)));
  let shown = chs.map((_, i) => i);
  const stepFrom = (k) => {
    const p = shown.indexOf(at);
    if (!shown.length) return at;
    if (p < 0) return shown[0];
    return shown[(p + k + shown.length) % shown.length];
  };
  const find = () => {
    const text = q ? q.value : '';
    shown = chs.map((_, i) => i).filter((i) => findsFilm(hay[i], text));
    items.forEach((b) => { b.hidden = !shown.includes(Number(b.dataset.ch)); });
    document.querySelectorAll('.list [data-g]').forEach((x) => { x.hidden = !shown.some((i) => chs[i].group === x.dataset.g); });
    document.getElementById('sc-wnone').hidden = shown.length > 0;
    const n = document.getElementById('sc-wcount');
    if (n) n.textContent = norm(text) ? (d.theatre.found || '').replace('{n}', shown.length).replace('{total}', chs.length) : '';
    document.querySelectorAll('.wfind [data-tag]').forEach((b) => b.classList.toggle('on', norm(b.dataset.tag) === norm(text)));
    try {                                                   // a find can be shared: ?find=storyboard#watch
      const u = new URL(location.href);
      if (norm(text)) u.searchParams.set('find', text); else u.searchParams.delete('find');
      history.replaceState(null, '', u);
    } catch { /* a sandboxed page keeps its address */ }
  };

  const mark = () => items.forEach((b) => { const i = Number(b.dataset.ch); b.classList.toggle('on', i === at); b.classList.toggle('seen', seen.has(chs[i].key)); b.setAttribute('aria-selected', i === at ? 'true' : 'false'); });
  const say = () => {
    const c = chs[at];
    document.getElementById('sc-of').textContent = d.theatre.of.replace('{n}', at + 1).replace('{total}', chs.length);
    document.getElementById('sc-title').textContent = c.title;
    document.getElementById('sc-line').textContent = c.line;
    document.getElementById('sc-mod').textContent = c.module;
    // a long film's own moments (chapter `marks`: [{t: seconds, title}]) - press one and the film jumps there
    const mk = document.getElementById('sc-marks');
    mk.innerHTML = (c.marks || []).map((m, i) => `<li><button type="button" data-mark="${i}"><span>${Math.floor(m.t / 60)}:${String(Math.floor(m.t % 60)).padStart(2, '0')}</span> ${esc(m.title)}</button></li>`).join('');
    mk.querySelectorAll('[data-mark]').forEach((b) => b.addEventListener('click', () => {
      const m = c.marks[Number(b.dataset.mark)];
      const go = () => { video.currentTime = m.t; video.play().catch(() => {}); cover.hidden = true; };
      if (video.readyState >= 1) go(); else video.addEventListener('loadedmetadata', go, { once: true });
    }));
    const tg = document.getElementById('sc-tags');
    if (tg) tg.innerHTML = d.theatre.search ? (c.tags || []).map((t) => `<button type="button" class="wtag" data-tag="${esc(t)}">${esc(t)}</button>`).join('') : '';
    const nx = chs[stepFrom(1)];
    if (nx === c) { document.getElementById('sc-next').innerHTML = ''; return; }
    document.getElementById('sc-next').innerHTML = nx ? `${esc(d.theatre.up_next)}: <b>${esc(nx.title)}</b> · ${esc(nx.module)}` : '';
  };
  const load = (i, play) => {
    at = (i + chs.length) % chs.length;
    store.set('at', at);
    const c = chs[at];
    video.innerHTML = `<source src="${media(c.key, 'mp4')}" type="video/mp4"/><track kind="captions" srclang="en" label="${esc(d.theatre.captions)}" src="${media(c.key, 'vtt')}"/>`;
    video.poster = media(c.key, 'jpg');
    video.load();
    cover.style.backgroundImage = `url("${media(c.key, 'jpg')}")`;
    cover.querySelector('em').textContent = c.title;
    cover.hidden = !!play;
    document.getElementById('sc-bar').style.width = '0';
    say();
    mark();
    const on = items.find((b) => Number(b.dataset.ch) === at);
    const list = on && on.closest('.list');               // the list scrolls inside itself - never the page
    if (list && list.scrollHeight > list.clientHeight) list.scrollTo({ top: on.offsetTop - list.clientHeight / 2 + on.clientHeight / 2, behavior: 'smooth' });
    if (play) video.play().catch(() => { cover.hidden = false; });
  };
  video.addEventListener('timeupdate', () => {
    if (!video.duration) return;
    const pct = (100 * video.currentTime) / video.duration;
    document.getElementById('sc-bar').style.width = `${pct}%`;
    const th = items.find((b) => Number(b.dataset.ch) === at);
    if (th) th.querySelector('.th i').style.width = `${pct}%`;
    const ms = chs[at].marks || [];
    const here = ms.reduce((k, m, i) => (video.currentTime + 0.5 >= m.t ? i : k), -1);
    document.querySelectorAll('#sc-marks [data-mark]').forEach((b) => b.classList.toggle('on', Number(b.dataset.mark) === here));
  });
  video.addEventListener('play', () => { cover.hidden = true; });
  video.addEventListener('ended', () => {
    seen.add(chs[at].key);
    store.set('seen', [...seen]);
    mark();
    const p = shown.indexOf(at);
    if (auto.checked && p >= 0 && p < shown.length - 1) load(shown[p + 1], true);
  });
  auto.addEventListener('change', () => store.set('auto', auto.checked));
  cover.addEventListener('click', () => { cover.hidden = true; video.play().catch(() => { cover.hidden = false; }); });
  document.querySelectorAll('[data-step]').forEach((b) => b.addEventListener('click', () => load(stepFrom(Number(b.dataset.step)), !video.paused || cover.hidden)));
  if (q) {
    q.addEventListener('input', find);
    q.addEventListener('keydown', (e) => { if (e.key === 'Enter' && shown.length) { e.preventDefault(); load(shown[0], true); } });
  }
  document.addEventListener('click', (e) => {
    const tag = q && e.target.closest('[data-tag]');      // a tag finds every film that carries it; pressed again, clears
    if (tag) {
      q.value = norm(q.value) === norm(tag.dataset.tag) ? '' : tag.dataset.tag;
      find();
      if (!tag.closest('.wfind')) q.scrollIntoView({ behavior: 'smooth', block: 'center' });
      return;
    }
    const pick = e.target.closest('[data-ch]');
    if (pick) { load(Number(pick.dataset.ch), true); if (!pick.classList.contains('ch')) document.getElementById('watch').scrollIntoView({ behavior: 'smooth' }); return; }
    if (e.target.closest('[data-play-all]')) { document.getElementById('watch').scrollIntoView({ behavior: 'smooth' }); load(at, true); }
  });
  document.addEventListener('keydown', (e) => {
    if (e.target.closest('input, textarea')) return;
    if (e.key === 'n' || e.key === 'N') load(stepFrom(1), true);
    if (e.key === 'p' || e.key === 'P') load(stepFrom(-1), true);
  });
  const asked = q && new URLSearchParams(location.search).get('find');
  if (asked) { q.value = asked; find(); if (shown.length && !shown.includes(at)) at = shown[0]; }
  load(at, false);
}

// ---------------------------------------------------------------------------------------------- the feature list

function wireFeatures(d) {
  const box = document.getElementById('sc-fcols');
  const q = document.getElementById('sc-fq');
  let group = '';
  const draw_ = () => {
    const words = q.value.trim().toLowerCase();
    const html = d.features.groups.map((g, i) => {
      if (group !== '' && String(i) !== group) return '';
      const rows = g.rows.filter((r) => !words || r.toLowerCase().includes(words));
      return rows.length ? `<div class="fgroup"><h3>${esc(g.title)}</h3><ul>${rows.map((r) => `<li>${icon('check', 16)}<span>${esc(r)}</span></li>`).join('')}</ul></div>` : '';
    }).join('');
    box.innerHTML = html || `<p class="fnone">${esc(d.features.none)}</p>`;
  };
  document.querySelectorAll('[data-fg]').forEach((b) => b.addEventListener('click', () => {
    group = b.dataset.fg;
    document.querySelectorAll('[data-fg]').forEach((x) => x.classList.toggle('on', x === b));
    draw_();
  }));
  q.addEventListener('input', draw_);
  draw_();
}

// ----------------------------------------------------------------------------------- the bar and the reveal on scroll

function wireChrome() {
  const top = document.getElementById('top');
  const menu = document.getElementById('sc-menu');
  const nav = document.getElementById('sc-nav');
  const shut = () => { top.classList.remove('open'); menu.setAttribute('aria-expanded', 'false'); };
  menu.addEventListener('click', () => { const on = !top.classList.contains('open'); top.classList.toggle('open', on); menu.setAttribute('aria-expanded', String(on)); });
  nav.addEventListener('click', (e) => { if (e.target.closest('a')) shut(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') shut(); });
  const solid = () => top.classList.toggle('solid', window.scrollY > 40);
  window.addEventListener('scroll', solid, { passive: true });
  solid();
  const els = document.querySelectorAll('.reveal');
  if (!('IntersectionObserver' in window)) { els.forEach((x) => x.classList.add('in')); return; }
  const io = new IntersectionObserver((rows) => rows.forEach((r) => { if (r.isIntersecting) { r.target.classList.add('in'); io.unobserve(r.target); } }), { rootMargin: '0px 0px -8% 0px' });
  els.forEach((x) => io.observe(x));
}

fetch('api/showcase', { credentials: 'same-origin' })
  .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
  .then(draw)
  .catch(() => { root.removeAttribute('aria-busy'); });  // the server-drawn name stays on screen
