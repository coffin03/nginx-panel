"""证书续期：检测本机的 ACME 客户端，执行续期命令并校验结果。

续期本身交给 certbot / acme.sh 等成熟工具，面板只负责编排：
检测可用命令 → 执行 → 比对证书是否真的更新 → 按需 reload nginx。
"""

import glob
import os
import shutil
import subprocess
from typing import List, Optional

from ..core.db import db
from ..core.errors import AppError
from ..core.i18n import t
from ..nginx.certinfo import load_certificate
from ..nginx.process import build_adapter
from .instances import load_instance_tree, target_of

RENEW_TIMEOUT = 180


def _resolve(path: str, prefix: str) -> str:
    return path if os.path.isabs(path) else os.path.join(prefix, path)


def _certbot_lineage(cert_path: str) -> Optional[str]:
    normalized = cert_path.replace("\\", "/")
    marker = "/etc/letsencrypt/live/"
    if marker in normalized:
        return normalized.split(marker, 1)[1].split("/")[0]

    real = os.path.realpath(cert_path)
    for conf in glob.glob("/etc/letsencrypt/renewal/*.conf"):
        try:
            with open(conf, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError:
            continue
        for line in text.splitlines():
            key, _, value = line.partition("=")
            if key.strip() in ("cert", "cert_path") and value.strip():
                if os.path.realpath(value.strip()) == real:
                    return os.path.splitext(os.path.basename(conf))[0]
    return None


def _certbot() -> Optional[dict]:
    exe = shutil.which("certbot")
    if not exe:
        return None
    return {"id": "certbot", "label": "certbot", "command": "", "exe": exe}


def _acmesh() -> Optional[dict]:
    candidates = [shutil.which("acme.sh"), os.path.expanduser("~/.acme.sh/acme.sh"), "/root/.acme.sh/acme.sh"]
    exe = next((p for p in candidates if p and os.path.isfile(p)), None)
    if not exe:
        return None
    return {"id": "acme", "label": "acme.sh", "command": "", "exe": exe}


def detect_options(inst: dict, cert_path: str) -> List[dict]:
    path = _resolve(cert_path, inst["prefix"])
    domains: List[str] = []
    try:
        domains = load_certificate(path).get("domains") or []
    except Exception:
        pass

    options: List[dict] = []
    certbot = _certbot()
    if certbot:
        lineage = _certbot_lineage(path)
        command = f'"{certbot["exe"]}" renew --non-interactive'
        if lineage:
            command += f' --cert-name "{lineage}"'
        options.append({"id": "certbot", "label": "certbot", "command": command})

    acme = _acmesh()
    if acme and domains:
        domain = domains[0]
        options.append(
            {"id": "acme", "label": "acme.sh", "command": f'"{acme["exe"]}" --renew -d "{domain}" --force'}
        )

    options.append({"id": "custom", "label": t("renew.custom"), "command": ""})
    return options


def _brief(info: Optional[dict]) -> Optional[dict]:
    if not info:
        return None
    return {
        "domains": info.get("domains", []),
        "not_after": info.get("not_after"),
        "sha256": info.get("sha256"),
    }


def renew_certificate(
    inst: dict,
    cert_path: str,
    command: str,
    reload: bool = True,
    operator: str = "",
) -> dict:
    path = _resolve(cert_path, inst["prefix"])
    if not os.path.isfile(path):
        raise AppError(t("renew.cert_missing", path=cert_path))
    if not (command or "").strip():
        raise AppError(t("renew.no_command"))

    try:
        before = load_certificate(path)
    except Exception as exc:
        raise AppError(t("cert.invalid", error=exc))

    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=inst["prefix"],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=RENEW_TIMEOUT,
        )
        exit_code = proc.returncode
        output = (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired:
        exit_code = -1
        output = t("renew.timeout", seconds=RENEW_TIMEOUT)

    try:
        after = load_certificate(path)
        parse_error = ""
    except Exception as exc:
        after = None
        parse_error = str(exc)

    changed = bool(
        after
        and (after.get("sha256") != before.get("sha256") or after.get("not_after") != before.get("not_after"))
    )

    reload_result = None
    if changed and reload:
        adapter = build_adapter(target_of(inst), load_instance_tree(inst))
        result = adapter.reload()
        reload_result = {"ok": result.ok, "output": result.output, "exit_code": result.exit_code}

    output = output[-8000:]
    with db() as conn:
        conn.execute(
            """INSERT INTO operation(instance_id,created_at,action,ok,detail)
               VALUES (?,datetime('now','localtime'),?,?,?)""",
            (inst["id"], "renew-cert", int(exit_code == 0 and changed), output[:4000]),
        )

    return {
        "ok": exit_code == 0,
        "changed": changed,
        "exit_code": exit_code,
        "output": output,
        "parse_error": parse_error,
        "before": _brief(before),
        "after": _brief(after),
        "reload": reload_result,
        "path": path,
        "operator": operator,
    }