"""2026-10-08 owner: Fetch with OpenAI said "Asking Gemini..." and Gemini failed with "Cannot send a request, as the client has
been closed." - the busy line names the AI picked (word fetching takes {ai}), and the Gemini client is held for its call.
Run from D:/Simplyfile (re-runnable)."""
import json
from pathlib import Path


def patch(path, a, b):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    if b in s:
        return
    assert s.count(a) == 1, (path, a[:60])
    p.write_text(s.replace(a, b), encoding="utf-8")
    print("patched", path)


patch("rulewatch.py",
      '            resp = genai.Client(api_key=secret).models.generate_content(model=k["model"], contents=prompt, config=cfg)',
      '            client = genai.Client(api_key=secret)        # held: a temporary client closes before its call answers\n'
      '            resp = client.models.generate_content(model=k["model"], contents=prompt, config=cfg)')
patch("static/page-rulewatch.js",
      "      S.ai = host.querySelector('#tw-ai') ? host.querySelector('#tw-ai').value : '';\n",
      "      S.ai = host.querySelector('#tw-ai') ? host.querySelector('#tw-ai').value : '';\n"
      "      const pick = (S.ais || []).find((a) => a.provider === S.ai) || (S.ais || []).find((a) => a.ready) || {};\n"
      "      btn.dataset.work = w('fetching', { ai: pick.label || w('ai_auto') });   // the AI actually asked\n")
p = Path("chips/ui.taxwatch.json")
c = json.loads(p.read_text(encoding="utf-8"))
old, new = "Asking Gemini, official sources only...", "Asking {ai}, official sources only..."
if old in json.dumps(c, ensure_ascii=False):
    c = json.loads(json.dumps(c, ensure_ascii=False).replace(old, new))
    c["version"] += 1
    c["description_nl"] += " 2026-10-08: fetching names the AI picked ({ai})."
    p.write_text(json.dumps(c, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("ui.taxwatch")
