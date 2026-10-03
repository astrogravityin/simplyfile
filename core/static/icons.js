// One stroked icon set, inline. No icon font, no sprite fetch, no dependency — every glyph is a
// string of SVG paths on a 24-grid, drawn in `currentColor` at 1.75 stroke so it sits with text.
//
// `icon('save')` returns markup you drop straight into a template string.

const PATHS = {
  // navigation
  prompt:    'M4 17l6-6-6-6|M12 19h8',
  setup:     'M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z|M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9v0a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z',
  help:      'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20Z|M9.1 9a3 3 0 0 1 5.8 1c0 2-3 3-3 3|M12 17h.01',
  bell:      'M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9|M10.3 21a1.94 1.94 0 0 0 3.4 0',
  heart:     'M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z',
  share:     'M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8|M16 6l-4-4-4 4|M12 2v13',
  chat:      'M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2Z',
  book:      'M4 19.5A2.5 2.5 0 0 1 6.5 17H20|M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z',
  film:      'M4 3h16a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z|M7 3v18|M17 3v18|M3 8h4|M17 8h4|M3 16h4|M17 16h4',
  key:       'M16.5 7.5a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z|M11.4 9.6 3 18v3h3v-2h2v-2h2l1.4-1.4',
  // actions
  plus:      'M12 5v14|M5 12h14',
  check:     'M20 6 9 17l-5-5',
  close:     'M18 6 6 18|M6 6l12 12',
  trash:     'M3 6h18|M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2|M19 6v14a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V6|M10 11v6|M14 11v6',
  edit:      'M11 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-5|M18.5 2.5a2.12 2.12 0 0 1 3 3L12 15l-4 1 1-4Z',
  pause:     'M7 4h3v16H7z|M14 4h3v16h-3z',
  scissors:  'M6 6a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z|M6 23a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z|M8.1 8.1 20 20|M8.1 15.9 20 4|M7.5 7.5 12 12l-4.5 4.5',
  wand:      'M4 20 16 8|M14 6l4 4|M18 2v4|M16 4h4|M5 4v4|M3 6h4|M19 15v3|M17.5 16.5h3',
  translate: 'M3 5h10|M8 3v2|M11 5c0 4-3.5 7-8 8|M6 9c1.5 2.5 4 4.3 7 5|M13 21l4.5-11L22 21|M15 17h5',
  search:    'M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16Z|M21 21l-4.3-4.3',
  refresh:   'M20.5 11A8.5 8.5 0 0 0 5.6 6.1L3.5 8|M3.5 3.5V8H8|M3.5 13a8.5 8.5 0 0 0 14.9 4.9l2.1-1.9|M20.5 20.5V16H16',
  upload:    'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4|M17 8l-5-5-5 5|M12 3v13',
  grip:      'M9 5h.01|M15 5h.01|M9 12h.01|M15 12h.01|M9 19h.01|M15 19h.01',
  download:  'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4|M7 10l5 5 5-5|M12 15V3',
  play:      'M8 5.14v13.72a.5.5 0 0 0 .76.43l11.1-6.86a.5.5 0 0 0 0-.86L8.76 4.71A.5.5 0 0 0 8 5.14Z',
  save:      'M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2Z|M17 21v-8H7v8|M7 3v5h8',
  send:      'M22 2 11 13|M22 2l-7 20-4-9-9-4 20-7Z',
  // objects
  folder:    'M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z',
  git:       'M6 3v12|M18 9a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z|M6 21a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z|M18 9a9 9 0 0 1-9 9',
  mail:      'M4 4h16a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z|M22 7l-10 6L2 7',
  link:      'M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7|M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7',
  external:  'M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6|M15 3h6v6|M10 14 21 3',
  deck:      'M3 4h18v12H3Z|M12 16v4|M8 20h8|M7 12l3-3 2 2 4-4',
  image:     'M3 5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5Z|M8.5 11a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z|M21 15l-5-5L5 21',
  users:     'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2|M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z|M22 21v-2a4 4 0 0 0-3-3.87|M16 3.13a4 4 0 0 1 0 7.75',
  eye:       'M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z|M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z',
  spark:     'M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9L12 3Z|M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8L19 15Z',
  money:     'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20Z|M15 9a3 3 0 0 0-3-1.5c-1.7 0-3 .9-3 2.2 0 3 6 1.6 6 4.6 0 1.3-1.3 2.2-3 2.2A3 3 0 0 1 9 15|M12 6v12',
  // feedback
  alert:     'M12 9v4|M12 17h.01|M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z',
  info:      'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20Z|M12 16v-4|M12 8h.01',
  // shell
  user:      'M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2|M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z',
  menu:      'M3 6h18|M3 12h18|M3 18h18',
  sun:       'M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10Z|M12 1v2|M12 21v2|M4.2 4.2l1.4 1.4|M18.4 18.4l1.4 1.4|M1 12h2|M21 12h2|M4.2 19.8l1.4-1.4|M18.4 5.6l1.4-1.4',
  moon:      'M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z',
  mic:       'M12 15a3 3 0 0 0 3-3V6a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3Z|M19 11a7 7 0 0 1-14 0|M12 18v4|M8 22h8',
  clock:     'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20Z|M12 6v6l4 2',
  shield:    'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z|M9 12l2 2 4-4',
  lock:      'M5 11h14a1 1 0 0 1 1 1v8a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1v-8a1 1 0 0 1 1-1Z|M8 11V7a4 4 0 0 1 8 0v4',
  pulse:     'M3 12h4l3-8 4 16 3-8h4',
  chip:      'M7 5h10a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2Z|M10 10h4v4h-4z|M9 2v3|M15 2v3|M9 19v3|M15 19v3|M2 9h3|M2 15h3|M19 9h3|M19 15h3',
  globe:     'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20Z|M2 12h20|M12 2a15 15 0 0 1 0 20|M12 2a15 15 0 0 0 0 20',
  ban:       'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20Z|M5 5l14 14',
  archive:   'M3 4h18v4H3z|M5 8v11a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8|M10 12h4',
  // chevrons
  right:     'M9 18l6-6-6-6',
  dleft:     'M11.5 17l-5-5 5-5|M18 17l-5-5 5-5',
  dright:    'M12.5 17l5-5-5-5|M6 17l5-5-5-5',
  speaker:   'M11 5 6 9H3v6h3l5 4V5Z|M15.5 8.5a5 5 0 0 1 0 7|M18.5 5.5a9 9 0 0 1 0 13',
  left:      'M15 18l-6-6 6-6',
  up:        'M18 15l-6-6-6 6',
  down:      'M6 9l6 6 6-6',
};

