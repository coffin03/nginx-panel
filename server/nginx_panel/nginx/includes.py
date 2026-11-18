"""配置文件加载与 include 递归展开。

- 所有文件按二进制读取，使用 utf-8 + surrogateescape 解码，保证写回时字节级一致。
- include 相对路径优先按 nginx prefix 解析，找不到再退回包含者所在目录。
- 支持通配符，限制递归深度与文件数量，避免环形 include 导致死循环。
"""

import glob
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .ast import Node, SourceFile
from .parser import parse_source

MAX_DEPTH = 16
MAX_FILES = 800


class ConfTree:
    def __init__(self, root_path: str, prefix: str):
        self.root_path = os.path.abspath(root_path)
        self.prefix = os.path.abspath(prefix)
        self.root: Optional[SourceFile] = None
        self.files: Dict[str, SourceFile] = {}
        self.errors: List[str] = []

    def get(self, path: str) -> Optional[SourceFile]:
        return self.files.get(_key(path))

    def all_files(self) -> List[SourceFile]:
        return list(self.files.values())

    def flatten_nodes(self):
        """逻辑树：把 include 展开后的节点也遍历出来。"""

        def walk(nodes):
            for n in nodes:
                yield n
                for sub in n.included:
                    yield from walk(sub.nodes)
                if n.block:
                    yield from walk(n.block)

        if self.root:
            yield from walk(self.root.nodes)


def _key(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


def read_text(path: str) -> tuple[str, bool]:
    with open(path, "rb") as fh:
        data = fh.read()
    bom = data.startswith(b"\xef\xbb\xbf")
    if bom:
        data = data[3:]
    return data.decode("utf-8", "surrogateescape"), bom


def write_text(path: str, text: str, bom: bool = False) -> None:
    data = text.encode("utf-8", "surrogateescape")
    if bom:
        data = b"\xef\xbb\xbf" + data
    with open(path, "wb") as fh:
        fh.write(data)


def resolve_include(pattern: str, prefix: str, base_dir: str) -> List[str]:
    candidates = []
    if os.path.isabs(pattern):
        candidates.append(pattern)
    else:
        candidates.append(os.path.join(prefix, pattern))
        candidates.append(os.path.join(base_dir, pattern))

    found: List[str] = []
    for cand in candidates:
        matches = sorted(glob.glob(cand))
        files = [m for m in matches if os.path.isfile(m)]
        if files:
            found = files
            break
    return found


def load_tree(conf_path: str, prefix: str) -> ConfTree:
    tree = ConfTree(conf_path, prefix)
    if not os.path.isfile(tree.root_path):
        tree.errors.append(f"主配置不存在: {tree.root_path}")
        return tree
    tree.root = _expand(tree.root_path, tree.prefix, tree, [], 0, base_dir=os.path.dirname(tree.root_path))
    return tree


def _expand(path: str, prefix: str, tree: ConfTree, stack: List[str], depth: int, base_dir: str = "") -> SourceFile:
    abspath = os.path.abspath(path)
    key = _key(abspath)
    existing = tree.files.get(key)
    if existing is not None:
        return existing

    if depth > MAX_DEPTH:
        src = SourceFile(path=abspath, text="", error="include 层级过深")
        tree.files[key] = src
        tree.errors.append(f"{abspath}: include 层级过深")
        return src
    if len(tree.files) >= MAX_FILES:
        src = SourceFile(path=abspath, text="", error="include 文件数超过上限")
        tree.files[key] = src
        tree.errors.append(f"{abspath}: include 文件数超过上限")
        return src

    try:
        text, bom = read_text(abspath)
    except OSError as exc:
        src = SourceFile(path=abspath, text="", error=f"无法读取: {exc}")
        tree.files[key] = src
        tree.errors.append(f"{abspath}: 无法读取: {exc}")
        return src

    src = parse_source(text, abspath)
    src.bom = bom
    tree.files[key] = src
    if src.error:
        tree.errors.append(f"{abspath}: {src.error}")

    stack = stack + [key]
    for node in src.nodes:
        _expand_node(node, prefix, tree, stack, depth, os.path.dirname(abspath))
    return src


def _expand_node(node: Node, prefix: str, tree: ConfTree, stack: List[str], depth: int, base_dir: str) -> None:
    if node.is_include and node.args:
        pattern = node.args[0]
        files = resolve_include(pattern, prefix, base_dir)
        if not files:
            node.include_error = f"未匹配到文件: {pattern}"
            return
        for fpath in files:
            if _key(fpath) in stack:
                node.include_error = f"检测到循环 include: {fpath}"
                continue
            child = _expand(fpath, prefix, tree, stack, depth + 1, base_dir=os.path.dirname(fpath))
            node.included.append(child)
    for child in node.block or []:
        _expand_node(child, prefix, tree, stack, depth, base_dir)


def find_node_by_position(tree: ConfTree, file_path: str, name_start: int) -> Optional[Node]:
    src = tree.get(file_path)
    if not src:
        return None
    for node in src.nodes:
        for n in node.walk():
            if n.file == src.path and n.name_start == name_start:
                return n
    return None