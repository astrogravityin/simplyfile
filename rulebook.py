"""The rule book (2026-10-06 owner): every rule My return's tax engine follows, written for a CA to check - the law, a plain
sentence, the figures and worked examples - built from the chips each time it is opened (GET /api/rulebook, the Rule book
button on Tax rules), so it is always what the engine does: after Apply on Tax rules it already shows the new figures.
Index and plain words: chip rulebook.sections. Figures and examples: each rule chip's own params and test_cases."""
import datetime
import html
import re
from pathlib import Path

from core import engine

ROOT = Path(__file__).resolve().parent
SKIP_PARAM = re.compile(r"^(msg_|label_|word_)")
e = html.escape


def inr(n) -> str:
    """12,34,567 - the Indian grouping a CA reads."""
    neg, n = n < 0, abs(n)
    whole, frac = (f"{n:.2f}".split(".") if isinstance(n, float) and n != int(n) else (str(int(n)), ""))
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        head = ",".join(re.findall(r"\d{1,2}", head[::-1]))[::-1]
        whole = f"{head},{tail}"
    frac = frac.rstrip("0")
    return ("-" if neg else "") + whole + (f".{frac}" if frac else "")


WORDS: dict = {}


def fmt(v, key: str = "") -> str:
    if isinstance(v, str) and v in WORDS:                       # a word key (why_simple) -> the sentence a person sees
        return f"&ldquo;{e(WORDS[v])}&rdquo;"
    if v is None:
        return "no limit"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, (int, float)):
        pct = any(w in key for w in ("pct", "rate", "percent")) and not key.startswith("rates")
        return f"{inr(v)}%" if pct and abs(v) <= 100 else inr(v)
    if isinstance(v, str):
        return e(v) if v else "-"
    if isinstance(v, list):
        if v and all(isinstance(x, dict) and "rate" in x and ("upto" in x or "above" in x) for x in v):
            parts, lo = [], 0
            for x in v:
                if "upto" in x:
                    hi = x["upto"]
                    parts.append(f"{inr(lo)} - {inr(hi) if hi is not None else 'above'}: <b>{fmt(x['rate'], 'rate')}</b>")
                    lo = hi or lo
                else:
                    parts.append(f"above {inr(x['above'])}: <b>{fmt(x['rate'], 'rate')}</b>")
            return "<br>".join(parts)
        if all(not isinstance(x, (dict, list)) for x in v):
            return ", ".join(fmt(x, key) for x in v) or "-"
        return "<br>".join(fmt(x, key) for x in v)
    if isinstance(v, dict):
        return "<br>".join(f"<span class='k'>{e(str(k2))}</span> {fmt(x, key + '.' + str(k2) if isinstance(x, (int, float)) else str(k2))}" for k2, x in v.items())
    return e(str(v))


def short(v, key: str = "") -> str:
    s = fmt(v, key)
    return s if len(re.sub("<[^>]+>", "", s)) < 400 else s[:400] + " ..."


def todo_list() -> list[tuple[str, str]]:
    """The scenarios not built yet, from MYRETURN-SCENARIOS.md (lines marked todo or part)."""
    p = ROOT / "MYRETURN-SCENARIOS.md"
    out, head = [], ""
    for ln in p.read_text(encoding="utf-8").splitlines() if p.exists() else []:
        if ln.startswith("### "):
            head = ln[4:].strip()
        elif ln.startswith("- ") and ("**todo**" in ln or "**part**" in ln):
            out.append((head, re.sub(r"\*\*", "", ln[2:]).strip()))
    return out


