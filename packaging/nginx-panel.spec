# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：生成单文件 nginx-panel.exe（前端 dist 内嵌）。"""

import os

from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))

datas = [
    # 前端构建产物 -> 运行时 _MEIPASS/web
    (os.path.join(ROOT, "web", "dist"), "web"),
]

hiddenimports = (
    collect_submodules("uvicorn")
    + collect_submodules("watchfiles")
    + collect_submodules("webview")
    + collect_submodules("pythonnet")
    + collect_submodules("clr_loader")
    + ["bcrypt", "sqlite3", "clr", "tkinter", "tkinter.filedialog", "tkinter.ttk"]
)

a = Analysis(
    [os.path.join(ROOT, "server", "run.py")],
    pathex=[os.path.join(ROOT, "server")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["matplotlib", "pytest", "IPython"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="nginx-panel",
    icon=os.path.join(ROOT, "packaging", "nginx-panel.ico"),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)