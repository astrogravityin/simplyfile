// Rules and assumptions beside the ITR JSON (2026-10-19 owner: "the detail rules / assumption applied to generate the ITR 2, 3 and
// 5 ... next to the json file, very clearly visible"). Drawn from the itr-check answer's `rules` (itr_json.assumptions, chip
// itr.assumptions) on Compute & close and on My return's File step. Words: chip ui.itrrules. Presentation only.
import { esc, t } from './app.js';
import { icon } from './icons.js';

const w = (k, v) => t('itrrules', k, v);

// Your figures -> rules (chips) -> CBDT schema -> JSON file: where every line below comes from.
const flow = () => {
  const steps = ['flow_1', 'flow_2', 'flow_3', 'flow_4'];
  return `<svg class="ir-flow" viewBox="0 0 400 64" role="img" aria-label="${esc(steps.map((k) => w(k)).join(' → '))}">
    <defs><linearGradient id="ir-g" x1="0" x2="1"><stop offset="0" stop-color="var(--brand)"/><stop offset="1" stop-color="var(--ok)"/></linearGradient></defs>
    <rect x="20" y="20" width="360" height="4" rx="2" fill="url(#ir-g)" opacity=".35"/>
    ${steps.map((k, i) => { const x = 20 + i * 120; return `<g><circle cx="${x}" cy="22" r="11" fill="var(--panel)" stroke="url(#ir-g)" stroke-width="2.5"/>
      <text x="${x}" y="26.5" text-anchor="middle" font-size="11" font-weight="700" fill="var(--brand)">${i + 1}</text>
      <text x="${x}" y="52" text-anchor="${i === 0 ? 'start' : i === 3 ? 'end' : 'middle'}" dx="${i === 0 ? -10 : i === 3 ? 10 : 0}" font-size="11" fill="var(--muted)">${esc(w(k))}</text></g>`; }).join('')}
  </svg>`;
};

// The card: the flow, a count, and every rule numbered under its group - a line that needs the person's attention in amber.
export const rulesCard = (rules) => {
  if (!rules || !rules.groups) return '';
  const warns = rules.groups.flatMap((g) => g.items).filter((x) => x.warn).length;
  return `<div class="ir-head"><div class="ir-title">${icon('shield', 16)}<b>${esc(w('title'))}</b><span class="tag">${esc(w('count', { n: rules.count }))}</span>
      ${warns ? `<span class="tag warn">${icon('alert', 11)} ${esc(w('attention', { n: warns }))}</span>` : ''}</div>
    <p class="small muted">${esc(w('lede'))}</p>${flow()}</div>
    <ol class="ir-list">${rules.groups.map((g) => `<li class="ir-group"><h4>${esc(g.label)}</h4><ol>${g.items.map((x) => `<li class="${x.warn ? 'is-warn' : ''}">
      ${x.warn ? icon('alert', 13) : ''}<span>${esc(x.say)}</span>${x.rule ? ` <code class="ir-rule" title="${esc(w('rule'))}">${esc(x.rule)}</code>` : ''}</li>`).join('')}</ol></li>`).join('')}</ol>
    ${rules.missing && rules.missing.length ? `<p class="small cc-check is-bad">${esc(w('missing', { names: rules.missing.join(', ') }))}</p>` : ''}`;
};
