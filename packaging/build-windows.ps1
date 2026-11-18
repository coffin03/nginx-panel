# 一键构建 Windows 便携版：web 前端 + nginx-panel.exe
# 用法：powershell -ExecutionPolicy Bypass -File packaging\build-windows.ps1
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Write-Host "==> 仓库目录: $root"

Write-Host "==> 构建前端"
Push-Location (Join-Path $root 'web')
try {
    if (-not (Test-Path 'node_modules')) {
        npm install
    }
    npm run build
} finally {
    Pop-Location
}

Write-Host "==> 安装后端依赖"
python -m pip install --quiet -r (Join-Path $root 'server\requirements.txt')

Write-Host "==> 打包 exe"
python -m PyInstaller --noconfirm --clean `
    --distpath (Join-Path $root 'dist') `
    --workpath (Join-Path $root 'build') `
    (Join-Path $PSScriptRoot 'nginx-panel.spec')

Write-Host ""
Write-Host "构建完成: $root\dist\nginx-panel.exe"
Write-Host "双击运行后打开桌面窗口（内嵌 WebView2），关闭窗口即退出"