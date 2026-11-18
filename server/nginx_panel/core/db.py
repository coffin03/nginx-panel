"""SQLite 访问层（标准库 sqlite3，WAL 模式，无 ORM）。"""

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from .config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS instance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    binary TEXT NOT NULL,
    prefix TEXT NOT NULL,
    conf_path TEXT NOT NULL,
    run_mode TEXT NOT NULL DEFAULT 'local',
    systemd_unit TEXT NOT NULL DEFAULT '',
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS snapshot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    instance_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    message TEXT NOT NULL DEFAULT '',
    trigger TEXT NOT NULL DEFAULT 'manual',
    files_hash TEXT NOT NULL,
    test_ok INTEGER,
    operator TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (instance_id) REFERENCES instance(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_snapshot_instance ON snapshot(instance_id, id DESC);

CREATE TABLE IF NOT EXISTS blob (
    snapshot_id INTEGER NOT NULL,
    path TEXT NOT NULL,
    content_zlib BLOB NOT NULL,
    PRIMARY KEY (snapshot_id, path),
    FOREIGN KEY (snapshot_id) REFERENCES snapshot(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS apply_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    instance_id INTEGER NOT NULL,
    snapshot_id INTEGER,
    created_at TEXT NOT NULL,
    ok INTEGER NOT NULL,
    message TEXT NOT NULL DEFAULT '',
    detail TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS operation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    instance_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    action TEXT NOT NULL,
    ok INTEGER NOT NULL,
    detail TEXT NOT NULL DEFAULT ''
);
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.db_path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=15000")
    return conn


@contextmanager
def db() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with db() as conn:
        conn.executescript(SCHEMA)