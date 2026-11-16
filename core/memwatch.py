"""Memory watch: what this portal weighs, what moved it, the whole server around it — and what that means.

Built the chip way (core/engine.py). This module only GATHERS FACTS, and it gathers them with the
standard library (no psutil): resident memory, the processes this portal started, the machine's
memory and CPU, every process on the box, network bytes, disk. Every judgement — the limit that
applies, which request is worth recording, the trend, the spike, the verdict and its words, which
network cards count, how the offenders and other services rank — is a `memory.*` chip in
core/chips/, with its knobs and its test cases.

Why it exists (the studio, 2026-09-10): a process killed for memory prints no traceback anywhere,
and a one-minute platform graph never shows the ten-second spike that did it. So the portal keeps its
own record: a reading every few seconds, and the name of every request that moved memory.

Linux reads /proc (and the container's cgroup limit). Windows reads this process and the machine
through ctypes; the per-process table needs Linux. Nothing is written to disk: a restart starts clean.
"""
from __future__ import annotations

import os
import shutil
import sys
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends

from core import engine, rules, store

rules.subject("server", "The server this portal runs on", [
    {"name": "rss_mb", "type": "number", "label": "Portal memory now (MB)"},
    {"name": "limit_mb", "type": "number", "label": "Memory limit (MB)"},
    {"name": "pct", "type": "number", "label": "Memory used, % of the limit"},
    {"name": "climb_mb", "type": "number", "label": "Baseline climb in ten minutes (MB)"},
    {"name": "level", "type": "text", "label": "Memory verdict: ok, watch, warn or kill"},
    {"name": "title", "type": "text", "label": "Verdict headline"},
    {"name": "message", "type": "text", "label": "Verdict message"},
    {"name": "cpu", "type": "number", "label": "Server CPU %"},
    {"name": "disk_free_mb", "type": "number", "label": "Free disk (MB)"},
    {"name": "spike_path", "type": "text", "label": "Latest request that spiked memory"}],
    "Read every sample (every few seconds) by Memory watch.")
rules.trigger("server.sample", "server", "Memory watch takes a reading", ["banner", "notify", "flag"],
              "Every sample. Use a cooldown on anything that tells a person.")
rules.subject("portal", "The whole portal, once a day", [
    {"name": "date", "type": "text", "label": "Today (UTC, YYYY-MM-DD)"},
    {"name": "weekday", "type": "text", "label": "Day of the week"},
    {"name": "accounts", "type": "number", "label": "Accounts"},
    {"name": "disk_free_mb", "type": "number", "label": "Free disk (MB)"},
    {"name": "data_mb", "type": "number", "label": "Data folder (MB)"}])
rules.trigger("daily", "portal", "Once a day", ["banner", "notify"], "The first sample after midnight UTC.")

router = APIRouter()
MB = 1024 * 1024
_S = engine.run("memory.settings")
SAMPLES: deque = deque(maxlen=int(_S["keep_samples"]))
EVENTS: deque = deque(maxlen=int(_S["keep_events"]))
_LOCK = threading.Lock()
_PEAK = {"rss": 0, "at": None, "path": ""}
_DISK: dict = {}
_PROCS: dict = {"app": [], "other": [], "supported": False}
_APP_BYTES = [0]
_PREV: dict = {}
_started = 0.0
PROC = "/proc"  # the Linux readers take their root from here, so a test can hand them a fake one
STARTED_AT = datetime.now(timezone.utc)


def _conf(name: str, default: int) -> int:
    try:
        return os.sysconf(name)
    except (AttributeError, ValueError, OSError):
        return default


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --- facts: this process ------------------------------------------------------------------------

