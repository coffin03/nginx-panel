"""新建站点：生成 server 块写入 conf.d，并按需在 http 块中挂载 include。

生成内容只包含常用指令；写入仍然走 apply 流水线（快照 → nginx -t → reload →
健康检查 → 失败回滚），与手动编辑的行为保持一致。
"""

import os
import re
from typing import List, Tuple

from ..core.errors import AppError
from ..core.i18n import t
from ..nginx import writer
from ..nginx.includes import load_tree, read_text
from ..nginx.parser import parse_source
from .apply import apply_changes, file_sha
from .instances import target_of

SERVER_NAME_RE = re.compile(r"^[A-Za-z0-9*._:\- ]+$")
SLUG_RE = re.compile(r"[^a-z0-9._-]+")
PROXY_RE = re.compile(r"^(https?://[^\s;{}]+|unix:[^\s;{}]+|[A-Za-z0-9._-]+)$")
FILENAME_RE = re.compile(r"^[A-Za-z0-9._-]+\.conf$")
DISABLED_RE = re.compile(r"^[A-Za-z0-9._-]+\.conf\.disabled$")

SITE_DIR = "conf.d"
INCLUDE_PATTERN = "conf.d/*.conf"
DISABLED_SUFFIX = ".disabled"


def _slug(value: str) -> str:
    slug = SLUG_RE.sub("-", value.strip().lower()).strip("-._")
    return slug[:60] or "site"


def _filename(value: str, server_name: str) -> str:
    name = (value or "").strip()
    if not name:
        name = _slug(server_name.split()[0]) + ".conf"
    elif not name.endswith(".conf"):
        name += ".conf"
    if not FILENAME_RE.match(name) or ".." in name:
        raise AppError(t("site.filename_invalid"))
    return name


def _site_content(data: dict, server_name: str, warnings: List[str], prefix: str) -> str:
    kind = data.get("kind") or "static"
    listen = int(data.get("listen") or 80)
    ssl = bool(data.get("ssl"))
    redirect = bool(data.get("redirect_http", True)) and ssl
    lines: List[str] = [f"# {t('site.comment')}", "server {"]
    lines.append(f"    listen {listen}{' ssl' if ssl else ''};")
    lines.append(f"    server_name {server_name};")
    if ssl:
        lines.append(f"    ssl_certificate {writer.quote_arg(data['ssl_certificate'].strip())};")
        lines.append(f"    ssl_certificate_key {writer.quote_arg(data['ssl_certificate_key'].strip())};")
        lines.append("    ssl_protocols TLSv1.2 TLSv1.3;")
    lines.append("")

    location = data.get("location") or "/"
    if not location.startswith("/") or re.search(r"[\s;{}]", location):
        raise AppError(t("site.location_invalid"))
    lines.append(f"    location {location} {{")
    if kind == "static":
        root = (data.get("root") or "").strip()
        lines.append(f"        root {writer.quote_arg(root)};")
        index = (data.get("index") or "index.html index.htm").strip()
        if index:
            lines.append(f"        index {index};")
        if root:
            check = root if os.path.isabs(root) else os.path.join(prefix, root)
            if not os.path.isdir(check):
                warnings.append(t("site.root_missing", path=root))
    else:
        lines.append(f"        proxy_pass {(data.get('proxy_pass') or '').strip()};")
        lines.append("        proxy_set_header Host $host;")
        lines.append("        proxy_set_header X-Real-IP $remote_addr;")
        lines.append("        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;")
        lines.append("        proxy_set_header X-Forwarded-Proto $scheme;")
    lines.append("    }")

    access_log = (data.get("access_log") or "").strip()
    error_log = (data.get("error_log") or "").strip()
    if access_log:
        lines.append(f"    access_log {writer.quote_arg(access_log)};")
    if error_log:
        lines.append(f"    error_log {writer.quote_arg(error_log)};")
    lines.append("}")

    if redirect:
        port = int(data.get("redirect_port") or 80)
        if port != listen:
            lines.append("")
            lines.append(f"# {t('site.redirect_comment')}")
            lines.append("server {")
            lines.append(f"    listen {port};")
            lines.append(f"    server_name {server_name};")
            lines.append("    return 301 https://$host$request_uri;")
            lines.append("}")
    return "\n".join(lines) + "\n"


