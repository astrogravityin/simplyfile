"""Sending mail, so people can sign themselves up and reset their own passwords.

The owner fills in one SMTP account in Setup. Gmail is the common case and the fiddly one, so the
errors below translate its refusals into what actually has to change.

stdlib `smtplib` only — nothing to install. Mail that cannot be sent raises with a sentence the
owner can act on; it is never swallowed into a log nobody reads.
"""
from __future__ import annotations

from typing import Any
import html
import json
import re
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


def _site_doc(root: Path | None = None) -> tuple[dict, dict]:
    """(the portal's site file, its mail block) - file and block named by chip mail.settings; unreadable = ({}, {})."""
    k = settings()
    try:
        doc = json.loads(((root or ROOT) / str(k["site_file"])).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}, {}
    if not isinstance(doc, dict):
        return {}, {}
    return doc, (doc.get(str(k["site_block"])) if isinstance(doc.get(str(k["site_block"])), dict) else {})


def site_sender(root: Path | None = None) -> dict:
    """The sender the portal's own site file sets (2026-10-16 owner: display names did not match the app - every new site
    had copied smtp.json, sender name and all, from the first site found). File and block: chip mail.settings. The block's
    from_email / from_name; no from_name = the file's label. No file, or nothing in it = {} (smtp.json alone, as before)."""
    doc, blk = _site_doc(root)
    if not doc:
        return {}
    got = {"from_email": str(blk.get("from_email") or "").strip(), "from_name": str(blk.get("from_name") or doc.get("label") or "").strip()}
    return {f: v for f, v in got.items() if v}


def layout() -> dict:
    """The branded page around every mail: chip mail.layout (words, sizes, colours, the email-safe page)."""
    return engine.run("mail.layout")


def site_brand(root: Path | None = None, name: str = "") -> dict:
    """What the branded HTML part shows (2026-10-16 owner: one shared Gmail sender, so the inbox picture is the same for
    every site - each site's look goes INSIDE the mail). {name, host, accent, mark: PNG bytes or None}. The mark is the PNG
    the site file's mail block names (key: chip mail.layout mark_block_key) inside the portal folder and under
    mark_max_bytes; else None = the monogram. A bad or missing accent = the chip's default."""
    lay, base = layout(), (root or ROOT).resolve()
    doc, blk = _site_doc(root)
    accent = str(blk.get(str(lay["accent_block_key"])) or "").strip()
    mark, rel = None, str(blk.get(str(lay["mark_block_key"])) or "").strip()
    if rel:
        p = (base / rel).resolve()
        try:
            if p.is_relative_to(base) and p.suffix.lower() == ".png" and p.stat().st_size <= int(lay["mark_max_bytes"]):
                mark = p.read_bytes()
        except OSError:
            mark = None
    return {"name": str(blk.get("from_name") or doc.get("label") or name or "").strip(), "host": str(doc.get("host") or "").strip(),
            "accent": accent if re.fullmatch(str(lay["accent_pattern"]), accent) else str(lay["accent"]), "mark": mark}


def html_body(text: str, brand: dict) -> str:
    """The mail text as the site's branded page: escaped, a blank line = a new paragraph, a line break kept, web addresses
    clickable; the page, paragraph, link, mark and footer are chip mail.layout's words."""
    lay, esc = layout(), html.escape
    name, accent = brand.get("name") or "", brand.get("accent") or lay["accent"]
    url_re = re.compile(str(lay["url_pattern"]))

    def linked(chunk: str) -> str:
        out, at = [], 0
        for m in url_re.finditer(chunk):
            out += [esc(chunk[at:m.start()]), ops.template(lay["link"], {"url": esc(m.group(0)), "text": esc(m.group(0)), "accent": accent})]
            at = m.end()
        return "".join(out + [esc(chunk[at:])])
    paras = [p.strip("\n") for p in re.split(r"\n[ \t]*\n", (text or "").replace("\r\n", "\n")) if p.strip()]
    body = "".join(ops.template(lay["para"], {"text": "<br>".join(linked(ln) for ln in p.split("\n"))}) for p in paras)
    px = int(lay["mark_px"])
    if brand.get("mark"):
        mark = ops.template(lay["mark_img"], {"cid": lay["mark_cid"], "px": px, "site": esc(name)})
    else:
        caps = "".join(ch for ch in name if ch.isupper()) or name[:1].upper()
        mark = ops.template(lay["mark_monogram"], {"px": px, "accent": accent, "initials": esc(caps[: int(lay["initials_max"])])})
    host = brand.get("host") or ""
    footer = ops.template(lay["footer"], {"site": esc(name), "host_link": ops.template(lay["host_link"], {"host": esc(host)}) if host else ""})
    first = next((ln.strip() for ln in (text or "").splitlines() if ln.strip()), "")
    return ops.template(lay["page"], {"subject": esc(brand.get("subject") or name), "preheader": esc(first[: int(lay["preheader_chars"])]),
                                      "mark": mark, "site": esc(name), "body": body, "footer": footer, "accent": accent,
                                      "width": lay["width"], "band": lay["band"], "font_px": lay["font_px"], "outer_pad": lay["outer_pad"]})


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


