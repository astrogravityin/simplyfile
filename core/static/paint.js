// Paint only when the HTML changed (2026-11-18, week class 47 - CodyFy G-83: an open chat flickered because every pushed update
// rewrote it whole). A screen that redraws on the push stream (onEvent / followUrl / watchJob) writes its HTML through this:
// the same HTML into the same untouched box is a no-op, so focus, scroll, an open <details> and a half-typed field survive.
// "Untouched" = its first node is still the one this call painted - a box someone else redrew (the router, another page) is
// always painted again. No imports: a node self-test loads it alone (core/codeguards.py).
const SEEN = new WeakMap();   // box -> { html, first }

/** Write `html` into `el` unless it already shows exactly that. Returns true when it painted. */
export function paintIfChanged(el, html) {
  if (!el) return false;
  const last = SEEN.get(el);
  if (last && last.html === html && el.firstChild && last.first === el.firstChild) return false;
  el.innerHTML = html;
  SEEN.set(el, { html, first: el.firstChild });
  return true;
}
