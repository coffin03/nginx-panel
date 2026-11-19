"""配置备份导出与导入。

导出：把主配置及其 include 链中位于 nginx 目录内的文件打包成 zip，
      并写入 manifest.json（实例信息、文件清单、目录外引用）。
导入：先校验 zip（路径穿越、体积、条目数），再交给 apply 流水线
      （快照 → 写盘 → nginx -t → reload → 失败自动回滚）。
"""

import base64
import binascii
import hashlib
import io
import json
import os
import re
import time
import zipfile
from typing import Dict, List, Tuple

from ..core.errors import AppError
from ..core.i18n import t
from ..nginx.includes import load_tree
from .apply import apply_changes, file_sha
from .instances import target_of

BACKUP_VERSION = 1
MANIFEST = "manifest.json"
FILES_DIR = "files"
MAX_FILES = 300
MAX_TOTAL = 50 * 1024 * 1024
MAX_ENTRY = 20 * 1024 * 1024
_SLUG_RE = re.compile(r"[^A-Za-z0-9._-]+")
_DRIVE_RE = re.compile(r"^[A-Za-z]:")


def _within(path: str, prefix_real: str) -> bool:
    try:
        return os.path.commonpath([os.path.realpath(path), prefix_real]) == prefix_real
    except ValueError:
        return False


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def export_backup(inst: dict) -> Tuple[bytes, str]:
    """打包当前实例的配置文件，返回 (zip 字节, 建议文件名)。"""
    prefix_real = os.path.realpath(inst["prefix"])
    tree = load_tree(target_of(inst).conf_abs, prefix_real)
    if tree.root is None:
        raise AppError(t("apply.main_conf_unreadable"), 400)

    buf = io.BytesIO()
    files: List[dict] = []
    external: List[str] = []
    seen = set()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for src in tree.all_files():
            real = os.path.realpath(src.path)
            if not _within(real, prefix_real):
                external.append(src.path)
                continue
            rel = os.path.relpath(real, prefix_real).replace(os.sep, "/")
            if rel in seen:
                continue
            seen.add(rel)
            try:
                with open(real, "rb") as fh:
                    data = fh.read()
            except OSError:
                continue
            zf.writestr(f"{FILES_DIR}/{rel}", data)
            files.append({"rel": rel, "size": len(data), "sha256": _sha(data)})

        if not files:
            raise AppError(t("backup.empty"), 400)

        manifest = {
            "app": "nginx-panel",
            "version": BACKUP_VERSION,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "instance": {
                "name": inst["name"],
                "prefix": inst["prefix"],
                "conf_path": inst["conf_path"],
            },
            "files": files,
            "external": external,
        }
        zf.writestr(MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=2))

    slug = _SLUG_RE.sub("-", inst["name"]).strip("-._") or "nginx"
    filename = f"nginx-backup-{slug}-{time.strftime('%Y%m%d-%H%M%S')}.zip"
    return buf.getvalue(), filename


def _decode(data: str) -> bytes:
    try:
        return base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError):
        raise AppError(t("backup.invalid_data"), 400)


def _safe_rel(name: str) -> str:
    """把 zip 条目名归一化成相对路径，拒绝绝对路径与 .. 穿越。"""
    rel = name.replace("\\", "/")
    if rel.startswith("/") or _DRIVE_RE.match(rel):
        raise AppError(t("backup.bad_entry", path=name), 400)
    parts = [p for p in rel.split("/") if p not in ("", ".")]
    if not parts or any(p == ".." for p in parts):
        raise AppError(t("backup.bad_entry", path=name), 400)
    return "/".join(parts)


