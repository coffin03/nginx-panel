"""文件树、文件读取与 diff。"""

import difflib
import os
from typing import List, Optional

from ..core.errors import AppError
from ..core.i18n import t
from ..nginx.includes import ConfTree, load_tree
from ..nginx.parser import parse_source
from .apply import file_sha
from .instances import target_of

SKIP_DIRS = {
    ".git",
    "node_modules",
    "logs",
    "temp",
    "client_body_temp",
    "proxy_temp",
    "fastcgi_temp",
    "uwsgi_temp",
    "scgi_temp",
    "data",
    "__pycache__",
}
TEXT_EXTS = {"", ".conf", ".types", ".map", ".lua", ".inc", ".txt", ".json", ".bak", ".template", ".tmpl", ".default", ".nginx"}


def is_text_ext(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in TEXT_EXTS


def _is_binary(path: str) -> bool:
    try:
        with open(path, "rb") as fh:
            chunk = fh.read(8192)
        return b"\0" in chunk
    except OSError:
        return True


def list_files(inst: dict, tree: Optional[ConfTree] = None) -> dict:
    prefix = inst["prefix"]
    target = target_of(inst)
    tree = tree or load_tree(target.conf_abs, prefix)
    main_path = os.path.realpath(target.conf_abs)
    included = {os.path.realpath(s.path) for s in tree.all_files()}

    entries: List[dict] = []
    truncated = False
    for root, dirs, files in os.walk(prefix):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        if len(entries) > 3000:
            truncated = True
            break
        rel_root = os.path.relpath(root, prefix)
        for name in files:
            path = os.path.join(root, name)
            try:
                stat = os.stat(path)
            except OSError:
                continue
            real = os.path.realpath(path)
            rel = name if rel_root == "." else os.path.join(rel_root, name)
            entries.append(
                {
                    "path": path,
                    "rel": rel.replace("\\", "/"),
                    "name": name,
                    "size": stat.st_size,
                    "mtime": int(stat.st_mtime),
                    "included": real in included,
                    "editable": is_text_ext(path) and not _is_binary(path),
                    "is_main": real == main_path,
                    "external": False,
                }
            )

    # 补充 include 到 nginx 目录之外的文件
    seen = {os.path.realpath(e["path"]) for e in entries}
    for src in tree.all_files():
        real = os.path.realpath(src.path)
        if real in seen:
            continue
        try:
            stat = os.stat(src.path)
        except OSError:
            continue
        entries.append(
            {
                "path": src.path,
                "rel": src.path.replace("\\", "/"),
                "name": os.path.basename(src.path),
                "size": stat.st_size,
                "mtime": int(stat.st_mtime),
                "included": True,
                "editable": not _is_binary(src.path),
                "is_main": real == main_path,
                "external": True,
            }
        )

    entries.sort(key=lambda e: (not e["is_main"], e["rel"]))
    return {
        "prefix": prefix,
        "conf_path": target.conf_abs,
        "files": entries,
        "truncated": truncated,
        "errors": tree.errors,
    }


def _allowed_paths(inst: dict, tree: ConfTree) -> set:
    prefix = os.path.realpath(inst["prefix"])
    paths = {prefix}
    for src in tree.all_files():
        paths.add(os.path.realpath(src.path))
    return paths


def _within(real: str, prefix: str) -> bool:
    try:
        return os.path.commonpath([real, prefix]) == prefix
    except ValueError:
        return False


def check_path_allowed(path: str, inst: dict, tree: ConfTree) -> str:
    real = os.path.realpath(path)
    prefix = os.path.realpath(inst["prefix"])
    if _within(real, prefix):
        return path
    for src in tree.all_files():
        if os.path.realpath(src.path) == real:
            return path
    raise AppError(t("file.outside_prefix"), 403)


def read_file(inst: dict, path: str, tree: Optional[ConfTree] = None) -> dict:
    target = target_of(inst)
    tree = tree or load_tree(target.conf_abs, inst["prefix"])
    path = path if os.path.isabs(path) else os.path.join(inst["prefix"], path)
    path = check_path_allowed(path, inst, tree)
    if not os.path.isfile(path):
        raise AppError(t("file.not_found"), 404)
    if _is_binary(path):
        raise AppError(t("file.not_text"), 400)
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError as exc:
        raise AppError(t("file.read_failed", error=exc), 500)
    bom = raw.startswith(b"\xef\xbb\xbf")
    if bom:
        raw = raw[3:]
    content = raw.decode("utf-8", "surrogateescape")
    parsed = parse_source(content, path)
    return {
        "path": path,
        "content": content,
        "hash": file_sha(path),
        "bom": bom,
        "eol": "\r\n" if "\r\n" in content else "\n",
        "parse_error": parsed.error,
        "size": len(raw),
    }


def snapshot_diff(inst: dict, snapshot_content: str, path: str) -> str:
    current = read_file(inst, path)["content"]
    diff = difflib.unified_diff(
        snapshot_content.splitlines(keepends=True),
        current.splitlines(keepends=True),
        fromfile=t("file.diff_snapshot", name=os.path.basename(path)),
        tofile=t("file.diff_current", name=os.path.basename(path)),
        lineterm="\n",
    )
    return "".join(diff)