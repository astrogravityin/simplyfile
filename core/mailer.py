"""Sending mail, so people can sign themselves up and reset their own passwords.

The owner fills in one SMTP account in Setup. Gmail is the common case and the fiddly one, so the
errors below translate its refusals into what actually has to change.

stdlib `smtplib` only — nothing to install. Mail that cannot be sent raises with a sentence the
owner can act on; it is never swallowed into a log nobody reads.
"""
from __future__ import annotations

import json
import smtplib
import socket
import ssl
import time
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path

from core import engine, ops, store

ROOT = Path(__file__).resolve().parent.parent


def settings() -> dict:
    """Default port and security, the connection timeout: chip mail.settings."""
    return engine.run("mail.settings")


def smtp_fields() -> dict:
    """{field: {label, secret, hint}} in form order — chip mail.smtp_fields (the field names are the stored keys)."""
    return {r["name"]: {k: v for k, v in r.items() if k != "name"} for r in engine.run("mail.smtp_fields")["fields"]}


def defaults() -> dict:
    s = settings()
    return {f: "" for f in smtp_fields()} | {"port": str(s["default_port"]), "security": s["default_security"]}


def site_sender(root: Path | None = None) -> dict:
    """The sender the portal's own site file sets (2026-10-16 owner: display names did not match the app - every new site
    had copied smtp.json, sender name and all, from the first site found). File and block: chip mail.settings. The block's
    from_email / from_name; no from_name = the file's label. No file, or nothing in it = {} (smtp.json alone, as before)."""
    k = settings()
    try:
        doc = json.loads(((root or ROOT) / str(k["site_file"])).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(doc, dict):
        return {}
    blk = doc.get(str(k["site_block"])) if isinstance(doc.get(str(k["site_block"])), dict) else {}
    got = {"from_email": str(blk.get("from_email") or "").strip(), "from_name": str(blk.get("from_name") or doc.get("label") or "").strip()}
    return {f: v for f, v in got.items() if v}


def config() -> dict:
    """smtp.json (server, login, password) with the site file's sender over it - what Setup shows and what is sent."""
    return defaults() | store.read("smtp", {}) | site_sender()


def save(patch: dict) -> None:
    """A BLANK secret means "keep the stored one" — the browser is never sent the real value, so an
    empty box is ignorance, not an instruction to wipe it. Whitespace inside a secret is dropped:
    Google prints an App Password as four groups of four, and people paste it exactly as shown."""
    fields = smtp_fields()
    with store._LOCK:                        # noqa: SLF001 - part of the store's own tooling
        cur = store.read("smtp", {})
        for field, value in (patch or {}).items():
            if field not in fields:
                continue
            text = str(value if value is not None else "")
            if fields[field]["secret"]:
                text = "".join(text.split())
                if not text:
                    continue
            cur[field] = text.strip()
        store.write("smtp", cur)


def configured() -> bool:
    c = config()
    return bool(c.get("host") and c.get("from_email"))


def error_kind(error: Exception) -> str:
    """Which kind of failure this is — a fact about the exception, not a sentence."""
    if isinstance(error, smtplib.SMTPAuthenticationError):
        return "auth_rejected"
    if isinstance(error, smtplib.SMTPSenderRefused):
        return "sender_refused"
    if isinstance(error, smtplib.SMTPRecipientsRefused):
        return "recipient_refused"
    if isinstance(error, (socket.timeout, TimeoutError)):
        return "timeout"
    if isinstance(error, ssl.SSLError):
        return "tls"
    if isinstance(error, (socket.gaierror, ConnectionRefusedError, OSError)):
        return "unreachable"
    return "other"


def _friendly(error: Exception, c: dict) -> str:
    """What the owner has to change, not what the library called it: the sentence is chip mail.errors."""
    kind = error_kind(error)
    if kind == "auth_rejected" and "gmail" in (c.get("host") or "").lower():
        kind = "auth_rejected_gmail"
    return engine.say("mail.errors", kind, from_email=c.get("from_email"), host=c.get("host"), port=c.get("port"),
                      timeout=settings()["timeout_seconds"], error=error, kind=type(error).__name__)


def send(to: str, subject: str, text: str) -> None:
    """One plain-text message. Plain text on purpose: it lands in the inbox, not the promotions tab,
    and there is nothing in these mails that wants formatting."""
    c = config()
    if not configured():
        raise RuntimeError(engine.say("mail.errors", "not_configured"))
    msg = EmailMessage()
    msg["From"] = formataddr((c["from_name"] or "", c["from_email"]))
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)

    k = settings()
    port = int(c["port"] or (k["ssl_port"] if c["security"] == "ssl" else k["starttls_port"]))
    timeout = float(k["timeout_seconds"])
    tries = max(1, int(k.get("tries") or 1))
    for n in range(1, tries + 1):
        try:
            _deliver(c, port, timeout, msg)
            return
        except Exception as e:  # noqa: BLE001 - every failure becomes one sentence the owner can act on
            if n < tries and error_kind(e) in (k.get("retry_kinds") or []):
                time.sleep(float(k.get("retry_wait_seconds") or 0))   # a passing timeout: once more (chip mail.settings)
                continue
            raise RuntimeError(_friendly(e, c)) from e


