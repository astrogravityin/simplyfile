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
# Say where this runs before anything else: the product, this folder, its branch and where it pushes.
Write-Host ''
Write-Host '=== SimplyFy: Commit to GitHub ===' -ForegroundColor Cyan
Write-Host "  Folder : $RepoRoot"
Write-Host "  Branch : $(try { git -C $RepoRoot branch --show-current 2>&1 } catch { })"
Write-Host "  GitHub : $(try { git -C $RepoRoot remote get-url origin 2>&1 } catch { })"
Write-Host ''

# `powershell -File` (the .cmd wrapper) hands a [string[]] ONE string: "-Paths a,b" arrives as "a,b". Split it.
if ($Paths) {
    $Paths = @($Paths | ForEach-Object { $_ -split ',' } | ForEach-Object { $_.Trim() } | Where-Object { $_ })
}

# Windows PowerShell 5.1 does not stop on a failing native command (git, python) - check every exit code.
function Assert-Ok([string]$What) {
    if ($LASTEXITCODE -ne 0) { throw "$What failed (exit $LASTEXITCODE). Stopped here." }
}

if (-not (Test-Path '.git')) { throw 'Run this from the SimplyFy git folder (D:\Simplyfile).' }
$Python = if (Test-Path '.venv\Scripts\python.exe') { '.venv\Scripts\python.exe' } else { 'python' }
$branch = (git branch --show-current).Trim()
if (-not $branch) { throw 'Could not detect the current git branch.' }

$status = if ($Paths) { git status --short -- $Paths } else { git status --short }
$commit = [bool]$status
if (-not $commit) {
    Write-Host 'No changes to commit.' -ForegroundColor Yellow
    # Commits made here that GitHub has not got (a push that failed last time) still go up.
    $ErrorActionPreference = 'Continue'
    git fetch -q origin 2>&1 | Out-Null
    $ahead = git rev-list --count '@{u}..HEAD' 2>&1
    $unpushed = ($LASTEXITCODE -ne 0) -or ([int]"$ahead" -gt 0)
    $ErrorActionPreference = 'Stop'
    if (-not $unpushed -or $NoPush) {
        if ($Deploy) { & "$RepoRoot\Deploy-To-VPS.ps1"; Assert-Ok 'Deploy' }
        exit 0
    }
    Write-Host 'Commits here are not on GitHub yet - pushing them.' -ForegroundColor Yellow
}
if ($commit) {

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
# Another run may have committed these same changes meanwhile (2026-10-06): nothing staged = nothing to commit, push anyway.
git diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
    git commit -m $Message
    Assert-Ok 'git commit'
} else { Write-Host 'Already committed - nothing new to commit.' -ForegroundColor Yellow }
}

if ($NoPush) {
    Write-Host 'Commit created. Push skipped (-NoPush).' -ForegroundColor Yellow
    exit 0
}
Write-Host "Pushing $branch to origin..." -ForegroundColor Cyan
# A repo GitHub created with its own first commit (a README) shares no history with this folder: merge it in once,
# this folder's files winning, then push. Anything else (someone else pushed) still stops below with git's message.
$ErrorActionPreference = 'Continue'
git fetch -q origin 2>&1 | Out-Null
$remote = git rev-parse -q --verify "origin/$branch" 2>&1
if ($LASTEXITCODE -eq 0) {
    git merge-base HEAD "origin/$branch" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "GitHub has its own first commit - merging it in (this folder's files win)..." -ForegroundColor Yellow
        git merge "origin/$branch" --allow-unrelated-histories -X ours --no-edit
        Assert-Ok 'Merging GitHub''s first commit'
    }
}
$ErrorActionPreference = 'Stop'
git push -u origin $branch
Assert-Ok 'git push (the commit exists locally; push again once the cause is fixed)'
Write-Host "Pushed $(git rev-parse --short HEAD)." -ForegroundColor Green

if ($Deploy) {
    & "$RepoRoot\Deploy-To-VPS.ps1"
    Assert-Ok 'Deploy'
} else {
    Write-Host 'To put it live: Deploy-To-VPS.cmd' -ForegroundColor Cyan
}
