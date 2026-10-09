"""The landing page's "Every screen, one by one" (owner 2026-10-09: "add the tours to the landing page Watch section").
Each work screen's recorded Tour Video (tmp/tour_video/<prefix>-<screen>/) is re-encoded small and streamable into
static/showcase/<prefix>-screen-<screen>.{mp4,jpg,vtt} and listed in chip showcase.page as a chapter of its own group.
Which screens, the group's words and the prefix: chip showcase.screen_tours. Only a video newer than its tour script and
its Guide me goes public - a stale one is named and left out (re-record it, run this again). Admin screens never: the chip
lists work screens only. Run after showcase_films.py (that one rewrites its own films; this one keeps them).

    python tools/showcase/screen_films.py
"""
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "tmp" / "tour_video"
OUT = ROOT / "static" / "showcase"


def chip(name: str) -> tuple[Path, dict]:
    p = ROOT / "chips" / f"{name}.json"
    return p, json.loads(p.read_text(encoding="utf-8"))


def knobs(c: dict) -> dict:
    return {x["name"]: x["default"] for x in c["params"]}


def fresh(key: str, screen: str) -> bool:
    mp4, tour, guide = SRC / key / f"{key}.mp4", ROOT / "tours" / f"{key}.json", ROOT / "chips" / f"guide.{screen}.json"
    script = max(tour.stat().st_mtime if tour.is_file() else 0, guide.stat().st_mtime if guide.is_file() else 0)
    return mp4.is_file() and mp4.stat().st_mtime >= script


def marks(key: str) -> tuple[str, list[dict]]:
    lines = (SRC / key / "description.txt").read_text(encoding="utf-8").splitlines()
    rows = [{"t": int(m.group(1)) * 60 + int(m.group(2)), "title": m.group(3).strip()}
            for m in (re.match(r"(\d+):(\d\d)\s+(.+)", ln.strip()) for ln in lines) if m]
    return (lines[0].strip() if lines else key), rows


def encode(ff: str, key: str, out: str) -> None:
    src = SRC / key / f"{key}.mp4"
    if (OUT / f"{out}.mp4").exists() and (OUT / f"{out}.mp4").stat().st_mtime > src.stat().st_mtime:
        return
    subprocess.run([ff, "-loglevel", "error", "-y", "-i", str(src), "-c:v", "libx264", "-preset", "slow", "-crf", "30", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(OUT / f"{out}.mp4")], check=True)
    secs = sum(float(x) * m for x, m in zip(re.search(r"Duration: ([\d:.]+)", subprocess.run([ff, "-i", str(src)], capture_output=True, text=True).stderr)
                                                .group(1).split(":"), (3600, 60, 1)))
    subprocess.run([ff, "-loglevel", "error", "-y", "-ss", f"{secs * 0.3:.1f}", "-i", str(src), "-frames:v", "1", "-vf", "scale=960:-2", "-q:v", "4",
                    str(OUT / f"{out}.jpg")], check=True)
    srt = (SRC / key / f"{key}.srt").read_text(encoding="utf-8")
    (OUT / f"{out}.vtt").write_bytes(("WEBVTT\n\n" + re.sub(r"(\d\d:\d\d:\d\d),(\d\d\d)", r"\1.\2", srt)).encode("utf-8"))


def main() -> None:
    import imageio_ffmpeg  # noqa: PLC0415
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    _, st = chip("showcase.screen_tours")
    S = knobs(st)
    OUT.mkdir(parents=True, exist_ok=True)
    rows, left = [], []
    for s in S["screens"]:
        key = f"{S['prefix']}-{s['screen']}"
        if not fresh(key, s["screen"]):
            left.append(s["screen"])
            continue
        out = f"{S['prefix']}-screen-{s['screen']}"
        encode(ff, key, out)
        title, mk = marks(key)
        rows.append({"key": out, "group": S["group"]["id"], "title": s.get("title") or title, "module": S["module"],
                     "line": s["line"], "tags": s.get("tags") or [], "marks": mk})
        print(out, (OUT / f"{out}.mp4").stat().st_size // 1024, "KB")
    p, c = chip("showcase.page")
    P = {x["name"]: x for x in c["params"]}
    P["chapters"]["default"] = [x for x in P["chapters"]["default"] if x.get("group") != S["group"]["id"]] + rows
    groups = P["theatre"]["default"].setdefault("groups", [])
    P["theatre"]["default"]["groups"] = [g for g in groups if g.get("id") != S["group"]["id"]] + ([S["group"]] if rows else [])
    c["version"] = c.get("version", 1) + 1
    p.write_bytes((json.dumps(c, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    import sys  # noqa: PLC0415
    sys.path.insert(0, str(ROOT))
    from core import engine  # noqa: PLC0415 - the test holds what the engine answers (a portal may fill {product})
    engine.register_dir(ROOT / "chips")
    engine.refresh()
    got = engine.run("showcase.page")
    for t in c.get("test_cases", []):
        t["expect_value"] = {k: got[k] for k in c["expr"]["fields"]}
    p.write_bytes((json.dumps(c, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(f"showcase.page: {len(rows)} screen tour(s) on the landing page" + (f"; left out, stale or not recorded: {', '.join(left)}" if left else ""))


if __name__ == "__main__":
    main()
