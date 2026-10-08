# core/ — the portal framework

Everything a new portal needs before its first product screen. Copy this folder into the new portal
and it gets these features:

| Module | File | What it gives you |
|---|---|---|
| Login | `auth.py`, `mailer.py`, `store.py` | The AUTH.md standard: sign up with display name + user name + email, proven by an emailed 6-digit code (skipped and marked unconfirmed when there is no mail), password twice; sign in by user name or email; Forgot password with a code; change password; owner **Reset Password** in People & access with a forced change enforced on the server; invitations; rate limits; lockout. Every policy, number and sentence is an `auth.*` / `mail.texts` chip. |
| People & access | `access.py` | Accounts and roles. Groups. Allow/deny rules per screen and per function for the portal's own screens, where **deny wins** and an **owner is never locked out**. "Check a person" shows the answer and the reason. People can request access. |
| Portal activity | `ledger.py` | One row per request: who, method, path, screen, status and time. Reports by person and by screen, plus archive download and clear. |
| Visitors | `ledger.py`, `geo.py` | Page views, visits, pages, devices, browsers, referrers and time on page. Places come from CDN headers or a local IP database, shown on a world map and an India map by state. |
| Storage | `storage.py` | Every account by space used, file count and how long it has held files. Ask a person to clean up: a second request at least 3 days after the first, a third at least 3 days after that, and from day 7 the owner may delete some or all of their items. The server enforces the dates. Requests go by email and also appear as a banner in the portal, so they work without SMTP. The host registers what counts as a file: `storage.register(items=…, delete=…, manage_hash=…)`. |
| Memory watch | `memwatch.py` | Same screen as the studio. A verdict in words with hints. Resident memory against the limit (cgroup, machine RAM, or `PORTAL_MEMORY_LIMIT_MB`). A **whole-server** view: CPU, memory, disk and bandwidth for this portal versus other services, CPU and bandwidth charts, a portal process table and an other-services table. A 4-hour memory chart. **Offenders** (requests ranked by their largest move) and recent moves. |
| How to Use | `howto.py` | Training links for each screen, shown as a button in the top bar and on the sign-in page. |
| **Resumable jobs** | `jobs.py`, `chips/jobs.*` | Long work as a list of saved steps on disk. A failure, a Stop or a server restart keeps every finished step; pressing the same button again carries on from the first missing one and never makes or pays for a step twice. Before a paid step, `jobs.may_continue` checks the budget and stops cleanly with what the rest would cost. `ready` = how much can be played right now. Generate uses it today; the studio's shorts and film shots will too. |
| **Words** | `words.py`, `chips/ui.*`, `t()`/`loadWords()` in `static/ui.js` | Every word on every screen is chip `ui.<screen>` (framework screens here, the portal's in `<portal>/chips`). A language overrides any word with `ui.<screen>.<lang>`. `core/ui_words_ratchet.json` counts sentences still typed into JavaScript per file — it may only go down (2 left: the "portal is not answering" card, which must work when the words cannot be fetched). |
| **Top search** | `find.py`, `chips/find.*`, the pill in `static/shell.js` | One box in the top bar (Ctrl/Cmd K, or `/`) that reaches every screen and every action the person may open, and jumps straight there. The rows come from the catalog, so a screen added later is searchable with no code change; what matches, what ranks first and every word are chips `find.score`, `find.keywords`, `find.settings`, `find.messages`. |
| **Chips & ops** | `engine.py`, `ops.py`, `chips/` | The architecture everything above is moving onto (see below). |
| **Rules** | `rules.py`, `rules/`, `scenarios/` | When a trigger fires and a rule's test holds on the trigger's facts, it does something: refuse, banner, email, value or flag. |
| **Ops & Chips Builder**, **Rule Chip Builder** | `builder.py`, `static/page-ocb.js`, `static/page-rcb.js`, `static/builder-ui.js` | Two screens (menu group **Build**) to see, edit, test and publish every chip and rule without touching code. **Owner-only** (admin screens: hidden from every other role, closed to grants). |

The backend needs only the standard library plus FastAPI, with no psutil and no database server.
Small state is stored in JSON under `data/`. The ledger is stored in `data/ledger.sqlite3`.

## Chips and ops: the standard architecture

This is the studio's rule: nothing is hard-coded, and every decision is data. It holds for every portal built on core/.

- An **op** (`ops.py`) is a generic, pure primitive, such as `median`, `pct`, `filter_rows`, `group_rows`, `rank_rows`, `decision_table` or `template`. It never knows the domain. An input it cannot answer returns `None`.
- A **chip** (`chips/*.json` for the framework, `<portal>/chips/*.json` for the portal's own business) is one named decision:
  - `params` are its knobs, with defaults.
  - `expr` builds the answer from ops and other chips.
  - `test_cases` prove the chip works.
  - The file name is the `chip_id`.
- The grammar matches the studio `backend/engine`:
  - `{"chip": id, "args": {}}` calls another chip.
  - `{"vop": op, ...}` calls an op, or `choose` with `cases` and `else`.
  - `{"op": "all|any|not|eq|ne|in_set|ge|gt|le|lt|at_least"}` is a tri-state test: an unknown operand never passes.
  - `"$knob"` reads a knob or an argument.
- **Python gathers facts and asks chips.** For example, `memwatch.py` reads `/proc` and then calls `engine.run("memory.verdict", facts)`. A threshold, a message, a ranking or a policy written inline in Python is a defect, and `selfcheck.py` ratchets fail on it.
- `python -m core.engine [portal/chips]` certifies every chip: references resolve, knobs exist, and every test holds. `core.install(app, catalog=…, chips="chips")` registers the portal's folder and logs any certification problem at start.
- An edited chip file is picked up within 5 seconds, with no restart. The exception is `memory.settings`, which is read once at start.

Converted so far:
- **Memory watch** (`memory.*`)
- roles (`people.*`) and builder permissions (`builder.can`)
- **People & access** (`access.decide`, `people.reset_password`)
- **the way in** (`auth.*`, `mail.texts`)
- **Portal activity and Visitors** (`ledger.*`): what is stored (path, referrer, IP network), skipped paths,
  the repeat window, device, browser and system patterns, CDN or database place, report ranges and sizes, retention
- **Storage** (`storage.stage` timeline, `storage.messages`)

- **Framework leftovers:** `access.*`, `builder.*`, `rules.*`, `howto.*`, `geo.*`, `mail.errors`,
  `mail.smtp_fields`, `mail.settings`, and every error sentence
- **The portal's own business** (`tv/chips`, 38 chips): `portal.*` (app), `narrator.*` (the AI prompt, the
  estimate and how key errors are read), `scan.*`, `manuals.*` (the HTML allow-list), `media.*`,
  `projects.*`, `source.*` (Git checks), `store.*` (models, funds)

**Everything is chips now.** `selfcheck.py` → `chips_only_check` fails when:
- an `HTTPException` sentence is written in any `.py` file,
- a converted module stops asking its chips, or
- a security chip loses `audience: admin`.

The owner-only security chips are: Git URL and branch checks, source settings (token scrub), the manual
HTML allow-list and layout, embeddable videos, and storage limits and defaults.

Left in Python on purpose:
- **plumbing:** file I/O, ffmpeg, git, the MMDB reader, the HTML parser
- **registries:** action, tone and outcome-kind names that screens and CSS depend on
- **two security walls:** `owns()` and `check_scan_path()`. As editable business chips they could open
  another account's rows or the server's disk.

## Rules: what the portal does

A chip answers a question. A **rule** acts on the answer.

```
WHEN  a trigger fires         server.sample · daily · signup.submit · page.view · upload.start
GIVEN the facts of its subject server{rss_mb, limit_mb, pct, level, title…} · signup{email, domain…} · …
IF    its test holds          chips, ops, knobs and named values over the facts
THEN  outcomes                refuse · banner · notify (email; a banner when there is no mail) · value · flag
```

- Python registers **subjects** (`rules.subject`, which facts exist), **triggers** (`rules.trigger`, where
  `rules.fire(name, facts, {"person": u})` is called and which outcomes may happen there) and **outcome
  kinds** (`rules.kind`). That is the only code a rule ever needs. A module that wants a new moment adds one
  `fire` call.
- A rule is JSON: `rule_id`, `label`, `description`, `trigger`, `priority`, `stop`, `params` (knobs),
  `values` (named values, worked out in order), `when`, `then`, `test_cases` (a scenario plus extra facts,
  and whether it should fire), `status` (published | inactive), `version`.
- Outcome text fills in `{fact}`, `{knob}` and `{value.field}`. A field written as `"$knob"` takes the
  knob's value. `cooldown_minutes` keeps a reading that arrives every few seconds from sending a hundred emails.
- **Scenarios** (`scenarios/*.json`) are named sets of facts, such as `server_kill` or `signup_disposable`.
  They are what a test or a dry run is tried on, the portal's version of the studio's sample charts.
- Shipped rules: `memory_alarm` (banner and email to the owner at warn or kill), `disk_low_daily` and
  `signup_disposable_email` (shipped switched off).

## The builders: who does what

| | Author | Editor | Owner |
|---|---|---|---|
| Open the builders, test, make scenarios | yes | yes | yes |
| Draft, and submit for review | their own work | anything | anything |
| Publish, return with a note, switch off or on, restore a version | — | yes | yes |
| Framework chips (shipped in `core/`, or `audience: admin`) | see and test only | see and test only | yes |
| Delete what the builder made; switch an op off | — | — | yes |

- The table above is the chip `builder.can`, a decision table, so it can be changed in Ops & chips.
- Roles are `owner > editor > author > member`. Sign-ups are **members** (`people.new_account_role`), who
  never see the builders.
- On 2026-09-17 every existing "editor" became a member once (`access.migrate_roles`). The owner promotes
  whoever should build.

Life of a chip or a rule:
- **draft → review → publish.** A publish is refused while any problem or failing test remains.
- **return** sends a draft back to its author with a note.
- **switch off** is refused while live chips or rules still use the item.
- **restore** turns any past version back into a draft.

Storage:
- Everything the builders write lives under `data/builder/`: drafts, published overrides, history,
  scenarios, and op switches. None of it is in git, so a save on the server can never block a `git pull`.
- A published override wins over the shipped file with the same id.
- To keep a change permanently, copy its JSON into the portal's `chips/` or `rules/`.

## A new portal in three files

**`catalog.json`** lists your screens. Core adds its own Admin screens after them.

```json
[
  {"id": "orders", "label": "Orders", "group": "Work", "icon": "book",
   "functions": [{"id": "refund", "label": "Issue a refund"}]},
  {"id": "reports", "label": "Reports", "group": "Work", "icon": "pulse", "admin": true}
]
```

A screen marked `admin` is for the portal owner only. No rule, group or access request can open it
to anyone else. Core's own screens are all `admin`: People & access (including sign-up and SMTP
email), Portal activity, Visitors, Storage, Memory watch and How to Use pages. Every other screen is open to
all accounts until a rule denies it.

