# 生成可分发的 Windows 便携版压缩包（本地复现 CI 产物）
# 用法：powershell -ExecutionPolicy Bypass -File packaging\make-release.ps1 [-SkipBuild]
param(
    [switch]$SkipBuild
)
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$init = Join-Path $root 'server\nginx_panel\__init__.py'
$version = (Select-String -Path $init -Pattern '__version__\s*=\s*"(.+?)"').Matches[0].Groups[1].Value
Write-Host "==> 版本: $version"

if (-not $SkipBuild) {
    & (Join-Path $PSScriptRoot 'build-windows.ps1')
} elseif (-not (Test-Path (Join-Path $root 'dist\nginx-panel.exe'))) {
    throw 'dist\nginx-panel.exe 不存在，不能使用 -SkipBuild'
}

$stage = Join-Path $root 'build\release'
Remove-Item -Recurse -Force $stage -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $stage | Out-Null
Copy-Item (Join-Path $root 'dist\nginx-panel.exe') $stage
Copy-Item (Join-Path $root 'LICENSE') (Join-Path $stage 'LICENSE.txt')

$zip = Join-Path $root "dist\nginx-panel-$version-win64.zip"
Remove-Item -Force $zip -ErrorAction SilentlyContinue
Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $zip

$hash = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLower()
$sums = Join-Path $root 'dist\SHA256SUMS.txt'
"$hash  nginx-panel-$version-win64.zip" | Set-Content $sums -Encoding ascii

Write-Host ""
Write-Host "发布包: $zip"
Write-Host "校验值: $sums"
Get-Content $sums