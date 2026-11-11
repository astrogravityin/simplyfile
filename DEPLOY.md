# Deploying SimplyFile to the VPS — sf.valuestream.in

SimplyFile has its own repository, its own checkout on the server (`/opt/simplyfile`), its own Python venv, service,
port and data folder. It shares nothing with the other portals except the machine and nginx.

```bash
# 0. DNS (Hostinger hPanel -> Domains -> valuestream.in -> DNS): A record  sf -> the VPS IP
dig +short sf.valuestream.in                 # must print the VPS IP before step 5

# 1. the code (a private repo: use a deploy key or a read-only token)
cd /opt && git clone https://github.com/astrogravityin/simplyfile.git simplyfile
cd /opt/simplyfile
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt
.venv/bin/python selfcheck.py                 # "All checks passed."

# 2. a free port (8810 tv, 8820 sm are taken)
for p in $(seq 8830 8899); do ss -ltnH "sport = :$p" | grep -q . || { echo "FREE $p"; break; }; done

# 3. the service
cat >/etc/systemd/system/simplyfile.service <<'UNIT'
[Unit]
Description=SimplyFile (sf.valuestream.in)
After=network.target

[Service]
WorkingDirectory=/opt/simplyfile
Environment=TV_DATA=/opt/simplyfile/data
Environment=PORTAL_COOKIE=sf_session
Environment=TV_HTTPS=1
Environment=TV_OWNER_EMAIL=chandra.s.vempati@gmail.com
Environment=PORT=8830
ExecStart=/opt/simplyfile/.venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 8830
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT
mkdir -p /opt/simplyfile/data && chmod 700 /opt/simplyfile/data    # client statements and PANs live here
systemctl daemon-reload && systemctl enable --now simplyfile
curl -sf http://127.0.0.1:8830/health && echo " simplyfile up"

# 4. nginx - a fresh port-80 block (certbot adds 443 in step 5)
cat >/etc/nginx/sites-available/sf.valuestream.in <<'CONF'
server {
    listen 80;
    listen [::]:80;
    server_name sf.valuestream.in;
    client_max_body_size 50M;
    proxy_request_buffering off;
    location / {
        proxy_pass         http://127.0.0.1:8830;
        proxy_http_version 1.1;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }
}
CONF
ln -sf /etc/nginx/sites-available/sf.valuestream.in /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

# 5. TLS
certbot --nginx -d sf.valuestream.in --redirect

# 6. backups - tools/backup.sh, every hour (see "Backups" below)
printf 'SF_OFFSITE=sfcrypt:
23 * * * * root bash /opt/simplyfile/tools/backup.sh
' >/etc/cron.d/simplyfile-backup
rm -f /var/backups/sf-data-*.tar.gz   # the old one-file-per-hour copies, if this VPS had them
```

Then open https://sf.valuestream.in, create the owner (the first account; `TV_OWNER_EMAIL` reserves the seat for that
address), and set **Email (SMTP)** as in `README.md`.

## Backups

`tools/backup.sh` runs every hour from cron. Each copy is the `data` folder without `data/geo` (the place database,
downloaded again by itself), so a copy is about the size of the firms' uploaded papers and statements - a few MB today.

| Where | Kept | How |
|---|---|---|
| `/var/backups/sf/hour-HH.tar.gz` | last 24 hours | every hour; each hour overwrites yesterday's |
| `/var/backups/sf/day-Mon.tar.gz` | last 7 days | the 02:23 copy |
| `/var/backups/sf/week-N.tar.gz` | last 5 Sundays | the Sunday 02:23 copy |
| `$SF_OFFSITE` (off the VPS) | 7 days + 5 weeks | the daily and weekly copies, sent by `rclone` |

Disk use is bounded: 36 slots, each overwritten, never more. Check it with `du -sh /var/backups/sf`.

Off-site, once (the copies hold client PANs and returns, so they are encrypted before they leave the VPS):

```bash
apt-get install -y rclone
rclone config    # 1) a remote for the storage you choose (Backblaze B2, S3, Google Drive...), e.g. "b2"
                 # 2) a "crypt" remote over it, e.g. "sfcrypt" -> b2:my-bucket/simplyfile, with a long password
bash /opt/simplyfile/tools/backup.sh && rclone ls sfcrypt:    # try it
```

Keep the crypt password somewhere other than the VPS - without it the off-site copies cannot be opened.
`SF_OFFSITE=` in `/etc/cron.d/simplyfile-backup` names the remote; for local copies only write `SF_OFFSITE=""` - a bare `SF_OFFSITE=` makes cron reject the whole file ("bad minute ... this crontab file will be ignored", 2026-10-06: no backup ran for 44 hours).

Restore (stops the portal for a moment):

```bash
systemctl stop simplyfile
mv /opt/simplyfile/data /opt/simplyfile/data.before-restore
tar xzf /var/backups/sf/hour-09.tar.gz -C /opt/simplyfile      # or: rclone copy sfcrypt:day-Mon.tar.gz /tmp/ first
systemctl start simplyfile
```

