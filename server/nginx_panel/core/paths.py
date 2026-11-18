"""运行目录解析：源码运行与 PyInstaller 打包后的可执行文件都要能找到数据目录。"""

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def base_dir() -> Path:
    """exe 所在目录（打包后）或仓库根目录（开发时）。"""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


def web_dist_dir() -> Path:
    """前端构建产物目录。"""
    if is_frozen():
        # 打包时把 dist 放到 exe 同级 web/ 或 _MEIPASS/web
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            p = Path(meipass) / "web"
            if p.exists():
                return p
        return Path(sys.executable).resolve().parent / "web"
    return base_dir() / "web" / "dist"


def data_dir() -> Path:
    """数据目录：优先 exe 同级 data/，不可写时退回用户目录。"""
    if is_frozen():
        preferred = base_dir() / "data"
        if _writable(preferred):
            return preferred
        appdata = os.environ.get("APPDATA") or str(Path.home())
        fallback = Path(appdata) / "nginx-panel"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback
    path = base_dir() / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def resource_path(relative: str) -> Path:
    """读取随包资源（如内置前端静态文件）。"""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass) / relative
    return base_dir() / relative