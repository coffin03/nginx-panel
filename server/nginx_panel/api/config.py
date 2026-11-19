"""配置文件读取、应用、结构化表单接口。"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from ..core.errors import AppError
from ..core.i18n import t
from ..core.security import current_user
from ..services.apply import apply_changes, file_sha
from ..services.files import list_files, read_file
from ..services.form import get_form, save_form
from ..services.instances import get_instance, load_instance_tree

router = APIRouter(prefix="/instances/{instance_id}", tags=["config"])


class FileWrite(BaseModel):
    path: str
    content: str
    base_hash: Optional[str] = None
    message: str = ""
    reload: bool = True


class Change(BaseModel):
    path: str
    content: str
    base_hash: Optional[str] = None


class ApplyPayload(BaseModel):
    changes: List[Change] = Field(default_factory=list)
    message: str = ""
    reload: bool = True


@router.get("/tree")
def tree(instance_id: int, _: dict = Depends(current_user)):
    inst = get_instance(instance_id)
    return list_files(inst)


@router.get("/file")
def file_content(instance_id: int, path: str = Query(...), _: dict = Depends(current_user)):
    inst = get_instance(instance_id)
    return read_file(inst, path)


@router.put("/file")
def write_file(instance_id: int, payload: FileWrite, user: dict = Depends(current_user)):
    inst = get_instance(instance_id)
    result = apply_changes(
        inst,
        [{"path": payload.path, "content": payload.content, "base_hash": payload.base_hash}],
        message=payload.message or t("config.edit_message"),
        operator=user["username"],
        reload=payload.reload,
        trigger="editor",
    )
    return result


@router.post("/apply")
def apply(instance_id: int, payload: ApplyPayload, user: dict = Depends(current_user)):
    inst = get_instance(instance_id)
    if not payload.changes:
        raise AppError(t("config.empty_changes"))
    return apply_changes(
        inst,
        [c.model_dump() for c in payload.changes],
        message=payload.message or t("config.batch_message"),
        operator=user["username"],
        reload=payload.reload,
        trigger="batch",
    )


@router.get("/form")
def form(instance_id: int, _: dict = Depends(current_user)):
    return get_form(get_instance(instance_id))


@router.post("/form")
def save_form_api(instance_id: int, payload: dict, user: dict = Depends(current_user)):
    return save_form(get_instance(instance_id), payload, user["username"])


@router.get("/hashes")
def hashes(instance_id: int, _: dict = Depends(current_user)):
    inst = get_instance(instance_id)
    tree = load_instance_tree(inst)
    return {src.path: file_sha(src.path) for src in tree.all_files()}