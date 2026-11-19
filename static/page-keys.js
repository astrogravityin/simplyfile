// Account & key — YOUR keys, YOUR balance, YOUR runs, and (2026-09-23) the keys you LEND and the ones
// you were lent. A key is a way to spend money, so a borrowed one is never silently yours: it is
// tagged with its owner, it cannot become your default or be deleted by you, every run on it lands on
// the owner's usage list, and either side can end the loan in one press. That is also why every
// screen in this portal needs a sign-in.
import { api, BASE, esc, listBox, when, say, toast, busy, money, budget, toLocal, state, pageHead, modal, passwordDialog, confirmDialog,
         refreshMe, secretField, wireSecrets, choiceField, choiceValue, wireChoices, t, loadWords, ps, offAttr, setCurrency } from './app.js';
import { icon, emptyState } from './icons.js';

// Every word on this screen is chip ui.keys (core/words.py) - none is written here.
const w = (k, v) => t('keys', k, v);
const sw = (k, v) => t('shell', k, v);      // the portal's own words: Cancel, Delete, Close - one word everywhere

const GUIDE = () => `${BASE}/help/gemini-key`;

// What in this portal uses a key: chip ai.features' labels (sent with the edition at sign-in), or the "needs no key" line.
const usesLine = () => {
  const feats = (state.edition && state.edition.ai_features) || [];
  return feats.length ? w('uses_key', { features: feats.map((f) => `<b>${esc(f)}</b>`).join(', ') }) : w('uses_none');
};

export async function keysPage(host) {
  await loadWords('keys');
  const d = await api('/api/keys');
  const funds = d.funds.gemini;
  const ready = !!d.set.gemini_api_key;
  const spentPct = funds.loaded_usd ? Math.min(100, (funds.spent_usd / funds.loaded_usd) * 100) : 0;

  host.innerHTML = pageHead(w('title'), w('lede', { uses: usesLine() }),
    `<a href="${GUIDE()}" target="_blank" rel="noopener"><button type="button">${icon('help')} ${w('how_to_get')}</button></a>`)

    + `<div id="k-msg"></div>

    <section class="card keycard ${ready ? 'ready' : ''}">
      <div class="keytop">
        <span class="orb">${icon(ready ? 'check' : 'key', 20)}</span>
        <div class="txt">
          <b>${w(ready ? 'key_connected' : 'no_key')}</b>
          <span>${ready
            ? w('ready_line', { model: esc(d.values.gemini_model), ends: esc(d.values.gemini_api_key) })
            : w('no_key_line')}</span>
        </div>
        <div class="acts">
          ${ready ? `<button type="button" id="k-test">${icon('spark')} ${w('test_it')}</button>` : ''}
          <button type="button" class="primary" id="k-edit">${icon(ready ? 'edit' : 'plus')} ${w(ready ? 'replace_key' : 'add_key')}</button>
        </div>
      </div>
      <div id="k-test-out"></div>
    </section>

    <div class="split">
      <section class="card"><h2>${icon('money', 17)} ${w('budget_card')}</h2>
        <p class="muted small">${w('budget_note', { guide: GUIDE() })}</p>
        <div class="meters">
          <div class="meter"><span class="lbl">${w('budgeted')}</span><b>${funds.loaded_usd ? budget(funds.loaded_usd) : '—'}</b></div>
          <div class="meter"><span class="lbl">${w('spent_here')}</span><b>${money(funds.spent_usd)}</b></div>
          <div class="meter ${funds.low ? 'low' : ''}"><span class="lbl">${w('left')}</span>
            <b>${budget(funds.left_usd)}</b></div>
        </div>
        ${funds.loaded_usd ? `<div class="bar" style="margin:12px 0 4px"><i style="width:${spentPct}%"></i></div>` : ''}
        ${funds.low ? `<div class="note warn">${icon('alert')}<div>${w('budget_low')}</div></div>` : ''}
        <div class="field" style="margin-top:12px"><label for="k-currency">${w('currency_label')}</label>
          <select id="k-currency">${d.currency.choices.map((x) => `<option value="${esc(x.code)}" ${x.code === d.currency.code ? 'selected' : ''}>${esc(x.code)} ${esc(x.symbol)} · ${esc(x.label)}</option>`).join('')}</select>
          <p class="small muted" style="margin:6px 0 0">${w('currency_note')}
            ${d.currency.rates_at ? w('rates_at', { at: esc(d.currency.rates_at) }) : w('rates_fixed')}
            ${d.currency.rates_error ? w('rates_failed', { why: esc(d.currency.rates_error) }) : ''}</p></div>
        <div class="field" style="margin-top:12px"><label for="k-loaded">${w('budget_label', { code: esc(d.currency.code) })}</label>
          <input id="k-loaded" value="${funds.loaded_usd ? toLocal(funds.loaded_usd) : ''}" inputmode="decimal" placeholder="10"/></div>
        <div class="row" style="margin-top:12px"><button id="k-funds" type="button">${icon('save')} ${w('save_budget')}</button></div>
      </section>

      <section class="card"><h2>${icon('user', 17)} ${w('account_card')}</h2>
        <dl class="facts">
          <div><dt>${w('name')}</dt><dd>${esc(state.user.name || '—')}</dd></div>
          <div><dt>${w('email')}</dt><dd>${esc(state.user.email)}</dd></div>
          <div><dt>${w('role')}</dt><dd><span class="tag ${state.user.role === 'owner' ? 'brand' : ''}">${esc(state.user.role)}</span></dd></div>
        </dl>
        <div class="row" style="margin-top:14px">
          <button type="button" id="k-pass">${icon('shield')} ${w('change_password')}</button>
        </div>
        <p class="small muted" style="margin-top:12px">${w('privacy_note')}</p>
      </section>
    </div>

    ${poolCard(d, ps('keys').pool_provider)}

    ${providersCard(d)}

    ${state.user.role === 'owner' ? `<section class="card" id="k-models"><h2>${icon('chip', 17)} ${w('mc_card')}</h2>
      <p class="muted small">${w('mc_note')}</p>
      <button type="button" class="primary" id="k-mcheck">${icon('search', 14)} ${w('mc_check')}</button></section>` : ''}

    ${walletCard(d)}

    ${sharedCard(d)}

    ${reportCard(d)}

    ${billsCard(d)}

    <section class="card" id="k-usage"><h2>${icon('clock', 17)} ${w('usage_card')}</h2>
      <p class="muted small">${w('usage_note')}</p>
      <div class="row tight" style="margin-bottom:10px">
        <input id="k-usage-q" placeholder="${esc(w('usage_search_ph'))}" style="max-width:280px"/></div>
      <div id="k-usage-table">${usageTable(d.usage)}</div>
    </section>`;

  const msg = host.querySelector('#k-msg');
  host.querySelector('#k-edit').onclick = () => keyDialog(() => keysPage(host));
  host.querySelector('#k-pass').onclick = passwordDialog;
  const wadd = host.querySelector('#kw-add');
  if (wadd) wadd.onclick = (e) => busy(e.currentTarget, async () => {
    try {
      const r = await api('/api/wallet/add', { method: 'POST', body: { email: host.querySelector('#kw-email').value,
        amount: host.querySelector('#kw-amount').value, note: host.querySelector('#kw-note').value } });   // the owner's currency
      toast(r.message, 'ok', 8); keysPage(host);
    } catch (err) { say(msg, 'bad', esc(err.message)); }
  });
  const wcap = host.querySelector('#kw-capgo');
  if (wcap) wcap.onclick = (e) => busy(e.currentTarget, async () => {
    try {
      const r = await api('/api/wallet/cap', { method: 'POST', body: { email: host.querySelector('#kw-email').value, cap: host.querySelector('#kw-cap').value } });
      toast(r.message, 'ok', 8); keysPage(host);
    } catch (err) { say(msg, 'bad', esc(err.message)); }
  });
  const mcheck = host.querySelector('#k-mcheck');
  if (mcheck) mcheck.onclick = (e) => busy(e.currentTarget, () => modelCheck(host));

  const test = host.querySelector('#k-test');
  if (test) test.onclick = (e) => busy(e.currentTarget, () => runTest(host.querySelector('#k-test-out')));

  host.querySelector('#k-funds').onclick = (e) => busy(e.currentTarget, async () => {
    try {
      await api('/api/funds', { method: 'PUT', body: {
        provider: ps('keys').pool_provider, loaded: host.querySelector('#k-loaded').value } });   // in the person's currency
      toast(w('budget_saved'), 'ok');
      keysPage(host);
    } catch (err) { say(msg, 'bad', esc(err.message)); }
  });
  host.querySelector('#k-currency').onchange = async (e) => {
    try {
      const r = await api('/api/currency', { method: 'PUT', body: { code: e.target.value } });
      state.currency = r.currency;
      setCurrency(r.currency);
      toast(w('currency_saved', { code: r.currency.code }), 'ok');
      keysPage(host);
    } catch (err) { say(msg, 'bad', esc(err.message)); }
  };
  wireProviders(host, d, msg);
  wirePool(host, msg);
  wireSharing(host, d, msg);
  const again = () => keysPage(host);
  const lentHost = host.querySelector('#ks-lent');
  if (lentHost) listBox(lentHost, { list: 'keys_lent', row: lentRow, wire: (rows, r, reload) => wireLent(rows, d, msg, () => { reload(); again(); }) });
  host.querySelectorAll('[data-lent-key]').forEach((b) => {
    b.onclick = () => modal(w('lent_title'), '<div id="kl-box"></div>', { wide: true, onOpen: (body) => {
      listBox(body.querySelector('#kl-box'), { list: 'keys_lent', args: { key_id: b.dataset.lentKey }, row: lentRow,
        wire: (rows, r, reload) => wireLent(rows, d, msg, reload) });
    }, onClose: again });
  });
  const heldHost = host.querySelector('#ks-held');
  if (heldHost) listBox(heldHost, { list: 'keys_held', row: (g) => heldRow(g, (d.shares || {}).label_max || 60),
    wire: (rows) => wireHeld(rows, msg, again) });
  host.querySelectorAll('[data-bills]').forEach((el) => listBox(el, { list: el.dataset.bills, row: (x) => billRow(el.dataset.bills, x),
    wire: (rows, r, reload) => wireBills(rows, msg, () => { reload(); again(); }) }));
  const walletsHost = host.querySelector('#kw-list');
  if (walletsHost) listBox(walletsHost, { list: 'wallets', empty: w('wallets_none'),
    row: (x) => `<div class="small lent-row">${esc(w('wallet_row', { email: x.email, left: money(x.left_usd), today: money(x.today_usd) }))}</div>` });
  wireUsage(host, msg);
  wireReport(host, msg);
}