**`app.py`**

```python
from fastapi import Depends, FastAPI
import core
from core.access import screen

app = FastAPI()
core.install(app, catalog="catalog.json")

@app.get("/api/orders")
def orders(u: dict = Depends(screen("orders"))): ...

@app.post("/api/orders/{oid}/refund")
def refund(oid: str, u: dict = Depends(screen("orders", "refund"))): ...
```

Every `/api` route needs a guard: `screen(...)`, `core.owner` or `core.signed_in`. The only exception
is a route you mean to be public. See `framework_check` in `tv/selfcheck.py`, which fails the build
on a route with no guard.

**`static/app.js`**

```js
import { startPortal } from '../core-static/shell.js';
import { ordersPage } from './page-orders.js';

startPortal({
  views: { orders: ordersPage, reports: reportsPage },   // one per catalog id
  pitch: () => '<h2>Orders, handled.</h2><p class="sub">…</p>',
  landing: '#/orders',
});
```

`index.html` loads `core-static/portal.css` first, then the portal's own CSS. A view is
`async (host) => { host.innerHTML = … }`. Import `api`, `modal`, `toast`, `busy`, `pageHead` and the
rest from `core-static/ui.js`.

## Rules the framework keeps for you

- **Body-free ledger.** It stores no request bodies, no query strings and no tokens, and it cuts IP
  addresses to /24 (IPv4) or /48 (IPv6).
