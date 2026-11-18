"""结构化表单：把白名单指令映射为表单模型，保存时生成最小文本补丁。"""

import os
from typing import Dict, List, Optional

from ..core.errors import AppError
from ..nginx import writer
from ..nginx.ast import Node, SourceFile, TextEdit
from ..nginx.includes import ConfTree, load_tree
from ..nginx.process import find_directive
from .apply import apply_changes, file_sha
from .instances import target_of

SERVER_FIELDS = [
    "listen",
    "server_name",
    "root",
    "index",
    "client_max_body_size",
    "ssl_certificate",
    "ssl_certificate_key",
    "return",
    "rewrite",
    "charset",
    "autoindex",
    "access_log",
    "error_log",
]
MULTI_SERVER_FIELDS = {"listen"}
LOCATION_FIELDS = [
    "proxy_pass",
    "root",
    "index",
    "try_files",
    "return",
    "rewrite",
    "alias",
    "client_max_body_size",
    "proxy_read_timeout",
    "proxy_connect_timeout",
    "proxy_send_timeout",
    "proxy_set_header",
    "add_header",
]
MULTI_LOCATION_FIELDS = {"proxy_set_header", "add_header"}
UPSTREAM_FIELDS = ["server", "keepalive", "least_conn", "ip_hash", "random", "hash"]

ALLOWED_NAMES = set(SERVER_FIELDS) | set(LOCATION_FIELDS) | set(UPSTREAM_FIELDS) | {"location", "upstream"}
READONLY_SERVER = {"ssl_certificate", "ssl_certificate_key"}


def _iter_nodes(nodes: List[Node]):
    for node in nodes:
        yield node
        for sub in node.included:
            yield from _iter_nodes(sub.nodes)
        if node.block:
            yield from _iter_nodes(node.block)


def _directive(node: Node) -> dict:
    return {
        "file": node.file,
        "start": node.name_start,
        "args": list(node.args),
        "line": node.line,
        "text": " ".join([node.name, *node.args]),
    }


def _collect(nodes: List[Node], names: List[str]) -> Dict[str, List[dict]]:
    result: Dict[str, List[dict]] = {name: [] for name in names}
    for node in nodes:
        if node.name in result:
            result[node.name].append(_directive(node))
    return result


def _block_nodes(node: Node) -> List[Node]:
    """展开块内的 include（include 指令本身保留在未知指令里）。"""
    out: List[Node] = []

    def walk(nodes):
        for n in nodes:
            out.append(n)
            for sub in n.included:
                walk(sub.nodes)

    walk(node.block or [])
    return out


def _location_model(node: Node) -> dict:
    children = _block_nodes(node)
    fields = _collect(children, LOCATION_FIELDS)
    nested = [
        _location_model(n)
        for n in children
        if n.name == "location" and n.block is not None
    ]
    local_names = set(LOCATION_FIELDS) | {"location", "include", "if"}
    unknown = sorted({n.name for n in children if n.name not in local_names})
    return {
        "id": f"{node.file}:{node.name_start}",
        "file": node.file,
        "start": node.name_start,
        "line": node.line,
        "modifier": node.args[0] if len(node.args) > 1 else "",
        "path": node.args[-1] if node.args else "",
        "args": list(node.args),
        "fields": fields,
        "locations": nested,
        "unknown": unknown,
    }


def _server_model(node: Node) -> dict:
    children = _block_nodes(node)
    fields = _collect(children, SERVER_FIELDS)
    locations = [_location_model(n) for n in children if n.name == "location" and n.block is not None]
    local_names = set(SERVER_FIELDS) | {"location", "include", "ssl_protocols", "ssl_ciphers", "ssl_session_cache"}
    unknown = sorted({n.name for n in children if n.name not in local_names})
    return {
        "id": f"{node.file}:{node.name_start}",
        "file": node.file,
        "start": node.name_start,
        "line": node.line,
        "fields": fields,
        "locations": locations,
        "unknown": unknown,
        "listen_count": len(fields.get("listen", [])),
    }


def _upstream_model(node: Node) -> dict:
    children = _block_nodes(node)
    fields = _collect(children, UPSTREAM_FIELDS)
    unknown = sorted({n.name for n in children if n.name not in set(UPSTREAM_FIELDS) | {"include"}})
    return {
        "id": f"{node.file}:{node.name_start}",
        "file": node.file,
        "start": node.name_start,
        "line": node.line,
        "name": node.args[0] if node.args else "",
        "fields": fields,
        "unknown": unknown,
    }


