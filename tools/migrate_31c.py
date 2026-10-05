"""One-off (2026-10-05): repayments of loans moved from SF Ref "3CD 31(b)" to "3CD 31(c)", as Form 3CD numbers them
(31(b) is now a specified sum taken). Rewrites the saved refs of every statement in a data folder.

    python tools/migrate_31c.py <data dir>            # dry run: how many refs would change
    python tools/migrate_31c.py <data dir> --apply    # rewrite them (back the folder up first)

Only saved tags (sf_files/<client>/<ay>/<file>.tags.json - the store adds its own .json) change. A ref written in a client's own sheet (its SF Ref column)
is the client's file - re-download it from Intake & map after this, or the old ref comes back with next year's upload."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

OLD = re.compile(r"\b3CD\s+31\(b\)", re.I)


def run(data: Path, apply: bool) -> tuple[int, int]:
    files = refs = 0
    for p in sorted((data / "sf_files").glob("*/*/*.tags.json*")):
        tags = json.loads(p.read_text(encoding="utf-8") or "{}")
        new = {k: OLD.sub("3CD 31(c)", v) if isinstance(v, str) else v for k, v in tags.items()}
        n = sum(1 for k in tags if new[k] != tags[k])
        if n:
            files, refs = files + 1, refs + n
            if apply:
                p.write_text(json.dumps(new, ensure_ascii=False, indent=1), encoding="utf-8")
    return files, refs


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    if sys.argv[1] == "--selftest":  # ponytail: one statement, two refs, one rewritten
        import tempfile
        with tempfile.TemporaryDirectory() as t:
            p = Path(t, "sf_files", "c1", "2026-27", "f1.tags.json.json")
            p.parent.mkdir(parents=True)
            p.write_text(json.dumps({"S!3": "3CD 31(a) #1; 3CD 31(b) #1", "S!4": "ITR3 HP"}))
            assert run(Path(t), False) == (1, 1) and "31(b)" in p.read_text()
            assert run(Path(t), True) == (1, 1) and json.loads(p.read_text())["S!3"] == "3CD 31(a) #1; 3CD 31(c) #1"
            assert run(Path(t), True) == (0, 0), "a second run changes nothing"
        print("migrate_31c self-check OK")
        sys.exit(0)
    f, r = run(Path(sys.argv[1]), "--apply" in sys.argv)
    print(f"{r} refs in {f} statements {'rewritten' if '--apply' in sys.argv else 'would be rewritten (dry run)'}")
