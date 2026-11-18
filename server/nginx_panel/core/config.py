"""全局配置。"""

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

from .paths import data_dir


@dataclass
class Settings:
    data_dir: Path
    host: str = "127.0.0.1"
    port: int = 8090
    session_max_age: int = 7 * 24 * 3600
    secret_key: str = field(default="")

    @property
    def db_path(self) -> Path:
        return self.data_dir / "nginx-panel.db"

    @property
    def log_dir(self) -> Path:
        d = self.data_dir / "logs"
        d.mkdir(parents=True, exist_ok=True)
        return d


def _load_secret(path: Path) -> str:
    env = os.environ.get("NGINX_PANEL_SECRET")
    if env:
        return env
    if path.exists():
        value = path.read_text(encoding="utf-8").strip()
        if value:
            return value
    value = secrets.token_urlsafe(48)
    path.write_text(value, encoding="utf-8")
    return value


def load_settings() -> Settings:
    env_dir = os.environ.get("NGINX_PANEL_DATA_DIR")
    d = Path(env_dir).resolve() if env_dir else data_dir()
    d.mkdir(parents=True, exist_ok=True)
    settings = Settings(data_dir=d)
    settings.host = os.environ.get("NGINX_PANEL_HOST", settings.host)
    settings.port = int(os.environ.get("NGINX_PANEL_PORT", settings.port))
    settings.secret_key = _load_secret(d / "secret.key")
    return settings


settings = load_settings()