For the big sites on the same VPS the same idea saves most of the space: an hourly `tar` of 3.1 GB that barely changes
stores 3.1 GB every hour. `restic` keeps only what changed between copies (and encrypts), so 24 hourly copies of a
3.1 GB site cost about 3.1 GB plus the day's changes.

## Every update

On your machine, two double-clicks:

- `Commit-To-GitHub.cmd` — runs `selfcheck.py`, stages, refuses client data / broken `.py` / `.json` / huge files
  (`tools/staged_check.py`), commits, pushes. `-Paths a,b` commits only those files; `-Deploy` also deploys.
- `Deploy-To-VPS.cmd` — over ssh (key `%USERPROFILE%\.ssh\explore_whattag`, or `-Key` / `SF_VPS_KEY`) runs
  `bash /opt/simplyfile/deploy.sh` on the VPS: pull, install, self-check, and only then restart, then waits for `/health`.

Or on the VPS directly: `bash /opt/simplyfile/deploy.sh`.

## Release folders - a deploy you can undo (W1.4, 2026-11-11)

`deploy/deploy.sh` builds every update in its own folder and moves the site to it only when it passed:

```
<base>/releases/<commit>/     one per release (a git worktree); .venv -> <base>/venvs/<hash of the lock file>
<base>/current -> releases/…  what the service runs
<base>/data/                  the portal's memory - never inside a release
```

1. pull the checkout, build `releases/<commit>`, install packages (`requirements.lock` when there is one);
2. run `selfcheck.py` inside the new release - a failure stops here, the live release is untouched;
3. start the new release on the **probe port** with an empty data folder and ask `/health` - a failure stops here;
4. move `current` (one atomic rename), restart, ask the live `/health` - a failure moves `current` back and restarts
   the old release;
5. keep the newest `keep_releases` folders (never the live one or the rollback one).

`bash deploy/deploy.sh rollback` (or `Deploy-To-VPS.cmd -Rollback`) puts the release before back; `status` shows
what is live and what a rollback would go to. `--target staging` does all of it in the staging folder on its own port.
Folders, ports, service user, keep-N, health wait and commands are in chip **deploy.settings** (Ops & chips);
`DEPLOY_<NAME>` overrides one run. The server address and ssh key are in `deploy/vps.local` on your machine (never in
git) or `SF_VPS` / `SF_VPS_KEY`. Proof on any machine, no server touched: `bash deploy/harness/dryrun.sh`.
Guard: `python selfcheck_deploy.py`.

### Switch-over to release folders (once per server, owner)

Until this is done `Deploy-To-VPS.cmd` keeps running the old `deploy.sh`, so nothing changes by accident.

```bash
# as root on the VPS
useradd --system --home /opt/simplyfile --shell /usr/sbin/nologin simplyfile
cd /opt/simplyfile && grep -E '^Environment=(PORTAL_COOKIE|TV_HTTPS|TV_OWNER_EMAIL)' \
  /etc/systemd/system/simplyfile.service | sed 's/^Environment=//' > portal.env && chmod 640 portal.env
chown -R simplyfile:simplyfile /opt/simplyfile && chown root:simplyfile portal.env
echo 'simplyfile ALL=(root) NOPASSWD: /usr/bin/systemctl restart simplyfile, /usr/bin/systemctl restart simplyfile-demo-*' \
  > /etc/sudoers.d/simplyfile-deploy && chmod 440 /etc/sudoers.d/simplyfile-deploy && visudo -c
runuser -u simplyfile -- bash deploy/deploy.sh init            # builds releases/<HEAD>, points current at it
cp /etc/systemd/system/simplyfile.service /root/simplyfile.service.before
bash deploy/deploy.sh unit > /etc/systemd/system/simplyfile.service   # User=simplyfile, WorkingDirectory=current
systemctl daemon-reload && systemctl restart simplyfile && curl -sf http://127.0.0.1:8830/health
```

Back out (if the health line fails): copy `/root/simplyfile.service.before` back, `daemon-reload`, restart. The VPS
Console's SSO drop-in (`simplyfile.service.d/`) is kept by both. Staging: `git clone` the repo to
`/opt/simplyfile-staging`, the same steps with `--target staging`, a `staging.` nginx block to port 8837.

## Self-host image

`docker compose up -d --build` runs the portal on port 8830 with its data in the `data` volume (`Dockerfile`, non-root
user, health check). Site values (`PORTAL_OWNER_EMAIL`, `PORTAL_HTTPS`, ...) come from a `.env` file beside
`compose.yml`.

## If something is wrong

- `journalctl -u simplyfile -n 50` — the service log.
- `curl -s http://127.0.0.1:8830/health/run` (on the VPS) — which commit is running.
- `[Errno 98] address already in use` — the port is taken: pick another in step 2, in the unit and in nginx.
- Locked out: `cd /opt/simplyfile && TV_DATA=/opt/simplyfile/data .venv/bin/python admin.py` lists accounts and resets
  a password.
