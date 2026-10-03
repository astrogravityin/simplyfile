"""Where a visitor is when no CDN says so: a local IP database, looked up on this server.

No address is sent anywhere. Cloudflare/Vercel location headers still win when they exist
(ledger.place); this fills the gap for a portal served straight from a VPS.

The database is DB-IP "IP to City Lite" (CC BY 4.0 — the Visitors page carries the credit),
downloaded once a month into data/geo/. Any GeoLite2-City-shaped .mmdb works too:
PORTAL_GEOIP_DB=/path/to/file.mmdb uses it and never downloads. PORTAL_GEOIP=off turns both off.

The reader is stdlib (mmap + int.from_bytes), so core/ still needs nothing beyond FastAPI.
MaxMind DB format: https://maxmind.github.io/MaxMind-DB/
"""
from __future__ import annotations

import gzip
import ipaddress
import mmap
import os
import shutil
import struct
import threading
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

from core import engine, ops, store

MARKER = b"\xab\xcd\xefMaxMind.com"
DAY = 86400                # seconds in a day: a unit, not a policy
# Where the file comes from, how often it is refreshed and retried: chip geo.settings. Every sentence: geo.messages.


def settings() -> dict:
    return engine.run("geo.settings")


def say(key: str, **values) -> str:
    return engine.say("geo.messages", key, **values)


class Reader:
    def __init__(self, path: Path):
        with open(path, "rb") as f:
            self.buf = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        at = self.buf.rfind(MARKER)
        if at < 0:
            self.buf.close()
            raise ValueError(say("not_mmdb", file=Path(path).name))
        start = at + len(MARKER)
        meta, _ = self._decode(start, start)
        self.nodes, self.size, self.version = meta["node_count"], meta["record_size"], meta["ip_version"]
        if self.size not in (24, 28, 32):
            self.buf.close()
            raise ValueError(say("bad_record_size", size=self.size))
        self.node_bytes = self.size // 4
        self.data = self.nodes * self.node_bytes + 16
        self.v4root = 0
        if self.version == 6:      # IPv4 lives under ::/96 of an IPv6 tree
            for _ in range(96):
                if self.v4root >= self.nodes:
                    break
                self.v4root = self._record(self.v4root, 0)

    def _record(self, node: int, bit: int) -> int:
        b, o = self.buf, node * self.node_bytes
        if self.size == 24:
            return int.from_bytes(b[o + 3 * bit:o + 3 * bit + 3], "big")
        if self.size == 32:
            return int.from_bytes(b[o + 4 * bit:o + 4 * bit + 4], "big")
        if bit == 0:  # 28: the middle byte's high nibble belongs to the left record
            return ((b[o + 3] & 0xF0) << 20) | int.from_bytes(b[o:o + 3], "big")
        return ((b[o + 3] & 0x0F) << 24) | int.from_bytes(b[o + 4:o + 7], "big")

    def _decode(self, off: int, base: int):
        b = self.buf
        ctrl = b[off]; off += 1
        kind = ctrl >> 5
        if kind == 1:  # pointer, relative to the data section
            ss, v = (ctrl >> 3) & 3, ctrl & 7
            if ss == 0:
                p = (v << 8) | b[off]
            elif ss == 1:
                p = ((v << 16) | int.from_bytes(b[off:off + 2], "big")) + 2048
            elif ss == 2:
                p = ((v << 24) | int.from_bytes(b[off:off + 3], "big")) + 526336
            else:
                p = int.from_bytes(b[off:off + 4], "big")
            value, _ = self._decode(base + p, base)
            return value, off + ss + 1
        if kind == 0:
            kind = 7 + b[off]; off += 1
        size = ctrl & 0x1F
        if size >= 29:
            extra = size - 28
            n = int.from_bytes(b[off:off + extra], "big"); off += extra
            size = 29 + n if extra == 1 else (285 + n if extra == 2 else 65821 + n)
        if kind == 7:  # map
            out = {}
            for _ in range(size):
                k, off = self._decode(off, base)
                out[k], off = self._decode(off, base)
            return out, off
        if kind == 11:  # array
            arr = []
            for _ in range(size):
                v, off = self._decode(off, base)
                arr.append(v)
            return arr, off
        if kind == 14:  # boolean: the size IS the value
            return bool(size), off
        raw = b[off:off + size]
        off += size
        if kind == 2:
            return raw.decode("utf-8", "replace"), off
        if kind == 3:
            return struct.unpack(">d", raw)[0], off
        if kind == 15:
            return struct.unpack(">f", raw)[0], off
        if kind == 8:
            return int.from_bytes(raw.rjust(4, b"\0"), "big", signed=True), off
        if kind in (5, 6, 9, 10):
            return int.from_bytes(raw, "big"), off
        return raw, off  # bytes, cache container, end marker: nothing a place needs

    def get(self, ip: str):
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return None
        if addr.version == 6 and self.version == 4:
            return None
        node, bits = (self.v4root, 32) if addr.version == 4 else (0, 128)
        value = int(addr)
        for i in range(bits):
            if node >= self.nodes:
                break
            node = self._record(node, (value >> (bits - 1 - i)) & 1)
        if node <= self.nodes:  # == node_count means "no data"; < means the tree ran out of address
            return None
        return self._decode(self.data + node - self.nodes - 16, self.data)[0]


