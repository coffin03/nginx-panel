"""配置体检接口。"""

from fastapi import APIRouter, Depends

from ..core.security import current_user
from ..services.checks import collect_checks
from ..services.instances import get_instance

router = APIRouter(prefix="/instances/{instance_id}/checks", tags=["checks"])


@router.get("")
def index(instance_id: int, _: dict = Depends(current_user)):
    return collect_checks(get_instance(instance_id))