# AUTH — the sign-up and sign-in standard for every portal

Owner's list (2026-09-17). Look and wording follow **astrosahai.in** (`src/components/individual/AstroSahaiHome.tsx`
`SahaiLoginCard`, `src/components/common/ForgotPassword.tsx`). The admin reset follows **AstroStage → Portal Admin
→ User Access → Reset Password** (`src/components/admin/UserAccessManager.tsx` `ResetPasswordModal`,
`backend/routers/portal_admin.py` `set-password`). Where those have a known gap, this standard fixes it
(marked **FIX**).

Every number, pattern, message and "what comes next" below is a **knob on an `auth.*` chip**, not a constant
in Python (see SKILL.md §1). The defaults written here are the chip defaults.

---

## 1. The card

One card, three tabs: **Sign in · Sign up · Forgot password** (Forgot is also a link under Sign in).
Heading "Sign up" on the sign-up tab, "Enter <Portal name>" otherwise. Each multi-step flow shows a
progress rail, e.g. `1 · Details › 2 · Code › 3 · Password`. Primary button shows a spinner while busy.
Errors show beside the field they are about; outcomes show as a toast.

| # | Owner's item | Where |
|---|---|---|
| 1 | Sign-up page like astrosahai.in | §2 |
| 2 | Display name | §2 step 1 |
| 3 | User name | §2 step 1 |
| 4 | Email id | §2 step 1 |
| 5 | Get confirmation code by email | §2 step 1 → §4 |
| 6 | Enter code — first time (verify email, only then continue) or during forgot password | §2 step 2, §3 step 2 |
| 7 | Password | §2 step 3 |
| 8 | Confirm password | §2 step 3 |
| 9 | Forgot password | §3 |
| 10 | Enter code | §3 step 2 |
| 11 | Change password | §3 step 3, §5 |
| 12 | Owner/admin can change the password in User Access | §6 |

---

## 2. Sign up

**Step 1 — Details**

| Field | Label / placeholder | Rule (chip `auth.signup_fields`) |
|---|---|---|
| Display name | "Display name" / "How your name appears" | required, 1–60 characters after trim; any script |
| User name | "User name" / "letters, numbers, . _ -" | required, 3–30, `^[a-z0-9][a-z0-9._-]*$` after lower-casing, not in `reserved` (admin, owner, root, support, system, api, …), unique |
| Email | "Email" / "you@example.com" | required, valid shape, lower-cased, unique |

Button **"Send verification code"**. Note under it: "We email a 6-digit code to confirm it's you first."
Client pre-checks shape only; the server decides (never re-validate on the page what the server decides).
User name and email uniqueness are checked **when the account is created** (§2 step 3) and answered in a
way that does not reveal other people's accounts beyond what sign-up inherently must (see §8).

**Step 2 — Enter code** ("Verification code" / "6-digit code from your email")
Buttons **"Confirm email"**, **"Change details"**, and a quiet "Didn't get it? Send a new code"
(disabled for `resend_after_s`, default 60 s, with a countdown).

**FIX (AstroSahai checks only the length on the page):** the code is checked **on the server** here —
`POST /api/auth/code/check {email, purpose:"signup", code}` → `{proof}`. `proof` is a single-use,
short-lived (`proof_ttl_s` 900) token bound to *email + purpose*. Wrong code → "That code is not right or has
expired." After `max_attempts` (5) wrong tries the code is burned: "Too many tries. Send a new code."
Only a valid code moves to step 3: "Email confirmed. Now choose your password."

**Step 3 — Password**

| Field | Label / placeholder | Rule (chip `auth.password_ok`) |
|---|---|---|
| Password | "Password" / "At least 8 characters" | `min_length` 8, `max_length` 128, not equal to user name or email, not in a small common-password list knob |
| Confirm password | "Confirm password" / "Repeat password" | equals Password: "Passwords do not match." |