/** The lender's report. Not loaded until asked for — it walks the whole receipt roll. */
function wireReport(host, msg) {
  const box = host.querySelector('#k-report-table');
  if (!box) return;
  const group = host.querySelector('#k-report-group');
  const q = host.querySelector('#k-report-q');
  const load = async (page) => {
    try {
      const got = await api(`/api/keys/report?group=${encodeURIComponent(group.value)}&q=${encodeURIComponent(q.value)}&page=${page}`);
      box.innerHTML = reportTable(got);
      box.querySelectorAll('[data-report-page]').forEach((b) => { b.onclick = () => load(Number(b.dataset.reportPage)); });
    } catch (err) { say(msg, 'bad', esc(err.message)); }
  };
  host.querySelector('#k-report-go').onclick = (e) => busy(e.currentTarget, () => load(1));
  group.onchange = () => { if (box.innerHTML) load(1); };
}

// --- lend a key, take it back, give it back, send the bill --------------------------------------------------------

function wireSharing(host, d, msg) {
  const again = () => keysPage(host);
  const termsFields = (v, code) => `
    <div class="field"><label for="ks-markup">${w('terms_markup')}</label>
      <input id="ks-markup" inputmode="decimal" value="${esc(String(v.markup || 0))}" style="max-width:120px"/>
      <span class="small muted">${w('terms_markup_hint')}</span></div>
    <div class="row tight">
      <div class="field"><label for="ks-day">${esc(w('terms_cap_day', { code }))}</label>
        <input id="ks-day" inputmode="decimal" value="${esc(String(v.day || 0))}" style="max-width:110px"/></div>
      <div class="field"><label for="ks-week">${esc(w('terms_cap_week', { code }))}</label>
        <input id="ks-week" inputmode="decimal" value="${esc(String(v.week || 0))}" style="max-width:110px"/></div>
      <div class="field"><label for="ks-month">${esc(w('terms_cap_month', { code }))}</label>
        <input id="ks-month" inputmode="decimal" value="${esc(String(v.month || 0))}" style="max-width:110px"/></div></div>
    <p class="small muted">${w('terms_cap_hint')}</p>`;
  const termsBody = (body) => ({
    markup_pct: body.querySelector('#ks-markup').value,
    cap_day_usd: body.querySelector('#ks-day').value,
    cap_week_usd: body.querySelector('#ks-week').value,
    cap_month_usd: body.querySelector('#ks-month').value,
  });
  // The owner sees, live, exactly what the other person will be quoted at the mark-up being typed.
  const wireRatePreview = (body) => {
    const box = body.querySelector('#ks-rates');
    const markup = body.querySelector('#ks-markup');
    if (!box || !markup) return;
    let timer;
    const draw = async () => {
      try {
        const r = await api(`/api/keys/rates?markup_pct=${encodeURIComponent(markup.value || 0)}`);
        box.innerHTML = ratesBlock(r, w('rates_preview'));
      } catch { box.innerHTML = ''; }
    };
    markup.oninput = () => { clearTimeout(timer); timer = setTimeout(draw, 350); };
    draw();
  };
  const code = (d.currency || {}).code || 'USD';
  host.querySelectorAll('[data-share]').forEach((b) => {
    b.onclick = () => modal(w('share_title'), `
      <p class="small muted">${w('share_note')}</p>
      <div class="field"><label for="ks-email">${esc(b.dataset.name)}</label>
        <input id="ks-email" type="email" autocomplete="off" placeholder="${esc(w('share_email_ph'))}"/></div>
      ${termsFields({}, code)}
      <div id="ks-rates"></div>
      <div id="ks-msg" style="margin-top:10px"></div>`,
      { footer: `<button type="button" data-cancel>${sw('cancel')}</button>
          <button type="button" class="primary" id="ks-go">${icon('check')} ${w('share_cta')}</button>`,
        onOpen: (body, close) => {
          const card = body.closest('.modal');
          card.querySelector('[data-cancel]').onclick = close;
          wireRatePreview(body);
          card.querySelector('#ks-go').onclick = (e) => busy(e.currentTarget, async () => {
            try {
              const r = await api(`/api/keys/pool/${encodeURIComponent(b.dataset.share)}/share`,
                { method: 'POST', body: { email: body.querySelector('#ks-email').value, ...termsBody(body) } });
              close(); toast(r.message, 'ok', 9); again();
            } catch (err) { say(body.querySelector('#ks-msg'), 'bad', esc(err.message)); }
          });
        } });
  });
  wireHeld(host, msg, again);
}

