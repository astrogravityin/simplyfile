---
name: screen-test
description: >
  HARD checklist for testing any screen change in AstroStage (and every ValueStream portal) BEFORE telling the owner it
  works. Use whenever you verify a change in a browser (Playwright, the Browser pane, a tour), say "tested", "verified",
  "works", or hand the owner something to check on prod. Built 2026-10-29 after the owner found, while showing it, a
  progress window my test had "passed": it was in the page but hidden BEHIND the AstroConnector window.
---

# Screen test — test what the PERSON sees, not what the page holds

The owner must never be the first to find a problem. A test passes only when a person sitting at the screen would
agree. "The element exists" is NOT a pass.

## 0. Before the test: write the scenario as the person lives it

Number each step in the person's words ("A opens AstroConnector, draws, presses Close"). For every step write what they
should SEE, how long they WAIT, and what they must NOT lose. Two people (A has it, B does not)? Run two browsers at once,
one per account, in the same chat. Test the owner's exact scenario, word for word, before any variation.

### 0a. The scenario matrix for anything shared between people (calls, chats, connectors, boards)

Owner 2026-10-29 found two more holes the same day ("did you really test all scenarios?"). For a shared thing, run
EVERY cell, in two (or three) browsers at once - not only the path the owner typed:

| Who acts | Action | While the other person… | What the other must see |
|---|---|---|---|
| Opener (A) | open / play / Close | has it open / closed / never opened | closed for both when A closes |
| Other (B) | open / play / Close | A has it open / A closed it / A left the chat | live, or a copy, never stuck |
| Either | share a screen | the other has the shared thing open | the share, on top |
| Either | lose the network 40 s, then 100 s+ | the other stays | back by itself, mic + camera as before, no stray ring |
| Either | phone in the background, laptop asleep | the other keeps talking | the call is NOT ended by the server |
| Same person | joins on a second device / tab | first device in the call | told "moved", no seat or call lost |
| Either | reload / close the tab | the other is still in | the other is not dropped |

A row the scenario cannot reach on this machine (no LiveKit admin locally, no real phone) is named in the report as
"not run (why)", never skipped silently.

## 1. The checklist (every item, every changed screen)

| # | Check | How (Playwright) | The mistake it stops |
|---|---|---|---|
| 1 | **Visible, on top** - not just present | `elementFromPoint` at the element's centre is the element or inside it (helper below). Never `locator.count()` alone | 2026-10-29: progress window z-1500 under the 9000 AstroConnector window: "count 1", owner saw nothing |
| 2 | **Shown fast** - every wait over ~1 s shows a progress window (UEW) at once | Time from the press to the window being VISIBLE (check 1); must be under 0.3 s. Then time to done | Send showed nothing for 3.6 s; Pages button blank for 1.5 s |
| 3 | **Paints before heavy work** | The progress window is visible while the work runs, not only after | Picture-making held the browser: the window came after the work |
| 4 | **Works end to end** - the result arrives where the person looks | Read it back: the message in the chat, the row in the list, the saved session after reload | "Sent" toast with nothing in the chat |
| 5 | **Every role** | Owner/admin, a user WITH the feature, a user WITHOUT it, a guest. Same steps each | Copy for people without the connector |
| 6 | **Close, reopen, reload** | Close it, open again: same state? Reload the page: same? The other person's view? | Work lost on close |
| 7 | **Sizes and themes** | 1366 light, 390 dark (phone, touch), 768 dark | Pro column cut on phone; Save under the fold |
| 8 | **Escape and Close** | Escape closes the top thing only; Close visible without scrolling | Popups owner reported 100+ times |
| 9 | **Words** | Read the visible text: no keys (`pages.step_keep`), no "undefined", sentence case, the time names its zone | Missing chip word showed its key |
| 10 | **No errors** | `pageerror` and console errors = 0; failed requests (4xx/5xx) = 0 for the feature's calls | 401s on a test account looked like "slow" |
| 11 | **Screenshot read** | Take one per changed state and LOOK at it before saying it works | A test "passed" over a covered window |
| 12 | **Fails when broken** | Undo the fix on a COPY (or in memory) and show the test fails | A guard that never bites |
| 14 | **First open is slow? A UEW is there** (owner 2026-10-30) | Open the screen cold (first visit, empty cache, through the Try it / prod address, not localhost). Any blank or white screen longer than ~1 s with no progress window = FAIL. Check the UEW EXISTS for every step you expect to be slow - page load, chart, backend, build, AI | REQ-0055 Try it: white page for minutes, nothing said why |
| 15 | **The project's own tests RAN** | Run them yourself and paste the pass/fail count. Written-not-run = FAIL row | REQ-0055: main test written, never run, 1 of 119 failed |
| 16 | **The owner's 10 points** answered from evidence | Reuse first, chips and ops, professional narration + SVG, Guide me, Tour Video, UI on laptop/tablet/phone light+dark, tested on all three, agent scope, MCP scope, status/pending/next - each with its proof | The owner pasted this list many times; now it is the test |
| 13 | **In its REAL home, on every device - opened, not just listed** | The feature is clicked open where people meet it (a connector: ValueConnect -> a chat -> Connectors -> the connector -> a game/board on screen; also Connect Store) at 390 phone + touch, 768 tablet + touch AND 1366 laptop, then used once (a move, a mark). A test page / harness / laptop-only pass does NOT count | 2026-10-30 PlayConnector: boards checked in a harness at 3 sizes, GamyFy at 3 sizes, ValueConnect only on the laptop - the owner could SEE PlayConnector on phone and tablet but could not OPEN it |

