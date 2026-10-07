param(
    # The VPS and the ssh key on THIS machine. Defaults = the Hostinger VPS; override per run or with
    # environment variables SF_VPS / SF_VPS_KEY.
    [string]$Server = $(if ($env:SF_VPS) { $env:SF_VPS } else { 'root@72.61.174.232' }),
    [string]$Key = $(if ($env:SF_VPS_KEY) { $env:SF_VPS_KEY } else { "$env:USERPROFILE\.ssh\explore_whattag" }),
    [string]$Dir = '/opt/simplyfile'
)

$ErrorActionPreference = 'Stop'

# What deploy.sh pulls is what GitHub has - warn if this machine has commits GitHub has not seen.
Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)
Write-Host ''
Write-Host '=== SimplyFy: Deploy to VPS ===' -ForegroundColor Cyan
Write-Host "  From   : $((Get-Location).Path)  (GitHub: $(try { git remote get-url origin 2>&1 } catch { }))"
Write-Host "  To     : ${Server}:$Dir  (runs $Dir/deploy.sh there)"
Write-Host ''
try { git fetch -q origin 2>&1 | Out-Null } catch { }
# Windows PowerShell 5.1 with 'Stop' turns git's stderr into a crash - ask quietly, decide here.
$ahead = $null
try { $ahead = (git rev-list --count '@{u}..HEAD' 2>&1 | Where-Object { $_ -is [string] }) } catch { }
if ($LASTEXITCODE -ne 0 -or -not $ahead) {
    throw 'This branch has never been pushed to GitHub, so the VPS has nothing to pull. Run Commit-To-GitHub.cmd first.'
}
if ([int]$ahead -gt 0) {
    Write-Host "Note: $ahead local commit(s) are not pushed - the VPS will NOT get them. Run Commit-To-GitHub.cmd first." -ForegroundColor Yellow
}

$sshArgs = @('-o', 'StrictHostKeyChecking=accept-new')
if ($Key -and (Test-Path $Key)) { $sshArgs += @('-i', $Key) }
Write-Host "Deploying SimplyFy on $Server ($Dir)..." -ForegroundColor Cyan
# exit 3 = the site was never set up on the VPS (no deploy.sh there): updates need a first setup by New site
ssh @sshArgs $Server "test -f $Dir/deploy.sh || exit 3; bash $Dir/deploy.sh"
if ($LASTEXITCODE -eq 3) {
    throw "$Dir on the VPS has no deploy.sh - the site was never set up there. First setup: VPS Console -> New site -> App (Create), then use Deploy-To-VPS.cmd for every update."
}
if ($LASTEXITCODE -ne 0) { throw "Deploy failed on the VPS (exit $LASTEXITCODE) - read the lines above." }
Write-Host 'Live: https://sf.valuestream.in' -ForegroundColor Green