def build(to: str, subject: str, text: str, c: dict | None = None, root: Path | None = None) -> EmailMessage:
    """One message: the plain text exactly as it always was, plus (2026-10-16) the site's branded HTML beside it
    (multipart/alternative; the mark PNG rides inside as an inline cid image - multipart/related; Gmail strips SVG and
    nothing remote is ever loaded). `c` = the sender (from_name, from_email); default = config()."""
    c = config() if c is None else c
    msg = EmailMessage()
    msg["From"] = formataddr((c.get("from_name") or "", c.get("from_email") or ""))
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)
    brand = site_brand(root, name=c.get("from_name") or "") | {"subject": subject}
    msg.add_alternative(html_body(text, brand), subtype="html")
    if brand["mark"]:
        cid = str(layout()["mark_cid"])
        msg.get_payload()[1].add_related(brand["mark"], "image", "png", cid=f"<{cid}>", disposition="inline", filename=f"{cid}.png")
    return msg


def send_once(to: str, subject: str, text: str, once: str) -> bool:
    """send(), but a message already sent to this address with this key (`once`, the event's own key) is never sent again
    (core/writes.send_once, 2026-11-18 week class 30). False = it went before, nothing sent."""
    from core import writes  # noqa: PLC0415 - writes reads chips; mailer is imported early
    return writes.send_once("mail", f"{to}|{once}", lambda: send(to, subject, text))


def send(to: str, subject: str, text: str, picture: bytes | None = None) -> None:
    """One message: plain text (unchanged) + the site's branded HTML (build()); `picture` = a PNG shown above the words."""
    c = config()
    if not configured():
        raise RuntimeError(engine.say("mail.errors", "not_configured"))
    msg = build(to, subject, text, c)

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
    # 2026-10-16 branded mail (one shared Gmail sender, each site's look inside): the plain-text part is byte-for-byte what
    # it always was, the HTML part names the site and carries ITS mark as a cid image, and nothing remote is ever loaded
    lay, who = layout(), {"from_name": "X", "from_email": "a@x.example"}
    nasty = body + "\nSee https://example.test/a?b=1&c=2.\n\n<script>alert(1)</script>"
    old = EmailMessage()
    old.set_content(nasty)
    m = build("to@x.example", subject, nasty, who)
    parts = {p.get_content_type(): p for p in m.walk()}
    assert m.get_content_type() == "multipart/alternative" and {"text/plain", "text/html"} <= set(parts), list(parts)
    tp = parts["text/plain"]
    assert tp.get_payload() == old.get_payload() and all(tp[h] == old[h] for h in ("Content-Type", "Content-Transfer-Encoding")), "plain text changed"
    page = parts["text/html"].get_content()
    _, blk = _site_doc()
    brand = site_brand()
    assert brand["name"] and html.escape(brand["name"]) in page, "the HTML part does not name the site"
    assert "<script>" not in page and "&lt;script&gt;" in page and 'href="https://example.test/a?b=1&amp;c=2"' in page
    assert not re.findall(r"<img[^>]*src=\"(?!cid:)", page) and "url(" not in page and "@import" not in page, "a remote image or font"
    if blk.get(str(lay["mark_block_key"])):         # the site file names a mark: it must load and ride inside as a cid image
        assert brand["mark"] and brand["mark"][:8] == b"\x89PNG\r\n\x1a\n", f"mark {blk.get(lay['mark_block_key'])} missing, too big or not a PNG"
        assert "image/png" in parts and parts["image/png"]["Content-ID"] == f"<{lay['mark_cid']}>" and f"cid:{lay['mark_cid']}" in page
        assert m.get_payload()[1].get_content_type() == "multipart/related", "the mark must sit with the HTML (multipart/related)"
    assert re.fullmatch(str(lay["accent_pattern"]), brand["accent"]) and brand["accent"] in page
    (t / settings()["site_file"]).write_text(json.dumps({"label": "ExampleFy", "host": "xy.example.test"}), encoding="utf-8")
    mono = build("to@x.example", "s", "t", who, root=t)             # no mark in the site file = the label's monogram, no image
    mono_page = next(p for p in mono.walk() if p.get_content_type() == "text/html").get_content()
    assert "cid:" not in mono_page and ">EF<" in mono_page and not any(p.get_content_type() == "image/png" for p in mono.walk())
    calls: list[Any] = []                                   # one automatic retry on a passing timeout, never on a refused password

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
