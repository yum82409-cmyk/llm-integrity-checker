[CmdletBinding()]
param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8000,
    [switch]$NoBrowser,
    [switch]$ReinstallDependencies
)

$script = Join-Path $PSScriptRoot 'scripts\Start-Model-Integrity-Checker.ps1'
& $script -Port $Port -NoBrowser:$NoBrowser -ReinstallDependencies:$ReinstallDependencies
exit $LASTEXITCODE