// a borrowed key's own name and Give back - on the pool rows and on each page of list keys_held
function wireHeld(host, msg, again) {
  // The borrower's own name for a borrowed key, edited where the borrowed keys live.
  host.querySelectorAll('[data-grant-label]').forEach((inp) => {
    inp.onchange = async () => {
      try {
        const r = await api(`/api/keys/pool/${encodeURIComponent(inp.dataset.key)}/name`, { method: 'PUT', body: { name: inp.value } });
        toast(r.message || w('pool_renamed'), 'ok'); again();
      } catch (err) { say(msg, 'bad', esc(err.message)); }
    };
  });
  host.querySelectorAll('[data-return]').forEach((b) => {
    b.onclick = () => confirmDialog(w('give_back_title', { name: b.dataset.name }), w('give_back_body'), async () => {
      try { const r = await api(`/api/keys/shares/${encodeURIComponent(b.dataset.return)}`, { method: 'DELETE' }); toast(r.message, 'ok'); again(); }
      catch (err) { say(msg, 'bad', esc(err.message)); }
    }, w('give_back'), { tone: 'danger' });
  });
}

// the buttons on a bill row (push a bill, settle one) - wired per listBox page
function wireBills(root, msg, reload) {
  root.querySelectorAll('[data-bill-key]').forEach((b) => {
    b.onclick = () => confirmDialog(
      w('bill_push_title', { name: b.dataset.name, amount: b.dataset.amount }),
      w('bill_push_body', { runs: b.dataset.runs, label: esc(b.dataset.label) }), async () => {
        try {
          const r = await api('/api/keys/bills', { method: 'POST', body: { key_id: b.dataset.billKey, holder_id: b.dataset.billHolder } });
          toast(r.message, 'ok', 9); reload();
        } catch (err) { say(msg, 'bad', esc(err.message)); }
      }, w('bill_push'), { tone: 'brand' });
  });
  root.querySelectorAll('[data-settle]').forEach((b) => {
    b.onclick = () => confirmDialog(w('bill_settle_title', { amount: b.dataset.amount, owner: b.dataset.owner }),
      w('bill_settle_body'), async () => {
        try { const r = await api(`/api/keys/bills/${encodeURIComponent(b.dataset.settle)}/settle`, { method: 'POST', body: {} }); toast(r.message, 'ok'); reload(); }
        catch (err) { say(msg, 'bad', esc(err.message)); }
      }, w('bill_settle'), { tone: 'brand' });
  });
}

/** One page of usage at a time: the roll holds thousands of runs and the screen asks for 25. */
function wireUsage(host, msg) {
  const box = host.querySelector('#k-usage-table');
  const q = host.querySelector('#k-usage-q');
  if (!box || !q) return;
  const load = async (page) => {
    try {
      const got = await api(`/api/keys/usage?q=${encodeURIComponent(q.value)}&page=${page}`);
      box.innerHTML = usageTable(got);
      wireUsage(host, msg);
    } catch (err) { say(msg, 'bad', esc(err.message)); }
  };
  let timer;
  q.oninput = () => { clearTimeout(timer); timer = setTimeout(() => load(1), 300); };
  box.querySelectorAll('[data-usage-page]').forEach((b) => { b.onclick = () => load(Number(b.dataset.usagePage)); });
}

// --- Shared keys: its own section, both directions (2026-09-23) ---------------------------------------------------
// A lent key spends the OWNER's balance on the OWNER's terms: a mark-up on what each run really costs
// and a rolling cap per day / week / month. The borrower sees only the marked-up price, renames the
// key for themselves, and is quoted roughly what a minute of video will cost them before they start.

function windowBar(use) {
  const names = ps('keys').windows || [];
  return `<span class="small muted">${names.filter((n) => use[n]).map((n) => {
    const u = use[n];
    return `${w(`window_${n}`)} ${u.cap
      ? esc(w('window_used', { spent: money(u.spent), cap: money(u.cap) }))
      : w('window_uncapped')}`;
  }).join(' · ')}</span>`;
}

// 2026-09-28 managed credits: the person's ONE balance on the portal's keys; the owner adds credit and sets limits
function walletCard(d) {
  const v = d.wallet || {};
  const mine = v.added_usd ? `<section class="card" id="k-wallet"><h2>${icon('key', 17)} ${w('wallet_card')}</h2>
      <p class="muted small">${w('wallet_note')}</p>
      <div class="row tight"><b style="font-size:20px">${esc(w('wallet_left', { left: money(v.left_usd) }))}</b>
        <span class="muted small">${esc(v.cap_usd ? w('wallet_today', { today: money(v.today_usd), cap: money(v.cap_usd) }) : w('wallet_today_nocap', { today: money(v.today_usd) }))}</span></div>
      <p class="small muted">${esc(w('wallet_added_total', { added: money(v.added_usd), refunded: money(v.refunded_usd) }))}</p></section>` : '';
  if (!d.wallets_owner) return mine;
  return mine + `<section class="card" id="k-wallets"><h2>${icon('users', 17)} ${w('wallets_card')}</h2>
      <p class="muted small">${w('wallets_note')}</p>
      <div class="row tight" style="flex-wrap:wrap">
        <div class="field"><label for="kw-email">${w('wallet_email')}</label><input id="kw-email" type="email" autocomplete="off"/></div>
        <div class="field"><label for="kw-amount">${w('wallet_amount')}</label><input id="kw-amount" inputmode="decimal" style="max-width:110px"/></div>
        <div class="field"><label for="kw-note">${w('wallet_note_f')}</label><input id="kw-note"/></div>
        <button type="button" class="primary" id="kw-add">${icon('plus')} ${w('wallet_add')}</button>
        <div class="field"><label for="kw-cap">${w('wallet_cap')}</label><input id="kw-cap" inputmode="decimal" style="max-width:100px"/></div>
        <button type="button" id="kw-capgo">${w('wallet_cap_go')}</button></div>
      <div id="kw-list"></div></section>`;
}

