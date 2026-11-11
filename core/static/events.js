// One push stream per signed-in page (core/events.py, chip events.settings; owner 2026-11-08 "server tells, page never
// asks on a timer"). The shell starts it after bootstrap; any module listens with onEvent(topic, fn). The browser's own
// EventSource reconnects (the server's `retry:`) and sends Last-Event-ID, so missed news arrives without a fetch.
const BASE = new URL('..', import.meta.url).href.replace(/\/$/, '');   // same as ui.js BASE (no import: ui.js imports this)

let src = null;
let topics = {};
const subs = {};                     // logical topic -> Set(fn)
const wired = new Set();             // logical topics with a listener on the current stream

function wire(name) {
  if (!src || wired.has(name) || !topics[name]) return;
  wired.add(name);
  src.addEventListener(topics[name], (e) => {
    let data = {};
    try { data = JSON.parse(e.data); } catch { return; }
    (subs[name] || []).forEach((fn) => { try { fn(data); } catch { /* one listener never stops the others */ } });
  });
}

/** Open the stream (bootstrap `events` = {url, topics}); null closes it (signed out). */
export function startEvents(k) {
  if (!k) { if (src) src.close(); src = null; wired.clear(); return; }
  if (src) return;
  topics = k.topics || {};
  src = new EventSource(`${BASE}${k.url}`, { withCredentials: true });
  Object.keys(subs).forEach(wire);
}

/** Listen for one topic; returns the function that stops listening. */
export function onEvent(name, fn) {
  (subs[name] = subs[name] || new Set()).add(fn);
  wire(name);
  return () => subs[name].delete(fn);
}
