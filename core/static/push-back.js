// The Connect window's last page (core/issues.py api_push_back): tells the Issues tab how it went (same site, so a
// BroadcastChannel reaches it whatever the Allow page did to window.opener), drops the one-time code from the address
// bar, and closes itself when Connect worked. A file, not an inline script: the portal's script policy allows no inline code.
const d = document.body.dataset;
history.replaceState(null, '', location.pathname);
try { new BroadcastChannel('push-connect').postMessage({ push_connect: d.ok === '1', message: d.message }); } catch { /* an old browser: the page still says how it went */ }
if (d.ok === '1') setTimeout(() => window.close(), 900);
