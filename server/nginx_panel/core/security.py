"""认证与密码散列。"""

import time
from typing import Optional

import bcrypt
from fastapi import HTTPException, Request, status

from .db import db

_LOGIN_FAILS: dict[str, list[float]] = {}
MAX_FAILS = 8
WINDOW = 300.0


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def user_count() -> int:
    with db() as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM user").fetchone()
    return int(row["c"])


def create_user(username: str, password: str) -> int:
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO user(username, password_hash, created_at) VALUES (?,?,datetime('now','localtime'))",
            (username, hash_password(password)),
        )
        return int(cur.lastrowid)


def get_user(username: str) -> Optional[dict]:
    with db() as conn:
        row = conn.execute("SELECT * FROM user WHERE username=?", (username,)).fetchone()
    return dict(row) if row else None


def get_user_by_id(uid: int) -> Optional[dict]:
    with db() as conn:
        row = conn.execute("SELECT * FROM user WHERE id=?", (uid,)).fetchone()
    return dict(row) if row else None


def check_rate_limit(key: str) -> None:
    now = time.time()
    fails = [t for t in _LOGIN_FAILS.get(key, []) if now - t < WINDOW]
    _LOGIN_FAILS[key] = fails
    if len(fails) >= MAX_FAILS:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "尝试次数过多，请稍后再试")


def record_failure(key: str) -> None:
    _LOGIN_FAILS.setdefault(key, []).append(time.time())


def clear_failures(key: str) -> None:
    _LOGIN_FAILS.pop(key, None)


def current_user(request: Request) -> dict:
    uid = request.session.get("uid")
    if not uid:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "未登录")
    user = get_user_by_id(int(uid))
    if not user:
        request.session.clear()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "会话失效")
    return user


def require_setup_done() -> None:
    if user_count() == 0:
        raise HTTPException(status.HTTP_428_PRECONDITION_REQUIRED, "尚未初始化管理员账号")