/** The busy spinner. A dash-gapped ring rather than a path, so it reads at 14px. */
export function spinner(size = 15) {
  return `<svg class="ico spin" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true">
    <circle cx="12" cy="12" r="9" stroke-opacity=".25"/><path d="M21 12a9 9 0 0 0-9-9"/></svg>`;
}

export function icon(name, size = 16) {
  const d = PATHS[name];
  if (!d) return '';
  const paths = d.split('|').map((p) => `<path d="${p}"/>`).join('');
  return `<svg class="ico" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"
    aria-hidden="true" focusable="false">${paths}</svg>`;
}

/** The portal's mark: a play triangle sitting on two lines of text. Documentation that moves.
 *  Drawn to stay legible at 24px in the sidebar, so: one solid shape, two rules, nothing fine. */
export function logo(size = 28) {
  const id = `lg${size}`;
  return `<svg width="${size}" height="${size}" viewBox="0 0 32 32" fill="none" aria-hidden="true">
    <rect x="1" y="1" width="30" height="30" rx="9" fill="url(#${id})"/>
    <rect x="1.5" y="1.5" width="29" height="29" rx="8.5" stroke="#fff" stroke-opacity=".2"/>
    <path d="M13 10.6a.9.9 0 0 1 1.37-.77l6.4 3.96a.9.9 0 0 1 0 1.53l-6.4 3.95a.9.9 0 0 1-1.37-.76v-7.9Z" fill="#fff"/>
    <path d="M9.5 23.2h13M9.5 26.2h8" stroke="#fff" stroke-opacity=".62" stroke-width="1.8" stroke-linecap="round"/>
    <defs><linearGradient id="${id}" x1="1" y1="1" x2="31" y2="31" gradientUnits="userSpaceOnUse">
      <stop stop-color="#7c5cf0"/><stop offset="1" stop-color="#5b5bd6"/></linearGradient></defs>
  </svg>`;
}

/** Empty states. One quiet drawing, never a photo, never a mascot. */
export function blank(kind) {
  const art = {
    screens: '<rect x="8" y="14" width="48" height="34" rx="4"/><path d="M8 22h48M20 56h24M32 48v8"/><path d="M18 30h12M18 36h20" stroke-opacity=".5"/>',
    links: '<path d="M26 38a9 9 0 0 0 13.5.9l5.4-5.4a9 9 0 0 0-12.7-12.7l-3 3"/><path d="M38 26a9 9 0 0 0-13.5-.9l-5.4 5.4a9 9 0 0 0 12.7 12.7l3-3"/>',
    manuals: '<path d="M14 16a4 4 0 0 1 4-4h12v40H18a4 4 0 0 0-4 4V16Z"/><path d="M50 16a4 4 0 0 0-4-4H34v40h12a4 4 0 0 1 4 4V16Z"/><path d="M32 12v40" stroke-opacity=".4"/>',
    videos: '<rect x="10" y="16" width="44" height="30" rx="4"/><path d="M28 25.5v11l10-5.5-10-5.5Z" fill="currentColor" stroke="none" fill-opacity=".55"/>',
    projects: '<path d="M10 22a4 4 0 0 1 4-4h9l4 4h17a4 4 0 0 1 4 4v18a4 4 0 0 1-4 4H14a4 4 0 0 1-4-4V22Z"/>',
  }[kind] || '';
  return `<svg width="128" height="72" viewBox="0 0 64 64" fill="none" stroke="currentColor"
    stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${art}</svg>`;
}

/** The standard empty panel: a drawing, a sentence, and exactly one thing to do. */
export function emptyState(kind, title, line, actionHtml = '') {
  return `<div class="empty">${blank(kind)}
    <h3>${title}</h3><p>${line}</p>${actionHtml}</div>`;
}
