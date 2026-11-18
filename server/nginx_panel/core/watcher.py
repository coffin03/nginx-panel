"""外部修改监听：非本程序写入的配置变化自动存一份 auto 快照。"""

import os
import threading
import time
from typing import Dict, Optional

from .db import db

_threads: Dict[int, threading.Event] = {}
_suppress: Dict[int, float] = {}
_last_hash: Dict[int, str] = {}
_guard = threading.Lock()

SKIP_PARTS = ("/logs/", "/temp/", "/client_body_temp/", "/proxy_temp/", "/data/", "__pycache__")
SKIP_SUFFIX = (".log", ".pid", ".ngp-tmp")


def mark_applied(instance_id: int, seconds: float = 4.0) -> None:
    _suppress[instance_id] = time.time() + seconds


def _suppressed(instance_id: int) -> bool:
    return time.time() < _suppress.get(instance_id, 0)


def _filter(_change, path: str) -> bool:
    p = path.replace("\\", "/")
    if any(part in p for part in SKIP_PARTS):
        return False
    if p.endswith(SKIP_SUFFIX):
        return False
    return True


def _current_hash(instance_id: int) -> Optional[str]:
    from ..services.instances import get_instance, load_instance_tree
    from ..services.snapshots import tree_files_hash

    inst = get_instance(instance_id)
    tree = load_instance_tree(inst)
    if tree.root is None:
        return None
    return tree_files_hash(tree)


def _snapshot_if_changed(instance_id: int) -> None:
    from ..services.instances import get_instance, load_instance_tree
    from ..services.snapshots import create_snapshot, tree_files_hash

    try:
        inst = get_instance(instance_id)
        tree = load_instance_tree(inst)
        if tree.root is None:
            return
        digest = tree_files_hash(tree)
        if digest == _last_hash.get(instance_id):
            return
        if _suppressed(instance_id):
            return
        create_snapshot(instance_id, tree, "检测到外部修改，自动快照", trigger="auto")
        _last_hash[instance_id] = digest
    except Exception:
        pass


def _run(instance_id: int, stop: threading.Event) -> None:
    from watchfiles import watch

    backoff = 1.0
    while not stop.is_set():
        try:
            from ..services.instances import get_instance

            inst = get_instance(instance_id)
            prefix = inst["prefix"]
            if not os.path.isdir(prefix):
                if stop.wait(10):
                    return
                continue
            try:
                _last_hash[instance_id] = _current_hash(instance_id) or ""
            except Exception:
                pass
            for _changes in watch(
                prefix,
                watch_filter=_filter,
                debounce=1500,
                step=500,
                stop_event=stop,
                rust_timeout=2000,
            ):
                if stop.is_set():
                    return
                if _suppressed(instance_id):
                    continue
                time.sleep(1.0)
                _snapshot_if_changed(instance_id)
            backoff = 1.0
        except Exception:
            if stop.wait(backoff):
                return
            backoff = min(backoff * 2, 30)


def start_instance(instance_id: int) -> None:
    with _guard:
        existing = _threads.get(instance_id)
        if existing and not existing.is_set():
            return
        stop = threading.Event()
        _threads[instance_id] = stop
    t = threading.Thread(target=_run, args=(instance_id, stop), name=f"watch-{instance_id}", daemon=True)
    t.start()


def stop_instance(instance_id: int) -> None:
    with _guard:
        stop = _threads.pop(instance_id, None)
    if stop:
        stop.set()
    _last_hash.pop(instance_id, None)


def restart_instance(instance_id: int) -> None:
    stop_instance(instance_id)
    start_instance(instance_id)


def start_all() -> None:
    from ..services.instances import list_instances

    for inst in list_instances():
        start_instance(int(inst["id"]))


def stop_all() -> None:
    for instance_id in list(_threads.keys()):
        stop_instance(instance_id)