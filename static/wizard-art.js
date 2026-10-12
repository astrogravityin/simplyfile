// New filing's pictures - hand-drawn SVG line art, coloured only by the portal's tokens (light and dark follow on their own).
// art(kind): one card's illustration (who a return is for, what applies); hero(): the start screen's picture - documents
// flowing into a return; rail(steps, now, done): the four steps. Every word arrives as an argument (chip ui.wizard).
import { esc } from './app.js';

const P = {   // each picture on a 64 x 64 grid: s = stroke lines, f = soft fills, a = accent lines (the brand's second colour)
  self: { f: '<circle cx="32" cy="24" r="9"/><path d="M15 50c2-10 9-15 17-15s15 5 17 15z"/>', s: '<circle cx="32" cy="24" r="9"/><path d="M15 50c2-10 9-15 17-15s15 5 17 15"/>', a: '<path d="M44 14l2 4 4 1-3 3 1 4-4-2-4 2 1-4-3-3 4-1z"/>' },
  person: { f: '<circle cx="27" cy="23" r="8"/><path d="M12 49c2-9 8-13 15-13s13 4 15 13z"/>', s: '<circle cx="27" cy="23" r="8"/><path d="M12 49c2-9 8-13 15-13s13 4 15 13"/>', a: '<rect x="40" y="34" width="14" height="11" rx="2"/><path d="M44 34v-3h6v3M40 39h14"/>' },
  family: { f: '<circle cx="21" cy="22" r="6"/><circle cx="43" cy="22" r="6"/><path d="M9 48c1-8 6-12 12-12s11 4 12 12zM31 48c1-8 6-12 12-12s11 4 12 12z"/>', s: '<circle cx="21" cy="22" r="6"/><circle cx="43" cy="22" r="6"/><path d="M9 48c1-8 6-12 12-12s11 4 12 12M31 48c1-8 6-12 12-12s11 4 12 12"/>', a: '<circle cx="32" cy="35" r="4"/><path d="M26 50c1-5 3-8 6-8s5 3 6 8"/>' },
  salary: { f: '<rect x="10" y="20" width="44" height="26" rx="4"/>', s: '<rect x="10" y="20" width="44" height="26" rx="4"/><path d="M10 28h44"/>', a: '<path d="M27 34h10M27 38h10M31 34c4 0 4 4 0 4l5 5"/>' },
  employers: { f: '<path d="M8 50V24l12-6v32zM40 50V18l14 6v26z"/>', s: '<path d="M8 50V24l12-6v32M40 50V18l14 6v26M6 50h52M12 30h4M12 37h4M44 28h6M44 35h6"/>', a: '<path d="M24 33h12M32 29l4 4-4 4"/>' },
  house: { f: '<path d="M14 30l18-15 18 15v20H14z"/>', s: '<path d="M10 32l22-18 22 18M14 29v21h36V29M27 50V38h10v12"/>', a: '<circle cx="47" cy="17" r="4"/><path d="M47 21v8M47 26h3"/>' },
  interest: { f: '<ellipse cx="26" cy="44" rx="13" ry="5"/><ellipse cx="26" cy="36" rx="13" ry="5"/>', s: '<ellipse cx="26" cy="44" rx="13" ry="5"/><path d="M13 36v8M39 36v8"/><ellipse cx="26" cy="36" rx="13" ry="5"/><path d="M13 28v8M39 28v8"/><ellipse cx="26" cy="28" rx="13" ry="5"/>', a: '<path d="M44 26l10-10M45 17h.1M53 25h.1"/><circle cx="45" cy="17" r="2"/><circle cx="53" cy="25" r="2"/>' },
  shares: { f: '<rect x="12" y="36" width="8" height="14" rx="1.5"/><rect x="26" y="28" width="8" height="22" rx="1.5"/><rect x="40" y="22" width="8" height="28" rx="1.5"/>', s: '<rect x="12" y="36" width="8" height="14" rx="1.5"/><rect x="26" y="28" width="8" height="22" rx="1.5"/><rect x="40" y="22" width="8" height="28" rx="1.5"/><path d="M8 50h48"/>', a: '<path d="M12 26l12-8 9 5 17-11M44 12h6v6"/>' },
  property: { f: '<path d="M8 46l14-8 20 6 14-8v14H8z"/>', s: '<path d="M8 46l14-8 20 6 14-8M8 52h48"/>', a: '<path d="M38 36V14l12 4-12 4"/><path d="M22 38v-8"/>' },
  vda: { f: '<path d="M32 10l18 10v22L32 52 14 42V20z"/>', s: '<path d="M32 10l18 10v22L32 52 14 42V20zM14 20l18 10 18-10M32 30v22"/>', a: '<circle cx="32" cy="30" r="3"/>' },
  business: { f: '<path d="M12 28h40v22H12z"/>', s: '<path d="M10 28l5-12h34l5 12M12 28h40v22H12zM26 50V38h12v12"/>', a: '<path d="M10 28c0 4 5 4 5 0 0 4 6 4 6 0 0 4 6 4 6 0 0 4 6 4 6 0 0 4 6 4 6 0 0 4 5 4 5 0"/>' },
  foreign: { f: '<circle cx="32" cy="32" r="20"/>', s: '<circle cx="32" cy="32" r="20"/><path d="M12 32h40M32 12c-7 7-7 33 0 40M32 12c7 7 7 33 0 40"/>', a: '<path d="M18 20c5 3 23 3 28 0M18 44c5-3 23-3 28 0"/>' },
  nri: { f: '<path d="M8 46c8-10 40-10 48 0z"/>', s: '<path d="M8 46c8-10 40-10 48 0M6 50h52"/>', a: '<path d="M18 30l26-12 4 2-10 9 6 7-3 1-8-5-9 4-4-1 7-5z"/>' },
  arrears: { f: '<rect x="12" y="16" width="40" height="36" rx="4"/>', s: '<rect x="12" y="16" width="40" height="36" rx="4"/><path d="M12 25h40M22 12v8M42 12v8"/>', a: '<path d="M40 40a8 8 0 1 1-3-7M37 28v5h5"/>' },
  losses: { f: '<path d="M10 20l14 12 10-6 20 18v6H10z"/>', s: '<path d="M10 20l14 12 10-6 20 18M8 50h48"/>', a: '<path d="M44 44h10v-10"/><path d="M14 44h18M28 40l4 4-4 4"/>' },
  revise: { f: '<path d="M16 10h22l10 10v34H16z"/>', s: '<path d="M16 10h22l10 10v34H16zM38 10v10h10M22 28h18M22 35h12"/>', a: '<path d="M30 50l3-9 15-15 6 6-15 15zM45 29l6 6"/>' },
  // 2026-10-11 later: the businesses (who) and the kinds of work
  firm: { f: '<path d="M10 50V26l22-12 22 12v24z"/>', s: '<path d="M8 27l24-13 24 13M12 26v24h40V26M6 50h52M24 50V38h16v12"/>', a: '<circle cx="24" cy="30" r="3"/><circle cx="40" cy="30" r="3"/><path d="M28 30h8"/>' },
  llp: { f: '<rect x="12" y="18" width="40" height="32" rx="3"/>', s: '<rect x="12" y="18" width="40" height="32" rx="3"/><path d="M12 28h40M24 18v-6h16v6"/>', a: '<path d="M22 38l6 6 14-14"/>' },
  aop: { f: '<circle cx="18" cy="26" r="6"/><circle cx="32" cy="20" r="6"/><circle cx="46" cy="26" r="6"/>', s: '<circle cx="18" cy="26" r="6"/><circle cx="32" cy="20" r="6"/><circle cx="46" cy="26" r="6"/><path d="M8 48c1-7 5-11 10-11s9 4 10 11M22 44c1-8 5-12 10-12s9 4 10 12M36 48c1-7 5-11 10-11s9 4 10 11"/>', a: '<path d="M14 54h36"/>' },
  company: { f: '<path d="M16 54V12h22v42zM38 54V26h12v28z"/>', s: '<path d="M16 54V12h22v42M38 26h12v28M10 54h46M22 20h4M30 20h4M22 28h4M30 28h4M22 36h4M30 36h4M42 34h4M42 42h4"/>', a: '<path d="M24 54v-8h6v8"/>' },
  trust: { f: '<path d="M32 10l18 8v12c0 12-8 20-18 24-10-4-18-12-18-24V18z"/>', s: '<path d="M32 10l18 8v12c0 12-8 20-18 24-10-4-18-12-18-24V18z"/>', a: '<path d="M32 24c-3-4-9-2-8 3 1 4 8 9 8 9s7-5 8-9c1-5-5-7-8-3z"/>' },
  trading: { f: '<path d="M12 22h40l-4 26H16z"/>', s: '<path d="M8 16h6l4 30h30l4-20H16M24 54a3 3 0 1 0 0-.1M44 54a3 3 0 1 0 0-.1"/>', a: '<path d="M26 32h18M28 39h14"/>' },
  factory: { f: '<path d="M8 52V30l12 8v-8l12 8v-8l12 8V14h10v38z"/>', s: '<path d="M8 52V30l12 8v-8l12 8v-8l12 8V14h10v38zM6 52h52"/>', a: '<path d="M48 10c0-3 4-3 4-6M16 46h6M28 46h6"/>' },
  services: { f: '<circle cx="32" cy="32" r="12"/>', s: '<circle cx="32" cy="32" r="12"/><path d="M32 12v6M32 46v6M12 32h6M46 32h6M18 18l4 4M42 42l4 4M46 18l-4 4M18 46l4-4"/>', a: '<circle cx="32" cy="32" r="4"/>' },
  profession: { f: '<rect x="12" y="22" width="40" height="28" rx="4"/>', s: '<rect x="12" y="22" width="40" height="28" rx="4"/><path d="M24 22v-6h16v6M12 34h40"/>', a: '<path d="M30 34v4h4v-4"/>' },
  farm: { f: '<path d="M8 50c10-6 38-6 48 0z"/>', s: '<path d="M8 50c10-6 38-6 48 0M32 46V22"/>', a: '<path d="M32 30c-6 0-10-4-10-10 6 0 10 4 10 10zM32 26c6 0 10-4 10-10-6 0-10 4-10 10zM32 38c-5 0-8-3-8-8 5 0 8 3 8 8z"/>' },
  gst: { f: '<rect x="12" y="12" width="40" height="40" rx="5"/>', s: '<rect x="12" y="12" width="40" height="40" rx="5"/><path d="M12 22h40"/>', a: '<path d="M24 44l16-14M25 33h.1M39 42h.1"/><circle cx="25" cy="33" r="2.5"/><circle cx="39" cy="42" r="2.5"/>' },
  presumptive: { f: '<circle cx="32" cy="32" r="20"/>', s: '<circle cx="32" cy="32" r="20"/><path d="M32 12v20h20"/>', a: '<path d="M32 32L46 18"/>' },
  books: { f: '<path d="M12 14h18v38H12zM34 14h18v38H34z"/>', s: '<path d="M12 14h18v38H12zM34 14h18v38H34zM16 22h10M16 28h10M38 22h10M38 28h10"/>', a: '<path d="M16 40h10M38 40h10"/>' },
  audit: { f: '<path d="M14 10h26l10 10v34H14z"/>', s: '<path d="M14 10h26l10 10v34H14zM40 10v10h10"/>', a: '<circle cx="30" cy="36" r="8"/><path d="M36 42l8 8M26 36l3 3 5-6"/>' },
  partners: { f: '<circle cx="22" cy="22" r="7"/><circle cx="42" cy="22" r="7"/>', s: '<circle cx="22" cy="22" r="7"/><circle cx="42" cy="22" r="7"/><path d="M8 50c1-9 6-14 14-14 4 0 7 1 10 4 3-3 6-4 10-4 8 0 13 5 14 14"/>', a: '<path d="M26 46h12M32 40v12"/>' },
  stock: { f: '<path d="M10 30h20v22H10zM34 30h20v22H34zM22 10h20v20H22z"/>', s: '<path d="M10 30h20v22H10zM34 30h20v22H34zM22 10h20v20H22z"/>', a: '<path d="M18 30v6M44 30v6M32 10v6"/>' },
  machine: { f: '<circle cx="24" cy="36" r="14"/>', s: '<circle cx="24" cy="36" r="14"/><circle cx="24" cy="36" r="5"/><path d="M38 36h16M46 28v16"/>', a: '<path d="M24 18v4M24 50v4M6 36h4M38 36h0"/>' },
};

