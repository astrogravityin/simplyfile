# Product demos - demo.valuestream.in

One public link for every product: `demo.valuestream.in` is a hub page (`hub/index.html`, cards from `hub/products.json`), and
each product's demo runs at its own path - SimplyFile at `/tax`. A demo is the same code as prod, started in demo mode
(`PORTAL_DEMO=1`, core/demo.py): visitors sign in with a code mailed to them, each on a seat of their own (SimplyFile: a Partner
in Demo CA Filing Firm), and the data is put back from a snapshot every night. Who came and what they opened: sign in to the demo
as the owner - People, Activity and Visitors.

## First time (on the VPS, as root)

1. DNS: an `A` record `demo.valuestream.in` -> the VPS address (where valuestream.in's DNS is managed).
2. Deploy the code as usual (Commit-To-GitHub, Deploy-To-VPS) so `/opt/simplyfile/deploy/demo/` exists.
3. Copy the snapshot to the VPS, e.g. from Windows: `scp demo-tax-snapshot.tgz root@<vps>:/root/`
4. `bash /opt/simplyfile/deploy/demo/setup.sh tax 8840 /root/demo-tax-snapshot.tgz` - the service, the data, prod's mail
   settings, the nightly reset. It ends with `SETUP OK`.
5. nginx: `cp /opt/simplyfile/deploy/demo/nginx-demo.conf /etc/nginx/sites-available/demo.valuestream.in`,
   `ln -s /etc/nginx/sites-available/demo.valuestream.in /etc/nginx/sites-enabled/`, `nginx -t && systemctl reload nginx`,
   then `certbot --nginx -d demo.valuestream.in`.
6. Your own passwords on the demo (typed, never shown):
   `/opt/simplyfile/.venv/bin/python /opt/simplyfile/deploy/demo/account.py /opt/simplyfile-demo/tax/data demo@valuestream.in`
   and the same for the owner account (add `--new-email you@... ` to change its address first).
7. The demo's mail (codes) through Brevo, not prod's Gmail: sign in to the demo as the owner -> Projects & portal -> Email
   (SMTP): server `smtp-relay.brevo.com`, port `587`, security `starttls`, user = the Brevo SMTP login, password = the Brevo
   SMTP key, send from `contact@valuestream.in` (the verified Brevo sender), sender name `SimplyFile demo`. Send yourself a
   code from "Try the demo" to check. The nightly reset keeps these settings.

## Every day

- A deploy restarts the demos too (deploy.sh).
- 03:00 IST the data goes back to the snapshot; accounts, the activity log, mail and portal settings are kept.
- Reset now: `bash /opt/simplyfile/deploy/demo/reset.sh tax`.
- A new snapshot: copy it to the VPS and run step 4 again (it replaces the snapshot; the next reset uses it).

## Another product (Legal, Medical...)

Its own code folder and service with `PORTAL_DEMO=1` and `PORTAL_BASE=/legal` on its own port, a `/legal/` block in
`nginx-demo.conf`, and a card in `hub/products.json`. Demo sign-in, the banner and the visitor log come from core/ for free;
the product adds only where a visitor's seat goes (SimplyFile: `firms.seat_demo`, chip `demo.host`).
