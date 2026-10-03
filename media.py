"""Voice, video and what a model call costs.

ffmpeg arrives with `imageio-ffmpeg` (a wheel, no system install), voices with `edge-tts` (free,
no key). So the only thing in this portal that ever costs money is the Gemini call behind
"Draft with AI", and this file is where its price is worked out.

Prices, speaking pace, timing gaps, mix levels and the ffmpeg output patterns are the chip
`media.settings`; the one sentence this file says is in `media.messages`. Python runs ffmpeg and does
the arithmetic.
"""
from __future__ import annotations

import json
import math
import re
import subprocess
from pathlib import Path

from core import engine


def is_picture(data: bytes) -> bool:
    """THE test of "is this really a picture" (2026-10-02 review: articles and books each had a copy, Ads and Katha borrowed
    a private one): Pillow can read it, whatever its name says - a fake .png made a book's PDF fail."""
    import io  # noqa: PLC0415
    from PIL import Image  # noqa: PLC0415
    try:
        Image.open(io.BytesIO(data)).verify()
        return True
    except Exception:  # noqa: BLE001 - any reason it cannot be read: not a picture
        return False

ROOT = Path(__file__).resolve().parent
engine.register_dir(ROOT / "chips")


def _cfg() -> dict:
    return engine.run("media.settings")


def audio_args() -> list[str]:
    """THE audio a file is written with (chip media.settings): codec, bitrate, sample rate, channels. 2026-10-02 (sm Ads,
    "no voice narration"): the loudness pass wrote 96 kHz mono, the title cards 48 kHz stereo, and the export joined
    them by stream copy - the voice went silent after the first card. Every writer of audio uses this, so pieces always
    match."""
    cfg = _cfg()
    return ["-c:a", cfg["audio_codec"], "-b:a", cfg["audio_bitrate"], "-ar", str(int(cut_settings()["sample_rate"])), "-ac", str(int(cfg["audio_channels"]))]


def __getattr__(name: str):
    """`media.VIDEO_TOKENS_PER_SECOND`, `media.WORDS_PER_SECOND` and `media.PRICES` still answer for callers
    written before the chips — read live from `media.settings`."""
    if name in ("VIDEO_TOKENS_PER_SECOND", "WORDS_PER_SECOND"):
        return _cfg()[name.lower()]
    if name == "PRICES":
        return {r["model"]: {"in": r["in"], "out": r["out"]} for r in _cfg()["prices"]}
    raise AttributeError(name)


def cost_usd(model: str, tokens_in: int, tokens_out: int) -> float | None:
    """US dollars for one call. Unknown model → None and the screen says "unknown", never "$0.00" — a
    price we cannot work out is not a price of zero. The longest price row the model name starts with wins."""
    cfg = _cfg()
    name = (model or "").strip().split(cfg["model_path_separator"])[-1]
    row = max((r for r in cfg["prices"] if name.startswith(r["model"])), key=lambda r: len(r["model"]), default=None)
    if row is None:
        # 2026-09-19 a model of another provider (chip providers.models) is priced there
        import providers  # noqa: PLC0415
        row = providers.price_row((model or "").strip())
    if row is None:
        return None
    per = cfg["tokens_per_price_unit"]
    return round(tokens_in / per * row["in"] + tokens_out / per * row["out"], 6)


def ffmpeg() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return _cfg()["ffmpeg_command"]


def fit_still_command(src: Path, dst: Path, aspect: str) -> list[str]:
    """Centre-crop a picture to `aspect` ("9:16"), so a clip started from it is that shape - no black bars."""
    w, h = (float(n) for n in aspect.split(":"))
    a = w / h
    return [ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
            "-vf", f"crop='min(iw,ih*{a:.6f})':'min(ih,iw/{a:.6f})',scale=trunc(iw/2)*2:trunc(ih/2)*2", "-frames:v", "1", str(dst)]


_BOXES: dict = {}


def picture_box(path: Path) -> tuple[int, int] | None:
    """The picture's own width and height inside the frame, black bars cut away (ffmpeg cropdetect, chip
    media.settings box_*). 2026-09-21: a 9:16 clip held a square picture in bars, which only a person watching saw.
    Remembered per file identity, like duration()."""
    st = Path(path).stat()
    key = (str(path), st.st_mtime_ns, st.st_size)
    if key not in _BOXES:
        k = _cfg()
        r = subprocess.run([ffmpeg(), "-hide_banner", "-ss", str(k["box_probe_at_s"]), "-i", str(path), "-t", "1",
                            "-vf", k["box_filter"], "-f", "null", "-"], capture_output=True, text=True)
        got = re.findall(k["crop_pattern"], r.stderr)
        while len(_BOXES) >= int(k["duration_cache_max"]):
            _BOXES.pop(next(iter(_BOXES)))
        _BOXES[key] = (int(got[-1][0]), int(got[-1][1])) if got else None
    return _BOXES[key]


def frame_size(path: Path) -> tuple[int, int] | None:
    """A video's own width and height, or None when ffmpeg names none. 2026-09-21, the owner's first full run:
    9:16 clips (720x1280) were joined at the chip's LANDSCAPE default (1280x720), so the export shrank a vertical
    picture into a wide frame and back again - a postage stamp in the middle of the screen.
    2026-10-03 owner: "I checked it" ran 15-55 s - the final check asked ffmpeg once per clip and per export on every
    run, three runs per tick. Remembered per file identity, like duration()."""
    m = re.search(_cfg()["frame_size_pattern"], _info(path))
    return (int(m[1]), int(m[2])) if m else None


def _info(path: Path) -> str:
    """What `ffmpeg -i` says about a file, remembered per file identity (path, modified time, size). frame_size,
    video_codec, fps and has_audio all read it: one probe per file, never one per question and per page load."""
    try:
        st = Path(path).stat()
    except OSError:
        return ""                                    # no file: nothing to read, as ffmpeg itself would say
    key = (str(path), st.st_mtime_ns, st.st_size)
    if key not in _INFO:
        r = subprocess.run([ffmpeg(), "-i", str(path)], capture_output=True, text=True)
        while len(_INFO) >= int(_cfg()["duration_cache_max"]):          # the cap is chip media.settings
            _INFO.pop(next(iter(_INFO)))
        _INFO[key] = r.stderr
    return _INFO[key]


_INFO: dict = {}   # ponytail: per process; a restart probes each file once more


def duration(path: Path) -> float:
    """A file's length. 2026-09-19: Sound's status asked ffmpeg once per clip on EVERY page load (7 clips = 2 s,
    1,200 = minutes). Remembered per file identity (path, modified time, size): a changed file is measured again."""
    st = Path(path).stat()
    key = (str(path), st.st_mtime_ns, st.st_size)
    if key in _DURATIONS:
        return _DURATIONS[key]
    r = subprocess.run([ffmpeg(), "-i", str(path)], capture_output=True, text=True)
    m = re.search(_cfg()["duration_pattern"], r.stderr)
    if not m:
        raise RuntimeError(engine.say("media.messages", "no_duration", name=Path(path).name))
    secs = int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])
    while len(_DURATIONS) >= int(_cfg()["duration_cache_max"]):          # the cap is chip media.settings
        _DURATIONS.pop(next(iter(_DURATIONS)))                            # oldest first
    _DURATIONS[key] = secs
    return secs