_reader: Reader | None = None
_state = {"source": "", "updated": "", "error": ""}
_lock = threading.Lock()
_started = False


def _db_file() -> Path:
    return store.DATA / "geo" / "dbip-city-lite.mmdb"


def _open(path: Path, source: str) -> bool:
    global _reader
    try:
        r = Reader(path)
    except (OSError, ValueError) as e:
        _state.update(source="missing", error=f"{Path(path).name}: {e}")
        return False
    with _lock:
        _reader = r
        lookup.cache_clear()
    _state.update(source=source, error="",
                  updated=datetime.fromtimestamp(Path(path).stat().st_mtime, timezone.utc).isoformat(timespec="seconds"))
    return True


@lru_cache(maxsize=4096)
def lookup(ip: str) -> tuple[str, str, str]:
    """(country ISO code, region, city) — empty strings when unknown."""
    r = _reader
    try:
        rec = r.get(ip) if r else None
    except (ValueError, IndexError):  # a file swapped out under a lookup: unknown this once
        return "", "", ""
    if not isinstance(rec, dict):
        return "", "", ""
    en = lambda d: ((d or {}).get("names") or {}).get("en") or ""  # noqa: E731
    subs = rec.get("subdivisions") or [{}]
    return ((rec.get("country") or {}).get("iso_code") or "")[:8], en(subs[0])[:60], en(rec.get("city"))[:60]


def status() -> dict:
    return dict(_state)


def _swap(tmp: Path, dest: Path) -> None:
    global _reader
    with _lock:
        if _reader is not None and os.name == "nt":  # Windows cannot replace a file that is mapped
            _reader.buf.close()
            _reader = None
        os.replace(tmp, dest)


