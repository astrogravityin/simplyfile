"""Deploy you can undo (W1.4, scorecard B10) - static guard: python selfcheck_deploy.py

Fails when one of the B10 losses comes back:
  - a server address or ssh key name typed into Deploy-To-VPS.ps1 (they come from env / deploy/vps.local);
  - deploy/vps.local not ignored by git;
  - the service unit without a non-root User=, or not running <base>/current;
  - a folder, port or keep-N typed into deploy/deploy.sh (they live in chip deploy.settings);
  - the chip without a prod AND a staging target on their own folders and ports, or keeping fewer than 2 releases;
  - the image running as root or keeping data inside the image.
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
    if 'VOLUME ["/data"]' not in dock or "PORTAL_DATA=/data" not in dock:
        bad.append("Dockerfile keeps the data inside the image (needs PORTAL_DATA=/data and VOLUME /data)")
    return bad


FILES = ["Deploy-To-VPS.ps1", "deploy/deploy.sh", "deploy/portal.service.in", "Dockerfile", ".gitignore",
         "chips/deploy.settings.json"]


def main() -> None:
    files = {k: read(k) for k in FILES}
    bad = problems(files)
    assert not bad, "deploy guard:\n  " + "\n  ".join(bad)
    # the guard bites: each loss, put back once, must be caught
    bites = [
        ("Deploy-To-VPS.ps1", files["Deploy-To-VPS.ps1"] + "\n# default 'root@10.0.0.1'"),
        ("Deploy-To-VPS.ps1", files["Deploy-To-VPS.ps1"] + "\nssh @sshArgs $Server $remote\n"),
        ("deploy/portal.service.in", files["deploy/portal.service.in"].replace("User={{USER}}", "User=root")),
        ("deploy/portal.service.in", files["deploy/portal.service.in"].replace("TimeoutStopSec={{STOP}}", "")),
        ("deploy/deploy.sh", files["deploy/deploy.sh"] + "\nBASE=/opt/simplyfile\n"),
        ("Dockerfile", files["Dockerfile"].replace("USER portal", "")),
        (".gitignore", files[".gitignore"].replace("deploy/vps.local", "")),
        ("chips/deploy.settings.json", files["chips/deploy.settings.json"].replace('"port": 8837', '"port": 8830')),
        ("chips/deploy.settings.json", files["chips/deploy.settings.json"].replace(" --timeout-graceful-shutdown {graceful_stop_s}", "")),
    ]
    for name, text in bites:
        assert problems(files | {name: text}), f"deploy guard did not bite on {name}"
    print("deploy guard: release folders + rollback, non-root unit, no typed host, staging, image - ok")


if __name__ == "__main__":
    main()
