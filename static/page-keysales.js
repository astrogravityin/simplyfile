// Keys for sale — the seller's desk. Who reaches it is chip keysales.may_sell (a list of roles: the
// Sales Person role is one row in it, the owner is always there). Until one key is on sale here,
// nobody on the portal sees a Buy a key menu at all.
//
// Billing only: approving hands over prepaid credit and raises a bill. No money moves through here.
import { api, esc, say, toast, busy, money, pageHead, modal, confirmDialog, t, loadWords, listBox, when } from './app.js';
import { icon, emptyState } from './icons.js';

const w = (k, v) => t('keysales', k, v);
const sw = (k, v) => t('shell', k, v);      // the portal's own words: Cancel, Delete, Close - one word everywhere

export async function keySalesPage(host) {
  await loadWords('keysales');
  const d = await api('/api/keysales');

  host.innerHTML = pageHead(w('title'), w('lede'),
    `<button type="button" class="primary" id="s-new">${icon('plus')} ${w('new_offer')}</button>`)

    + `<div id="s-msg"></div>
    <div class="note" id="ks-terms"><div><p class="small" style="margin:0">${esc(d.billing_only)}</p></div></div>

    <section class="card" id="ks-offers"><h2>${icon('key', 17)} ${w('offers_card')}</h2>
      ${d.offers.length ? d.offers.map((o) => `<div class="row tight small lent-row">
          <b>${esc(o.title)}</b>
          <span class="tag ${o.markup_pct ? 'warn' : 'ok'}">${esc(o.terms)}</span>
          ${o.active ? '' : `<span class="tag">${w('offer_off_tag')}</span>`}
          ${o.note ? `<span class="muted">${esc(o.note)}</span>` : ''}
          <span class="spacer"></span>
          <button type="button" class="small ghost" data-edit="${esc(o.id)}">${icon('edit', 12)} ${w('offer_edit')}</button>
          <button type="button" class="small ghost danger" data-drop="${esc(o.id)}" data-title="${esc(o.title)}">${icon('trash', 12)} ${w('offer_delete')}</button>
        </div>`).join('')
      : emptyState('key', w('no_offers_title'), w('no_offers_body'))}
    </section>

    <section class="card" id="ks-waiting"><h2>${icon('clock', 17)} ${w('waiting_card')}</h2>
      ${d.waiting_n ? '<div id="ks-waiting-list"></div>' : emptyState('clock', w('no_waiting_title'), w('no_waiting_body'))}
    </section>

    ${d.answered_n ? `<section class="card" id="ks-answered"><h2>${icon('check', 17)} ${w('answered_card')}</h2>
      <div id="ks-answered-list"></div></section>` : ''}`;

  const msg = host.querySelector('#s-msg');
  const again = () => keySalesPage(host);

  const offerDialog = (o) => modal(o ? o.title : w('new_offer'), `
    <div class="field"><label for="so-key">${w('offer_key')}</label>
      <select id="so-key">${d.keys.map((k) => `<option value="${esc(k.id)}" ${o && o.key_id === k.id ? 'selected' : ''}>
        ${esc(k.name)} · ${esc(k.provider)} · ${esc(k.hint)}</option>`).join('')}</select></div>
    <div class="field"><label for="so-title">${w('offer_title')}</label>
      <input id="so-title" maxlength="${d.title_max}" value="${esc((o || {}).title || '')}"/></div>
    <div class="field"><label for="so-markup">${w('offer_markup')}</label>
      <input id="so-markup" inputmode="decimal" value="${esc(String((o || {}).markup_pct || 0))}" style="max-width:120px"/></div>
    <div class="field"><label for="so-note">${w('offer_note')}</label>
      <input id="so-note" maxlength="${d.note_max}" value="${esc((o || {}).note || '')}"/></div>
    <label class="check small"><input type="checkbox" id="so-active" ${!o || o.active ? 'checked' : ''}/><span>${w('offer_active')}</span></label>
    <div id="so-msg" style="margin-top:10px"></div>`,
    { footer: `<button type="button" data-cancel>${sw('cancel')}</button>
        <button type="button" class="primary" id="so-go">${icon('save')} ${w('offer_save')}</button>`,
      onOpen: (body, close) => {
        const card = body.closest('.modal');
        card.querySelector('[data-cancel]').onclick = close;
        card.querySelector('#so-go').onclick = (e) => busy(e.currentTarget, async () => {
          try {
            const r = await api('/api/keysales/offers', { method: 'PUT', body: {
              id: (o || {}).id || '', key_id: body.querySelector('#so-key').value,
              title: body.querySelector('#so-title').value,
              markup_pct: body.querySelector('#so-markup').value,
              note: body.querySelector('#so-note').value,
              active: body.querySelector('#so-active').checked } });
            close(); toast(r.message, 'ok', 9); again();
          } catch (err) { say(body.querySelector('#so-msg'), 'bad', esc(err.message)); }
        });
      } });

  host.querySelector('#s-new').onclick = () => offerDialog(null);
  host.querySelectorAll('[data-edit]').forEach((b) => {
    b.onclick = () => offerDialog(d.offers.find((x) => x.id === b.dataset.edit));
  });
  host.querySelectorAll('[data-drop]').forEach((b) => {
    b.onclick = () => confirmDialog(w('offer_delete_title', { title: b.dataset.title }), w('offer_delete_body'), async () => {
      try { const r = await api(`/api/keysales/offers/${encodeURIComponent(b.dataset.drop)}`, { method: 'DELETE' }); toast(r.message, 'ok'); again(); }
      catch (err) { say(msg, 'bad', esc(err.message)); }
    }, w('offer_delete'), { tone: 'danger' });
  });

  const decide = (id, approve, title, bodyText, cta, tone) => confirmDialog(title, bodyText, async () => {
    try {
      const r = await api(`/api/keysales/orders/${encodeURIComponent(id)}`, { method: 'POST', body: { approve } });
      toast(r.message, 'ok', 9); again();
    } catch (err) { say(msg, 'bad', esc(err.message)); }
  }, cta, tone ? { tone } : {});
  // 2026-09-28 owner "tens of thousands": requests are lists sales_waiting / sales_answered - one page at a time
  const waiting = host.querySelector('#ks-waiting-list');
  if (waiting) listBox(waiting, { list: 'sales_waiting', row: waitingRow, wire: (rows) => wireDecide(rows),
    wrap: (html) => `<div class="scroll"><table><thead><tr>
        <th>${w('col_when')}</th><th>${w('col_buyer')}</th><th>${w('col_offer')}</th>
        <th>${w('col_amount')}</th><th></th></tr></thead><tbody>${html}</tbody></table></div>` });
  const answered = host.querySelector('#ks-answered-list');
  if (answered) listBox(answered, { list: 'sales_answered', row: answeredRow,
    wrap: (html) => `<div class="scroll"><table><thead><tr>
        <th>${w('col_when')}</th><th>${w('col_buyer')}</th><th>${w('col_offer')}</th>
        <th>${w('col_amount')}</th><th>${w('col_state')}</th><th>${w('col_credit')}</th></tr></thead><tbody>${html}</tbody></table></div>` });
  const wireDecide = (root) => {
  root.querySelectorAll('[data-yes]').forEach((b) => {
    b.onclick = () => decide(b.dataset.yes, true,
      w('approve_title', { buyer: b.dataset.buyer, amount: b.dataset.amount }),
      w('approve_body', { amount: b.dataset.amount }), w('approve'), 'brand');
  });
  root.querySelectorAll('[data-no]').forEach((b) => {
    b.onclick = () => decide(b.dataset.no, false,
      w('reject_title', { buyer: b.dataset.buyer }), w('reject_body'), w('reject'), 'danger');
  });
  };
}

