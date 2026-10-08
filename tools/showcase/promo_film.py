"""The public marketing film (piece 10 of a domain portal): chip promo.film -> <out_dir>/<out>.{mp4,jpg,vtt}.

    python tools/showcase/promo_film.py            # build the film
    python tools/showcase/promo_film.py --sheet    # and a contact sheet in tmp/promo/ to look at before sending it

Every word, the voice, the colours, the folders and which seconds of which showcase film each scene shows are the chip; this file only
renders. A card scene is drawn as a page (Playwright) in the chip's skin colours; a clip scene cuts the showcase film from
`start` for as long as its voice-over (edge-tts, free neural voices) runs, with the scene's label as a lower third.
Product-neutral: no domain word lives here, so it can move to the reference (SimplyFile) as boilerplate unchanged.
"""
import asyncio
import html
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
WORK = ROOT / "tmp" / "promo"


def film() -> dict:
    from core import engine  # noqa: PLC0415
    engine.register_dir(ROOT / "chips")   # the domain's own chips, as app.py registers them
    return engine.run("promo.film")


def ffmpeg() -> str:
    import imageio_ffmpeg  # noqa: PLC0415
    return imageio_ffmpeg.get_ffmpeg_exe()


def run(args: list) -> None:
    r = subprocess.run([ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", *map(str, args)], capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"ffmpeg failed: {r.stderr[-800:]}")


def seconds(path: Path) -> float:
    r = subprocess.run([ffmpeg(), "-hide_banner", "-i", str(path)], capture_output=True, text=True)
    h, m, s = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr).groups()
    return int(h) * 3600 + int(m) * 60 + float(s)


def spoken(text: str) -> str:
    """The narrator's lexicon (tools/tour_video/_lexicon.json), as make_tour applies it to every tour."""
    lex = json.loads((ROOT / "tools" / "tour_video" / "_lexicon.json").read_text(encoding="utf-8"))["say_as"]
    for word, say in lex.items():
        text = re.sub(rf"(?<!\w){re.escape(word)}(?!\w)", say, text)
    return text


async def voices(f: dict) -> list[Path]:
    import edge_tts  # noqa: PLC0415
    out = []
    for i, sc in enumerate(f["scenes"]):
        p = WORK / f"vo{i:02d}.mp3"
        await edge_tts.Communicate(spoken(sc["say"]), f["voice"], rate=f["rate"]).save(str(p))   # the tours' lexicon: "Tradify", not "Trady F Y"
        out.append(p)
    return out


def card_html(sc: dict, k: dict, w: int, h: int) -> str:
    e = lambda s: html.escape(str(s or ""))  # noqa: E731
    steps = "".join(f'<li><b>{i + 1}</b>{e(t)}</li>' for i, t in enumerate(sc.get("steps") or []))
    return f"""<!doctype html><meta charset="utf-8"><style>
body{{margin:0;width:{w}px;height:{h}px;font-family:'Segoe UI',system-ui,sans-serif;color:{k['on_night']};
  background:radial-gradient(1100px 560px at 80% 0%,color-mix(in srgb,{k['brand']} 32%,transparent),transparent 60%),
  radial-gradient(800px 480px at 0% 100%,color-mix(in srgb,{k['gold']} 16%,transparent),transparent 55%),{k['night']};
  display:flex;flex-direction:column;justify-content:center;padding:0 120px;box-sizing:border-box}}
.eb{{color:{k['gold']};font-weight:700;letter-spacing:.14em;text-transform:uppercase;font-size:24px;margin-bottom:22px}}
h1{{font-size:92px;line-height:1.02;margin:0 0 26px;font-weight:800;letter-spacing:-.025em}}
p{{font-size:36px;line-height:1.35;color:{k['on_night_2']};margin:0;max-width:1100px}}
ol{{list-style:none;padding:0;margin:34px 0 0;display:flex;gap:22px}}
li{{flex:1;background:{k['night_2']};border:1px solid rgba(255,255,255,.10);border-radius:16px;padding:26px 24px;font-size:28px;font-weight:600}}
li b{{display:inline-grid;place-items:center;width:44px;height:44px;border-radius:50%;background:{k['brand']};margin-right:14px;font-size:24px}}
.btn{{display:inline-block;margin-top:40px;background:{k['brand']};padding:22px 40px;border-radius:12px;font-size:34px;font-weight:700;
  box-shadow:0 14px 34px -12px color-mix(in srgb,{k['brand']} 90%,transparent)}}
.url{{margin-top:22px;font-size:34px;color:{k['gold']};font-weight:600}}
.note{{position:absolute;bottom:44px;left:120px;font-size:22px;color:{k['on_night_2']}}}
</style><div class="eb">{e(sc.get('eyebrow'))}</div><h1>{e(sc.get('title'))}</h1>{f"<p>{e(sc['sub'])}</p>" if sc.get('sub') else ''}
<ol>{steps}</ol>{f'<div><span class="btn">{e(sc["button"])}</span></div>' if sc.get('button') else ''}
{f'<div class="url">{e(sc["url"])}</div>' if sc.get('url') else ''}{f'<div class="note">{e(sc["note"])}</div>' if sc.get('note') else ''}"""


def label_html(text: str, k: dict, w: int, h: int) -> str:
    return f"""<!doctype html><meta charset="utf-8"><style>html,body{{margin:0;background:transparent;width:{w}px;height:{h}px}}
div{{position:absolute;left:48px;bottom:48px;font-family:'Segoe UI',system-ui,sans-serif;background:{k['night']}E6;color:{k['on_night']};
  font-size:34px;font-weight:700;padding:18px 30px;border-radius:14px;border-left:8px solid {k['gold']}}}</style><div>{html.escape(text)}</div>"""


async def pictures(f: dict) -> None:
    from playwright.async_api import async_playwright  # noqa: PLC0415
    w, h = f["size"]
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        page = await b.new_page(viewport={"width": w, "height": h})
        for i, sc in enumerate(f["scenes"]):
            if sc["kind"] == "card":
                await page.set_content(card_html(sc, f["skin"], w, h))
                await page.screenshot(path=str(WORK / f"card{i:02d}.png"))
            elif sc.get("label"):
                await page.set_content(label_html(sc["label"], f["skin"], w, h))
                await page.screenshot(path=str(WORK / f"label{i:02d}.png"), omit_background=True)
        await b.close()


def segment(i: int, sc: dict, vo: Path, f: dict) -> tuple[Path, float]:
    w, h = f["size"]
    dur = round(seconds(vo) + float(f["pad_seconds"]), 2)
    fade = float(f["fade_seconds"])
    out = WORK / f"seg{i:02d}.mp4"
    look = f"fps={f['fps']},setsar=1,format=yuv420p,fade=t=in:st=0:d={fade},fade=t=out:st={dur - fade}:d={fade}"
    audio = ["-map", "1:a", "-af", f"apad=whole_dur={dur}", "-c:a", "aac", "-ar", "24000", "-ac", "1", "-b:a", "96k"]
    enc = ["-c:v", "libx264", "-preset", "medium", "-crf", "22", "-t", dur, "-movflags", "+faststart"]
    if sc["kind"] == "card":
        run(["-loop", 1, "-t", dur, "-i", WORK / f"card{i:02d}.png", "-i", vo, "-map", "0:v", "-vf", look, *audio, *enc, out])
    else:
        src = ROOT / f["sources_dir"] / sc["source"]
        if seconds(src) < float(sc["start"]) + dur:
            raise SystemExit(f"scene {i + 1}: {sc['source']} ends before {sc['start']} + {dur}s - pick an earlier start or say less")
        scale = f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2"
        if sc.get("label"):
            run(["-ss", sc["start"], "-t", dur, "-i", src, "-i", vo, "-loop", 1, "-t", dur, "-i", WORK / f"label{i:02d}.png",
                 "-filter_complex", f"[0:v]{scale}[b];[b][2:v]overlay=0:0,{look}[v]", "-map", "[v]", *audio, *enc, out])
        else:
            run(["-ss", sc["start"], "-t", dur, "-i", src, "-i", vo, "-map", "0:v", "-vf", f"{scale},{look}", *audio, *enc, out])
    return out, dur


def stamp(t: float) -> str:
    return f"{int(t // 3600):02d}:{int(t % 3600 // 60):02d}:{t % 60:06.3f}"


def main() -> None:
    f = film()
    WORK.mkdir(parents=True, exist_ok=True)
    vo = asyncio.run(voices(f))
    asyncio.run(pictures(f))
    segs, cues, t = [], [], 0.0
    for i, sc in enumerate(f["scenes"]):
        p, dur = segment(i, sc, vo[i], f)
        segs.append(p)
        cues.append(f"{i + 1}\n{stamp(t)} --> {stamp(t + dur - float(f['pad_seconds']))}\n{sc['say']}\n")
        t += dur
    dest = ROOT / f["out_dir"]
    dest.mkdir(parents=True, exist_ok=True)
    mp4 = dest / f"{f['out']}.mp4"
    # joined by re-encoding (concat filter), not stream copy: a still-image scene and a footage scene differ in timebase,
    # and the copy join dropped the cards (2026-10-06 first cut)
    joins = "".join(f"[{i}:v][{i}:a]" for i in range(len(segs))) + f"concat=n={len(segs)}:v=1:a=1[v][a]"
    run([x for p in segs for x in ("-i", p)] + ["-filter_complex", joins, "-map", "[v]", "-map", "[a]", "-c:v", "libx264",
         "-preset", "medium", "-crf", "22", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "24000", "-ac", "1", "-b:a", "96k",
         "-movflags", "+faststart", mp4])
    (dest / f"{f['out']}.vtt").write_text("WEBVTT\n\n" + "\n".join(cues), encoding="utf-8")
    first = next((i for i, sc in enumerate(f["scenes"]) if sc["kind"] == "card"), None)
    if first is not None:
        run(["-i", WORK / f"card{first:02d}.png", "-q:v", 3, dest / f"{f['out']}.jpg"])
    print(f"{mp4.relative_to(ROOT)}: {seconds(mp4):.1f} s, {len(segs)} scenes, {mp4.stat().st_size / 1e6:.1f} MB")
    if "--sheet" in sys.argv:
        run(["-i", mp4, "-vf", "fps=1/4,scale=360:-1,tile=4x5", "-frames:v", 1, WORK / "sheet.png"])
        print(f"contact sheet: {(WORK / 'sheet.png').relative_to(ROOT)}")
    print(json.dumps({"scenes": [round(seconds(p), 1) for p in segs]}))


if __name__ == "__main__":
    main()