// 2026-09-28 owner "it goes beyond 10 we are gone": the people who hold my keys are list keys_lent - one searched page
// at a time (listBox); these are the buttons on each of its rows.
function wireLent(root, d, msg, reload) {
  const code = (d.currency || {}).code || 'USD';
  root.querySelectorAll('[data-terms]').forEach((b) => {
    b.onclick = () => modal(w('terms_title', { name: b.dataset.name }), `
      ${termsFields({ markup: b.dataset.markup, day: b.dataset.day, week: b.dataset.week, month: b.dataset.month }, code)}
      <div id="ks-rates"></div>
      <div id="ks-msg" style="margin-top:10px"></div>`,
      { footer: `<button type="button" data-cancel>${sw('cancel')}</button>
          <button type="button" class="primary" id="ks-go">${icon('save')} ${w('terms_save')}</button>`,
        onOpen: (body, close) => {
          const card = body.closest('.modal');
          card.querySelector('[data-cancel]').onclick = close;
          wireRatePreview(body);
          card.querySelector('#ks-go').onclick = (e) => busy(e.currentTarget, async () => {
            try {
              const r = await api(`/api/keys/shares/${encodeURIComponent(b.dataset.terms)}/terms`,
                { method: 'PUT', body: termsBody(body) });
              close(); toast(r.message || w('terms_saved'), 'ok', 8); reload();
            } catch (err) { say(body.querySelector('#ks-msg'), 'bad', esc(err.message)); }
          });
        } });
  });
  root.querySelectorAll('[data-revoke]').forEach((b) => {
    b.onclick = () => confirmDialog(w('take_back_title', { name: b.dataset.name }), w('take_back_body'), async () => {
      try { const r = await api(`/api/keys/shares/${encodeURIComponent(b.dataset.revoke)}`, { method: 'DELETE' }); toast(r.message, 'ok'); reload(); }
      catch (err) { say(msg, 'bad', esc(err.message)); }
    }, w('take_back'), { tone: 'danger' });
  });
}

function lentRow(g) {
  return `<div class="row tight small lent-row">
        <b>${esc(g.holder_name)}</b><span class="muted">${esc(g.holder_email)}</span>
        <span class="tag">${esc(g.label_at_grant || '')}</span>
        <span class="tag">${esc(g.terms)}</span>
        ${g.use ? windowBar(g.use) : ''}
        <span class="small muted">${esc(w('grant_since', { at: String(g.granted_at || '').slice(0, 10) }))}</span>
        <span class="spacer"></span>
        <button type="button" class="small ghost" data-terms="${esc(g.id)}" data-name="${esc(g.holder_name)}"
          data-markup="${esc(String(g.markup_pct || 0))}" data-day="${esc(String(g.cap_day_usd || 0))}"
          data-week="${esc(String(g.cap_week_usd || 0))}" data-month="${esc(String(g.cap_month_usd || 0))}">${icon('edit', 12)} ${w('terms_edit')}</button>
        <button type="button" class="small ghost danger" data-revoke="${esc(g.id)}" data-name="${esc(g.holder_name)}">${icon('trash', 12)} ${w('take_back')}</button>
      </div>`;
}

// 2026-09-28 the keys lent to me are list keys_held - a page at a time, each with its windows and my prices
function heldRow(g, labelMax) {
  return `<div class="lent-row" style="display:block">
        <div class="row tight small">
          <input data-grant-label="${esc(g.id)}" data-key="${esc(g.key_id)}" value="${esc(g.holder_label || '')}" maxlength="${labelMax}"
            placeholder="${esc(g.owner_name)}" title="${esc(w('borrowed_rename_hint'))}" style="max-width:220px;font-weight:600"/>
          <span class="muted">${esc(w('borrowed_owner', { owner: g.owner_name }))}</span>
          <span class="tag">${esc(g.terms)}</span>
          ${g.use ? windowBar(g.use) : ''}
          ${g.blocked_reason ? `<span class="tag bad" title="${esc(g.blocked_reason)}">${w('blocked_now')}</span>` : ''}
          ${!g.blocked_reason && g.low_reason ? `<span class="tag warn">${w('low_now')}</span>` : ''}
          <span class="spacer"></span>
          ${g.blocked_reason || g.low_reason ? `<a href="#/buykey"><button type="button" class="small">${icon('plus', 12)} ${w('buy_more')}</button></a>` : ''}
          <button type="button" class="small ghost danger" data-return="${esc(g.id)}" data-name="${esc(g.holder_label || g.owner_name)}">${icon('trash', 12)} ${w('give_back')}</button>
        </div>
        ${g.blocked_reason ? `<p class="small" style="color:var(--bad);margin:4px 0 0">${esc(g.blocked_reason)}</p>` : ''}
        ${!g.blocked_reason && g.low_reason ? `<p class="small" style="color:var(--warn);margin:4px 0 0">${esc(g.low_reason)}</p>` : ''}
        ${ratesBlock(g.rates, w('rates_title'))}
      </div>`;
}

function sharedCard(d) {
  const sh = d.shares || {};
  return `<section class="card"><h2>${icon('users', 17)} ${w('shared_card')}</h2>
    <p class="muted small">${w('shared_note')}</p>

    <h3 class="small">${w('shared_lent')}</h3>
    ${sh.lent_total ? '<div id="ks-lent"></div>' : `<p class="small muted">${w('shared_none_lent')}</p>`}

    <h3 class="small" style="margin-top:14px">${w('shared_held')}</h3>
    ${sh.held_n ? '<div id="ks-held"></div>' : `<p class="small muted">${w('shared_none_held')}</p>`}
  </section>`;
}

/** Never a bare number: the estimate always carries the sentence saying what moves it. */
function ratesBlock(rates, title) {
  if (!rates || !(rates.lines || []).length) return '';
  return `<div class="note" style="margin-top:8px"><div>
    <b class="small">${esc(title)}</b>
    <ul class="small" style="margin:6px 0">${rates.lines.map((x) => `<li>${esc(x)}</li>`).join('')}</ul>
    <p class="small muted" style="margin:0">${esc(rates.markup_line)}</p>
    <p class="small muted" style="margin:4px 0 0">${esc(rates.disclaimer)}</p></div></div>`;
}

// --- the lender's report: per key, per person, per sitting --------------------------------------------------------

function reportCard(d) {
  if (!(d.shares || {}).lent_total) return '';
  return `<section class="card" id="k-report"><h2>${icon('chart', 17) || icon('money', 17)} ${w('report_card')}</h2>
    <p class="muted small">${w('report_note')}</p>
    <div class="row tight" style="margin-bottom:10px">
      <select id="k-report-group" aria-label="${esc(w('report_group_label'))}">
        <option value="key">${w('report_group_key')}</option>
        <option value="person" selected>${w('report_group_person')}</option>
        <option value="session">${w('report_group_session')}</option></select>
      <input id="k-report-q" placeholder="${esc(w('report_search_ph'))}" style="max-width:240px"/>
      <button type="button" class="small" id="k-report-go">${w('report_open')}</button></div>
    <div id="k-report-table"></div></section>`;
}