def _windows_rss() -> int:
    import ctypes
    from ctypes import wintypes

    class PMC(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + \
                   [(n, ctypes.c_size_t) for n in ("PeakWorkingSetSize", "WorkingSetSize",
                    "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                    "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]
    k32 = ctypes.WinDLL("kernel32")
    k32.GetCurrentProcess.restype = wintypes.HANDLE
    k32.K32GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
    pmc = PMC()
    pmc.cb = ctypes.sizeof(PMC)
    k32.K32GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb)
    return int(pmc.WorkingSetSize)


def rss() -> int:
    """Resident memory of this process, in bytes. 0 when the platform will not say."""
    try:
        with open(f"{PROC}/self/statm", "rb") as f:
            return int(f.read().split()[1]) * _conf("SC_PAGE_SIZE", 4096)
    except (OSError, ValueError, AttributeError):
        pass
    if os.name == "nt":
        try:
            return _windows_rss()
        except Exception:  # noqa: BLE001 - a missing number, never a crashed request
            return 0
    try:
        import resource  # peak, not current — the best a bare POSIX offers
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return peak if sys.platform == "darwin" else peak * 1024
    except Exception:  # noqa: BLE001
        return 0


def reader() -> str:
    return "proc" if os.path.exists(f"{PROC}/self/statm") else ("windows" if os.name == "nt" else "resource")


# --- facts: the machine -------------------------------------------------------------------------

def machine() -> dict:
    """Total and available RAM on this machine (bytes)."""
    try:
        info = {}
        with open(f"{PROC}/meminfo", encoding="ascii") as f:
            for line in f:
                k, v = line.split(":", 1)
                info[k] = int(v.split()[0]) * 1024
        return {"total": info.get("MemTotal", 0), "available": info.get("MemAvailable", 0)}
    except OSError:
        pass
    if os.name == "nt":
        try:
            import ctypes

            class MS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong)] + \
                           [(n, ctypes.c_ulonglong) for n in ("total", "avail", "tpf", "apf", "tv", "av", "aev")]
            ms = MS()
            ms.dwLength = ctypes.sizeof(MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))
            return {"total": int(ms.total), "available": int(ms.avail)}
        except Exception:  # noqa: BLE001
            pass
    return {"total": 0, "available": 0}


def _cgroup_bytes() -> int | None:
    for path in ("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory/memory.limit_in_bytes"):
        try:
            raw = Path(path).read_text(encoding="ascii").strip()
        except OSError:
            continue
        if raw.isdigit() and int(raw) < 1 << 50:  # "max" or a huge sentinel = no container limit
            return int(raw)
    return None


def limit() -> dict:
    """{mb, source} — the facts, judged by chip memory.limit."""
    env = os.getenv("PORTAL_MEMORY_LIMIT_MB", "").strip()
    cg = _cgroup_bytes()
    return engine.run("memory.limit", {"env_mb": int(env) if env.isdigit() else None,
                                       "cgroup_mb": cg // MB if cg else None,
                                       "machine_mb": machine()["total"] // MB or None})


def _cpu_times() -> tuple[float, float] | None:
    """(busy, total) seconds of the whole machine since boot."""
    try:
        with open(f"{PROC}/stat", encoding="ascii") as f:
            parts = [float(x) for x in f.readline().split()[1:9]]  # guest time is already inside user
        tick = _conf("SC_CLK_TCK", 100)
        idle = parts[3] + (parts[4] if len(parts) > 4 else 0)
        return (sum(parts) - idle) / tick, sum(parts) / tick
    except (OSError, ValueError, AttributeError):
        pass
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes
            idle, kernel, user = wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME()
            ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user))
            ft = lambda t: ((t.dwHighDateTime << 32) | t.dwLowDateTime) / 1e7  # noqa: E731
            total = ft(kernel) + ft(user)  # kernel time includes idle
            return total - ft(idle), total
        except Exception:  # noqa: BLE001
            pass
    return None


def _processes() -> list[dict] | None:
    """Every process on a Linux box: pid, parent, name, CPU seconds, resident bytes. None elsewhere."""
    try:
        pids = [p for p in os.listdir(PROC) if p.isdigit()]
        page, tick = _conf("SC_PAGE_SIZE", 4096), _conf("SC_CLK_TCK", 100)
    except OSError:
        return None
    out = []
    for pid in pids:
        try:
            with open(f"{PROC}/{pid}/stat", "rb") as f:
                raw = f.read()
            name = raw[raw.index(b"(") + 1:raw.rindex(b")")].decode(errors="replace")
            st = raw[raw.rindex(b")") + 2:].split()
            with open(f"{PROC}/{pid}/statm", "rb") as f:
                res = int(f.read().split()[1]) * page
            out.append({"pid": int(pid), "ppid": int(st[1]), "name": name,
                        "cpu_s": (int(st[11]) + int(st[12])) / tick, "rss": res})
        except (OSError, ValueError, IndexError):
            continue
    return out


