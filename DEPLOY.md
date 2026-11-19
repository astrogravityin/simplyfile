# Deploying SimplyFile to the VPS — sf.valuestream.in

SimplyFile has its own repository, its own checkout on the server (`/opt/simplyfile`), its own Python venv, service,
port and data folder. It shares nothing with the other portals except the machine and nginx.

```bash
# 0. DNS (Hostinger hPanel -> Domains -> valuestream.in -> DNS): A record  sf -> the VPS IP
dig +short sf.valuestream.in                 # must print the VPS IP before step 5

# 1. the code (a private repo: use a deploy key or a read-only token)
cd /opt && git clone https://github.com/astrogravityin/simplyfile.git simplyfile
cd /opt/simplyfile
# the service's own user (never root): packages, the self-check and the app run as it (2026-11-18 gap audit C1-18)
useradd --system --home-dir /opt/simplyfile --no-create-home --shell /usr/sbin/nologin simplyfile
mkdir -p data && chown -R simplyfile:simplyfile /opt/simplyfile && git config --system --add safe.directory /opt/simplyfile
runuser -u simplyfile -- python3 -m venv .venv
runuser -u simplyfile -- .venv/bin/pip install -q --require-hashes --no-deps -r requirements.lock   # every file checked by its hash
runuser -u simplyfile -- .venv/bin/python selfcheck.py                                             # "All checks passed."

# 2. a free port (8810 tv, 8820 sm are taken)
for p in $(seq 8830 8899); do ss -ltnH "sport = :$p" | grep -q . || { echo "FREE $p"; break; }; done

# 3. the service
cat >/etc/systemd/system/simplyfile.service <<'UNIT'
[Unit]
Description=SimplyFile (sf.valuestream.in)
After=network.target

[Service]
User=simplyfile
Group=simplyfile
WorkingDirectory=C:/Program Files/Git/opt/simplyfile/nEnvironment=TV_DATA=/opt/simplyfile/data/nEnvironment=PORTAL_COOKIE=sf_session
Environment=TV_HTTPS=1
Environment=TV_OWNER_EMAIL=chandra.s.vempati@gmail.com
Environment=PORT=8830
ExecStart=/opt/simplyfile/.venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 8830
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT
chmod 700 /opt/simplyfile/data    # client statements and PANs live here (owned by simplyfile)
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
# 6b. restore drill - monthly, restores the newest copy into a temp folder and checks it (see "Restore drill" below)
printf '41 4 1 * * root SF_APP=/opt/simplyfile SF_BACKUPS=/var/backups/sf /opt/simplyfile/.venv/bin/python /opt/simplyfile/tools/restore_drill.py
' >/etc/cron.d/simplyfile-restore-drill
bash /opt/simplyfile/tools/backup.sh && SF_BACKUPS=/var/backups/sf /opt/simplyfile/.venv/bin/python /opt/simplyfile/tools/restore_drill.py   # the first drill, now
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

### Restore drill (monthly, automatic)

A backup nobody restored is a hope. `tools/restore_drill.py` (cron line `/etc/cron.d/simplyfile-restore-drill`, step 6b) takes
the newest copy in `SF_BACKUPS`, unpacks it into a temp folder, checks every `.json` parses and every `.sqlite3` passes
`PRAGMA integrity_check`, starts the portal on that copy and asks `/api/bootstrap` (chip `health.settings` `drill_*`), then
writes the date and the result to `data/restore_drill.json`. The live portal is not stopped. The owners' health bar turns red
(and the bell rings once) when the last drill failed or the last good one is older than 35 days (`drill_max_days`), or when
a server has never drilled. Run it by hand the same way any time; exit 0 = good.

For the big sites on the same VPS the same idea saves most of the space: an hourly `tar` of 3.1 GB that barely changes
stores 3.1 GB every hour. `restic` keeps only what changed between copies (and encrypts), so 24 hourly copies of a
3.1 GB site cost about 3.1 GB plus the day's changes.

## Every update

2026-11-18 (gap audit C1-18): `deploy.sh` runs the package install, the self-check and the Tour Video recorder as the unit's
`User=` (root keeps only `git pull`, the one sign-in drop-in and the restart); a unit still without `User=` makes it print
`WARNING: <service> runs as root` - do the switch-over below once. Only a hashed `requirements.lock` is installed (no lock = the
deploy stops); the recorder installs `tools/tour_video/requirements.lock` the same way.

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
git config --system --add safe.directory /opt/simplyfile        # root's own git (VPS Console) still reads the checkout
# the GitHub read-only deploy key sits in ROOT's ~/.ssh/config: give the service user the same key, or its fetch fails
# ("Could not resolve hostname github-simplyfile", 2026-11-12)
install -d -o simplyfile -g simplyfile -m 700 /etc/simplyfile
install -o simplyfile -g simplyfile -m 600 /root/.ssh/simplyfile_deploy /etc/simplyfile/github_deploy
ssh-keyscan -t ed25519,rsa github.com > /etc/simplyfile/known_hosts
printf 'Host github-simplyfile\n  HostName github.com\n  User git\n  IdentityFile /etc/simplyfile/github_deploy\n  IdentitiesOnly yes\n  UserKnownHostsFile /etc/simplyfile/known_hosts\n' > /etc/simplyfile/ssh_config
chown simplyfile:simplyfile /etc/simplyfile/* && chmod 600 /etc/simplyfile/*
runuser -u simplyfile -- git -C /opt/simplyfile config core.sshCommand "ssh -F /etc/simplyfile/ssh_config"
runuser -u simplyfile -- git -C /opt/simplyfile fetch origin   # must succeed before going on
runuser -u simplyfile -- bash deploy/deploy.sh init            # builds releases/<HEAD>, points current at it
cp /etc/systemd/system/simplyfile.service /root/simplyfile.service.before
bash deploy/deploy.sh unit > /etc/systemd/system/simplyfile.service   # User=simplyfile, WorkingDirectory=current
systemctl daemon-reload && systemctl restart simplyfile && curl -sf http://127.0.0.1:8830/health
```