function reportTable(page) {
  const rows = (page || {}).rows || [];
  if (!rows.length) return emptyState('money', w('no_report_title'), w('no_report_body'));
  const tot = page.totals || {};
  const bySession = page.group === 'session';
  return `<p class="small muted">${esc(w('report_totals', { runs: tot.runs, base: money(tot.base_usd), charged: money(tot.charged_usd) }))}</p>
    <div class="scroll"><table><thead><tr>
      <th>${w('col_key')}</th>${page.group === 'key' ? '' : `<th>${w('col_usedby')}</th>`}
      ${bySession ? `<th>${w('col_session')}</th>` : ''}
      <th>${w('col_terms')}</th><th>${w('col_runs')}</th><th>${w('col_duration')}</th>
      <th>${w('col_base')}</th><th>${w('markup_col')}</th><th>${w('col_charged')}</th>
      <th>${w('col_first')}</th><th>${w('col_last')}</th></tr></thead>
    <tbody>${rows.map((r) => `<tr>
      <td><b>${esc(r.key_label || '—')}</b></td>
      ${page.group === 'key' ? '' : `<td class="small">${esc(r.holder_name || '')}<div class="muted">${esc(r.holder_email || '')}</div></td>`}
      ${bySession ? `<td class="small muted"><code>${esc(r.session_label || '')}</code></td>` : ''}
      <td class="small">${esc(r.terms || '')}</td>
      <td>${esc(String(r.runs || 0))}</td>
      <td class="small">${r.seconds ? `${Math.round(r.seconds)}s` : '—'}</td>
      <td class="small muted">${money(r.base_usd)}</td>
      <td class="small">${r.markup_pct ? `+${esc(String(r.markup_pct))}%` : '—'}</td>
      <td><b>${money(r.charged_usd)}</b></td>
      <td class="small muted">${esc(String(r.first_at || '').slice(0, 10))}</td>
      <td class="small muted">${esc(String(r.last_at || '').slice(0, 10))}</td></tr>`).join('')}</tbody></table></div>
    <div class="row tight" style="margin-top:10px">
      <button type="button" class="small ghost" data-report-page="${page.page - 1}" ${offAttr(page.page <= 1 ? t('shell', 'off_first_page') : '')}>${w('prev')}</button>
      <span class="small muted">${esc(w('page_of', { page: page.page, pages: page.pages, total: page.total }))}</span>
      <button type="button" class="small ghost" data-report-page="${page.page + 1}" ${offAttr(page.page >= page.pages ? t('shell', 'off_last_page') : '')}>${w('next')}</button></div>`;
}

// --- key usage across the board (2026-09-23): every paid run, own key or borrowed ---------------------------------
// The lender sees WHAT it cost but only the beginning of what the borrower called it (chip
// keyshare.name_seen); the person who ran it sees it whole, so a bill can be checked against it.

function usageTable(page) {
  const rows = (page || {}).rows || [];
  if (!rows.length) return emptyState('videos', w('no_usage_title'), w('no_usage_body'));
  return `<div class="scroll"><table><thead><tr>
      <th>${w('col_date')}</th><th>${w('col_portal')}</th><th>${w('col_key')}</th><th>${w('col_whose')}</th>
      <th>${w('col_owner')}</th><th>${w('col_usedby')}</th><th>${w('col_activity')}</th>
      <th>${w('col_duration')}</th><th>${w('col_cost')}</th></tr></thead>
    <tbody>${rows.map((r) => `<tr>
      <td class="small muted">${esc(when(r.at))}</td>
      <td class="small">${esc(r.portal || '')}</td>
      <td class="small"><b>${esc(r.key_label || '—')}</b><div class="muted">${esc(r.provider || '')}${r.model ? ` · ${esc(r.model)}` : ''}</div></td>
      <td><span class="tag ${r.own ? '' : 'warn'}">${r.own ? w('own_tag') : w('shared_tag')}</span></td>
      <td class="small">${esc(r.owner_name || '')}</td>
      <td class="small">${esc(r.used_by || '')}</td>
      <td>${esc(r.activity || '')}${r.error ? `<div class="small" style="color:var(--bad)">${esc(r.error)}</div>` : ''}
        ${r.tokens_in ? `<div class="small muted">${w('tokens', { in: r.tokens_in.toLocaleString(), out: (r.tokens_out || 0).toLocaleString() })}</div>` : ''}</td>
      <td class="small">${r.seconds ? `${r.seconds}s` : '—'}</td>
      <td>${r.free ? `<span class="tag ok">${w('free')}</span>` : money(r.cost_usd)}</td></tr>`).join('')}</tbody></table></div>
    <div class="row tight" style="margin-top:10px">
      <button type="button" class="small ghost" data-usage-page="${page.page - 1}" ${offAttr(page.page <= 1 ? t('shell', 'off_first_page') : '')}>${w('prev')}</button>
      <span class="small muted">${esc(w('page_of', { page: page.page, pages: page.pages, total: page.total }))}</span>
      <button type="button" class="small ghost" data-usage-page="${page.page + 1}" ${offAttr(page.page >= page.pages ? t('shell', 'off_last_page') : '')}>${w('next')}</button></div>`;
}

// --- bills (2026-09-23): what people owe for spending on your key, and what you owe on theirs ----------------------

// 2026-09-28 owner "tens of thousands": bills are lists keys_owing / keys_bills_received / keys_bills_sent - one page each
const billLine = (x) => esc(w('bill_line', { runs: x.runs, amount: money(x.cost_usd),
  from_at: String(x.from_at || '').slice(0, 10) || '—', to_at: String(x.to_at || x.last_at || '').slice(0, 10) }));
function billRow(list, x) {
  if (list === 'keys_owing') return `<div class="row tight small lent-row">
        <b>${esc(x.holder_name)}</b><span class="muted">${esc(x.key_label)}</span><span>${billLine(x)}</span>
        <span class="spacer"></span>
        <button type="button" class="small" data-bill-key="${esc(x.key_id)}" data-bill-holder="${esc(x.user_id)}"
          data-name="${esc(x.holder_name)}" data-amount="${esc(money(x.cost_usd))}" data-runs="${esc(String(x.runs))}"
          data-label="${esc(x.key_label)}">${icon('send', 12)} ${w('bill_push')}</button></div>`;
  if (list === 'keys_bills_received') return `<div class="row tight small lent-row">
        <b>${esc(x.owner_name)}</b><span class="muted">${esc(x.key_label)}</span><span>${billLine(x)}</span>
        ${x.note ? `<span class="muted">${esc(x.note)}</span>` : ''}
        <span class="spacer"></span>
        ${x.settled_at ? `<span class="tag ok">${esc(w('bill_settled', { at: String(x.settled_at).slice(0, 10) }))}</span>`
          : `<button type="button" class="small" data-settle="${esc(x.id)}" data-amount="${esc(money(x.cost_usd))}"
               data-owner="${esc(x.owner_name)}">${w('bill_settle')}</button>`}</div>`;
  return `<div class="row tight small lent-row">
        <b>${esc(x.holder_name)}</b><span class="muted">${esc(x.key_label)}</span><span>${billLine(x)}</span>
        <span class="spacer"></span>
        <span class="tag ${x.settled_at ? 'ok' : 'warn'}">${x.settled_at ? esc(w('bill_settled', { at: String(x.settled_at).slice(0, 10) })) : w('bill_unsettled')}</span>
        </div>`;
}

