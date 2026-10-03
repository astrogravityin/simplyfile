// Buy a key — credit on somebody else's AI key, prepaid. The menu does not exist until a seller has
// put a key up for sale (catalog `hide_when_denied` + core.access.register_available), so this page
// is never reached empty by accident.
//
// Nothing here takes money. Asking creates a request; the seller answers it on Keys for sale, and a
// yes hands over the credit and raises a bill the two of you settle between yourselves.
import { api, esc, say, toast, busy, money, pageHead, modal, confirmDialog, t, loadWords, listBox, when } from './app.js';
import { icon, emptyState } from './icons.js';

const w = (k, v) => t('buykey', k, v);
const sw = (k, v) => t('shell', k, v);      // the portal's own words: Cancel, Delete, Close - one word everywhere

export async function buyKeyPage(host) {
  await loadWords('buykey');
  const d = await api('/api/buykey');

  host.innerHTML = pageHead(w('title'), w('lede'))
    + `<div id="b-msg"></div>

    <div class="note warn" id="bk-terms">${icon('alert')}<div>
      <p class="small" style="margin:0">${esc(d.buy_note)}</p>
      <p class="small" style="margin:6px 0 0"><b>${esc(w('disclaimer_label'))}</b> ${esc(d.disclaimer)}</p>
      <p class="small muted" style="margin:6px 0 0">${esc(d.billing_only)}</p></div></div>

    ${d.low_credit.length ? `<section class="card" id="bk-low"><h2>${icon('alert', 17)} ${w('low_card')}</h2>
      ${d.low_credit.map((x) => `<div class="row tight small lent-row">
        <span class="tag ${x.stopped ? 'bad' : 'warn'}">${x.stopped ? w('low_stopped') : w('low_warn')}</span>
        <b>${esc(x.label)}</b><span class="muted">${esc(x.owner_name)}</span>
        <span>${esc(x.message)}</span>
        <span class="spacer"></span>
        ${x.offer_id ? `<button type="button" class="small primary" data-buy="${esc(x.offer_id)}"
          data-title="${esc(x.label)}" data-seller="${esc(x.owner_name)}">${icon('plus', 12)} ${w('buy_more')}</button>` : ''}
      </div>`).join('')}</section>` : ''}

    <section class="card" id="bk-sale"><h2>${icon('money', 17)} ${w('on_sale')}</h2>
      ${d.offers_n ? '<div id="bk-offers"></div>' : emptyState('money', w('no_offers_title'), w('no_offers_body'))}
    </section>

    <section class="card" id="bk-orders"><h2>${icon('clock', 17)} ${w('my_orders')}</h2>
      ${d.orders_n ? '<div id="bk-orders-list"></div>'
      : emptyState('clock', w('no_orders_title'), w('no_orders_body'))}
    </section>`;

  // 2026-10-01 (Phase 3): the offers are list buy_offers - one searched page at a time, each card drawn here
  const offerCard = (o) => `<div class="pv-row">
        <div class="pv-head"><b>${esc(o.title)}</b>
          <span class="tag">${esc(o.seller_line)}</span>
          <span class="tag ${o.markup_pct ? 'warn' : 'ok'}">${esc(o.terms)}</span></div>
        ${o.note ? `<p class="small muted">${esc(o.note)}</p>` : ''}
        ${ratesList(o.rates, false)}
        <div class="row tight" style="margin-top:8px">
          <button type="button" class="small primary" data-buy="${esc(o.id)}"
            data-title="${esc(o.title)}" data-seller="${esc(o.seller_name)}">${icon('plus', 12)} ${w('ask_cta')}</button></div>
      </div>`;
  const msg = host.querySelector('#b-msg');
  const again = () => buyKeyPage(host);

  const seenOffers = {};
  const wireBuy = (root) => root.querySelectorAll('[data-buy]').forEach((b) => {
    b.onclick = async () => {
      if (!seenOffers[b.dataset.buy]) {                  // a low-credit "buy more" names an offer not on this page
        try { (await api(`/api/lists/buy_offers?${new URLSearchParams({ pick: b.dataset.buy })}`)).rows.forEach((o) => { seenOffers[o.id] = o; }); } catch { /* the ask still opens */ }
      }
      ask(b, seenOffers[b.dataset.buy] || {});
    };
  });
  const ask = (b, offer) => modal(w('ask_title', { seller: b.dataset.seller, title: b.dataset.title }), `
      <div class="field"><label>${w('ask_for')}</label>
        <div class="row tight" id="bk-packs">${d.packs.map((p, i) => `
          <button type="button" class="small ${i === 0 ? 'primary' : 'ghost'}" data-pack="${esc(String(p))}">${money(p)}</button>`).join('')}</div></div>
      ${d.custom_ok ? `<div class="field"><label for="bk-amount">${w('custom')}</label>
        <input id="bk-amount" inputmode="decimal" value="${esc(String(d.packs[0]))}" style="max-width:140px"/></div>` : ''}
      <div class="field"><label for="bk-note">${w('note_label')}</label><input id="bk-note" autocomplete="off"/></div>
      <div class="note warn">${icon('alert')}<div>${ratesList(offer.rates, true)}</div></div>
      <div id="bk-msg" style="margin-top:10px"></div>`,
      { footer: `<button type="button" data-cancel>${sw('cancel')}</button>
          <button type="button" class="primary" id="bk-go">${icon('check')} ${w('ask_cta')}</button>`,
        onOpen: (body, close) => {
          const card = body.closest('.modal');
          const amount = body.querySelector('#bk-amount');
          card.querySelector('[data-cancel]').onclick = close;
          body.querySelectorAll('[data-pack]').forEach((p) => {
            p.onclick = () => {
              body.querySelectorAll('[data-pack]').forEach((x) => x.classList.replace('primary', 'ghost'));
              p.classList.replace('ghost', 'primary');
              if (amount) amount.value = p.dataset.pack;
            };
          });
          card.querySelector('#bk-go').onclick = (e) => busy(e.currentTarget, async () => {
            const picked = body.querySelector('[data-pack].primary');
            try {
              const r = await api('/api/buykey/orders', { method: 'POST', body: {
                offer_id: b.dataset.buy,
                amount_usd: amount ? amount.value : (picked || {}).dataset.pack,
                note: body.querySelector('#bk-note').value } });
              close(); toast(r.message, 'ok', 9); again();
            } catch (err) { say(body.querySelector('#bk-msg'), 'bad', esc(err.message)); }
          });
        } });
  wireBuy(host);
  const offersHost = host.querySelector('#bk-offers');
  if (offersHost) listBox(offersHost, { list: 'buy_offers', wrap: (html) => `<div class="pv-grid">${html}</div>`,
    row: (o) => { seenOffers[o.id] = o; return offerCard(o); }, wire: (rows) => wireBuy(rows) });

  // 2026-09-28 owner "tens of thousands": my requests are list buy_orders - one page at a time
  const orders = host.querySelector('#bk-orders-list');
  if (orders) listBox(orders, { list: 'buy_orders', row: orderRow,
    wrap: (html) => `<div class="scroll"><table><thead><tr>
        <th>${w('col_when')}</th><th>${w('col_offer')}</th><th>${w('col_amount')}</th>
        <th>${w('col_state')}</th><th>${w('col_credit')}</th><th></th></tr></thead><tbody>${html}</tbody></table></div>`,
    wire: (rows) => rows.querySelectorAll('[data-withdraw]').forEach((b) => {
      b.onclick = () => confirmDialog(w('withdraw_title'), w('withdraw_body'), async () => {
        try { const r = await api(`/api/buykey/orders/${encodeURIComponent(b.dataset.withdraw)}`, { method: 'DELETE' }); toast(r.message, 'ok'); again(); }
        catch (err) { say(msg, 'bad', esc(err.message)); }
      }, w('withdraw'), { tone: 'danger' });
    }) });
}

