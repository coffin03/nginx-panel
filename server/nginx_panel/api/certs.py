"""证书：列表、续期命令探测与执行。"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..core.security import current_user
from ..services.certs import collect_certificates
from ..services.instances import get_instance
from ..services.renew import detect_options, renew_certificate

router = APIRouter(prefix="/instances/{instance_id}/certificates", tags=["certificates"])


class RenewPayload(BaseModel):
    path: str
    command: str
    reload: bool = True


@router.get("")
def index(instance_id: int, _: dict = Depends(current_user)):
    inst = get_instance(instance_id)
    return {"certificates": collect_certificates(inst)}


@router.get("/renew-options")
def renew_options(instance_id: int, path: str, _: dict = Depends(current_user)):
    inst = get_instance(instance_id)
    return {"options": detect_options(inst, path)}


@router.post("/renew")
def renew(instance_id: int, payload: RenewPayload, user: dict = Depends(current_user)):
    inst = get_instance(instance_id)
    return renew_certificate(
        inst,
        payload.path,
        payload.command,
        reload=payload.reload,
        operator=user["username"],
    )