[CmdletBinding()]
param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8000,
    [switch]$NoBrowser,
    [switch]$ReinstallDependencies
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
$ToolRoot = Join-Path $RepoRoot 'third_party\hlwy-ai-checker'
$StartPy = Join-Path $PSScriptRoot 'start.py'
$Requirements = Join-Path $RepoRoot 'requirements.txt'
$RuntimeRoot = Join-Path $env:LOCALAPPDATA 'AI-Dev-Bootstrap\ModelIntegrityCheckerRuntime'
$VenvRoot = Join-Path $RuntimeRoot '.venv'
$VenvPython = Join-Path $VenvRoot 'Scripts\python.exe'
$StampPath = Join-Path $RuntimeRoot 'requirements.sha256'
$Url = "http://127.0.0.1:$Port"

function Get-Health {
    try {
        return Invoke-RestMethod -Uri "$Url/health" -TimeoutSec 2
    }
    catch {
        return $null
    }
}

function Resolve-BasePython {
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py) {
        & $py.Source -3 -c "import sys; print(sys.version)" *> $null
        if ($LASTEXITCODE -eq 0) {
            return [pscustomobject]@{ File = $py.Source; Prefix = @('-3') }
        }
    }

    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($python) {
        & $python.Source -c "import sys; print(sys.version)" *> $null
        if ($LASTEXITCODE -eq 0) {
            return [pscustomobject]@{ File = $python.Source; Prefix = @() }
        }
    }

    throw 'Python 3 was not found. Install Python 3.10+ or run Install-AI-Dev.cmd first.'
}

if (-not (Test-Path -LiteralPath $StartPy)) {
    throw "Checker backend not found: $StartPy"
}

$health = Get-Health
if ($health -and $health.app -eq 'hlwy-ai-checker') {
    Write-Host "Model integrity checker is already running at $Url" -ForegroundColor Green
    if (-not $NoBrowser) { Start-Process $Url }
    return
}

$portOwner = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($portOwner) {
    throw "Port $Port is already used by process $($portOwner.OwningProcess). Try -Port 18080."
}

New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null

if (-not (Test-Path -LiteralPath $VenvPython)) {
    $base = Resolve-BasePython
    Write-Host 'Creating isolated Python environment...' -ForegroundColor Cyan
    & $base.File @($base.Prefix) -m venv $VenvRoot
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $VenvPython)) {
        throw 'Failed to create the Python virtual environment.'
    }
}

$requirementsHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $Requirements).Hash
$installedHash = if (Test-Path -LiteralPath $StampPath) { (Get-Content -LiteralPath $StampPath -Raw).Trim() } else { '' }
if ($ReinstallDependencies -or $installedHash -ne $requirementsHash) {
    Write-Host 'Installing checker dependency (requests)...' -ForegroundColor Cyan
    & $VenvPython -m pip install --disable-pip-version-check --quiet -r $Requirements
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
    Set-Content -LiteralPath $StampPath -Value $requirementsHash -Encoding ascii
}

$env:HLWY_PORT = [string]$Port
$env:HLWY_NO_BROWSER = if ($NoBrowser) { '1' } else { '0' }

Write-Host "Starting model integrity checker at $Url" -ForegroundColor Green
& $VenvPython $StartPy
exit $LASTEXITCODE