def _deliver(c: dict, port: int, timeout: float, msg: EmailMessage) -> None:
    if c["security"] == "ssl":
        server = smtplib.SMTP_SSL(c["host"], port, timeout=timeout, context=ssl.create_default_context())
    else:
        server = smtplib.SMTP(c["host"], port, timeout=timeout)
    with server:
        server.ehlo()
        if c["security"] == "starttls":
            server.starttls(context=ssl.create_default_context())
            server.ehlo()
        if c["username"]:
            server.login(c["username"], c["password"])
        server.send_message(msg)


# --- the messages this portal sends: their words are the chip mail.texts ------------------------------

_KEYS = {"code_signup": ("code_subject_signup", "code_text_signup"), "code_reset": ("code_subject_reset", "code_text_reset"),
         "invite": ("invite_subject", "invite_text"), "reset_by_owner": ("reset_by_owner_subject", "reset_by_owner_text"),
         "test": ("test_subject", "test_text"), "signup_exists": ("signup_exists_subject", "signup_exists_text")}


def compose(kind: str, **values) -> tuple[str, str]:
    """(subject, text) for one of the portal's emails, from chip mail.texts with the values filled in."""
    texts = engine.run("mail.texts")
    subject_key, text_key = _KEYS[kind]
    values = {"change_note": texts.get("change_note", "")} | values
    return ops.template(texts[subject_key], values), ops.template(texts[text_key], values)


if __name__ == "__main__":  # ponytail: one runnable self-check
    gm = {"host": "smtp.gmail.com", "port": "587", "from_email": "me@gmail.com"}
    assert "App Password" in _friendly(smtplib.SMTPAuthenticationError(535, b"bad"), gm)
    assert "App Password" not in _friendly(smtplib.SMTPAuthenticationError(535, b"bad"),
                                           {"host": "mail.example.com"})
    assert "starttls" in _friendly(ssl.SSLError("wrong version number"), gm)
    assert "me@gmail.com" in _friendly(smtplib.SMTPSenderRefused(553, b"no", "x"), gm)
    assert _friendly(ValueError("odd"), gm) == "ValueError: odd" and set(smtp_fields()) >= {"host", "password"}
    assert smtp_fields()["password"]["secret"] is True and defaults()["security"] == settings()["default_security"]
    subject, body = compose("code_reset", product="My Portal", code="123456", minutes=60)
    assert "123456" in body and "60 minutes" in body and "My Portal" in subject and "123456" in subject
    import tempfile                              # the site file sets the sender; none = smtp.json alone
    t = Path(tempfile.mkdtemp())
    assert site_sender(t) == {}
    (t / settings()["site_file"]).write_text(json.dumps({"label": "ExampleFy"}), encoding="utf-8")
    assert site_sender(t) == {"from_name": "ExampleFy"}, "no mail block: the label is the display name"
    (t / settings()["site_file"]).write_text(json.dumps({"label": "ExampleFy", settings()["site_block"]: {"from_email": "a@x.example", "from_name": "Ex"}}), encoding="utf-8")
    assert site_sender(t) == {"from_email": "a@x.example", "from_name": "Ex"}
    calls = []                                   # one automatic retry on a passing timeout, never on a refused password

    def flaky(c, port, timeout, msg):
        calls.append(1)
        if len(calls) == 1:
            raise smtplib.SMTPServerDisconnected("Connection unexpectedly closed: The read operation timed out")
    real, real_cfg, real_ok = _deliver, config, configured
    globals().update(_deliver=flaky, config=lambda: gm | {"security": "starttls", "username": "", "password": "", "from_name": "X"},
                     configured=lambda: True)
    try:
        send("to@x.example", "s", "t")
        assert len(calls) == settings()["tries"] == 2, calls
        calls.clear()
        globals()["_deliver"] = lambda *a: (_ for _ in ()).throw(smtplib.SMTPAuthenticationError(535, b"bad"))
        try:
            send("to@x.example", "s", "t")
            raise AssertionError("a refused login passed")
        except RuntimeError as e:
            assert "App Password" in str(e)
    finally:
        globals().update(_deliver=real, config=real_cfg, configured=real_ok)
    print("core.mailer self-check OK")
