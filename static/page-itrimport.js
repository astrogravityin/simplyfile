// Import old returns - #/itrimport. A four-step wizard: 1 upload a client's ITR JSON as filed; 2 whose return it is - the
// client with this PAN, another client, or a new client made from the return (and start this year for them); 3 the
// acknowledgement no. and date filed; 4 done - the statement as filed and next year's statement to fill, as Excel.
// The server reads and decides (itr_import.py, chips itr.*); words: chip ui.itrimport.
import { api, BASE, esc, toast, busy, pageHead, t, loadWords, dropZone, wireDrops } from './app.js';
import { icon } from './icons.js';

const w = (k, v) => t('itrimport', k, v);
const money = (n) => `₹${Math.round(Number(n || 0)).toLocaleString('en-IN')}`;
const kindWord = (k) => w(`imp_kind_${k}`);

export async function itrImportPage(host) {
  await loadWords('itrimport');
  const S = { step: 1, file: null, p: null, who: '', done: null };
  const steps = () => `<ol class="ii-steps">${['s1', 's2', 's3', 's4'].map((s, i) => `<li class="${i + 1 < S.step ? 'is-done' : i + 1 === S.step ? 'is-now' : ''}">
    <span>${i + 1 < S.step ? icon('check', 12) : i + 1}</span>${esc(w(s))}</li>`).join('')}</ol>`;
  const summary = (f) => `<div class="card ii-sum"><div class="ii-sum-h">${icon('folder', 18)}<div><b>${esc(w('found', { form: f.form, ay: f.ay, kind: kindWord(f.kind) }))}</b>
      <div class="small muted">${esc(f.name)} · <code>${esc(f.pan)}</code></div></div></div>
    <table class="cc-tbl ii-tbl"><tbody>
      ${[['HP', f.hp], ['BP', f.bp], ['CG', f.cg], ['OS', f.os], ['SAL', f.sal]].filter((x) => x[1]).map(([h, v]) => `<tr><td>${esc(w(`h_${h}`))}</td><td class="num">${money(v)}</td></tr>`).join('')}
      <tr class="cc-key"><td>${esc(w('f_income'))}</td><td class="num">${money(f.income)}</td></tr>
      <tr><td>${esc(w('f_tax'))}</td><td class="num">${money(f.tax_net)}</td></tr>
      <tr><td>${esc(w('f_paid'))}</td><td class="num">${money(f.paid)}</td></tr>
      ${f.refund ? `<tr><td>${esc(w('f_refund'))}</td><td class="num">${money(f.refund)}</td></tr>` : ''}
      ${f.payable ? `<tr><td>${esc(w('f_payable'))}</td><td class="num">${money(f.payable)}</td></tr>` : ''}</tbody></table></div>`;

  const draw = () => {
    const f = S.p && S.p.facts;
    let body = '';
    if (S.step === 1) {
      body = `<section class="card ii-card"><h3 class="rc-h">${icon('upload', 15)} ${esc(w('up_title'))}</h3><p class="small muted">${esc(w('up_hint'))}</p>
        ${dropZone('ii-file', { accept: '.json,application/json', title: w('choose'), hint: '.json' })}
        <div class="row tight ii-acts"><span></span><button type="button" class="primary" id="ii-read">${esc(w('next'))} ${icon('right', 14)}</button></div></section>`;
    } else if (S.step === 2) {
      const m = S.p.match[0];
      const others = S.p.clients.filter((c) => !m || c.id !== m.id);
      body = summary(f) + `<section class="card ii-card"><h3 class="rc-h">${icon('users', 15)} ${esc(w('match_title'))}</h3>
        <p class="small ${m ? 'ii-ok' : 'muted'}">${esc(m ? w('match_found', { name: m.name }) : w('match_none', { pan: f.pan }))}</p>
        ${m ? `<label class="ii-opt"><input type="radio" name="ii-who" value="${esc(m.id)}" ${S.who === m.id ? 'checked' : ''}/> <span>${esc(w('use_existing', { name: m.name }))}</span></label>` : ''}
        <label class="ii-opt"><input type="radio" name="ii-who" value="new" ${S.who === 'new' ? 'checked' : ''}/> <span>${esc(w('make_new'))}</span></label>
        <div class="grid two ii-new" ${S.who === 'new' ? '' : 'hidden'}>
          <div class="field"><label for="ii-name">${esc(w('f_name'))}</label><input id="ii-name" value="${esc(S.name ?? f.name)}"/></div>
          <div class="field"><label for="ii-email">${esc(w('f_email'))}</label><input id="ii-email" type="email" value="${esc(S.email ?? f.email ?? '')}"/></div>
          <div class="field"><label for="ii-phone">${esc(w('f_mobile'))}</label><input id="ii-phone" value="${esc(S.phone ?? f.mobile ?? '')}"/></div></div>
        ${others.length ? `<label class="ii-opt"><input type="radio" name="ii-who" value="other" ${S.who === 'other' ? 'checked' : ''}/> <span>${esc(w('pick_other'))}</span></label>
          <select id="ii-other" ${S.who === 'other' ? '' : 'hidden'}><option value="">${esc(w('pick_ph'))}</option>${others.map((c) => `<option value="${esc(c.id)}">${esc(c.name)} · ${esc(c.pan)}</option>`).join('')}</select>` : ''}
        ${f.ay !== S.p.current_ay ? `<label class="check ii-now"><input type="checkbox" id="ii-now" ${S.now ? 'checked' : ''}/> <span>${esc(w('also_now', { ay: S.p.current_ay }))}</span></label>` : ''}
        <div class="row tight ii-acts"><button type="button" class="ghost" id="ii-back">${icon('left', 14)} ${esc(w('back'))}</button>
          <button type="button" class="primary" id="ii-next">${esc(w('next'))} ${icon('right', 14)}</button></div></section>`;
    } else if (S.step === 3) {
      body = summary(f) + `<section class="card ii-card"><h3 class="rc-h">${icon('lock', 15)} ${esc(w('confirm_title'))}</h3>
        <div class="grid two"><div class="field"><label for="ii-ack">${esc(w('ack'))}</label><input id="ii-ack" inputmode="numeric" maxlength="15" value="${esc(S.ack || '')}"/></div>
          <div class="field"><label for="ii-on">${esc(w('filed_on'))}</label><input id="ii-on" type="date" value="${esc(S.on || '')}" max="${new Date().toISOString().slice(0, 10)}"/></div></div>
        <div class="row tight ii-acts"><button type="button" class="ghost" id="ii-back">${icon('left', 14)} ${esc(w('back'))}</button>
          <button type="button" class="primary" id="ii-go">${icon('download', 14)} ${esc(w('import'))}</button></div></section>`;
    } else {
      const d = S.done;
      const st = (which) => `${BASE}/api/itrimport/${encodeURIComponent(d.client.id)}/${encodeURIComponent(d.ay)}/statement?which=${which}`;
      body = `<section class="card ii-card ii-done"><div class="ii-sum-h">${icon('check', 20)}<div><h3>${esc(w('done_title'))}</h3>
          <div>${esc(w('done_body', { name: d.client.name, ay: d.ay, kind: kindWord(d.kind), on: d.filed_on.split('-').reverse().join('/') }))}</div>
          ${d.replaced ? `<div class="small muted">${esc(w('imp_replaces'))}</div>` : ''}</div></div>
        <div class="cc-dl ii-dl"><a class="cc-file" href="${st('filed')}">${icon('download', 16)}<span><b>${esc(w('dl_filed'))}</b></span></a>
          <a class="cc-file" href="${st('next')}">${icon('download', 16)}<span><b>${esc(w('dl_next', { ay: d.next_ay }))}</b></span></a></div>
        <div class="row tight ii-acts"><a class="button" href="#/compute?c=${encodeURIComponent(d.client.id)}&ay=${encodeURIComponent(d.ay)}">${icon('money', 14)} ${esc(w('open_compute'))}</a>
          <button type="button" class="primary" id="ii-again">${icon('plus', 14)} ${esc(w('another'))}</button></div></section>`;
    }
    host.innerHTML = pageHead(w('title'), esc(w('lede'))) + steps() + body;
    wire();
  };

  const wire = () => {
    const $ = (s) => host.querySelector(s);
    wireDrops(host);
    if ($('#ii-read')) $('#ii-read').onclick = (e) => busy(e.currentTarget, async () => {
      const f = $('#ii-file').files[0];
      if (!f) { toast(w('choose'), 'warn'); return; }
      const fd = new FormData(); fd.append('file', f);
      try {
        S.p = await api('/api/itrimport/read', { method: 'POST', body: fd });
        S.file = f;
        S.who = S.p.match.length ? S.p.match[0].id : 'new';
        S.now = !S.p.match.length;
        S.step = 2; draw();
      } catch (err) { toast(err.message, 'bad', 8); }
    });
    host.querySelectorAll('[name="ii-who"]').forEach((r) => { r.onchange = () => { keep(); S.who = r.value; draw(); }; });
    const keep = () => {
      if ($('#ii-name')) { S.name = $('#ii-name').value; S.email = $('#ii-email').value; S.phone = $('#ii-phone').value; }
      if ($('#ii-now')) S.now = $('#ii-now').checked;
      if ($('#ii-ack')) { S.ack = $('#ii-ack').value; S.on = $('#ii-on').value; }
      if ($('#ii-other')) S.otherId = $('#ii-other').value;
    };
    if ($('#ii-back')) $('#ii-back').onclick = () => { keep(); S.step -= 1; draw(); };
    if ($('#ii-next')) $('#ii-next').onclick = () => { keep(); S.step = 3; draw(); };
    if ($('#ii-go')) $('#ii-go').onclick = (e) => busy(e.currentTarget, async () => {
      keep();
      const cid = S.who === 'other' ? S.otherId : S.who;
      const fd = new FormData(); fd.append('file', S.file);
      fd.append('body', JSON.stringify({ cid, ack_no: S.ack, filed_on: S.on, also_now: !!S.now, name: S.name, email: S.email, phone: S.phone }));
      try { S.done = await api('/api/itrimport', { method: 'POST', body: fd }); S.step = 4; draw(); toast(w('done_title'), 'ok'); }
      catch (err) { toast(err.message, 'bad', 8); }
    });
    if ($('#ii-again')) $('#ii-again').onclick = () => { Object.assign(S, { step: 1, file: null, p: null, who: '', done: null, name: undefined, email: undefined, phone: undefined, ack: '', on: '', now: false }); draw(); };
  };
  draw();
}
