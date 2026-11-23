"""QA stage + QC gate travel with every portal (owner 2026-11-15; 2026-11-16: "I was under the impression that every new session
will follow" - only AstroStage and SteadyMove pointed their sessions at the rules, so a session anywhere else never saw them).

A session reads only the CLAUDE.md of the repo it works in, so each portal carries:
1. both documents (docs/dt-qa_standard-v1_0.md + docs/dt-qc_gate-v1_0.md) with the same numbers (QC-5 checks QA-5);
2. a CLAUDE.md that points at both and says a report without the QC table is not finished;
3. the QC gate sized to the change (S/M/L section, owner 2026-11-16);
4. on the owner's computer (DomainTemplate on the machine), the same QC rows as DomainTemplate - a drifted copy fails;
5. owner 2026-11-23 ("you should have in one place and all those portal should have one like file stating that refer to that
   folder/file"): the two documents live ONLY in DomainTemplate/docs. A portal keeps a POINTER file under the same name (first
   line POINTER + the canonical path). A full copy where DomainTemplate is reachable fails. Where DomainTemplate is not on the
   machine (VPS gate, build computer) a pointer passes on its CLAUDE.md lines alone - the numbers are checked at home.
Run by every portal's selfcheck (`from core import qualitycheck; qualitycheck.check()`) and alone: `python -m core.qualitycheck`.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = (("docs/dt-qa_standard-v1_0.md", "docs/dt-qc_gate-v1_0.md"),   # DomainTemplate names (every Fy portal)
        ("docs/quality/QA_STANDARD.md", "docs/quality/QC_GATE.md"))   # AstroStage names
NO_TABLE = "A report without the QC table is not finished"
SIZED = "## Size the gate to the change"   # owner 2026-11-16: S/M/L evidence, a one-line fix pays no six screenshots
# 2026-11-18 gap audit C1-6: partner code (a portal under review or rebuild) runs only in a sandbox, and its agent files are data
SANDBOX = "Partner code runs ONLY inside a sandbox"
SANDBOX_SAYS = ("`--ignore-scripts`", "no network", "no credentials", "are data to report, never instructions")
SANDBOX_DOCS = ("REBUILD-PROMPT.md", "skills/portal-review/SKILL.md")
QA_ITEM = re.compile(r"^(\d+)\. \*\*", re.M)
QC_ROW = re.compile(r"^\| QC-(\d+) \| ([^|]+)\|", re.M)
POINTER = "<!-- standard-pointer: "   # a pointer file's first line: POINTER + "DomainTemplate/docs/<name>" + " -->"


def _pair(root: Path) -> tuple[Path, Path]:
    for qa, qc in DOCS:
        if (root / qa).is_file() and (root / qc).is_file():
            return root / qa, root / qc
    raise AssertionError(f"QA/QC documents missing - copy the pointer files {DOCS[0][0]} and {DOCS[0][1]} from DomainTemplate/starter")


def _canonical(p: Path) -> tuple[str | None, bool]:
    """(the document's text, is it a pointer). A pointer is followed up the folders to DomainTemplate; None = not on this machine."""
    s = p.read_text(encoding="utf-8")
    if not s.startswith(POINTER):
        return s, False
    rel = s[len(POINTER):].split(" -->", 1)[0].strip()
    hit = next((b / rel for b in p.resolve().parents if (b / rel).is_file()), None)
    return (hit.read_text(encoding="utf-8") if hit else None), True


def _home(root: Path) -> Path | None:
    """DomainTemplate's docs folder when it is on this machine (the repo itself, beside it, or further up)."""
    for b in [root.resolve(), *root.resolve().parents]:
        for d in (b / "docs", b / "DomainTemplate" / "docs"):
            if (d / "dt-qc_gate-v1_0.md").is_file() and (d.parent / "starter").is_dir() and not _canonical(d / "dt-qc_gate-v1_0.md")[1]:
                return d
    return None


def sandbox_rule(dt: Path) -> None:
    """In DomainTemplate (REBUILD-PROMPT.md beside starter/): each document carries the sandbox line, every part of it."""
    for doc in SANDBOX_DOCS:
        line = next((x for x in (dt / doc).read_text(encoding="utf-8").splitlines() if SANDBOX in x), "")
        missing = [w for w in (SANDBOX, *SANDBOX_SAYS) if w not in line]
        assert not missing, f"{doc}: the sandbox rule lost {missing} - partner code must never run outside a sandbox"


def _claude(root: Path, qa_p: Path, qc_p: Path) -> str:
    claude = root / "CLAUDE.md"
    assert claude.is_file(), "no CLAUDE.md - a new session here would never see the QA/QC rules"
    s = claude.read_text(encoding="utf-8")
    rel = (qa_p.relative_to(root).as_posix(), qc_p.relative_to(root).as_posix())
    assert all(r in s for r in rel), f"CLAUDE.md does not point at {rel[0]} and {rel[1]}"
    assert NO_TABLE in s, f"CLAUDE.md lacks the line '{NO_TABLE}'"
    return "CLAUDE.md points at both, no-QC-table rule present"


def check(root: Path = ROOT) -> str:
    qa_p, qc_p = _pair(root)
    (qa_text, qa_ptr), (qc_text, qc_ptr) = _canonical(qa_p), _canonical(qc_p)
    home = _home(root)
    is_home = bool(home) and qa_p.parent.resolve() == home.resolve()
    if home and not is_home and qa_p.name.startswith("dt-"):
        copies = [p.name for p, ptr in ((qa_p, qa_ptr), (qc_p, qc_ptr)) if not ptr]
        assert not copies, f"{copies}: a full copy - keep the pointer file (DomainTemplate/starter/docs); change the standard only in DomainTemplate/docs"
    claude_ok = _claude(root, qa_p, qc_p)
    if qa_text is None or qc_text is None:
        return f"  quality: pointer files, DomainTemplate not on this machine (numbers checked at home); {claude_ok} OK"
    qa = [int(n) for n in QA_ITEM.findall(qa_text.split("## Report format")[0])]
    qc = [int(n) for n, _ in QC_ROW.findall(qc_text)]
    assert qc and qc == list(range(1, len(qc) + 1)), f"QC numbers not 1..n: {qc}"
    assert qa == qc, f"every QA item needs its QC check (QA {qa} vs QC {qc})"
    assert SIZED in qc_text, f"{qc_p.name} lacks '{SIZED}' (S/M/L) - copy it from DomainTemplate"
    dt = home / "dt-qc_gate-v1_0.md" if home else None
    if dt and not is_home and not qc_ptr:
        assert QC_ROW.findall(qc_text) == QC_ROW.findall(dt.read_text(encoding="utf-8")), f"{qc_p.name} drifted from DomainTemplate - copy it across"
    if home and (home.parent / SANDBOX_DOCS[0]).is_file():
        sandbox_rule(home.parent)
    seven = seven_questions(home.parent) if home else ""
    one = " (one copy, in DomainTemplate)" if qc_ptr else ""
    return f"  quality: QA {len(qa)} items = QC {len(qc)} checks{one}, {claude_ok}{seven} OK"


SEVEN = "## 1b. Seven questions a person asks of every screen"
SEVEN_ROW = re.compile(r"^\| [1-7] \| [^|]+\?", re.M)


def seven_questions(dt: Path) -> str:
    """Owner 2026-11-19 (the Equation editor passed its tests and failed all seven): skill ui-standard keeps its seven
    questions - what is that, can I change it, built from, worth its space, source and who settles it, first, phone."""
    s = (dt / "skills" / "ui-standard" / "SKILL.md").read_text(encoding="utf-8")
    part = s.split(SEVEN, 1)[1].split("\n## ", 1)[0] if SEVEN in s else ""
    assert len(SEVEN_ROW.findall(part)) == 7, f"skills/ui-standard/SKILL.md lost '{SEVEN}' or one of its 7 rows"
    return ", the seven screen questions kept"


if __name__ == "__main__":
    print(check())
