"""站点：列表、新建、启停与删除。"""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ..core.security import current_user
from ..services.instances import get_instance
from ..services.sites import create_site, delete_site, list_sites, preview_site, set_site_enabled

router = APIRouter(prefix="/instances/{instance_id}/sites", tags=["sites"])


class SitePayload(BaseModel):
    server_name: str = ""
    kind: str = "static"
    root: str = ""
    proxy_pass: str = ""
    location: str = "/"
    listen: int = 80
    redirect_http: bool = True
    redirect_port: int = 80
    ssl: bool = False
    ssl_certificate: str = ""
    ssl_certificate_key: str = ""
    access_log: str = ""
    error_log: str = ""
    index: str = "index.html index.htm"
    filename: str = ""


@router.post("/preview")
def preview(instance_id: int, payload: SitePayload, _: dict = Depends(current_user)):
    return preview_site(get_instance(instance_id), payload.model_dump())


@router.get("")
def index(instance_id: int, _: dict = Depends(current_user)):
    return list_sites(get_instance(instance_id))


@router.post("")
def create(instance_id: int, payload: SitePayload, user: dict = Depends(current_user)):
    inst = get_instance(instance_id)
    return create_site(inst, payload.model_dump(), operator=user["username"])


@router.post("/{name}/enable")
def enable(instance_id: int, name: str, user: dict = Depends(current_user), reload: bool = Query(True)):
    return set_site_enabled(get_instance(instance_id), name, True, operator=user["username"], reload=reload)


@router.post("/{name}/disable")
def disable(instance_id: int, name: str, user: dict = Depends(current_user), reload: bool = Query(True)):
    return set_site_enabled(get_instance(instance_id), name, False, operator=user["username"], reload=reload)


@router.delete("/{name}")
def remove(instance_id: int, name: str, user: dict = Depends(current_user), reload: bool = Query(True)):
    return delete_site(get_instance(instance_id), name, operator=user["username"], reload=reload)