function billsCard(d) {
  const b = d.bills || {};
  if (!b.owing_n && !b.sent_n && !b.received_n) {
    return `<section class="card"><h2>${icon('money', 17)} ${w('bills_card')}</h2>
      ${emptyState('money', w('no_bills_title'), w('no_bills_body'))}</section>`;
  }
  return `<section class="card"><h2>${icon('money', 17)} ${w('bills_card')}</h2>
    <p class="muted small">${w('bills_note')}</p>
    ${b.owing_n ? `<h3 class="small">${w('bill_owing')}</h3><div data-bills="keys_owing"></div>` : ''}
    ${b.received_n ? `<h3 class="small" style="margin-top:14px">${w('bills_received')}</h3><div data-bills="keys_bills_received"></div>` : ''}
    ${b.sent_n ? `<h3 class="small" style="margin-top:14px">${w('bills_sent')}</h3><div data-bills="keys_bills_sent"></div>` : ''}
  </section>`;
}

// --- several keys per provider (2026-09-19): default first, rotated on quota / invalid (providers.py) -------------

// A borrowed key is somebody else's money: it cannot become your default and you cannot delete it,
// so those two buttons are not drawn for it. Renaming one IS yours (the owner keeps their own label).
function lentRows(d, keyId) {
  const n = ((d.shares || {}).lent_counts || {})[keyId] || 0;
  if (!n) return '';
  return `<div class="lent row tight small"><span>${icon('users', 12)} ${esc(w('lent_count', { n }))}</span>
      <button type="button" class="small ghost" data-lent-key="${esc(keyId)}">${icon('users', 12)} ${w('lent_manage')}</button></div>`;
}

function poolRows(d, pid) {
  const keys = (d.pool || {})[pid] || [];
  if (!keys.length) return '';
  // 2026-09-26: your own key running low / stopped offers the way to fix it - the provider's own page to add credit
  const where = (((d.providers || {}).providers || []).find((x) => x.id === pid) || {}).where || '';
  return `<div class="pool">${keys.map((k) => `<div class="pool-row ${k.usable ? '' : 'off'}">
      <input data-pool-rename="${esc(k.id)}" value="${esc(k.name)}" maxlength="${d.key_name_max}" title="${esc(k.shared ? w('borrowed_rename_hint') : w('pool_rename_hint'))}" style="max-width:220px;font-weight:600"/><code class="small">${esc(k.hint)}</code>
      ${k.shared ? `<span class="tag warn" title="${esc(w('borrowed_owner', { owner: k.owner_name || '' }))}">${w('borrowed_tag')} ${esc(w('borrowed_owner', { owner: k.owner_name || '' }))}</span>` : ''}
      ${k.is_default ? `<span class="tag brand">${w('pool_is_default')}</span>` : ''}
      <span class="tag ${k.status === 'active' ? 'ok' : k.status === 'exhausted' ? 'warn' : 'bad'}" title="${esc(k.reason || '')}">${esc(w(`status_${k.status}`) || k.status)}</span>
      ${k.since ? `<span class="small muted">${esc(w('pool_since', { at: when(k.since) }))}</span>` : ''}
      ${k.low ? `<span class="tag warn" title="${esc(k.low_reason || '')}">${w('low_now')}</span>` : ''}
      ${k.blocked ? `<span class="tag bad" title="${esc(k.blocked_reason || '')}">${w('blocked_now')}</span>` : ''}
      <span class="spacer"></span>
      ${k.shared || k.is_default ? '' : `<button type="button" class="small ghost" data-pool-default="${esc(k.id)}">${w('pool_default')}</button>`}
      ${!k.shared && where && (k.low || k.status !== 'active') ? `<a class="pill" href="${esc(where)}" target="_blank" rel="noopener" title="${esc(w('add_credit_tip'))}">${icon('plus', 12)} ${w('add_credit')} ${icon('external', 11)}</a>` : ''}
      <button type="button" class="small ghost" data-pool-test="${esc(k.id)}">${icon('spark', 12)} ${w('pool_test')}</button>
      ${k.shared
        ? `<button type="button" class="small ghost danger" data-return="${esc(k.grant_id)}" data-name="${esc(k.name)}">${icon('trash', 12)} ${w('give_back')}</button>`
        : `<button type="button" class="small ghost" data-share="${esc(k.id)}" data-name="${esc(k.name)}">${icon('user', 12)} ${w('share_open')}</button>
           <button type="button" class="small ghost danger" data-pool-remove="${esc(k.id)}" data-name="${esc(k.name)}">${icon('trash', 12)} ${w('pool_remove')}</button>`}
    </div>${k.shared ? '' : lentRows(d, k.id)}`).join('')}</div>`;
}

function poolAddForm(pid, label, have = false) {
  // 2026-09-20 owner: "Add another key - but there is no key". The first one is not "another".
  return `<div class="row tight pool-add">
    <input type="password" autocomplete="new-password" data-lpignore="true" data-1p-ignore spellcheck="false" data-pool-secret="${esc(pid)}" placeholder="${esc(label)}"/>
    <input data-pool-name="${esc(pid)}" placeholder="${esc(w('pool_name'))}" style="max-width:160px"/>
    <button type="button" class="small" data-pool-add="${esc(pid)}">${icon('plus', 13)} ${have ? w('pool_add') : w('pool_add_first')}</button></div>`;
}

const hasKeys = (d, pid) => (((d.pool || {})[pid] || []).length > 0);

function poolCard(d, pid) {
  const p = (d.providers || {}).providers?.find((x) => x.id === pid);
  if (!p) return '';
  return `<section class="card"><h2>${icon('key', 17)} ${esc(w('pool_title', { label: p.label }))}</h2>
    <p class="muted small">${w('pool_note')}</p>
    ${poolRows(d, pid)}
    ${poolAddForm(pid, (d.fields[p.key_field] || {}).label || p.key_field, hasKeys(d, pid))}
    <div id="pool-out-${esc(pid)}"></div></section>`;
}

function wirePool(host, msg) {
  const again = () => keysPage(host);
  host.querySelectorAll('[data-pool-add]').forEach((b) => {
    b.onclick = () => busy(b, async () => {
      const pid = b.dataset.poolAdd;
      const secret = host.querySelector(`[data-pool-secret="${pid}"]`).value;
      const name = (host.querySelector(`[data-pool-name="${pid}"]`) || {}).value || '';
      if (!secret.trim()) { say(msg, 'warn', w('paste_first')); return; }
      try { await api('/api/keys/pool', { method: 'POST', body: { provider: pid, secret, name } }); toast(w('pool_added'), 'ok'); again(); }
      catch (err) { say(msg, 'bad', esc(err.message)); }
    });
  });
  host.querySelectorAll('[data-pool-rename]').forEach((inp) => {
    inp.onchange = async () => {
      try { const r = await api(`/api/keys/pool/${encodeURIComponent(inp.dataset.poolRename)}/name`, { method: 'PUT', body: { name: inp.value } }); inp.value = r.name; toast(w('pool_renamed'), 'ok'); }
      catch (err) { say(msg, 'bad', esc(err.message)); }
    };
  });
  host.querySelectorAll('[data-pool-default]').forEach((b) => {
    b.onclick = () => busy(b, async () => {
      try { await api(`/api/keys/pool/${b.dataset.poolDefault}/default`, { method: 'POST' }); again(); } catch (err) { say(msg, 'bad', esc(err.message)); }
    });
  });
  host.querySelectorAll('[data-pool-test]').forEach((b) => {
    b.onclick = () => busy(b, async () => {
      try { const r = await api(`/api/keys/pool/${b.dataset.poolTest}/test`, { method: 'POST' }); toast(r.message, 'ok', 8); again(); }
      catch (err) { say(msg, 'bad', esc(err.message)); again(); }
    });
  });
  host.querySelectorAll('[data-pool-remove]').forEach((b) => {
    b.onclick = () => confirmDialog(w('pool_remove_title', { name: b.dataset.name }), w('pool_remove_body'), async () => {
      try { await api(`/api/keys/pool/${b.dataset.poolRemove}`, { method: 'DELETE' }); again(); } catch (err) { say(msg, 'bad', esc(err.message)); }
    }, w('pool_remove'), { tone: 'danger' });
  });
}