_DURATIONS: dict = {}   # ponytail: per process; a restart measures each clip once more


def video_codec(path: Path) -> str:
    """The picture format inside the recording ("h264", "hevc", "vp9"); "" when ffmpeg says nothing."""
    m = re.search(engine.setting("media.playback", "video_stream_pattern"), _info(path))
    return (m[1] if m else "").lower()


def fps(path: Path) -> float | None:
    """Frames per second of a recording, from ffmpeg's stream line; None when it says none (a still picture)."""
    m = re.search(_cfg()["fps_pattern"], _info(path))
    return float(m[1]) if m else None


def has_audio(path: Path) -> bool:
    return bool(re.search(_cfg()["audio_stream_pattern"], _info(path)))


def voices() -> dict:
    return json.loads((ROOT / _cfg()["voices_file"]).read_text(encoding="utf-8"))


def lexicon() -> dict:
    """How the voice should say your product's words — "tedbook" → "Ted Book". Edited in Setup."""
    from store import read
    return read("lexicon", {})


def for_ear() -> str:
    """What a prompt that writes SPOKEN text tells the model (chip speech.rules) - one place for every module."""
    return engine.say("speech.rules", "for_ear")


def spoken(text: str) -> str:
    # 2026-09-30: a list page worked the same line out three times per scene, per card, per visit - kept by (lexicon, line)
    words = tuple((lexicon() or {}).items())
    if (words, text) not in _SPOKEN:
        while len(_SPOKEN) >= int(_cfg()["spoken_cache_max"]):           # the cap is chip media.settings
            _SPOKEN.pop(next(iter(_SPOKEN)))                              # oldest first
        _SPOKEN[(words, text)] = _spoken(words, text)
    return _SPOKEN[(words, text)]


_SPOKEN: dict = {}


def _spoken(words: tuple, text: str) -> str:
    for word, say in words:
        text = re.sub(rf"\b{re.escape(word)}\b", say, text)
    return text


def stamp(sec: float, srt: bool) -> str:
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return (f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int((s % 1) * 1000):03d}" if srt
            else f"{int(h * 60 + m):02d}:{int(s):02d}")


def caption_cues(text: str, start: float, length: float, most: int) -> list[tuple[float, float, str]]:
    """Split one spoken line into on-screen captions of at most `most` characters, cut between words (sentence ends
    first), each shown for its share of the spoken time. 2026-09-28 a 32 s narration was ONE caption cut at 270
    characters, so the screen showed "... lay empty. In te" and never the rest."""
    words, cues, cur = text.split(), [], ""
    for wd in words:
        if cur and len(cur) + 1 + len(wd) > most:
            # cut at the last sentence end past a third of the card, else the last comma past half - never "so / no dog"
            cut = max((cur.rfind(m) for m in (". ", "! ", "? ")), default=-1)
            if cut < len(cur) // 3:
                cut = cur.rfind(", ") if cur.rfind(", ") >= len(cur) // 2 else -1
            if cut > 0:
                cues.append(cur[:cut + 1])
                cur = f"{cur[cut + 2:]} {wd}"
            else:
                cues.append(cur)
                cur = wd
        else:
            cur = f"{cur} {wd}".strip()
        if cur.endswith((".", "!", "?")) and len(cur) > most * 0.6:   # a sentence that fills most of a card ends it
            cues.append(cur)
            cur = ""
    if cur:
        cues.append(cur)
    size = sum(len(c) for c in cues) or 1
    out, t = [], start
    for c in cues:
        d = length * len(c) / size
        out.append((t, t + d, c))
        t += d
    return out


def speech_window(segs: list[dict], i: int, total: float) -> float:
    """Seconds this line may speak before the next one starts (or the video ends)."""
    cfg = _cfg()
    nxt = segs[i + 1]["start"] if i + 1 < len(segs) else (total or segs[i]["end"])
    return max(cfg["min_window_seconds"], nxt - segs[i]["start"] - cfg["window_gap_seconds"])


def speed_up_percent(spoken_secs: float, window: float, cap: int | None = None) -> int:
    """How much faster to speak so `spoken_secs` fits `window`. 0 when it already fits."""
    if spoken_secs <= window:
        return 0
    cfg = _cfg()
    cap = cfg["speed_up_cap_percent"] if cap is None else cap
    return min(cap, math.ceil(round((spoken_secs / window - 1) * 100, 6)) + cfg["speed_up_margin_percent"])


def rescale_timeline(segs: list[dict], total: float) -> tuple[list[dict], float]:
    """Stretch a script whose times are plainly not seconds back onto the real video.

    2026-09-17: a draft came back with every line between 0 and 0.32 for a 54-second recording —
    the model answered in minutes. Every line then had a window of a few hundredths of a second,
    the whole narration piled up at the start, and the MP4 was a garble of voices talking over each
    other. If the words could not physically be said inside the span the model gave, the span is
    wrong, not the words: scale it to the video and say so. Returns the segments and the factor
    used (1.0 = untouched)."""
    if not segs or not total:
        return segs, 1.0
    cfg = _cfg()
    last = max(s["end"] for s in segs)
    span = last - min(s["start"] for s in segs)
    need = sum(len(str(s.get("text", "")).split()) for s in segs) / cfg["words_per_second"]
    if last >= total * cfg["timeline_trusted_share"] or span <= 0 or need <= span * cfg["timeline_word_slack"]:
        return segs, 1.0                       # a real, if tight, timeline — leave it alone
    factor = total / last
    out = [dict(s, start=round(s["start"] * factor, 2), end=round(s["end"] * factor, 2)) for s in segs]
    return out, round(factor, 3)


def stagger(starts: list[float], lengths: list[float], gap: float | None = None) -> list[float]:
    """Push each spoken clip to begin after the one before it has finished.

    Two voices at once is not narration, it is noise, and no amount of speeding a line up can save
    a window of 0.03 seconds. A line that would overlap starts late instead — late and clear beats
    on time and garbled."""
    gap = _cfg()["stagger_gap_seconds"] if gap is None else gap
    out, at = [], 0.0
    for st, ln in zip(starts, lengths):
        begin = max(st, at)
        out.append(round(begin, 2))
        at = begin + ln + gap
    return out


def picture_args(codec: str = "") -> list[str]:
    """How the picture is written into the MP4 the portal hands out.

    2026-09-18: a phone records in HEVC (H.265). Copied straight through, the narrated video made
    Windows demand a paid "HEVC Video Extensions" pack before it would play. Anything that is not a
    portable format (chip media.needs_reencode) is re-encoded to H.264, which plays everywhere for
    nothing; a recording that is already portable is still copied, which is fast and loses nothing."""
    k = engine.run("media.playback")
    if engine.run("media.needs_reencode", {"codec": codec, "portable_codecs": k["portable_codecs"],
                                           "always": k["always_reencode"]}) is not True:
        return ["-c:v", "copy"]
    args = ["-c:v", k["encoder"], "-crf", str(k["crf"]), "-preset", k["preset"], "-pix_fmt", k["pixel_format"]]
    return args + (["-movflags", "+faststart"] if k["faststart"] else [])