- **One resolver.** The menu, the API guard and the Check tab all call `access.decide()`.
- **Owners are never locked out.** The admin screens and SMTP belong to owners alone, and only an
  owner can create or remove another owner.
- **Tracking comes free.** Every screen the shell shows and every request the server answers is
  recorded. A new page needs no tracking code.

## Environment

| Variable | Default | Meaning |
|---|---|---|
| `PORTAL_DATA` | `<portal>/data` | Where everything is stored |
| `PORTAL_BASE` | empty | The mount path when hosted under a path, e.g. `/tv` |
| `PORTAL_OWNER_EMAIL` | empty | Reserves the owner seat for one address |
| `PORTAL_HTTPS` | off | Sets the `Secure` flag on the session cookie |
| `PORTAL_COOKIE` | `portal_session` | Session cookie name |
| `PORTAL_PRODUCT_NAME` | `Portal` | Name shown before the owner sets one |
| `PORTAL_SESSION_DAYS` | 14 | How long a sign-in lasts |
| `PORTAL_AUTH_PER_MINUTE` | 20 | Sign-in calls allowed from one address per minute |
| `PORTAL_TRUSTED_PROXY` | `nginx` | Where the caller's address comes from, for rate limits, Activity and the maps. `nginx`: `X-Real-IP`, else the LAST `X-Forwarded-For` hop. `cloudflare`: `CF-Connecting-IP` (firewall the origin to Cloudflare's ranges). `none`: the socket peer. The FIRST `X-Forwarded-For` entry is never trusted — the caller writes it. Any other value refuses to start |
| `PORTAL_MEMORY_LIMIT_MB` | detected | Overrides the memory limit Memory watch reports against |
| `PORTAL_DISK_PATHS` | empty | Extra folders (os.pathsep list, e.g. a backup folder) counted as this portal's disk |

