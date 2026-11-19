"""配置备份：导出、导入前检查、导入。"""

import io

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..core.security import current_user
from ..services.backup import export_backup, import_backup, inspect_backup
from ..services.instances import get_instance

router = APIRouter(prefix="/instances/{instance_id}/backup", tags=["backup"])


class BackupPayload(BaseModel):
    data: str


class ImportPayload(BaseModel):
    data: str
    reload: bool = True


@router.get("/export")
def export(instance_id: int, _: dict = Depends(current_user)):
    data, filename = export_backup(get_instance(instance_id))
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/inspect")
def inspect(instance_id: int, payload: BackupPayload, _: dict = Depends(current_user)):
    return inspect_backup(get_instance(instance_id), payload.data)


@router.post("/import")
def do_import(instance_id: int, payload: ImportPayload, user: dict = Depends(current_user)):
    return import_backup(
        get_instance(instance_id),
        payload.data,
        operator=user["username"],
        reload=payload.reload,
    )