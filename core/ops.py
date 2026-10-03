"""Ops: the generic primitives every chip is built from. The same idea as AstroStage's engine ops.

An op knows numbers, text, lists, rows and tables. It never knows what a portal, a memory limit or a
visitor is. Every judgement (a threshold, a message, which rows count, what order) is a knob on a chip
in core/chips/*.json or <portal>/chips/*.json, never a constant in Python.

Rules every op keeps:
  * Pure. It uses only its arguments: no clock unless it is passed, no files, no network, no globals.
  * An input it cannot answer returns None. None never passes as an answer ("0 MB" is a reading;
    "unknown" is None).
  * Arguments are keyword arguments with defaults. The catalog (params + doc) is read from the
    signature, so a new op is one function plus one line in OPS.
"""
from __future__ import annotations

import functools
import inspect
import math
import re
from collections import Counter
from typing import Any


def _num(v: Any) -> float | None:
    if isinstance(v, bool) or v in (None, ""):
        return None
    try:
        n = float(v)
    except (TypeError, ValueError):
        return None
    return n if math.isfinite(n) else None


def _truthy(v: Any) -> bool:
    """Booleans from a builder often arrive as TEXT ("true"/"false")."""
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "on")
    return bool(v)


def _tidy(n: float) -> float | int:
    return int(n) if float(n).is_integer() else n


# --- numbers ------------------------------------------------------------------------------------

def add(a: Any = None, b: Any = None) -> Any:
    """a + b."""
    x, y = _num(a), _num(b)
    return None if x is None or y is None else _tidy(x + y)


def sub(a: Any = None, b: Any = None) -> Any:
    """a − b."""
    x, y = _num(a), _num(b)
    return None if x is None or y is None else _tidy(x - y)


def mul(a: Any = None, b: Any = None) -> Any:
    """a × b."""
    x, y = _num(a), _num(b)
    return None if x is None or y is None else _tidy(x * y)


def div(a: Any = None, b: Any = None, digits: Any = None) -> Any:
    """a ÷ b, rounded to `digits` when given. Division by zero is unknown (None), never 0."""
    x, y = _num(a), _num(b)
    if x is None or not y:
        return None
    return round_to(x / y, digits) if digits not in (None, "") else _tidy(x / y)


def pct(part: Any = None, whole: Any = None, digits: Any = 0) -> Any:
    """part as a percentage of whole."""
    x, y = _num(part), _num(whole)
    if x is None or not y:
        return None
    return round_to(100 * x / y, digits)


def round_to(value: Any = None, digits: Any = 0) -> Any:
    """value rounded to `digits` places (0 = a whole number)."""
    x = _num(value)
    if x is None:
        return None
    d = int(_num(digits) or 0)
    return int(round(x)) if d <= 0 else round(x, d)


def floor_to(value: Any = None, step: Any = 1) -> Any:
    """value rounded DOWN to a whole multiple of `step` (1 = a whole number). round_to rounds half up, which is
    wrong for "how many fit" questions: 3 pictures shared by 2 people is 1 each, not 2."""
    x, s = _num(value), _num(step)
    if x is None or not s:
        return None
    return _tidy(math.floor(x / s) * s)


def first_free_slot(start: Any = 0, length: Any = 0, busy: Any = None, gap: Any = 0,
                    earliest: Any = None, latest_end: Any = None) -> Any:
    """The earliest moment at or after `start` where something `length` long fits without touching any of the
    `busy` spans ([from, to] pairs), keeping `gap` clear on both sides. Generic: a line of narration that must not
    talk over a line of dialogue, a slot in a timetable.
    `latest_end`: it must also END by then (the film's length). 2026-09-21: an 8 s film pushed a narration line to
    8.3 s - after the film ended - because it missed the gap before the dialogue by 0.04 s. So when nothing fits
    from `start`, the search starts again from `earliest` (as early as it may go); and when nothing fits at all,
    `start` comes back unchanged - an overlap is better than a line nobody hears."""
    s, n, g = _num(start), _num(length), _num(gap) or 0
    if s is None or n is None:
        return None
    spans = sorted((float(_num(a)), float(_num(b))) for a, b in (busy or []) if _num(a) is not None and _num(b) is not None)
    end = _num(latest_end)

    def scan(t: float) -> float:
        for a, b in spans:
            if t + n + g <= a:
                break
            if t < b + g:
                t = b + g
        return t

    t = scan(float(s))
    if end is None or t + n <= end:
        return _tidy(round(t, 3))
    lo = _num(earliest)
    if lo is not None and lo < s:
        t = scan(float(lo))
        if t + n <= end:
            return _tidy(round(t, 3))
    return _tidy(round(float(s), 3))

def clamp(value: Any = None, low: Any = None, high: Any = None) -> Any:
    """value kept between low and high (either may be blank)."""
    x = _num(value)
    if x is None:
        return None
    if _num(low) is not None:
        x = max(x, _num(low))
    if _num(high) is not None:
        x = min(x, _num(high))
    return _tidy(x)


def largest(values: Any = None) -> Any:
    """The largest number in a list (unreadable items skipped)."""
    nums = [n for n in (_num(v) for v in (values or [])) if n is not None]
    return _tidy(max(nums)) if nums else None


def smallest(values: Any = None) -> Any:
    """The smallest number in a list (unreadable items skipped)."""
    nums = [n for n in (_num(v) for v in (values or [])) if n is not None]
    return _tidy(min(nums)) if nums else None


def first_at_least(items: Any = None, value: Any = None) -> Any:
    """The smallest number in a list that is >= value; the largest when none is (a clip length that holds a shot)."""
    nums = sorted(n for n in (_num(v) for v in (items or [])) if n is not None)
    want = _num(value)
    if not nums or want is None:
        return None
    return _tidy(next((n for n in nums if n >= want), nums[-1]))


