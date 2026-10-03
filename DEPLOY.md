# Deploying SimplyFile to the VPS — sf.valuestream.in

SimplyFile has its own repository, its own checkout on the server (`/opt/simplyfile`), its own Python venv, service,
port and data folder. It shares nothing with AstroStage, tv or sm except the machine and nginx.

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

# 6. backups - the data folder is the portal's whole memory
echo '23 * * * * root tar czf /var/backups/sf-data-$(date +\%H).tar.gz -C /opt/simplyfile data' >/etc/cron.d/simplyfile-backup
```

Then open https://sf.valuestream.in, create the owner (the first account; `TV_OWNER_EMAIL` reserves the seat for that
address), and set **Email (SMTP)** as in `README.md`.

## Every update

On your machine, two double-clicks:

- `Commit-To-GitHub.cmd` — runs `selfcheck.py`, stages, refuses client data / broken `.py` / `.json` / huge files
  (`tools/staged_check.py`), commits, pushes. `-Paths a,b` commits only those files; `-Deploy` also deploys.
- `Deploy-To-VPS.cmd` — over ssh (key `%USERPROFILE%\.ssh\explore_whattag`, or `-Key` / `SF_VPS_KEY`) runs
  `bash /opt/simplyfile/deploy.sh` on the VPS: pull, install, self-check, and only then restart, then waits for `/health`.

Or on the VPS directly: `bash /opt/simplyfile/deploy.sh`.

## If something is wrong

- `journalctl -u simplyfile -n 50` — the service log.
- `curl -s http://127.0.0.1:8830/health/run` (on the VPS) — which commit is running.
- `[Errno 98] address already in use` — the port is taken: pick another in step 2, in the unit and in nginx.
- Locked out: `cd /opt/simplyfile && TV_DATA=/opt/simplyfile/data .venv/bin/python admin.py` lists accounts and resets
  a password.