function orderRow(o) {
  return `<tr>
          <td class="small muted">${esc(when(o.requested_at))}</td>
          <td>${esc(o.title)}<div class="small muted">${esc(o.seller_name)}</div></td>
          <td>${money(o.amount_usd)}</td>
          <td><span class="tag ${o.state === 'approved' ? 'ok' : o.state === 'rejected' ? 'bad' : ''}">${w(`state_${o.state}`)}</span>
            ${o.reason ? `<div class="small muted">${esc(w('reason_label'))}: ${esc(o.reason)}</div>` : ''}</td>
          <td class="small">${o.credit && o.credit.line ? esc(o.credit.line) : '—'}</td>
          <td>${o.state === 'requested'
            ? `<button type="button" class="small ghost danger" data-withdraw="${esc(o.id)}">${w('withdraw')}</button>` : ''}</td>
        </tr>`;
}

/** The quote a buyer gets BEFORE they ask — their price, and what moves it. The offer cards leave the
 *  disclaimer out because the page says it once at the top; the dialog where the money is actually
 *  committed always carries it, however many times that repeats it. */
function ratesList(rates, withDisclaimer = true) {
  if (!rates || !(rates.lines || []).length) return '';
  return `<ul class="small" style="margin:6px 0">${rates.lines.map((x) => `<li>${esc(x)}</li>`).join('')}</ul>
    <p class="small muted" style="margin:0">${esc(rates.markup_line)}</p>
    ${withDisclaimer ? `<p class="small" style="margin:4px 0 0"><b>${esc(w('disclaimer_label'))}</b> ${esc(rates.disclaimer)}</p>` : ''}`;
}
