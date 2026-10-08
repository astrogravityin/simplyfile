// Screen guide on every portal: the Guide me button in the top bar, and the tour it opens.
// The drawing, the spotlight, the voice and the pictures are the portable kit (guide-kit.js + guide-kit.css,
// the same file the Guide Me Builder exports to other sites). This adapter only fetches the screen's tour
// (core/guide.py, chip guide.<screen> - or one imported in How to Use Configure) and hands the kit the
// portal's own words (chips ui.guide + ui.shell), so every word stays editable in Ops & chips.
import { api, esc, t, loadWords, keep, kept, toast } from './ui.js';
import { icon } from './icons.js';
import { openTour, closeTour, art, WORD_KEYS } from './guide-kit.js';

export { art };
export const closeGuide = closeTour;

const w = (k, v) => t('guide', k, v);

/** Guide me, for the top bar. `seen` = this person has taken this screen's tour (the button stops glowing). */
export function guideButton(screen, settings = {}) {
  const glow = settings.pulse_until_seen !== false && !kept(`guide.seen.${screen}`);
  return `<button type="button" class="chipbtn gd-btn ${glow ? 'gd-glow' : ''}" data-guide="${esc(screen)}"
    data-tip="${esc(w('guide_tip'))}" aria-label="${esc(w('guide_tip'))}">${icon('spark', 14)} ${esc(w('guide_me'))}</button>`;
}

export function wireGuide(root, product = '') {
  root.querySelectorAll('[data-guide]').forEach((b) => {
    b.onclick = () => { b.classList.remove('gd-glow'); openGuide(b.dataset.guide, product); };
  });
}

/** The portal's words for the card, as raw templates ({n} stays for the kit to fill). */
function words() {
  const raw = { n: '{n}', total: '{total}' };
  const out = {};
  for (const k of WORD_KEYS) {
    const v = k.startsWith('rd_') ? t('shell', k) : w(k, raw);
    out[k] = v;
  }
  return out;
}

export async function openGuide(screen, product = '') {
  closeTour();
  await loadWords('guide', 'shell').catch(() => {});
  let tour;
  try { tour = await api(`/api/core/guide/${encodeURIComponent(screen)}`); } catch (e) {
    toast(w('failed', { why: e.message }), 'bad');
    return;
  }
  keep(`guide.seen.${screen}`, '1');
  openTour(tour, { words: words(), product, screen });
}