Show/hide eye on both; live "8+ characters ✓ · matches ✓" hints (hints only — the server decides).
Button **"Create account"** → `POST /api/auth/signup {display_name, username, email, password, confirm, proof}`.
Server re-checks every field, consumes `proof` **after** the uniqueness checks pass (**FIX:** AstroSahai burns
the code before "already registered" and wastes it), creates the account `verified: true`, role from chip
`auth.new_account_role` (default the portal's normal role), signs the person in (session cookie), logs
`SIGNUP`. If the proof expired: back to step 2 with "Your code expired. Send a new one."

---

## 3. Sign in and Forgot password

**Sign in:** "User name or email" / "Enter user name or email" + "Password" / "Enter password", button
**"Sign in"**, link **"Forgot password?"**. Server matches the trimmed, lower-cased identity against user
name OR email. Wrong → 401 "That user name or email and password do not match." (same text whether the
account exists). Rate limit per IP and per identity; lockout after `lock_after` (8) wrong passwords for
`lock_for_s` (900): "Too many wrong passwords. Try again in N minutes, or use Forgot password."
An unverified account (only possible when created without mail, §7) is asked to verify first.

**Forgot password — step 1:** "User name or email", button **"Send reset code"** →
`POST /api/auth/code/send {identity, purpose:"reset"}`. **Always** answers
"If that account exists, we've emailed a 6-digit code to its address." — including for suspended accounts
and accounts without email (**FIX:** AstroSahai answers 403/400 there, which reveals the account).

**Step 2 — Enter code:** "Reset code" / "6-digit code from your email", button **"Continue"**,
"Didn't get it? Send a new code". `POST /api/auth/code/check {identity, purpose:"reset", code}` → `{proof}`.
Unknown account and wrong code give the SAME answer (**FIX:** AstroSahai returns 404 "User not found").

**Step 3 — Change password:** "New password", "Confirm new password" (rules = `auth.password_ok`), button
**"Set new password"** → `POST /api/auth/reset {identity, proof, password, confirm}`. Server sets the password,
marks the email verified (the code proved the address), **revokes every session** of that account, clears
`must_change_password`, logs `PASSWORD_RESET`. Done screen: "Password updated. Sign in with your new password."
button **"Back to sign in"**.

**Never again (2026-10-01) — other tabs signed you back out.** The token lives in SHARED localStorage; a
tab's in-memory axios default header does not. Every client (axios AND fetch) reads the token from storage
per request (`api.ts` request interceptor + `authFetch`). Otherwise a sign-in in tab A makes tab B's
bottom-bar poll go tokenless → 401 "Not authenticated" → 401 recovery wipes the shared token → tab A out.
Guard: `src/services/adminWorkspace.test.ts` ("axios calls carry the stored token").

---

## 4. Codes

- 6 digits from `secrets` (length is a knob). Delivered only by email (WhatsApp later as another channel of the
  same code — hidden/"coming soon" until configured).
- Stored **hashed** (sha-256 of code + per-portal secret), never plain (**FIX**), never logged, never in the
  activity ledger, never in a URL.
- Keyed by *email + purpose*; issuing a code replaces only the code of **the same purpose** (**FIX:** AstroSahai
  deletes every purpose, so a login code cancels a pending reset).
- TTL knobs: `signup_ttl_s` 900, `reset_ttl_s` 3600. Single use. `max_attempts` 5 then burned.
- Send throttle per address (`sends_per_hour` 3) and per IP; same success message when throttled.
- **Recent mail (2026-10-06).** Every code / notice attempt is logged (`store.log_mail` -> `mail_log`, never the code)
  with its outcome: `sent`, `failed` + the mail.errors sentence, `throttled` + when the next may go, `no_account`,
  `no_email`. The owner reads it on Setup -> Email -> Recent mail (GET `/api/smtp/log`, owner only); tones are chip
  `mail.outcomes`, words `ui.access` `ml_*`. Why: "the reset code never came" took an SSH session, and the code had
  been sent all along - Gmail filed it under a label. A successful send printed nothing, so only a log proves it.
  The public answer stays identical for everyone. Guard: tv/selfcheck.py "Recent mail" block.

---

## 5. Change password (signed in) and forced change

User menu → **"Change password"**: "Current password", "New password", "Confirm new password" →
`POST /api/auth/password {current, password, confirm}`. Wrong current → "Your current password is not right."
New must differ from current. On success: other sessions revoked, this one kept, toast "Password changed."

**Forced change** (after an admin reset with "Require change at next login"): the portal shows only
"Set a new password" — "Temporary password", "New password", "Confirm new password", buttons
**"Update password"** and **"Sign out instead"**.
**FIX:** enforced **on the server** — while `must_change_password` is set, every route except
`/api/auth/password`, `/api/auth/signout` and bootstrap answers 403 `{"must_change_password": true}`
(AstroStage enforces it only in `App.tsx`, and astrosahai.in skips the check entirely).

---

## 6. Owner/admin reset — User Access → Reset Password

**Tenant wall:** a password is the ACCOUNT's, and one account spans every tenant — so reset is
portal-wide: refused from inside a tenant (AstroStage `set_user_password` → `admin_scope.portal_only`),
and the button is hidden in a Workspace Admin's User Access. A tenant admin never resets, deletes or
reads another tenant's view of a person (SKILL.md §2 "Tenant wall").

Row button **"Reset Password"** in User Access (owner-only screen) opens a dialog (pinned footer):

- Header: "Reset Password", the person's display name and email/user name.
- "New password" / "Type or auto-generate" with Show, Copy and **"Auto-generate"**.
  **FIX:** generation happens on the server with `secrets` (14 chars, lower+upper+digit, no look-alikes) —
  AstroStage generates in the browser with `Math.random`.
- ☑ "Require change at next login" (on by default) — "Signs them out everywhere and forces a new password."
- ☐ "Email the new password to the user" (off; disabled without an email or without SMTP) —
  "Sends through the portal's SMTP."
- Buttons **"Cancel"**, **"Set password"** (spinner while busy).
- Result: "Temporary password" with Copy, then one of "Emailed to the person." / "Email not sent: <reason>" /
  "Share this password securely with the person." and **"Done"**.

`POST /api/core/people/{id}/password {password?, generate, require_change=true, send_email=false}` — owner only
(404 for anyone else). Rules = `auth.password_ok`. Always revokes the person's sessions. Logs
`ADMIN_RESET_PASSWORD` with `{require_change, generated, emailed}` (never the password). Returns the password
only when generated or not emailed. The owner resetting their OWN password here is refused — use Change password.
Command-line fallback for a locked-out owner stays (`admin.py passwd`, password typed at a prompt).

---

## 7. When the portal cannot send email

The owner rule "gate nothing on an unconfigured dependency" still holds, and so does "verify first, then
continue". Chip `auth.no_mail_policy` decides; default `verify_later`:

| Situation | Default behaviour |
|---|---|
| Sign up, no SMTP | Step 2 is skipped; account created `verified: false`; a banner asks the person to confirm their email once mail works. Owner sees a warning on Setup: "Email is not set up — sign-ups are not verified and Forgot password cannot send codes." |
| Forgot password, no SMTP | Card still shows **Forgot password**; step 1 answers "This portal can't send email yet. Ask the portal owner to reset your password." (it does NOT hide the link — tv.valuestream.in hid it, and people had no way back). |
| Owner wants strict | Knob `no_mail_policy: "closed"` — sign-up tab says "Sign-up opens once the owner sets up email." |

---

## 8. Endpoints (framework names) and guards

| Method + path | Who | Does |
|---|---|---|
| POST `/api/auth/code/send` | anyone, throttled | email a code for `signup` or `reset`; same answer always |
| POST `/api/auth/code/check` | anyone, throttled | code → single-use `proof` |
| POST `/api/auth/signup` | anyone with a signup `proof` | create + sign in |
| POST `/api/auth/signin` | anyone, rate limit + lockout | user name or email + password |
| POST `/api/auth/reset` | anyone with a reset `proof` | new password, revoke sessions |
| POST `/api/auth/password` | signed in | change (or forced change) |
| POST `/api/auth/signout` | signed in | **revoke the session on the server** (**FIX:** AstroStage logout only logs) |
| POST `/api/core/people/{id}/password` | owner | admin reset |
| GET `/api/smtp/log` | owner | Recent mail: every code / notice attempt and its outcome, newest first |

Chips: `auth.signup_fields`, `auth.password_ok`, `auth.code_policy`, `auth.limits`, `auth.no_mail_policy`,
`auth.new_account_role`, `auth.next_step` (decision table for the card's steps), `auth.messages` (every sentence).

Sign-up is the one place that must reveal "that user name / email is taken" — say it only at step 3, after a
valid proof, so it cannot be used to probe addresses the prober doesn't own.

Selfcheck walks all of it end to end with a fake mailer: sign up (bad code rejected, attempts burn, proof
single-use, duplicate refused without burning the proof), sign in by user name and by email, lockout, forgot
(identical answers for stranger / suspended / no-email), reset revokes sessions, forced change blocks other
routes, admin reset owner-only and 404 for others, no code or password ever in the ledger. Each guard
bite-tested.

---

## 9. Where things stand (2026-09-17)

**tv.valuestream.in (tv/core) implements this standard as of 2026-09-17 (late).**
- **Endpoints:** `/api/auth/code/send`, `/code/check`, `/signup`, `/signin` (by `identity`), `/reset`,
  `/password`, `/invite`, and `/api/core/people/{id}/password`.
- **Forced change:** enforced by the `force_password_change` middleware.
- **Chips:** `auth.limits`, `auth.code_policy`, `auth.no_mail_policy`, `auth.signup_open`,
  `auth.username_problem`, `auth.display_name_problem`, `auth.email_problem`, `auth.password_problem`,
  `auth.signin_gate`, `auth.must_change_allows`, `auth.messages`, `people.reset_password`, `access.decide` and
  `mail.texts`. Chip `access.decide` is the resolver behind the menu, every guard, and "Check a person".
- **Store:** codes are hashed with a per-portal secret (`data/secret.json`), and each is keyed by address and
  purpose. Proofs are single-use tokens. User names are migrated once (`store.ensure_usernames`).
- **Walkthrough:** `tv/selfcheck.py` walks every step. A ratchet fails if a policy, a number or a sentence
  returns to `auth.py`, `access.py`, `mailer.py` or `store.py`.
- **Removed:** the old `#/verify` and `#/reset` email links. Invitations are still links (`#/invite`).

**AstroStage / astrosahai.in — gaps the FIX notes above close:** sign-up code checked only for length in the
browser; code consumed before duplicate check; forgot/reset reveal account existence (403/400/404); codes
stored plain; one purpose cancels another; admin password generated with `Math.random`; forced change not
enforced on the server (and skipped on astrosahai.in); logout does not revoke the token; no lockout.

## 10. Never sign out on a blip (2026-10-10)

Only a refused token (401, or `X-Auth-Stale`) ends a session. A slow, aborted or failed profile call (`/auth/me`) keeps the token and asks again a few seconds later - AstroStage's AuthContext wiped the session whenever `/auth/me` failed on a browser with no cached profile, so busy machines and recordings were signed out. Guard: `src/contexts/authKeepsSessionOnBlip.test.tsx`.

## 11. One sign-in across every site of the family (single sign-on, 2026-10-27)

Owner: "signed in to AstroStage, AstroGaami asks me to sign in again." Three holes, all fixed:

1. A redeemed hand-off code stored the token ONLY; the session reader needs token + username + this
   tab's live mark, so the target read as signed out. Redeem returns `username`; the client writes the
   session through ONE helper (`keepSession`, `src/services/handoff.ts`) and the storage keys live there
   once (AuthContext imports them). A hand-off writes exactly what the sign-in reader reads.
2. A plain link or bookmark to another host carried nothing. A workspace host with no session bounces
   once to the `home` site (row `home: true` in chip `access.portal_sites`) as `#sso=<url>`; home,
   signed in, sends a one-time code back (`#handoff=`, never a token); signed out, sends the visitor
   back with `#sso=none` (only to an origin `GET /auth/handoff/sso` calls family) and the normal
   sign-in shows. One bounce per `ttl_seconds` per tab, so it can never loop.
3. The workspace route chose the sign-in page while the stored session was still loading: a signed-in
   person saw it flash. Every route waits for `auth.isLoading` before showing the sign-in page.

Guards: `src/services/handoff.test.ts` (session keys written, bounce both ways, no open redirect,
no flash; bitten on a copy), `backend/tests/test_auth_handoff.py` (redeem names the person, sso
home + family-only return).
