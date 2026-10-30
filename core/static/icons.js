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
  agent:     'M5 10a3 3 0 0 1 3-3h8a3 3 0 0 1 3 3v6a3 3 0 0 1-3 3H8a3 3 0 0 1-3-3Z|M12 7V4|M10 4h4|M9.5 13h.01|M14.5 13h.01|M2.5 12v3|M21.5 12v3',
  plug:      'M9 2v5|M15 2v5|M6 7h12v4a6 6 0 0 1-12 0Z|M12 17v5',
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
  // 2026-10-04: the studio's bottom bar and Notes / Issues / Chip Chat (the same Lucide shapes the studio draws)
  crop:      'M6 2v14a2 2 0 0 0 2 2h14|M18 22V8a2 2 0 0 0-2-2H2',
  video:     'm16 13 5.223 3.482a.5.5 0 0 0 .777-.416V7.87a.5.5 0 0 0-.752-.432L16 10.5|M4 6h10a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2Z',
  notebook:  'M13.4 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-7.4|M2 6h4|M2 10h4|M2 14h4|M2 18h4|M21.378 5.626a1 1 0 1 0-3.004-3.004l-5.01 5.012a2 2 0 0 0-.506.854l-.837 2.87a.5.5 0 0 0 .62.62l2.87-.837a2 2 0 0 0 .854-.506z',
  flag:      'M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z|M4 22v-7',
  copy:      'M10 8h10a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H10a2 2 0 0 1-2-2V10a2 2 0 0 1 2-2Z|M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2',
  square:    'M5 3h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z',
  bold:      'M6 12h9a4 4 0 0 1 0 8H7a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h7a4 4 0 0 1 0 8',
  italic:    'M19 4h-9|M14 20H5|M15 4 9 20',
  underline: 'M6 4v6a6 6 0 0 0 12 0V4|M4 20h16',
  list:      'M3 12h.01|M3 18h.01|M3 6h.01|M8 12h13|M8 18h13|M8 6h13',
  olist:     'M10 12h11|M10 18h11|M10 6h11|M4 10h2|M4 6h1v4|M6 18H4c0-1 2-2 2-3s-1-1.5-2-1',
  eraser:    'm7 21-4.3-4.3c-1-1-1-2.5 0-3.4l9.6-9.6c1-1 2.5-1 3.4 0l5.6 5.6c1 1 1 2.5 0 3.4L13 21|M22 21H7|m5 11 9 9',
  sparkles:  'M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z|M20 3v4|M22 5h-4|M4 17v2|M5 18H3',
  clip:      'm21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48',
  rotccw:    'M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8|M3 3v5h5',
  rotcw:     'M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8|M21 3v5h-5',
  cap:       'M21.42 10.922a1 1 0 0 0-.019-1.838L12.83 5.18a2 2 0 0 0-1.66 0L2.6 9.08a1 1 0 0 0 0 1.832l8.57 3.908a2 2 0 0 0 1.66 0z|M22 10v6|M6 12.5V16a6 3 0 0 0 12 0v-3.5',
  skip:      'M5 4l10 8-10 8V4z|M19 5v14',
  okcircle:  'M22 11.08V12a10 10 0 1 1-5.93-9.14|M22 4 12 14.01l-3-3',
  // chevrons
  right:     'M9 18l6-6-6-6',
  dleft:     'M11.5 17l-5-5 5-5|M18 17l-5-5 5-5',
  dright:    'M12.5 17l5-5-5-5|M6 17l5-5-5-5',
  speaker:   'M11 5 6 9H3v6h3l5 4V5Z|M15.5 8.5a5 5 0 0 1 0 7|M18.5 5.5a9 9 0 0 1 0 13',
  left:      'M15 18l-6-6 6-6',
  up:        'M18 15l-6-6-6 6',
  down:      'M6 9l6 6 6-6',
  // more emblems (lucide 1.9.0, ISC licence, Copyright (c) Lucide Contributors): the 24-grid, one stroke
  'gamepad-2': 'M6 11L10 11|M8 9L8 13|M15 12L15.01 12|M18 10L18.01 10',
  'joystick': 'M6 15v-2|M12 15V9|M9 6a3 3 0 1 0 6 0a3 3 0 1 0 -6 0Z',
  'dices': 'M4 10h8a2 2 0 0 1 2 2v8a2 2 0 0 1 -2 2h-8a2 2 0 0 1 -2 -2v-8a2 2 0 0 1 2 -2Z|M6 18h.01|M10 14h.01|M15 6h.01|M18 9h.01',
  'dice-5': 'M5 3h14a2 2 0 0 1 2 2v14a2 2 0 0 1 -2 2h-14a2 2 0 0 1 -2 -2v-14a2 2 0 0 1 2 -2Z|M16 8h.01|M8 8h.01|M8 16h.01|M16 16h.01|M12 12h.01',
  'puzzle': '',
  'trophy': 'M10 14.66v1.626a2 2 0 0 1-.976 1.696A5 5 0 0 0 7 21.978|M14 14.66v1.626a2 2 0 0 0 .976 1.696A5 5 0 0 1 17 21.978|M18 9h1.5a1 1 0 0 0 0-5H18|M4 22h16|M6 9a6 6 0 0 0 12 0V3a1 1 0 0 0-1-1H7a1 1 0 0 0-1 1z|M6 9H4.5a1 1 0 0 1 0-5H6',
  'medal': 'M11 12 5.12 2.2|m13 12 5.88-9.8|M8 7h8|M7 17a5 5 0 1 0 10 0a5 5 0 1 0 -10 0Z|M12 18v-2h-.5',
  'crown': 'M5 21h14',
  'swords': 'M14.5 L17.5 L3 L6 L3 L3 L6 L3 L17.5 L14.5|M13 19L19 13|M16 16L20 20|M19 21L21 19|M14.5 L6.5 L18 L3 L21 L3 L21 L6 L17.5 L9.5|M5 14L9 18|M7 17L4 20|M3 19L5 21',
  'target': 'M2 12a10 10 0 1 0 20 0a10 10 0 1 0 -20 0Z|M6 12a6 6 0 1 0 12 0a6 6 0 1 0 -12 0Z|M10 12a2 2 0 1 0 4 0a2 2 0 1 0 -4 0Z',
  'spade': 'M12 18v4',
  'club': 'M12 17.66L12 22',
  'diamond': '',
  'book-open': 'M12 7v14',
  'graduation-cap': 'M22 10v6|M6 12.5V16a6 3 0 0 0 12 0v-3.5',
  'pencil': 'm15 5 4 4',
  'ruler': 'm14.5 12.5 2-2|m11.5 9.5 2-2|m8.5 6.5 2-2|m17.5 15.5 2-2',
  'calculator': 'M6 2h12a2 2 0 0 1 2 2v16a2 2 0 0 1 -2 2h-12a2 2 0 0 1 -2 -2v-16a2 2 0 0 1 2 -2Z|M8 6L16 6|M16 14L16 18|M16 10h.01|M12 10h.01|M8 10h.01|M12 14h.01|M8 14h.01|M12 18h.01|M8 18h.01',
  'languages': 'm5 8 6 6|m4 14 6-6 2-3|M2 5h12|M7 2h1|m22 22-5-10-5 10|M14 18h6',
  'brain': 'M12 18V5|M15 13a4.17 4.17 0 0 1-3-4 4.17 4.17 0 0 1-3 4|M17.598 6.5A3 3 0 1 0 12 5a3 3 0 1 0-5.598 1.5|M17.997 5.125a4 4 0 0 1 2.526 5.77|M18 18a4 4 0 0 0 2-7.464|M19.967 17.483A4 4 0 1 1 12 18a4 4 0 1 1-7.967-.517|M6 18a4 4 0 0 1-2-7.464|M6.003 5.125a4 4 0 0 0-2.526 5.77',
  'lightbulb': 'M9 18h6|M10 22h4',
  'library': 'm16 6 4 14|M12 6v14|M8 8v12|M4 4v16',
  'atom': 'M11 12a1 1 0 1 0 2 0a1 1 0 1 0 -2 0Z',
  'flask-conical': 'M6.453 15h11.094|M8.5 2h7',
  'microscope': 'M6 18h8|M3 22h18|M14 22a7 7 0 1 0 0-14h-1|M9 14h2|M9 12a2 2 0 0 1-2-2V6h6v4a2 2 0 0 1-2 2Z|M12 6V3a1 1 0 0 0-1-1H9a1 1 0 0 0-1 1v3',
  'telescope': 'm13.56 11.747 4.332-.924|m16 21-3.105-6.21|m6.158 8.633 1.114 4.456|m8 21 3.105-6.21|M10 13a2 2 0 1 0 4 0a2 2 0 1 0 -4 0Z',
  'activity': '',
  'stethoscope': 'M11 2v2|M5 2v2|M5 3H4a2 2 0 0 0-2 2v4a6 6 0 0 0 12 0V5a2 2 0 0 0-2-2h-1|M8 15a6 6 0 0 0 12 0v-3|M18 10a2 2 0 1 0 4 0a2 2 0 1 0 -4 0Z',
  'pill': 'm8.5 8.5 7 7',
  'dumbbell': 'm2.5 21.5 1.4-1.4|m20.1 3.9 1.4-1.4|m9.6 14.4 4.8-4.8',
  'apple': 'M12 6.528V3a1 1 0 0 1 1-1h0',
  'salad': 'M7 21h10|M12 21a9 9 0 0 0 9-9H3a9 9 0 0 0 9 9Z|m13 12 4-4|M10.9 7.25A3.99 3.99 0 0 0 4 10c0 .73.2 1.41.54 2',
  'baby': 'M10 16c.5.3 1.2.5 2 .5s1.5-.2 2-.5|M15 12h.01|M9 12h.01',
  'bike': 'M15 17.5a3.5 3.5 0 1 0 7 0a3.5 3.5 0 1 0 -7 0Z|M2 17.5a3.5 3.5 0 1 0 7 0a3.5 3.5 0 1 0 -7 0Z|M14 5a1 1 0 1 0 2 0a1 1 0 1 0 -2 0Z|M12 17.5V14l-3-3 4-3 2 3h2',
  'footprints': 'M16 17h4|M4 13h4',
  'hospital': 'M12 7v4|M14 21v-3a2 2 0 0 0-4 0v3|M14 9h-4|M18 21V5a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16',
  'syringe': 'm18 2 4 4|m17 7 3-3|M19 9 8.7 19.3c-1 1-2.5 1-3.4 0l-.6-.6c-1-1-1-2.5 0-3.4L15 5|m9 11 4 4|m5 19-3 3|m14 4 6 6',
  'wallet': 'M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4',
  'credit-card': 'M4 5h16a2 2 0 0 1 2 2v10a2 2 0 0 1 -2 2h-16a2 2 0 0 1 -2 -2v-10a2 2 0 0 1 2 -2Z|M2 10L22 10',
  'banknote': 'M4 6h16a2 2 0 0 1 2 2v8a2 2 0 0 1 -2 2h-16a2 2 0 0 1 -2 -2v-8a2 2 0 0 1 2 -2Z|M10 12a2 2 0 1 0 4 0a2 2 0 1 0 -4 0Z|M6 12h.01M18 12h.01',
  'piggy-bank': 'M16 10h.01|M2 8v1a2 2 0 0 0 2 2h1',
  'coins': 'M13.744 17.736a6 6 0 1 1-7.48-7.48|M15 6h1v4|m6.134 14.768.866-.5 2 3.464|M10 8a6 6 0 1 0 12 0a6 6 0 1 0 -12 0Z',
  'receipt': 'M12 17V7|M16 8h-6a2 2 0 0 0 0 4h4a2 2 0 0 1 0 4H8',
  'trending-up': 'M16 7h6v6|m22 7-8.5 8.5-5-5L2 17',
  'chart-pie': 'M21.21 15.89A10 10 0 1 1 8 2.83',
  'chart-column': 'M3 3v16a2 2 0 0 0 2 2h16|M18 17V9|M13 17V5|M8 17v-3',
  'landmark': 'M10 18v-7|M14 18v-7|M18 18v-7|M3 22h18|M6 18v-7',
  'badge-percent': 'm15 9-6 6|M9 9h.01|M15 15h.01',
  'shopping-cart': 'M7 21a1 1 0 1 0 2 0a1 1 0 1 0 -2 0Z|M18 21a1 1 0 1 0 2 0a1 1 0 1 0 -2 0Z',
  'shopping-bag': 'M16 10a4 4 0 0 1-8 0|M3.103 6.034h17.794',
  'store': 'M15 21v-5a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v5|M4 10.95V19a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8.05',
  'gift': 'M12 7v14|M20 11v8a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-8|M4 7h16a1 1 0 0 1 1 1v2a1 1 0 0 1 -1 1h-16a1 1 0 0 1 -1 -1v-2a1 1 0 0 1 1 -1Z',
  'tag': 'M7 7.5a0.5 0.5 0 1 0 1 0a0.5 0.5 0 1 0 -1 0Z',
  'ticket': 'M13 5v2|M13 17v2|M13 11v2',
  'package': 'M12 22V12|M3.29 L7 L12 L12 L20.71 L7|m7.5 4.27 9 5.15',
  'truck': 'M14 18V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v11a1 1 0 0 0 1 1h2|M15 18H9|M15 18a2 2 0 1 0 4 0a2 2 0 1 0 -4 0Z|M5 18a2 2 0 1 0 4 0a2 2 0 1 0 -4 0Z',
  'map': 'M15 5.764v15|M9 3.236v15',
  'map-pin': 'M9 10a3 3 0 1 0 6 0a3 3 0 1 0 -6 0Z',
  'compass': 'M2 12a10 10 0 1 0 20 0a10 10 0 1 0 -20 0Z',
  'plane': '',
  'train-front': 'M8 3.1V7a4 4 0 0 0 8 0V3.1|m9 15-1-1|m15 15 1-1|M9 19c-2.8 0-5-2.2-5-5v-4a8 8 0 0 1 16 0v4c0 2.8-2.2 5-5 5Z|m8 19-2 3|m16 19 2 3',
  'bus': 'M8 6v6|M15 6v6|M2 12h19.6|M5 18a2 2 0 1 0 4 0a2 2 0 1 0 -4 0Z|M9 18h5|M14 18a2 2 0 1 0 4 0a2 2 0 1 0 -4 0Z',
  'car': 'M5 17a2 2 0 1 0 4 0a2 2 0 1 0 -4 0Z|M9 17h6|M15 17a2 2 0 1 0 4 0a2 2 0 1 0 -4 0Z',
  'ship': 'M12 10.189V14|M12 2v3|M19 13V7a2 2 0 0 0-2-2H7a2 2 0 0 0-2 2v6',
  'rocket': 'M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5|M9 12H4s.55-3.03 2-4c1.62-1.08 5 .05 5 .05',
  'tent': 'M3.5 21 14 3|M20.5 21 10 3|M15.5 21 12 15l-3.5 6|M2 21h20',
  'mountain': 'm8 3 4 8 5-5 5 15H2L8 3z',
  'tree-palm': 'M13 8c0-2.76-2.46-5-5.5-5S2 5.24 2 8h2l1-1 1 1h4|M11 15.5c.5 2.5-.17 4.5-1 6.5h4c2-5.5-.5-12-1-14',
  'hotel': 'M10 22v-6.57|M12 11h.01|M12 7h.01|M14 15.43V22|M15 16a5 5 0 0 0-6 0|M16 11h.01|M16 7h.01|M8 11h.01|M8 7h.01|M6 2h12a2 2 0 0 1 2 2v16a2 2 0 0 1 -2 2h-12a2 2 0 0 1 -2 -2v-16a2 2 0 0 1 2 -2Z',
  'luggage': 'M8 18V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v14|M10 20h4|M14 20a2 2 0 1 0 4 0a2 2 0 1 0 -4 0Z|M6 20a2 2 0 1 0 4 0a2 2 0 1 0 -4 0Z',
  'house': 'M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8',
  'lamp': 'M12 12v6',
  'sofa': 'M20 9V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v3|M4 18v2|M20 18v2|M12 4v9',
  'bed': 'M2 4v16|M2 8h18a2 2 0 0 1 2 2v10|M2 17h20|M6 8v9',
  'utensils': 'M3 2v7c0 1.1.9 2 2 2h4a2 2 0 0 0 2-2V2|M7 2v20|M21 15V2a5 5 0 0 0-5 5v6c0 1.1.9 2 2 2h3Zm0 0v7',
  'chef-hat': 'M6 17h12',
  'coffee': 'M10 2v2|M14 2v2|M6 2v2',
  'cake': 'M20 21v-8a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8|M4 16s.5-1 2-1 2.5 2 4 2 2.5-2 4-2 2.5 2 4 2 2-1 2-1|M2 21h20|M7 8v3|M12 8v3|M17 8v3|M7 4h.01|M12 4h.01|M17 4h.01',
  'pizza': 'm12 14-1 1|m13.75 18.25-1.25 1.42|M17.775 5.654a15.68 15.68 0 0 0-12.121 12.12|M18.8 9.3a1 1 0 0 0 2.1 7.7',
  'soup': 'M12 21a9 9 0 0 0 9-9H3a9 9 0 0 0 9 9Z|M7 21h10|M19.5 12 22 6',
  'music': 'M9 18V5l12-2v13|M3 18a3 3 0 1 0 6 0a3 3 0 1 0 -6 0Z|M15 16a3 3 0 1 0 6 0a3 3 0 1 0 -6 0Z',
  'headphones': '',
  'radio': 'M16.247 7.761a6 6 0 0 1 0 8.478|M19.075 4.933a10 10 0 0 1 0 14.134|M4.925 19.067a10 10 0 0 1 0-14.134|M7.753 16.239a6 6 0 0 1 0-8.478|M10 12a2 2 0 1 0 4 0a2 2 0 1 0 -4 0Z',
  'tv': 'm17 2-5 5-5-5|M4 7h16a2 2 0 0 1 2 2v11a2 2 0 0 1 -2 2h-16a2 2 0 0 1 -2 -2v-11a2 2 0 0 1 2 -2Z',
  'camera': 'M9 13a3 3 0 1 0 6 0a3 3 0 1 0 -6 0Z',
  'palette': 'M13 6.5a0.5 0.5 0 1 0 1 0a0.5 0.5 0 1 0 -1 0Z|M17 10.5a0.5 0.5 0 1 0 1 0a0.5 0.5 0 1 0 -1 0Z|M6 12.5a0.5 0.5 0 1 0 1 0a0.5 0.5 0 1 0 -1 0Z|M8 7.5a0.5 0.5 0 1 0 1 0a0.5 0.5 0 1 0 -1 0Z',
  'brush': 'm11 10 3 3|M9.969 17.031 21.378 5.624a1 1 0 0 0-3.002-3.002L6.967 14.031',
  'clapperboard': 'm12.296 3.464 3.02 3.956|M3 11h18v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z|m6.18 5.276 3.1 3.899',
  'podcast': 'M16.85 18.58a9 9 0 1 0-9.7 0|M8 14a5 5 0 1 1 8 0|M11 11a1 1 0 1 0 2 0a1 1 0 1 0 -2 0Z',
  'newspaper': 'M15 18h-5|M18 14h-8|M11 6h6a1 1 0 0 1 1 1v2a1 1 0 0 1 -1 1h-6a1 1 0 0 1 -1 -1v-2a1 1 0 0 1 1 -1Z',
  'briefcase': 'M16 20V4a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16|M4 6h16a2 2 0 0 1 2 2v10a2 2 0 0 1 -2 2h-16a2 2 0 0 1 -2 -2v-10a2 2 0 0 1 2 -2Z',
  'building-2': 'M10 12h4|M10 8h4|M14 21v-3a2 2 0 0 0-4 0v3|M6 21V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v16',
  'calendar': 'M8 2v4|M16 2v4|M5 4h14a2 2 0 0 1 2 2v14a2 2 0 0 1 -2 2h-14a2 2 0 0 1 -2 -2v-14a2 2 0 0 1 2 -2Z|M3 10h18',
  'clipboard-list': 'M9 2h6a1 1 0 0 1 1 1v2a1 1 0 0 1 -1 1h-6a1 1 0 0 1 -1 -1v-2a1 1 0 0 1 1 -1Z|M12 11h4|M12 16h4|M8 11h.01|M8 16h.01',
  'file-text': 'M14 2v5a1 1 0 0 0 1 1h5|M10 9H8|M16 13H8|M16 17H8',
  'inbox': 'M22 L12 L16 L12 L14 L15 L10 L15 L8 L12 L2 L12',
  'phone': '',
  'printer': 'M6 9V3a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v6|M7 14h10a1 1 0 0 1 1 1v6a1 1 0 0 1 -1 1h-10a1 1 0 0 1 -1 -1v-6a1 1 0 0 1 1 -1Z',
  'scale': 'M12 3v18|m19 8 3 8a5 5 0 0 1-6 0zV7|M3 7h1a17 17 0 0 0 8-2 17 17 0 0 0 8 2h1|m5 8 3 8a5 5 0 0 1-6 0zV7|M7 21h10',
  'gavel': 'm14 13-8.381 8.38a1 1 0 0 1-3.001-3l8.384-8.381|m16 16 6-6|m21.5 10.5-8-8|m8 8 6-6|m8.5 7.5 8 8',
  'hammer': 'm15 12-9.373 9.373a1 1 0 0 1-3.001-3L12 9|m18 15 4-4',
  'wrench': '',
  'smartphone': 'M7 2h10a2 2 0 0 1 2 2v16a2 2 0 0 1 -2 2h-10a2 2 0 0 1 -2 -2v-16a2 2 0 0 1 2 -2Z|M12 18h.01',
  'laptop': 'M20.054 15.987H3.946',
  'monitor': 'M4 3h16a2 2 0 0 1 2 2v10a2 2 0 0 1 -2 2h-16a2 2 0 0 1 -2 -2v-10a2 2 0 0 1 2 -2Z|M8 21L16 21|M12 17L12 21',
  'cpu': 'M12 20v2|M12 2v2|M17 20v2|M17 2v2|M2 12h2|M2 17h2|M2 7h2|M20 12h2|M20 17h2|M20 7h2|M7 20v2|M7 2v2|M6 4h12a2 2 0 0 1 2 2v12a2 2 0 0 1 -2 2h-12a2 2 0 0 1 -2 -2v-12a2 2 0 0 1 2 -2Z|M9 8h6a1 1 0 0 1 1 1v6a1 1 0 0 1 -1 1h-6a1 1 0 0 1 -1 -1v-6a1 1 0 0 1 1 -1Z',
  'wifi': 'M12 20h.01|M2 8.82a15 15 0 0 1 20 0|M5 12.859a10 10 0 0 1 14 0|M8.5 16.429a5 5 0 0 1 7 0',
  'cloud': 'M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z',
  'database': 'M3 5a9 3 0 1 0 18 0a9 3 0 1 0 -18 0Z|M3 5V19A9 3 0 0 0 21 19V5|M3 12A9 3 0 0 0 21 12',
  'qr-code': 'M4 3h3a1 1 0 0 1 1 1v3a1 1 0 0 1 -1 1h-3a1 1 0 0 1 -1 -1v-3a1 1 0 0 1 1 -1Z|M17 3h3a1 1 0 0 1 1 1v3a1 1 0 0 1 -1 1h-3a1 1 0 0 1 -1 -1v-3a1 1 0 0 1 1 -1Z|M4 16h3a1 1 0 0 1 1 1v3a1 1 0 0 1 -1 1h-3a1 1 0 0 1 -1 -1v-3a1 1 0 0 1 1 -1Z|M21 16h-3a2 2 0 0 0-2 2v3|M21 21v.01|M12 7v3a2 2 0 0 1-2 2H7|M3 12h.01|M12 3h.01|M12 16v.01|M16 12h1|M21 12v.01|M12 21v-1',
  'bot': 'M12 8V4H8|M6 8h12a2 2 0 0 1 2 2v8a2 2 0 0 1 -2 2h-12a2 2 0 0 1 -2 -2v-8a2 2 0 0 1 2 -2Z|M2 14h2|M20 14h2|M15 13v2|M9 13v2',
  'code-xml': 'm18 16 4-4-4-4|m6 8-4 4 4 4|m14.5 4-5 16',
  'terminal': 'M12 19h8|m4 17 6-6-6-6',
  'server': 'M4 2h16a2 2 0 0 1 2 2v4a2 2 0 0 1 -2 2h-16a2 2 0 0 1 -2 -2v-4a2 2 0 0 1 2 -2Z|M4 14h16a2 2 0 0 1 2 2v4a2 2 0 0 1 -2 2h-16a2 2 0 0 1 -2 -2v-4a2 2 0 0 1 2 -2Z|M6 6L6.01 6|M6 18L6.01 18',
  'star': '',
  'leaf': 'M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12',
  'flower-2': 'M10 8a2 2 0 1 0 4 0a2 2 0 1 0 -4 0Z|M12 10v12|M12 22c4.2 0 7-1.667 7-5-4.2 0-7 1.667-7 5Z|M12 22c-4.2 0-7-1.667-7-5 4.2 0 7 1.667 7 5Z',
  'tree-pine': 'M12 22v-3',
  'sprout': 'M4 9a5 5 0 0 1 8 4 5 5 0 0 1-8-4|M5 21h14',
  'flame': '',
  'droplet': '',
  'umbrella': 'M12 13v7a2 2 0 0 0 4 0|M12 2v2',
  'snowflake': 'm10 20-1.25-2.5L6 18|M10 4 8.75 6.5 6 6|m14 20 1.25-2.5L18 18|m14 4 1.25 2.5L18 6|m17 21-3-6h-4|m17 3-3 6 1.5 3|M2 12h6.5L10 9|m20 10-1.5 2 1.5 2|M22 12h-6.5L14 15|m4 10 1.5 2L4 14|m7 21 3-6-1.5-3|m7 3 3 6h4',
  'dog': 'M11.25 16.25h1.5L12 17z|M16 14v.5|M8 14v.5',
  'cat': 'M8 14v.5|M16 14v.5|M11.25 16.25h1.5L12 17l-.75-.75Z',
  'bird': 'M16 7h.01|M3.4 18H12a8 8 0 0 0 8-8V7a4 4 0 0 0-7.28-2.3L2 20|m20 7 2 .5-2 .5|M10 18v3|M14 17.75V21|M7 18a6 6 0 0 0 3.84-10.61',
  'fish': 'M18 12v.5|M16 17.93a9.77 9.77 0 0 1 0-11.86',
  'paw-print': 'M9 4a2 2 0 1 0 4 0a2 2 0 1 0 -4 0Z|M16 8a2 2 0 1 0 4 0a2 2 0 1 0 -4 0Z|M18 16a2 2 0 1 0 4 0a2 2 0 1 0 -4 0Z',
  'smile': 'M2 12a10 10 0 1 0 20 0a10 10 0 1 0 -20 0Z|M8 14s1.5 2 4 2 4-2 4-2|M9 9L9.01 9|M15 9L15.01 9',
  'hand-heart': 'M11 14h2a2 2 0 0 0 0-4h-3c-.6 0-1.1.2-1.4.6L3 16|m2 15 6 6',
  'handshake': 'm11 17 2 2a1 1 0 1 0 3-3|m21 3 1 11h-2|M3 3 2 14l6.5 6.5a1 1 0 1 0 3-3|M3 4h8',
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

