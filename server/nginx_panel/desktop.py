"""Windows 桌面窗口模式：用内嵌 WebView2 显示面板界面，不依赖系统浏览器。"""

import ctypes
import json
import os
import socket
import threading
import time
import urllib.request

import uvicorn

from .core.config import settings
from .main import app

WINDOW_TITLE = "nginx-panel"


def show_error(message: str) -> None:
    """没有控制台时用系统弹窗提示错误。"""
    try:
        ctypes.windll.user32.MessageBoxW(None, message, WINDOW_TITLE, 0x10)
    except Exception:
        print(message)


def _is_panel(port: int) -> bool:
    """判断端口上是否是已在运行的 nginx-panel。"""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1) as resp:
            return json.load(resp).get("app") == "nginx-panel"
    except Exception:
        return False


def _port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _serve(port: int) -> None:
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=port,
        log_level="info",
        access_log=False,
        log_config=None,
    )


def run_desktop() -> None:
    """打开桌面窗口；窗口关闭后退出进程。"""
    import webview  # 导入失败由调用方回退到浏览器模式

    port = settings.port
    reuse = _is_panel(port)
    if not reuse and not _port_free(port):
        port = _free_port()
    url = f"http://127.0.0.1:{port}"

    webview.create_window(
        WINDOW_TITLE,
        url,
        width=1280,
        height=820,
        min_size=(960, 600),
        text_select=True,
    )

    if not reuse:
        threading.Thread(target=_serve, args=(port,), daemon=True).start()
        deadline = time.time() + 20
        while time.time() < deadline and not _is_panel(port):
            time.sleep(0.2)

    try:
        webview.start()
    except Exception as exc:  # WebView2 运行时缺失等
        show_error(f"桌面窗口启动失败：{exc}\n将改用浏览器打开面板。")
        import webbrowser

        webbrowser.open(url)
        while True:
            time.sleep(3600)
    finally:
        os._exit(0)