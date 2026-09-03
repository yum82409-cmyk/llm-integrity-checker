Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$LogPath = Join-Path $ScriptRoot 'deploy.log'
$Success = [System.Collections.Generic.List[string]]::new()
$Failed = [System.Collections.Generic.List[string]]::new()

function Write-Step([string]$Message) { Write-Host "`n==> $Message" -ForegroundColor Cyan }
function Invoke-Safely([string]$Name, [scriptblock]$Action) {
    try { & $Action; $Success.Add($Name); Write-Host "[OK] $Name" -ForegroundColor Green }
    catch { $Failed.Add("$Name :: $($_.Exception.Message)"); Write-Host "[FAIL] $Name :: $($_.Exception.Message)" -ForegroundColor Red }
}
function Test-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $p = [Security.Principal.WindowsPrincipal]::new($id)
    return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}
function Ensure-Admin {
    if (Test-Admin) { return }
    $args = "-NoProfile -ExecutionPolicy Bypass -File `"$($MyInvocation.MyCommand.Path)`""
    Start-Process -FilePath 'powershell.exe' -ArgumentList $args -Verb RunAs -Wait
    exit $LASTEXITCODE
}
function Read-DotEnv([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { throw "Missing .env: $Path (copy .env.example to .env)" }
    $items = @{}
    foreach ($line in Get-Content -LiteralPath $Path) {
        if ($line -match '^\s*#' -or $line -notmatch '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$') { continue }
        $key = $Matches[1]; $value = $Matches[2].Trim().Trim('"', "'")
        $items[$key] = $value
    }
    return $items
}
function Test-Winget { return [bool](Get-Command winget -ErrorAction SilentlyContinue) }
function Install-WingetPackage([string]$Id, [string]$Name) {
    if (-not (Test-Winget)) { throw 'winget is unavailable' }
    $existing = winget list --id $Id --exact --accept-source-agreements 2>$null
    if ($LASTEXITCODE -eq 0 -and $existing -match [regex]::Escape($Id)) { return }
    winget install --id $Id --exact --silent --accept-package-agreements --accept-source-agreements --disable-interactivity
    if ($LASTEXITCODE -ne 0) { throw "winget failed for $Name (exit $LASTEXITCODE)" }
}
function Install-GitHubLatest([string]$Repo, [string]$Name) {
    $release = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/releases/latest" -Headers @{ 'User-Agent'='ai-dev-bootstrap' }
    $asset = $release.assets | Where-Object { $_.name -match '\.(exe|msi)$' } | Select-Object -First 1
    if (-not $asset) { throw "No exe/msi asset found for $Repo" }
    $tmp = Join-Path $env:TEMP $asset.name
    Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $tmp -Proxy $env:HTTPS_PROXY
    if ($asset.name -match '\.msi$') { Start-Process msiexec.exe -ArgumentList "/i `"$tmp`" /qn /norestart" -Wait -NoNewWindow }
    else { Start-Process $tmp -ArgumentList '/S','/silent','/verysilent' -Wait -NoNewWindow }
    Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
}
function Copy-Tree([string]$Source, [string]$Destination) {
    if (-not (Test-Path $Source)) { return }
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    Copy-Item -Path (Join-Path $Source '*') -Destination $Destination -Recurse -Force
}
try {
    Ensure-Admin
    Start-Transcript -Path $LogPath -Append | Out-Null
    Write-Step 'Step 1: 初始化与读取 .env'
    $dotEnvPath = Join-Path $ScriptRoot '.env'
    if (-not (Test-Path -LiteralPath $dotEnvPath)) {
        Copy-Item (Join-Path $ScriptRoot '.env.example') $dotEnvPath
        Write-Host "已生成 $dotEnvPath，请填写 API Key 后重新运行。" -ForegroundColor Yellow
        Start-Process notepad.exe -ArgumentList "`"$dotEnvPath`"" -Wait
    }
    $envMap = Read-DotEnv $dotEnvPath
    foreach ($k in $envMap.Keys) { [Environment]::SetEnvironmentVariable($k, $envMap[$k], 'Process') }

    Write-Step 'Step 2: 网络基础实施'
    if (-not $env:HTTP_PROXY) { $env:HTTP_PROXY = 'http://127.0.0.1:7890' }
    if (-not $env:HTTPS_PROXY) { $env:HTTPS_PROXY = $env:HTTP_PROXY }
    $env:ALL_PROXY = $env:HTTPS_PROXY
    Invoke-Safely '网络连通性检查' { Invoke-WebRequest -Uri 'https://api.github.com' -UseBasicParsing -Proxy $env:HTTPS_PROXY | Out-Null }
    foreach ($pkg in @(@('ClashVergeRev.ClashVergeRev','Clash Verge Rev','clash-verge-rev/clash-verge-rev'), @('sshwy.cc-switch','CC Switch','sshwy/cc-switch'))) {
        Invoke-Safely $pkg[1] { try { Install-WingetPackage $pkg[0] $pkg[1] } catch { $repo = if ($pkg[2] -eq 'sshwy/cc-switch' -and $env:CCSWITCH_REPO) { $env:CCSWITCH_REPO } elseif ($pkg[2] -eq 'openclaw/openclaw' -and $env:OPENCLAW_REPO) { $env:OPENCLAW_REPO } else { $pkg[2] }; Install-GitHubLatest $repo $pkg[1] } }
    }
    Copy-Tree (Join-Path $ScriptRoot 'configs\proxy') (Join-Path $env:APPDATA 'Clash Verge Rev')

    Write-Step 'Step 3: 核心 Agent 与 IDE 部署'
    Invoke-Safely 'Python 3.12' { Install-WingetPackage 'Python.Python.3.12' 'Python 3.12' }
    Invoke-Safely 'Cursor' { Install-WingetPackage 'Anysphere.Cursor' 'Cursor' }
    Invoke-Safely 'Chatbox' { Install-WingetPackage 'Chatbox.Chatbox' 'Chatbox' }
    Invoke-Safely 'OpenClaw' { $repo = if ($env:OPENCLAW_REPO) { $env:OPENCLAW_REPO } else { 'openclaw/openclaw' }; Install-GitHubLatest $repo 'OpenClaw' }

    Write-Step 'Step 4: Machine 环境变量与配置注入'
    $cursorDir = Join-Path $env:APPDATA 'Cursor\User'; New-Item -ItemType Directory -Force -Path $cursorDir | Out-Null
    Copy-Item (Join-Path $ScriptRoot 'configs\cursor\settings.json') (Join-Path $cursorDir 'settings.json') -Force
    Copy-Tree (Join-Path $ScriptRoot 'configs\openclaw') (Join-Path $env:APPDATA 'OpenClaw')

    Write-Step 'Step 5: 部署结果'
    Write-Host "`n成功 ($($Success.Count))" -ForegroundColor Green; $Success | ForEach-Object { Write-Host "  $_" -ForegroundColor Green }
    Write-Host "失败 ($($Failed.Count))" -ForegroundColor Red; $Failed | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
    Write-Host '`n本次进程中的环境变量不会写入系统；如需长期配置，请使用系统安全的密钥管理方案。' -ForegroundColor Yellow
}
catch { Write-Host "部署中止: $($_.Exception.Message)" -ForegroundColor Red; exit 1 }
finally { try { Stop-Transcript | Out-Null } catch {} }
