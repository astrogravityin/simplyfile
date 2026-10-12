"""The landing page's "Every filing, step by step" (2026-10-11 owner: "every demo use case must have its own step-by-step video on the
demo site and on the main landing page's Watch section"). Each worked example of chip wizard.cases has its film recorded
(tools/showcase/record_cases.sh -> tmp/tour_video/sf-case-<id>/); this re-encodes it small and streamable into
static/showcase/sf-case-<id>.{mp4,jpg,vtt} (the file New filing's Watch how plays, and the landing's) and lists it in chip
showcase.page as a chapter of its own group (chip showcase.case_films: the group's words, its tags). Only its own group is
rewritten: every other chapter and group (the films, the screen tours - screen_films.py) is kept as it is. A film older than its
tour script is named and left out. Run after screen_films.py:

    python tools/showcase/case_films.py
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import screen_films as sf  # noqa: E402 - the same encoder, marks reader and chip helpers


def main() -> None:
    import imageio_ffmpeg  # noqa: PLC0415
    from core import engine  # noqa: PLC0415
    import store  # noqa: F401,PLC0415 - registers the portal's chips
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    K = sf.knobs(sf.chip("showcase.case_films")[1])
    cases = engine.run("wizard.cases")["rows"]
    sf.OUT.mkdir(parents=True, exist_ok=True)
    rows, left = [], []
    for c in cases:
        key = c["film"]
        mp4, tour = sf.SRC / key / f"{key}.mp4", ROOT / "tours" / f"{key}.json"
        if not mp4.is_file() or mp4.stat().st_mtime < tour.stat().st_mtime:
            left.append(c["id"])
            continue
        sf.encode(ff, key, key)
        _, mk = sf.marks(key)
        rows.append({"key": key, "group": K["group"]["id"], "title": c["title"], "module": c["form"], "line": c["line"],
                     "tags": K["tags"] + [c["form"]], "marks": mk})
        print(key, (sf.OUT / f"{key}.mp4").stat().st_size // 1024, "KB")
    p, ch = sf.chip("showcase.page")
    P = {x["name"]: x for x in ch["params"]}
    others = [x for x in P["chapters"]["default"] if x.get("group") != K["group"]["id"]]
    at = next((i for i, x in enumerate(others) if x.get("group") == K["before"]), len(others))
    P["chapters"]["default"] = others[:at] + rows + others[at:]
    th = P["theatre"]["default"]
    groups = [g for g in th.get("groups") or [] if g.get("id") != K["group"]["id"]]
    gi = next((i for i, g in enumerate(groups) if g.get("id") == K["before"]), len(groups))
    th["groups"] = groups[:gi] + ([K["group"]] if rows else []) + groups[gi:]
    for t in K["topics"]:
        if rows and t not in th.setdefault("topics", []):
            th["topics"].append(t)
    pl = P["play"]["default"]                                   # Try it live: the demo's counts with the worked examples in
    if rows:
        pl["sub"] = re.sub(K["play_sub_from"], K["play_sub_to"], pl["sub"], count=1)
        pl["window"]["rows"] = [[a, K["play_counts"].get(a, b)] for a, b in pl["window"]["rows"]]
        pl["tries"] = [x for x in pl["tries"] if x[:30] != K["play_try"][:30]] + [K["play_try"]]   # this one, said once
    ch["version"] = ch.get("version", 1) + 1
    p.write_bytes((json.dumps(ch, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    engine.refresh()
    got = engine.run("showcase.page")
    for t in ch.get("test_cases", []):
        t["expect_value"] = {k: got[k] for k in ch["expr"]["fields"]}
    p.write_bytes((json.dumps(ch, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(f"showcase.page: {len(rows)} worked-example film(s) on the landing page" + (f"; left out, stale or not recorded: {', '.join(left)}" if left else ""))


if __name__ == "__main__":
    main()
