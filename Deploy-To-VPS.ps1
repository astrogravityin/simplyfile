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
git fetch -q origin 2>$null
$ahead = (git rev-list --count '@{u}..HEAD' 2>$null)
if ($ahead -and [int]$ahead -gt 0) {
    Write-Host "Note: $ahead local commit(s) are not pushed - the VPS will NOT get them. Run Commit-To-GitHub.cmd first." -ForegroundColor Yellow
}

$sshArgs = @('-o', 'StrictHostKeyChecking=accept-new')
if ($Key -and (Test-Path $Key)) { $sshArgs += @('-i', $Key) }
Write-Host "Deploying SimplyFile on $Server ($Dir)..." -ForegroundColor Cyan
ssh @sshArgs $Server "bash $Dir/deploy.sh"
if ($LASTEXITCODE -ne 0) { throw "Deploy failed on the VPS (exit $LASTEXITCODE) - read the lines above." }
Write-Host 'Live: https://sf.valuestream.in' -ForegroundColor Green