def download(dest: Path) -> None:
    """This month's file, else last month's (a new month's file appears a day or two in)."""
    today = datetime.now(timezone.utc)
    months = [today.strftime("%Y-%m"), (today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")]
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    last = None
    k = settings()
    for month in months:
        try:
            req = urllib.request.Request(ops.template(k["url_template"], {"month": month}),
                                         headers={"User-Agent": "portal-core-geo"})
            with urllib.request.urlopen(req, timeout=float(k["download_timeout_seconds"])) as resp, gzip.GzipFile(fileobj=resp) as gz, \
                    open(tmp, "wb") as out:
                shutil.copyfileobj(gz, out, 1 << 20)
            Reader(tmp).buf.close()  # refuse a truncated or wrong file before it replaces a good one
            _swap(tmp, dest)
            return
        except Exception as e:  # noqa: BLE001 - reported on the Visitors page, retried later
            last = e
            tmp.unlink(missing_ok=True)
    raise RuntimeError(say("download_failed", error=last))


def _loop(on_loaded) -> None:
    dest = _db_file()
    if dest.exists() and _open(dest, "dbip"):
        on_loaded()
    while True:
        age = time.time() - dest.stat().st_mtime if dest.exists() else None
        k = settings()
        if age is None or age > float(k["refresh_days"]) * DAY:
            try:
                download(dest)
                if _open(dest, "dbip"):
                    on_loaded()
            except Exception as e:  # noqa: BLE001
                if _reader is None:
                    _state.update(source="missing", error=str(e)[:300])
        time.sleep(float(k["retry_seconds"]))


def start(on_loaded=lambda: None) -> None:
    """Called once by core.install. `on_loaded` runs each time a database opens (ledger back-fill)."""
    global _started
    if _started:
        return
    _started = True
    if os.getenv("PORTAL_GEOIP", "").lower() in ("off", "0", "false", "no"):
        _state.update(source="off")
        return
    own = os.getenv("PORTAL_GEOIP_DB", "").strip()
    if own:
        if _open(Path(own), "file"):
            on_loaded()
        return
    _state.update(source="loading")
    threading.Thread(target=_loop, args=(on_loaded,), name="geoip", daemon=True).start()


# --- self-check: a tiny database written here, so the reader is proven without the network --------

def _encode(v) -> bytes:
    def head(kind: int, size: int) -> bytes:
        ext = b""
        if size >= 29:
            ext, size = (bytes([size - 29]), 29) if size < 285 else ((size - 285).to_bytes(2, "big"), 30)
        if kind > 7:
            return bytes([size]) + bytes([kind - 7]) + ext
        return bytes([(kind << 5) | size]) + ext
    if isinstance(v, tuple):  # ("ptr", offset) — a pointer, as real files use for repeated values
        p = v[1]
        if p < 2048:
            return bytes([0x20 | (p >> 8)]) + bytes([p & 0xFF])
        p -= 2048
        return bytes([0x28 | (p >> 16)]) + (p & 0xFFFF).to_bytes(2, "big")
    if isinstance(v, str):
        raw = v.encode()
        return head(2, len(raw)) + raw
    if isinstance(v, int):
        raw = v.to_bytes(4, "big").lstrip(b"\0")
        return head(6, len(raw)) + raw
    if isinstance(v, list):
        return head(11, len(v)) + b"".join(_encode(x) for x in v)
    return head(7, len(v)) + b"".join(_encode(k) + _encode(x) for k, x in v.items())


def tiny_db(path: Path, entries: list[tuple[str, dict]], v6: bool = True, size: int = 24) -> Path:
    """Write a MaxMind DB (record size 24, 28 or 32) holding `entries` [(network, record)]. Test use only."""
    filler = _encode("x" * 3000)                       # pushes later data past a 1-byte pointer
    data = [filler]
    shared = sum(map(len, data)); data.append(_encode("IN"))
    offsets, nodes = [], [[None, None]]
    for net, rec in entries:
        rec = {**rec, "note": ("ptr", 0)}
        if isinstance(rec.get("country"), dict) and rec["country"].get("iso_code") == "IN":
            rec["country"] = {"iso_code": ("ptr", shared)}
        offsets.append(sum(map(len, data))); data.append(_encode(rec))
        n = ipaddress.ip_network(net)
        width = 128 if v6 else 32
        plen = n.prefixlen + (96 if v6 and n.version == 4 else 0)
        bits, node = int(n.network_address), 0
        for i in range(plen):
            bit = (bits >> (width - 1 - i)) & 1
            if i == plen - 1:
                nodes[node][bit] = ("data", len(offsets) - 1)
            else:
                if nodes[node][bit] is None:
                    nodes.append([None, None]); nodes[node][bit] = len(nodes) - 1
                node = nodes[node][bit]
    count = len(nodes)
    rec_of = lambda r: count if r is None else (count + 16 + offsets[r[1]] if isinstance(r, tuple) else r)  # noqa: E731

    def pack(a: int, b: int) -> bytes:
        if size == 28:
            return (a & 0xFFFFFF).to_bytes(3, "big") + bytes([(a >> 24) << 4 | (b >> 24)]) + (b & 0xFFFFFF).to_bytes(3, "big")
        return a.to_bytes(size // 8, "big") + b.to_bytes(size // 8, "big")
    tree = b"".join(pack(rec_of(a), rec_of(b)) for a, b in nodes)
    meta = _encode({"node_count": count, "record_size": size, "ip_version": 6 if v6 else 4,
                    "binary_format_major_version": 2, "binary_format_minor_version": 0, "build_epoch": 0,
                    "database_type": "test", "description": {"en": "test"}, "languages": ["en"]})
    path.write_bytes(tree + b"\0" * 16 + b"".join(data) + MARKER + meta)
    return path


def _self_check() -> None:
    import tempfile  # noqa: PLC0415
    rows = [("49.207.0.0/16", {"country": {"iso_code": "IN"}, "subdivisions": [{"names": {"en": "Telangana"}}],
                               "city": {"names": {"en": "Hyderabad"}}}),
            ("8.8.8.0/24", {"country": {"iso_code": "US"}, "city": {"names": {"en": "Mountain View"}}})]
    with tempfile.TemporaryDirectory() as tmp:
        for v6, size in ((True, 24), (False, 24), (True, 28), (True, 32)):
            r = Reader(tiny_db(Path(tmp) / f"t{v6}{size}.mmdb", rows, v6, size))
            hit = r.get("49.207.12.34")
            assert hit and hit["country"]["iso_code"] == "IN", hit          # 2-byte pointer
            assert hit["note"] == "x" * 3000, "1-byte pointer and a 29+ length string"
            assert hit["subdivisions"][0]["names"]["en"] == "Telangana"
            assert r.get("8.8.8.8")["city"]["names"]["en"] == "Mountain View"
            assert r.get("1.1.1.1") is None and r.get("49.208.0.1") is None and r.get("nonsense") is None
            r.buf.close()
    # A tiny tree never holds a record past 2^24, so the 28-bit nibble split is proven on raw bytes.
    r = Reader.__new__(Reader)
    r.buf, r.size, r.node_bytes = bytes.fromhex("BCDEF1A1234567"), 28, 7
    assert (r._record(0, 0), r._record(0, 1)) == (0xABCDEF1, 0x1234567), "28-bit records split wrong"


if __name__ == "__main__":
    _self_check()
    print("geo ok")