def median(values: Any = None) -> Any:
    """The middle value of a list: the upper middle when the count is even (as AstroStage)."""
    nums = sorted(n for n in (_num(v) for v in (values or [])) if n is not None)
    return _tidy(nums[len(nums) // 2]) if nums else None


def median_shift(values: Any = None, window: Any = 40, min_before: Any = 10) -> Any:
    """Median of the last `window` values minus the median of the `window` before them — a trend that
    a single spike cannot fake. 0 while fewer than `min_before` earlier values exist (too soon to say)."""
    vals = list(values or [])
    w = int(_num(window) or 0)
    if w <= 0:
        return None
    tail, before = vals[-w:], vals[-2 * w:-w]
    if len(before) < int(_num(min_before) or 0) or not before:
        return 0
    a, b = median(tail), median(before)
    return None if a is None or b is None else _tidy(a - b)


# --- text ---------------------------------------------------------------------------------------

_SLOT = re.compile(r"\{([A-Za-z_][\w.\-]*)(?::([^{}]*))?\}")


def template(text: Any = "", values: Any = None) -> str:
    """`{name}` in text replaced from values; `{verdict.title}` reads inside a row; `{delta:+}` shows a
    sign; `{n:person|people}` is the word for one or for any other count (2026-10-02: "1 people"). A name with no
    value becomes blank, never an error."""
    vals = values if isinstance(values, dict) else {}

    def fill(m: re.Match) -> str:
        v = get(vals, m.group(1))
        if m.group(2) and "|" in m.group(2):
            one, many = m.group(2).split("|", 1)
            return one if _num(v) == 1 else many
        if v is None:
            return ""
        v = _tidy(v) if isinstance(v, float) else v
        try:
            return format(v, m.group(2)) if m.group(2) else str(v)
        except (ValueError, TypeError):
            return str(v)
    return _SLOT.sub(fill, str(text or ""))


def text_length(text: Any = None) -> int | None:
    """How many characters the text has (surrounding spaces not counted)."""
    return None if text is None else len(str(text).strip())


def matches(text: Any = None, pattern: Any = "") -> bool | None:
    """TRUE when the WHOLE text fits the pattern (a regular expression). A broken pattern is unknown."""
    if text is None:
        return None
    try:
        return re.fullmatch(str(pattern or ""), str(text)) is not None
    except re.error:
        return None


def ends_with_any(text: Any = "", suffixes: Any = None, ignore_case: Any = True) -> bool | None:
    """TRUE when text ends with any of the suffixes."""
    if text is None:
        return None
    t = str(text)
    ss = [str(p) for p in (suffixes or [])]
    if _truthy(ignore_case):
        t, ss = t.lower(), [p.lower() for p in ss]
    return any(t.endswith(p) for p in ss if p)


def search(text: Any = None, pattern: Any = "") -> bool | None:
    """TRUE when the pattern (a regular expression) is found ANYWHERE in the text. (?i) makes it ignore case."""
    if text is None:
        return None
    try:
        return re.search(str(pattern or ""), str(text)) is not None
    except re.error:
        return None


def values_matching(values: Any = None, pattern: Any = "") -> list | None:
    """The distinct texts among a record's values (or a list) in which the pattern (a regular expression) is found,
    in first-seen order ({"a": "I checked it", "b": "Save"} with ^I  -> ["I checked it"]). A broken pattern is unknown."""
    if values is None:
        return None
    items = values.values() if isinstance(values, dict) else values if isinstance(values, (list, tuple)) else [values]
    try:
        rx = re.compile(str(pattern or ""))
    except re.error:
        return None
    out: list = []
    for v in items:
        if isinstance(v, str) and v not in out and rx.search(v):
            out.append(v)
    return out


def text_pick(text: Any = None, pattern: Any = "", group: Any = 1) -> str | None:
    """The part of the text a pattern's group captures ("https://a.com/x?q" with ^(https?://[^/?#]+) → "https://a.com")."""
    if text is None:
        return None
    try:
        m = re.search(str(pattern or ""), str(text))
    except re.error:
        return None
    if not m:
        return None
    try:
        return m.group(int(_num(group) or 0))
    except (IndexError, re.error):
        return None


def cut_at_any(text: Any = "", chars: Any = "") -> str:
    """Text up to (not including) the first of these characters: "#/reset?token=x" with "?&" → "#/reset"."""
    t = str(text or "")
    cuts = [t.find(ch) for ch in str(chars or "") if t.find(ch) >= 0]
    return t[:min(cuts)] if cuts else t


def sub_text(text: Any = "", pattern: Any = "", replacement: Any = "") -> str:
    """Every match of `pattern` (a regular expression) in text replaced by `replacement` (groups as \\1): a secret
    path part masked, a suffix dropped. A bad pattern leaves the text as it was."""
    if not pattern:
        return str(text or "")
    try:
        return re.sub(str(pattern), str(replacement or ""), str(text or ""))
    except re.error:
        return str(text or "")


def truncate(text: Any = "", length: Any = 0, mark: Any = "") -> str:
    """At most `length` characters (0 or blank = no limit); `mark` (e.g. "…") ends a text that was cut."""
    n = int(_num(length) or 0)
    t = str(text or "")
    return t[:n] + str(mark or "") if 0 < n < len(t) else t


def contains(text: Any = None, part: Any = "", ignore_case: Any = True) -> bool | None:
    """TRUE when part appears in text."""
    if text is None:
        return None
    t, p = str(text), str(part or "")
    return (p.lower() in t.lower()) if _truthy(ignore_case) else (p in t)


def ip_network(ip: Any = "", ipv4_bits: Any = 24, ipv6_bits: Any = 48) -> str:
    """An address cut to its network ("203.0.113.77" → "203.0.113.0/24"); not an address → ""."""
    import ipaddress  # noqa: PLC0415
    try:
        addr = ipaddress.ip_address(str(ip or "").strip())
    except ValueError:
        return ""
    bits = int(_num(ipv4_bits if addr.version == 4 else ipv6_bits) or (32 if addr.version == 4 else 128))
    return str(ipaddress.ip_network(f"{addr}/{bits}", strict=False))


def first_matching(text: Any = "", rows: Any = None, pattern_field: Any = "pattern", value_field: Any = "name",
                   default: Any = None) -> Any:
    """The value of the first row whose pattern is found in the text (rows are tried in order), else default."""
    for r in rows or []:
        if isinstance(r, dict) and search(text, r.get(pattern_field)):
            return r.get(value_field)
    return default


def epoch_date(epoch: Any = None, fmt: Any = "%d %b %Y") -> str | None:
    """A moment (seconds since 1970, UTC) written as a date."""
    from datetime import datetime, timezone  # noqa: PLC0415
    n = _num(epoch)
    if n is None:
        return None
    try:
        return datetime.fromtimestamp(n, timezone.utc).strftime(str(fmt or "%d %b %Y"))
    except (OverflowError, OSError, ValueError):
        return None


def days_between(start: Any = "", end: Any = "", digits: Any = 1) -> float | None:
    """Days from one ISO moment to another, rounded to `digits`; None when either is blank or unreadable, or one
    carries a zone and the other does not (unknown, never a guess)."""
    from datetime import datetime  # noqa: PLC0415
    try:
        a = datetime.fromisoformat(str(start).replace("Z", "+00:00"))
        b = datetime.fromisoformat(str(end).replace("Z", "+00:00"))
        return _tidy(round((b - a).total_seconds() / 86400, int(_num(digits) or 0)))
    except (ValueError, TypeError):
        return None


def split_text(text: Any = "", separators: Any = ", ;", strip: Any = " @", pattern: Any = "") -> list:
    """Text cut into words at any of the separator characters (or, given, at every match of the regular expression
    `pattern`); each word trimmed of `strip` characters, blanks dropped. "a.com, @b.org" → ["a.com", "b.org"]."""
    seps = str(separators or " ")
    words = re.split(str(pattern) if pattern else "[" + re.escape(seps) + "]+", str(text or ""))
    return [w.strip(str(strip or "")) for w in words if w.strip(str(strip or ""))]


def key_sentences(text: Any = "", count: Any = 3, sentence_pattern: Any = "", word_pattern: Any = "", stop_words: Any = None,
                  min_words: Any = 4) -> list:
    """The `count` sentences that carry the text's most frequent words, in their own order - a summary without a model.
    A sentence scores the summed frequency of its words (stop words skipped) over the square root of its length."""
    sents = [s.strip() for s in re.split(str(sentence_pattern or r"(?<=[.!?])\s+"), str(text or "")) if s.strip()]
    word = re.compile(str(word_pattern or r"[^\W\d_]+"))
    stop = {str(w).lower() for w in (stop_words or [])}
    words = [[w.lower() for w in word.findall(s)] for s in sents]
    freq: dict = {}
    for ws in words:
        for w in ws:
            if w not in stop:
                freq[w] = freq.get(w, 0) + 1
    scored = [(sum(freq.get(w, 0) for w in ws) / max(len(ws), 1) ** 0.5, n) for n, ws in enumerate(words) if len(ws) >= int(min_words or 0)]
    keep = sorted(n for _, n in sorted(scored, key=lambda x: -x[0])[: max(int(count or 0), 0)])
    return [sents[n] for n in keep]


def pattern_hits(text: Any = "", rows: Any = None, pattern_field: Any = "pattern", id_field: Any = "id", most: Any = 50,
                 around: Any = 30) -> list:
    """Every place a row's pattern (a regular expression) is found in the text, in text order: [{id, at, found, context}]
    - a proofreader's free pass from a list of rules. A broken pattern finds nothing; at most `most` hits in all."""
    t, out, pad = str(text or ""), [], max(int(_num(around) or 0), 0)
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        try:
            rx = re.compile(str(r.get(pattern_field) or ""))
        except re.error:
            continue
        if not rx.pattern:
            continue
        for m in rx.finditer(t):
            out.append({"id": r.get(id_field), "at": m.start(), "found": m.group(0),
                        "context": t[max(m.start() - pad, 0): m.end() + pad].replace("\n", " ").strip()})
    return sorted(out, key=lambda h: h["at"])[: max(int(_num(most) or 0), 0)]


def shared_runs(text: Any = "", others: Any = None, n: Any = 8, min_share: Any = 0.2, word_pattern: Any = "") -> list:
    """How much of `text` appears word for word in each other text: every run of `n` words (a shingle) of `text` that
    is also in the other one, as a share of all its runs. Rows {id, title, share, sample} at or above min_share, the
    largest first - an originality check without a model. `others` = [{id, title, text}]."""
    word = re.compile(str(word_pattern or r"[^\W_]+"))
    k = max(int(_num(n) or 0), 1)

    def runs(s: str) -> set:
        w = [x.lower() for x in word.findall(str(s or ""))]
        return {" ".join(w[i:i + k]) for i in range(len(w) - k + 1)}
    mine = runs(text)
    if not mine:
        return []
    out = []
    for o in others or []:
        if not isinstance(o, dict):
            continue
        both = mine & runs(o.get("text"))
        share = round(len(both) / len(mine), 3)
        if both and share >= float(_num(min_share) or 0):
            out.append({"id": o.get("id"), "title": o.get("title"), "share": share, "sample": min(both)})
    return sorted(out, key=lambda r: -r["share"])


def replace_once(text: Any = "", find: Any = "", put: Any = "") -> dict:
    """`find` replaced by `put` ONLY when it is in the text exactly once: {text, n} - n = how many times it was there (the
    text is unchanged unless n == 1). A correction that could land in the wrong place is never made."""
    t, f = str(text or ""), str(find or "")
    n = t.count(f) if f else 0
    return {"text": t.replace(f, str(put or ""), 1) if n == 1 else t, "n": n}


def _attr_re(attrs: Any) -> Any:
    names = "|".join(re.escape(str(a)) for a in (attrs or []))
    return re.compile(r'(\s(?:' + names + r')=")([^"]*)(")', re.I) if names else None


def html_texts(html: Any = "", attrs: Any = None) -> list[str]:
    """The words a reader sees, piece by piece, in page order: every run of text between tags that holds more than spaces,
    and the value of each named attribute (`attrs`, e.g. alt - what a screen reader says for a picture). Entities read."""
    import html as h  # noqa: PLC0415
    ar, out = _attr_re(attrs), []
    for i, x in enumerate(re.split(r"(<[^>]*>)", str(html or ""))):
        if i % 2 == 0:
            if x.strip():
                out.append(h.unescape(x))
        elif ar:
            out.extend(h.unescape(m.group(2)) for m in ar.finditer(x) if m.group(2).strip())
    return out


def html_put_texts(html: Any = "", texts: Any = None, attrs: Any = None) -> str:
    """The same HTML with its pieces (as html_texts counts them, same `attrs`) replaced in order by `texts`; every tag and
    every other attribute stays exactly as it was. A piece with no replacement stays; spaces around a run are kept."""
    import html as h  # noqa: PLC0415
    ar, parts, new = _attr_re(attrs), re.split(r"(<[^>]*>)", str(html or "")), list(texts or [])
    n = 0

    def take() -> Any:
        nonlocal n
        got = new[n] if n < len(new) else None
        n += 1
        return got

    for i, x in enumerate(parts):
        if i % 2 == 0:
            if x.strip():
                got = take()
                if got is not None:
                    lead, tail = x[: len(x) - len(x.lstrip())], x[len(x.rstrip()):]
                    parts[i] = lead + h.escape(str(got).strip(), quote=False) + tail
        elif ar:
            def one(m):
                if not m.group(2).strip():
                    return m.group(0)
                got = take()
                return m.group(0) if got is None else m.group(1) + h.escape(str(got).strip(), quote=True) + m.group(3)
            parts[i] = ar.sub(one, x)
    return "".join(parts)


def script_of(text: Any = "", bases: Any = None, size: Any = 128) -> int | None:
    """Which Unicode block (by its first code point, from `bases`) holds most of the letters in the text; None when none."""
    n = int(size or 128)
    counts = {int(b): 0 for b in (bases or [])}
    for ch in str(text or ""):
        o = ord(ch)
        for b in counts:
            if b <= o < b + n:
                counts[b] += 1
                break
    best = max(counts, key=counts.get, default=None)
    return best if best is not None and counts[best] else None


def script_shift(text: Any = "", to_base: Any = 0, bases: Any = None, size: Any = 128, fallback: Any = None) -> str:
    """Letters written in one parallel Unicode block moved to the same place in another (the Indian scripts share one
    layout): each letter in any of `bases` goes to `to_base` + its place, when that letter exists there; anything else
    (other scripts, HTML, digits, a letter the target lacks) stays as it is. `fallback` {place: [places]}: what a letter the
    target writes differently becomes (e.g. Tamil has no dha - it writes ta); it wins over the plain move."""
    import unicodedata  # noqa: PLC0415
    n, to, bs = int(size or 128), int(to_base or 0), [int(b) for b in (bases or [])]
    fb = {str(k): [int(x) for x in v] for k, v in (fallback or {}).items()}   # "place" for every script, "base:place" for one
    out = []
    for ch in str(text or ""):
        o = ord(ch)
        b = next((x for x in bs if x <= o < x + n), None)
        if b is None or b == to:
            out.append(ch)
        elif f"{b}:{o - b}" in fb or str(o - b) in fb:
            out.append("".join(chr(to + x) for x in fb.get(f"{b}:{o - b}", fb.get(str(o - b)))))
        else:
            new = chr(to + (o - b))
            out.append(new if unicodedata.name(new, "") else ch)
    return "".join(out)


def same_members(a: Any = None, b: Any = None) -> bool | None:
    """TRUE when two lists hold the same items the same number of times, in any order (a new order of the same things)."""
    if a is None or b is None:
        return None
    return sorted(map(str, a)) == sorted(map(str, b))


def starts_with_any(text: Any = "", prefixes: Any = None, ignore_case: Any = True) -> bool | None:
    """TRUE when text begins with any of the prefixes."""
    if text is None:
        return None
    t = str(text)
    ps = [str(p) for p in (prefixes or [])]
    if _truthy(ignore_case):
        t, ps = t.lower(), [p.lower() for p in ps]
    return any(t.startswith(p) for p in ps)


# --- lists and rows -----------------------------------------------------------------------------

def pluck(rows: Any = None, key: Any = "") -> list | None:
    """One field from each row, in order (a row without it gives None)."""
    if not isinstance(rows, list):
        return None
    return [r.get(key) if isinstance(r, dict) else None for r in rows]


def slice_list(items: Any = None, start: Any = None, end: Any = None) -> list | None:
    """items[start:end]; negative counts from the end, blank means the edge."""
    if not isinstance(items, list):
        return None
    s = None if _num(start) is None else int(_num(start))
    e = None if _num(end) is None else int(_num(end))
    return items[s:e]


def count(items: Any = None) -> int | None:
    """How many items a list holds (None when it is not a list)."""
    return len(items) if isinstance(items, list) else None


def last(items: Any = None) -> Any:
    """The last item of a list (None when empty)."""
    return items[-1] if isinstance(items, list) and items else None


def compact(values: Any = None) -> list:
    """The list without blanks (None, empty text, empty list)."""
    return [v for v in (values or []) if v not in (None, "", [])]


def first_with(rows: Any = None, field: Any = "", value: Any = None, out: Any = "id", default: Any = None) -> Any:
    """`out` of the first row whose list `field` holds `value` (e.g. the first storyteller whose languages hold the
    book's language), else default."""
    for r in rows or []:
        if isinstance(r, dict) and value in (r.get(field) or []):
            return r.get(out)
    return default


def coalesce(values: Any = None) -> Any:
    """The first value that is not blank."""
    return next((v for v in (values or []) if v not in (None, "")), None)


def json_in_text(text: Any = "", fence_pattern: Any = "") -> Any:
    """The JSON an answer carries (a model's or a pasted one): the value itself when it is already parsed, else the text
    without its code fence, else the first {...} inside it; None when there is none."""
    import json  # noqa: PLC0415
    if isinstance(text, (dict, list)):
        return text
    s = re.sub(str(fence_pattern), "", str(text or "").strip()) if fence_pattern else str(text or "").strip()
    found = sorted((m for m in (re.search(r"\{.*\}", s, re.S), re.search(r"\[.*\]", s, re.S)) if m), key=lambda m: m.start())
    for t in (s, *(m.group(0) for m in found)):         # the outermost first: {...} or a bare [...] list (2026-10-03)
        try:
            return json.loads(t) if t else None
        except ValueError:
            continue
    return None


def match_case(word: Any = "", like: Any = "") -> str:
    """`word` with its first letter raised when `like` starts with a capital (a suggestion fits the sentence it goes in)."""
    w, l = str(word or ""), str(like or "")
    return w[:1].upper() + w[1:] if w and l[:1].isupper() else w


def first_named(rows: Any = None, name: Any = "", field: Any = "name") -> Any:
    """The first row whose `field` starts with `name`, else the first that holds it anywhere - any case ("Ravi" finds
    "Ravi Kumar", "kumar" finds "Ravi Kumar"); None when none does or the name is blank."""
    n = str(name or "").strip().lower()
    if not n:
        return None
    rows_ = [r for r in rows or [] if isinstance(r, dict)]
    return next((r for r in rows_ if str(r.get(field) or "").lower().startswith(n)), None) \
        or next((r for r in rows_ if n in str(r.get(field) or "").lower()), None)


def total(values: Any = None, digits: Any = 6) -> Any:
    """The sum of the numbers - UNKNOWN (None) when any one is unknown, never a sum that quietly leaves it out (a cost
    with one unpriced part is not that cost). An empty list totals 0."""
    nums = [_num(v) for v in (values or [])]
    return None if any(n is None for n in nums) else round_to(sum(nums), digits)


def stable_hash(text: Any = "", mod: Any = 2 ** 31, hex_digits: Any = 0) -> int:
    """A number from text that is the same on every run and machine (SHA-1, never Python's salted hash), below `mod` -
    the same name always picks the same voice, the same film always gets the same seed. `hex_digits` > 0 = only the
    first that many hex digits (a film's seed has always used 8 - kept so earlier films keep their seed)."""
    import hashlib  # noqa: PLC0415
    m, d = int(_num(mod) or 0), int(_num(hex_digits) or 0)
    h = hashlib.sha1(str(text or "").encode("utf-8")).hexdigest()
    return int(h[:d] if d > 0 else h, 16) % m if m > 0 else 0


def hash_hex(text: Any = "", digits: Any = 12) -> str:
    """The first `digits` hex digits of text's SHA-1 - a stable public handle that never shows what it was made from."""
    import hashlib  # noqa: PLC0415
    return hashlib.sha1(str(text or "").encode("utf-8")).hexdigest()[: max(int(_num(digits) or 0), 0)]


def strings_in(value: Any = None, pattern: Any = "") -> list:
    """Every string anywhere inside nested records and lists that matches `pattern` (blank = every string), in order."""
    out: list = []
    stack = [value]
    while stack:
        v = stack.pop()
        if isinstance(v, str):
            if not pattern or matches(v, pattern):
                out.append(v)
        elif isinstance(v, dict):
            stack.extend(reversed(list(v.values())))
        elif isinstance(v, list):
            stack.extend(reversed(v))
    return out


def pack_text(text: Any = "", size: Any = 0, split: Any = r"(?<=[.!?])\s+", min_cut: Any = 0.5) -> list:
    """Sentences (cut by `split`) packed into pieces of at most `size` characters; a sentence longer than that is cut at
    its last space - unless that space is before `min_cut` of the size, then at the size itself. What a voice reads in one go."""
    n, out, cur = int(_num(size) or 0), [], ""
    if n <= 0:
        return [str(text or "")] if str(text or "").strip() else []
    for sent in re.split(str(split), str(text or "")):
        while len(sent) > n:
            cut = sent.rfind(" ", 0, n)
            cut = cut if cut > n * float(_num(min_cut) or 0) else n
            out.append((cur + " " + sent[:cut]).strip() if cur else sent[:cut])
            cur, sent = "", sent[cut:].strip()
        if cur and len(cur) + 1 + len(sent) > n:
            out.append(cur)
            cur = sent
        else:
            cur = (cur + " " + sent).strip()
    if cur:
        out.append(cur)
    return [c for c in out if c.strip()]


def ease(p: Any = 0, how: Any = "linear") -> float:
    """Progress 0..1 eased: "smooth" = smoothstep (slow in, slow out), anything else = straight. Out-of-range p is held."""
    x = min(1.0, max(0.0, float(_num(p) or 0)))
    return x * x * (3 - 2 * x) if how == "smooth" else x


def name_value_lines(text: Any = "", sep: Any = ":") -> list:
    """'name: value' lines -> [{name, value}] (a line without the separator, or with no name, is skipped; the value may
    hold the separator itself). A look sheet, a glossary typed one per line."""
    out = []
    for ln in str(text or "").splitlines():
        name, found, value = ln.partition(str(sep or ":"))
        if found and name.strip():
            out.append({"name": name.strip(), "value": value.strip()})
    return out


def pack_words(text: Any = "", words: Any = 0, split: Any = r"(?<=[.!?])\s+") -> list:
    """Sentences (cut by `split`) packed into pieces of about `words` words: a piece closes at the sentence that
    reaches the count (never mid-sentence). What a whiteboard or avatar scene says."""
    n, out, cur = int(_num(words) or 0), [], []
    for sent in [x.strip() for x in re.split(str(split), str(text or "")) if x.strip()]:
        cur.append(sent)
        if n and len(" ".join(cur).split()) >= n:
            out.append(" ".join(cur))
            cur = []
    if cur:
        out.append(" ".join(cur))
    return out


def last_line(text: Any = "", fallback: Any = "") -> str:
    """The last non-blank line of a text (what a failed tool said last), else the fallback."""
    lines = [x for x in str(text or "").strip().splitlines() if x.strip()]
    return lines[-1] if lines else str(fallback or "")


def after_heading(text: Any = "", heading: Any = "") -> str:
    """The text without its first line when that line IS the heading (a chapter that repeats its own title first);
    else the text as it is."""
    t = str(text or "")
    first, _, rest = t.lstrip().partition("\n")
    return rest if str(heading or "").strip() and first.strip() == str(heading).strip() else t


def trim_to_sentence(text: Any = "", most: Any = 0, ends: Any = None, min_share: Any = 0.5) -> str:
    """The first `most` characters, ended at the last sentence end (one of `ends`, e.g. ". ") when that keeps more than
    `min_share` of them - a sample that stops at a sentence, not mid-word."""
    t = str(text or "")[: int(_num(most) or 0)]
    cut = max((t.rfind(e) for e in (ends or [])), default=-1)
    return t[: cut + 1] if cut > len(t) * float(_num(min_share) or 0) else t


def fit_count(sizes: Any = None, most: Any = 0) -> int:
    """How many items, from the first, fit within `most` together (always one at least when there is one) - a big job
    sent part by part."""
    n, total = 0, 0.0
    for x in sizes or []:
        v = _num(x) or 0
        if n and total + v > (_num(most) or 0):
            break
        n, total = n + 1, total + v
    return n


_CMP = {"ge": lambda a, b: a >= b, "gt": lambda a, b: a > b, "le": lambda a, b: a <= b,
        "lt": lambda a, b: a < b, "eq": lambda a, b: a == b, "ne": lambda a, b: a != b}


def filter_rows(rows: Any = None, field: Any = "", cmp: Any = "eq", value: Any = None, absolute: Any = False) -> list | None:
    """Rows whose `field` compares to `value` (cmp: eq ne ge gt le lt). Numbers compare as numbers;
    `absolute` compares the size of a number whatever its sign."""
    if not isinstance(rows, list) or cmp not in _CMP:
        return None
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        have, want = r.get(field), value
        hn, wn = _num(have), _num(want)
        if hn is not None and wn is not None:
            have, want = (abs(hn) if _truthy(absolute) else hn), wn
        elif have is None:
            continue
        else:
            have, want = str(have), str(want)
        if _CMP[cmp](have, want):
            out.append(r)
    return out


def match_rows(rows: Any = None, where: Any = None) -> list | None:
    """Rows that fit every condition in `where` {field: wanted}: a blank wanted ("" / None / []) = any; a list = one of
    them; True = the field holds something; False = it is empty; anything else = equal (text, any case)."""
    if not isinstance(rows, list):
        return None
    conds = [(f, v) for f, v in (where or {}).items() if v not in ("", None, [])] if isinstance(where, dict) else []

    def fits(have: Any, want: Any) -> bool:
        if want is True or want is False:
            return bool(have) is want
        if isinstance(want, list):
            return str(have).lower() in {str(x).lower() for x in want}
        return str(have if have is not None else "").lower() == str(want).lower()
    return [r for r in rows if isinstance(r, dict) and all(fits(r.get(f), v) for f, v in conds)]


def rank_rows(rows: Any = None, by: Any = None, descending: Any = True, limit: Any = None) -> list | None:
    """Rows sorted by one or more fields (numbers as numbers), then cut to `limit`."""
    if not isinstance(rows, list):
        return None
    fields = by if isinstance(by, list) else [by]

    def key(r):
        out = []
        for f in fields:
            v = r.get(f) if isinstance(r, dict) else None
            n = _num(v)
            out.append((0, n) if n is not None else (1, str(v or "")))
        return out
    ranked = sorted([r for r in rows if isinstance(r, dict)], key=key, reverse=_truthy(descending))
    n = _num(limit)
    return ranked[:int(n)] if n is not None and n >= 0 else ranked


def rows_view(rows: Any = None, query: Any = "", search_keys: Any = None, sort_key: Any = "", sort_desc: Any = True,
              page: Any = 1, page_size: Any = 30, max_page_size: Any = 300) -> dict | None:
    """One page of rows for a list that may hold thousands: `query` (case-blind, every word must appear)
    matched over `search_keys`, sorted by `sort_key` (numbers as numbers, blanks last), then the page asked
    for. Returns {rows, total, page, pages, page_size} - the screen never receives more than one page."""
    if not isinstance(rows, list):
        return None
    words = [x for x in str(query or "").lower().split() if x]
    keys = [k for k in (search_keys if isinstance(search_keys, list) else [search_keys]) if k]
    kept = [r for r in rows if isinstance(r, dict)]
    if words:
        def text(r):
            return " ".join(str(r.get(k) or "") for k in keys).lower() if keys else " ".join(str(v) for v in r.values()).lower()
        kept = [r for r in kept if all(wd in text(r) for wd in words)]
    if sort_key:
        def key(r):
            v = r.get(sort_key)
            n = _num(v)
            return (0, n, "") if n is not None else (1, 0, str(v or ""))
        kept = sorted(kept, key=lambda r: (r.get(sort_key) in (None, ""), key(r)), reverse=_truthy(sort_desc))
        if _truthy(sort_desc):                                     # blanks stay LAST whichever way it is sorted
            kept = [r for r in kept if r.get(sort_key) not in (None, "")] + [r for r in kept if r.get(sort_key) in (None, "")]
    size = max(1, min(int(_num(page_size) or 30), int(_num(max_page_size) or 300)))
    total = len(kept)
    pages = max(1, -(-total // size))
    pg = min(max(1, int(_num(page) or 1)), pages)
    return {"rows": kept[(pg - 1) * size: pg * size], "total": total, "page": pg, "pages": pages, "page_size": size}


def fuzzy_rows(rows: Any = None, query: Any = "", keys: Any = None, min_score: Any = 0.75, out: Any = "_match",
               ignore: Any = None, near_min: Any = 0) -> list | None:
    """Rows that match `query` even with a typo or half a word ("pedestrain", "pedes" -> The Pedestrian), best first.
    Each query word scores 1 when it starts, or sits inside, a word of the row's `keys`; else its closest spelling
    (difflib ratio). A row's score = the mean over the query's words; rows under `min_score` drop out. Each kept row
    gains `out` = its score. `ignore` = words that never count ("how", "to", "the" in a question); a spelling closer than `near_min` counts 0
    (long texts hold many half-alike words). No query: every row, unscored.
    ponytail: one pass over every row per query - an index when a list outgrows ~50k rows."""
    if not isinstance(rows, list):
        return None
    import difflib  # noqa: PLC0415 - stdlib, only when a list is searched
    skip = {str(x).lower() for x in ignore} if isinstance(ignore, list) else set()
    words = [x for x in re.findall(r"\w+", str(query or "").lower()) if x and x not in skip]
    kept = [r for r in rows if isinstance(r, dict)]
    if not words:
        return kept
    fields = [k for k in (keys if isinstance(keys, list) else [keys]) if k]
    floor = _num(min_score) or 0

    close = _num(near_min) or 0
    texts = [" ".join(str(r.get(k) or "") for k in fields).lower() if fields else " ".join(str(v) for v in r.values()).lower() for r in kept]
    pools = [set(re.findall(r"\w+", t)) for t in texts]
    # each typed word against every DIFFERENT word once (not once per row): {word: {spelling: how alike}}
    vocab = set().union(*pools) if pools else set()
    alike: dict[str, dict[str, float]] = {}
    for word in set(words):
        room, near = max(2, len(word) // 3), {}
        for v in vocab:
            if abs(len(v) - len(word)) > room:
                continue
            m = difflib.SequenceMatcher(None, word, v)    # the cheap upper bounds first: same answer, far fewer full compares
            if m.real_quick_ratio() >= close and m.quick_ratio() >= close and (r_ := m.ratio()) >= close and r_ > 0:
                near[v] = r_
        alike[word] = near

    def best(word: str, pool: set[str], text: str) -> float:
        if word in text:
            return 1.0
        near = alike[word]
        return max((near[v] for v in pool if v in near) if len(pool) < len(near) else (x for v, x in near.items() if v in pool), default=0.0)
    scored = []
    for r, text, pool in zip(kept, texts, pools):
        score = sum(best(w, pool, text) for w in words) / len(words)
        if score >= floor:
            scored.append(dict(r) | {str(out): round(score, 3)})
    return sorted(scored, key=lambda r: -r[str(out)])


def rows_math(rows: Any = None, out: Any = "value", how: Any = "add", a: Any = None, b: Any = None, values: Any = None) -> list | None:
    """Each row gains `out` = a (how) b, where a and b are each a number, a field of the row, or a named value
    (`values`); how = add | sub | mul | div | max | min (never `op`: in a chip that key means a test). Unknown operand or a zero divisor -> None, never 0.
    Chains in a chip: age_days + fresh_days -> t, then fresh_days / t -> fresh (a score that fades with age)."""
    if not isinstance(rows, list):
        return None
    vals = values if isinstance(values, dict) else {}
    fns = {"add": lambda x, y: x + y, "sub": lambda x, y: x - y, "mul": lambda x, y: x * y,
           "div": lambda x, y: x / y if y else None, "max": max, "min": min}
    fn = fns.get(str(how))
    if fn is None:
        return None
    res = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        x, y = _named(a, r, vals), _named(b, r, vals)
        v = fn(x, y) if x is not None and y is not None else None
        res.append(dict(r) | {str(out): _tidy(v) if v is not None else None})
    return res


def group_rows(rows: Any = None, key: Any = None, measures: Any = None, separator: Any = " ") -> list | None:
    """Rows grouped by one or more fields. measures = {out_name: [agg, field]} with agg one of
    count, sum, max, min, last, first. The group's key text is in `key`, and each grouped field is
    also a column of its own, so a caller can tell the groups apart without re-splitting that text."""
    if not isinstance(rows, list):
        return None
    fields = key if isinstance(key, list) else [key]
    groups: dict[str, dict] = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        k = str(separator).join(str(r.get(f, "")) for f in fields)
        g = groups.setdefault(k, {"key": k} | {str(f): r.get(f) for f in fields} | {"_rows": []})
        g["_rows"].append(r)
    out = []
    for g in groups.values():
        rs = g.pop("_rows")
        for name, spec in (measures or {}).items():
            agg, field = (spec + [None])[:2] if isinstance(spec, list) else (spec, None)
            vals = [r.get(field) for r in rs if field]
            nums = [n for n in (_num(v) for v in vals) if n is not None]
            # 2026-09-21: max/min also answer for TEXT when no number is there - the latest date ("2026-09-21")
            # of a group is a real question, and "no numbers" is not an answer to it
            words = [str(v) for v in vals if isinstance(v, str) and v != ""]
            g[name] = {"count": len(rs), "sum": _tidy(sum(nums)) if nums else 0,
                       "max": _tidy(max(nums)) if nums else (max(words) if words else None),
                       "min": _tidy(min(nums)) if nums else (min(words) if words else None),
                       "last": vals[-1] if vals else None, "first": vals[0] if vals else None}.get(agg)
        out.append(g)
    return out


def rows_aggregate(rows: Any = None, agg: Any = "sum", key: Any = None, where: Any = None, digits: Any = 2) -> Any:
    """Aggregate over rows (AstroStage access_ops.rows_aggregate). agg: sum | count | max | min |
    distinct | mode. `where` = {field: value or [values]} keeps matching rows only; a sum keeps `digits` places
    (money in cents of a cent needs 4)."""
    if not isinstance(rows, list):
        return None
    rows = [r for r in rows if isinstance(r, dict)]
    if isinstance(where, dict) and where:
        rows = [r for r in rows if all((r.get(f) in v) if isinstance(v, list) else r.get(f) == v
                                       for f, v in where.items())]
    a = str(agg or "sum").lower()
    if a == "count":
        return len(rows)
    if key in (None, ""):
        return None
    vals = [r.get(key) for r in rows if r.get(key) is not None]
    if a == "distinct":
        return list(dict.fromkeys(vals))
    if a == "mode":
        strs = [str(v) for v in vals if str(v).strip()]
        return sorted(Counter(strs).items(), key=lambda kv: (-kv[1], kv[0]))[0][0] if strs else None
    nums = [n for n in (_num(v) for v in vals) if n is not None]
    if a == "sum":
        return _tidy(round(sum(nums), int(_num(digits) if _num(digits) is not None else 2)))
    if not nums:
        return None
    return _tidy(max(nums)) if a == "max" else _tidy(min(nums)) if a == "min" else None


def _named(name: Any, row: dict, values: dict) -> float | None:
    """A factor: a number as written, else the row's own field, else a named value; unknown → None."""
    n = _num(name)
    if n is not None and not isinstance(name, bool):
        return n
    return _num(row.get(name)) if name in row else _num(values.get(name))


def rows_product(rows: Any = None, values: Any = None, factors: Any = "factors", out: Any = "value",
                 divisors: Any = "", digits: Any = None) -> list | None:
    """Each row gains `out` = the product of the factors its `factors` field names (a number, a field of the
    row, or a named value), divided by those its `divisors` field names. A list of lists is a SUM of such
    products ([[in_tokens, in_rate], [out_tokens, out_rate]]). Any unknown factor → None, never 0.
    `factors` / `divisors` given as a LIST (not a field name) apply to every row: [["minutes", "rate"]] / [60]."""
    if not isinstance(rows, list):
        return None
    vals = values if isinstance(values, dict) else {}
    same_factors = factors if isinstance(factors, list) else None
    same_divisors = divisors if isinstance(divisors, list) else None

    def product(names: list, r: dict) -> float | None:
        got = [_named(x, r, vals) for x in names]
        if not names or None in got:
            return None
        v = 1.0
        for x in got:
            v *= x
        return v

    res = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        names = same_factors if same_factors is not None else (r.get(factors) or [])
        under = same_divisors if same_divisors is not None else ((r.get(divisors) if divisors else None) or [])
        terms = names if names and all(isinstance(x, list) for x in names) else [names]
        parts = [product(t, r) for t in terms]
        down = [_named(x, r, vals) for x in under]
        v = None
        if parts and None not in parts and None not in down and 0 not in down:
            v = sum(parts)
            for x in down:
                v /= x
            v = _tidy(round(v, int(digits))) if digits not in (None, "") else _tidy(v)
        res.append(dict(r) | {str(out): v})
    return res


def rows_lookup(rows: Any = None, values: Any = None, field: Any = "role", prefix: Any = "", suffix: Any = "",
                out: Any = "rate") -> list | None:
    """Each row gains `out` = the named value `prefix + row[field] + suffix` (a rate per role, a price per
    model): a row that says role=artist reads rate_artist. No such value → None, never 0."""
    if not isinstance(rows, list):
        return None
    vals = values if isinstance(values, dict) else {}
    return [dict(r) | {str(out): _num(vals.get(f"{prefix}{r.get(field, '')}{suffix}"))} for r in rows if isinstance(r, dict)]


def rows_index(rows: Any = None, key: Any = "id") -> dict | None:
    """Rows as one record keyed by a field ({"comic": {...}, "audiobook": {...}}), so a sentence can name one."""
    if not isinstance(rows, list):
        return None
    return {str(r.get(key)): r for r in rows if isinstance(r, dict) and r.get(key) not in (None, "")}


def rows_band(rows: Any = None, values: Any = None, field: Any = "fact", scores: Any = None) -> list | None:
    """Each row's named value banded against the row's own `good` and `fair` marks (`higher_better` says
    which way is good): the row gains `value`, `band` (good | fair | weak | unknown) and `score`
    (scores = [good, fair, weak], default 100/60/25; unknown scores None)."""
    if not isinstance(rows, list):
        return None
    vals = values if isinstance(values, dict) else {}
    s = scores if isinstance(scores, list) and len(scores) == 3 else [100, 60, 25]
    res = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        v, good, fair = _num(vals.get(r.get(field))), _num(r.get("good")), _num(r.get("fair"))
        up = _truthy(r.get("higher_better", True))
        if v is None or good is None or fair is None:
            band = "unknown"
        elif (v >= good) if up else (v <= good):
            band = "good"
        elif (v >= fair) if up else (v <= fair):
            band = "fair"
        else:
            band = "weak"
        res.append(dict(r) | {"value": None if v is None else _tidy(v), "band": band,
                              "score": {"good": s[0], "fair": s[1], "weak": s[2]}.get(band)})
    return res


def rows_check(rows: Any = None, values: Any = None, field: Any = "fact", cmp_field: Any = "op", value_field: Any = "value") -> list | None:
    """Each row's named value (`field` names a key of `values`) compared, by the row's own `cmp_field` (eq ne ge gt le lt,
    or = == >= > <= < !=), to the row's `value_field` - a number or text, or the NAME of another value. The row gains
    `have`, `need` and `state`: pass | fail | skip (skip = one side unknown; unknown never passes)."""
    if not isinstance(rows, list):
        return None
    vals = values if isinstance(values, dict) else {}
    alias = {"=": "eq", "==": "eq", "!=": "ne", ">=": "ge", ">": "gt", "<=": "le", "<": "lt"}
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        have = vals.get(r.get(field))
        want = r.get(value_field)
        need = vals.get(want) if isinstance(want, str) and want in vals else want
        cmp = alias.get(str(r.get(cmp_field)), str(r.get(cmp_field)))
        hn, nn = _num(have), _num(need)
        if have is None or need is None or cmp not in _CMP:
            state = "skip"
        elif hn is not None and nn is not None:
            state = "pass" if _CMP[cmp](hn, nn) else "fail"
        else:
            state = "pass" if _CMP[cmp](str(have), str(need)) else "fail"
        out.append(dict(r) | {"have": have, "need": need, "state": state})
    return out


def rows_having(rows: Any = None, field: Any = "", value: Any = None) -> list | None:
    """Rows whose `field` is a list holding `value` (or equals it, for a plain field)."""
    if not isinstance(rows, list):
        return None
    return [r for r in rows if isinstance(r, dict) and (value in r[field] if isinstance(r.get(field), list) else r.get(field) == value)]


def decision_table(facts: Any = None, rules: Any = None, current: Any = None) -> Any:
    """First matching rule's `set`, else `current` (AstroStage access_ops.decision_table).
    rules: [{when: {fact: value}, from: [...], set: x}]. The table IS the policy."""
    f = facts if isinstance(facts, dict) else {}

    def same(have: Any, want: Any) -> bool:
        if isinstance(want, bool) or str(want).strip().lower() in ("true", "false"):
            return _truthy(have) == _truthy(want)
        return str(have) == str(want)

    for rule in (rules or []):
        if isinstance(rule, dict) and all(same(f.get(k), v) for k, v in (rule.get("when") or {}).items()) \
                and (not rule.get("from") or current in rule.get("from")):
            return rule.get("set")
    return current


def _at_path(doc: Any, path: str) -> tuple[list, bool]:
    """Values at a path: "title", "voice.rate", "steps[].title" (one value per list item). -> (values, many)."""
    cur, many = [doc], False
    for part in [p for p in str(path or "").split(".") if p]:
        spread = part.endswith("[]")
        key = part[:-2] if spread else part
        nxt = []
        for c in cur:
            v = c.get(key) if isinstance(c, dict) else (
                c[int(key)] if isinstance(c, list) and key.lstrip("-").isdigit() and -len(c) <= int(key) < len(c) else None)
            if spread:
                many = True
                nxt.extend(v if isinstance(v, list) else [])
            else:
                nxt.append(v)
        cur = nxt
    return cur, many


def _blank(v: Any) -> bool:
    return v is None or (isinstance(v, (str, list, dict)) and not (v.strip() if isinstance(v, str) else v))


def _one_check(doc: Any, row: dict, sets: dict) -> list[dict]:
    """One rule row -> its failures [{say, path, index?}]. A value that is absent is only judged by `required`."""
    if "any_of" in row:   # passes when any listed row passes (e.g. a known portal OR a workspace:<code>)
        tries = [_one_check(doc, dict(r) | {"say": row.get("say")}, sets) for r in row.get("any_of") or [] if isinstance(r, dict)]
        return [] if any(not t for t in tries) else (tries[0] if tries else [])
    check, want = str(row.get("check") or ""), row.get("value")
    vals, many = _at_path(doc, str(row.get("path") or ""))
    bad = lambda i=None: {"say": row.get("say"), "path": row.get("path")} | ({"index": i} if many and i is not None else {})
    if check == "min_items":
        return [] if len(vals if many else (vals[0] or [])) >= int(_num(want) or 0) else [bad()]
    if check == "max_items":
        return [] if len(vals if many else (vals[0] or [])) <= int(_num(want) or 0) else [bad()]
    if check == "any_contains":
        return [] if any(isinstance(v, str) and str(want) in v for v in vals) else [bad()]
    out = []
    for i, v in enumerate(vals):
        if check == "required":
            ok = not _blank(v)
        elif _blank(v):
            ok = True
        elif check == "in_set":   # a set the caller did not give is unknown - unknown never fails a document
            members = sets.get(str(row.get("set")))
            ok = members is None or v in members
        elif check == "matches":
            ok = matches(str(v), str(want)) is True
        elif check == "range":
            n, lo, hi = _num(v), _num((want or [None, None])[0]), _num((want or [None, None])[1])
            ok = n is not None and (lo is None or n >= lo) and (hi is None or n <= hi)
        else:
            ok = True
        if not ok:
            out.append(bad(i))
    return out


def doc_problems(doc: Any = None, rules: Any = None, sets: Any = None, also: Any = None) -> list:
    """A document (a JSON script, a form) checked against a table of rules - the table IS the policy.
    Row: {path, check, value?, set?, when?, any_of?, say}. path: "title", "voice.rate", "steps[].title".
    check: required | min_items | max_items | in_set (value in sets[set]) | matches (regex) | range [lo, hi] |
    any_contains (some value holds the text). `when` = a row of the same shape that must PASS for this one to count.
    `also` = a second table checked after `rules` (e.g. an envelope's rules on top of the body's).
    -> [{say, path, index?}] - `say` is the row's message key; empty = no problems."""
    s = sets if isinstance(sets, dict) else {}
    out: list = []
    for row in [*(rules or []), *(also or [])]:
        if not isinstance(row, dict):
            continue
        gate = row.get("when")
        if isinstance(gate, dict) and _one_check(doc, gate, s):
            continue
        out.extend(_one_check(doc, row, s))
    return out


def literal(value: Any = None) -> Any:
    """The value as written."""
    return value


def record(fields: Any = None) -> dict:
    """A row built from named values: {name: value}."""
    return dict(fields) if isinstance(fields, dict) else {}


def merge(rows: Any = None) -> dict:
    """Several rows made one; a later field wins."""
    out: dict = {}
    for r in rows or []:
        if isinstance(r, dict):
            out.update(r)
    return out


def get(value: Any = None, path: Any = "") -> Any:
    """A field from a row, dotted for nesting (`peak.rss`); a list index is a number (`events.0`)."""
    cur = value
    for part in [p for p in str(path or "").split(".") if p]:
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list) and part.lstrip("-").isdigit() and -len(cur) <= int(part) < len(cur):
            cur = cur[int(part)]
        else:
            return None
    return cur


OPS = {f.__name__: f for f in (
    add, sub, mul, div, pct, round_to, floor_to, first_free_slot, clamp, largest, smallest, first_at_least, median, median_shift,
    template, starts_with_any, ends_with_any, text_length, matches, split_text, key_sentences, pattern_hits, shared_runs, replace_once, first_with, html_texts, html_put_texts, script_of, script_shift, same_members, search, text_pick, values_matching, cut_at_any,
    truncate, sub_text, contains, ip_network, first_matching, epoch_date,
    pluck, slice_list, count, last, compact, coalesce, json_in_text, fit_count, match_case, stable_hash, hash_hex, strings_in, total, first_named, pack_text, trim_to_sentence, after_heading, last_line, pack_words, name_value_lines, ease, filter_rows, rank_rows, rows_view, fuzzy_rows, match_rows, rows_math, group_rows, rows_aggregate,
    rows_product, rows_band, rows_index, rows_lookup, rows_check, rows_having, decision_table, doc_problems, literal, record, merge, get,
)}


def catalog() -> list[dict]:
    """Every op with its parameters and first doc line — what a builder palette shows."""
    return [{"op": name, "params": list(inspect.signature(fn).parameters),
             "doc": (fn.__doc__ or "").strip().splitlines()[0]} for name, fn in sorted(OPS.items())]


def run(op: str, args: dict) -> Any:
    fn = OPS.get(op)
    if fn is None:
        raise KeyError(f"no op named {op!r}")
    allowed = _params(fn)
    return fn(**{k: v for k, v in args.items() if k in allowed})


@functools.lru_cache(maxsize=None)
def _params(fn) -> frozenset:
    """An op's argument names, read once (2026-09-30: read on every call, a third of a list page's time)."""
    return frozenset(inspect.signature(fn).parameters)


if __name__ == "__main__":
    # 2026-10-02 "1 people": {n:one|many} - the word for one, or for any other count
    assert template("{n} {n:person|people}", {"n": 1}) == "1 person" and template("{n} {n:person|people}", {"n": 2}) == "2 people"
    assert template("{n:work|works}", {"n": "1"}) == "work" and template("{n:work|works}", {}) == "works"
    # 2026-09-30 owner "Avatar Video screen taking long time to load - we can have thousands" (12 s for 7 videos):
    # an op's argument names are read once, not on every call
    _arg = next(iter(inspect.signature(OPS["count"]).parameters))
    _sig, _read = inspect.signature, []
    inspect.signature = lambda f: (_read.append(f), _sig(f))[1]
    _params.cache_clear()
    assert run("count", {"junk": 1, _arg: [1, 2]}) == 2 and run("count", {_arg: []}) == 0
    inspect.signature = _sig
    assert len(_read) == 1, "ops.run read the op's signature again"
    # 2026-09-28 owner "flexi search": a typo or half a word still finds it; nonsense does not
    shelf_ = [{"title": "The Pedestrian", "pen": "Mira"}, {"title": "Monkey and Crocodile", "pen": "Ravi"}]
    assert [r["title"] for r in fuzzy_rows(shelf_, "pedestrain", ["title", "pen"])] == ["The Pedestrian"]
    assert [r["title"] for r in fuzzy_rows(shelf_, "croc", ["title"])] == ["Monkey and Crocodile"]
    assert fuzzy_rows(shelf_, "zzqx", ["title"]) == [] and len(fuzzy_rows(shelf_, "", ["title"])) == 2
    assert fuzzy_rows(shelf_, "mira", ["title", "pen"])[0]["_match"] == 1.0
    vo_ = [{"id": "a", "gender": "Male", "accent": "Indian", "paid": ""}, {"id": "b", "gender": "Female", "accent": "US", "paid": ""},
           {"id": "c", "gender": "Male", "accent": "Any", "paid": "gemini"}]
    assert [r["id"] for r in match_rows(vo_, {"paid": False, "gender": "male", "accent": ["Indian", "British"]})] == ["a"]
    assert [r["id"] for r in match_rows(vo_, {"paid": True, "gender": ""})] == ["c"] and len(match_rows(vo_, {})) == 3, "blank = any"
    assert fuzzy_rows(shelf_, "how to find the croc", ["title"], ignore=["how", "to", "find", "the"])[0]["_match"] == 1.0,         "question words never pull a real hit under the line"
    assert fuzzy_rows(shelf_, "pedestrain", ["title"], near_min=0.95) == [] and fuzzy_rows(shelf_, "pedestrain", ["title"], near_min=0.8),         "near_min: a typo still counts, a half-alike word does not"
    assert count([1, 2]) == 2 and count([]) == 0 and count("ab") is None
    assert rows_math([{"age": 3}], "t", "add", "age", "fresh", {"fresh": 7}) == [{"age": 3, "t": 10}]
    assert rows_math([{"t": 10}], "f", "div", "fresh", "t", {"fresh": 7})[0]["f"] == 0.7
    assert rows_math([{"x": 1}], "y", "div", "x", 0)[0]["y"] is None and rows_math([{"x": 1}], "y", "add", "x", "nope")[0]["y"] is None
    assert div(1, 0) is None and pct(30, 200) == 15 and pct(1, 3, 1) == 33.3
    assert median([5, 1, 3]) == 3 and median([1, 2, 3, 4]) == 3 and median([]) is None
    assert first_at_least([8, 4, 6], 3) == 4 and first_at_least([4, 6, 8], 6) == 6 and first_at_least([4, 6, 8], 10) == 8
    assert first_at_least([], 3) is None and first_at_least([4], None) is None
    assert median_shift([0] * 80 + [100] * 40 + [150] * 40) == 50 and median_shift([1] * 45) == 0
    assert template("{a} of {b} ({c:+} MB){missing}", {"a": 1, "b": 2.0, "c": 5}) == "1 of 2 (+5 MB)"
    assert template("{v.title} at {v.pct}%", {"v": {"title": "Spike", "pct": 91}}) == "Spike at 91%"
    rows = [{"m": "GET", "p": "/a", "d": 10, "t": 1}, {"m": "GET", "p": "/a", "d": 60, "t": 2},
            {"m": "POST", "p": "/b", "d": -7, "t": 3}]
    g = group_rows(rows, ["m", "p"], {"count": ["count"], "max_delta": ["max", "d"], "last_at": ["last", "t"]})
    assert g[0] == {"key": "GET /a", "m": "GET", "p": "/a", "count": 2, "max_delta": 60, "last_at": 2},         "a group carries the fields it was grouped by, not only their joined text"
    # 2026-09-21 first_free_slot: narration must not talk over a spoken shot
    assert first_free_slot(0.5, 3.2, [[4.0, 8.0]], 0.25) == 0.5, "it fits before the dialogue"
    assert first_free_slot(0.5, 4.0, [[4.0, 8.0]], 0.25) == 8.25, "too long to fit before: after the dialogue"
    assert first_free_slot(0.5, 1.0, [[0.0, 2.0], [3.0, 6.0]], 0.25) == 6.25, "a gap too small is skipped"
    assert first_free_slot(0.5, 0.5, [[0.0, 2.0], [3.0, 6.0]], 0.25) == 2.25, "a gap big enough is used"
    assert first_free_slot(1.0, 2.0, [], 0) == 1 and first_free_slot(None, 2, [], 0) is None
    # the owner's 8 s film: 3.24 s of narration misses the gap before 4.0 by 0.04 s from 0.5 - start it earlier
    assert first_free_slot(0.5, 3.24, [[4.0, 8.0]], 0.3, earliest=0, latest_end=8.0) == 0, "earlier, not past the end"
    assert first_free_slot(0.5, 3.24, [[4.0, 8.0]], 0.3, latest_end=8.0) == 0.5, "no room anywhere: keep the start"
    assert first_free_slot(0.5, 2.0, [[4.0, 8.0]], 0.3, earliest=0, latest_end=12.0) == 0.5, "fits as asked: untouched"
    assert first_free_slot(0.5, 4.0, [[4.0, 8.0]], 0.3, earliest=0, latest_end=13.0) == 8.3, "after, while the film lasts"
    # 2026-09-21 max/min answer for text too: the latest date in a group, where no number exists
    dated = [{"s": "Ranipur", "at": "2026-09-20"}, {"s": "Ranipur", "at": "2026-09-21"}]
    assert group_rows(dated, "s", {"latest": ["max", "at"], "first_at": ["min", "at"]})[0]["latest"] == "2026-09-21"
    assert group_rows(dated, "s", {"first_at": ["min", "at"]})[0]["first_at"] == "2026-09-20"
    assert group_rows([{"s": "x", "at": None}], "s", {"latest": ["max", "at"]})[0]["latest"] is None, "nothing there = None"
    assert [r["d"] for r in rank_rows(rows, "d", True, 2)] == [60, 10]
    assert [r["d"] for r in filter_rows(rows, "d", "ge", 7, absolute=True)] == [10, 60, -7]
    assert decision_table({"x": "true"}, [{"when": {"x": True}, "set": "yes"}], "no") == "yes"
    # 2026-09-28 a document checked against a rules table (Guide me scripts: chip guide.script_rules)
    d_ = {"title": "T", "steps": [{"title": "a", "say": "b", "target": "section.as-home"}, {"title": "", "say": "c"}], "voice": {"rate": 5}}
    r_ = [{"path": "title", "check": "required", "say": "no_title"}, {"path": "steps", "check": "min_items", "value": 3, "say": "few"},
          {"path": "steps[].title", "check": "required", "say": "step_title"}, {"path": "voice.rate", "check": "range", "value": [0.5, 2], "say": "rate"},
          {"path": "portal", "any_of": [{"path": "portal", "check": "in_set", "set": "p"}, {"path": "portal", "check": "matches", "value": "ws:[a-z]+"}], "say": "portal"},
          {"when": {"path": "steps[].target", "check": "any_contains", "value": "as-home"}, "path": "steps[].open", "check": "any_contains", "value": "[data-open]", "say": "must_open"}]
    got_ = doc_problems(d_, r_, {"p": ["sm"]})
    assert [g["say"] for g in got_] == ["few", "step_title", "rate", "must_open"] and got_[1]["index"] == 1, got_
    assert doc_problems(d_ | {"portal": "x"}, r_[4:5], {"p": ["sm"]})[0]["say"] == "portal"
    assert not doc_problems(d_ | {"portal": "ws:ag"}, r_[4:5], {"p": ["sm"]}) and not doc_problems({"portal": "sm"}, r_[4:5], {"p": ["sm"]})
    assert not doc_problems({"steps": [{"target": "x"}]}, r_[5:], {}), "the when-gate: no list, no need to open"
    assert get({"a": [{"b": 4}]}, "a.-1.b") == 4 and starts_with_any("Docker0", ["docker"]) is True
    assert matches("ravi.k", "^[a-z0-9][a-z0-9._-]*$") and matches("x", "(") is None and text_length("  ab ") == 2
    assert key_sentences("The lion ruled. A lion and a bull met in the forest. Birds sang. The bull and the lion became friends.", 2, min_words=3) == [
        "A lion and a bull met in the forest.", "The bull and the lion became friends."]
    assert same_members(["b", "a"], ["a", "b"]) and not same_members(["a", "a"], ["a", "b"]) and not same_members(["a"], ["a", "b"])
    # 2026-10-02 owner: spell / grammar / originality on every narration - the free pass is rule rows and word runs
    ph_ = pattern_hits("It was was late ,said Ravi.", [{"id": "twice", "pattern": r"(?i)\b(\w+) \1\b"}, {"id": "gap", "pattern": " ,"}, {"id": "bad", "pattern": "("}])
    assert [h["id"] for h in ph_] == ["twice", "gap"] and ph_[0]["found"] == "was was", ph_
    sr_ = shared_runs("the hare jumped into the fire and was not burnt at all", [{"id": "a", "title": "Hare", "text": "Then the hare jumped into the fire and was not burnt."}, {"id": "b", "text": "other words"}], n=4, min_share=0.3)
    assert first_with([{"id": "a", "langs": ["hi"]}, {"id": "b", "langs": ["te", "ta"]}], "langs", "ta") == "b" and first_with([], "langs", "x", default="d") == "d"
    assert json_in_text('```json\n{"a": 1}\n```', r"^```(?:json)?\s*|\s*```$") == {"a": 1} and json_in_text('Sure: {"a": 2} ok') == {"a": 2}
    assert json_in_text("no json") is None and json_in_text({"a": 3}) == {"a": 3}
    assert match_case("their", "Thier") == "Their" and match_case("their", "thier") == "their" and match_case("", "X") == ""
    assert first_named([{"name": "Ravi Kumar"}, {"name": "Sita"}], "kumar")["name"] == "Ravi Kumar" and first_named([{"name": "Sita"}], "") is None
    assert total([1, 2.5]) == 3.5 and total([1, None]) is None and total([]) == 0
    assert stable_hash("abc", 2 ** 31) == int("a9993e364706816aba3e25717850c26c9cd0d89d", 16) % 2 ** 31 and stable_hash("x", 0) == 0
    assert pack_text("Aa bb. Cc dd. Ee.", 8) == ["Aa bb.", "Cc dd.", "Ee."] and pack_text("aaaa bbbb cccc", 9) == ["aaaa bbbb", "cccc"] and pack_text("", 5) == []
    assert all(len(x) <= 10 for x in pack_text("x" * 25, 10)) and trim_to_sentence("One. Two three four", 12, [". "]) == "One. Two thr"
    # 2026-10-03 Katha V2: an author handle and every sentence inside an asset - ops, never hand code
    assert hash_hex("katha-author:u1", 12) == __import__("hashlib").sha1(b"katha-author:u1").hexdigest()[:12]
    assert strings_in({"a": "one two", "b": ["x", {"c": "three four"}], "d": 5}, "(?s).* .*") == ["one two", "three four"]
    assert strings_in(["a", ["b"]]) == ["a", "b"] and strings_in(None) == []
    assert ease(0.5, "smooth") == 0.5 and ease(0.25, "smooth") == 0.15625 and ease(2, "linear") == 1.0 and ease(-1, "smooth") == 0.0
    assert name_value_lines("Ravi: tall, kind: always" + chr(10) + "no sep" + chr(10) + ": x") == [{"name": "Ravi", "value": "tall, kind: always"}]
    assert pack_words("One two. Three four five. Six.", 3) == ["One two. Three four five.", "Six."] and pack_words("", 3) == []
    assert last_line("a" + chr(10) + "boom" + chr(10), "ffmpeg") == "boom" and last_line("", "ffmpeg") == "ffmpeg"
    assert json_in_text("here: [{\"a\": 1}] ok") == [{"a": 1}] and json_in_text("x {\"b\": 2} y") == {"b": 2}
    assert after_heading("Dawn" + chr(10) + "he year", "Dawn") == "he year" and after_heading("Dusk" + chr(10) + "x", "Dawn") == "Dusk" + chr(10) + "x" and after_heading("a", "") == "a"
    assert trim_to_sentence("One two three. Four", 19, [". "]) == "One two three." and trim_to_sentence("abc", 2, [". "]) == "ab"
    assert fit_count([4, 4, 4], 9) == 2 and fit_count([20, 1], 9) == 1 and fit_count([], 9) == 0 and fit_count([1, 2], 99) == 2
    assert html_texts("<p>Rain &amp; sun <b>here</b></p>\n<img src=x>") == ["Rain & sun ", "here"]
    assert html_put_texts("<p>Rain &amp; sun <b>here</b></p>", ["Pluie & soleil", "ici"]) == "<p>Pluie &amp; soleil <b>ici</b></p>"
    assert html_texts('<img src="a.jpg" alt="Gold swan" /><p>Hi</p>', ["alt"]) == ["Gold swan", "Hi"]
    assert html_put_texts('<img src="a.jpg" alt="Gold swan" /><p>Hi</p>', ["Cygne d\'or", "Salut"], ["alt"]) == '<img src="a.jpg" alt="Cygne d&#x27;or" /><p>Salut</p>'
    assert script_shift("नमस्ते <b>ok</b>", 0x0C00, [0x0900, 0x0C00]) == "నమస్తే <b>ok</b>"
    assert script_shift("ౝढ़", 0x0B80, [0x0900, 0x0B80, 0x0C00], fallback={"93": [31], "3072:93": [40, 77]}) == "ந்ட"
    assert script_shift("బుద్ధ", 0x0B80, [0x0B80, 0x0C00], fallback={"44": [42], "38": [36], "39": [36]}) == "புத்த"
    assert script_of("నమ abc", [0x0900, 0x0C00]) == 0x0C00 and script_of("abc", [0x0900]) is None
    assert replace_once("Teh hare", "Teh", "The") == {"text": "The hare", "n": 1} and replace_once("a a", "a", "b") == {"text": "a a", "n": 2} and replace_once("x", "", "y")["n"] == 0
    assert [r["id"] for r in sr_] == ["a"] and sr_[0]["share"] >= 0.5 and shared_runs("", [{"text": "x"}]) == [], sr_
    assert split_text("<a@x.org>;  b@y.org" + chr(10) + "c@z.org", "", "<> ", "[" + chr(92) + "s,;]+") == ["a@x.org", "b@y.org", "c@z.org"]
    assert split_text("a.com, @b.org;;c.net") == ["a.com", "b.org", "c.net"] and ends_with_any("X@A.COM", ["@a.com"])
    assert ip_network("203.0.113.77") == "203.0.113.0/24" and ip_network("2001:db8:abcd:12:1::5") == "2001:db8:abcd::/48"
    assert cut_at_any("#/reset?token=S", "?&") == "#/reset" and truncate("abcdef", 3) == "abc"
    # 2026-09-23 a public link's token is masked before the ledger keeps the path
    assert sub_text("/w/AbC-1_z.mp4", r"(/w/)[A-Za-z0-9_-]+(\.[a-z0-9]+)$", r"\1*\2") == "/w/*.mp4" and sub_text("/x", "(", "y") == "/x"
    assert text_pick("https://www.google.com/search?q=me", "^(https?://[^/?#]+)") == "https://www.google.com"
    assert values_matching({"a": "I checked it", "b": "Save", "c": "I checked it", "d": 3}, "^I ") == ["I checked it"], "distinct texts, first seen"
    assert values_matching(["OK", "OKAY"], "^OK(?![A-Za-z])") == ["OK"] and values_matching({}, "x") == []
    assert values_matching({"a": "x"}, "(") is None and values_matching(None, "x") is None, "broken pattern / nothing = unknown"
    assert first_matching("Chrome/120 Edg/120", [{"pattern": "Edg/", "name": "Edge"}, {"pattern": "Chrome/", "name": "Chrome"}]) == "Edge"
    assert search("MyBot/1", "(?i)bot") and epoch_date(0) == "01 Jan 1970" and contains("text/html; utf-8", "TEXT/HTML")
    assert days_between("2026-09-20T00:00:00", "2026-09-22T12:00:00") == 2.5 and days_between("", "2026-09-22") is None
    assert days_between("2026-09-20T00:00:00Z", "2026-09-22T00:00:00") is None, "a zone beside none is unknown, not a guess"
    assert rows_aggregate([{"v": 0.00012}, {"v": 0.0001}], "sum", "v", digits=4) == 0.0002 and rows_aggregate([{"v": 0.004}], "sum", "v") == 0
    # 2026-09-19 a list of thousands reaches the screen one page at a time
    big = [{"id": i, "name": f"Film {i}", "logline": "rain" if i % 2 else "sun", "updated": f"2026-09-{i % 28 + 1:02d}"} for i in range(1, 251)]
    v = rows_view(big, "", ["name", "logline"], "updated", True, 1, 30)
    assert v["total"] == 250 and v["pages"] == 9 and len(v["rows"]) == 30 and v["rows"][0]["updated"] == "2026-09-28", (v["total"], v["pages"])
    assert rows_view(big, "rain film 7", ["name", "logline"], "id", False, 1, 10)["rows"][0]["name"] == "Film 7"
    assert rows_view(big, "", [], "", True, 99, 30)["page"] == 9 and rows_view(big, "", [], "", True, 1, 9999)["page_size"] == 300
    assert rows_view(big, "nothing-like-this", ["name"], "", True, 1, 30) == {"rows": [], "total": 0, "page": 1, "pages": 1, "page_size": 30}
    blanks = [{"n": "a", "updated": ""}, {"n": "b", "updated": "2026-01-01"}, {"n": "c"}]
    assert [r["n"] for r in rows_view(blanks, "", [], "updated", True, 1, 10)["rows"]] == ["b", "a", "c"], "blanks last"
    # 2026-09-22 book assessment: a cost is units x rate per row; a criterion is banded by its own marks
    steps = [{"f": ["words", "tpw", 2]}, {"f": ["words", "missing"]}, {"f": [3, "n"], "d": ["per"]}, {"f": []}]
    got = rows_product(steps, {"words": 100, "tpw": 1.5}, "f", "usd", "d")
    assert [r["usd"] for r in got] == [300, None, None, None], got
    assert rows_product([{"f": [3, "n"], "d": ["per"], "n": 4, "per": 8}], {}, "f", "v", "d")[0]["v"] == 1.5
    assert rows_product([{"f": [1], "d": [0]}], {}, "f", "v", "d")[0]["v"] is None, "divide by zero is unknown"
    assert rows_product([{"f": [["a", 2], ["b", 3]]}], {"a": 10, "b": 1}, "f", "v")[0]["v"] == 23, "a sum of products"
    # 2026-09-23 people cost: the same factors for every row (minutes x the row's rate, per hour), a rate looked up by role
    people = rows_lookup([{"role": "artist", "min": 90}, {"role": "nobody", "min": 5}], {"rate_artist": 40}, "role", "rate_", "", "rate")
    assert [r["rate"] for r in people] == [40, None], people
    assert [r["usd"] for r in rows_product(people, {}, [["min", "rate"]], "usd", [60])] == [60, None], "a literal factor list applies to every row"
    assert rows_product([{"f": ["x"], "x": 4}], {}, "f", "v", [2])[0]["v"] == 2, "a literal divisor list too"
    assert rows_product([{"f": [["a", 2], ["zz", 3]]}], {"a": 10}, "f", "v")[0]["v"] is None, "one unknown term = unknown"
    assert rows_index([{"id": "a", "n": 1}, {"id": "", "n": 2}, {"id": "b"}]) == {"a": {"id": "a", "n": 1}, "b": {"id": "b"}}
    crit = [{"fact": "a", "good": 10, "fair": 5}, {"fact": "a", "good": 2, "fair": 20, "higher_better": "false"},
            {"fact": "b", "good": 1, "fair": 0}, {"fact": "a", "good": 30, "fair": 20}]
    assert [(r["band"], r["score"]) for r in rows_band(crit, {"a": 12})] == [("good", 100), ("fair", 60), ("unknown", None), ("weak", 25)]
    assert {o["op"] for o in catalog()} == set(OPS)
    print("core.ops self-check OK")
