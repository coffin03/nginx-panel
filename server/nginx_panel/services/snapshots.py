"""快照：把配置树整体压缩存入 SQLite，用于历史、diff 与回滚。"""

import hashlib
import os
import zlib
from typing import Dict, List, Optional

from ..core.db import db
from ..nginx.includes import ConfTree


def file_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def tree_files_hash(tree: ConfTree) -> str:
    h = hashlib.sha256()
    for src in sorted(tree.all_files(), key=lambda s: s.path):
        try:
            with open(src.path, "rb") as fh:
                data = fh.read()
        except OSError:
            data = b""
        h.update(os.path.normcase(src.path).encode("utf-8", "surrogateescape"))
        h.update(b"\0")
        h.update(file_hash(data).encode())
        h.update(b"\n")
    return h.hexdigest()


def capture_files(tree: ConfTree) -> Dict[str, str]:
    files: Dict[str, str] = {}
    for src in tree.all_files():
        try:
            with open(src.path, "rb") as fh:
                raw = fh.read()
            files[src.path] = raw.decode("utf-8", "surrogateescape")
        except OSError:
            continue
    return files


def create_snapshot(
    instance_id: int,
    tree: ConfTree,
    message: str,
    trigger: str = "manual",
    operator: str = "",
    test_ok: Optional[bool] = None,
) -> int:
    files = capture_files(tree)
    digest = tree_files_hash(tree)
    with db() as conn:
        cur = conn.execute(
            """INSERT INTO snapshot(instance_id,created_at,message,trigger,files_hash,test_ok,operator)
               VALUES (?,datetime('now','localtime'),?,?,?,?,?)""",
            (instance_id, message, trigger, digest, None if test_ok is None else int(test_ok), operator),
        )
        snapshot_id = int(cur.lastrowid)
        rows = [(snapshot_id, path, zlib.compress(content.encode("utf-8", "surrogateescape"), 6)) for path, content in files.items()]
        conn.executemany("INSERT INTO blob(snapshot_id,path,content_zlib) VALUES (?,?,?)", rows)
    return snapshot_id


def list_snapshots(instance_id: int, limit: int = 50, offset: int = 0) -> List[dict]:
    with db() as conn:
        rows = conn.execute(
            """SELECT s.id,s.created_at,s.message,s.trigger,s.files_hash,s.test_ok,s.operator,
                      (SELECT COUNT(*) FROM blob b WHERE b.snapshot_id=s.id) AS file_count
               FROM snapshot s WHERE s.instance_id=? ORDER BY s.id DESC LIMIT ? OFFSET ?""",
            (instance_id, limit, offset),
        ).fetchall()
    return [dict(r) for r in rows]


def get_snapshot(instance_id: int, snapshot_id: int) -> dict:
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM snapshot WHERE id=? AND instance_id=?", (snapshot_id, instance_id)
        ).fetchone()
        if not row:
            from ..core.errors import AppError

            raise AppError("快照不存在", 404)
        files = conn.execute(
            "SELECT path, LENGTH(content_zlib) AS packed_size FROM blob WHERE snapshot_id=? ORDER BY path",
            (snapshot_id,),
        ).fetchall()
    data = dict(row)
    data["files"] = [dict(f) for f in files]
    return data


def load_snapshot_file(snapshot_id: int, path: str) -> str:
    with db() as conn:
        row = conn.execute(
            "SELECT content_zlib FROM blob WHERE snapshot_id=? AND path=?", (snapshot_id, path)
        ).fetchone()
    if not row:
        from ..core.errors import AppError

        raise AppError("快照中不存在该文件", 404)
    return zlib.decompress(row["content_zlib"]).decode("utf-8", "surrogateescape")


def snapshot_files(snapshot_id: int) -> Dict[str, str]:
    with db() as conn:
        rows = conn.execute("SELECT path,content_zlib FROM blob WHERE snapshot_id=?", (snapshot_id,)).fetchall()
    return {r["path"]: zlib.decompress(r["content_zlib"]).decode("utf-8", "surrogateescape") for r in rows}


def mark_test_result(snapshot_id: int, ok: bool) -> None:
    with db() as conn:
        conn.execute("UPDATE snapshot SET test_ok=? WHERE id=?", (int(ok), snapshot_id))


def prune_snapshots(instance_id: int, keep: int = 200) -> None:
    with db() as conn:
        rows = conn.execute(
            "SELECT id FROM snapshot WHERE instance_id=? ORDER BY id DESC LIMIT -1 OFFSET ?",
            (instance_id, keep),
        ).fetchall()
        ids = [r["id"] for r in rows]
        for sid in ids:
            conn.execute("DELETE FROM blob WHERE snapshot_id=?", (sid,))
            conn.execute("DELETE FROM snapshot WHERE id=?", (sid,))


def log_apply(instance_id: int, snapshot_id: Optional[int], ok: bool, message: str, detail: str = "") -> None:
    with db() as conn:
        conn.execute(
            """INSERT INTO apply_log(instance_id,snapshot_id,created_at,ok,message,detail)
               VALUES (?,?,datetime('now','localtime'),?,?,?)""",
            (instance_id, snapshot_id, int(ok), message, detail[:8000]),
        )


def recent_applies(instance_id: int, limit: int = 20) -> List[dict]:
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM apply_log WHERE instance_id=? ORDER BY id DESC LIMIT ?", (instance_id, limit)
        ).fetchall()
    return [dict(r) for r in rows]