## 2. Environment traps (rule them out FIRST, they cost hours)

- Local backend slow or restarting (other sessions edit `.py`): `curl http://localhost:8001/public-portal/build`
  three times; wait for three fast 200s before blaming the code.
- Test sign-ins expire or are invalidated: a 401 on `/connect/me` = mint fresh local tokens
  (`backend/` + `D:/Temp/mdshots/mint_local.py <users>`), never print them.
- An "optional skipped" step in a tour = a defect, not a pass.
- Local calls use the PROD call server (`.env` LIVEKIT_URL = wss://api.astrostage.in): every local call test joins real
  prod LiveKit rooms. Keep them short, and when reading the prod LiveKit log count them out (browser HeadlessChrome,
  local user ids). 2026-10-30: 88 of 94 "drops" in the log were my own tests, not users.
- A count that is right for the wrong reason (a sent picture of the chart in the chat looks like the open tool):
  check the element's own `data-` mark AND that it is visible.

## 3. Visibility helper (paste into any Playwright test)

```python
ON_TOP = """(sel) => { const d = document.querySelector(sel); if (!d) return false;
  const c = d.firstElementChild || d; const r = c.getBoundingClientRect();
  if (!r.width || !r.height) return false;
  const e = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2); return !!e && d.contains(e); }"""
visible_on_top = lambda pg, sel: pg.evaluate(ON_TOP, sel)
```

Timing a wait: press -> poll every 50 ms for `visible_on_top(pg, '[data-progress-dialog]')` -> record seconds to
visible and seconds to done. Report both numbers.

## 4. The report to the owner

Every "tested" claim lists: the scenario steps (numbered), each with PASS/FAIL and the evidence (number, read-back,
screenshot), sizes/themes run, roles run, and anything NOT tested with the reason. Never "works" without that table.

## Never

- Never report "works" from `count()`, a toast, or a status code alone.
- Never let the owner find it first: if the owner can find it by clicking, the test should have clicked it.
- Never test only my own account when the change is about another role.
- Never skip a step because the local site is slow - wait for it, or say plainly which step was not run.
- Never say "tested on phone / tablet / laptop" for a piece checked outside the screen people use it in. Name WHERE each
  size was checked; "harness only" is a FAIL row in the report, not a pass (2026-10-30, PlayConnector).
- Never sign a headless test in with a saved storage_state alone - it lacks the session mark (feedback tour sign-in);
  drive it through `make_tour.py` (a raw tour JSON with `viewport` + `--check`) so the test signs in like the tour does.

## A page that hands work to a phone app (2026-10-29, Brahma Muhurta: an 11:39 app alarm did not ring at all)

- The page stood down because the app said "the phone holds it", and the phone could not sound it (notifications off).
  Testing only the browser path missed it.
- Test BOTH paths: plain browser AND the app path with a fake `window.Capacitor.Plugins.<Name>` in the page (each
  answer: works / refuses / older app without the method). A page may stand down only on a CONFIRMED capability, and
  must take the job back when the app reports it did not do it.
- Fake clocks move FORWARD from the page's real open time and use the job's own moment (its id), never "today's date"
  near midnight.
