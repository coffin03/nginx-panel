"""登录与账号接口。"""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from ..core.errors import AppError
from ..core.security import (
    check_rate_limit,
    clear_failures,
    create_user,
    current_user,
    get_user,
    hash_password,
    record_failure,
    user_count,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class Credentials(BaseModel):
    username: str
    password: str


class PasswordChange(BaseModel):
    old_password: str
    new_password: str


@router.get("/status")
def auth_status(request: Request):
    initialized = user_count() > 0
    uid = request.session.get("uid")
    username = None
    if uid:
        from ..core.security import get_user_by_id

        user = get_user_by_id(int(uid))
        if user:
            username = user["username"]
        else:
            request.session.clear()
    return {"initialized": initialized, "authenticated": bool(username), "username": username}


@router.post("/setup")
def setup(payload: Credentials, request: Request):
    if user_count() > 0:
        raise AppError("管理员已存在，请直接登录", 400)
    username = payload.username.strip()
    if len(username) < 2:
        raise AppError("用户名至少 2 个字符")
    if len(payload.password) < 6:
        raise AppError("密码至少 6 位")
    uid = create_user(username, payload.password)
    request.session["uid"] = uid
    return {"ok": True, "username": username}


@router.post("/login")
def login(payload: Credentials, request: Request):
    key = f"{request.client.host if request.client else 'local'}:{payload.username}"
    check_rate_limit(key)
    user = get_user(payload.username.strip())
    if not user or not verify_password(payload.password, user["password_hash"]):
        record_failure(key)
        raise AppError("用户名或密码错误", 401)
    clear_failures(key)
    request.session["uid"] = user["id"]
    return {"ok": True, "username": user["username"]}


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@router.post("/password")
def change_password(payload: PasswordChange, user: dict = Depends(current_user)):
    if not verify_password(payload.old_password, user["password_hash"]):
        raise AppError("原密码错误", 400)
    if len(payload.new_password) < 6:
        raise AppError("新密码至少 6 位")
    from ..core.db import db

    with db() as conn:
        conn.execute("UPDATE user SET password_hash=? WHERE id=?", (hash_password(payload.new_password), user["id"]))
    return {"ok": True}