def _parse(inst: dict, raw: bytes) -> Tuple[dict, List[dict], List[str]]:
    """校验并读取 zip，返回 (manifest, 文件条目, 警告)。条目内含 content 字节。"""
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw))
    except (zipfile.BadZipFile, OSError):
        raise AppError(t("backup.invalid_zip"), 400)

    prefix_real = os.path.realpath(inst["prefix"])
    warnings: List[str] = []
    entries: List[dict] = []
    manifest = None
    seen = set()
    total = 0

    with archive:
        infos = [i for i in archive.infolist() if not i.is_dir()]
        if len(infos) > MAX_FILES + 1:
            raise AppError(t("backup.too_many_files", limit=MAX_FILES), 400)

        for info in infos:
            name = _safe_rel(info.filename)
            if name in seen:
                raise AppError(t("backup.duplicate_entry", path=name), 400)
            seen.add(name)
            if info.flag_bits & 0x1:
                raise AppError(t("backup.encrypted"), 400)

            total += info.file_size
            if info.file_size > MAX_ENTRY or total > MAX_TOTAL:
                raise AppError(t("backup.too_large", limit=MAX_TOTAL // (1024 * 1024)), 400)

            try:
                data = archive.read(info)
            except (zipfile.BadZipFile, RuntimeError, OSError):
                raise AppError(t("backup.invalid_zip"), 400)

            if name == MANIFEST:
                try:
                    manifest = json.loads(data.decode("utf-8"))
                except (UnicodeDecodeError, ValueError) as exc:
                    raise AppError(t("backup.manifest_invalid", error=exc), 400)
                if not isinstance(manifest, dict):
                    raise AppError(t("backup.manifest_invalid", error="not an object"), 400)
                continue

            if not name.startswith(FILES_DIR + "/"):
                warnings.append(t("backup.ignored_entry", path=name))
                continue

            rel = name[len(FILES_DIR) + 1 :]
            dest = os.path.join(prefix_real, rel)
            if not _within(dest, prefix_real):
                raise AppError(t("backup.bad_entry", path=name), 400)

            exists = os.path.isfile(dest)
            sha = _sha(data)
            if not exists:
                status = "new"
            elif file_sha(dest) == sha:
                status = "unchanged"
            else:
                status = "changed"
            entries.append(
                {
                    "rel": rel,
                    "path": dest,
                    "size": len(data),
                    "sha256": sha,
                    "status": status,
                    "content": data,
                }
            )

    if manifest is None:
        raise AppError(t("backup.manifest_missing"), 400)
    return manifest, entries, warnings


def _manifest_meta(manifest: dict) -> dict:
    instance = manifest.get("instance") if isinstance(manifest.get("instance"), dict) else {}
    return {
        "created_at": manifest.get("created_at") or "",
        "name": instance.get("name") or "",
        "prefix": instance.get("prefix") or "",
        "conf_path": instance.get("conf_path") or "",
        "version": manifest.get("version") or 0,
        "external": manifest.get("external") if isinstance(manifest.get("external"), list) else [],
    }


def inspect_backup(inst: dict, data: str) -> dict:
    manifest, entries, warnings = _parse(inst, _decode(data))
    meta = _manifest_meta(manifest)

    if meta["prefix"] and os.path.abspath(meta["prefix"]) != os.path.abspath(inst["prefix"]):
        warnings.append(t("backup.prefix_mismatch", from_=meta["prefix"], to=inst["prefix"]))
    if meta["external"]:
        warnings.append(t("backup.external_hint", n=len(meta["external"])))

    summary = {"total": len(entries), "new": 0, "changed": 0, "unchanged": 0}
    for item in entries:
        summary[item["status"]] += 1

    return {
        "manifest": meta,
        "files": [
            {k: v for k, v in item.items() if k != "content"}
            for item in entries
        ],
        "summary": summary,
        "warnings": warnings,
    }


def import_backup(inst: dict, data: str, operator: str = "", reload: bool = True) -> dict:
    manifest, entries, warnings = _parse(inst, _decode(data))
    if not entries:
        raise AppError(t("backup.empty"), 400)

    meta = _manifest_meta(manifest)
    changes = [
        {
            "path": item["path"],
            "content": item["content"].decode("utf-8", "surrogateescape"),
            "base_hash": None,
        }
        for item in entries
    ]
    result = apply_changes(
        inst,
        changes,
        message=t("backup.import_message", name=meta["name"] or inst["name"]),
        operator=operator,
        reload=reload,
        trigger="import",
    )
    result["warnings"] = list(result.get("warnings") or []) + warnings
    result["files"] = [item["rel"] for item in entries]
    return result