def _has_include(src) -> bool:
    for node in src.nodes:
        for item in node.walk():
            if item.is_include and item.args and "conf.d" in item.args[0].replace("\\", "/"):
                return True
    return False


def _http_block(src):
    for node in src.nodes:
        if node.name == "http" and node.block is not None:
            return node
    return None


def _prepare(inst: dict, data: dict) -> Tuple[str, str, str, bool, List[str]]:
    """校验参数并生成站点文件：返回 (rel, abs_path, content, needs_include, warnings)。"""
    prefix = os.path.abspath(inst["prefix"])
    server_name = (data.get("server_name") or "").strip()
    if not server_name:
        raise AppError(t("site.name_required"))
    if not SERVER_NAME_RE.match(server_name):
        raise AppError(t("site.name_invalid"))

    kind = data.get("kind") or "static"
    if kind not in ("static", "proxy"):
        raise AppError(t("site.kind_invalid"))

    try:
        listen = int(data.get("listen") or 80)
    except (TypeError, ValueError):
        raise AppError(t("site.port_invalid"))
    if not 1 <= listen <= 65535:
        raise AppError(t("site.port_invalid"))

    if kind == "static" and not (data.get("root") or "").strip():
        raise AppError(t("site.root_required"))
    if kind == "proxy":
        proxy_pass = (data.get("proxy_pass") or "").strip()
        if not proxy_pass:
            raise AppError(t("site.proxy_required"))
        if not PROXY_RE.match(proxy_pass):
            raise AppError(t("site.proxy_invalid"))

    if data.get("ssl"):
        cert = (data.get("ssl_certificate") or "").strip()
        key = (data.get("ssl_certificate_key") or "").strip()
        if not cert or not key:
            raise AppError(t("site.ssl_required"))
        for value in (cert, key):
            path = value if os.path.isabs(value) else os.path.join(prefix, value)
            if not os.path.isfile(path):
                raise AppError(t("site.ssl_missing", path=value))

    name = _filename(data.get("filename") or "", server_name)
    rel = f"{SITE_DIR}/{name}"
    target_path = os.path.join(prefix, SITE_DIR, name)

    tree = load_tree(target_of(inst).conf_abs, prefix)
    if tree.root is None:
        raise AppError(t("apply.main_conf_unreadable"), 400)
    needs_include = not _has_include(tree.root)
    if needs_include and _http_block(tree.root) is None:
        raise AppError(t("site.no_http_block"), 400)

    warnings: List[str] = []
    content = _site_content(data, server_name, warnings, prefix)
    return rel, target_path, content, needs_include, warnings


def preview_site(inst: dict, data: dict) -> dict:
    rel, path, content, needs_include, warnings = _prepare(inst, data)
    return {
        "rel": rel,
        "path": path,
        "content": content,
        "needs_include": needs_include,
        "exists": os.path.exists(path),
        "warnings": warnings,
    }


def create_site(inst: dict, data: dict, operator: str = "", reload: bool = True) -> dict:
    rel, path, content, needs_include, warnings = _prepare(inst, data)
    if os.path.exists(path):
        raise AppError(t("site.file_exists", path=rel))

    changes = [{"path": path, "content": content}]
    if needs_include:
        prefix = os.path.abspath(inst["prefix"])
        tree = load_tree(target_of(inst).conf_abs, prefix)
        main = tree.root
        http = _http_block(main)
        indent = writer.child_indent(main.text, http)
        edit = writer.insert_block_child_raw(main, http, f"{indent}include {INCLUDE_PATTERN};{main.eol}")
        changes.append(
            {
                "path": main.path,
                "content": writer.apply_edits(main.text, [edit]),
                "base_hash": file_sha(main.path),
            }
        )

    result = apply_changes(
        inst,
        changes,
        message=t("site.message", name=(data.get("server_name") or "").strip()),
        operator=operator,
        reload=reload,
    )
    result.update({"path": path, "rel": rel, "content": content})
    result["warnings"] = list(result.get("warnings") or []) + warnings
    return result


