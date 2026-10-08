"""Limits every module needs - each function only ASKS its chip (2026-09-28 owner: "chips and ops only").
A module never writes `len(x) >= settings()["max"]` or `text[:n]`: the comparison is policy, so it is a chip too.

  room_left(count, most)   limits.room_left   one more may be added
  within(count, most)      limits.room_left   count is at most `most` (a list sent whole: 3 of most 3 is fine)
  too_soon(since, gap)     limits.too_soon    too few seconds since the last time
  one_of(value, choices)   limits.one_of      a choice from a chip's list
  clip(text, most)         limits.clip        spaces tidied, cut to the longest allowed
  too_big(size, most_mb)   limits.too_big     a file bigger than the most allowed (MB)
  newest(rows, keep, by)   limits.newest      the newest rows, at most keep
  allow(action, who, n)    limits.rates       at most `most` of an action per person per window (2026-10-01)
"""
from __future__ import annotations

from core import engine


def room_left(count, most) -> bool:
    return engine.run("limits.room_left", {"count": count, "most": most}) is True


def within(count, most) -> bool:
    return room_left(count - 1, most)                   # at most `most` = one fewer still has room


def too_soon(since, gap) -> bool:
    return engine.run("limits.too_soon", {"since": since, "gap": gap}) is True


def one_of(value, choices) -> bool:
    return engine.run("limits.one_of", {"value": value, "choices": list(choices)}) is True


def too_big(size, most_mb) -> bool:
    return engine.run("limits.too_big", {"size": size, "most_mb": most_mb}) is True


def clip(text, most) -> str:
    return engine.run("limits.clip", {"text": str(text or ""), "most": most}) or ""


def newest(rows: list, keep, by: str = "at") -> list:
    return engine.run("limits.newest", {"rows": rows, "keep": keep, "by": by}) or []


def zip_room(zf) -> None:
    """Refuse a zip that unpacks bigger than chip limits.files unzip_most_mb (a zip bomb), before anything is read out."""
    from fastapi import HTTPException  # noqa: PLC0415
    k = engine.run("limits.files")
    if not room_left(sum(int(i.file_size or 0) for i in zf.infolist()) - 1, float(k["unzip_most_mb"]) * 1024 * 1024):
        raise HTTPException(400, engine.say("limits.files", "too_big_unpacked", mb=k["unzip_most_mb"]))


def allow(action: str, who: str, n: int = 1) -> bool:
    """May `who` do `action` `n` more times now? Chip limits.rates names the window and the most; an action it does not
    name is never limited. Allowed = counted (kept in a small file per action, so a restart does not reset it)."""
    import time  # noqa: PLC0415
    from core import store  # noqa: PLC0415
    rule = (engine.run("limits.rates") or {}).get(action)
    if not rule or n <= 0:
        return True
    now, per, name = time.time(), float(rule["per_s"]), f"rates-{action}"
    with store._LOCK:                                   # noqa: SLF001
        seen = store.read(name, {}) or {}
        hits = [t for t in seen.get(str(who), []) if now - float(t) < per]
        if not room_left(len(hits) + n - 1, rule["most"]):
            return False
        seen[str(who)] = hits + [now] * int(n)
        store.write(name, {k: v for k, v in seen.items() if v and now - float(max(v)) < per})
    return True


if __name__ == "__main__":  # ponytail: the wrappers carry each chip's answer through unchanged
    assert within(3, 3) and not within(4, 3) and within(0, 3)
    assert room_left(2, 3) and not room_left(3, 3) and too_soon(5, 20) and not too_soon(20, 20)
    assert one_of("en", ["en"]) and not one_of("xx", ("en",)) and clip("  a   b ", 2) == "a " and clip(None, 5) == ""
    assert [r["at"] for r in newest([{"at": "1"}, {"at": "3"}, {"at": "2"}], 2)] == ["3", "2"]
    # 2026-10-01: one gate (chip limits.rates) - counts per person, blocks at `most`, another person is not blocked
    import tempfile  # noqa: PLC0415
    from pathlib import Path  # noqa: PLC0415
    from core import store  # noqa: PLC0415
    _was = store.DATA
    store.DATA = Path(tempfile.mkdtemp())
    try:
        most_ = engine.run("limits.rates")["access_request"]["most"]
        assert all(allow("access_request", "u1") for _ in range(most_)) and not allow("access_request", "u1"), "the most is the most"
        assert allow("access_request", "u2") and allow("not_a_named_action", "u1"), "per person; an unnamed action is not limited"
        assert not allow("issue", "u3", most_ + 10_000), "n at once counts as n"
    finally:
        store.DATA = _was
    import io, zipfile  # noqa: E401, PLC0415 - 2026-10-01: a zip that unpacks too big is refused before it is read
    from fastapi import HTTPException  # noqa: PLC0415
    _b = io.BytesIO()
    with zipfile.ZipFile(_b, "w", zipfile.ZIP_DEFLATED) as _z:
        _z.writestr("small.txt", "ok")
    zip_room(zipfile.ZipFile(io.BytesIO(_b.getvalue())))
    _info = zipfile.ZipFile(io.BytesIO(_b.getvalue())).infolist()[0]
    _info.file_size = int(float(engine.run("limits.files")["unzip_most_mb"]) * 1024 * 1024) + 1
    class _Fake:  # noqa: N801 - a zip whose header claims more than the most
        def infolist(self):
            return [_info]
    try:
        zip_room(_Fake())
        raise AssertionError("a zip bigger than limits.files unzip_most_mb was let through")
    except HTTPException as e_:
        assert e_.status_code == 400
    print("core.limits self-check OK")