// --- other providers (2026-09-19): a key per provider, a pick per kind of work, a budget per provider ---------------

const priceLine = (m) => {
  if (m.kind === 'text' && m.in !== undefined) return w('price_text', { in: budget(m.in), out: budget(m.out) });
  if (m.kind === 'image' && m.usd_per_image !== undefined) return w('price_image', { usd: money(m.usd_per_image) });
  if (m.kind === 'video' && m.usd_per_second_low !== null && m.usd_per_second_low !== undefined) return w('price_video', { low: money(m.usd_per_second_low), high: money(m.usd_per_second_high) });
  return '';
};

/** 2026-09-26 owner: "new models come and go very fast - how will the portal know?" Ask every provider for its list:
 *  a NEW model can be added (its price is yours to confirm - only OpenRouter says it), a GONE one retired. Each is a new
 *  version of chips providers.models / providers.model_facts. A model a call found withdrawn is already out of the lists. */
async function modelCheck(host) {
  let r;
  try { r = await api('/api/models/check'); } catch (err) { toast(err.message, 'bad', 8); return; }
  const qual = [5, 4, 3, 2, 1].map((q) => `<option value="${q}" ${q === 3 ? 'selected' : ''}>${'★'.repeat(q)}</option>`).join('');
  const priceFields = (m) => (m.kind === 'text'
    ? `<input data-f="in" type="number" step="0.0001" min="0" placeholder="${esc(w('mc_in'))}" value="${m.price.in ?? ''}"/><input data-f="out" type="number" step="0.0001" min="0" placeholder="${esc(w('mc_out'))}" value="${m.price.out ?? ''}"/>`
    : m.kind === 'image' ? `<input data-f="usd_per_image" type="number" step="0.001" min="0" placeholder="${esc(w('mc_per_image'))}"/>`
      : `<input data-f="usd_per_second" type="number" step="0.001" min="0" placeholder="${esc(w('mc_per_second'))}"/>`);
  const body = (r.providers || []).map((p) => `<div class="mc-prov"><h3 class="sw-h3">${esc(p.label)}</h3>
      ${p.error ? `<p class="small muted">${esc(p.error)}</p>` : ''}
      ${!p.error && !p.new.length && !p.gone.length ? `<p class="small muted">${esc(w('mc_same'))}</p>` : ''}
      ${p.new.map((m) => `<div class="mc-row" data-p="${esc(p.provider)}" data-id="${esc(m.id)}" data-kind="${esc(m.kind)}">
        <span class="tag ok">${esc(w('mc_new'))}</span><b>${esc(m.id)}</b><span class="muted small">${esc(w(`mc_kind_${m.kind}`))}</span>
        <input data-f="label" value="${esc(m.label)}" aria-label="${esc(w('label_label'))}"/>${priceFields(m)}<select data-f="quality" title="${esc(w('mc_quality'))}">${qual}</select>
        <input data-f="good_for" placeholder="${esc(w('mc_good_for'))}"/>
        <button type="button" class="small primary" data-add>${icon('plus', 12)} ${w('mc_add')}</button></div>`).join('')}
      ${p.gone.map((m) => `<div class="mc-row" data-id="${esc(m.id)}">
        <span class="tag warn">${esc(w('mc_gone'))}</span><b>${esc(m.id)}</b>
        <span class="small muted">${esc(w(m.seen_gone ? 'mc_gone_seen' : 'mc_gone_note', { provider: p.label }))}</span>
        <button type="button" class="small" data-retire>${icon('close', 12)} ${w('mc_retire')}</button></div>`).join('')}</div>`).join('');
  modal(w('mc_title'), `<p class="small muted">${esc(w('mc_lede'))}</p>${body}`, {
    wide: true,
    onOpen: (m) => {
      m.querySelectorAll('[data-add]').forEach((b) => { b.onclick = () => {
        const row = b.closest('.mc-row');
        const f = Object.fromEntries([...row.querySelectorAll('[data-f]')].map((x) => [x.dataset.f, x.value]));
        const price = f.in || f.out || f.usd_per_image || f.usd_per_second;
        if (!price) { toast(w('mc_price_first'), 'warn'); return; }
        busy(b, async () => {
          try { await api('/api/models/add', { method: 'POST', body: { provider: row.dataset.p, id: row.dataset.id, kind: row.dataset.kind, ...f } }); row.remove(); toast(w('mc_added', { model: row.dataset.id }), 'ok'); } catch (err) { toast(err.message, 'bad', 8); }
        });
      }; });
      m.querySelectorAll('[data-retire]').forEach((b) => { b.onclick = () => {
        const row = b.closest('.mc-row');
        confirmDialog(w('mc_retire_title', { model: row.dataset.id }), w('mc_retire_body'), async () => {
          try { await api('/api/models/retire', { method: 'POST', body: { id: row.dataset.id } }); row.remove(); toast(w('mc_retired', { model: row.dataset.id }), 'ok'); } catch (err) { toast(err.message, 'bad', 8); }
        }, w('mc_retire'), { tone: 'warn' });
      }; });
    } });
}