def cut_settings() -> dict:
    """How a trim is cut and how a join is levelled: chip media.cut."""
    return engine.run("media.cut")


def trim_command(src: Path, start: float, end: float, out: Path) -> list[str]:
    """Keep one stretch of a recording. `exact` off puts -ss BEFORE -i, which seeks to the nearest
    keyframe and copies - instant, but the cut can land a second out. `exact` on re-encodes, so the
    cut is on the frame asked for, and the result is H.264 whatever went in."""
    k = cut_settings()
    if not k["exact"]:
        return [ffmpeg(), "-y", "-ss", f"{start:.3f}", "-i", str(src), "-t", f"{end - start:.3f}",
                "-c", "copy", "-movflags", "+faststart", str(out)]
    fade = float(k["fade_seconds"])
    audio = (f"afade=t=in:st=0:d={fade},afade=t=out:st={max(0.0, end - start - fade):.3f}:d={fade}"
             if fade > 0 else "anull")
    return [ffmpeg(), "-y", "-ss", f"{start:.3f}", "-i", str(src), "-t", f"{end - start:.3f}",
            # an exact cut must re-encode whatever the source is: a copy can only cut at a keyframe
            "-af", audio, *picture_args("reencode"), *audio_args(), str(out)]


def join_command(parts: list[Path], out: Path, has_sound: list[bool] | None = None,
                 lengths: list[float] | None = None,
                 ranges: list[tuple[float, float] | None] | None = None,
                 size: tuple[int, int] | None = None) -> list[str]:
    """Several recordings, one after another. Phones, screen recorders and generated clips never agree
    on size, frame rate or sound rate, and concat demands they do - so every piece is brought to the
    numbers in chip media.cut first (or to `size`, an export shape). That is why joining always re-encodes."""
    k = cut_settings()
    w, h, fps, rate = int(k["width"]), int(k["height"]), int(k["fps"]), int(k["sample_rate"])
    if size:
        w, h = int(size[0]), int(size[1])
    sound = list(has_sound) if has_sound is not None else [True] * len(parts)
    spans = list(ranges) if ranges is not None else [None] * len(parts)
    cmd = [ffmpeg(), "-y"]
    for i, p in enumerate(parts):
        if spans[i]:                    # 2026-09-18 composer: only the stretch the owner kept of this clip
            a, b = spans[i]
            cmd += ["-ss", f"{float(a):.3f}", "-t", f"{float(b) - float(a):.3f}"]
        cmd += ["-i", str(p)]
    silent = len(parts)                 # one silent track per piece that has none, so concat can pair them
    for i, p in enumerate(parts):
        if not sound[i]:
            if spans[i]:
                secs = float(spans[i][1]) - float(spans[i][0])
            else:
                secs = (lengths or [])[i] if lengths and i < len(lengths) else duration(p)
            cmd += ["-f", "lavfi", "-t", f"{float(secs):.3f}", "-i", f"anullsrc=r={rate}:cl=stereo"]
    steps, take = [], {}
    for i in range(len(parts)):
        steps.append(f"[{i}:v]scale={w}:{h}:force_original_aspect_ratio=decrease,"
                     f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps}[v{i}]")
        if sound[i]:
            take[i] = f"{i}:a"
        else:
            take[i] = f"{silent}:a"
            silent += 1
        steps.append(f"[{take[i]}]aresample={rate},aformat=sample_fmts=fltp:channel_layouts=stereo[a{i}]")
    lanes = "".join(f"[v{i}][a{i}]" for i in range(len(parts)))
    graph = ";".join(steps) + ";" + lanes + f"concat=n={len(parts)}:v=1:a=1[vout][aout]"
    return cmd + ["-filter_complex", graph, "-map", "[vout]", "-map", "[aout]",
                  *picture_args("reencode"), *audio_args(),
                  str(out)]


def sound_mix_command(video: Path, clips: list[Path], starts: list[float], music: Path | None, out: Path,
                      total: float, film_volume: float, music_volume: float, loudness: dict | None = None,
                      film_sound: bool = True) -> list[str]:
    """Voices at their start times over the film's own sound (levelled) and, when there is one, a music
    track looped under everything (levelled). `film_sound` False = the film has no sound track (a lecture's
    looped teacher is silent): a silent track stands in, so the graph binds - 2026-09-21 the mix failed on
    "Error binding filtergraph inputs/outputs" the first time a silent film met it.
    loudness {target_lufs, true_peak_db, range_lu}: the whole mix brought to one broadcast level (EBU R128
    loudnorm) - generated clips, free voices and an uploaded track all arrive at different levels."""
    cfg = _cfg()
    cmd = [ffmpeg(), "-y", "-i", str(video)]
    parts, labels = [], []
    for i, (clip, st) in enumerate(zip(clips, starts)):
        cmd += ["-i", str(clip)]
        ms = int(st * 1000)
        parts.append(f"[{i + 1}:a]adelay={ms}|{ms}[a{i}]")
        labels.append(f"[a{i}]")
    n = len(clips) + 1
    if music is not None:
        cmd += ["-stream_loop", "-1", "-i", str(music)]
        parts.append(f"[{n}:a]volume={music_volume}[mus]")
        labels.append("[mus]")
        n += 1
    bg = "0:a"
    if not film_sound:
        cmd += ["-f", "lavfi", "-t", f"{total:.2f}", "-i", f"anullsrc=r={int(cut_settings()['sample_rate'])}:cl=stereo"]
        bg = f"{n}:a"
    parts.append(f"[{bg}]volume={film_volume}[bg]")
    # 2026-10-02 owner ("there is no voice narration"): duration=first ends the mix with its FIRST input - that was the
    # first voice line (2.2 s), so a film voiced line by line (sm Ads: a line per shot) went silent after line one.
    # The film's own track (as long as the film) leads, so the mix lasts the whole film.
    labels.insert(0, "[bg]")
    graph = ";".join(parts) + ";" + "".join(labels) + f"amix=inputs={len(labels)}:normalize=0:duration=first"
    if loudness:
        margin = float(loudness.get("limiter_margin_db") or 0)
        # 2026-09-21: loudnorm alone let an 8 s film reach +0.6 dBTP; a limiter under the target catches what it misses
        limiter = (f",alimiter=limit={10 ** ((float(loudness['true_peak_db']) - margin) / 20):.4f}:attack=5:release=50:level=disabled"
                   if margin > 0 else "")
        graph += (f"[mix];[mix]loudnorm=I={float(loudness['target_lufs'])}:TP={float(loudness['true_peak_db'])}:"
                  f"LRA={float(loudness['range_lu'])}{limiter}[aout]")
    else:
        graph += "[aout]"
    return cmd + ["-filter_complex", graph, "-map", "0:v", "-map", "[aout]", "-c:v", "copy",
                  *audio_args(), "-t", f"{total:.2f}", str(out)]


