"""扫描实例配置中引用的证书，解析到期时间与域名。"""

import os
from datetime import datetime, timezone
from typing import Dict, List

from ..core.i18n import t
from ..nginx.certinfo import CertError, load_certificate
from .instances import load_instance_tree

WARN_DAYS = 30


def _resolve(value: str, prefix: str) -> str:
    return value if os.path.isabs(value) else os.path.join(prefix, value)


def collect_certificates(inst: dict) -> List[dict]:
    tree = load_instance_tree(inst)
    prefix = inst["prefix"]
    now = datetime.now(timezone.utc)
    seen: Dict[str, bool] = {}
    items: List[dict] = []

    for node in tree.flatten_nodes():
        if node.name != "ssl_certificate" or not node.args:
            continue
        value = node.args[0]
        if not value or value.startswith("data:"):
            continue
        path = _resolve(value, prefix)
        real = os.path.realpath(path)
        if real in seen:
            continue
        seen[real] = True

        item = {"path": path, "file": node.file, "line": node.line, "exists": os.path.isfile(path), "error": ""}
        try:
            info = load_certificate(path)
            not_after = datetime.strptime(info["not_after"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            days = (not_after - now).days
            item.update(info)
            item["days_left"] = days
            item["status"] = "expired" if days < 0 else ("warning" if days <= WARN_DAYS else "ok")
        except FileNotFoundError:
            item["status"] = "missing"
            item["error"] = t("cert.missing", path=path)
        except (OSError, CertError, ValueError) as exc:
            item["status"] = "invalid"
            item["error"] = t("cert.invalid", error=exc)
        items.append(item)

    items.sort(key=lambda x: x.get("days_left", 10**9))
    return items