function waitingRow(o) {
  return `<tr>
          <td class="small muted">${esc(when(o.requested_at))}</td>
          <td>${esc(o.buyer_name)}<div class="small muted">${esc(o.buyer_email)}</div></td>
          <td>${esc(o.title)}${o.note ? `<div class="small muted">${esc(o.note)}</div>` : ''}</td>
          <td><b>${money(o.amount_usd)}</b>${o.markup_pct ? `<div class="small muted">+${esc(String(o.markup_pct))}%</div>` : ''}</td>
          <td class="row tight">
            <button type="button" class="small primary" data-yes="${esc(o.id)}" data-buyer="${esc(o.buyer_name)}"
              data-amount="${esc(money(o.amount_usd))}">${w('approve')}</button>
            <button type="button" class="small ghost danger" data-no="${esc(o.id)}" data-buyer="${esc(o.buyer_name)}">${w('reject')}</button>
          </td></tr>`;
}

function answeredRow(o) {
  return `<tr>
          <td class="small muted">${esc(when(o.decided_at || o.withdrawn_at))}</td>
          <td class="small">${esc(o.buyer_name)}</td>
          <td class="small">${esc(o.title)}</td>
          <td>${money(o.amount_usd)}</td>
          <td><span class="tag ${o.state === 'approved' ? 'ok' : 'bad'}">${esc(o.state)}</span>
            ${o.reason ? `<div class="small muted">${esc(o.reason)}</div>` : ''}</td>
          <td class="small">${o.credit && o.credit.line ? esc(o.credit.line) : '—'}</td>
        </tr>`;
}