function providersCard(d) {
  const p = d.providers;
  if (!p) return '';
  const others = p.providers.filter((x) => x.id !== ps('keys').pool_provider);
  const kinds = ['text', 'image'];
  return `<section class="card"><h2>${icon('chip', 17)} ${w('providers_card')}</h2>
    <p class="muted small">${w('providers_note')}</p>
    <div class="pv-grid">
      ${others.map((x) => `<div class="pv-row">
        <div class="pv-head"><b>${esc(x.label)}</b>
          ${x.free ? `<span class="tag ok">${w('free_tag')}</span>` : ''}
          <span class="tag ${x.have_key ? 'ok' : ''}">${x.have_key ? w('key_in') : w('needs_key')}</span>
          ${x.where ? `<a class="small" href="${esc(x.where)}" target="_blank" rel="noopener">${w('get_key')} ${icon('external', 11)}</a>` : ''}</div>
        ${x.key_field ? poolRows(d, x.id) : ''}
        ${x.have_key && d.funds[x.id] ? `<div class="row tight small pv-fund"><label for="pv-fund-${esc(x.id)}">${esc(w('budget_for', { label: x.label }))}</label>
          <input id="pv-fund-${esc(x.id)}" inputmode="decimal" style="max-width:110px" value="${d.funds[x.id].loaded_usd ? toLocal(d.funds[x.id].loaded_usd) : ''}" placeholder="10"/>
          <span class="small muted">${esc(d.currency.code)}</span>
          <button type="button" class="small ghost" data-fund="${esc(x.id)}" title="${esc(w('fund_save'))}" aria-label="${esc(w('fund_save'))}">${icon('save', 12)}</button>
          <span class="muted">${money(d.funds[x.id].spent_usd)}${d.funds[x.id].left_usd !== null ? ` · ${budget(d.funds[x.id].left_usd)}` : ''}</span>
          <small class="muted">${esc(w('budget_shared', { label: x.label }))}</small></div>` : ''}
        ${x.key_field ? poolAddForm(x.id, (d.fields[x.key_field] || {}).label || x.key_field, hasKeys(d, x.id)) : ''}
      </div>`).join('')}
    </div>
    <div class="pv-picks">${kinds.map((kind) => {
      const chosen = p.chosen[kind] || {};
      const models = (p.kinds[kind] || []).filter((m) => m.have_key || m.provider === chosen.provider);
      return `<div class="field"><label for="pv-${kind}">${esc(w(`kind_${kind}`))}</label>
        <select id="pv-${kind}" data-kind="${kind}">${models.map((m) => `<option value="${esc(m.provider)}|${esc(m.id)}" ${m.provider === chosen.provider && m.id === chosen.model ? 'selected' : ''}>
          ${esc(p.providers.find((x) => x.id === m.provider)?.label || m.provider)} · ${esc(m.label || m.id)}${priceLine(m) ? ` — ${esc(priceLine(m))}` : ''}</option>`).join('')}</select></div>`;
    }).join('')}</div>
  </section>`;
}

function wireProviders(host, d, msg) {
  host.querySelectorAll('[data-save-key]').forEach((b) => {
    b.onclick = () => busy(b, async () => {
      const field = b.dataset.saveKey;
      const val = host.querySelector(`[data-key="${field}"]`).value.trim();
      if (!val || val.startsWith('•')) return;
      try {
        await api('/api/keys', { method: 'PUT', body: { values: { [field]: val } } });
        toast(w('key_saved', { label: b.dataset.label }), 'ok');
        keysPage(host);
      } catch (err) { say(msg, 'bad', esc(err.message)); }
    });
  });
  host.querySelectorAll('[data-fund]').forEach((b) => {
    b.onclick = () => busy(b, async () => {
      try {
        await api('/api/funds', { method: 'PUT', body: { provider: b.dataset.fund, loaded: host.querySelector(`#pv-fund-${b.dataset.fund}`).value } });
        toast(w('budget_saved'), 'ok');
        keysPage(host);
      } catch (err) { say(msg, 'bad', esc(err.message)); }
    });
  });
  host.querySelectorAll('select[data-kind]').forEach((sel) => {
    sel.onchange = async () => {
      const [provider, model] = sel.value.split('|');
      try {
        const got = await api('/api/providers/choice', { method: 'PUT', body: { kind: sel.dataset.kind, provider, model } });
        toast(w('choice_saved', { kind: w(`kind_${sel.dataset.kind}`), label: got.label, model: got.model }), 'ok');
      } catch (err) { say(msg, 'bad', esc(err.message)); keysPage(host); }
    };
  });
}

/** Four words to Google on this person's own key. The only honest answer to "is my key working?",
 *  and cheap enough to press whenever you wonder. */
async function runTest(out) {
  say(out, 'info', w('asking'));
  try {
    const r = await api('/api/keys/test', { method: 'POST' });
    say(out, 'ok', w('test_ok', { model: esc(r.model), secs: r.elapsed_s, cost: money(r.cost_usd) })
      + (r.switched_from ? w('test_switched', { from: esc(r.switched_from), model: esc(r.model) }) : ''));
  } catch (e) { say(out, 'bad', esc(e.message)); }
}

/** Adding a key from wherever you noticed you needed one — this page, or the middle of a video.
 *  Saving and proving it are one press, because a key that was never tried is not yet a key. */
export async function keyDialog(onSaved = () => {}) {
  await loadWords('keys');         // opened from Videos too, before this screen was ever drawn
  const fields = {
    gemini_api_key: { label: w('key_label') },
    gemini_model: { label: w('model_label'),
                    choices: ps('keys').gemini_models || [] },
  };
  modal(w('dialog_title'), `
    <p class="small muted">${w('dialog_note', { guide: GUIDE() })}</p>
    ${secretField('kd-key', fields.gemini_api_key.label,
      { hint: w('key_hint') })}
    <div class="field"><label for="kd-label">${w('label_label')}</label>
      <input id="kd-label" autocomplete="off"/>
      <span class="small muted">${w('label_hint')}</span></div>
    ${choiceField('kd-model', fields.gemini_model.label, {
      choices: fields.gemini_model.choices, value: 'gemini-flash-latest', otherOk: true,
      hint: w('model_hint') })}
    <div id="kd-msg" style="margin-top:12px"></div>`,
    { footer: `<span class="left">${w('saving_tries')}</span>
        <button type="button" data-cancel>${sw('cancel')}</button>
        <button type="button" class="primary" id="kd-go">${icon('check')} ${w('save_and_test')}</button>`,
      onOpen: (body, close) => {
        // No expected length: AI Studio keys are "AIza…" (39) or, since 2026, "AQ.…" (53). Google decides.
        wireSecrets(body);
        wireChoices(body);
        const card = body.closest('.modal');
        const out = body.querySelector('#kd-msg');
        card.querySelector('[data-cancel]').onclick = close;
        const labelBox = body.querySelector('#kd-label');
        // Prefill with the current default key's label, so replacing a key keeps (or corrects) its account name.
        api('/api/keys').then((d) => { const k = ((d.pool || {}).gemini || [])[0]; if (d.key_name_max) labelBox.maxLength = d.key_name_max; if (k && !labelBox.value) labelBox.value = k.name; }).catch(() => {});
        card.querySelector('#kd-go').onclick = (e) => busy(e.currentTarget, async () => {
          const key = body.querySelector('#kd-key').value.trim();
          if (!key) { say(out, 'warn', w('paste_first')); return; }
          try {
            await api('/api/keys', { method: 'PUT', body: { values: {
              gemini_api_key: key, gemini_model: choiceValue(body, 'kd-model') } } });
            await api(`/api/keys/pool/${encodeURIComponent('field:gemini')}/name`, { method: 'PUT', body: { name: labelBox.value } });
          } catch (err) { say(out, 'bad', esc(err.message)); return; }
          say(out, 'info', w('saved_asking'));
          try {
            const r = await api('/api/keys/test', { method: 'POST' });
            state.hasKey = true;
            await refreshMe();
            close();
            toast(r.switched_from
              ? w('works_switched', { from: r.switched_from, model: r.model })
              : w('works', { model: r.model }), 'ok', 9);
            onSaved(true);
          } catch (err) {
            // Saved but refused: keep the dialog open with Google's own sentence in it.
            state.hasKey = true;
            say(out, 'bad', `${esc(err.message)}<br/>${w('saved_but_refused')}`);
            onSaved(false);
          }
        });
      } });
}
