[CmdletBinding()]
param(
    [switch]$Reinstall
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
$RuntimeRoot = Join-Path $env:LOCALAPPDATA 'AI-Dev-Bootstrap\ModelIntegrityCheckerRuntime'
$VenvRoot = Join-Path $RuntimeRoot '.venv'
$VenvPython = Join-Path $VenvRoot 'Scripts\python.exe'
$Requirements = Join-Path $RepoRoot 'requirements-capability.txt'

if (-not (Test-Path -LiteralPath $VenvPython)) {
    throw "Checker runtime not found: $VenvPython. Start the main checker once first."
}

if ($Reinstall) {
    & $VenvPython -m pip uninstall -y evalscope *> $null
}

Write-Host 'Installing optional EvalScope capability engine...' -ForegroundColor Cyan
& $VenvPython -m pip install --disable-pip-version-check -r $Requirements
if ($LASTEXITCODE -ne 0) { throw 'EvalScope installation failed.' }

Write-Host 'EvalScope capability engine is ready.' -ForegroundColor Green
