"""API 路由注册。"""

from fastapi import APIRouter

from . import auth, backup, certs, checks, config, history, instances, logs, sites, system

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(instances.router)
api_router.include_router(config.router)
api_router.include_router(history.router)
api_router.include_router(logs.router)
api_router.include_router(system.router)
api_router.include_router(certs.router)
api_router.include_router(sites.router)
api_router.include_router(checks.router)
api_router.include_router(backup.router)


@api_router.get("/health")
def health():
    return {"ok": True, "app": "nginx-panel"}