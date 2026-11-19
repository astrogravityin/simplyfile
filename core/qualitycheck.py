"""QA stage + QC gate travel with every portal (owner 2026-11-15; 2026-11-16: "I was under the impression that every new session
will follow" - only AstroStage and SteadyMove pointed their sessions at the rules, so a session anywhere else never saw them).

A session reads only the CLAUDE.md of the repo it works in, so each portal carries:
1. both documents (docs/dt-qa_standard-v1_0.md + docs/dt-qc_gate-v1_0.md, the DomainTemplate copies) with the same numbers
   (QC-5 checks QA-5);
2. a CLAUDE.md that points at both and says a report without the QC table is not finished;
3. the QC gate sized to the change (S/M/L section, owner 2026-11-16);
4. on the owner's computer (DomainTemplate beside the repo), the same QC rows as DomainTemplate - a drifted copy fails.
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


def _pair(root: Path) -> tuple[Path, Path]:
    for qa, qc in DOCS:
        if (root / qa).is_file() and (root / qc).is_file():
            return root / qa, root / qc
    raise AssertionError(f"QA/QC documents missing - copy {DOCS[0][0]} and {DOCS[0][1]} from DomainTemplate")


def sandbox_rule(dt: Path) -> None:
    """In DomainTemplate (REBUILD-PROMPT.md beside starter/): each document carries the sandbox line, every part of it."""
    for doc in SANDBOX_DOCS:
        line = next((x for x in (dt / doc).read_text(encoding="utf-8").splitlines() if SANDBOX in x), "")
        missing = [w for w in (SANDBOX, *SANDBOX_SAYS) if w not in line]
        assert not missing, f"{doc}: the sandbox rule lost {missing} - partner code must never run outside a sandbox"


def check(root: Path = ROOT) -> str:
    qa_p, qc_p = _pair(root)
    qa = [int(n) for n in QA_ITEM.findall(qa_p.read_text(encoding="utf-8").split("## Report format")[0])]
    qc_text = qc_p.read_text(encoding="utf-8")
    qc = [int(n) for n, _ in QC_ROW.findall(qc_text)]
    assert qc and qc == list(range(1, len(qc) + 1)), f"QC numbers not 1..n: {qc}"
    assert qa == qc, f"every QA item needs its QC check (QA {qa} vs QC {qc})"
    assert SIZED in qc_text, f"{qc_p.name} lacks '{SIZED}' (S/M/L) - copy it from DomainTemplate"
    claude = root / "CLAUDE.md"
    assert claude.is_file(), "no CLAUDE.md - a new session here would never see the QA/QC rules"
    s = claude.read_text(encoding="utf-8")
    rel = (qa_p.relative_to(root).as_posix(), qc_p.relative_to(root).as_posix())
    assert all(r in s for r in rel), f"CLAUDE.md does not point at {rel[0]} and {rel[1]}"
    assert NO_TABLE in s, f"CLAUDE.md lacks the line '{NO_TABLE}'"
    dt = root.parent / "DomainTemplate" / "docs" / "dt-qc_gate-v1_0.md"
    if dt.is_file() and root.name != "DomainTemplate":
        assert QC_ROW.findall(qc_text) == QC_ROW.findall(dt.read_text(encoding="utf-8")), \
            f"{rel[1]} drifted from DomainTemplate - copy it across"
    if (root.parent / SANDBOX_DOCS[0]).is_file():
        sandbox_rule(root.parent)
    seven = seven_questions(dt.parent.parent) if dt.is_file() else ""
    return f"  quality: QA {len(qa)} items = QC {len(qc)} checks, CLAUDE.md points at both, no-QC-table rule present{seven} OK"


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