def _describe(path: str, text: str, enabled: bool, loaded: bool) -> dict:
    parsed = parse_source(text, path)
    names: List[str] = []
    listens: List[str] = []
    kind = ""
    certificate = ""
    ssl = False
    for node in parsed.nodes:
        if node.name != "server" or node.block is None:
            continue
        for item in node.walk():
            if item.name == "server_name":
                for value in item.args:
                    if value and value != "_" and value not in names:
                        names.append(value)
            elif item.name == "listen" and item.args:
                value = item.args[0]
                if value not in listens:
                    listens.append(value)
            elif item.name == "ssl_certificate" and item.args and not certificate:
                certificate = item.args[0]
                ssl = True
            elif item.name == "ssl_certificate_key" and item.args:
                ssl = True
            elif item.name == "proxy_pass" and not kind:
                kind = "proxy"
            elif item.name == "root" and not kind:
                kind = "static"
    return {
        "name": os.path.basename(path),
        "rel": f"{SITE_DIR}/{os.path.basename(path)}",
        "path": path,
        "enabled": enabled,
        "loaded": loaded,
        "server_names": names,
        "listens": listens,
        "kind": kind,
        "ssl": ssl,
        "certificate": certificate,
        "parse_error": parsed.error or "",
    }


def list_sites(inst: dict) -> dict:
    prefix = os.path.abspath(inst["prefix"])
    site_dir = os.path.join(prefix, SITE_DIR)
    tree = load_tree(target_of(inst).conf_abs, prefix)
    loaded = {os.path.realpath(src.path) for src in tree.all_files()}

    sites: List[dict] = []
    if os.path.isdir(site_dir):
        for name in sorted(os.listdir(site_dir)):
            if not FILENAME_RE.match(name) and not DISABLED_RE.match(name):
                continue
            path = os.path.join(site_dir, name)
            if not os.path.isfile(path):
                continue
            try:
                text, _ = read_text(path)
            except OSError:
                continue
            sites.append(
                _describe(path, text, not name.endswith(DISABLED_SUFFIX), os.path.realpath(path) in loaded)
            )

    sites.sort(key=lambda item: (not item["enabled"], item["name"]))
    return {
        "sites": sites,
        "include_configured": bool(tree.root and _has_include(tree.root)),
    }


def _site_path(inst: dict, name: str) -> Tuple[str, str]:
    name = (name or "").strip()
    if os.path.basename(name) != name or ".." in name:
        raise AppError(t("site.filename_invalid"))
    if not FILENAME_RE.match(name) and not DISABLED_RE.match(name):
        raise AppError(t("site.filename_invalid"))
    path = os.path.join(os.path.abspath(inst["prefix"]), SITE_DIR, name)
    if not os.path.isfile(path):
        raise AppError(t("site.not_found", name=name), 404)
    return name, path


def set_site_enabled(inst: dict, name: str, enabled: bool, operator: str = "", reload: bool = True) -> dict:
    name, path = _site_path(inst, name)
    if enabled and not name.endswith(DISABLED_SUFFIX):
        raise AppError(t("site.already_enabled", name=name))
    if not enabled and name.endswith(DISABLED_SUFFIX):
        raise AppError(t("site.already_disabled", name=name))

    target_name = name[: -len(DISABLED_SUFFIX)] if enabled else name + DISABLED_SUFFIX
    target_path = os.path.join(os.path.dirname(path), target_name)
    if os.path.exists(target_path):
        raise AppError(t("site.target_exists", name=target_name))

    text, _ = read_text(path)
    message = t("site.enable_message" if enabled else "site.disable_message", name=name)
    result = apply_changes(
        inst,
        [
            {"path": target_path, "content": text},
            {"path": path, "delete": True, "base_hash": file_sha(path)},
        ],
        message=message,
        operator=operator,
        reload=reload,
    )
    result.update({"name": target_name, "rel": f"{SITE_DIR}/{target_name}", "enabled": enabled})
    return result


def delete_site(inst: dict, name: str, operator: str = "", reload: bool = True) -> dict:
    name, path = _site_path(inst, name)
    result = apply_changes(
        inst,
        [{"path": path, "delete": True, "base_hash": file_sha(path)}],
        message=t("site.delete_message", name=name),
        operator=operator,
        reload=reload,
    )
    result.update({"name": name, "rel": f"{SITE_DIR}/{name}"})
    return result