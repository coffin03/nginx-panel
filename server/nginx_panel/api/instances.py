"""实例 CRUD、状态与运维操作。"""

import os
import shutil
import string
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..core.db import db
from ..core.errors import AppError
from ..core.i18n import t
from ..core.security import current_user
from ..nginx.process import build_adapter
from ..services.instances import (
    create_instance,
    delete_instance,
    get_instance,
    list_instances,
    load_instance_tree,
    target_of,
    update_instance,
)

router = APIRouter(prefix="/instances", tags=["instances"])


class InstancePayload(BaseModel):
    name: str
    binary: str
    prefix: str
    conf_path: str = "conf/nginx.conf"
    run_mode: str = "local"
    systemd_unit: str = ""


class InstanceUpdate(BaseModel):
    name: Optional[str] = None
    binary: Optional[str] = None
    prefix: Optional[str] = None
    conf_path: Optional[str] = None
    run_mode: Optional[str] = None
    systemd_unit: Optional[str] = None


def _status(inst: dict) -> dict:
    tree = load_instance_tree(inst)
    adapter = build_adapter(target_of(inst), tree)
    st = adapter.status()
    return {"running": st.running, "pid": st.pid, "detail": st.detail, "conf_errors": tree.errors}


@router.get("")
def index(_: dict = Depends(current_user)):
    items = list_instances()
    for inst in items:
        try:
            inst["status"] = _status(inst)
        except Exception as exc:  # 单个实例异常不影响列表
            inst["status"] = {"running": False, "pid": None, "detail": t("instance.status_check_failed", error=exc)}
    return items


@router.post("")
def create(payload: InstancePayload, _: dict = Depends(current_user)):
    inst = create_instance(payload.model_dump())
    from ..core.watcher import start_instance

    start_instance(int(inst["id"]))
    return inst


@router.get("/{instance_id}")
def detail(instance_id: int, _: dict = Depends(current_user)):
    inst = get_instance(instance_id)
    inst["status"] = _status(inst)
    return inst


@router.put("/{instance_id}")
def update(instance_id: int, payload: InstanceUpdate, _: dict = Depends(current_user)):
    data = {k: v for k, v in payload.model_dump().items() if v is not None}
    inst = update_instance(instance_id, data)
    from ..core.watcher import restart_instance

    restart_instance(instance_id)
    return inst


@router.delete("/{instance_id}")
def remove(instance_id: int, _: dict = Depends(current_user)):
    from ..core.watcher import stop_instance

    stop_instance(instance_id)
    delete_instance(instance_id)
    return {"ok": True}


@router.get("/{instance_id}/status")
def status(instance_id: int, _: dict = Depends(current_user)):
    return _status(get_instance(instance_id))


@router.post("/{instance_id}/ops/{action}")
def operate(instance_id: int, action: str, _: dict = Depends(current_user)):
    if action not in ("start", "stop", "reload", "restart", "test"):
        raise AppError(t("instance.unsupported_action"), 400)
    inst = get_instance(instance_id)
    tree = load_instance_tree(inst)
    adapter = build_adapter(target_of(inst), tree)
    result = getattr(adapter, action)()
    with db() as conn:
        conn.execute(
            """INSERT INTO operation(instance_id,created_at,action,ok,detail)
               VALUES (?,datetime('now','localtime'),?,?,?)""",
            (instance_id, action, int(result.ok), (result.output or "")[:4000]),
        )
    return {
        "ok": result.ok,
        "output": result.output,
        "exit_code": result.exit_code,
        "pid": result.pid,
        "running": result.running,
        "status": _status(inst),
    }


@router.get("/{instance_id}/operations")
def operations(instance_id: int, _: dict = Depends(current_user)):
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM operation WHERE instance_id=? ORDER BY id DESC LIMIT 50", (instance_id,)
        ).fetchall()
    return [dict(r) for r in rows]


@router.get("/{instance_id}/recent-applies")
def recent_applies(instance_id: int, _: dict = Depends(current_user)):
    from ..services.snapshots import recent_applies as _recent

    get_instance(instance_id)
    return _recent(instance_id)


@router.get("/system/detect")
def detect(_: dict = Depends(current_user)):
    """扫描常见位置，帮助快速添加实例。"""
    paths = []
    for name in ("nginx", "nginx.exe"):
        found = shutil.which(name)
        if found:
            paths.append(found)
    if os.name == "nt":
        for drive in _windows_drives():
            for sub in ("nginx", "tools\\nginx", "Program Files\\nginx", "Program Files (x86)\\nginx"):
                paths.append(os.path.join(drive, sub, "nginx.exe"))
            paths.extend(_scan_nginx_exes(drive, 3))
    else:
        paths.extend(["/usr/sbin/nginx", "/usr/local/nginx/sbin/nginx", "/opt/nginx/sbin/nginx"])

    candidates = []
    seen = set()
    for path in paths:
        if not path or not os.path.isfile(path):
            continue
        real = os.path.realpath(path)
        if real.lower() in seen:
            continue
        seen.add(real.lower())
        base = os.path.dirname(real)
        if os.path.basename(base) in ("sbin", "bin"):
            prefix = os.path.dirname(base)
        else:
            prefix = base
        conf = os.path.join(prefix, "conf", "nginx.conf")
        candidates.append(
            {
                "binary": real,
                "prefix": prefix,
                "conf_path": "conf/nginx.conf" if os.path.isfile(conf) else "nginx.conf",
                "conf_exists": os.path.isfile(conf) or os.path.isfile(os.path.join(prefix, "nginx.conf")),
            }
        )
    return {"candidates": candidates}


# 可能存放软件的一级目录名，扫描时只对这类目录继续下钻
_DETECT_CONTAINERS = (
    "tools",
    "software",
    "soft",
    "dev",
    "develop",
    "apps",
    "app",
    "server",
    "program files",
    "program files (x86)",
    "env",
    "web",
    "www",
    "opt",
    "work",
    "green",
)


def _windows_drives() -> list[str]:
    drives = []
    if os.name != "nt":
        return drives
    for letter in string.ascii_uppercase:
        root = f"{letter}:\\"
        if os.path.exists(root):
            drives.append(root)
    return drives


def _scan_nginx_exes(root: str, depth: int) -> list[str]:
    """在 root 下找 nginx.exe，只下钻疑似 nginx/软件目录，避免全盘遍历。"""
    found: list[str] = []
    try:
        entries = list(os.scandir(root))
    except OSError:
        return found
    for entry in entries:
        try:
            if not entry.is_dir():
                continue
        except OSError:
            continue
        exe = os.path.join(entry.path, "nginx.exe")
        if os.path.isfile(exe):
            found.append(exe)
        name = entry.name.lower()
        if depth > 1 and (
            name.startswith("nginx") or name.startswith("openresty") or name in _DETECT_CONTAINERS
        ):
            found.extend(_scan_nginx_exes(entry.path, depth - 1))
    return found