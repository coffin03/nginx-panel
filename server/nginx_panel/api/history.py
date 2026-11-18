"""历史快照：列表、查看、diff、回滚。"""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ..core.security import current_user
from ..services.apply import restore_snapshot
from ..services.files import snapshot_diff
from ..services.instances import get_instance
from ..services.snapshots import get_snapshot, list_snapshots, load_snapshot_file

router = APIRouter(prefix="/instances/{instance_id}/snapshots", tags=["history"])


class RestorePayload(BaseModel):
    reload: bool = True


@router.get("")
def index(
    instance_id: int,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _: dict = Depends(current_user),
):
    get_instance(instance_id)
    return list_snapshots(instance_id, limit, offset)


@router.get("/{snapshot_id}")
def detail(instance_id: int, snapshot_id: int, _: dict = Depends(current_user)):
    get_instance(instance_id)
    return get_snapshot(instance_id, snapshot_id)


@router.get("/{snapshot_id}/file")
def file_at(instance_id: int, snapshot_id: int, path: str = Query(...), _: dict = Depends(current_user)):
    get_instance(instance_id)
    return {"path": path, "content": load_snapshot_file(snapshot_id, path)}


@router.get("/{snapshot_id}/diff")
def diff(instance_id: int, snapshot_id: int, path: str = Query(...), _: dict = Depends(current_user)):
    inst = get_instance(instance_id)
    content = load_snapshot_file(snapshot_id, path)
    return {"path": path, "diff": snapshot_diff(inst, content, path)}


@router.post("/{snapshot_id}/restore")
def restore(
    instance_id: int,
    snapshot_id: int,
    payload: RestorePayload,
    user: dict = Depends(current_user),
):
    inst = get_instance(instance_id)
    return restore_snapshot(inst, snapshot_id, user["username"], reload=payload.reload)