def music_bed_command(bed: dict, out: Path) -> list[str]:
    """A soft music loop the portal plays itself (chip sound.music_beds row): each chord as sine voices (+ a quiet octave),
    a gentle tremolo, faded in and out, joined in order, then softened (low-pass) and given a little echo. No licensed
    track, no download - every note is in the chip (2026-10-03 owner: soft music under the free-road ads)."""
    secs, trem, lvl = float(bed["chord_seconds"]), float(bed["tremolo_hz"]), float(bed["level"])
    rate = int(cut_settings()["sample_rate"])
    parts = []
    for i, chord in enumerate(bed["chords"]):
        voices = "+".join(f"sin(2*PI*{float(f)}*t)+0.3*sin(2*PI*{2 * float(f)}*t)" for f in chord)
        parts.append(f"aevalsrc='{lvl / max(1, len(chord)):.4f}*({voices})*(0.75+0.25*sin(2*PI*{trem}*t))':s={rate}:d={secs},"
                     f"afade=t=in:d={min(0.6, secs / 4):.2f},afade=t=out:st={max(0.0, secs - 0.8):.2f}:d=0.8[c{i}]")
    graph = (";".join(parts) + ";" + "".join(f"[c{i}]" for i in range(len(bed["chords"])))
             + f"concat=n={len(bed['chords'])}:v=0:a=1,lowpass=f={int(bed['lowpass_hz'])},aecho={bed['echo']},aformat=channel_layouts=stereo[out]")
    return [ffmpeg(), "-v", "error", "-y", "-filter_complex", graph, "-map", "[out]", *audio_args(), str(out)]


def music_under_command(video: Path, music: Path, out: Path, volume: float) -> list[str]:
    """A finished video with music looped quietly under its own sound, the picture copied untouched (2026-10-03 owner:
    soft music under Avatar Videos). The video's track LEADS amix (duration=first) - led by the music, the mix would
    end with the music's loop, never the video."""
    return [ffmpeg(), "-v", "error", "-y", "-i", str(video), "-stream_loop", "-1", "-i", str(music),
            "-filter_complex", f"[1:a]volume={float(volume):.3f}[m];[0:a][m]amix=inputs=2:duration=first:normalize=0[a]",
            "-map", "0:v", "-map", "[a]", "-c:v", "copy", *audio_args(), "-movflags", "+faststart", str(out)]


def join_plan(n: int, chunk: int) -> list[list[int]]:
    """Which pieces go into which ffmpeg call. One call takes at most `chunk` inputs: a 600-clip film in one
    command overruns the Windows command line and ffmpeg's filter graph. Pieces are joined in runs, the runs
    joined again, until one file is left. Returns the runs as index lists; a final level joins the runs."""
    n, chunk = int(n), max(2, int(chunk))
    return [list(range(a, min(a + chunk, n))) for a in range(0, n, chunk)]


def join_all(parts: list[Path], out: Path, has_sound: list[bool], lengths: list[float], chunk: int, work: Path,
             size: tuple[int, int] | None = None, run=None) -> None:
    """Every piece into one file, however many: join_command on runs of `chunk`, then on the run files, until
    one remains. Run files sit in `work` and are removed. Raises RuntimeError with ffmpeg's last line."""
    import subprocess  # noqa: PLC0415
    do = run or (lambda cmd: subprocess.run(cmd, capture_output=True, text=True))
    level = 0
    parts, sound, lens = list(parts), list(has_sound), list(lengths)
    while True:
        runs = join_plan(len(parts), chunk)
        if len(runs) == 1:
            r = do(join_command(parts, out, sound, lens, size=size))
            if getattr(r, "returncode", 0):
                raise RuntimeError((r.stderr.strip().splitlines() or ["ffmpeg"])[-1])
            return
        work.mkdir(parents=True, exist_ok=True)
        made, made_len = [], []
        for j, idx in enumerate(runs):
            piece = work / f"join-{level}-{j:03d}{out.suffix}"
            r = do(join_command([parts[i] for i in idx], piece, [sound[i] for i in idx], [lens[i] for i in idx], size=size))
            if getattr(r, "returncode", 0):
                raise RuntimeError((r.stderr.strip().splitlines() or ["ffmpeg"])[-1])
            made.append(piece)
            made_len.append(sum(lens[i] for i in idx))
        for p in parts:
            if p.parent == work and p.name.startswith("join-"):
                p.unlink(missing_ok=True)
        parts, sound, lens, level = made, [True] * len(made), made_len, level + 1


def frame_command(src: Path, out: Path, at: float) -> list[str]:
    """One picture from a clip at `at` seconds - the continuity check looks at these, never at the clip."""
    return [ffmpeg(), "-y", "-ss", f"{float(at):.2f}", "-i", str(src), "-frames:v", "1", "-update", "1", str(out)]


def still(src: Path, out: Path, at: float) -> Path | None:
    """A clip as ONE picture (a card cover): its frame at `at` seconds (half-way in a shorter clip), made once and again
    only when the clip changes. None when ffmpeg reads no frame."""
    if not (out.is_file() and out.stat().st_mtime >= src.stat().st_mtime):
        # 2026-10-01: a clip ffmpeg cannot read ran ffmpeg again for every card on every page - the failure is kept for
        # this version of the clip (its time + size), so it is tried once more only when the clip changes
        sig = (str(src), src.stat().st_mtime_ns, src.stat().st_size, str(out), float(at))
        if sig in _NO_STILL:
            return None
        try:
            at = min(float(at), duration(src) / 2)
        except RuntimeError:                              # an unreadable file is no cover, never a failed page
            _NO_STILL.add(sig)
            return None
        r = subprocess.run(frame_command(src, out, at), capture_output=True, text=True)
        if r.returncode or not out.is_file():
            _NO_STILL.add(sig)
            return None
    return out


_NO_STILL: set = set()


def small(src: Path, out: Path, px: int, quality: int) -> Path | None:
    """A picture's small copy for a grid (no longer than px on its long side), made once and again only when the picture
    changes. None when the picture cannot be read (the grid then shows the picture itself)."""
    if not (out.is_file() and out.stat().st_mtime >= src.stat().st_mtime):
        from PIL import Image, UnidentifiedImageError  # noqa: PLC0415
        try:
            im = Image.open(src).convert("RGB")
        except (UnidentifiedImageError, OSError):
            return None
        im.thumbnail((int(px), int(px)))
        out.parent.mkdir(parents=True, exist_ok=True)
        im.save(out, quality=int(quality))
    return out


def loudness_command(path: Path) -> list[str]:
    """Measure only: ffmpeg's loudnorm in print mode reads the whole track and prints EBU R128 numbers."""
    return [ffmpeg(), "-hide_banner", "-nostats", "-i", str(path), "-af", "loudnorm=print_format=json", "-f", "null", "-"]


def parse_loudness(text: str) -> dict | None:
    """{lufs, true_peak_db, range_lu} out of loudnorm's JSON block, or None when it printed none."""
    import json as _json  # noqa: PLC0415
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", text or "", re.S)
    if not m:
        return None
    try:
        d = _json.loads(m.group(0))
        return {"lufs": round(float(d["input_i"]), 1), "true_peak_db": round(float(d["input_tp"]), 1), "range_lu": round(float(d["input_lra"]), 1)}
    except (ValueError, KeyError, TypeError):
        return None


def last_frame_command(src: Path, out: Path, from_end: float) -> list[str]:
    """The last picture of a clip as one PNG - what the next generated shot starts from (film continuity)."""
    return [ffmpeg(), "-y", "-sseof", f"-{float(from_end):.2f}", "-i", str(src), "-frames:v", "1", "-update", "1", str(out)]


