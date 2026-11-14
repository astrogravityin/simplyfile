param(
    # Where the VPS is and which ssh key opens it. Nothing is written in this script: per run (-Server / -Key), else
    # environment SF_VPS / SF_VPS_KEY, else the untracked file deploy\vps.local (lines SF_VPS=user@host, SF_VPS_KEY=path).
    [string]$Server = '',
    [string]$Key = '',
    # Which target in chip deploy.settings (prod | staging); its folder on the VPS comes from the same chip.
    [string]$Target = '',
    # Put the release before back (deploy/deploy.sh rollback) instead of deploying.
    [switch]$Rollback,
    # Only show what is live and what a rollback would go to.
    [switch]$Status
)

$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)

# --- the server and key: -Server/-Key, env, deploy\vps.local - never a default in this file -----------------------
$local = @{}
if (Test-Path 'deploy\vps.local') {
    foreach ($line in Get-Content 'deploy\vps.local') {
        if ($line -match '^\s*([A-Z_]+)\s*=\s*(.+?)\s*$') { $local[$Matches[1]] = $Matches[2] }
    }
}
if (-not $Server) { $Server = if ($env:SF_VPS) { $env:SF_VPS } else { $local['SF_VPS'] } }
if (-not $Key) { $Key = if ($env:SF_VPS_KEY) { $env:SF_VPS_KEY } else { $local['SF_VPS_KEY'] } }
if ($Key) { $Key = $Key -replace '^~', $env:USERPROFILE -replace '%USERPROFILE%', $env:USERPROFILE }
if (-not $Server) {
    throw "No VPS named. Write deploy\vps.local (never in git) with a line SF_VPS=user@host (and SF_VPS_KEY=path to the ssh key), or set SF_VPS."
}

# --- the target's folder, from chip deploy.settings (the same reader deploy.sh uses) ----------------------------
$cfg = @{}
foreach ($line in (python deploy\settings.py . $Target)) {
    if ($line -match "^DEPLOY_([A-Z_]+)=(.*)$") { $cfg[$Matches[1]] = $Matches[2].Trim("'") }
}
if (-not $cfg['BASE']) { throw 'Could not read chip deploy.settings (python deploy\settings.py).' }
$Dir = $cfg['BASE']; $Target = $cfg['TARGET']
$site = Get-Content 'valuestream.site.json' -Raw | ConvertFrom-Json

Write-Host ''
Write-Host "=== $($site.label): Deploy to VPS ($Target) ===" -ForegroundColor Cyan
Write-Host "  From   : $((Get-Location).Path)  (GitHub: $(try { git remote get-url origin 2>&1 } catch { }))"
Write-Host "  To     : ${Server}:$Dir"
Write-Host ''

if (-not $Rollback -and -not $Status) {
    # What deploy.sh pulls is what GitHub has - warn if this machine has commits GitHub has not seen.
    try { git fetch -q origin 2>&1 | Out-Null } catch { }
    $ahead = $null
    try { $ahead = (git rev-list --count '@{u}..HEAD' 2>&1 | Where-Object { $_ -is [string] }) } catch { }
    if ($LASTEXITCODE -ne 0 -or -not $ahead) {
        throw 'This branch has never been pushed to GitHub, so the VPS has nothing to pull. Run Commit-To-GitHub.cmd first.'
    }
    if ([int]$ahead -gt 0) {
        Write-Host "Note: $ahead local commit(s) are not pushed - the VPS will NOT get them. Run Commit-To-GitHub.cmd first." -ForegroundColor Yellow
    }
    $dirty = $null
    try { $dirty = @(git status --porcelain 2>&1 | Where-Object { $_ -is [string] }) } catch { }
    if ($dirty) {
        Write-Host "Note: $($dirty.Count) uncommitted change(s) here - the VPS will NOT get them. Run Commit-To-GitHub.cmd first." -ForegroundColor Yellow
    }
}

# 2026-11-14: run from Git Bash, `ssh` was Git's own (no ssh-agent, "Permission denied"). Windows' OpenSSH goes first, so
# the key the Windows ssh-agent holds opens the VPS from any shell.
$winSsh = Join-Path $env:SystemRoot 'System32\OpenSSH'
if (Test-Path (Join-Path $winSsh 'ssh.exe')) { $env:PATH = "$winSsh;$env:PATH" }

$sshArgs = @('-o', 'StrictHostKeyChecking=accept-new')
if ($Key -and (Test-Path $Key)) { $sshArgs += @('-i', $Key) }
$verb = if ($Status) { 'status' } elseif ($Rollback) { 'rollback' } else { 'deploy' }

# Release layout (current -> releases/<commit>) runs deploy/deploy.sh; a folder not switched over yet runs the old
# deploy.sh (prod only), so this script works before AND after the owner's switch-over.
# exit 3 = the site was never set up there. Runs under nohup: a dropped connection never stops it mid-way (2026-10-20).
$remote = @"
test -d $Dir/.git || exit 3; cd $Dir
if [ -e current ] && [ -f deploy/deploy.sh ]; then run="bash deploy/deploy.sh --target $Target $verb"
elif [ "$verb" = deploy ] && [ "$Target" = prod ] && [ -f deploy.sh ]; then run="bash deploy.sh"
else echo "$Dir is not in the release layout yet - DEPLOY.md, 'Switch-over to release folders'"; exit 4; fi
nohup `$run > deploy.log 2>&1 < /dev/null & pid=`$!; tail -n +1 -f --pid=`$pid deploy.log; wait `$pid
"@ -replace "`r", ''
Write-Host "$verb on $Server ($Dir)..." -ForegroundColor Cyan
# Windows PowerShell 5.1 drops the inner double quotes of a native argument (2026-11-13: the VPS ran run=bash deploy.sh
# unquoted - 'nohup: missing operand'); the script travels as base64, which has no quote to lose, on 5.1 and 7 alike.
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($remote))
ssh @sshArgs $Server "echo $b64 | base64 -d | bash"
if ($LASTEXITCODE -eq 3) {
    throw "$Dir on the VPS is not a checkout - the site was never set up there. First setup: VPS Console -> New site, or DEPLOY.md."
}
if ($LASTEXITCODE -ne 0) { throw "$verb failed on the VPS (exit $LASTEXITCODE) - read the lines above. The live release was kept." }
if ($verb -ne 'status') { Write-Host "Live: https://$($site.host)  ($Target)" -ForegroundColor Green }
