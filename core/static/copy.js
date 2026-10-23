// THE copy-to-clipboard of every portal (2026-10-19 owner: "Copy with toast. Use common copy paste component/module").
// One source for the app (ui.js copyText, with the portal's toast) and for pages that stand alone - a published manual
// inlines this file (manuals.doc_html), so its Copy buttons work online, from a download and on a USB stick alike.
// Rich text goes with plain text: a copied example pasted into the request editor keeps its bullets.

/** A toast for pages without the portal's own (a manual): one line at the bottom, gone after a moment. */
function ownToast(text, tone) {
  let t = document.getElementById('copy-toast');
  if (!t) {
    t = document.createElement('div');
    t.id = 'copy-toast';
    t.setAttribute('role', 'status');
    t.style.cssText = 'position:fixed;left:50%;bottom:24px;transform:translateX(-50%);z-index:9999;padding:10px 16px;border-radius:10px;'
      + 'font:600 14px system-ui,Segoe UI,sans-serif;box-shadow:0 10px 30px rgba(15,23,42,.25);transition:opacity .2s;max-width:calc(100vw - 32px)';
    document.body.append(t);
  }
  t.textContent = text;
  t.style.background = tone === 'bad' ? '#b91c1c' : '#0f766e';
  t.style.color = '#fff';
  t.style.opacity = '1';
  clearTimeout(t.hideAt);
  t.hideAt = setTimeout(() => { t.style.opacity = '0'; }, 2200);
}

/** Copies `text` (and `html` when given, for editors that take rich text). `say(message, tone)` tells the person; words come
 *  from the caller (its words chip): { copied, failed }. Returns true when it reached the clipboard. */
export async function copyText(text, { html = '', say = ownToast, copied = '', failed = '' } = {}) {
  try {
    if (html && window.ClipboardItem && navigator.clipboard && navigator.clipboard.write) {
      await navigator.clipboard.write([new ClipboardItem({
        'text/html': new Blob([html], { type: 'text/html' }), 'text/plain': new Blob([text], { type: 'text/plain' }) })]);
    } else {
      await navigator.clipboard.writeText(text);
    }
  } catch {
    // no clipboard permission (an old browser, a file opened from disk): the classic way
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.cssText = 'position:fixed;top:-1000px;opacity:0';
    document.body.append(ta);
    ta.select();
    let ok = false;
    try { ok = document.execCommand('copy'); } catch { ok = false; }
    ta.remove();
    if (!ok) { if (failed) say(failed, 'bad'); return false; }
  }
  if (copied) say(copied, 'ok');
  return true;
}

/** Every `.copy-block` under `root` gets a Copy button that copies the block (without the button) as text and rich text. */
export function wireCopyBlocks(root, words = {}) {
  root.querySelectorAll('.copy-block').forEach((block) => {
    if (block.querySelector(':scope > .copy-btn')) return;
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'copy-btn';
    b.textContent = words.copy || 'Copy';
    b.setAttribute('aria-label', words.copy_label || b.textContent);
    b.onclick = () => {
      // the text as the page shows it (innerText keeps the line breaks only on the live block), less this button's word
      const shown = block.innerText;
      const text = shown.startsWith(b.textContent) ? shown.slice(b.textContent.length) : shown;
      const clone = block.cloneNode(true);
      clone.querySelectorAll('.copy-btn').forEach((x) => x.remove());
      copyText(text.replace(/\n{3,}/g, '\n\n').trim(), { html: clone.innerHTML, copied: words.copied, failed: words.failed });
    };
    block.prepend(b);
  });
}
