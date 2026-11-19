"""Deploy you can undo (W1.4, scorecard B10) - static guard: python selfcheck_deploy.py

Fails when one of the B10 losses comes back:
  - a server address or ssh key name typed into Deploy-To-VPS.ps1 (they come from env / deploy/vps.local);
  - deploy/vps.local not ignored by git;
  - the service unit without a non-root User=, or not running <base>/current;
  - a folder, port or keep-N typed into deploy/deploy.sh (they live in chip deploy.settings);
  - a lock installed without its hashes;
  - the chip without a prod AND a staging target on their own folders and ports, prod not the site file's, or fewer than
    2 releases kept;
  - the image running as root or keeping data inside the image;
  - (supply chain, 2026-11-18 gap audit C1-18) a workflow action not pinned by a full commit SHA, a workflow without a
    top-level `permissions:`, `pull_request_target`, npm ci/install without --ignore-scripts, a lock line without its
    hash, a server/CI install from an unhashed file, the deploy's packages and self-check run as root.
The live proof (good -> broken -> still serving -> rollback) is bash deploy/harness/dryrun.sh.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read(rel: str) -> str:
    p = HERE / rel
    return p.read_text(encoding="utf-8") if p.is_file() else ""


def problems(f: dict[str, str]) -> list[str]:
    bad = []
    ps1, sh, unit, dock, ign = f["Deploy-To-VPS.ps1"], f["deploy/deploy.sh"], f["deploy/portal.service.in"], f["Dockerfile"], f[".gitignore"]
    if re.search(r"\b\d{1,3}(\.\d{1,3}){3}\b", ps1):
        bad.append("Deploy-To-VPS.ps1 has a server address typed in (use SF_VPS / deploy/vps.local)")
    if re.search(r"\.ssh[\\/]+\w", ps1):
        bad.append("Deploy-To-VPS.ps1 names an ssh key file (use SF_VPS_KEY / deploy/vps.local)")
    if re.search(r"^\s*ssh\b[^\n]*\$remote", ps1, re.M):   # 2026-11-13: Windows PowerShell 5.1 drops an argument's inner quotes
        bad.append("Deploy-To-VPS.ps1 hands the remote script to ssh as an argument - PowerShell 5.1 loses its quotes; send it as base64")
    if "System32\\OpenSSH" not in ps1:   # 2026-11-14: from Git Bash, Git's own ssh has no agent
        bad.append("Deploy-To-VPS.ps1 does not put Windows' OpenSSH first - from Git Bash its ssh has no agent (Permission denied)")
    if not re.search(r"^deploy/vps\.local$", ign, re.M):
        bad.append(".gitignore does not keep deploy/vps.local out of git")
    user = re.search(r"^User=(\S+)$", unit, re.M)
    if not user or user.group(1) == "root":
        bad.append("deploy/portal.service.in has no non-root User=")
    if "WorkingDirectory={{BASE}}/current" not in unit:
        bad.append("deploy/portal.service.in does not run <base>/current (the release the switch points at)")
    if "TimeoutStopSec={{STOP}}" not in unit:
        bad.append("deploy/portal.service.in has no TimeoutStopSec - systemd waits 90 s on a stuck stop (a 90 s 502 per deploy)")
    if "--timeout-graceful-shutdown" not in f["chips/deploy.settings.json"]:
        bad.append("chip deploy.settings start_cmd has no --timeout-graceful-shutdown - uvicorn waits on the open push stream")
    code = "\n".join(line for line in sh.splitlines() if not line.lstrip().startswith("#"))
    if re.search(r"/opt/|\b8[0-9]{3}\b|keep_releases\s*=\s*\d", code):
        bad.append("deploy/deploy.sh has a folder or port typed in (chip deploy.settings holds them)")
    if 'set_link "$rel/$k" "$BASE/kept/$k"' not in code or "tmp/tour_video" not in f["chips/deploy.settings.json"]:
        bad.append("deploy/deploy.sh does not keep tmp/tour_video across releases (chip deploy.settings kept) - every deploy loses the recorded Tour Videos")
    if "tourvideo.ensure_recorder()" not in code or "PLAYWRIGHT_BROWSERS_PATH" not in code:
        bad.append("deploy/deploy.sh does not install the Tour Video recorder (and its browser in <base>/.playwright) per release")
    if "Environment=PLAYWRIGHT_BROWSERS_PATH={{BASE}}/.playwright" not in unit:
        bad.append("deploy/portal.service.in does not point the service at <base>/.playwright - a non-root service cannot reach root's browser")
    for step in ("selfcheck failed", "probe", "moving back", "rollback"):
        if step not in sh:
            bad.append(f"deploy/deploy.sh lost its '{step}' step")
    try:
        chip = {p["name"]: p.get("default") for p in json.loads(f["chips/deploy.settings.json"])["params"]}
        t = chip["targets"]
        if not {"prod", "staging"} <= set(t):
            bad.append("chip deploy.settings needs a prod and a staging target")
        else:
            if t["prod"]["base"] == t["staging"]["base"]:
                bad.append("chip deploy.settings: staging shares prod's folder")
            ports = [t["prod"]["port"], t["prod"]["probe_port"], t["staging"]["port"], t["staging"]["probe_port"]]
            if len(set(ports)) != 4:
                bad.append("chip deploy.settings: prod, staging and probe ports must all differ")
            if any(v.get("user") in (None, "", "root") for v in t.values()):
                bad.append("chip deploy.settings: every target needs a non-root service user")
        if int(chip["keep_releases"]) < 2:
            bad.append("chip deploy.settings keeps fewer than 2 releases - nothing to roll back to")
    except (KeyError, ValueError, TypeError) as e:
        bad.append(f"chip deploy.settings is missing or unreadable ({e})")
    if not re.search(r"^USER (?!root)\S+", dock, re.M):
        bad.append("Dockerfile runs as root")
    if not re.search(r'^VOLUME \["/data"', dock, re.M) or "PORTAL_DATA=/data" not in dock:
        bad.append("Dockerfile keeps the data inside the image (needs PORTAL_DATA=/data and VOLUME /data)")
    # 2026-11-18 gap audit C1-14: a staging deploy is refused when it points at prod (deploy/separation.py, chip deploy.separation)
    if 'deploy/separation.py" "$BASE" "$TARGET"' not in sh or "def problems" not in f["deploy/separation.py"]:
        bad.append("deploy/deploy.sh does not ask deploy/separation.py before a deploy - staging may point at prod's data or keys")
    if "staging" not in (json.loads(f["chips/deploy.separation.json"] or "{}").get("test_cases") or [{}])[0].get("expect_value", {}).get("guarded", []):
        bad.append("chip deploy.separation does not guard staging")
    return bad


FILES = ["Deploy-To-VPS.ps1", "deploy/deploy.sh", "deploy/portal.service.in", "Dockerfile", ".gitignore",
         "chips/deploy.settings.json", "deploy/separation.py", "chips/deploy.separation.json"]


SUPPLY_GLOBS = ("*.sh", "deploy/*.sh", "deploy/*/*.sh", "*.ps1", "*.cmd", "Dockerfile", ".github/workflows/*.yml",
                ".github/workflows/*.yaml", "DEPLOY.md", "chips/*.json", "core/chips/*.json", "requirements*.lock", "*/*/requirements*.lock")


def supply_files(root: Path = HERE) -> dict[str, str]:
    """Every script, workflow, chip and lock the supply-chain guard reads (tracked files; every file when not in git)."""
    import subprocess  # noqa: PLC0415
    from fnmatch import fnmatchcase  # noqa: PLC0415
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True, check=True).stdout.decode("utf-8", "replace")
        names = [f for f in out.split("\0") if f]
    except (OSError, subprocess.CalledProcessError):
        names = [f.relative_to(root).as_posix() for g in SUPPLY_GLOBS for f in root.glob(g)]
    keep = sorted({n for n in names if any(fnmatchcase(n, g) and n.count("/") == g.count("/") for g in SUPPLY_GLOBS)})
    return {n: (root / n).read_text(encoding="utf-8", errors="replace") for n in keep if (root / n).is_file()}


def supply(f: dict[str, str]) -> list[str]:
    """Supply chain + CI (gap audit C1-18, classes J/K/M): what could slip in through a package, an action or the CI token."""
    bad = []
    try:   # chip deps.lock local_only: the developer start scripts (requirements.txt on a Windows/Mac machine)
        local = next(p["default"] for p in json.loads(f.get("core/chips/deps.lock.json", "{}"))["params"] if p["name"] == "local_only")
    except (KeyError, StopIteration, ValueError):
        local = []
    for name, text in f.items():
        yml = name.endswith((".yml", ".yaml"))
        code = "\n".join(ln.split(" #")[0] if yml else ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))
        if name.startswith(".github/workflows/"):
            for ref in re.findall(r"uses:\s*['\"]?([^\s'\"]+)", code):
                if not ref.startswith("./") and not re.search(r"@[0-9a-f]{40}$", ref):
                    bad.append(f"{name}: action {ref} is not pinned by a full commit SHA (keep the tag as a comment after it)")
            if not re.search(r"^permissions:", text, re.M):
                bad.append(f"{name}: no top-level permissions: (contents: read) - the token gets the default write scope")
            if "pull_request_target" in code:
                bad.append(f"{name}: pull_request_target runs a stranger's pull request with this repo's token and secrets")
        for m in re.finditer(r"\bnpm\s+(?:ci|install|i)\b[^\n;&|]*", code):
            if "--ignore-scripts" not in m.group(0):
                bad.append(f"{name}: '{m.group(0).strip()[:60]}' without --ignore-scripts - a package's install script would run")
        if re.search(r"requirements[^/]*\.lock$", name):
            joined = re.sub(r"\\\r?\n", " ", text).splitlines()
            unhashed = [ln for ln in joined if re.match(r"\s*[A-Za-z0-9]", ln) and "--hash=sha256:" not in ln]
            if unhashed:
                bad.append(f"{name}: {len(unhashed)} line(s) without a hash, e.g. {unhashed[0][:50]}")
        for m in [] if name in local else re.finditer(r"pip3? install\b[^\n;&|\"]*?-r\s+(\S+)", code):
            if not m.group(1).rstrip("\"',").endswith(".lock") or "--require-hashes" not in m.group(0):
                bad.append(f"{name}: '{m.group(0)[:70]}' installs from an unhashed file (only a hashed .lock with --require-hashes)")
    try:
        reqs = next(p["default"] for p in json.loads(f.get("chips/deploy.settings.json", "{}"))["params"] if p["name"] == "requirements")
        if any(not str(r).endswith(".lock") for r in reqs):
            bad.append("chip deploy.settings requirements names an unhashed file - a release installs only hashed locks")
    except (KeyError, StopIteration, ValueError):
        bad.append("chip deploy.settings has no requirements list")
    legacy, rel = f.get("deploy.sh", ""), f.get("deploy/deploy.sh", "")
    for step in ("as_app .venv/bin/pip install", "as_app .venv/bin/python selfcheck.py"):
        if legacy and step not in legacy:
            bad.append(f"deploy.sh runs '{step.split(' ', 1)[1]}' as root - run it as the unit's User= (as_app)")
    if "DEPLOY.md" in f and not re.search(r"^User=(?!root\b)\S+", f["DEPLOY.md"], re.M):
        bad.append("DEPLOY.md: the first install's service unit has no non-root User= - the site would run as root")
    if rel and 'exec runuser -u "$DEPLOY_USER"' not in rel:
        bad.append("deploy/deploy.sh no longer hands itself to the service user - the release is built and checked as root")
    return bad


def supply_bites(sf: dict[str, str]) -> None:
    """Each supply-chain loss, put back once, must be caught."""
    wf = ".github/workflows/check.yml"
    sha = re.search(r"@[0-9a-f]{40}", sf[wf])
    bites = [
        (wf, sf[wf].replace(sha.group(0), "@v4", 1) if sha else sf[wf] + "\n      - uses: actions/checkout@v4\n"),
        (wf, re.sub(r"^permissions:", "perms:", sf[wf], flags=re.M)),
        (wf, sf[wf].replace("  pull_request:\n", "  pull_request_target:\n", 1)),
        ("deploy.sh", sf["deploy.sh"] + "\nnpm ci\n"),
        ("Dockerfile", sf["Dockerfile"] + "\nRUN npm install --omit=dev\n"),
        ("requirements.lock", sf["requirements.lock"] + "evil==1.0\n"),
        ("Dockerfile", sf["Dockerfile"].replace("--require-hashes --no-deps -r requirements.lock", "-r requirements.txt")),
        ("chips/tourvideo.settings.json", sf["chips/tourvideo.settings.json"].replace("tour_video/requirements.lock", "tour_video/requirements.txt")),
        ("chips/deploy.settings.json", sf["chips/deploy.settings.json"].replace('"requirements.lock"\n', '"requirements.lock", "requirements.txt"\n', 1)),
        ("deploy.sh", sf["deploy.sh"].replace("as_app .venv/bin/pip install", ".venv/bin/pip install")),
        ("deploy.sh", sf["deploy.sh"].replace("as_app .venv/bin/python selfcheck.py", ".venv/bin/python selfcheck.py")),
        ("deploy/deploy.sh", sf["deploy/deploy.sh"].replace('exec runuser -u "$DEPLOY_USER"', "exec bash -c")),
        ("DEPLOY.md", re.sub(r"^User=.*$", "", sf["DEPLOY.md"], flags=re.M)),
        ("DEPLOY.md", sf["DEPLOY.md"].replace("--require-hashes --no-deps -r requirements.lock", "-r requirements.txt")),
        ("deploy/root_steps.sh", sf.get("deploy/root_steps.sh", "") + "\npip install -r requirements.txt\n"),
    ]
    for name, text in [(n_, t_) for n_, t_ in bites if n_ in sf]:   # a file this portal does not have is not bitten
        assert supply(sf | {name: text}), f"supply-chain guard did not bite on {name}: {text[-80:]!r}"




def main() -> None:
    files = {k: read(k) for k in FILES}
    bad = problems(files)
    assert not bad, "deploy guard:\n  " + "\n  ".join(bad)
    # the guard bites: each loss, put back once, must be caught
    bites = [
        ("Deploy-To-VPS.ps1", files["Deploy-To-VPS.ps1"] + "\n# default 'root@10.0.0.1'"),
        ("Deploy-To-VPS.ps1", files["Deploy-To-VPS.ps1"] + "\nssh @sshArgs $Server $remote\n"),
        ("Deploy-To-VPS.ps1", files["Deploy-To-VPS.ps1"].replace("System32\\OpenSSH", "")),
        ("deploy/portal.service.in", files["deploy/portal.service.in"].replace("User={{USER}}", "User=root")),
        ("deploy/portal.service.in", files["deploy/portal.service.in"].replace("TimeoutStopSec={{STOP}}", "")),
        ("deploy/deploy.sh", files["deploy/deploy.sh"] + "\nBASE=/opt/simplyfile\n"),
        ("deploy/deploy.sh", files["deploy/deploy.sh"].replace('set_link "$rel/$k" "$BASE/kept/$k"', "")),
        ("chips/deploy.settings.json", files["chips/deploy.settings.json"].replace("tmp/tour_video", "tmp/other")),
        ("deploy/deploy.sh", files["deploy/deploy.sh"].replace("tourvideo.ensure_recorder()", "")),
        ("deploy/deploy.sh", files["deploy/deploy.sh"].replace('PLAYWRIGHT_BROWSERS_PATH="$BASE/.playwright" ', "")),
        ("deploy/portal.service.in", files["deploy/portal.service.in"].replace("Environment=PLAYWRIGHT_BROWSERS_PATH={{BASE}}/.playwright", "")),
        ("Dockerfile", files["Dockerfile"].replace("USER portal", "")),
        (".gitignore", files[".gitignore"].replace("deploy/vps.local", "")),
        ("chips/deploy.settings.json", files["chips/deploy.settings.json"].replace('"port": 8837', '"port": 8830')),
        ("chips/deploy.settings.json", files["chips/deploy.settings.json"].replace(" --timeout-graceful-shutdown {graceful_stop_s}", "")),
        ("deploy/deploy.sh", files["deploy/deploy.sh"].replace('deploy/separation.py" "$BASE" "$TARGET"', "")),
    ]
    for name, text in bites:
        assert problems(files | {name: text}), f"deploy guard did not bite on {name}"
    import subprocess  # noqa: PLC0415
    import sys  # noqa: PLC0415
    r = subprocess.run([sys.executable, str(HERE / "deploy" / "separation.py"), "--selftest"], capture_output=True, text=True)
    assert r.returncode == 0, "deploy/separation.py self-test failed:\n" + (r.stdout + r.stderr)[-1500:]
    print(r.stdout.rstrip())
    print("deploy guard: release folders + rollback, non-root unit, no typed host, staging, image - ok")
    sf = supply_files()
    sbad = supply(sf)
    assert not sbad, "supply-chain guard:\n  " + "\n  ".join(sbad)
    supply_bites(sf)
    print(f"  supply: {len(sf)} scripts, workflows, chips and locks - actions by SHA, read-only token, hashed installs, not root OK")


if __name__ == "__main__":
    main()