Back out (if the health line fails): copy `/root/simplyfile.service.before` back, `daemon-reload`, restart. The VPS
Console's SSO drop-in (`simplyfile.service.d/`) is kept by both. Staging: `git clone` the repo to
`/opt/simplyfile-staging`, the same steps with `--target staging`, a `staging.` nginx block to port 8837.

Done on sf.valuestream.in 2026-11-12 (service user `simplyfile`, back-out copy `/root/simplyfile.service.before`).
Running as `simplyfile`, Server & sites can no longer read the sizes of other sites' root-only (0700) data folders.
The demo units (`simplyfile-demo-*`) still run as root from the checkout - the next step is to move them onto `current`.

## Seal key - credentials and AI keys sealed at rest

The stores named in chip `store.seal` (Credentials, people's AI keys, the key pool, Issue push keys) are written ENCRYPTED
(Fernet). The key that opens them lives OUTSIDE `data/`, so the hourly backup of `data/` alone opens nothing:

- On the VPS: `/opt/simplyfile/seal.key` (beside `data/`, mode 600, owned by the service user) - made by the portal itself at the
  first save of a sealed store. `PORTAL_SEAL_KEY_FILE=<path>` in `portal.env` puts it elsewhere; `PORTAL_SEAL_KEY=<key>` gives
  the key itself (wins over the file). Docker: the `/seal` volume (`compose.yml`).
- Back it up ONCE, apart from the data backups, the day it appears: `cat /opt/simplyfile/seal.key` into the owner's password
  manager (or an offline copy). Never in `/var/backups/<site>`, the off-site remote or git (`.gitignore` has `seal.key`).
- Restoring `data/` on a new server: put `seal.key` back beside `data/` (same name, `chmod 600`, service user's) BEFORE the
  first start. Without it the portal does not guess: a sealed store answers an error naming the missing key, nothing is read
  as empty and nothing is overwritten; with the key put back and a restart, everything opens again.
- Files saved before sealing (plain JSON) still read, and are sealed at their next save - nothing to run.
- Staging has its OWN seal key: `deploy.sh --target staging` refuses a staging whose key equals prod's (below).

## Staging is kept apart from prod

`bash deploy/deploy.sh --target staging deploy` (and `init`) first runs `deploy/separation.py`, which reads both targets'
`portal.env`, unit and drop-ins (`/etc/systemd/system/<service>.service.d/*.conf`), data folder, `smtp.json` and seal key,
and REFUSES - nothing built, nothing switched - when staging's data folder, database connection string, a `CRED_*` value, the
sign-in key, the seal key or the mail server + login equal prod's, or when staging holds a live payment key (`_live_`):
staging takes test keys only. Which settings, which targets: chip `deploy.separation`. Run the deploy as root (it reads
prod's root-only drop-ins before handing itself to the service user). Proof: `bash deploy/harness/dryrun.sh` cases
"staging pointing at prod's data" and "staging with a live payment key".

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