The Training & Video Portal still sets `TV_*` variables. `tv/store.py` maps them onto `PORTAL_*`.

| `PORTAL_GEOIP` | on | `off` stops the location lookup and its monthly download |
| `PORTAL_GEOIP_DB` | empty | Path to your own GeoLite2-City or DB-IP City `.mmdb`; nothing is downloaded |

## Places: CDN headers, else a local database

Country, region and city come from the `cf-ipcountry` / `cf-region` / `cf-ipcity` request headers
(or their Vercel equivalents) when a CDN sends them. Without one, `geo.py` looks the visitor's full
address up in a local copy of **DB-IP "IP to City Lite"** (CC BY 4.0, credited under the maps), then
the address is cut to its /24 or /48 as before. No address is sent to any service.

- The first start downloads the database into `data/geo/` in the background, and it refreshes
  monthly. The server needs outbound HTTPS to `download.db-ip.com`. Until the file is open, places
  read "unknown" and the Visitors screen says why.
- When the database opens, views stored without a place are filled in from their stored network.
- The reader is about 100 lines of stdlib code (`mmap`). No `maxminddb` package is needed.
- The Visitors screen draws a **world map by country** and an **India map by state**. Both are the
  the studio maps (`static/geo/`, copied from `src/components/admin/geo/`), loaded only on that screen.
