param(
    [string]$Message,
    # Commit only these paths instead of everything, e.g.  -Paths static/page-intake.js,chips/ui.intake.json
    [string[]]$Paths,
    [switch]$NoVerify,
    [switch]$NoPush,
    # After the push, run deploy.sh on the VPS (same as Deploy-To-VPS.cmd).
    [switch]$Deploy,
    [switch]$Yes
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RepoRoot

# `powershell -File` (the .cmd wrapper) hands a [string[]] ONE string: "-Paths a,b" arrives as "a,b". Split it.
if ($Paths) {
    $Paths = @($Paths | ForEach-Object { $_ -split ',' } | ForEach-Object { $_.Trim() } | Where-Object { $_ })
}

# Windows PowerShell 5.1 does not stop on a failing native command (git, python) - check every exit code.
function Assert-Ok([string]$What) {
    if ($LASTEXITCODE -ne 0) { throw "$What failed (exit $LASTEXITCODE). Stopped here." }
}

if (-not (Test-Path '.git')) { throw 'Run this from the SimplyFile git folder (D:\Simplyfile).' }
$Python = if (Test-Path '.venv\Scripts\python.exe') { '.venv\Scripts\python.exe' } else { 'python' }
$branch = (git branch --show-current).Trim()
if (-not $branch) { throw 'Could not detect the current git branch.' }

$status = if ($Paths) { git status --short -- $Paths } else { git status --short }
if (-not $status) {
    Write-Host 'No changes to commit.' -ForegroundColor Yellow
    if ($Deploy) { & "$RepoRoot\Deploy-To-VPS.ps1"; Assert-Ok 'Deploy' }
    exit 0
}

Write-Host ($(if ($Paths) { 'Changes in the given paths:' } else { 'Current changes (ALL of them):' })) -ForegroundColor Cyan
$status

if (-not $Message) { $Message = Read-Host 'Commit message' }
if (-not $Message.Trim()) { throw 'Commit message is required.' }

if (-not $Yes) {
    $what = if ($Paths) { 'Stage the paths listed above' } else { 'Stage ALL listed changes' }
    $confirm = Read-Host "$what, commit, and push? Type y to continue"
    if ($confirm -notin @('y', 'Y', 'yes', 'YES')) {
        Write-Host 'Cancelled. Nothing was staged.' -ForegroundColor Yellow
        exit 0
    }
}

if (-not $NoVerify) {
    # The same check deploy.sh runs on the VPS before a restart: failing here costs a minute, failing there is a
    # deploy that stops half-way.
    Write-Host 'Running selfcheck.py before commit...' -ForegroundColor Cyan
    & $Python selfcheck.py
    Assert-Ok 'selfcheck.py (nothing was staged or committed)'
}

if ($Paths) { git add -- $Paths } else { git add -A }
Assert-Ok 'git add'
# Client data never goes to GitHub, every staged .py / .json must parse, no file over GitHub's limit. Runs even
# with -NoVerify.
& $Python tools\staged_check.py
Assert-Ok 'Staged file check (files are staged but NOT committed - fix them, or unstage with: git restore --staged <file>)'
git commit -m $Message
Assert-Ok 'git commit'

if ($NoPush) {
    Write-Host 'Commit created. Push skipped (-NoPush).' -ForegroundColor Yellow
    exit 0
}
Write-Host "Pushing $branch to origin..." -ForegroundColor Cyan
git push -u origin $branch
Assert-Ok 'git push (the commit exists locally; push again once the cause is fixed)'
Write-Host "Pushed $(git rev-parse --short HEAD)." -ForegroundColor Green

if ($Deploy) {
    & "$RepoRoot\Deploy-To-VPS.ps1"
    Assert-Ok 'Deploy'
} else {
    Write-Host 'To put it live: Deploy-To-VPS.cmd' -ForegroundColor Cyan
}
