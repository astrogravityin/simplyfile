// Small drawing helpers every portal's screens share (boilerplate - domain-portal manifest). Presentation only: no words, no rules.
// 2026-10-05: boilerplate pages (approvals, portal analytics) import these from here, never from a domain page.
import { esc } from './app.js';
import { icon } from './icons.js';

// A steady colour per name for an initials badge.
export const hue = (name) => [...String(name)].reduce((h, ch) => (h * 31 + ch.charCodeAt(0)) % 360, 7);
export const initials = (name) => String(name).split(/\s+/).filter(Boolean).slice(0, 2).map((x) => x[0]).join('').toUpperCase() || '?';

// The one KPI tile every screen uses (CSS .sf-kpi): icon + label, the value, a sub-line - values line up across a row.
export const kpiTile = (ic, tone, label, value, sub) => `<div class="sf-kpi" style="--k:var(${tone})"><div class="sf-kpi-top"><span class="sf-kpi-ic">${icon(ic, 18)}</span>
  <span class="sf-kpi-lbl" title="${esc(label)}">${esc(label)}</span></div><div class="sf-kpi-big" title="${esc(String(value))}">${esc(String(value))}</div><div class="sf-kpi-sub">${esc(sub)}</div></div>`;

// A date as people read it: 05 Oct 2026 (with the weekday: Mon, 05 Oct 2026).
export const day = (iso, withWeekday = false) => {
  if (!iso) return '';
  const d = new Date(`${iso}T00:00:00`);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', ...(withWeekday ? { weekday: 'short' } : {}) });
};

// Horizontal bars, one per group ({key, n}) - largest first unless keep (portal analytics, a domain's analytics).
export function bars(groups, field = 'n', keep = false) {
  const top = Math.max(1, ...groups.map((g) => g[field] || 0));
  return `<div class="an-bars">${(keep ? groups : groups.slice().sort((a, b) => (b[field] || 0) - (a[field] || 0))).map((g) => `<div class="an-brow"><span>${esc(g.key || '-')}</span>
    <svg width="100%" height="10"><rect width="100%" height="10" rx="5" fill="var(--panel-2)"/><rect width="${Math.max(2, ((g[field] || 0) / top) * 100)}%" height="10" rx="5" fill="var(--brand)"/></svg><b>${g[field] || 0}</b></div>`).join('')}</div>`;
}
