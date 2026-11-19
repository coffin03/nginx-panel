"""配置体检：基于 AST 的静态规则检查，输出分级问题列表。

只做只读分析，不修改任何文件。
"""

import os
from typing import List

from ..core.i18n import t
from .instances import load_instance_tree

LEVEL_ORDER = {"error": 0, "warning": 1, "info": 2}
WEAK_TLS = {"SSLv2", "SSLv3", "TLSv1", "TLSv1.1"}


def _item(level: str, code: str, message: str, file: str = "", line: int = 0) -> dict:
    return {"level": level, "code": code, "message": message, "file": file, "line": line}


def _child_args(node, name: str) -> List[List[str]]:
    return [c.args for c in (node.block or []) if c.name == name and c.args]


def _port(listen_args: List[str]) -> str:
    if not listen_args:
        return "80"
    value = listen_args[0]
    if value.startswith("unix:"):
        return value
    return value.rsplit(":", 1)[-1]


def _resolve(value: str, prefix: str) -> str:
    return value if os.path.isabs(value) else os.path.join(prefix, value)


def collect_checks(inst: dict) -> dict:
    tree = load_instance_tree(inst)
    prefix = inst["prefix"]
    items: List[dict] = []

    for src in tree.all_files():
        if src.error:
            items.append(_item("error", "parse", t("check.parse_error", error=src.error), src.path))

    servers = [n for n in tree.flatten_nodes() if n.name == "server" and n.block is not None]
    http = next((n for n in (tree.root.nodes if tree.root else []) if n.name == "http" and n.block), None)
    http_protocols = [v for args in _child_args(http, "ssl_protocols") for v in args] if http else []

    # 1. 重复的 server_name（同一端口）
    seen = set()
    for node in servers:
        names = [v for args in _child_args(node, "server_name") for v in args if v and v != "_"]
        listens = _child_args(node, "listen")
        ports = {_port(args) for args in listens} or {"80"}
        for name in names:
            for port in ports:
                key = (name.lower(), port)
                if key in seen:
                    items.append(
                        _item(
                            "warning",
                            "duplicate_server_name",
                            t("check.duplicate_server_name", name=name, port=port),
                            node.file,
                            node.line,
                        )
                    )
                seen.add(key)

    # 2. TLS 与证书
    for node in servers:
        cert_nodes = [n for n in node.walk() if n.name == "ssl_certificate" and n.args]
        key_nodes = [n for n in node.walk() if n.name == "ssl_certificate_key" and n.args]
        for cert in cert_nodes:
            if cert.args[0].startswith("data:"):
                continue
            path = _resolve(cert.args[0], prefix)
            if not os.path.isfile(path):
                items.append(
                    _item("error", "cert_missing", t("check.cert_missing", path=cert.args[0]), cert.file, cert.line)
                )
        for key_node in key_nodes:
            path = _resolve(key_node.args[0], prefix)
            if not os.path.isfile(path):
                items.append(
                    _item(
                        "error",
                        "key_missing",
                        t("check.key_missing", path=key_node.args[0]),
                        key_node.file,
                        key_node.line,
                    )
                )

        protocols = [v for args in _child_args(node, "ssl_protocols") for v in args] or http_protocols
        weak = [v for v in protocols if v in WEAK_TLS]
        if weak and protocols:
            items.append(
                _item(
                    "warning",
                    "tls_weak",
                    t("check.tls_weak", protocols=", ".join(weak)),
                    node.file,
                    node.line,
                )
            )
        if (cert_nodes or key_nodes) and not protocols:
            items.append(
                _item("info", "tls_default", t("check.tls_default"), node.file, node.line)
            )

    # 3. 站点根目录
    for node in tree.flatten_nodes():
        if node.name != "root" or not node.args:
            continue
        value = node.args[0]
        if "$" in value:
            continue
        path = _resolve(value, prefix)
        if not os.path.isdir(path):
            items.append(_item("warning", "root_missing", t("check.root_missing", path=value), node.file, node.line))

    # 4. conf.d 站点是否被 include
    site_dir = os.path.join(prefix, "conf.d")
    site_files = []
    if os.path.isdir(site_dir):
        site_files = [n for n in os.listdir(site_dir) if n.endswith(".conf")]
    included = False
    if http is not None:
        for node in http.walk():
            if node.is_include and node.args and "conf.d" in node.args[0].replace("\\", "/"):
                included = True
                break
    if site_files and not included and http is not None:
        items.append(
            _item(
                "warning",
                "confd_not_included",
                t("check.confd_not_included", n=len(site_files)),
                http.file,
                http.line,
            )
        )

    # 5. http 级常见项
    if http is not None:
        for name, code, level in (
            ("gzip", "gzip_off", "info"),
            ("client_max_body_size", "body_size", "info"),
        ):
            if not any(n.name == name for n in http.walk()):
                items.append(_item(level, code, t(f"check.{code}"), http.file, http.line))
        tokens = [v for args in _child_args(http, "server_tokens") for v in args]
        if tokens and tokens[0] != "off":
            items.append(
                _item("info", "server_tokens", t("check.server_tokens"), http.file, http.line)
            )

    items.sort(key=lambda x: (LEVEL_ORDER.get(x["level"], 9), x["file"], x["line"]))
    summary = {level: sum(1 for i in items if i["level"] == level) for level in LEVEL_ORDER}
    return {"items": items, "summary": summary}