"""配置生效流水线：校验基线 → 快照 → 写盘 → nginx -t → reload → 健康检查，失败自动还原。"""

import hashlib
import os
import re
import threading
import time
from typing import Dict, List, Optional

from ..core.errors import AppError
from ..nginx.includes import ConfTree, load_tree
from ..nginx.parser import parse_source
from ..nginx.process import build_adapter
from .instances import target_of
from .snapshots import create_snapshot, log_apply, mark_test_result

_LOCKS: Dict[int, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()

_ERR_RE = re.compile(r"\[(emerg|alert|crit|error|warn)\] (.+)")
_LOC_RE = re.compile(r"in (.+?):(\d+)\s*$")


def _lock(instance_id: int) -> threading.Lock:
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(instance_id, threading.Lock())


def file_sha(path: str) -> Optional[str]:
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    except OSError:
        return None


def normalize_path(path: str, prefix: str) -> str:
    return path if os.path.isabs(path) else os.path.join(prefix, path)


def ensure_allowed(path: str, prefix: str, tree: ConfTree) -> None:
    real = os.path.realpath(path)
    prefix_real = os.path.realpath(prefix)
    if os.path.commonpath([real, prefix_real]) == prefix_real:
        return
    for src in tree.all_files():
        if os.path.realpath(src.path) == real:
            return
    raise AppError(f"不允许写入 nginx 目录之外的文件: {path}", 400)


def parse_nginx_errors(output: str) -> List[dict]:
    errors = []
    for line in output.splitlines():
        if not line.strip() or "test failed" in line:
            continue
        m = _ERR_RE.search(line)
        if not m:
            continue
        level, rest = m.group(1), m.group(2)
        loc = _LOC_RE.search(rest)
        item = {"level": level, "message": rest.strip()}
        if loc:
            item["file"] = loc.group(1).strip()
            item["line"] = int(loc.group(2))
            item["message"] = _LOC_RE.sub("", rest).strip()
        errors.append(item)
    return errors


def _write_bytes(path: str, data: bytes) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".ngp-tmp"
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.replace(tmp, path)


def _read_bytes(path: str) -> Optional[bytes]:
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError:
        return None


def error_log_path(tree: ConfTree, prefix: str) -> str:
    from ..nginx.process import find_directive

    node = find_directive(tree.root.nodes if tree.root else [], "error_log")
    if node and node.args:
        value = node.args[0]
        return value if os.path.isabs(value) else os.path.join(prefix, value)
    return os.path.join(prefix, "logs", "error.log")


def _tail_new(path: str, offset: int) -> str:
    try:
        size = os.path.getsize(path)
        if size <= offset:
            return ""
        with open(path, "rb") as fh:
            fh.seek(offset)
            return fh.read(200_000).decode("utf-8", "replace")
    except OSError:
        return ""


def apply_changes(
    inst: dict,
    changes: List[dict],
    message: str = "",
    operator: str = "",
    reload: bool = True,
    trigger: str = "manual",
    retest_only: bool = False,
) -> dict:
    """changes: [{path, content, base_hash?}]；base_hash 为 null 时不做冲突检查。"""
    prefix = inst["prefix"]
    target = target_of(inst)
    with _lock(int(inst["id"])):
        tree = load_tree(target.conf_abs, prefix)
        if tree.root is None:
            raise AppError("无法读取主配置，请检查实例配置", 400)

        adapter = build_adapter(target, tree)
        before_status = adapter.status()

        # 1. 路径与基线校验
        conflicts = []
        warnings = []
        prepared: List[dict] = []
        seen = set()
        for change in changes:
            path = normalize_path(change["path"], prefix)
            if path in seen:
                raise AppError(f"重复修改同一文件: {path}")
            seen.add(path)
            ensure_allowed(path, prefix, tree)
            current = file_sha(path)
            base_hash = change.get("base_hash")
            if base_hash and current and base_hash != current:
                conflicts.append({"path": path, "expected": base_hash, "actual": current})
                continue
            content = change.get("content", "")
            parsed = parse_source(content, path)
            if parsed.error:
                warnings.append({"path": path, "message": parsed.error})
            prepared.append({"path": path, "content": content, "exists": current is not None})

        if conflicts:
            raise AppError("文件已在磁盘上被修改，请刷新后重试", 409, {"conflicts": conflicts})

        if not prepared:
            raise AppError("没有需要应用的修改")

        # 2. 先快照当前状态
        snapshot_id = create_snapshot(
            int(inst["id"]), tree, message or "应用配置修改", trigger=trigger, operator=operator
        )

        # 3. 备份并写入
        from ..core.watcher import mark_applied

        mark_applied(int(inst["id"]), 5.0)
        originals: Dict[str, Optional[bytes]] = {p["path"]: _read_bytes(p["path"]) for p in prepared}
        try:
            for item in prepared:
                raw = item["content"].encode("utf-8", "surrogateescape")
                old = originals[item["path"]]
                if old is not None and old.startswith(b"\xef\xbb\xbf"):
                    raw = b"\xef\xbb\xbf" + raw
                _write_bytes(item["path"], raw)
        except OSError as exc:
            _restore(originals)
            log_apply(int(inst["id"]), snapshot_id, False, "写盘失败", str(exc))
            raise AppError(f"写入配置失败: {exc}", 500, {"snapshot_id": snapshot_id})

        # 4. nginx -t
        test = adapter.test()
        if not test.ok:
            _restore(originals)
            mark_test_result(snapshot_id, False)
            log_apply(int(inst["id"]), snapshot_id, False, "配置校验失败", test.output)
            raise AppError(
                "nginx 配置校验失败，已自动还原",
                400,
                {
                    "stage": "test",
                    "output": test.output,
                    "errors": parse_nginx_errors(test.output),
                    "snapshot_id": snapshot_id,
                    "warnings": warnings,
                },
            )
        mark_test_result(snapshot_id, True)

        # 5. reload 与健康检查
        reload_output = ""
        if reload and before_status.running:
            log_before = _log_offset(tree, prefix)
            rl = adapter.reload()
            reload_output = rl.output
            if not rl.ok:
                _restore(originals)
                adapter.reload()
                log_apply(int(inst["id"]), snapshot_id, False, "reload 失败，已回滚", rl.output)
                raise AppError(
                    "reload 失败，已自动回滚",
                    500,
                    {
                        "stage": "reload",
                        "output": rl.output,
                        "errors": parse_nginx_errors(rl.output),
                        "snapshot_id": snapshot_id,
                    },
                )
            time.sleep(0.3)
            after = adapter.status()
            new_log = _tail_new(error_log_path(tree, prefix), log_before)
            fatal = [ln for ln in new_log.splitlines() if "[emerg]" in ln or "[alert]" in ln]
            if not after.running or fatal:
                _restore(originals)
                adapter.reload()
                detail = "\n".join(fatal[:20]) or "reload 后进程未运行"
                log_apply(int(inst["id"]), snapshot_id, False, "健康检查失败，已回滚", detail)
                raise AppError(
                    "reload 后健康检查失败，已自动回滚",
                    500,
                    {"stage": "health", "output": detail, "snapshot_id": snapshot_id},
                )

        log_apply(int(inst["id"]), snapshot_id, True, message or "应用配置修改", test.output)
        return {
            "ok": True,
            "snapshot_id": snapshot_id,
            "test_output": test.output,
            "reload_output": reload_output,
            "reloaded": bool(reload and before_status.running),
            "warnings": warnings,
            "files": [p["path"] for p in prepared],
        }


def _log_offset(tree: ConfTree, prefix: str) -> int:
    try:
        return os.path.getsize(error_log_path(tree, prefix))
    except OSError:
        return 0


def _restore(originals: Dict[str, Optional[bytes]]) -> None:
    for path, data in originals.items():
        try:
            if data is None:
                if os.path.exists(path):
                    os.remove(path)
            else:
                _write_bytes(path, data)
        except OSError:
            pass


def restore_snapshot(inst: dict, snapshot_id: int, operator: str = "", reload: bool = True) -> dict:
    from .snapshots import snapshot_files

    files = snapshot_files(snapshot_id)
    if not files:
        raise AppError("快照为空，无法回滚", 400)
    target = target_of(inst)
    tree = load_tree(target.conf_abs, inst["prefix"])
    extra = [src.path for src in tree.all_files() if src.path not in files]
    changes = [{"path": path, "content": content, "base_hash": None} for path, content in files.items()]
    result = apply_changes(
        inst, changes, message=f"回滚到快照 #{snapshot_id}", operator=operator, reload=reload, trigger="restore"
    )
    result["untouched_extra_files"] = extra
    return result