def _http_nodes(tree: ConfTree) -> Optional[Node]:
    if not tree.root:
        return None
    return find_directive(tree.root.nodes, "http")


def get_form(inst: dict) -> dict:
    target = target_of(inst)
    tree = load_tree(target.conf_abs, inst["prefix"])
    http = _http_nodes(tree)
    hashes = {src.path: file_sha(src.path) for src in tree.all_files()}
    if http is None:
        return {
            "readonly": True,
            "reason": "主配置中没有找到 http 块",
            "servers": [],
            "upstreams": [],
            "files": hashes,
            "errors": tree.errors,
        }
    nodes = list(_iter_nodes(http.block or []))
    servers = [_server_model(n) for n in nodes if n.name == "server" and n.block is not None]
    upstreams = [_upstream_model(n) for n in nodes if n.name == "upstream" and n.block is not None]
    return {
        "readonly": bool(tree.errors),
        "reason": "; ".join(tree.errors) if tree.errors else "",
        "servers": servers,
        "upstreams": upstreams,
        "files": hashes,
        "fields": {
            "server": SERVER_FIELDS,
            "server_multi": sorted(MULTI_SERVER_FIELDS),
            "location": LOCATION_FIELDS,
            "location_multi": sorted(MULTI_LOCATION_FIELDS),
            "upstream": UPSTREAM_FIELDS,
        },
    }


def _find_node(tree: ConfTree, file: str, start: int) -> Node:
    src = tree.get(file)
    if src is None:
        raise AppError("文件已被删除，请刷新页面", 409)
    for node in src.nodes:
        for n in node.walk():
            if n.name_start == start and n.file == src.path:
                return n
    raise AppError("配置位置已失效（可能被其他修改影响），请刷新页面", 409)


def save_form(inst: dict, payload: dict, operator: str = "") -> dict:
    target = target_of(inst)
    tree = load_tree(target.conf_abs, inst["prefix"])
    edits_by_file: Dict[str, List[TextEdit]] = {}

    def add(src: SourceFile, edit: TextEdit):
        edits_by_file.setdefault(src.path, []).append(edit)

    for item in payload.get("edits") or []:
        file = item.get("file")
        start = item.get("start")
        if not file or start is None:
            raise AppError("表单修改缺少定位信息")
        src = tree.get(file)
        if src is None:
            raise AppError("文件不存在或已变更，请刷新页面", 409)
        node = _find_node(tree, file, int(start))
        if node.name not in ALLOWED_NAMES:
            raise AppError(f"不允许通过表单修改指令: {node.name}")
        if item.get("delete"):
            if node.name in ("listen", "server", "location", "upstream"):
                # 删除 listen 是允许的，但删块请走删除接口
                if node.name != "listen":
                    raise AppError(f"不支持在表单中删除 {node.name} 块")
            add(src, writer.delete_node(src, node))
        else:
            args = item.get("args")
            if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
                raise AppError("参数格式错误")
            add(src, writer.set_args(src, node, args))

    for item in payload.get("inserts") or []:
        file = item.get("file")
        name = item.get("name")
        args = item.get("args") or []
        if not file or not name:
            raise AppError("新增指令缺少文件或名称")
        if name not in ALLOWED_NAMES:
            raise AppError(f"不允许通过表单新增指令: {name}")
        if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
            raise AppError("参数格式错误")
        src = tree.get(file)
        if src is None:
            raise AppError("文件不存在，请刷新页面", 409)
        if item.get("parent_start") is not None:
            parent = _find_node(tree, file, int(item["parent_start"]))
            if parent.block is None:
                raise AppError("目标位置不是块，无法插入")
            add(src, writer.append_child(src, parent, args, name))
        elif item.get("after_start") is not None:
            anchor = _find_node(tree, file, int(item["after_start"]))
            add(src, writer.insert_after(src, anchor, args, name))
        else:
            raise AppError("新增指令缺少插入位置")

    if not edits_by_file:
        raise AppError("没有需要保存的表单修改")

    changes = []
    for path, edits in edits_by_file.items():
        src = tree.get(path)
        try:
            content = writer.apply_file_edits(src, edits)
        except ValueError as exc:
            raise AppError(str(exc), 400)
        changes.append({"path": path, "content": content, "base_hash": file_sha(path)})

    return apply_changes(
        inst,
        changes,
        message=payload.get("message") or "表单修改",
        operator=operator,
        reload=bool(payload.get("reload", True)),
        trigger="form",
    )