/** One card's picture: a soft disc, the drawing in the brand's line, its accent in the second colour. */
export function art(kind) {
  const p = P[kind] || P.revise;
  return `<svg class="wz-art" viewBox="0 0 64 64" aria-hidden="true" focusable="false">
    <circle cx="32" cy="32" r="31" class="wz-disc"/><g class="wz-fill">${p.f}</g><g class="wz-line">${p.s}</g><g class="wz-acc">${p.a}</g></svg>`;
}

/** The start screen: three documents (Form 16, AIS, 26AS) drawn into a return that ticks itself - with a soft glow behind. */
export function hero() {
  const doc = (x, y, r, mark) => `<g transform="translate(${x} ${y}) rotate(${r})"><path d="M0 0h46l14 14v62a4 4 0 0 1-4 4H0a4 4 0 0 1-4-4V4a4 4 0 0 1 4-4z" class="wz-h-sheet"/>
      <path d="M46 0v10a4 4 0 0 0 4 4h10" class="wz-h-fold"/>${mark}</g>`;
  return `<svg class="wz-hero" viewBox="0 0 360 220" aria-hidden="true" focusable="false">
    <defs><radialGradient id="wz-glow" cx="50%" cy="50%" r="50%"><stop offset="0%" class="wz-h-g1"/><stop offset="100%" class="wz-h-g2"/></radialGradient></defs>
    <ellipse cx="236" cy="112" rx="130" ry="96" fill="url(#wz-glow)"/>
    ${doc(18, 34, -10, '<path d="M8 26h30M8 34h22M8 42h26" class="wz-h-ln"/><text x="12" y="64" class="wz-h-glyph">16</text>')}
    ${doc(64, 20, -3, '<rect x="8" y="40" width="8" height="22" rx="2" class="wz-h-bar"/><rect x="21" y="30" width="8" height="32" rx="2" class="wz-h-bar2"/><rect x="34" y="46" width="8" height="16" rx="2" class="wz-h-bar"/><path d="M8 20h34" class="wz-h-ln"/>')}
    ${doc(110, 40, 6, '<circle cx="28" cy="40" r="14" class="wz-h-ring"/><path d="M21 40l5 5 10-11" class="wz-h-ok"/>')}
    <path d="M184 92c18 0 22 20 40 20" class="wz-h-flow"/><path d="M184 128c18 0 22-16 40-16" class="wz-h-flow"/><path d="M218 105l8 7-8 7" class="wz-h-arrow"/>
    <g transform="translate(236 34)"><rect x="0" y="0" width="104" height="146" rx="12" class="wz-h-form"/>
      <rect x="14" y="16" width="44" height="10" rx="5" class="wz-h-chip"/><path d="M14 44h76M14 60h60M14 76h70M14 92h50" class="wz-h-ln"/>
      <circle cx="80" cy="118" r="15" class="wz-h-seal"/><path d="M72 118l6 6 10-12" class="wz-h-tick"/></g>
    <path d="M330 26l3 7 7 3-7 3-3 7-3-7-7-3 7-3z" class="wz-h-spark"/><path d="M200 40l2 4 4 2-4 2-2 4-2-4-4-2 4-2z" class="wz-h-spark"/></svg>`;
}

/** steps: [{id, label}]; now: an id; reach: how far a click may go (steps after it are shown, not pressable). */
export function rail(steps, now, reach) {
  const at = steps.findIndex((s) => s.id === now);
  const open = steps.findIndex((s) => s.id === reach);
  return `<ol class="wz-rail" aria-label="${esc(steps.map((s) => s.label).join(' - '))}">${steps.map((s, i) => {
    const cls = i < at ? 'is-done' : i === at ? 'is-now' : '';
    const can = i <= Math.max(open, at);
    return `<li class="wz-step ${cls}"><button type="button" class="wz-node" data-step="${esc(s.id)}" ${can ? '' : 'disabled'} ${i === at ? 'aria-current="step"' : ''}>
      <span class="wz-dot">${i < at ? '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3.5 8.5l3 3 6-7"/></svg>' : i + 1}</span><span class="wz-lab">${esc(s.label)}</span></button></li>`;
  }).join('')}</ol>`;
}
