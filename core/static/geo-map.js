// One choropleth for every map on the Visitors screen (world by country, India by state) — the plain-JS
// port of the studio's GeoChoropleth.tsx. Shapes arrive pre-projected as SVG paths (./geo/*.js, copied
// from the studio), so there is no mapping library and no runtime projection. Colour = magnitude on a
// LOG scale because traffic is heavily skewed; zero stays neutral so "none" never reads as "a little".
import { esc } from './ui.js';

const STEPS = 6;

export function level(value, max) {
  if (!value || value <= 0 || max <= 0) return 0;
  return 1 + Math.min(STEPS - 1, Math.floor((Math.log1p(value) / Math.log1p(max)) * STEPS));
}

/** shapes: [{key, name, d}] · values: {key: count} */
export function choropleth({ viewBox, shapes, values, unit, attribution = '' }) {
  const max = Math.max(0, ...Object.values(values));
  return `<div class="geo">
    <svg viewBox="${viewBox}" role="img" aria-label="Map of ${esc(unit)}">
      ${shapes.map((s) => `<path class="l${level(values[s.key] || 0, max)}" d="${s.d}"><title>${esc(s.name)}: ${(values[s.key] || 0).toLocaleString()} ${esc(unit)}</title></path>`).join('')}
    </svg>
    <div class="geo-legend"><span><i class="l0"></i> none</span>
      <span>fewer ${Array.from({ length: STEPS }, (_, i) => `<i class="l${i + 1}"></i>`).join('')} more (${max.toLocaleString()})</span>
      ${attribution ? `<span class="muted">${attribution}</span>` : ''}</div></div>`;
}

// The IP database and the DataMeet map name India's states differently ("National Capital Territory of
// Delhi" vs "Delhi", "Andaman and Nicobar Islands" vs "Andaman & Nicobar", old names like "Orissa").
// Both sides go through this one key. Same rules as the studio indiaRegion.ts.
const DNH = 'dadra and nagar haveli and daman and diu';
const ALIAS = {
  orissa: 'odisha',
  pondicherry: 'puducherry',
  uttaranchal: 'uttarakhand',
  'dadra and nagar haveli': DNH,
  'daman and diu': DNH,
  'andaman nicobar': 'andaman and nicobar',
};

export function regionKey(name) {
  const s = String(name || '')
    .toLowerCase()
    .replace(/&/g, ' and ')
    .replace(/national capital territory of|union territory of|state of|\bnct\b|\bislands?\b/g, ' ')
    .replace(/[^a-z ]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  return ALIAS[s] ?? s;
}