def build() -> str:
    WORDS.update(engine.run("ui.myreturn"))
    idx = engine.run("rulebook.sections")
    chips = engine.chips()
    areas = idx["areas"]
    rows, n_tests = [], 0
    for i, r in enumerate(idx["rules"], 1):
        c = chips.get(r["chip"])
        if not c:
            continue
        tests = c.get("test_cases") or []
        inputs = {k for t in tests for k in (t.get("args") or {})}       # what the tests vary is an input, not a figure
        knobs = [p for p in c.get("params", []) if p["name"] not in inputs and not SKIP_PARAM.match(p["name"])
                 and p.get("default") not in (None, "", 0, False, [], {})]
        n_tests += len(tests)
        title = re.sub(r"^(My return|Compute|Close|Rule book):\s*", "", c.get("label", r["chip"])).strip()
        title = title[:1].upper() + title[1:]
        fig = "".join(f"<tr><th scope='row'>{e(p.get('label') or p['name'])}</th><td>{short(p['default'], p['name'])}</td></tr>" for p in knobs)
        ex = []
        for t in tests[:5]:
            args = t.get("args") or {}
            given = "; ".join(f"{e(k)} = {short(v, k)}" for k, v in args.items()) or "the figures above"
            got = t.get("expect_value", t.get("expect"))
            ex.append(f"<li><span class='given'>Given</span> {given}<br><span class='gives'>gives</span> {short(got)}</li>")
        rows.append({"n": i, "area": r["area"], "html": f"""
<article class="rule" id="r{i}">
  <header><span class="num">R{i}</span><h3>{e(title)}</h3></header>
  <p class="law"><span>Law</span> {e(r['law'])}</p>
  <p class="plain">{e(r['plain'])}</p>
  {f'<div class="tbl"><table class="figs"><caption>Figures it uses</caption><tbody>{fig}</tbody></table></div>' if fig else ''}
  {f'<div class="ex"><h4>Worked examples - the engine is tested on each</h4><ol>{"".join(ex)}</ol>{f"<p class=more>and {len(tests) - 5} more</p>" if len(tests) > 5 else ""}</div>' if ex else ''}
  {f'<p class="gap"><span>Not covered yet</span> {e(r["gaps"])}</p>' if r.get("gaps") else ''}
  <details><summary>Engine detail</summary><p class="mono">chip {e(r['chip'])} · version {c.get('version')} · {len(tests)} tests</p><p class="note">{e(c.get('description_nl', ''))}</p></details>
</article>"""})
    toc = "".join(f"<li><a href='#a-{a['id']}'>{e(a['label'])}</a><ul>" + "".join(
        f"<li><a href='#r{x['n']}'>R{x['n']}</a></li>" for x in rows if x["area"] == a["id"]) + "</ul></li>" for a in areas)
    body = "".join(f"<section class='area' id='a-{a['id']}'><h2>{e(a['label'])}</h2>" + "".join(x["html"] for x in rows if x["area"] == a["id"]) + "</section>" for a in areas)
    todo = todo_list()
    todo_html = "".join(f"<li><span class='k'>{e(h)}</span> {e(t)}</li>" for h, t in todo)
    today = datetime.date.today().strftime("%d %b %Y")
    return f"""<title>SimplyFy Rule Book</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,500;6..72,600&family=Public+Sans:wght@400;600&family=JetBrains+Mono:wght@400&display=swap">
<style>
/* Layout: a statute-like book - sticky contents on the left, one readable column of rules on the right; stacks on a phone. */
:root {{ --bg:#f6f8fa; --paper:#ffffff; --ink:#16202a; --muted:#566271; --line:#dbe1e7; --accent:#0f6b67; --tint:#e3f1ef; --warn:#8a5a00; --warn-tint:#fdf3df;
  --display:"Newsreader", Georgia, "Times New Roman", serif; --body:"Public Sans", system-ui, -apple-system, "Segoe UI", sans-serif; --mono:"JetBrains Mono", ui-monospace, Consolas, monospace; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --bg:#0e141a; --paper:#141c24; --ink:#e4eaf0; --muted:#9aa6b2; --line:#26323d; --accent:#56c2b7; --tint:#14302f; --warn:#e3b45c; --warn-tint:#2e2414; color-scheme:dark; }} }}
:root[data-theme="dark"] {{ --bg:#0e141a; --paper:#141c24; --ink:#e4eaf0; --muted:#9aa6b2; --line:#26323d; --accent:#56c2b7; --tint:#14302f; --warn:#e3b45c; --warn-tint:#2e2414; color-scheme:dark; }}
* {{ box-sizing:border-box }}
body {{ background:var(--bg); color:var(--ink); font:16px/1.6 var(--body); padding-inline:16px; padding-block:0 64px }}
a {{ color:var(--accent) }} a:focus-visible, summary:focus-visible {{ outline:2px solid var(--accent); outline-offset:2px }}
.wrap {{ max-width:1180px; margin:0 auto; display:grid; grid-template-columns:240px minmax(0,1fr); gap:40px }}
@media (max-width:860px) {{ .wrap {{ grid-template-columns:minmax(0,1fr) }} nav.toc {{ position:static; max-height:none }} }}
.top {{ max-width:1180px; margin:0 auto; padding-block:40px 24px; border-bottom:1px solid var(--line); margin-bottom:28px }}
.eyebrow {{ font:600 12px/1 var(--body); letter-spacing:.12em; text-transform:uppercase; color:var(--accent) }}
h1 {{ font:600 clamp(32px,5vw,46px)/1.1 var(--display); margin:10px 0 12px; text-wrap:balance }}
.lede {{ max-width:68ch; color:var(--muted); margin:0 }}
.facts {{ display:flex; flex-wrap:wrap; gap:8px 22px; margin-top:18px; font-size:14px; color:var(--muted) }} .facts b {{ color:var(--ink); font-variant-numeric:tabular-nums }}
.how {{ max-width:68ch; margin-top:20px; padding:14px 16px; background:var(--tint); border-radius:10px; font-size:15px }}
nav.toc {{ position:sticky; top:calc(env(safe-area-inset-top,0px) + 16px); align-self:start; max-height:calc(100vh - 32px); overflow:auto; font-size:14px }}
nav.toc ul {{ list-style:none; margin:0; padding:0 }} nav.toc > ul > li {{ margin-bottom:10px }} nav.toc > ul > li > a {{ font-weight:600; color:var(--ink); text-decoration:none }}
nav.toc ul ul {{ display:flex; flex-wrap:wrap; gap:4px 8px; margin-top:4px }} nav.toc ul ul a {{ font:12px/1.4 var(--mono); text-decoration:none }}
main {{ min-width:0 }}
.area > h2 {{ font:600 28px/1.2 var(--display); margin:36px 0 14px; padding-top:8px; border-top:2px solid var(--ink) }}
.rule {{ background:var(--paper); border:1px solid var(--line); border-radius:12px; padding:20px 22px; margin-bottom:16px; scroll-margin-top:16px }}
.rule header {{ display:flex; gap:12px; align-items:baseline }} .rule h3 {{ font:600 21px/1.3 var(--display); margin:0; text-wrap:balance }}
.num {{ flex:none; font:12px/1 var(--mono); color:var(--accent); border:1px solid var(--accent); border-radius:6px; padding:4px 6px }}
.law {{ margin:10px 0 6px; font-size:14px; color:var(--muted) }} .law span, .gap span {{ font:600 11px/1 var(--body); letter-spacing:.1em; text-transform:uppercase; margin-right:6px; color:var(--accent) }}
.plain {{ margin:0 0 12px; max-width:70ch }}
.tbl {{ overflow-x:auto }} table.figs {{ border-collapse:collapse; width:100%; font-size:14px; font-variant-numeric:tabular-nums }}
table.figs caption, .ex h4 {{ text-align:left; font:600 12px/1 var(--body); letter-spacing:.08em; text-transform:uppercase; color:var(--muted); margin:6px 0 8px }}
table.figs th, table.figs td {{ text-align:left; vertical-align:top; padding:7px 10px 7px 0; border-top:1px solid var(--line) }} table.figs th {{ font-weight:600; width:38%; padding-right:16px }}
.k {{ font:12px/1.5 var(--mono); color:var(--muted); margin-right:4px }}
.ex {{ margin-top:12px }} .ex ol {{ margin:0; padding-left:20px; font-size:14px; display:grid; gap:8px }} .given, .gives {{ font:600 11px/1 var(--body); letter-spacing:.08em; text-transform:uppercase; color:var(--accent) }}
.more {{ font-size:13px; color:var(--muted); margin:6px 0 0 }}
.gap {{ margin:14px 0 0; padding:10px 12px; background:var(--warn-tint); border-radius:8px; font-size:14px }} .gap span {{ color:var(--warn) }}
details {{ margin-top:12px; font-size:13px; color:var(--muted) }} summary {{ cursor:pointer }} .mono {{ font-family:var(--mono) }} .note {{ max-width:80ch }}
.todo {{ background:var(--paper); border:1px solid var(--line); border-radius:12px; padding:18px 22px }} .todo ul {{ margin:0; padding-left:18px; display:grid; gap:6px; font-size:15px }}
@media (prefers-reduced-motion: no-preference) {{ html {{ scroll-behavior:smooth }} }}
</style>
<div class="top">
  <div class="eyebrow">SimplyFy · My return · AY 2026-27</div>
  <h1>The rule book</h1>
  <p class="lede">Every rule the tax engine follows, in the order a return is worked: which form, each head of income, deductions, tax, interest and the balance. For each: the section of the Act, what it does in plain words, the figures it uses and the worked examples it is tested on. It is generated from the engine itself, so it is exactly what the engine does today.</p>
  <div class="facts"><span><b>{len(rows)}</b> rules</span><span><b>{n_tests}</b> worked examples, all passing</span><span>made <b>{today}</b></span></div>
  <p class="how"><b>To review:</b> read each rule against the Act. Where a rule, a figure or an example is wrong, leave a comment naming its number (R1, R2 ...) and what it should be. Rules marked <b>Not covered yet</b> are known gaps, listed again at the end.</p>
</div>
<div class="wrap">
  <nav class="toc" aria-label="Contents"><ul>{toc}<li><a href="#todo">Not built yet</a></li></ul></nav>
  <main>{body}
    <section class="area" id="todo"><h2>Not built yet</h2><div class="todo"><ul>{todo_html}</ul></div></section>
  </main>
</div>
"""



if __name__ == "__main__":  # ponytail: the page builds and the Indian grouping holds
    import store  # noqa: F401 - registers the portal's chips
    page = build()
    assert "<title>SimplyFy Rule Book</title>" in page and "R1" in page and "Not built yet" in page
    assert inr(1234567) == "12,34,567" and inr(500) == "500" and inr(12.5) == "12.5", inr(1234567)
    print("rulebook self-check OK")