/** 2026-10-04: the Chip Chat mark, as the studio draws it - a speech bubble holding a chip (the question goes in, a chip
 *  answers), indigo to teal, with a spark. Its own gradient id per size so two on a page never clash. */
let ccg = 0;
export function chipChatGlyph(size = 24) {
  const id = `ccg${ccg += 1}`;
  return `<svg viewBox="0 0 32 32" width="${size}" height="${size}" aria-hidden="true" data-chip-chat-glyph>
    <defs><linearGradient id="${id}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#4f46e5"/><stop offset="1" stop-color="#0f8b7d"/></linearGradient></defs>
    <path d="M6 4h20a4 4 0 0 1 4 4v12a4 4 0 0 1-4 4H14l-6 5v-5H6a4 4 0 0 1-4-4V8a4 4 0 0 1 4-4z" fill="url(#${id})"/>
    <rect x="11" y="9" width="10" height="10" rx="2" fill="#fff"/><rect x="13.5" y="11.5" width="5" height="5" rx="1" fill="url(#${id})"/>
    <g stroke="#fff" stroke-width="1.4" stroke-linecap="round"><path d="M13.5 7.2v1.3M16 7.2v1.3M18.5 7.2v1.3M13.5 19.5v1.3M16 19.5v1.3M18.5 19.5v1.3"/>
      <path d="M9.2 11.5h1.3M9.2 14h1.3M9.2 16.5h1.3M21.5 11.5h1.3M21.5 14h1.3M21.5 16.5h1.3"/></g>
    <circle cx="26.5" cy="7.5" r="1.6" fill="#fde68a"/></svg>`;
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
