"""实例管理。"""

import os
from typing import List, Optional

from ..core.db import db
from ..core.errors import AppError
from ..nginx.process.base import InstanceTarget


def _row_to_dict(row) -> dict:
    data = dict(row)
    data["enabled"] = bool(data["enabled"])
    return data


def list_instances() -> List[dict]:
    with db() as conn:
        rows = conn.execute("SELECT * FROM instance ORDER BY id").fetchall()
    return [_row_to_dict(r) for r in rows]


def get_instance(instance_id: int) -> dict:
    with db() as conn:
        row = conn.execute("SELECT * FROM instance WHERE id=?", (instance_id,)).fetchone()
    if not row:
        raise AppError("实例不存在", 404)
    return _row_to_dict(row)


def create_instance(data: dict) -> dict:
    name = (data.get("name") or "").strip()
    binary = (data.get("binary") or "").strip()
    prefix = (data.get("prefix") or "").strip()
    conf_path = (data.get("conf_path") or "conf/nginx.conf").strip()
    run_mode = (data.get("run_mode") or "local").strip()
    unit = (data.get("systemd_unit") or "").strip()

    if not name:
        raise AppError("实例名称不能为空")
    if not binary:
        raise AppError("nginx 可执行文件路径不能为空")
    if not prefix:
        raise AppError("nginx 目录（prefix）不能为空")
    if run_mode not in ("local", "systemd"):
        raise AppError("运行模式只能是 local 或 systemd")

    prefix = os.path.abspath(prefix)
    if not os.path.isdir(prefix):
        raise AppError(f"nginx 目录不存在: {prefix}")
    if not os.path.isabs(conf_path):
        conf_abs = os.path.join(prefix, conf_path)
    else:
        conf_abs = conf_path
    if not os.path.isfile(conf_abs):
        raise AppError(f"主配置文件不存在: {conf_abs}")

    with db() as conn:
        cur = conn.execute(
            """INSERT INTO instance(name,binary,prefix,conf_path,run_mode,systemd_unit,enabled,created_at)
               VALUES (?,?,?,?,?,?,1,datetime('now','localtime'))""",
            (name, binary, prefix, conf_path, run_mode, unit),
        )
        new_id = int(cur.lastrowid)
    return get_instance(new_id)


def update_instance(instance_id: int, data: dict) -> dict:
    current = get_instance(instance_id)
    name = (data.get("name", current["name"]) or "").strip()
    binary = (data.get("binary", current["binary"]) or "").strip()
    prefix = os.path.abspath(data.get("prefix", current["prefix"]) or current["prefix"])
    conf_path = (data.get("conf_path", current["conf_path"]) or "conf/nginx.conf").strip()
    run_mode = data.get("run_mode", current["run_mode"])
    unit = (data.get("systemd_unit", current["systemd_unit"]) or "").strip()

    if not name or not binary:
        raise AppError("名称与可执行文件路径不能为空")
    if not os.path.isdir(prefix):
        raise AppError(f"nginx 目录不存在: {prefix}")
    if run_mode not in ("local", "systemd"):
        raise AppError("运行模式只能是 local 或 systemd")

    with db() as conn:
        conn.execute(
            """UPDATE instance SET name=?,binary=?,prefix=?,conf_path=?,run_mode=?,systemd_unit=? WHERE id=?""",
            (name, binary, prefix, conf_path, run_mode, unit, instance_id),
        )
    return get_instance(instance_id)


def delete_instance(instance_id: int) -> None:
    get_instance(instance_id)
    with db() as conn:
        conn.execute("DELETE FROM instance WHERE id=?", (instance_id,))


def target_of(inst: dict) -> InstanceTarget:
    return InstanceTarget(
        id=int(inst["id"]),
        name=inst["name"],
        binary=inst["binary"],
        prefix=inst["prefix"],
        conf_path=inst["conf_path"],
        run_mode=inst["run_mode"],
        systemd_unit=inst["systemd_unit"],
    )


def load_instance_tree(inst: dict):
    from ..nginx.includes import load_tree

    target = target_of(inst)
    return load_tree(target.conf_abs, target.prefix)