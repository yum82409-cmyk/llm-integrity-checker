[CmdletBinding()]
param([string]$OutputPath)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
if (-not $OutputPath) { $OutputPath = Join-Path $root 'AI-Dev-Bootstrap.zip' }
$OutputPath = [System.IO.Path]::GetFullPath($OutputPath)
$tempRoot = [System.IO.Path]::GetFullPath($env:TEMP).TrimEnd('\') + '\'
$staging = [System.IO.Path]::GetFullPath((Join-Path $env:TEMP ("ai-dev-bootstrap-" + [guid]::NewGuid().ToString('N'))))
if (-not $staging.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Unsafe staging path: $staging"
}
try {
    New-Item -ItemType Directory -Path $staging -Force | Out-Null
    Get-ChildItem -LiteralPath $root -Force | Where-Object {
        $_.Name -notin @('.env','deploy.log','.git') -and
        [System.IO.Path]::GetFullPath($_.FullName) -ne $OutputPath
    } | Copy-Item -Destination $staging -Recurse -Force
    if (Test-Path $OutputPath) { Remove-Item -LiteralPath $OutputPath -Force }
    Compress-Archive -Path (Join-Path $staging '*') -DestinationPath $OutputPath -CompressionLevel Optimal
    Write-Host "Installer package: $OutputPath" -ForegroundColor Green
}
finally { if (Test-Path $staging) { Remove-Item -LiteralPath $staging -Recurse -Force } }
