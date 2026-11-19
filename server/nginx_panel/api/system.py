"""本机文件/目录选择：弹出系统原生对话框，返回选中路径。"""

import os
import threading

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..core.errors import AppError
from ..core.i18n import t
from ..core.security import current_user

router = APIRouter(prefix="/system", tags=["system"])

_dialog_lock = threading.Lock()


class PickRequest(BaseModel):
    mode: str = "file"
    title: str = ""
    initial: str = ""


def _open_dialog(mode: str, title: str, initial: str) -> str:
    """在独立线程里创建 Tk 对话框，避免阻塞事件循环线程。"""
    result = {"path": "", "error": ""}
    # 线程不继承 contextvar，文案在进入线程前按当前语言取好
    text_missing = t("system.dialog_missing")
    text_failed = t("system.dialog_failed")
    text_title = title or t("system.dialog_title_folder" if mode == "folder" else "system.dialog_title_file")
    text_all_files = t("system.dialog_all_files")
    start_dir = initial or ""
    if start_dir and not os.path.isdir(start_dir):
        start_dir = os.path.dirname(start_dir)
    if start_dir and not os.path.isdir(start_dir):
        start_dir = ""

    def worker():
        try:
            import tkinter as tk
            from tkinter import filedialog
        except Exception:  # noqa: BLE001 - 缺少 tk 时给出可读提示
            result["error"] = text_missing
            return
        root = None
        try:
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            root.update()
            if mode == "folder":
                picked = filedialog.askdirectory(
                    parent=root,
                    title=text_title,
                    initialdir=start_dir or None,
                    mustexist=True,
                )
            else:
                picked = filedialog.askopenfilename(
                    parent=root,
                    title=text_title,
                    initialdir=start_dir or None,
                    filetypes=[(text_all_files, "*.*")],
                )
            result["path"] = picked or ""
        except Exception:  # noqa: BLE001 - 无图形界面时提示手动填写
            result["error"] = text_failed
        finally:
            if root is not None:
                root.destroy()

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join()
    if result["error"]:
        raise AppError(result["error"], 500)
    return result["path"]


@router.post("/pick")
def pick_path(payload: PickRequest, _: dict = Depends(current_user)):
    if payload.mode not in ("file", "folder"):
        raise AppError(t("system.invalid_pick_mode"))
    with _dialog_lock:
        path = _open_dialog(payload.mode, payload.title, payload.initial)
    if not path:
        return {"path": ""}
    return {"path": os.path.normpath(path)}