def _net_bytes() -> int | None:
    """Bytes in + out on the interfaces chip memory.counts_nic says count."""
    try:
        with open(f"{PROC}/net/dev", encoding="ascii") as f:
            lines = f.readlines()[2:]
    except OSError:
        return None
    total = 0
    for line in lines:
        name, _, rest = line.partition(":")
        cols = rest.split()
        if len(cols) >= 9 and engine.run("memory.counts_nic", {"name": name.strip()}):
            total += int(cols[0]) + int(cols[8])
    return total


def count_bytes(*lengths) -> None:
    """Request middleware hook: Content-Length of the request and the response (payload bytes only)."""
    for v in lengths:
        try:
            _APP_BYTES[0] += int(v or 0)
        except (TypeError, ValueError):
            pass


def host_sample() -> dict:
    """One reading of the whole server: CPU, memory and bandwidth, this portal against the rest."""
    now = time.time()
    prev, out = dict(_PREV), {}
    cpu = _cpu_times()
    procs = _processes()
    net = _net_bytes()
    ncpu = os.cpu_count() or 1
    _PREV.update(t=now, cpu=cpu, net=net, app_bytes=_APP_BYTES[0],
                 ticks={p["pid"]: p["cpu_s"] for p in procs or []}, self_cpu=time.process_time())
    dt = now - prev["t"] if prev else 0
    if cpu and prev.get("cpu") and cpu[1] > prev["cpu"][1]:
        out["cpu"] = round(100 * (cpu[0] - prev["cpu"][0]) / (cpu[1] - prev["cpu"][1]), 1)
    m = machine()
    if m["total"]:
        out["mem"] = (m["total"] - m["available"]) // MB
    if procs is not None:
        me, tree = os.getpid(), {os.getpid()}
        children: dict[int, list] = {}
        for p in procs:
            children.setdefault(p["ppid"], []).append(p["pid"])
        stack = [me]
        while stack:
            for c in children.get(stack.pop(), []):
                if c not in tree:
                    tree.add(c)
                    stack.append(c)
        rows_app, rows_other = [], []
        for p in procs:
            pcpu = round(100 * (p["cpu_s"] - prev.get("ticks", {}).get(p["pid"], p["cpu_s"])) / dt / ncpu, 1) if dt else 0.0
            row = {"pid": p["pid"], "name": p["name"], "cpu": max(0.0, pcpu), "mem": p["rss"] // MB}
            (rows_app if p["pid"] in tree else rows_other).append(
                row | {"role": "Portal" if p["pid"] == me else "Started by the portal"} if p["pid"] in tree else row)
        _PROCS.update(app=sorted(rows_app, key=lambda r: -r["mem"]),
                      other=engine.run("memory.other_services", {"procs": rows_other}), supported=True)
        out["cpu_app"] = round(sum(r["cpu"] for r in rows_app), 1)
        out["mem_app"] = sum(r["mem"] for r in rows_app)
    elif dt and prev.get("self_cpu") is not None:
        out["cpu_app"] = round(100 * (time.process_time() - prev["self_cpu"]) / dt / ncpu, 1)
        out["mem_app"] = rss() // MB
    if "cpu" in out and "cpu_app" in out:
        out["cpu_app"] = min(out["cpu_app"], out["cpu"])
    if "mem" in out and "mem_app" in out:
        out["mem_app"] = min(out["mem_app"], out["mem"])
    if dt:
        if net is not None and prev.get("net") is not None:
            out["net"] = round(max(0, net - prev["net"]) / dt / 1024, 1)
        out["net_app"] = round(max(0, _APP_BYTES[0] - prev.get("app_bytes", 0)) / dt / 1024, 1)
    return out


# --- facts: disk --------------------------------------------------------------------------------

def _dir_bytes(path: Path, skip: Path | None = None) -> int:
    total, stack = 0, [str(path)]
    skip_s = str(skip) if skip else None
    while stack:
        try:
            with os.scandir(stack.pop()) as it:
                for e in it:
                    try:
                        if e.is_dir(follow_symlinks=False):
                            if e.path != skip_s:
                                stack.append(e.path)
                        elif e.is_file(follow_symlinks=False):
                            total += e.stat(follow_symlinks=False).st_size
                    except OSError:
                        pass
        except OSError:
            pass
    return total


def refresh_disk() -> dict:
    root, data = store.ROOT.resolve(), store.DATA.resolve()
    du = shutil.disk_usage(data if data.exists() else root)
    inside = str(data).startswith(str(root))
    parts = [{"label": "Portal code", "path": str(root), "mb": _dir_bytes(root, data if inside else None) // MB},
             {"label": "Data", "path": str(data), "mb": _dir_bytes(data) // MB}]
    for p in [x.strip() for x in os.getenv("PORTAL_DISK_PATHS", "").split(os.pathsep) if x.strip()]:
        if Path(p).is_dir():
            parts.append({"label": Path(p).name, "path": p, "mb": _dir_bytes(Path(p)) // MB})
    used = (du.total - du.free) // MB
    _DISK.clear()
    _DISK.update({"at": _now(), "total_mb": du.total // MB, "used_mb": used, "free_mb": du.free // MB, "parts": parts,
                  **engine.run("memory.disk_split", {"used_mb": used, "parts": parts})})
    return _DISK


# --- sampling -----------------------------------------------------------------------------------

def children_rss() -> int:
    return sum(r["mem"] for r in _PROCS["app"] if r["pid"] != os.getpid()) * MB


def sample(path: str = "") -> dict:
    host = host_sample()
    own = rss() // MB
    row = {"t": _now(), "rss": own + children_rss() // MB, **host}
    with _LOCK:
        SAMPLES.append(row)
        if row["rss"] > _PEAK["rss"]:
            _PEAK.update(rss=row["rss"], at=row["t"], path=path)
    return row


def tell(row: dict) -> None:
    """Server tells: open Memory watch pages re-read after a new reading (no page timer). Nobody listening = nothing sent."""
    if events.listening(SCREEN_KEY):
        events.publish(SCREEN_KEY, "memory", {"t": row["t"]}, replay=False)


def _loop() -> None:
    last_disk = 0.0
    while True:
        try:
            tell(sample())
            if time.time() - last_disk >= _S["disk_every_seconds"]:
                last_disk = time.time()
                refresh_disk()
            fire_rules()
        except Exception:  # noqa: BLE001 - the watcher must never be the thing that dies
            pass
        time.sleep(_S["sample_seconds"])


_DAY = {"date": ""}


def fire_rules() -> None:
    """Hand the latest reading to the rules (server.sample), and once a UTC day the daily trigger."""
    snap = snapshot()
    v = snap["verdict"]
    host = snap["samples"][-1] if snap["samples"] else {}
    rules.fire("server.sample", {"rss_mb": snap["rss_mb"], "limit_mb": snap["limit_mb"], "pct": v.get("pct"),
                                 "climb_mb": v.get("climb_mb"), "level": v["level"], "title": v["title"],
                                 "message": v["message"], "cpu": host.get("cpu"),
                                 "disk_free_mb": _DISK.get("free_mb"),
                                 "spike_path": (engine.run("memory.spike", {"events": list(EVENTS)}) or {}).get("path", "")})
    today = datetime.now(timezone.utc)
    if _DAY["date"] != today.date().isoformat():
        first = not _DAY["date"]
        _DAY["date"] = today.date().isoformat()
        if not first:  # a restart is not a new day
            rules.fire("daily", {"date": _DAY["date"], "weekday": today.strftime("%A"), "accounts": len(store.users()),
                                 "disk_free_mb": _DISK.get("free_mb"),
                                 "data_mb": next((p["mb"] for p in _DISK.get("parts", []) if p["label"] == "Data"), None)})


def start() -> None:
    global _started
    if _started:
        return
    _started = time.time()
    threading.Thread(target=_loop, name="memwatch", daemon=True).start()


def note_request(method: str, path: str, before: int, status: int, ms: int) -> None:
    """Request middleware hook (before = rss() bytes when the request started)."""
    if not before:
        return
    after = rss()
    facts = {"before_mb": before // MB, "after_mb": after // MB, "limit_mb": _limit_mb()}
    try:
        if not engine.run("memory.is_move", facts):
            return
        with _LOCK:
            EVENTS.append({"t": _now(), "method": method, "path": path, "status": status, "ms": ms,
                           "before": facts["before_mb"], "after": facts["after_mb"],
                           "delta": facts["after_mb"] - facts["before_mb"]})
            if facts["after_mb"] > _PEAK["rss"]:
                _PEAK.update(rss=facts["after_mb"], at=_now(), path=f"{method} {path}")
        if engine.run("memory.should_log", facts):
            print(f"[mem] {method} {path} rss {facts['before_mb']}->{facts['after_mb']} MB "
                  f"({facts['after_mb'] - facts['before_mb']:+d}) in {ms} ms", file=sys.stderr, flush=True)
    except engine.ChipError:
        return  # a broken chip file must never take a request down


_LIMIT = {"at": 0.0, "mb": 0}


def _limit_mb() -> int:
    if time.time() - _LIMIT["at"] > 60:
        _LIMIT.update(at=time.time(), mb=int(limit()["mb"]))
    return _LIMIT["mb"]


# --- the page -----------------------------------------------------------------------------------

from core.access import may, screen  # noqa: E402 - access imports store/auth only, no cycle back here
from core import events  # noqa: E402

SCREEN_KEY = "s:memory"
events.KEYS.append(lambda u: [SCREEN_KEY] if may(u, "memory") else [])   # only those who may open the screen hear it


def snapshot() -> dict:
    with _LOCK:
        samples, events, peak = list(SAMPLES), list(EVENTS), dict(_PEAK)
    lim = limit()
    now_rss = rss() // MB + children_rss() // MB
    climb = engine.run("memory.climb_mb", {"rss_series": [s["rss"] for s in samples]}) or 0
    biggest = max(events, key=lambda e: e["delta"]) if events else None
    return {
        "rss_mb": now_rss, "limit_mb": lim["mb"], "limit_source": lim["source"],
        "started_at": STARTED_AT.isoformat(timespec="seconds"),
        "uptime_s": int((datetime.now(timezone.utc) - STARTED_AT).total_seconds()),
        "sample_seconds": _S["sample_seconds"], "reader": reader(), "pid": os.getpid(),
        "python": sys.version.split()[0], "platform": sys.platform,
        "peak": peak, "samples": samples,
        "events": events[-int(_S["events_shown"]):][::-1],
        "offenders": engine.run("memory.offenders", {"events": events}),
        "verdict": engine.run("memory.verdict", {"rss_mb": now_rss, "limit_mb": lim["mb"], "climb_mb": climb,
                                                 "spike": engine.run("memory.spike", {"events": events}),
                                                 "biggest": biggest}),
        "knobs": {"spike_mb": engine.knobs("memory.spike")["spike_mb"],
                  "warn_pct": engine.knobs("memory.verdict")["warn_pct"]},
        "host": {"cpu_count": os.cpu_count() or 1, "mem_total_mb": machine()["total"] // MB,
                 "disk": dict(_DISK), "procs_app": list(_PROCS["app"]), "procs_other": list(_PROCS["other"]),
                 "procs_supported": _PROCS["supported"]},
    }


@router.get("/api/core/memory")
def overview(_: dict = Depends(screen("memory"))):
    if not SAMPLES:
        sample()
    if not _DISK:
        refresh_disk()
    return snapshot()


@router.post("/api/core/memory/clear-events")
def clear_events(_: dict = Depends(screen("memory"))):
    with _LOCK:
        EVENTS.clear()
        _PEAK.update(rss=rss() // MB, at=_now(), path="")
    return {"ok": True}


if __name__ == "__main__":  # ponytail: one runnable self-check (the chips certify in core.engine)
    assert rss() > 1 * MB, f"this platform reports no memory at all ({rss()})"
    assert limit()["mb"] > 0
    first = sample()
    time.sleep(0.3)
    second = sample()
    assert second["rss"] > 0 and ("cpu" in second or os.name not in ("nt", "posix")), second
    before = rss()
    big = bytearray(os.urandom(1) * (30 * MB))              # touched pages, so resident
    note_request("GET", "/x", before, 200, 1)
    assert EVENTS and EVENTS[-1]["path"] == "/x" and EVENTS[-1]["delta"] >= 20, list(EVENTS)   # ponytail: 30 MB touched reads ~24 resident on Windows (flaky at 25, 2026-11-16)
    refresh_disk()
    assert _DISK["total_mb"] > 0 and _DISK["app_mb"] + _DISK["other_mb"] == _DISK["used_mb"], _DISK
    snap = snapshot()
    assert snap["verdict"]["level"] in {"ok", "watch", "warn", "kill"} and snap["offenders"][0]["key"] == "GET /x", snap["offenders"]
    del big

    # The Linux readers, against a fake proc tree (so they are proven on any machine, the VPS included).
    import tempfile
    me = os.getpid()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        def proc(pid, name, ppid, ticks, pages):
            (root / str(pid)).mkdir(exist_ok=True)
            (root / str(pid) / "stat").write_text(f"{pid} ({name}) S {ppid} 0 0 0 0 0 0 0 0 0 {ticks} 0 0 0", encoding="ascii")
            (root / str(pid) / "statm").write_text(f"{pages * 2} {pages} 0 0 0 0 0", encoding="ascii")

        (root / "net").mkdir()
        (root / "self").mkdir()
        (root / "self" / "statm").write_text("100 256 0", encoding="ascii")
        (root / "meminfo").write_text("MemTotal: 4194304 kB\nMemAvailable: 1048576 kB\n", encoding="ascii")

        def tick(cpu_busy, net, portal_ticks):
            (root / "stat").write_text(f"cpu  {cpu_busy} 0 0 {1000 * (1 + cpu_busy // 300) - cpu_busy} 0 0 0 0 5 0\ncpu0 1 1 1 1\n", encoding="ascii")
            (root / "net" / "dev").write_text("h1\nh2\n  eth0: " + f"{net} 0 0 0 0 0 0 0 {net} 0 0 0 0 0 0 0\n"
                                              + f"docker0: {net * 50} 0 0 0 0 0 0 0 {net * 50} 0 0 0 0 0 0 0\n", encoding="ascii")
            proc(me, "python3", 1, portal_ticks, 25600)            # 100 MB
            proc(4242, "ffmpeg", me, 0, 12800)                     # 50 MB, started by the portal
            proc(7, "nginx", 1, 0, 2560)
            proc(8, "nginx", 1, 0, 2560)
        PROC, saved = str(root), dict(_PREV)
        _PREV.clear()
        tick(100, 0, 0)
        host_sample()
        tick(300, 10240, 0)                                     # 200 of 1000 busy ticks
        _PREV["t"] = time.time() - 10                           # ten seconds later… (after the writes, so slow disks can't stretch dt)
        h = host_sample()
        assert h["cpu"] == 20.0, h
        assert h["mem"] == 3072 and h["mem_app"] == 150, h      # the whole tree: portal + ffmpeg
        assert h["net"] == 2.0, ("docker0 never counts", h)     # 20480 bytes / 10 s / 1024
        assert {r["name"] for r in _PROCS["app"]} == {"python3", "ffmpeg"}, _PROCS["app"]
        assert _PROCS["other"] == [{"key": "nginx", "name": "nginx", "count": 2, "cpu": 0, "mem": 20}], _PROCS["other"]
        assert rss() == 256 * 4096
        PROC = "/proc"
        _PREV.clear()
        _PREV.update(saved)
    print("core.memwatch self-check OK")
