"""FastAPI 应用入口。"""

import os
import sys
import threading
import webbrowser
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .api import api_router
from .core.config import settings
from .core.db import init_db
from .core.errors import AppError
from .core.paths import web_dist_dir


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    try:
        from .core.watcher import start_all

        start_all()
    except Exception:
        pass
    yield
    try:
        from .core.watcher import stop_all

        stop_all()
    except Exception:
        pass


def create_app() -> FastAPI:
    app = FastAPI(
        title="nginx-panel",
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        session_cookie="ngp_session",
        max_age=settings.session_max_age,
        same_site="lax",
        https_only=False,
    )

    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError):
        return JSONResponse({"message": exc.message, "detail": exc.detail}, status_code=exc.status_code)

    app.include_router(api_router, prefix="/api")

    dist = web_dist_dir()
    if dist.exists():
        assets = dist / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa(full_path: str):
            if full_path.startswith("api/"):
                return JSONResponse({"message": "Not Found"}, status_code=404)
            candidate = dist / full_path
            if full_path and candidate.is_file():
                return FileResponse(str(candidate))
            return FileResponse(str(dist / "index.html"))
    else:

        @app.get("/", include_in_schema=False)
        def placeholder():
            return JSONResponse(
                {
                    "app": "nginx-panel",
                    "message": "前端尚未构建，请在 web/ 目录执行 npm install && npm run build",
                }
            )

    return app


app = create_app()


def _prepare_frozen_runtime() -> None:
    """打包后无控制台：补齐标准流，并把日志写入数据目录。"""
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")

    import logging
    from logging.handlers import RotatingFileHandler

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if not any(isinstance(h, RotatingFileHandler) for h in root.handlers):
        handler = RotatingFileHandler(
            settings.log_dir / "app.log",
            maxBytes=2 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        root.addHandler(handler)


def _open_browser(url: str) -> None:
    import time

    time.sleep(1.2)
    try:
        webbrowser.open(url)
    except Exception:
        pass


def run() -> None:
    import logging

    import uvicorn

    frozen = bool(getattr(sys, "frozen", False))
    if frozen:
        _prepare_frozen_runtime()

    # Windows 打包版默认打开桌面窗口；NGINX_PANEL_BROWSER=1 改用浏览器，
    # NGINX_PANEL_NO_BROWSER=1 只跑后台服务。
    if (
        frozen
        and os.name == "nt"
        and os.environ.get("NGINX_PANEL_NO_BROWSER") != "1"
        and os.environ.get("NGINX_PANEL_BROWSER") != "1"
    ):
        try:
            from .desktop import run_desktop

            run_desktop()
            return
        except Exception:
            logging.getLogger("nginx_panel").exception("桌面窗口启动失败，回退浏览器模式")

    host = settings.host
    port = settings.port
    url = f"http://{'127.0.0.1' if host in ('0.0.0.0', '::') else host}:{port}"

    if os.environ.get("NGINX_PANEL_NO_BROWSER") != "1":
        threading.Thread(target=_open_browser, args=(url,), daemon=True).start()

    print(f"nginx-panel 已启动: {url}")
    print(f"数据目录: {settings.data_dir}")
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=False,
        log_config=None if frozen else uvicorn.config.LOGGING_CONFIG,
    )


if __name__ == "__main__":
    if getattr(sys, "frozen", False):
        run()
    else:
        run()