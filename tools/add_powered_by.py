"""2026-10-07 owner: every portal (each a valuestream.in sub-domain) says "Powered by ValueStream", with ValueStream's logo -
on the sign-in page and at the foot of the menu. Boilerplate: core/static/shell.js + portal.css + chip ui.shell, logo
core/static/valuestream.png. Re-runnable. Run from the portal's root (D:/Simplyfile)."""
import json
from pathlib import Path
_ROOT = Path(__file__).resolve().parents[1]   # repo root: paths never depend on the folder it is started from

W = {"powered_by": "Powered by", "powered_name": "ValueStream", "powered_href": "https://valuestream.in"}
p = (_ROOT / "core/chips/ui.shell.json")
c = json.loads(p.read_text(encoding="utf-8"))
have = {x["name"] for x in c["params"]}
for k, v in W.items():
    if k in have:
        continue
    c["params"].append({"name": k, "type": "text", "default": v, "label": k.replace("_", " ")})
    c["expr"]["fields"][k] = "$" + k
    for t in c["test_cases"]:
        if isinstance(t.get("expect_value"), dict) and not t.get("args"):
            t["expect_value"][k] = v
c["version"] += 1
c["description_nl"] += " 2026-10-07: powered_by / powered_name / powered_href - 'Powered by ValueStream' on the sign-in page and the menu foot."
p.write_text(json.dumps(c, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

s_path = (_ROOT / "core/static/shell.js")
s = s_path.read_text(encoding="utf-8")
FN = """
/** "Powered by ValueStream" with its logo (2026-10-07 owner: every portal is a valuestream.in sub-domain). Words: ui.shell. */
function poweredBy() {
  if (!w('powered_name') || w('powered_name') === 'powered_name') return '';
  return `<a class="powered" href="${esc(w('powered_href'))}" target="_blank" rel="noopener">
    <img src="${BASE}/core-static/valuestream.png" width="18" height="18" alt="">${esc(w('powered_by'))} <b>${esc(w('powered_name'))}</b></a>`;
}

function authShell(inner) {"""
if "function poweredBy()" not in s:
    s = s.replace("\nfunction authShell(inner) {", FN, 1)
    a = "      ${config.pitch()}\n    </aside>"
    assert s.count(a) == 1
    s = s.replace(a, "      ${config.pitch()}\n      ${poweredBy()}\n    </aside>")
    a = "      ${slot(config.navFoot) ? `<div class=\"foot\">${slot(config.navFoot)}</div>` : ''}\n    </nav>"
    assert s.count(a) == 1
    s = s.replace(a, "      ${slot(config.navFoot) ? `<div class=\"foot\">${slot(config.navFoot)}</div>` : ''}\n      ${poweredBy()}\n    </nav>")
    s_path.write_text(s, encoding="utf-8")

css = (_ROOT / "core/static/portal.css")
t = css.read_text(encoding="utf-8")
if ".powered{" not in t:
    t += ("\n/* Powered by ValueStream (2026-10-07): sign-in pitch and menu foot */\n"
          ".powered{display:inline-flex;align-items:center;gap:7px;font-size:12px;color:var(--muted);text-decoration:none;margin-top:auto;padding-top:14px}\n"
          ".powered img{display:block;border-radius:4px}\n.powered b{color:var(--ink-2);font-weight:650}\n.powered:hover b{color:var(--brand)}\n"
          ".side .powered{padding:10px 12px 4px;margin-top:0}\n.collapsed .side .powered{justify-content:center;font-size:0;gap:0}\n"
          ".collapsed .side .powered b{display:none}\n")
    css.write_text(t, encoding="utf-8")
print("powered by: ok")
