"""日志浏览与 tail。"""

import os
from typing import List

from fastapi import APIRouter, Depends, Query

from ..core.errors import AppError
from ..core.i18n import t
from ..core.security import current_user
from ..services.files import _within
from ..services.instances import get_instance, load_instance_tree, target_of

router = APIRouter(prefix="/instances/{instance_id}/logs", tags=["logs"])


def _log_dirs(inst: dict) -> List[str]:
    dirs = [os.path.join(inst["prefix"], "logs")]
    tree = load_instance_tree(inst)
    for node in (tree.root.nodes if tree.root else []):
        if node.name in ("error_log", "access_log") and node.args:
            value = node.args[0]
            if value and value != "/dev/null" and not value.startswith("syslog:"):
                path = value if os.path.isabs(value) else os.path.join(inst["prefix"], value)
                dirs.append(os.path.dirname(path))
    return list(dict.fromkeys(dirs))


@router.get("")
def index(instance_id: int, _: dict = Depends(current_user)):
    inst = get_instance(instance_id)
    files = []
    for directory in _log_dirs(inst):
        if not os.path.isdir(directory):
            continue
        try:
            names = os.listdir(directory)
        except OSError:
            continue
        for name in names:
            path = os.path.join(directory, name)
            if not os.path.isfile(path):
                continue
            try:
                stat = os.stat(path)
            except OSError:
                continue
            files.append(
                {
                    "name": name,
                    "path": path,
                    "size": stat.st_size,
                    "mtime": int(stat.st_mtime),
                }
            )
    files.sort(key=lambda f: f["mtime"], reverse=True)
    return {"files": files}


@router.get("/tail")
def tail(
    instance_id: int,
    name: str = Query(..., description="日志文件名或绝对路径"),
    lines: int = Query(200, ge=1, le=5000),
    _: dict = Depends(current_user),
):
    inst = get_instance(instance_id)
    path = name if os.path.isabs(name) else None
    if path is None:
        for directory in _log_dirs(inst):
            candidate = os.path.join(directory, name)
            if os.path.isfile(candidate):
                path = candidate
                break
    if not path:
        raise AppError(t("log.not_found"), 404)
    allowed = any(_within(os.path.realpath(path), os.path.realpath(d)) for d in _log_dirs(inst))
    if not allowed:
        raise AppError(t("log.path_forbidden"), 403)
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError as exc:
        raise AppError(t("log.read_failed", error=exc), 500)
    text = data.decode("utf-8", "replace")
    all_lines = text.splitlines()
    return {
        "path": path,
        "lines": all_lines[-lines:],
        "size": len(data),
        "truncated": len(all_lines) > lines,
    }