def fade_graph(seconds: float, k: dict) -> str:
    """Open from black and close to black without changing the film's length by a frame (chip export.finish).
    Blank when both fades are 0. `seconds` = how long the film is, so the closing fade knows where to start."""
    ins, outs, total = float(k.get("fade_in_seconds") or 0), float(k.get("fade_out_seconds") or 0), float(seconds or 0)
    parts = []
    if ins > 0:
        parts.append(f"fade=t=in:st=0:d={min(ins, total or ins):.3f}")
    if outs > 0 and total > outs:
        parts.append(f"fade=t=out:st={total - outs:.3f}:d={outs:.3f}")
    return ",".join(parts)


def fade_sound_args(seconds: float, k: dict) -> list[str]:
    """The same two fades on the sound. Empty when the chip says no, or when there is nothing to fade."""
    if not k.get("fade_sound"):
        return []
    ins, outs, total = float(k.get("fade_in_seconds") or 0), float(k.get("fade_out_seconds") or 0), float(seconds or 0)
    parts = []
    if ins > 0:
        parts.append(f"afade=t=in:st=0:d={min(ins, total or ins):.3f}")
    if outs > 0 and total > outs:
        parts.append(f"afade=t=out:st={total - outs:.3f}:d={outs:.3f}")
    return ["-af", ",".join(parts)] if parts else []


def captions_filter(name: str, k: dict) -> str:
    """Burn a captions file into the picture (chip export.finish). `name` is the ASS file's NAME only (captions_ass
    wrote it) - ffmpeg is run from the folder it sits in, because a Windows path inside a filter argument needs its
    drive colon escaped three times over and a plain name needs none. 2026-10-02 (sm Ads, Hindi): the `subtitles`
    filter shapes text the SIMPLE way - "हिस्सा" came out "हस्सिा", every Indic script broken; `ass` with
    shaping=complex sets it right, the script's own font from the folder `f` beside it."""
    return f"ass={name}:fontsdir=f:shaping=complex"


def captions_ass(srt: Path, k: dict, font: Path | None = None, family: str = "") -> str:
    """film.srt -> film.ass beside it, styled from chip export.finish, its fonts copied into the folder `f`: the MAIN
    font (export.finish caption_main_font - Latin, digits) first, then `font`, the font the text's script needs.
    2026-10-02: Noto Devanagari has no Latin letters, so "Sample Bakery" in a Hindi line fell back to a font twice the
    size; Noto Sans + Noto <script> are one size family. Returns the ASS file's name for captions_filter."""
    import shutil  # noqa: PLC0415
    main = Path(__file__).parent / "fonts" / str(k.get("caption_main_font") or "")
    if main.is_file():
        (srt.parent / "f").mkdir(exist_ok=True)
        shutil.copy2(main, srt.parent / "f" / main.name)
        from PIL import ImageFont  # noqa: PLC0415
        family = ImageFont.truetype(str(main), 12).getname()[0]
    out = srt.with_suffix(".ass")
    subprocess.run([ffmpeg(), "-v", "error", "-y", "-i", srt.name, out.name], cwd=str(srt.parent), capture_output=True, check=False)
    if not out.is_file():
        return ""
    if font and Path(font).is_file():
        (srt.parent / "f").mkdir(exist_ok=True)
        shutil.copy2(font, srt.parent / "f" / Path(font).name)
    style = (f"Style: Default,{family or 'Arial'},{int(k['caption_font_size'])},{k['caption_colour']},{k['caption_colour']},"
             f"{k['caption_outline_colour']},{k['caption_outline_colour']},0,0,0,0,100,100,0,0,{int(k.get('caption_border_style', 1))},"
             f"{int(k['caption_outline'])},{int(k['caption_shadow'])},{int(k['caption_alignment'])},10,10,{int(k['caption_margin'])},1")
    text = re.sub(r"(?m)^Style: Default,.*$", lambda _m: style, out.read_text(encoding="utf-8"))
    out.write_text(text, encoding="utf-8")
    return out.name


def look_graph(look: dict, width: int = 0, height: int = 0) -> str:
    """The finishing pass over a picture (chip film.look): a light grade, grain, darker corners and cinema bars,
    as one comma-joined ffmpeg filter chain. Blank when the look is off - the caller then leaves the picture alone.
    `width`/`height` = the frame the chain runs in; scope bars need real numbers, because after a crop the filter
    after it reads the CROPPED height as ih and would pad nothing."""
    if not look or not look.get("on"):
        return ""
    parts = [f"eq=contrast={float(look['contrast']):.3f}:saturation={float(look['saturation']):.3f}:gamma={float(look['gamma']):.3f}"]
    grain = float(look.get("grain") or 0)
    if grain > 0:
        parts.append(f"noise=alls={int(grain)}:allf={'t+u' if look.get('grain_moves', True) else 'u'}")
    if look.get("vignette"):
        parts.append(f"vignette={look.get('vignette_angle') or 'PI/5'}")
    ratio = float(look.get("scope_ratio") or 0)
    w, h = int(width), int(height)
    if ratio > 0 and w and h:
        band = min(h, int(w / ratio) // 2 * 2)                  # even height, never taller than the frame itself
        if band < h:
            parts.append(f"crop={w}:{band},pad={w}:{h}:0:{(h - band) // 2}:black")
    return ",".join(parts)


def reframe_graph(width: int, height: int, fill: str, look: dict | None = None,
                  after: list[str] | tuple[str, ...] | None = None) -> str:
    """The picture brought to a new shape (a vertical short from a wide recording, or the reverse).
    blur: the picture itself, enlarged and blurred, fills the sides behind it - the Shorts/Reels look;
    crop: the middle only, nothing added; bars: black bars. Ends in [v].
    `look`: the finishing pass (chip film.look) laid on last, so grain and bars ride over the finished frame.
    `after`: filters laid on after the look - fades, and captions, which stay crisp because nothing grades them."""
    w, h = int(width), int(height)
    tail = ",".join(x for x in (look_graph(look or {}, w, h), *(after or ())) if x)
    tail = "," + tail if tail else ""
    if fill == "crop":
        return f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1{tail}[v]"
    if fill == "bars":
        return (f"[0:v]scale={w}:{h}:force_original_aspect_ratio=decrease,"
                f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1{tail}[v]")
    return (f"[0:v]split[bg0][fg0];[bg0]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
            f"boxblur=24:2[bg];[fg0]scale={w}:{h}:force_original_aspect_ratio=decrease[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1{tail}[v]")


def short_command(src: Path, start: float, end: float, out: Path, width: int, height: int, fill: str) -> list[str]:
    """One short: a stretch of the recording, cut exactly, in the shape asked for, playable anywhere."""
    return [ffmpeg(), "-y", "-ss", f"{start:.3f}", "-i", str(src), "-t", f"{end - start:.3f}",
            "-filter_complex", reframe_graph(width, height, fill), "-map", "[v]", "-map", "0:a?",
            *picture_args("reencode"), *audio_args(), str(out)]


def mix_command(video: Path, clips: list[Path], starts: list[float], out: Path,
                total: float, keep_original: bool, codec: str = "") -> list[str]:
    """Lay each spoken clip over the video at its own start time; one MP4 out, playable by anyone."""
    cfg = _cfg()
    cmd = [ffmpeg(), "-y", "-i", str(video)]
    parts, labels = [], []
    for i, (clip, st) in enumerate(zip(clips, starts)):
        cmd += ["-i", str(clip)]
        ms = int(st * 1000)
        parts.append(f"[{i + 1}:a]adelay={ms}|{ms}[a{i}]")
        labels.append(f"[a{i}]")
    n = len(clips)
    if keep_original:
        parts.append(f"[0:a]volume={cfg['original_audio_volume']}[bg]")
        labels.append("[bg]")
        n += 1
    graph = ";".join(parts) + ";" + "".join(labels) + f"amix=inputs={n}:normalize=0:duration=longest[aout]"
    cmd += ["-filter_complex", graph, "-map", "0:v", "-map", "[aout]", *picture_args(codec), *audio_args()]
    if total:
        cmd += ["-t", f"{total:.2f}"]
    return cmd + [str(out)]


if __name__ == "__main__":  # ponytail: one runnable self-check
    # 2026-09-30 owner "Avatar Video screen taking long time to load - we can have thousands" (12 s for 7 videos):
    # a line's spoken form is worked out once per (lexicon, line), not three times per scene per card per visit
    _real, _made = _spoken, []
    globals()["_spoken"] = lambda w_, t_: (_made.append(t_), _real(w_, t_))[1]
    _SPOKEN.clear()
    assert spoken("a line") == spoken("a line") and _made == ["a line"], ("the same line was worked out again", _made)
    globals()["_spoken"] = _real
    assert _real((("tedbook", "Ted Book"),), "a tedbook") == "a Ted Book"
    _long = ("In 2053, Leonard Mead liked to walk. Every night he went out alone, in soft sneakers, so no dog would bark. "
             "Behind every curtain, the blue light of a television flickered. The houses were silent, like tombs. "
             "The great highways that once roared with cars lay empty. In ten years of walking, Leonard had never met another person.")
    _cues = caption_cues(_long, 0.5, 32.0, 90)
    assert " ".join(c[2] for c in _cues) == _long, "every word of a spoken line reaches the screen - never cut"
    assert all(len(c[2]) <= 90 for c in _cues) and len(_cues) > 1, _cues
    assert not any(c[2].split()[-1] in ("so", "lay", "the", "a") for c in _cues), ("a card never ends mid-phrase", _cues)
    assert abs(_cues[0][0] - 0.5) < 1e-9 and abs(_cues[-1][1] - 32.5) < 1e-6, "captions fill the spoken time exactly"
    import sys
    assert cost_usd("gemini-2.5-flash", 1_000_000, 0) == 0.30
    assert cost_usd("models/gemini-2.5-flash-lite", 0, 1_000_000) == 0.40
    assert cost_usd("something-new", 10, 10) is None, "unknown is unknown, never free"
    assert speed_up_percent(4.4, 4.0) == 13 and speed_up_percent(3.0, 4.0) == 0
    assert stamp(65.5, True) == "00:01:05,500" and stamp(65.5, False) == "01:05"
    segs = [{"start": 0, "end": 3}, {"start": 5, "end": 8}]
    assert speech_window(segs, 0, 10) == 4.85 and speech_window(segs, 1, 10) == 4.85
    # 2026-09-17: a draft in minutes (0 … 0.32 for a 54s video) made every window a few hundredths
    # of a second, and the voices talked over each other.
    bad = [{"start": 0, "end": 0.03, "text": "To sign in, first enter your username in the Username field"},
           {"start": 0.29, "end": 0.32, "text": "Click the Sign In button to proceed"}]
    fixed, factor = rescale_timeline(bad, 54)
    assert factor > 100 and fixed[-1]["end"] == 54, "a timeline in minutes must be stretched to the video"
    ok = [{"start": 0, "end": 5, "text": "five words go in here"}, {"start": 6, "end": 30, "text": "and more"}]
    assert rescale_timeline(ok, 32)[1] == 1.0, "a real timeline must be left alone"
    assert stagger([0, 0.03, 0.06], [2.0, 1.5, 1.0]) == [0, 2.12, 3.74], "clips must not overlap"
    assert stagger([0, 10], [2.0, 1.0]) == [0, 10], "room to spare means keep the model's timing"
    cmd = mix_command(Path("v.mp4"), [Path("a.mp3")], [1.5], Path("o.mp4"), 10, True, "h264")
    assert "[1:a]adelay=1500|1500[a0];[0:a]volume=0.15[bg];[a0][bg]amix=inputs=2:normalize=0:duration=longest[aout]" in cmd
    # 2026-10-02 ("no voice narration"): every audio writer names rate + channels, so joins by stream copy keep the voice
    assert cmd[-11:] == ["-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2", "-t", "10.00", "o.mp4"], cmd
    # 2026-09-19 a film's mix is brought to one loudness (voices, clips and music arrive at different levels)
    smix = sound_mix_command(Path("f.mp4"), [Path("n.mp3")], [0.5], None, Path("o.mp4"), 40, 0.35, 0.22,
                             {"target_lufs": -16, "true_peak_db": -1.5, "range_lu": 11})
    sgraph = smix[smix.index("-filter_complex") + 1]
    assert sgraph.endswith("amix=inputs=2:normalize=0:duration=first[mix];[mix]loudnorm=I=-16.0:TP=-1.5:LRA=11.0[aout]"), sgraph
    plain = sound_mix_command(Path("f.mp4"), [Path("n.mp3")], [0.5], None, Path("o.mp4"), 40, 0.35, 0.22)
    assert "loudnorm" not in plain[plain.index("-filter_complex") + 1], "off means off"
    # 2026-09-21 a silent film (a lecture): a silent track stands in for [0:a], the graph is otherwise the same
    mute = sound_mix_command(Path("f.mp4"), [Path("n.mp3")], [0.5], Path("m.mp3"), Path("o.mp4"), 40, 0.35, 0.22, film_sound=False)
    mgraph = mute[mute.index("-filter_complex") + 1]
    assert "anullsrc=" in " ".join(mute) and "[3:a]volume=0.35[bg]" in mgraph and "[0:a]" not in mgraph and "amix=inputs=3" in mgraph, mgraph
    # 2026-09-18: an HEVC phone recording copied through made Windows ask for a paid codec pack.
    assert picture_args("h264") == ["-c:v", "copy"], "an already portable recording is copied, not re-encoded"
    for hevc in ("hevc", "vp9", "av1", ""):
        out_args = picture_args(hevc)
        assert out_args[:2] == ["-c:v", "libx264"] and "yuv420p" in out_args, (hevc, out_args)
    assert "-movflags" in picture_args("hevc"), "the index goes to the front, so it plays while downloading"
    # 2026-09-18 trim and join (the floor SteadyMove's shorts and films stand on)
    cut = trim_command(Path("a.mp4"), 2.5, 7.0, Path("b.mp4"))
    assert cut[cut.index("-ss") + 1] == "2.500" and cut[cut.index("-t") + 1] == "4.500", cut
    assert cut.index("-ss") < cut.index("-i"), "seek before the input, or ffmpeg decodes what it throws away"
    assert "libx264" in cut, "an exact cut re-encodes, so it lands on the frame asked for"
    join = join_command([Path("a.mp4"), Path("b.mp4")], Path("c.mp4"), [True, True])
    graph = join[join.index("-filter_complex") + 1]
    assert "concat=n=2:v=1:a=1" in graph and graph.count("scale=1280:720") == 2, graph
    assert "aresample=48000" in graph, "pieces must agree on the sound rate before they can be joined"
    assert join[-1] == "c.mp4" and "libx264" in join
    # 2026-09-19 a one-hour film is 600 clips: never one ffmpeg call, runs of `chunk`, then the runs
    assert join_plan(600, 40) == [list(range(a, a + 40)) for a in range(0, 600, 40)] and join_plan(7, 40) == [list(range(7))]
    assert join_plan(41, 40)[-1] == [40] and join_plan(0, 40) == []
    calls = []

    class _Ok:
        returncode = 0
        stderr = ""
    import tempfile
    scratch = Path(tempfile.mkdtemp())                       # the runner makes its work folder; never inside the repo
    join_all([Path(f"c{i}.mp4") for i in range(90)], Path("film.mp4"), [True] * 90, [1.0] * 90, 40, scratch, run=lambda c: (calls.append(c), _Ok())[1])
    ins = [sum(1 for x in c if x == "-i") for c in calls]
    assert ins == [40, 40, 10, 3] and calls[-1][-1] == "film.mp4" and "join-0-002" in " ".join(calls[-1]), ins
    calls.clear()
    join_all([Path("a.mp4"), Path("b.mp4")], Path("film.mp4"), [True, False], [1.0, 2.0], 40, scratch, run=lambda c: (calls.append(c), _Ok())[1])
    assert len(calls) == 1 and "anullsrc" in " ".join(calls[0]), "a small film is one call, silent pieces still paired"
    # 2026-09-19 another provider's model is priced from chip providers.models; a model nobody prices is None, never $0
    assert cost_usd("gpt-4.1-nano", 1_000_000, 1_000_000) == 0.5 and cost_usd("llama3.1", 5000, 500) == 0.0 and cost_usd("no-such-model", 10, 10) is None
    # 2026-09-19 the mix is MEASURED after it is made, so the owner never has to listen to know its level
    sample = 'x\n[Parsed_loudnorm_0 @ 0x1] \n{\n\t"input_i" : "-15.87",\n\t"input_tp" : "-1.42",\n\t"input_lra" : "9.30",\n\t"target_offset" : "0.0"\n}\n'
    assert parse_loudness(sample) == {"lufs": -15.9, "true_peak_db": -1.4, "range_lu": 9.3} and parse_loudness("nothing") is None
    assert loudness_command(Path("m.mp4"))[-2:] == ["null", "-"] and "print_format=json" in " ".join(loudness_command(Path("m.mp4")))
    assert frame_command(Path("c.mp4"), Path("f.png"), 0.5)[3] == "0.50" and frame_command(Path("c.mp4"), Path("f.png"), 0.5)[-1] == "f.png"
    # a recording with no sound still joins: a silent track is made for it, or concat refuses the pair
    quiet = join_command([Path("a.mp4")], Path("c.mp4"), [False], [3.0])
    assert "anullsrc=r=48000:cl=stereo" in " ".join(quiet), quiet
    # the composer: clip 1 is a trimmed stretch, clip 2 is whole; the silent track matches the STRETCH
    mixed = join_command([Path("a.mp4"), Path("b.mp4")], Path("c.mp4"), [False, True], [60.0, 9.0],
                         [(12.0, 19.5), None])
    first = mixed.index("a.mp4")
    assert mixed[first - 5:first - 1] == ["-ss", "12.000", "-t", "7.500"], mixed[:first + 1]
    assert "-ss" not in mixed[first + 1:mixed.index("b.mp4")], "a whole clip must not be cut"
    assert "-t 7.500 -i anullsrc" in " ".join(mixed), "a silent stretch is as long as the stretch, not the file"
    # 2026-09-18 shorts: a stretch in a new shape, the sound kept when there is any
    short = short_command(Path("a.mp4"), 10, 40, Path("s.mp4"), 1080, 1920, "blur")
    assert short[short.index("-t") + 1] == "30.000" and "0:a?" in short, short
    assert "boxblur" in reframe_graph(1080, 1920, "blur") and "crop=1080:1920" in reframe_graph(1080, 1920, "crop")
    # 2026-09-20 the finishing look rides on the reframe pass and must not change the frame it was given
    plain = {"on": True, "contrast": 1.0, "saturation": 1.0, "gamma": 1.0, "grain": 0, "vignette": False, "scope_ratio": 0}
    assert look_graph({"on": False}) == "" and look_graph({}) == "", "the look off = nothing added, the picture untouched"
    assert look_graph(plain) == "eq=contrast=1.000:saturation=1.000:gamma=1.000", "no grain, no corners = a grade alone"
    rich = look_graph(plain | {"grain": 6, "vignette": True, "scope_ratio": 2.39}, 1920, 1080)
    assert "noise=alls=6:allf=t+u" in rich and "vignette=" in rich and "crop=1920:802,pad=1920:1080:0:139:black" in rich, rich
    assert look_graph(plain | {"scope_ratio": 2.39}, 1080, 1920).endswith("pad=1080:1920:0:735:black"), "bars go INSIDE the frame"
    assert look_graph(plain | {"scope_ratio": 1.0}, 1920, 1080) == look_graph(plain, 1920, 1080), "a shape wider than the frame adds no bars"
    for fill in ("crop", "bars", "blur"):
        g = reframe_graph(1920, 1080, fill, plain | {"grain": 6})
        assert g.endswith("[v]") and "noise=alls=6" in g and g.index("noise") > g.index("setsar=1"), ("the look is laid on LAST", g)
    # 2026-09-20 the editing pass: fades that never change the length, captions crisp over the grade
    fin = {"fade_in_seconds": 0.6, "fade_out_seconds": 0.8, "fade_sound": True, "caption_font_size": 22,
           "caption_colour": "&H00FFFFFF", "caption_outline_colour": "&H00000000", "caption_outline": 2,
           "caption_shadow": 0, "caption_margin": 40, "caption_alignment": 2}
    assert fade_graph(10, fin) == "fade=t=in:st=0:d=0.600,fade=t=out:st=9.200:d=0.800", fade_graph(10, fin)
    assert fade_graph(10, fin | {"fade_in_seconds": 0, "fade_out_seconds": 0}) == "", "both fades off = the picture as it was"
    assert fade_graph(0.4, fin) == "fade=t=in:st=0:d=0.400", "a film shorter than its fades never fades past its own end"
    assert fade_sound_args(10, fin | {"fade_sound": False}) == [] and fade_sound_args(10, fin)[0] == "-af"
    caps = captions_filter("film.ass", fin)
    assert caps == "ass=film.ass:fontsdir=f:shaping=complex" and "/" not in caps.split(":")[0], (
        "a captions file is named, never pathed (ffmpeg runs from its folder), and Indic text is shaped COMPLEX", caps)
    # 2026-10-02 owner ("no voice narration"): a film voiced line by line - the mix lasts the whole film, and a line
    # after the first is heard (amix duration=first once ended with the first line). Real ffmpeg, tiny files.
    import tempfile as _tm  # noqa: PLC0415
    with _tm.TemporaryDirectory() as t_:
        t_ = Path(t_)
        subprocess.run([ffmpeg(), "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=64x64:d=6", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                        "-t", "6", "-c:v", "libx264", "-c:a", "aac", "-shortest", str(t_ / "v.mp4")], check=True)
        for n_ in (1, 2):
            subprocess.run([ffmpeg(), "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=1", str(t_ / f"l{n_}.wav")], check=True)
        subprocess.run(sound_mix_command(t_ / "v.mp4", [t_ / "l1.wav", t_ / "l2.wav"], [0.0, 3.0], None, t_ / "o.mp4", 6.0, 0.15, 0.2), capture_output=True, check=True)
        r_ = subprocess.run([ffmpeg(), "-hide_banner", "-i", str(t_ / "o.mp4"), "-map", "0:a", "-af", "atrim=start=3.1:end=3.9,volumedetect", "-f", "null", "-"],
                            capture_output=True, text=True)
        lvl_ = float(re.search(r"mean_volume: (\S+) dB", r_.stderr).group(1))
        assert duration(t_ / "o.mp4") >= 5.9 and lvl_ > -30, ("the second line is heard and the mix lasts the film", duration(t_ / "o.mp4"), lvl_)
    # 2026-10-03: free soft music - a bed is as long as its chords, heard, and quieter than speech (-19 dB mean here)
    with _tm.TemporaryDirectory() as t2_:
        bed_ = {"chords": [[261.63, 329.63, 392.0], [220.0, 261.63, 329.63]], "chord_seconds": 2, "tremolo_hz": 0.25, "lowpass_hz": 1800, "level": 0.25, "echo": "0.8:0.7:120:0.25"}
        o_ = Path(t2_) / "bed.m4a"
        subprocess.run(music_bed_command(bed_, o_), capture_output=True, check=True)
        r_ = subprocess.run([ffmpeg(), "-hide_banner", "-i", str(o_), "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True)
        mean_ = float(re.search(r"mean_volume: (\S+) dB", r_.stderr).group(1))
        assert 3.8 <= duration(o_) <= 4.4 and -45 < mean_ < -18, ("a soft bed, as long as its chords", duration(o_), mean_)
        # ...laid under a finished 9 s video (silent after 1 s): the video's length kept, its silence now carries the music
        v_ = Path(t2_) / "v.mp4"
        subprocess.run([ffmpeg(), "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=64x64:d=9", "-f", "lavfi", "-i",
                        "sine=f=300:d=1,apad=whole_dur=9", "-shortest", "-c:v", "libx264", *audio_args(), str(v_)], capture_output=True, check=True)
        subprocess.run(music_under_command(v_, o_, Path(t2_) / "m.mp4", 0.5), capture_output=True, check=True)
        r_ = subprocess.run([ffmpeg(), "-hide_banner", "-i", str(Path(t2_) / "m.mp4"), "-af", "atrim=start=6:end=8,volumedetect", "-f", "null", "-"],
                            capture_output=True, text=True)
        quiet_ = float(re.search(r"mean_volume: (\S+) dB", r_.stderr).group(1))
        assert abs(duration(Path(t2_) / "m.mp4") - duration(v_)) < 0.3 and quiet_ > -60, ("music looped under the whole video", duration(Path(t2_) / "m.mp4"), quiet_)
    # 2026-10-02: a Hindi line with English words - one size family (Noto Sans main + the script's Noto beside it)
    import tempfile as _tf  # noqa: PLC0415
    with _tf.TemporaryDirectory() as tmp_:
        srt_ = Path(tmp_) / "film.srt"
        srt_.write_text("1\n00:00:00,000 --> 00:00:02,000\nSample Bakery के ताज़ा केक।\n", encoding="utf-8")
        deva_ = Path(__file__).parent / "fonts" / "NotoSansDevanagari-Regular.ttf"
        got_ = captions_ass(srt_, fin | {"caption_main_font": "NotoSans-Regular.ttf"}, deva_, "Noto Sans Devanagari")
        assert got_ == "film.ass" and "Style: Default,Noto Sans," in (Path(tmp_) / got_).read_text(encoding="utf-8"), "Latin words set in Noto Sans"
        assert {x.name for x in (Path(tmp_) / "f").iterdir()} == {"NotoSans-Regular.ttf", deva_.name}, "both fonts travel with the captions"
    both = reframe_graph(1080, 1920, "crop", plain | {"grain": 6}, [fade_graph(10, fin), caps])
    assert both.index("noise") < both.index("fade=t=in") < both.index("ass="), ("grade, then fades, then words", both)
    assert "pad=1080:1080" in reframe_graph(1080, 1080, "bars")
    assert sys.modules[__name__].VIDEO_TOKENS_PER_SECOND == 290, "old callers still read media.VIDEO_TOKENS_PER_SECOND"
    assert re.search(_cfg()["duration_pattern"], "  Duration: 00:00:54.12, start") is not None
    # 2026-09-19: a clip's length is measured ONCE (Sound's status re-ran ffmpeg per clip on every page load)
    import tempfile as _tf  # noqa: PLC0415
    _calls, _real = [], subprocess.run
    _clip = Path(_tf.mkdtemp()) / "c.mp4"
    _clip.write_bytes(b"x")
    subprocess.run = lambda *a, **k: (_calls.append(1), type("R", (), {"stderr": "Duration: 00:00:05.50,"})())[1]
    try:
        assert duration(_clip) == 5.5 and duration(_clip) == 5.5 and len(_calls) == 1, "the same clip was measured twice"
        _clip.write_bytes(b"xy")                                  # changed file = measured again
        assert duration(_clip) == 5.5 and len(_calls) == 2
        # 2026-10-03: frame_size too - the final check asked it per clip and per export, three runs per tick (15-55 s)
        _calls.clear()
        subprocess.run = lambda *a, **k: (_calls.append(1), type("R", (), {"stderr": "Stream #0:0: Video: h264, yuv420p, 720x1280,"})())[1]
        frame_size(_clip); frame_size(_clip); fps(_clip); has_audio(_clip); video_codec(_clip)
        assert len(_calls) == 1, "one file, one probe - frame, fps, sound and codec read the same answer"
    finally:
        subprocess.run = _real
    # 2026-09-30 owner "add small thumbnails": a small copy, made once, remade when the picture changes; unreadable = None
    from PIL import Image as _Im  # noqa: PLC0415
    _d = Path(_tf.mkdtemp())
    _Im.new("RGB", (1600, 900), "red").save(_d / "big.png")
    _s = small(_d / "big.png", _d / "t" / "big.jpg", 360, 82)
    assert _s and _Im.open(_s).size[0] == 360 and _Im.open(_s).size[1] in (202, 203), "no longer than px, same shape"
    _t = _s.stat().st_mtime_ns
    assert small(_d / "big.png", _d / "t" / "big.jpg", 360, 82).stat().st_mtime_ns == _t, "made once"
    (_d / "bad.png").write_bytes(b"not a picture")
    assert small(_d / "bad.png", _d / "t" / "bad.jpg", 360, 82) is None
    print("media self-check OK")
